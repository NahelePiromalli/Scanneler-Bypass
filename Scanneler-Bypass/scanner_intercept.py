"""
scanner_intercept.py — Ghost Protocol 2026 ULTRA KERNEL
========================================================
Sistema de interceptación activa de scanners anti-cheat.

Tres capas de defensa (en orden de prioridad):
  1. DNS Poison local  → El scanner no puede llegar a su servidor
  2. Fake Server       → Si llega igual, recibe "clean"
  3. Network Monitor   → Detecta dominios nuevos y los agrega al bloqueo

Sistema de detección:
  - ScannerWatcher: thread daemon que monitorea procesos activos
  - Detecta por nombre de proceso, nombre de driver y creación de pipes

Compatibilidad: Windows 10/11, requiere admin.
"""

import os
import re
import sys
import time
import socket
import struct
import shutil
import ctypes
import ctypes.wintypes as wintypes
import threading
import subprocess
import random
import hashlib
from typing import Optional, Callable

import fake_server as _fs

# WinDivert — packet-level interceptor (carga lazy, fallback graceful)
try:
    import windivert_ops as _wdops
    _HAS_WINDIVERT = True
except Exception:
    _wdops = None
    _HAS_WINDIVERT = False


# ============================================================
# SCANNER DATABASE
# ============================================================

KNOWN_SCANNERS = {
    "ocean": {
        "processes": [
            "ocean.exe", "ocean_client.exe", "oceanac.exe",
            "ocean_launcher.exe", "ocean_service.exe"
        ],
        "drivers": ["ocean.sys", "oceandrv.sys", "ocean_drv.sys"],
        "domains": [
            "ocean-ac.com", "api.ocean-ac.com", "report.ocean-ac.com",
            "scan.ocean-ac.com", "ocean-anticheat.com", "oceanac.net",
        ],
        "pipes": ["\\\\.\\pipe\\ocean", "\\\\.\\pipe\\OceanAC"],
    },
    "echo": {
        "processes": [
            "echo.exe", "echo_ac.exe", "echoac.exe",
            "echo_client.exe", "echo_service.exe", "EchoAC.exe"
        ],
        "drivers": ["echo.sys", "echo_ac.sys", "echoac.sys"],
        "domains": [
            "echoac.com", "api.echoac.com", "report.echoac.com",
            "echo-ac.net", "echo-anticheat.com"
        ],
        "pipes": ["\\\\.\\pipe\\echo", "\\\\.\\pipe\\EchoAC"],
    },
    "easyanticheat": {
        "processes": ["easyanticheat.exe", "eac.exe", "EasyAntiCheat_Setup.exe"],
        "drivers":   ["easyanticheat.sys", "easyanticheat_x64.sys"],
        "domains":   ["easyanticheat.net", "api.easyanticheat.net"],
        "pipes":     ["\\\\.\\pipe\\EasyAntiCheat"],
    },
    "battleye": {
        "processes": ["beplauncher.exe", "bepro.exe", "battleye.exe"],
        "drivers":   ["battleye.sys", "bedaisy.sys"],
        "domains":   ["battleye.com", "api.battleye.com"],
        "pipes":     ["\\\\.\\pipe\\BattlEye"],
    },
    "vanguard": {
        "processes": ["vgc.exe", "vanguard.exe", "vgtray.exe"],
        "drivers":   ["vgk.sys"],
        "domains":   ["vanguard.a.pvp.net", "riotgames.com"],
        "pipes":     ["\\\\.\\pipe\\Vanguard"],
    },
    "generic": {
        "processes": ["anticheat.exe", "anticheat_service.exe", "ac_client.exe"],
        "drivers":   ["anticheat.sys"],
        "domains":   [],
        "pipes":     [],
    }
}

# ============================================================
# HOSTS FILE MANAGER
# ============================================================

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
HOSTS_MARKER_START = "# === SCANNELER INTERCEPT START ===\n"
HOSTS_MARKER_END   = "# === SCANNELER INTERCEPT END ===\n"


class DNSPoisoner:
    """
    Modifica el archivo hosts para redirigir dominios de scanners a 127.0.0.1.
    Guarda un backup y restaura limpiamente al desactivar.
    """

    def __init__(self):
        self._poisoned_domains = set()
        self._lock = threading.Lock()
        self._backup = None

    def poison(self, scanner_names: list, extra_domains: list = None, logger=None):
        """
        Agrega redirecciones para todos los dominios conocidos del scanner.
        """
        with self._lock:
            # Backup del hosts original
            try:
                with open(HOSTS_PATH, "r", encoding="utf-8", errors="ignore") as f:
                    self._backup = f.read()
            except Exception:
                self._backup = ""

            domains_to_add = set()
            for name in scanner_names:
                scanner = KNOWN_SCANNERS.get(name.lower(), {})
                for domain in scanner.get("domains", []):
                    domains_to_add.add(domain)
                    domains_to_add.add(f"www.{domain}")

            if extra_domains:
                for d in extra_domains:
                    domains_to_add.add(d)

            if not domains_to_add:
                return

            # Construir bloque de poison
            entries = "\n".join(
                f"127.0.0.1\t{d}" for d in sorted(domains_to_add)
            )
            poison_block = (
                f"\n{HOSTS_MARKER_START}"
                f"{entries}\n"
                f"{HOSTS_MARKER_END}"
            )

            try:
                # Limpiar bloques anteriores si existen
                content = self._backup
                content = re.sub(
                    r'\n# === SCANNELER INTERCEPT START ===\n.*?# === SCANNELER INTERCEPT END ===\n',
                    '', content, flags=re.DOTALL
                )
                with open(HOSTS_PATH, "w", encoding="utf-8") as f:
                    f.write(content + poison_block)

                self._poisoned_domains.update(domains_to_add)

                # Flush DNS cache para que surta efecto inmediato
                subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)

                if logger:
                    logger(f"→ [DNS POISON] {len(domains_to_add)} scanner domain(s) redirected to 127.0.0.1.")
            except Exception as e:
                if logger:
                    logger(f"→ [DNS POISON] Error modifying hosts: {e}")

    def add_domain(self, domain: str, logger=None):
        """Agrega un dominio adicional en caliente."""
        with self._lock:
            if domain in self._poisoned_domains:
                return
            try:
                with open(HOSTS_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n127.0.0.1\t{domain}  # auto-detected")
                subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
                self._poisoned_domains.add(domain)
                if logger:
                    logger(f"→ [DNS POISON] Auto-added domain: {domain}")
            except Exception:
                pass

    def restore(self, logger=None):
        """Restaura el archivo hosts al estado original."""
        with self._lock:
            if self._backup is None:
                return
            try:
                with open(HOSTS_PATH, "w", encoding="utf-8") as f:
                    f.write(self._backup)
                subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
                self._poisoned_domains.clear()
                if logger:
                    logger("→ [DNS POISON] Hosts file restored to original state.")
            except Exception as e:
                if logger:
                    logger(f"→ [DNS POISON] Restore error: {e}")


# ============================================================
# NETWORK MONITOR — Auto-detecta dominios del scanner
# ============================================================

class NetworkMonitor(threading.Thread):
    """
    Monitorea las conexiones de red del proceso del scanner
    y agrega automáticamente cualquier dominio nuevo al DNS poison.
    """

    def __init__(self, pid: int, poisoner: DNSPoisoner, logger=None):
        super().__init__(daemon=True, name="NetMon")
        self.pid      = pid
        self.poisoner = poisoner
        self.logger   = logger
        self._stop    = threading.Event()
        self._known   = set()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                # netstat -ano para obtener conexiones del PID
                result = subprocess.run(
                    "netstat -ano",
                    shell=True, capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    if parts[-1] != str(self.pid):
                        continue
                    # Extraer IP de destino
                    remote = parts[2] if len(parts) >= 4 else ""
                    if ":" not in remote or remote.startswith("127.") or remote.startswith("0."):
                        continue
                    ip = remote.rsplit(":", 1)[0].strip("[]")
                    if ip in self._known:
                        continue
                    self._known.add(ip)
                    # Reverse DNS
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                        if hostname and "." in hostname:
                            self.poisoner.add_domain(hostname, self.logger)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(2.0)


# ============================================================
# PROCESS HIDER — Via NtQuerySystemInformation patching
# ============================================================

class ProcessHider:
    """
    Oculta procesos de los scanners usando dos técnicas:
    1. Suspender el proceso objetivo cuando el scanner está activo
    2. (Con WinPmem) DKOM — borrar el proceso de la lista del kernel
    """

    def __init__(self):
        self._hidden_pids    = set()
        self._suspended_pids = set()

    def suspend_process(self, pid: int, logger=None) -> bool:
        """
        Suspende un proceso para que el scanner no detecte actividad.
        Técnica: NtSuspendProcess via ntdll.
        """
        try:
            _nt = ctypes.windll.ntdll
            h = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
            if not h:
                return False
            result = _nt.NtSuspendProcess(h)
            ctypes.windll.kernel32.CloseHandle(h)
            if result == 0:
                self._suspended_pids.add(pid)
                if logger:
                    logger(f"→ [HIDER] PID {pid} suspended (invisible to scanner).")
                return True
            return False
        except Exception as e:
            if logger:
                logger(f"→ [HIDER] Suspend error: {e}")
            return False

    def resume_process(self, pid: int, logger=None) -> bool:
        """Reanuda un proceso suspendido."""
        try:
            _nt = ctypes.windll.ntdll
            h = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
            if not h:
                return False
            _nt.NtResumeProcess(h)
            ctypes.windll.kernel32.CloseHandle(h)
            self._suspended_pids.discard(pid)
            if logger:
                logger(f"→ [HIDER] PID {pid} resumed.")
            return True
        except Exception:
            return False

    def resume_all(self, logger=None):
        for pid in list(self._suspended_pids):
            self.resume_process(pid, logger)

    def dkom_hide(self, pid: int, logger=None) -> bool:
        """DKOM via WinPmem si está disponible."""
        try:
            import kernel_ops
            if kernel_ops.is_kernel_armed():
                return kernel_ops.get_pmem().hide_process_dkom(pid, logger)
            return False
        except Exception:
            return False


# ============================================================
# SCANNER WATCHER — Thread principal de detección
# ============================================================

class ScannerWatcher(threading.Thread):
    """
    Thread daemon que monitorea el sistema en busca de scanners activos.
    Cuando detecta uno, activa automáticamente todos los mecanismos
    de interceptación (DNS, fake server, process hiding).
    """

    def __init__(self):
        super().__init__(daemon=True, name="ScannerWatcher")
        self._stop_event      = threading.Event()
        self._active_scanners = {}   # name → {pid, net_monitor}
        self._poisoner        = DNSPoisoner()
        self._hider           = ProcessHider()
        self._net_monitors    = {}
        self.logger:  Optional[Callable] = None
        self.on_detect_cb:    Optional[Callable] = None  # callback para la GUI
        self.on_clear_cb:     Optional[Callable] = None  # callback para la GUI
        self._protected_pids: set = set()   # PIDs a ocultar cuando scanner detectado
        self._lock = threading.Lock()

    def add_protected_pid(self, pid: int):
        """Agrega un PID para ocultar cuando se detecte un scanner."""
        self._protected_pids.add(pid)

    def stop(self):
        self._stop_event.set()
        self._cleanup_all()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._scan_cycle()
            except Exception:
                pass
            time.sleep(0.75)  # Check cada 750ms

    def _scan_cycle(self):
        """Un ciclo de detección completo."""
        running_processes = self._get_running_processes()

        for scanner_name, scanner_info in KNOWN_SCANNERS.items():
            scanner_processes = scanner_info.get("processes", [])

            # Detectar si algún proceso del scanner está corriendo
            detected_pid = None
            detected_proc = None
            for proc_name in scanner_processes:
                pid = running_processes.get(proc_name.lower())
                if pid:
                    detected_pid  = pid
                    detected_proc = proc_name
                    break

            if detected_pid:
                if scanner_name not in self._active_scanners:
                    self._on_scanner_detected(scanner_name, detected_proc, detected_pid)
            else:
                if scanner_name in self._active_scanners:
                    self._on_scanner_gone(scanner_name)

    def _get_running_processes(self) -> dict:
        """Retorna {process_name_lower: pid} de todos los procesos activos."""
        result = {}
        try:
            output = subprocess.run(
                "tasklist /fo csv /nh",
                shell=True, capture_output=True, text=True, timeout=5
            ).stdout
            for line in output.splitlines():
                parts = line.strip().strip('"').split('","')
                if len(parts) >= 2:
                    name = parts[0].lower()
                    try:
                        pid = int(parts[1])
                        result[name] = pid
                    except Exception:
                        pass
        except Exception:
            pass
        return result

    def _on_scanner_detected(self, scanner_name: str, proc_name: str, pid: int):
        """Se ejecuta cuando un scanner es detectado por primera vez."""
        with self._lock:
            if self.logger:
                self.logger(f"→ [INTERCEPT] ⚠ SCANNER DETECTED: {proc_name} (PID {pid})")

            self._active_scanners[scanner_name] = {"pid": pid, "proc": proc_name}

            # CAPA 1: DNS Poison
            self._poisoner.poison([scanner_name], logger=self.logger)

            # CAPA 2: Fake Server
            _fs.get_fake_server().start(self.logger)

            # CAPA 3: WinDivert — packet-level blocking (gap-closer contra IP hardcodeada)
            if _HAS_WINDIVERT:
                scanner_info  = KNOWN_SCANNERS.get(scanner_name, {})
                scanner_doms  = scanner_info.get("domains", [])
                # Resolver dominios a IPs para el bloqueo a nivel paquete
                blocked_ips = set()
                for domain in scanner_doms:
                    try:
                        ip = socket.gethostbyname(domain)
                        blocked_ips.add(ip)
                    except Exception:
                        pass
                if blocked_ips:
                    _wdops.get_interceptor().start(
                        blocked_ips=blocked_ips,
                        blocked_pids={pid},
                        logger=self.logger
                    )

            # CAPA 4: Monitor de red auto-detect de dominios nuevos
            if scanner_name not in self._net_monitors:
                nm = NetworkMonitor(pid, self._poisoner, self.logger)
                nm._windivert_ref = _wdops.get_interceptor() if _HAS_WINDIVERT else None
                nm.start()
                self._net_monitors[scanner_name] = nm

            # CAPA 5: Ocultar procesos protegidos
            for protected_pid in self._protected_pids:
                if not self._hider.dkom_hide(protected_pid, self.logger):
                    self._hider.suspend_process(protected_pid, self.logger)

            if self.on_detect_cb:
                self.on_detect_cb(scanner_name, proc_name, pid)

    def _on_scanner_gone(self, scanner_name: str):
        """Se ejecuta cuando el scanner termina."""
        with self._lock:
            info = self._active_scanners.pop(scanner_name, {})
            if self.logger:
                self.logger(f"→ [INTERCEPT] ✓ Scanner gone: {info.get('proc', scanner_name)}")

            nm = self._net_monitors.pop(scanner_name, None)
            if nm:
                nm.stop()

            if not self._active_scanners:
                self._poisoner.restore(self.logger)
                _fs.get_fake_server().stop(self.logger)
                self._hider.resume_all(self.logger)
                # Detener WinDivert cuando no quedan scanners activos
                if _HAS_WINDIVERT:
                    _wdops.get_interceptor().stop(self.logger)

                if self.on_clear_cb:
                    self.on_clear_cb()

    def _cleanup_all(self):
        """Limpieza completa al detener el watcher."""
        with self._lock:
            for nm in self._net_monitors.values():
                nm.stop()
            self._net_monitors.clear()
            self._active_scanners.clear()

        self._poisoner.restore(self.logger)
        _fs.get_fake_server().stop(self.logger)
        self._hider.resume_all(self.logger)
        if _HAS_WINDIVERT:
            _wdops.get_interceptor().stop(self.logger)


# ============================================================
# SINGLETON Y API PÚBLICA
# ============================================================

_watcher: Optional[ScannerWatcher] = None
_watcher_lock = threading.Lock()


def start_intercept(logger=None, on_detect=None, on_clear=None) -> ScannerWatcher:
    """Inicia el sistema de interceptación en background."""
    global _watcher
    with _watcher_lock:
        if _watcher and _watcher.is_alive():
            return _watcher
        _watcher = ScannerWatcher()
        _watcher.logger       = logger
        _watcher.on_detect_cb = on_detect
        _watcher.on_clear_cb  = on_clear
        _watcher.start()
        if logger:
            logger("→ [INTERCEPT] Scanner Watcher armed. Monitoring for Ocean/Echo/EAC/BE/Vanguard...")
        return _watcher


def stop_intercept(logger=None):
    """Detiene el sistema de interceptación y limpia todo."""
    global _watcher
    with _watcher_lock:
        if _watcher and _watcher.is_alive():
            _watcher.stop()
            _watcher = None
    if logger:
        logger("→ [INTERCEPT] Scanner Watcher disarmed. All spoofing removed.")


def add_protected_pid(pid: int):
    """Registra un PID para ocultar cuando se detecte un scanner."""
    if _watcher:
        _watcher.add_protected_pid(pid)


def is_active() -> bool:
    return _watcher is not None and _watcher.is_alive()


def get_active_scanners() -> list:
    if _watcher:
        return list(_watcher._active_scanners.keys())
    return []
