"""
windivert_ops.py — Ghost Protocol 2026 ULTRA KERNEL
=====================================================
Integración de WinDivert para interceptación de paquetes a nivel WFP.

A diferencia del DNS Poison (que opera en resolución de nombres),
WinDivert intercepta el paquete IP ya formado antes de salir al cable.
Funciona aunque el scanner tenga la IP hardcodeada o use DNS-over-HTTPS.

Descarga dinámica desde GitHub. Requiere admin.
"""

import os
import io
import struct
import socket
import ctypes
import ctypes.wintypes as wintypes
import threading
import zipfile
import tempfile
import random
import time
from typing import Optional, Set

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ============================================================
# CONSTANTS
# ============================================================

WINDIVERT_URL = (
    "https://github.com/basil00/Divert/releases/download/"
    "v2.2.0-A/WinDivert-2.2.0-A-win64.zip"
)

WINDIVERT_LAYER_NETWORK         = 0
WINDIVERT_LAYER_NETWORK_FORWARD = 1
WINDIVERT_FLAG_SNIFF            = 1
WINDIVERT_FLAG_DROP             = 4
WINDIVERT_FLAG_RECV_ONLY        = 64

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# IP protocols
IPPROTO_TCP = 6
IPPROTO_UDP = 17


# ============================================================
# WINDIVERT STRUCTURES
# ============================================================

class WINDIVERT_ADDRESS(ctypes.Structure):
    """WinDivert packet address metadata."""
    _fields_ = [
        ("Timestamp",       ctypes.c_int64),
        ("Layer",           ctypes.c_uint32, 8),
        ("Event",           ctypes.c_uint32, 8),
        ("Sniffed",         ctypes.c_uint32, 1),
        ("Outbound",        ctypes.c_uint32, 1),
        ("Loopback",        ctypes.c_uint32, 1),
        ("Impostor",        ctypes.c_uint32, 1),
        ("IPv6",            ctypes.c_uint32, 1),
        ("IPChecksum",      ctypes.c_uint32, 1),
        ("TCPChecksum",     ctypes.c_uint32, 1),
        ("UDPChecksum",     ctypes.c_uint32, 1),
        ("Reserved1",       ctypes.c_uint32, 8),
        ("Reserved2",       ctypes.c_uint32),
        ("IfIdx",           ctypes.c_uint32),
        ("SubIfIdx",        ctypes.c_uint32),
    ]


# GetExtendedTcpTable structures for PID → port mapping
class MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwState",      ctypes.c_ulong),
        ("dwLocalAddr",  ctypes.c_ulong),
        ("dwLocalPort",  ctypes.c_ulong),
        ("dwRemoteAddr", ctypes.c_ulong),
        ("dwRemotePort", ctypes.c_ulong),
        ("dwOwningPid",  ctypes.c_ulong),
    ]

class MIB_TCPTABLE_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwNumEntries", ctypes.c_ulong),
        ("table",        MIB_TCPROW_OWNER_PID * 4096),
    ]

TCP_TABLE_OWNER_PID_ALL = 5


# ============================================================
# WINDIVERT INTERCEPTOR
# ============================================================

class WinDivertInterceptor:
    """
    Intercepta paquetes de red a nivel WFP (Windows Filtering Platform).
    Bloquea los paquetes salientes hacia los servidores de scanners.
    
    Pipeline:
      WinDivertRecv → parse IP header → ¿dst en blocked_ips? → DROP
                                                               → WinDivertSend (re-inject)
    """

    def __init__(self):
        self._dll:         Optional[ctypes.CDLL] = None
        self._handle:      Optional[wintypes.HANDLE] = None
        self._thread:      Optional[threading.Thread] = None
        self._stop_event   = threading.Event()
        self._dll_path:    Optional[str] = None
        self._sys_path:    Optional[str] = None
        self._sys_installed = r"C:\Windows\System32\WinDivert64.sys"
        self.blocked_ips:  Set[str] = set()
        self.blocked_pids: Set[int] = set()
        self.active = False
        self._packets_dropped = 0
        self._lock = threading.Lock()

    # ----------------------------------------------------------
    # DOWNLOAD + LOAD
    # ----------------------------------------------------------

    def download_and_load(self, logger=None) -> bool:
        """Descarga WinDivert desde GitHub, extrae y carga la DLL."""
        if not _HAS_REQUESTS:
            if logger:
                logger("→ [WINDIVERT] requests not available.")
            return False
        try:
            if logger:
                logger("→ [WINDIVERT] Downloading WinDivert2 from GitHub...")
            resp = _requests.get(WINDIVERT_URL, timeout=30)
            if resp.status_code != 200:
                if logger:
                    logger(f"→ [WINDIVERT] HTTP {resp.status_code}")
                return False

            tmp = tempfile.gettempdir()
            rnd = random.randint(10000, 99999)

            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                names = zf.namelist()

                # Buscar los archivos x64 dentro del ZIP
                def find(suffix):
                    for n in names:
                        if n.endswith(suffix) and ("x64" in n or "64" in n):
                            return n
                    # Fallback sin filtro de directorio
                    for n in names:
                        if n.endswith(suffix):
                            return n
                    return None

                sys_entry = find("WinDivert64.sys")
                dll_entry = find("WinDivert64.dll")

                if not sys_entry or not dll_entry:
                    if logger:
                        logger("→ [WINDIVERT] Files not found in archive.")
                    return False

                self._sys_path = os.path.join(tmp, f"wds_{rnd}.sys")
                self._dll_path = os.path.join(tmp, f"wdd_{rnd}.dll")

                with open(self._sys_path, "wb") as f:
                    f.write(zf.read(sys_entry))
                with open(self._dll_path, "wb") as f:
                    f.write(zf.read(dll_entry))

            # El .sys debe estar en System32 para que WinDivert lo encuentre
            import shutil
            shutil.copy2(self._sys_path, self._sys_installed)

            # Cargar DLL
            self._dll = ctypes.CDLL(self._dll_path)
            self._setup_prototypes()

            if logger:
                logger("→ [WINDIVERT] ✓ Packet-level interceptor loaded.")
            return True

        except Exception as e:
            if logger:
                logger(f"→ [WINDIVERT] Load error: {e}")
            return False

    def _setup_prototypes(self):
        """Define los tipos de retorno y argumentos de las funciones WinDivert."""
        d = self._dll
        d.WinDivertOpen.restype           = wintypes.HANDLE
        d.WinDivertOpen.argtypes          = [ctypes.c_char_p, ctypes.c_int,
                                              ctypes.c_int16, ctypes.c_uint64]
        d.WinDivertRecv.restype           = wintypes.BOOL
        d.WinDivertRecv.argtypes          = [wintypes.HANDLE, ctypes.c_void_p,
                                              wintypes.UINT, ctypes.POINTER(wintypes.UINT),
                                              ctypes.POINTER(WINDIVERT_ADDRESS)]
        d.WinDivertSend.restype           = wintypes.BOOL
        d.WinDivertSend.argtypes          = [wintypes.HANDLE, ctypes.c_void_p,
                                              wintypes.UINT, ctypes.POINTER(wintypes.UINT),
                                              ctypes.POINTER(WINDIVERT_ADDRESS)]
        d.WinDivertClose.restype          = wintypes.BOOL
        d.WinDivertClose.argtypes         = [wintypes.HANDLE]
        d.WinDivertHelperCalcChecksums.restype  = wintypes.BOOL
        d.WinDivertHelperCalcChecksums.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                                    ctypes.POINTER(WINDIVERT_ADDRESS),
                                                    ctypes.c_uint64]

    # ----------------------------------------------------------
    # START / STOP
    # ----------------------------------------------------------

    def start(self, blocked_ips: set, blocked_pids: set, logger=None) -> bool:
        """
        Inicia el filtro de paquetes.
        Bloquea todo tráfico saliente hacia las IPs de scanners.
        """
        with self._lock:
            if self.active:
                return True
            if not self._dll:
                if not self.download_and_load(logger):
                    return False

            self.blocked_ips  = set(blocked_ips)
            self.blocked_pids = set(blocked_pids)
            self._stop_event.clear()
            self._packets_dropped = 0

            # Filtro: tráfico outbound IPv4 TCP o UDP
            filter_str = b"outbound and ip and (tcp or udp)"
            self._handle = self._dll.WinDivertOpen(
                filter_str, WINDIVERT_LAYER_NETWORK, 0, 0
            )
            if not self._handle or self._handle == INVALID_HANDLE_VALUE:
                err = ctypes.get_last_error()
                if logger:
                    logger(f"→ [WINDIVERT] WinDivertOpen failed: error {err}")
                return False

            self._thread = threading.Thread(
                target=self._intercept_loop,
                args=(logger,),
                daemon=True,
                name="WinDivertLoop"
            )
            self._thread.start()
            self.active = True
            if logger:
                logger(f"→ [WINDIVERT] Packet filter ACTIVE. "
                       f"Blocking {len(blocked_ips)} IP(s) from {len(blocked_pids)} PID(s).")
            return True

    def add_blocked_ip(self, ip: str):
        """Agrega una IP al bloqueo en caliente."""
        self.blocked_ips.add(ip)

    def stop(self, logger=None):
        """Para el filtro y limpia todos los archivos."""
        with self._lock:
            self._stop_event.set()
            if self._handle:
                try:
                    self._dll.WinDivertClose(self._handle)
                except Exception:
                    pass
                self._handle = None
            self.active = False

        if logger and self._packets_dropped:
            logger(f"→ [WINDIVERT] Stopped. {self._packets_dropped} packet(s) dropped.")

        # Limpiar archivos (sobreescribir antes de borrar)
        self._purge_files()

    def _purge_files(self):
        for path in [self._sys_path, self._dll_path, self._sys_installed]:
            if path and os.path.exists(path):
                try:
                    size = os.path.getsize(path)
                    with open(path, "r+b") as f:
                        f.write(os.urandom(size))
                    os.remove(path)
                except Exception:
                    pass

    # ----------------------------------------------------------
    # INTERCEPT LOOP
    # ----------------------------------------------------------

    def _get_tcp_pid_map(self) -> dict:
        """Retorna {local_port: pid} para todas las conexiones TCP activas."""
        result = {}
        try:
            table = MIB_TCPTABLE_OWNER_PID()
            size  = wintypes.DWORD(ctypes.sizeof(table))
            ret   = ctypes.windll.iphlpapi.GetExtendedTcpTable(
                ctypes.byref(table), ctypes.byref(size),
                True, socket.AF_INET, TCP_TABLE_OWNER_PID_ALL, 0
            )
            if ret == 0:
                for i in range(table.dwNumEntries):
                    row = table.table[i]
                    # Local port is in network byte order (big-endian)
                    local_port = socket.ntohs(row.dwLocalPort & 0xFFFF)
                    result[local_port] = row.dwOwningPid
        except Exception:
            pass
        return result

    def _intercept_loop(self, logger=None):
        """Loop principal de interceptación de paquetes."""
        packet   = ctypes.create_string_buffer(65535)
        addr     = WINDIVERT_ADDRESS()
        recv_len = wintypes.UINT(0)
        send_len = wintypes.UINT(0)

        while not self._stop_event.is_set():
            recv_len.value = 0
            ok = self._dll.WinDivertRecv(
                self._handle,
                packet, 65535,
                ctypes.byref(recv_len),
                ctypes.byref(addr)
            )
            if not ok:
                # Handle puede haberse cerrado
                if self._stop_event.is_set():
                    break
                time.sleep(0.01)
                continue

            pkt_len  = recv_len.value
            pkt_data = bytes(packet[:pkt_len])

            # Parse IPv4
            if len(pkt_data) < 20:
                self._reinject(packet, pkt_len, addr, send_len)
                continue

            ip_version = (pkt_data[0] >> 4)
            if ip_version != 4:
                self._reinject(packet, pkt_len, addr, send_len)
                continue

            # Destination IP
            dst_ip = socket.inet_ntoa(pkt_data[16:20])

            # Si el destino está en la lista de bloqueo → DROP
            if dst_ip in self.blocked_ips:
                # Check si el PID de origen es un scanner (o cualquier origen)
                # Drop silencioso — no re-inyectamos
                self._packets_dropped += 1
                continue

            # Si tenemos PIDs específicos a bloquear, verificar origen
            if self.blocked_pids:
                ip_hdr_len = (pkt_data[0] & 0x0F) * 4
                proto      = pkt_data[9]
                if proto in (IPPROTO_TCP, IPPROTO_UDP) and len(pkt_data) >= ip_hdr_len + 4:
                    src_port = struct.unpack_from(">H", pkt_data, ip_hdr_len)[0]
                    # Resolver PID para este puerto
                    tcp_map = self._get_tcp_pid_map()
                    owner_pid = tcp_map.get(src_port, 0)
                    if owner_pid in self.blocked_pids:
                        self._packets_dropped += 1
                        continue

            # Paquete limpio → re-inyectar
            self._reinject(packet, pkt_len, addr, send_len)

    def _reinject(self, packet, pkt_len, addr, send_len):
        """Re-inyecta un paquete no bloqueado."""
        send_len.value = 0
        try:
            self._dll.WinDivertSend(
                self._handle, packet, pkt_len,
                ctypes.byref(send_len), ctypes.byref(addr)
            )
        except Exception:
            pass


# ============================================================
# SINGLETON
# ============================================================

_interceptor = WinDivertInterceptor()

def get_interceptor() -> WinDivertInterceptor:
    return _interceptor
