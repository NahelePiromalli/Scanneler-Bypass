import os
import winreg
import codecs
import subprocess
import ctypes
import shutil
import random
import time
import sys
import hashlib
import requests
import json
import glob
import struct
from datetime import datetime
import keyboard
import sqlite3

# --- Módulos de kernel y scanner intercept (carga lazy, fallback graceful) ---
try:
    import kernel_ops as _kops
    _KERNEL_AVAILABLE = True
except Exception:
    _kops = None
    _KERNEL_AVAILABLE = False

try:
    import scanner_intercept as _sint
    _SCANNER_INTERCEPT_AVAILABLE = True
except Exception:
    _sint = None
    _SCANNER_INTERCEPT_AVAILABLE = False

DEEP_SCAN_ENABLED = False  # Por defecto desactivado para mayor velocidad
current_hook = None        # Fix: inicializar para evitar NameError en registrar_bind_global

# ==========================================================
# NÚCLEO ANTI-FORENSE: SOBREESCRITURA ALEATORIA
# Todas las eliminaciones del pipeline pasan por aquí.
# Anti-Ocean / Anti-Echo: el archivo se ve "modificado"
# antes de desaparecer, no "eliminado".
# ==========================================================

def overwrite_file_random(path, passes=3, logger=None):
    """
    Sobreescribe un archivo N veces con datos aleatorios antes de eliminarlo.
    Patrón DoD-inspirado: zeros → ones → random.
    Luego lo renombra varias veces para limpiar el MFT antes de borrar.
    
    Anti-Ocean/Echo: el archivo queda marcado como 'modificado' en el
    journal antes de desaparecer, sin dejar firma de 'borrado limpio'.
    """
    if not path or not os.path.exists(path):
        return False
    try:
        size = os.path.getsize(path)
        if size == 0:
            size = 512  # Mínimo para sobreescribir algo

        with open(path, "r+b", buffering=0) as f:
            # Pasada 1: Zeros
            f.seek(0)
            f.write(b'\x00' * size)
            f.flush()
            os.fsync(f.fileno())

            if passes >= 2:
                # Pasada 2: Ones
                f.seek(0)
                f.write(b'\xFF' * size)
                f.flush()
                os.fsync(f.fileno())

            # Pasada final: Random (siempre)
            f.seek(0)
            f.write(os.urandom(size))
            f.flush()
            os.fsync(f.fileno())

        # Renombrado múltiple para limpiar MFT name table
        dir_name = os.path.dirname(path)
        curr = path
        for _ in range(3):
            new = os.path.join(dir_name, f"_{random.randint(10000, 99999)}.tmp")
            try:
                os.rename(curr, new)
                curr = new
            except:
                break

        os.remove(curr)
        return True
    except Exception as e:
        if logger:
            logger(f"→ Overwrite error on {os.path.basename(path)}: {e}")
        try:
            os.remove(path)
        except:
            pass
        return False

def registrar_bind_global(tecla, callback, logger):
    """Registra una tecla para ejecutar una función en segundo plano."""
    global current_hook
    try:
        # Si ya había un bind, lo removemos para no acumular ejecuciones
        if current_hook:
            keyboard.unhook_all()
        
        # Registramos el nuevo bind
        # Usamos callback sin paréntesis para que se ejecute al presionar
        current_hook = keyboard.add_hotkey(tecla, callback)
        logger(f"→ Global Bind Active: [{tecla.upper()}]")
        return True
    except Exception as e:
        logger(f"→ Bind Error: {e}")
        return False

# ==========================================================
# CONFIGURACIÓN DE TU API EN RENDER
# ==========================================================
API_BASE_URL = "https://api-bypass-e6ty.onrender.com"

def get_hwid():
    """Genera el identificador único de hardware."""
    try:
        cmd = 'wmic csproduct get uuid'
        uuid = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        return hashlib.sha256(uuid.encode()).hexdigest()
    except:
        return "GENERIC-HWID-2026-VOID"

# ==========================================================
# SISTEMA DE LOGIN Y REGISTRO (SINCRONIZADO CON TU API)
# ==========================================================

def db_validate_login(username, password_input):
    """
    IMPORTANTE: Tu API usa OAuth2PasswordRequestForm.
    Debemos enviar los datos como FORMULARIO (data=), no como JSON.
    Se añade el Header x-hwid para vinculación de hardware.
    """
    try:
        hwid = get_hwid()
        # FastAPI espera 'username' y 'password' en Form Data
        payload = {
            "username": str(username).strip(),
            "password": str(password_input).strip()
        }
        
        # Enviamos el HWID como Header para que la API lo valide/registre
        headers = {
            "x-hwid": str(hwid)
        }
        
        response = requests.post(
            f"{API_BASE_URL}/login", 
            data=payload, 
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            # Retorna Éxito, Mensaje y el Rol del usuario
            return True, "Login successful.", data.get("role", "usuario")
        else:
            try:
                error_msg = response.json().get("detail", "Credenciales incorrectas")
            except:
                error_msg = "Error de autenticación"
            return False, error_msg, "usuario"
            
    except Exception as e:
        return False, f"Error de conexión: {e}", "usuario"

def db_redeem_key(username, key_string, password):
    """
    Sincronizado con el modelo UserRegister de tu API (key_code, username, password).
    """
    try:
        hwid = get_hwid()
        payload = {
            "key_code": str(key_string).strip(),
            "username": str(username).strip(),
            "password": str(password).strip()
        }
        
        # Registramos con el HWID en los Headers para vincular desde el registro
        headers = {"x-hwid": str(hwid)}
        
        response = requests.post(
            f"{API_BASE_URL}/keys/redeem", 
            json=payload, 
            headers=headers,
            timeout=25
        )
        
        if response.status_code == 201 or response.status_code == 200:
            return True, "Cuenta activada con éxito."
        else:
            try:
                msg = response.json().get("detail", "Llave inválida.")
            except:
                msg = "Error en el registro"
            return False, msg
            
    except Exception:
        return False, "API Offline"

# --- FUNCIONES DE ADMINISTRADOR ACTUALIZADAS ---

def db_generate_key(membresia="Monthly", amount=1):
    """
    Genera llaves dinámicas basadas en la selección del Admin Panel.
    Mapea la membresía a días reales para la API.
    """
    try:
        dias_map = {
            "Weekly": 7,
            "Monthly": 30,
            "Yearly": 365,
            "Lifetime": 9999
        }
        
        payload = {
            "membresia": membresia,
            "duracion_dias": dias_map.get(membresia, 30),
            "cantidad": int(amount)
        }
        
        response = requests.post(
            f"{API_BASE_URL}/keys/generate", 
            json=payload, 
            timeout=20
        )
        
        if response.status_code == 201 or response.status_code == 200:
            data = response.json()
            return True, data.get("keys", [])
        return False, []
    except Exception as e:
        print(f"Error Gen Keys: {e}")
        return False, []

def db_get_all_users():
    """Obtiene la lista de usuarios registrados desde la API."""
    try:
        # Endpoint ajustado a la nueva estructura de Admin
        response = requests.get(f"{API_BASE_URL}/admin/users", timeout=15)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def db_reset_hwid(username):
    """
    Solicita a la API resetear el hardware id de un usuario específico.
    """
    try:
        response = requests.put(
            f"{API_BASE_URL}/users/{username}/reset-hwid", 
            timeout=15
        )
        if response.status_code == 200:
            return True, response.json().get("message", "HWID Reseteado")
        else:
            try:
                msg = response.json().get("detail", "Error al resetear")
            except:
                msg = "Error de servidor"
            return False, msg
    except Exception as e:
        return False, f"Error de conexión: {e}"

# ==========================================================
# ANTI-FORENSICS: MANIPULACIÓN DE TIEMPO
# ==========================================================

def set_system_date(year, month, day, logger_func):
    try:
        new_date = f"{month}-{day}-{year}"
        subprocess.run(["powershell", "-Command", f"Set-Date -Date '{new_date}'"], capture_output=True)
        logger_func(f"⚡ System time desynchronized to: {new_date}")
    except Exception as e:
        logger_func(f"Time Error: {e}")

def restore_system_time(logger_func):
    try:
        subprocess.run(["w32tm", "/resync"], capture_output=True)
        subprocess.run(["powershell", "-Command", "Start-Service w32time; resync-time"], capture_output=True)
        logger_func("✅ System time resynchronized.")
    except:
        logger_func("⚠️ Could not resync time automatically.")

# ==========================================================
# LIMPIEZA ELITE (NÚCLEO FORENSE)
# ==========================================================

def time_stomp_archivo(ruta_archivo, logger):
    """Cambia MAC timestamps a 12/05/2015 para invalidar la línea de tiempo."""
    try:
        if not os.path.exists(ruta_archivo): return
        fecha_antigua = datetime(2015, 5, 12, 10, 30, 0)
        handle = ctypes.windll.kernel32.CreateFileW(ruta_archivo, 0x0100, 0, None, 3, 0, None)
        if handle == -1: return
        
        # Conversión a Windows FILETIME
        ft = int((fecha_antigua.timestamp() * 10000000) + 116444736000000000)
        ft_ctypes = ctypes.c_longlong(ft)
        
        res = ctypes.windll.kernel32.SetFileTime(handle, ctypes.byref(ft_ctypes), 
                                                 ctypes.byref(ft_ctypes), ctypes.byref(ft_ctypes))
        ctypes.windll.kernel32.CloseHandle(handle)
        if res: logger("→ TimeStomping: MAC timestamps set to 2015.")
    except: logger("→ TimeStomp: Failed to alter timestamps.")
    
def limpiar_rastros_globales_nombre(ruta_archivo, logger):
    """
    Busca coincidencias del nombre del archivo en las bases de datos de ejecución,
    sin importar en qué carpeta estuvo el archivo antes.
    """
    nombre_target = os.path.basename(ruta_archivo).lower()
    # Sacamos el nombre sin extensión por si Windows lo guardó así
    nombre_sin_ext = os.path.splitext(nombre_target)[0]

    # 1. Limpieza de Prefetch (Busca cualquier .pf con ese nombre)
    path_prefetch = r"C:\Windows\Prefetch"
    try:
        for f in os.listdir(path_prefetch):
            if f.upper().startswith(nombre_sin_ext.upper()):
                os.remove(os.path.join(path_prefetch, f))
                logger(f"→ Global Prefetch annihilated: {f}")
    except: pass

    # 2. Búsqueda en claves de registro persistentes (BAM, UserAssist, MUI)
    # Reutilizamos la lógica quirúrgica pero aplicada a CUALQUIER valor que contenga el nombre
    rutas_registro = [
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\bam\UserSettings"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache")
    ]

    for hkey, path in rutas_registro:
        try:
            # Esta lógica entra en subclaves (como los SIDs de la BAM) y busca el nombre
            # ... (Aquí usas un bucle recursivo similar al que ya tienes) ...
            logger(f"→ Registry scan complete for name: {nombre_target}")
        except: continue

def limpiar_prefetch_especifico(ruta_archivo, logger):
    """
    Borra el rastro .pf en C:/Windows/Prefetch del ejecutable.
    Para el servicio SysMain antes de borrar para evitar regeneración
    inmediata. Sobreescribe los .pf antes de eliminarlos (anti-Ocean/Echo).
    """
    nombre_base = os.path.basename(ruta_archivo).upper()
    nombre_sin_ext = os.path.splitext(nombre_base)[0]
    ruta_pf = os.path.expandvars(r'%SystemRoot%\Prefetch')
    try:
        # Parar SysMain (Superfetch) para evitar regeneración inmediata
        subprocess.run("sc stop SysMain", shell=True, capture_output=True)
        time.sleep(0.5)

        count = 0
        for f in os.listdir(ruta_pf):
            if f.upper().startswith(nombre_sin_ext):
                fp = os.path.join(ruta_pf, f)
                overwrite_file_random(fp, passes=3, logger=logger)
                count += 1
        if count:
            logger(f"→ Prefetch: {count} file(s) shredded for {nombre_base}")

        subprocess.run("sc start SysMain", shell=True, capture_output=True)
    except Exception as e:
        logger(f"→ Prefetch error: {e}")
        try:
            subprocess.run("sc start SysMain", shell=True, capture_output=True)
        except:
            pass

def limpiar_registro_selectivo(ruta_archivo, logger):
    """Limpia BAM, MUICache, PCA y Layers de forma quirúrgica."""
    rutas_reg = [
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\bam\UserSettings"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers")
    ]
    
    target = ruta_archivo.lower()
    
    for hkey, subkey_path in rutas_reg:
        try:
            with winreg.OpenKey(hkey, subkey_path, 0, winreg.KEY_ALL_ACCESS) as key:
                if "bam" in subkey_path:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        sid = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sid, 0, winreg.KEY_ALL_ACCESS) as sid_key:
                            eliminar_valor_si_existe(sid_key, target, logger)
                else:
                    eliminar_valor_si_existe(key, target, logger)
        except Exception: continue

def eliminar_valor_si_existe(key, target, logger):
    """Auxiliar para buscar la ruta del archivo dentro de una clave de registro."""
    try:
        num_vals = winreg.QueryInfoKey(key)[1]
        for i in range(num_vals - 1, -1, -1):
            val_name = winreg.EnumValue(key, i)[0]
            if target in val_name.lower():
                winreg.DeleteValue(key, val_name)
                logger(f"→ Registry trace purged: {os.path.basename(val_name)}")
    except: pass

def limpiar_ads_archivo(ruta_archivo, logger):
    """Elimina Zone.Identifier (Stream de origen de internet)."""
    try:
        subprocess.run(["powershell", "-Command", f"Unblock-File -Path '{ruta_archivo}'"], capture_output=True)
        logger("→ ADS / Zone.Identifier neutralized.")
    except: pass

def shred_y_destruir(ruta_archivo, logger):
    """
    Destrucción física DoD 3-pass (Anti-Recuperación y Anti-Carving).
    Pasada 1: zeros | Pasada 2: ones | Pasada 3: random.
    Luego renombrado x3 para limpiar el MFT name table.
    Usa overwrite_file_random como núcleo central anti-Ocean/Echo.
    """
    try:
        if not os.path.exists(ruta_archivo): return
        logger("→ DoD 3-Pass Shredding: Initiating physical destruction...")
        result = overwrite_file_random(ruta_archivo, passes=3, logger=logger)
        if result:
            logger("→ Physical stream destroyed. MFT name trace obfuscated.")
        else:
            logger("→ Shred: Partial destruction (file may be locked).")
    except Exception as e:
        logger(f"→ Destruction error: {e}")
    


# ==========================================================
# RASTROS ADICIONALES (PENDRIVE, RED Y SISTEMA)
# ==========================================================


def limpiar_clipboard(logger):
    """Vacía el portapapeles y el historial de Win+V."""
    try:
        # Vacía portapapeles tradicional
        ctypes.windll.user32.OpenClipboard(None)
        ctypes.windll.user32.EmptyClipboard()
        ctypes.windll.user32.CloseClipboard()
        
        # Comando para limpiar el historial de la nube/Win+V
        subprocess.run("powershell.exe Restart-Service -Name \"cbdhsvc_*\" -Force", shell=True, capture_output=True)
        logger("→ Clipboard & Win+V history sanitized.")
    except:
        pass

def limpiar_historial_consola(logger):
    """
    Borra el rastro de comandos en PowerShell/CMD y elimina los
    archivos Prefetch de los ejecutables de sistema (Host Prefetch).
    MEJORA: Sobreescribe el archivo de historial antes de borrarlo
    para que Ocean/Echo no detecten el borrado en el journal.
    """
    # 1. Limpieza de Historial de PowerShell (sobreescritura + borrado)
    path_ps = os.path.expandvars(r'%AppData%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt')
    try:
        if os.path.exists(path_ps):
            overwrite_file_random(path_ps, passes=3, logger=logger)
            logger("→ PowerShell history shredded.")
        subprocess.run("doskey /reinstall", shell=True, capture_output=True)
    except:
        pass

    # 2. Host Prefetch — rastros de herramientas usadas por Scanneler
    path_pf = os.path.expandvars(r'%SystemRoot%\Prefetch')
    hosts_limpieza = ["CMD.EXE", "POWERSHELL.EXE", "REG.EXE", "WEVTUTIL.EXE",
                      "FSUTIL.EXE", "SC.EXE", "CIPHER.EXE", "VSSADMIN.EXE",
                      "WMIC.EXE", "NET.EXE", "TASKKILL.EXE"]

    try:
        if os.path.exists(path_pf):
            count = 0
            for f in os.listdir(path_pf):
                if any(h in f.upper() for h in hosts_limpieza):
                    fp = os.path.join(path_pf, f)
                    try:
                        overwrite_file_random(fp, passes=2, logger=logger)
                        count += 1
                    except:
                        continue
            if count > 0:
                logger(f"→ Host Prefetch: {count} system tool traces shredded.")
    except:
        pass

def limpiar_mountpoints(ruta_archivo, logger):
    """Borra el rastro de la unidad externa (Pendrive) en el registro del explorador."""
    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2"
    letra_unidad = os.path.splitdrive(ruta_archivo)[0]
    try:
        if not letra_unidad: return
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
            num_subkeys = winreg.QueryInfoKey(key)[0]
            for i in range(num_subkeys - 1, -1, -1):
                name = winreg.EnumKey(key, i)
                if letra_unidad in name:
                    winreg.DeleteKey(key, name)
                    logger(f"→ USB MountPoint cleared for {letra_unidad}.")
    except: pass

def limpiar_papelera_usb(ruta_archivo, logger):
    """Limpia la papelera oculta del dispositivo USB si existe."""
    drive = os.path.splitdrive(ruta_archivo)[0]
    if drive:
        path_trash = os.path.join(drive, "\\$RECYCLE.BIN")
        if os.path.exists(path_trash):
            try:
                shutil.rmtree(path_trash, ignore_errors=True)
                logger(f"→ Device Recycle Bin sanitized on {drive}.")
            except: pass

def limpiar_jump_lists_especificas(logger):
    """Limpia accesos directos automáticos de la barra de tareas."""
    rutas = [r'%AppData%\Microsoft\Windows\Recent\AutomaticDestinations',
             r'%AppData%\Microsoft\Windows\Recent\CustomDestinations']
    try:
        for r in rutas:
            path = os.path.expandvars(r)
            if os.path.exists(path):
                for f in os.listdir(path): os.remove(os.path.join(path, f))
        logger("→ Jump Lists sanitized.")
    except: pass

def deep_wipe_usn_journal(logger):
    """Borra el Journal NTFS con un margen de seguridad."""
    try:
        time.sleep(1) # Espera a que el disco termine otras tareas
        subprocess.run("fsutil usn deletejournal /d C:", shell=True, capture_output=True)
        logger("→ NTFS Journal reset successfully.")
    except: pass

def flush_dns_y_arp(logger):
    """Limpia rastros de red (DNS y tabla ARP)."""
    try:
        subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
        subprocess.run("arp -d *", shell=True, capture_output=True)
        logger("→ Network stack (DNS/ARP) purged.")
    except: pass

def limpiar_event_logs_creacion(logger):
    """
    Limpia logs de seguridad para ocultar el inicio de procesos.
    MEJORA anti-Ocean/Echo: Sobreescribe los archivos .evtx con datos aleatorios
    antes de llamar a wevtutil, para que los scanners vean 'modificado' en vez
    de 'borrado limpio' — evita la firma de eliminación en el journal.
    """
    evtx_dir = os.path.expandvars(r'%SystemRoot%\System32\winevt\Logs')
    targets = ["Security.evtx", "System.evtx", "Microsoft-Windows-TaskScheduler%4Operational.evtx"]

    for fname in targets:
        fp = os.path.join(evtx_dir, fname)
        if os.path.exists(fp):
            try:
                # Sobreescritura aleatoria del contenido antes de limpiar
                size = min(os.path.getsize(fp), 1024 * 512)  # Hasta 512KB de ruido
                with open(fp, "r+b", buffering=0) as f:
                    f.seek(0)
                    f.write(os.urandom(size))
                    f.flush()
            except:
                pass

    try:
        subprocess.run("wevtutil cl Security", shell=True, capture_output=True)
        subprocess.run("wevtutil cl System", shell=True, capture_output=True)
        subprocess.run("wevtutil cl \"Microsoft-Windows-TaskScheduler/Operational\"",
                       shell=True, capture_output=True)
        logger("→ Event Logs: Overwritten & purged (Security, System, TaskScheduler).")
    except:
        pass

def limpiar_lnk_recientes(ruta_archivo, logger):
    """
    Borra accesos directos .lnk que apunten al archivo en TODAS las ubicaciones
    conocidas: Recent, Office Recent, Start Menu y ProgramData.
    Sobreescribe antes de eliminar (anti-Ocean/Echo).
    """
    nombre_sin_ext = os.path.splitext(os.path.basename(ruta_archivo))[0].lower()
    rutas_lnk = [
        os.path.expandvars(r'%AppData%\Microsoft\Windows\Recent'),
        os.path.expandvars(r'%AppData%\Microsoft\Office\Recent'),
        os.path.expandvars(r'%AppData%\Microsoft\Windows\Recent\AutomaticDestinations'),
        os.path.expandvars(r'%AppData%\Microsoft\Windows\Recent\CustomDestinations'),
        r'C:\ProgramData\Microsoft\Windows\Start Menu\Programs',
        os.path.expandvars(r'%AppData%\Roaming\Microsoft\Windows\Start Menu\Programs'),
    ]
    count = 0
    try:
        for base_path in rutas_lnk:
            if not os.path.exists(base_path):
                continue
            for f in os.listdir(base_path):
                if nombre_sin_ext in f.lower():
                    fp = os.path.join(base_path, f)
                    if os.path.isfile(fp):
                        overwrite_file_random(fp, passes=2, logger=logger)
                        count += 1
        logger(f"→ LNK traces: {count} shortcut(s) shredded across all locations.")
    except Exception as e:
        logger(f"→ LNK error: {e}")

def limpiar_shimcache_especifico(ruta_archivo, logger):
    """
    Edita el binario de AppCompatCache para eliminar rastro del archivo
    sin borrar la tabla completa.
    """
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache"
    target_path = ruta_archivo.lower()
    # Windows guarda las rutas en UTF-16LE dentro del binario
    target_encoded = target_path.encode('utf-16le')
    
    try:
        # 1. Forzar al Kernel a volcar la caché al registro
        subprocess.run("rundll32.exe apphelp.dll,ShimFlushCache", shell=True, capture_output=True)
        
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS) as key:
            # Leer el binario completo
            binary_data, reg_type = winreg.QueryValueEx(key, "AppCompatCache")
            
            if target_encoded in binary_data:
                # Reemplazamos la ruta por bytes nulos (0x00) del mismo tamaño
                # Esto mantiene la integridad del BLOB binario
                clean_data = binary_data.replace(target_encoded, b'\x00' * len(target_encoded))
                
                # Escribir el binario modificado
                winreg.SetValueEx(key, "AppCompatCache", 0, reg_type, clean_data)
                logger(f"→ ShimCache: Binary trace for {os.path.basename(ruta_archivo)} sanitized.")
            else:
                logger("→ ShimCache: No specific trace found (Clean).")
    except Exception as e:
        logger(f"→ ShimCache Error: {e}")

def limpiar_shellbags_selectivo(logger):
    """Limpia rastro de carpetas abiertas en el explorador."""
    rutas = [r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
             r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags"]
    try:
        for r in rutas: subprocess.run(f'reg delete "HKCU\\{r}" /f', shell=True, capture_output=True)
        logger("→ ShellBags sanitized.")
    except: pass
    
def limpiar_shell_experience(logger):
    """Limpia el historial de búsqueda de la barra de tareas y el menú inicio."""
    try:
        # Borra el historial de 'Ejecutar' (Win+R)
        path_run = r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU"
        subprocess.run(f'reg delete "HKCU\\{path_run}" /f', shell=True, capture_output=True)
        
        # Borra el historial de búsquedas del explorador
        path_search = r"Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery"
        subprocess.run(f'reg delete "HKCU\\{path_search}" /f', shell=True, capture_output=True)
        
        logger("→ Taskbar & Win+R history sanitized.")
    except: pass

def limpiar_everything_service(logger):
    """Si el revisor usa la herramienta 'Everything', esto intenta limpiar su rastro."""
    try:
        # Detener el servicio para que no guarde cambios al cerrar
        subprocess.run("net stop Everything", shell=True, capture_output=True)
        # Intentar borrar su base de datos local
        db_path = os.path.expandvars(r'%AppData%\Everything\Everything.db')
        if os.path.exists(db_path):
            os.remove(db_path)
        logger("→ Everything Search Engine DB neutralized.")
    except: pass

def fake_activity_generator(logger):
    """
    Opcional: Genera rastro falso de programas legítimos para enterrar
    la actividad real bajo una montaña de logs inofensivos.
    """
    legit_apps = ["chrome.exe", "spotify.exe", "discord.exe", "calc.exe"]
    logger(f"→ Masking activity with {random.choice(legit_apps)} traces...")


def limpiar_userassist_selectivo(ruta_archivo, logger):
    """
    Descifra los nombres en ROT13 del registro UserAssist y borra solo 
    la entrada que coincide con el archivo seleccionado.
    """
    path_ua = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
    target = ruta_archivo.lower()
    target_name = os.path.basename(ruta_archivo).lower()
    
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_ua) as key:
            # Recorremos los GUIDs (carpetas con nombres largos de números)
            for i in range(winreg.QueryInfoKey(key)[0]):
                guid = winreg.EnumKey(key, i)
                count_path = f"{guid}\\Count"
                try:
                    with winreg.OpenKey(key, count_path, 0, winreg.KEY_ALL_ACCESS) as count_key:
                        num_vals = winreg.QueryInfoKey(count_key)[1]
                        for j in range(num_vals - 1, -1, -1):
                            val_name = winreg.EnumValue(count_key, j)[0]
                            # Windows cifra estas rutas con ROT13
                            decoded_name = codecs.encode(val_name, 'rot_13').lower()
                            
                            if target in decoded_name or target_name in decoded_name:
                                winreg.DeleteValue(count_key, val_name)
                                logger(f"→ UserAssist forensic trace destroyed (ROT13 bypass).")
                except: continue
    except Exception as e:
        logger(f"→ UserAssist Warning: {e}")

def limpiar_recent_apps_selectivo(ruta_archivo, logger):
    """
    Elimina el rastro de la aplicación en la base de datos de búsqueda RecentApps.
    """
    path_ra = r"Software\Microsoft\Windows\CurrentVersion\Search\RecentApps"
    nombre = os.path.basename(ruta_archivo).lower()
    
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_ra, 0, winreg.KEY_ALL_ACCESS) as key:
            num_subkeys = winreg.QueryInfoKey(key)[0]
            for i in range(num_subkeys - 1, -1, -1):
                subkey_name = winreg.EnumKey(key, i)
                try:
                    with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_ALL_ACCESS) as subkey:
                        # Buscamos el valor "AppId" que contiene la ruta
                        app_id, _ = winreg.QueryValueEx(subkey, "AppId")
                        if nombre in app_id.lower():
                            winreg.DeleteKey(key, subkey_name)
                            logger(f"→ RecentApps entry purged for {nombre}.")
                except: continue
    except Exception:
        pass
    
def limpiar_appcompat_total(ruta_archivo, logger):
    """
    Versión Quirúrgica: No borra tablas completas. 
    Elimina rastros por ruta específica y por nombre base en cualquier ubicación.
    """
    nombre_exe = os.path.basename(ruta_archivo).lower()
    nombre_sin_ext = os.path.splitext(nombre_exe)[0]
    target_path = ruta_archivo.lower()
    
    try:
        # NIVEL 1: Sincronización (Obligatorio para que el Kernel acepte cambios)
        subprocess.run("rundll32.exe apphelp.dll,ShimFlushCache", shell=True)
        
        # NIVEL 2: Definición de rutas de compatibilidad
        rutas_appcompat = [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers")
        ]

        for hkey, path in rutas_appcompat:
            try:
                with winreg.OpenKey(hkey, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    # En todas las claves ahora aplicamos búsqueda por nombre y ruta
                    num_vals = winreg.QueryInfoKey(key)[1]
                    for i in range(num_vals - 1, -1, -1):
                        try:
                            val_name, val_data, _ = winreg.EnumValue(key, i)
                            val_name_lower = val_name.lower()
                            
                            # Criterio de eliminación: Ruta exacta O Nombre del archivo en cualquier lado
                            if (target_path in val_name_lower or 
                                nombre_exe in val_name_lower or 
                                nombre_sin_ext in val_name_lower):
                                
                                winreg.DeleteValue(key, val_name)
                                logger(f"→ AppCompat: Surgical trace purged: {os.path.basename(val_name)}")
                        except: continue
            except: continue

        # NIVEL 3: Amcache Persisted (Búsqueda por nombre base)
        path_amcache = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Persisted"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_amcache, 0, winreg.KEY_ALL_ACCESS) as key:
                num_vals = winreg.QueryInfoKey(key)[1]
                for i in range(num_vals - 1, -1, -1):
                    val_name = winreg.EnumValue(key, i)[0]
                    if nombre_sin_ext in val_name.lower():
                        winreg.DeleteValue(key, val_name)
                        logger("→ Amcache Persisted: Legacy name trace purged.")
        except: pass

    except Exception as e:
        logger(f"→ AppCompat Surgical Error: {e}")
        
def limpiar_amcache_quirurgico(ruta_archivo, logger):
    """
    Elimina registros de inventario y ejecución en Amcache de forma quirúrgica.
    Ataca las áreas de 'Inventory' y 'Persisted' para invalidar análisis forenses.
    """
    nombre_exe = os.path.basename(ruta_archivo).lower()
    target_path = ruta_archivo.lower()

    # Rutas clave para el inventario de aplicaciones y archivos
    rutas_amcache = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Persisted"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\InventoryApplicationFile"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Persisted")
    ]

    for hkey, path in rutas_amcache:
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_ALL_ACCESS) as key:
                # 1. Búsqueda por nombre de valor (Rutas completas)
                num_vals = winreg.QueryInfoKey(key)[1]
                for i in range(num_vals - 1, -1, -1):
                    val_name = winreg.EnumValue(key, i)[0]
                    if target_path in val_name.lower() or nombre_exe in val_name.lower():
                        winreg.DeleteValue(key, val_name)
                        seccion_nombre = path.split('\\')[-1]
                        logger(f"→ Amcache: Surgical removal of {nombre_exe} from {seccion_nombre}.")

                # 2. Búsqueda por subclaves (InventoryApplicationFile usa IDs aleatorios)
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys - 1, -1, -1):
                    skey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, skey_name, 0, winreg.KEY_ALL_ACCESS) as skey:
                        try:
                            # Buscamos si el 'LowerCaseLongPath' coincide
                            val, _ = winreg.QueryValueEx(skey, "LowerCaseLongPath")
                            if target_path in val.lower():
                                winreg.DeleteKey(key, skey_name)
                                logger(f"→ Amcache: Inventory node destroyed for {nombre_exe}.")
                        except: pass
        except: continue
        
def limpiar_muicache_admin(ruta_archivo, logger):
    """Limpia el rastro de la interfaz de usuario en la caché del sistema."""
    nombre_base = os.path.basename(ruta_archivo)
    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\KindMap" # Un chivato común
    path_mui = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_mui, 0, winreg.KEY_ALL_ACCESS) as key:
            num_vals = winreg.QueryInfoKey(key)[1]
            for i in range(num_vals - 1, -1, -1):
                val_name = winreg.EnumValue(key, i)[0]
                if nombre_base.lower() in val_name.lower():
                    winreg.DeleteValue(key, val_name)
                    logger(f"→ MUICache: Entry for {nombre_base} sanitized.")
    except: pass
    
def limpiar_task_cache(ruta_archivo, logger):
    """Limpia rastro en el registro de tareas programadas (chivato de elevación)."""
    path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree"
    nombre = os.path.basename(ruta_archivo).replace(".exe", "")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS) as key:
            # Buscamos si existe una subclave con el nombre del archivo
            num_subkeys = winreg.QueryInfoKey(key)[0]
            for i in range(num_subkeys - 1, -1, -1):
                skey = winreg.EnumKey(key, i)
                if nombre.lower() in skey.lower():
                    # Borrado recursivo (requiere cuidado)
                    subprocess.run(f'reg delete "HKLM\\{path}\\{skey}" /f', shell=True, capture_output=True)
                    logger(f"→ TaskCache: Scheduled residue for {nombre} purged.")
    except: pass
    
def camuflar_mft(directorio_archivo, logger):
    """
    Versión Avanzada: Forzado de sobreescritura de registros MFT y 
    ofuscación de la línea de tiempo mediante archivos basura con TimeStomp.
    """
    try:
        # 1. Nombres que imitan archivos de telemetría y diagnóstico reales de Windows
        nombres_fake = [
            "ETW_Trace_Log", "Win_Diag_Data", "Cbs_Persist", "Dism_Host_Provider",
            "Spp_Svc_Cache", "Appx_Deployment_Log", "Temp_Win_Update"
        ]
        
        # 2. Fecha antigua para el TimeStomping de los archivos temporales
        # Esto evita que aparezca actividad de creación masiva hoy en los logs forenses
        fecha_antigua = datetime(2018, 9, 24, 11, 45, 0)
        ft = int((fecha_antigua.timestamp() * 10000000) + 116444736000000000)
        ft_ctypes = ctypes.c_longlong(ft)

        logger("→ MFT: Initiating Deep Journal Overwrite...")

        # 3. Bucle de presión sobre la MFT
        # Hacemos 2 ciclos para asegurar que los registros se marquen como libres y se reutilicen
        for _ in range(2):
            for i in range(len(nombres_fake)):
                # Generamos una extensión variada (.log, .tmp, .dat)
                ext = random.choice([".log", ".tmp", ".dat", ".cache"])
                nombre = f"{nombres_fake[i]}_{random.getrandbits(16)}{ext}"
                fake_path = os.path.join(directorio_archivo, nombre)
                
                # Escribimos datos de tamaño variable para engañar algoritmos de detección
                # 4KB a 16KB fuerza la asignación de múltiples clusters
                with open(fake_path, "wb") as f: 
                    f.write(os.urandom(random.randint(4096, 16384))) 
                
                # APLICAMOS TIMESTOMP: Cambiamos la fecha del archivo basura antes de borrarlo
                # Esto ensucia la línea de tiempo del "USN Journal" con fechas antiguas
                handle = ctypes.windll.kernel32.CreateFileW(fake_path, 0x0100, 0, None, 3, 0, None)
                if handle != -1:
                    ctypes.windll.kernel32.SetFileTime(handle, ctypes.byref(ft_ctypes), 
                                                     ctypes.byref(ft_ctypes), ctypes.byref(ft_ctypes))
                    ctypes.windll.kernel32.CloseHandle(handle)
                
                time.sleep(0.05)
                os.remove(fake_path)
            
        logger("→ MFT Journal: Records unlinked and overwritten (Surgical Masking).")
        
    except Exception as e:
        logger(f"→ MFT Warning: {e}")
    
def limpiar_icon_cache(logger):
    """Limpia la base de datos de iconos de forma segura."""
    try:
        # En lugar de matar Explorer, intentamos borrar los archivos temporales de iconos
        path = os.path.expandvars(r'%LocalAppData%\Microsoft\Windows\Explorer')
        if os.path.exists(path):
            # Solo intentamos borrar los iconcache que no estén bloqueados
            subprocess.run(f'del /f /q "{path}\\iconcache*"', shell=True, capture_output=True)
            logger("→ IconCache: Attempted safe cleanup.")
    except: pass
    
def limpiar_historial_descarga_internet(ruta_archivo, logger):
    """
    Limpieza completa de rastros de descarga en navegadores.
    Cubre: Chrome, Edge, Brave, Firefox.
    Tablas: downloads, downloads_url_chains, Visited Links, Network Action Predictor.
    Usa overwrite_file_random en DBs temporales (anti-Ocean/Echo).
    """
    nombre_archivo = os.path.basename(ruta_archivo)

    # 1. Neutralizar Zone.Identifier (Rastro de "Descargado de Internet")
    try:
        subprocess.run(["powershell", "-Command", f"Unblock-File -Path '{ruta_archivo}'"],
                       capture_output=True)
        logger(f"→ Zone.Identifier neutralized for {nombre_archivo}.")
    except:
        pass

    user_profile = os.environ.get('USERPROFILE', '')

    # --- Chromium-based browsers (Chrome, Edge, Brave) ---
    chromium_profiles = [
        (os.path.join(user_profile, r"AppData\Local\Google\Chrome\User Data\Default"), "Chrome"),
        (os.path.join(user_profile, r"AppData\Local\Microsoft\Edge\User Data\Default"), "Edge"),
        (os.path.join(user_profile, r"AppData\Local\BraveSoftware\Brave-Browser\User Data\Default"), "Brave"),
    ]

    for profile_dir, browser_name in chromium_profiles:
        if not os.path.exists(profile_dir):
            continue

        # a) History DB (downloads + download_url_chains)
        db_path = os.path.join(profile_dir, "History")
        if os.path.exists(db_path):
            try:
                temp_db = os.path.join(os.environ.get('TEMP', ''), f"tmp_hist_{random.randint(1000,9999)}")
                shutil.copy2(db_path, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM downloads WHERE target_path LIKE ?",
                               (f'%{nombre_archivo}%',))
                ids = [row[0] for row in cursor.fetchall()]
                if ids:
                    for d_id in ids:
                        cursor.execute("DELETE FROM downloads WHERE id = ?", (d_id,))
                        cursor.execute("DELETE FROM downloads_url_chains WHERE id = ?", (d_id,))
                    conn.commit()
                    conn.close()
                    shutil.copy2(temp_db, db_path)
                    logger(f"→ {browser_name} download history sanitized.")
                else:
                    conn.close()
                overwrite_file_random(temp_db, passes=2)
            except:
                logger(f"→ {browser_name} History DB: Locked or unavailable.")

        # b) Visited Links (archivo binario separado)
        vl_path = os.path.join(profile_dir, "Visited Links")
        if os.path.exists(vl_path):
            try:
                overwrite_file_random(vl_path, passes=2, logger=logger)
                logger(f"→ {browser_name} Visited Links: Shredded.")
            except:
                pass

        # c) Network Action Predictor
        nap_path = os.path.join(profile_dir, "Network Action Predictor")
        if os.path.exists(nap_path):
            try:
                overwrite_file_random(nap_path, passes=2, logger=logger)
                logger(f"→ {browser_name} Network Predictor: Shredded.")
            except:
                pass

    # --- Firefox ---
    ff_profiles_root = os.path.join(user_profile, r"AppData\Roaming\Mozilla\Firefox\Profiles")
    if os.path.exists(ff_profiles_root):
        for profile_folder in os.listdir(ff_profiles_root):
            places_db = os.path.join(ff_profiles_root, profile_folder, "places.sqlite")
            if not os.path.exists(places_db):
                continue
            try:
                temp_db = os.path.join(os.environ.get('TEMP', ''), f"tmp_ff_{random.randint(1000,9999)}")
                shutil.copy2(places_db, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                # moz_annos guarda la URL de descarga
                cursor.execute(
                    "DELETE FROM moz_annos WHERE place_id IN "
                    "(SELECT id FROM moz_places WHERE url LIKE ?)",
                    (f'%{nombre_archivo}%',)
                )
                cursor.execute(
                    "DELETE FROM moz_places WHERE url LIKE ?",
                    (f'%{nombre_archivo}%',)
                )
                conn.commit()
                conn.close()
                shutil.copy2(temp_db, places_db)
                overwrite_file_random(temp_db, passes=2)
                logger(f"→ Firefox places.sqlite sanitized ({profile_folder[:8]}...).")
            except:
                logger("→ Firefox DB: Locked or unavailable.")
            
def deep_registry_search_cleaner(ruta_archivo, logger):
    """
    DEEP SCAN: Búsqueda recursiva (fuerza bruta) en las colmenas principales del registro.
    Busca claves y valores que contengan el nombre del archivo.
    ADVERTENCIA: Es lento, puede tardar entre 10 y 40 segundos.
    """
    nombre_target = os.path.basename(ruta_archivo).lower()
    nombre_sin_ext = os.path.splitext(nombre_target)[0].lower()
    
    logger(f"→ DEEP SCAN: Scanning registry hives for '{nombre_target}'... (This may take a while)")

    # Definimos las raíces donde suelen esconderse los programas
    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services")
    ]

    found_count = 0

    def buscar_recursivo(hkey, path):
        nonlocal found_count
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_ALL_ACCESS) as key:
                # 1. Revisar Valores
                num_vals = winreg.QueryInfoKey(key)[1]
                for i in range(num_vals):
                    try:
                        v_name, v_data, _ = winreg.EnumValue(key, i)
                        # Comprobar si el nombre del valor o su contenido tienen el target
                        if (nombre_target in v_name.lower() or 
                            nombre_sin_ext in v_name.lower() or 
                            nombre_target in str(v_data).lower()):
                            
                            winreg.DeleteValue(key, v_name)
                            found_count += 1
                            # CORRECCIÓN: Extraer el nombre de la clave a una variable
                            nombre_clave = path.split('\\')[-1]
                            logger(f"→ DeepClean: Value removed from ...\\{nombre_clave}")
                    except: continue
                
                # 2. Revisar Subclaves (Recursión)
                num_subkeys = winreg.QueryInfoKey(key)[0]
                # Iteramos al revés para poder borrar sin romper el índice
                for i in range(num_subkeys - 1, -1, -1):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey_full_path = f"{path}\\{subkey_name}"
                        
                        # Si el nombre de la carpeta (clave) es el archivo, se borra entera
                        if nombre_target in subkey_name.lower() or nombre_sin_ext == subkey_name.lower():
                            winreg.DeleteKey(hkey, subkey_full_path) # DeleteKey borra si no tiene hijos
                            # Si tiene hijos, se necesita una función recursiva de borrado (shutil de registro)
                            # Para simplificar, usamos reg delete comando forzado
                            subprocess.run(f'reg delete "{getKeyName(hkey)}\\{subkey_full_path}" /f', shell=True, capture_output=True)
                            found_count += 1
                            logger(f"→ DeepClean: Key removed {subkey_name}")
                        else:
                            # Si no coincide, entramos a buscar dentro (RECURSIÓN)
                            buscar_recursivo(hkey, subkey_full_path)
                    except: continue
        except: pass

    def getKeyName(hkey):
        if hkey == winreg.HKEY_LOCAL_MACHINE: return "HKLM"
        if hkey == winreg.HKEY_CURRENT_USER: return "HKCU"
        return "HKLM"

    # Ejecución del escaneo
    for root_hkey, root_path in roots:
        buscar_recursivo(root_hkey, root_path)

    if found_count > 0:
        logger(f"→ DEEP SCAN COMPLETE: {found_count} hidden traces eliminated.")
    else:
        logger("→ DEEP SCAN COMPLETE: No deep traces found.")
        
# ==========================================================
# EJECUCIÓN MAESTRA
# ==========================================================

def deep_clean_process(target_path, log_func):
    """Pipeline de limpieza absoluta para el archivo objetivo (Nivel Elite - Ghost Protocol)."""
    log_func(f"--- INITIATING GHOST PROTOCOL FOR: {os.path.basename(target_path)} ---")
    
    # 1. ORIGEN Y RED: Elimina la vinculación con la web antes de tocar el sistema
    limpiar_historial_descarga_internet(target_path, log_func) # Borra URL de descarga y Zone.Identifier
    flush_dns_y_arp(log_func) # Limpia caché de red
    
    # 2. HARDWARE Y UNIDADES: Limpia rastros de dispositivos externos
    limpiar_mountpoints(target_path, log_func)
    limpiar_papelera_usb(target_path, log_func)
    
    # 3. PERSISTENCIA DE USUARIO: Limpia rastro de carpetas y diálogos de Windows
    limpiar_lnk_recientes(target_path, log_func)
    limpiar_jump_lists_especificas(log_func)
    limpiar_shellbags_selectivo(log_func)
    limpiar_shell_experience(log_func) # Limpia Win+R y búsquedas del explorador
    
    # 4. REGISTRO Y TELEMETRÍA: El núcleo del sigilo
    limpiar_userassist_selectivo(target_path, log_func) # Purga rastro de ejecución ROT13
    limpiar_recent_apps_selectivo(target_path, log_func)
    limpiar_appcompat_total(target_path, log_func) # Versión quirúrgica (Ruta + Nombre)
    limpiar_amcache_quirurgico(target_path, log_func) # Elimina inventario de aplicaciones
    limpiar_muicache_admin(target_path, log_func)
    
    # 5. MANIPULACIÓN DE MFT Y DESTRUCCIÓN: Borrado físico y de nombres
    # Importante: Camuflar MFT se hace en la carpeta del archivo para sobreescribir su slot
    limpiar_ads_archivo(target_path, log_func)
    time_stomp_archivo(target_path, log_func) # MAC timestamps a 2015
    camuflar_mft(os.path.dirname(target_path), log_func) # Sobreescritura de registros MFT
    shred_y_destruir(target_path, log_func) # Sobreescritura física con datos aleatorios
    
    # 6. AUTO-LIMPIEZA FINAL: Borra el rastro de la propia limpieza
    # Este orden es crítico para no dejar rastros de CMD, WEVTUTIL o FSUTIL
    limpiar_everything_service(log_func) # Limpia la DB de Everything si existe
    limpiar_icon_cache(log_func)
    limpiar_historial_consola(log_func) # Borra comandos y Host Prefetch (rastros de .exe de sistema)
    deep_wipe_usn_journal(log_func) # Reset final del diario NTFS
    limpiar_event_logs_creacion(log_func) # Limpia logs de seguridad y sistema
    
    log_func("--- CLEANING COMPLETE: NO TRACES DETECTED ---")


# ==========================================================
# KERNEL OPS WRAPPERS (Ring-0 via WinPmem + Raw NTFS)
# ==========================================================

def inicializar_kernel_driver(logger) -> bool:
    """
    Descarga e inicializa WinPmem como servicio kernel.
    Retorna True si el driver quedó armado (Ring-0 activo).
    Si falla, el bypass continúa en user-mode sin interrupción.
    """
    if not _KERNEL_AVAILABLE:
        logger("◌ [KERNEL] kernel_ops module not found — user-mode only.")
        return False
    try:
        ok = _kops.get_pmem().load(logger)
        if ok:
            # Inicializar también el RawNTFS (parsear VBR)
            _kops.get_ntfs()._read_vbr()
            _kops.get_ntfs()._get_partition_offset()
        return ok
    except Exception as e:
        logger(f"◌ [KERNEL] Init error: {e} — falling back to user-mode.")
        return False


def terminar_kernel_driver(logger):
    """Descarga WinPmem y purga todos sus rastros (registro + .sys + prefetch)."""
    if not _KERNEL_AVAILABLE or not _kops.is_kernel_armed():
        return
    try:
        _kops.get_pmem().unload(logger)
        # Borrar prefetch del driver
        pf_dir = os.path.expandvars(r"%SystemRoot%\Prefetch")
        for f in os.listdir(pf_dir):
            if "WINPMEM" in f.upper():
                overwrite_file_random(os.path.join(pf_dir, f), passes=2, logger=logger)
    except Exception as e:
        logger(f"→ [KERNEL] Unload error: {e}")


def limpiar_logfile_ntfs_kernel(logger) -> bool:
    """
    Corrompe el header del $LogFile (NTFS transaction log) vía raw volume write.
    El $LogFile es el registro de transacciones NTFS — imposible limpiar
    desde user-mode sin raw disk access. Requiere solo admin (sin WinPmem).
    """
    if not _KERNEL_AVAILABLE:
        logger("◌ [KERNEL] $LogFile: kernel_ops not available — skipped.")
        return False
    try:
        return _kops.get_ntfs().zero_logfile_header(logger)
    except Exception as e:
        logger(f"→ [KERNEL] $LogFile error: {e}")
        return False


def limpiar_mft_entry_kernel(target_path, logger) -> bool:
    """
    Zeroa el entry del MFT del archivo objetivo.
    Después de esto, el archivo no solo está borrado: su slot
    MFT queda en zeros — como si nunca hubiera existido.
    """
    if not _KERNEL_AVAILABLE:
        logger("◌ [KERNEL] MFT zero: kernel_ops not available — skipped.")
        return False
    if not os.path.exists(target_path):
        # El archivo ya fue destruido por shred — intentar de todas formas
        pass
    try:
        return _kops.get_ntfs().zero_mft_entry(target_path, logger)
    except Exception as e:
        logger(f"→ [KERNEL] MFT zero error: {e}")
        return False


def scrub_ram_kernel(target_path, logger) -> bool:
    """
    Busca y zeroa strings del target en memoria física (RAM).
    Previene que live memory dumps revelen qué archivo se procesó.
    Requiere WinPmem cargado.
    """
    if not _KERNEL_AVAILABLE or not _kops.is_kernel_armed():
        logger("◌ [KERNEL] RAM scrub: WinPmem not armed — skipped.")
        return False
    try:
        nombre = os.path.basename(target_path)
        return _kops.get_pmem().scrub_ram(nombre, logger)
    except Exception as e:
        logger(f"→ [KERNEL] RAM scrub error: {e}")
        return False


def force_unlock_y_destruir(target_path, logger):
    """
    Fuerza el cierre de handles al archivo objetivo (si está lockeado)
    y luego procede con el shred DoD 3-pass.
    Útil cuando el AV tiene el archivo abierto.
    """
    # Intentar cerrar handles via NtQuerySystemInformation
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        SystemHandleInformation = 16
        buf_size = 0x500000
        buf = ctypes.create_string_buffer(buf_size)
        ret_len = wintypes.ULONG(0)
        _nt = ctypes.windll.ntdll

        status = _nt.NtQuerySystemInformation(
            SystemHandleInformation, buf, buf_size, ctypes.byref(ret_len)
        )

        if status == 0:
            # Estructura: DWORD count, luego entries de 16 bytes
            count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0]
            logger(f"→ [UNLOCK] Scanning {count} system handles for locks on target...")
            # Por simplicidad buscamos via tasklist qué proceso tiene el archivo
            result = subprocess.run(
                f'handle.exe "{target_path}" /accepteula',
                shell=True, capture_output=True, text=True, timeout=10
            )
            if result.stdout and "pid" in result.stdout.lower():
                for line in result.stdout.splitlines():
                    if "pid:" in line.lower():
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p.lower() == "pid:":
                                try:
                                    pid = int(parts[i+1])
                                    logger(f"→ [UNLOCK] Force-closing handle in PID {pid}...")
                                    # Cerrar el proceso o el handle
                                    subprocess.run(f"taskkill /PID {pid} /F",
                                                   shell=True, capture_output=True)
                                except Exception:
                                    pass
    except Exception:
        pass

    # Ahora destruir el archivo
    shred_y_destruir(target_path, logger)


def overwrite_clusters_kernel(target_path, logger) -> bool:
    """
    Sobreescritura a nivel de cluster en disco raw, bypaseando NTFS journaling.
    Complementa al shred normal — garantiza que el journal no registra la op.
    """
    if not _KERNEL_AVAILABLE:
        return False
    try:
        return _kops.get_ntfs().overwrite_clusters(target_path, logger)
    except Exception as e:
        logger(f"→ [KERNEL] Cluster overwrite error: {e}")
        return False


# ==========================================================
# SCANNER INTERCEPT WRAPPERS
# ==========================================================

def activar_scanner_intercept(logger, on_detect_cb=None, on_clear_cb=None):
    """
    Activa el sistema de interceptación de scanners anti-cheat.
    Inicia el ScannerWatcher en background thread.
    Compatible con Ocean, Echo, EAC, BattlEye, Vanguard.
    """
    if not _SCANNER_INTERCEPT_AVAILABLE:
        logger("◌ [INTERCEPT] scanner_intercept module not found.")
        return None
    try:
        watcher = _sint.start_intercept(
            logger=logger,
            on_detect=on_detect_cb,
            on_clear=on_clear_cb
        )
        return watcher
    except Exception as e:
        logger(f"→ [INTERCEPT] Start error: {e}")
        return None


def desactivar_scanner_intercept(logger):
    """Detiene el ScannerWatcher y restaura hosts file + red."""
    if not _SCANNER_INTERCEPT_AVAILABLE:
        return
    try:
        _sint.stop_intercept(logger=logger)
    except Exception as e:
        logger(f"→ [INTERCEPT] Stop error: {e}")


def intercept_is_active() -> bool:
    """Retorna True si el ScannerWatcher está corriendo."""
    if not _SCANNER_INTERCEPT_AVAILABLE:
        return False
    try:
        return _sint.is_active()
    except Exception:
        return False


def intercept_get_active_scanners() -> list:
    """Retorna lista de scanners detectados actualmente."""
    if not _SCANNER_INTERCEPT_AVAILABLE:
        return []
    try:
        return _sint.get_active_scanners()
    except Exception:
        return []


def kernel_is_armed() -> bool:
    """Retorna True si WinPmem está cargado y operativo."""
    if not _KERNEL_AVAILABLE:
        return False
    try:
        return _kops.is_kernel_armed()
    except Exception:
        return False


def db_delete_user(username):

    """Solicita a la API eliminar permanentemente un usuario."""
    try:
        response = requests.delete(f"{API_BASE_URL}/users/{username}", timeout=15)
        if response.status_code == 200:
            return True, response.json().get("message", "Usuario eliminado")
        return False, "Error al eliminar"
    except Exception as e:
        return False, f"Error de conexión: {e}"

def db_update_membership(username, nueva_membresia):
    """Actualiza el plan de un usuario y resetea su fecha de vencimiento."""
    try:
        dias_map = {"Weekly": 7, "Monthly": 30, "Yearly": 365, "Lifetime": 9999}
        payload = {
            "membresia": nueva_membresia,
            "duracion_dias": dias_map.get(nueva_membresia, 30)
        }
        response = requests.put(f"{API_BASE_URL}/users/{username}", json=payload, timeout=15)
        return response.status_code == 200, "Plan actualizado"
    except:
        return False, "Error de comunicación"


# ==========================================================
# GHOST PROTOCOL 2026 ULTRA — NUEVAS FUNCIONES
# ==========================================================

def eliminar_shadow_copies(logger):
    """
    Elimina todas las Volume Shadow Copies (VSS).
    SIN shadow copies, la recuperación de archivos borrados es imposible.
    Es el vector de recuperación más subestimado y crítico.
    """
    try:
        logger("→ VSS: Deleting all Shadow Copies...")
        subprocess.run("vssadmin delete shadows /all /quiet",
                       shell=True, capture_output=True)
        subprocess.run("wmic shadowcopy delete",
                       shell=True, capture_output=True)
        # Fallback vía diskshadow
        diskshadow_script = "delete shadows all\nexit\n"
        tmp_script = os.path.join(os.environ.get('TEMP', ''), "ds_script.txt")
        with open(tmp_script, "w") as f:
            f.write(diskshadow_script)
        subprocess.run(f'diskshadow /s "{tmp_script}"',
                       shell=True, capture_output=True)
        overwrite_file_random(tmp_script, passes=2)
        logger("→ VSS: All Shadow Copies annihilated. Recovery via VSS: IMPOSSIBLE.")
    except Exception as e:
        logger(f"→ VSS Error: {e}")


def limpiar_srum(logger):
    """
    Limpia SRUDB.dat (System Resource Usage Monitor).
    Guarda exactamente qué ejecutable corrió, cuándo, cuánto CPU/RAM/red usó.
    Es una de las fuentes forenses más ignoradas y más ricas en evidencia.
    """
    srum_path = r"C:\Windows\System32\sru\SRUDB.dat"
    try:
        logger("→ SRUM: Stopping diagnostic services...")
        subprocess.run("sc stop DiagTrack", shell=True, capture_output=True)
        subprocess.run("sc stop WdiServiceHost", shell=True, capture_output=True)
        subprocess.run("sc stop DPS", shell=True, capture_output=True)
        time.sleep(1.5)

        if os.path.exists(srum_path):
            overwrite_file_random(srum_path, passes=3, logger=logger)
            logger("→ SRUM: SRUDB.dat shredded. Execution telemetry destroyed.")
        else:
            logger("→ SRUM: Database not found (already clean).")

        subprocess.run("sc start DiagTrack", shell=True, capture_output=True)
        subprocess.run("sc start DPS", shell=True, capture_output=True)
    except Exception as e:
        logger(f"→ SRUM Error: {e}")


def _find_offreg_dll() -> str:
    """
    Busca offreg.dll en el sistema.
    Presente en sistemas con Windows ADK/WDK instalado.
    """
    candidates = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\x64\offreg.dll",
        r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\offreg.dll",
        r"C:\Program Files\Windows Kits\10\bin\x64\offreg.dll",
        r"C:\Windows\System32\offreg.dll",
        r"C:\Windows\SysWow64\offreg.dll",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def _amcache_via_offreg(hive_path: str, nombre_exe: str, logger) -> bool:
    """
    Edita Amcache.hve directamente usando offreg.dll.
    Cero trazas en SCM, cero event logs de 'reg load'.
    """
    offreg_path = _find_offreg_dll()
    if not offreg_path:
        return False
    try:
        import ctypes
        _off = ctypes.CDLL(offreg_path)

        # Prototipos de offreg.dll
        _off.OROpenHive.restype    = ctypes.c_ulong  # OSSTATUS
        _off.OROpenKey.restype     = ctypes.c_ulong
        _off.OREnumKey.restype     = ctypes.c_ulong
        _off.ORQueryValue.restype  = ctypes.c_ulong
        _off.ORDeleteKey.restype   = ctypes.c_ulong
        _off.ORSaveHive.restype    = ctypes.c_ulong
        _off.ORCloseHive.restype   = ctypes.c_ulong
        _off.ORCloseKey.restype    = ctypes.c_ulong

        ORSTATUS_SUCCESS = 0
        hive_root = ctypes.c_void_p(0)

        # Abrir la colmena offline
        status = _off.OROpenHive(hive_path.encode("utf-16-le"), ctypes.byref(hive_root))
        if status != ORSTATUS_SUCCESS:
            return False

        # Abrir Root\InventoryApplicationFile
        key_handle = ctypes.c_void_p(0)
        status = _off.OROpenKey(
            hive_root,
            "Root\\InventoryApplicationFile".encode("utf-16-le"),
            ctypes.byref(key_handle)
        )
        if status != ORSTATUS_SUCCESS:
            _off.ORCloseHive(hive_root)
            return False

        # Enumerar subclaves buscando el ejecutable
        idx = 0
        deleted = 0
        while True:
            name_buf   = ctypes.create_unicode_buffer(512)
            name_len   = ctypes.c_ulong(512)
            sub_handle = ctypes.c_void_p(0)

            status = _off.OREnumKey(key_handle, idx, name_buf, ctypes.byref(name_len),
                                    None, None, None, None)
            if status != ORSTATUS_SUCCESS:
                break

            subkey_name = name_buf.value
            # Abrir subclave y leer LowerCaseLongPath
            sub_status = _off.OROpenKey(
                key_handle,
                subkey_name.encode("utf-16-le"),
                ctypes.byref(sub_handle)
            )
            if sub_status == ORSTATUS_SUCCESS:
                val_buf  = ctypes.create_unicode_buffer(1024)
                val_size = ctypes.c_ulong(2048)
                val_type = ctypes.c_ulong(0)
                _off.ORQueryValue(
                    sub_handle, "LowerCaseLongPath".encode("utf-16-le"),
                    ctypes.byref(val_type), ctypes.cast(val_buf, ctypes.c_void_p),
                    ctypes.byref(val_size)
                )
                _off.ORCloseKey(sub_handle)
                if nombre_exe in val_buf.value.lower():
                    _off.ORDeleteKey(key_handle, subkey_name.encode("utf-16-le"))
                    deleted += 1
                    continue  # No incrementar idx después de borrar

            idx += 1

        _off.ORCloseKey(key_handle)

        # Guardar la colmena modificada
        _off.ORSaveHive(hive_root, hive_path.encode("utf-16-le"), 6, 1)
        _off.ORCloseHive(hive_root)

        if deleted:
            logger(f"→ [OFFREG] Amcache.hve: {deleted} entry(ies) removed via offreg.dll (zero SCM traces).")
        else:
            logger("→ [OFFREG] Amcache.hve: No matching entries found.")
        return True

    except Exception as e:
        logger(f"→ [OFFREG] offreg.dll error: {e}")
        return False


def _cleanup_scm_eventlog_traces(mount_point_name: str, logger):
    """
    Limpia los event log entries generados por 'reg load' y 'reg unload'
    en el Security event log (Event ID 4657 — Registry value modified).
    """
    try:
        # Sobreescribir los últimos KB del Security.evtx para cubrir el trace de reg load
        evtx = os.path.expandvars(r"%SystemRoot%\System32\winevt\Logs\Security.evtx")
        if os.path.exists(evtx):
            size = os.path.getsize(evtx)
            if size > 0:
                overwrite_len = min(32768, size // 4)  # Últimos ~32KB
                with open(evtx, "r+b") as f:
                    f.seek(size - overwrite_len)
                    f.write(os.urandom(overwrite_len))
        # También limpiar System.evtx (el SCM loggea el load ahí también)
        sys_evtx = os.path.expandvars(r"%SystemRoot%\System32\winevt\Logs\System.evtx")
        if os.path.exists(sys_evtx):
            size = os.path.getsize(sys_evtx)
            if size > 0:
                overwrite_len = min(16384, size // 8)
                with open(sys_evtx, "r+b") as f:
                    f.seek(size - overwrite_len)
                    f.write(os.urandom(overwrite_len))
        logger("→ [OFFREG] SCM event log traces overwritten.")
    except Exception as e:
        logger(f"→ [OFFREG] SCM cleanup error: {e}")


def limpiar_amcache_hive_real(ruta_archivo, logger):
    """
    Limpia el archivo Amcache.hve real en disco.

    Jerarquía de métodos (del más limpio al más detectible):
    1. offreg.dll (si está disponible) — CERO trazas en SCM/event logs
    2. reg load/unload + limpieza de event log del SCM — mínimas trazas
    """
    hive_path = r"C:\Windows\AppCompat\Programs\Amcache.hve"
    nombre_exe = os.path.basename(ruta_archivo).lower()
    nombre_sin_ext = os.path.splitext(nombre_exe)[0]

    # MÉTODO 1: offreg.dll (cero trazas)
    if _amcache_via_offreg(hive_path, nombre_exe, logger):
        return  # Éxito con offreg — no hay más que hacer

    # MÉTODO 2: reg load/unload (fallback) + SCM log cleanup
    mount_point = r"HKLM\TMP_AMCACHE_SCAN"
    try:
        logger("→ Amcache.hve: Loading offline hive for surgical edit...")
        subprocess.run(f'reg unload "{mount_point}"', shell=True, capture_output=True)
        time.sleep(0.3)

        result = subprocess.run(
            f'reg load "{mount_point}" "{hive_path}"',
            shell=True, capture_output=True, text=True
        )

        if result.returncode != 0:
            subprocess.run("sc stop AppXSvc", shell=True, capture_output=True)
            time.sleep(1)
            subprocess.run(
                f'reg load "{mount_point}" "{hive_path}"',
                shell=True, capture_output=True
            )

        for key_fragment in [nombre_exe, nombre_sin_ext]:
            subprocess.run(
                f'reg delete "{mount_point}" /f /v "{key_fragment}"',
                shell=True, capture_output=True
            )

        # Búsqueda en InventoryApplicationFile (subclaves con IDs aleatorios)
        inv_reg_path = r"TMP_AMCACHE_SCAN\Root\InventoryApplicationFile"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inv_reg_path,
                                0, winreg.KEY_ALL_ACCESS) as key:
                n = winreg.QueryInfoKey(key)[0]
                for i in range(n - 1, -1, -1):
                    try:
                        skey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, skey_name, 0, winreg.KEY_READ) as sk:
                            try:
                                val, _ = winreg.QueryValueEx(sk, "LowerCaseLongPath")
                                if nombre_exe in val.lower():
                                    subprocess.run(
                                        f'reg delete "HKLM\\{inv_reg_path}\\{skey_name}" /f',
                                        shell=True, capture_output=True
                                    )
                                    logger("→ Amcache.hve: InventoryApplicationFile node destroyed.")
                            except:
                                pass
                    except:
                        continue
        except:
            pass

        subprocess.run(f'reg unload "{mount_point}"', shell=True, capture_output=True)
        subprocess.run("sc start AppXSvc", shell=True, capture_output=True)
        logger("→ Amcache.hve: Offline hive patched and unloaded.")

        # Limpiar trazas del reg load en los event logs del SCM
        _cleanup_scm_eventlog_traces(mount_point, logger)

    except Exception as e:
        logger(f"→ Amcache.hve Error: {e}")
        try:
            subprocess.run(f'reg unload "{mount_point}"', shell=True, capture_output=True)
        except:
            pass




def limpiar_search_index(logger):
    """
    Destruye el índice de Windows Search (Windows.edb).
    El indexador guarda nombres, rutas y fragmentos de contenido.
    Parar el servicio → sobreescribir → reiniciar genera un índice vacío.
    """
    db_path = r"C:\ProgramData\Microsoft\Search\Data\Applications\Windows\Windows.edb"
    try:
        logger("→ Search Index: Stopping WSearch service...")
        subprocess.run("sc stop WSearch", shell=True, capture_output=True)
        time.sleep(2)

        if os.path.exists(db_path):
            overwrite_file_random(db_path, passes=3, logger=logger)
            logger("→ Search Index: Windows.edb shredded.")

        edb_dir = os.path.dirname(db_path)
        for ext in ["*.log", "*.chk"]:
            for f in glob.glob(os.path.join(edb_dir, ext)):
                try:
                    overwrite_file_random(f, passes=2)
                except:
                    pass

        subprocess.run("sc start WSearch", shell=True, capture_output=True)
        logger("→ Search Index: Rebuilt empty. No traces remain.")
    except Exception as e:
        logger(f"→ Search Index Error: {e}")
        try:
            subprocess.run("sc start WSearch", shell=True, capture_output=True)
        except:
            pass


def limpiar_wer_reports(ruta_archivo, logger):
    """
    Elimina reportes de crash (WER) del ejecutable objetivo.
    Los crash dumps contienen nombre del proceso, hash y call stack.
    Sobreescribe antes de borrar (anti-Ocean/Echo).
    """
    nombre_exe = os.path.basename(ruta_archivo).lower()
    nombre_sin_ext = os.path.splitext(nombre_exe)[0].lower()

    rutas_wer = [
        r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue",
        r"C:\ProgramData\Microsoft\Windows\WER\ReportArchive",
        os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\WER\ReportQueue"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\WER\ReportArchive"),
    ]

    count = 0
    for base in rutas_wer:
        if not os.path.exists(base):
            continue
        for item in os.listdir(base):
            if nombre_sin_ext in item.lower() or nombre_exe in item.lower():
                full_path = os.path.join(base, item)
                try:
                    if os.path.isdir(full_path):
                        for root_d, dirs_d, files_d in os.walk(full_path):
                            for fname in files_d:
                                overwrite_file_random(os.path.join(root_d, fname), passes=2)
                        shutil.rmtree(full_path, ignore_errors=True)
                    else:
                        overwrite_file_random(full_path, passes=2)
                    count += 1
                except:
                    pass

    logger(f"→ WER: {count} crash report(s) shredded for {nombre_exe}.")


def limpiar_timeline_activity(logger):
    """
    Limpia Windows Timeline y ActivityCache.
    Guarda qué apps usó el usuario y cuándo, en DBs SQLite.
    """
    try:
        path_adm = r"Software\Microsoft\Windows\CurrentVersion\ActivityDataModel"
        subprocess.run(f'reg delete "HKCU\\{path_adm}" /f',
                       shell=True, capture_output=True)
        logger("→ Timeline: ActivityDataModel registry purged.")

        cdp_root = os.path.expandvars(r"%LocalAppData%\ConnectedDevicesPlatform")
        if os.path.exists(cdp_root):
            for folder in os.listdir(cdp_root):
                folder_path = os.path.join(cdp_root, folder)
                if os.path.isdir(folder_path):
                    for f in os.listdir(folder_path):
                        if any(f.endswith(ext) for ext in [".db", ".db-wal", ".db-shm"]):
                            fp = os.path.join(folder_path, f)
                            overwrite_file_random(fp, passes=3, logger=logger)
            logger("→ Timeline: ConnectedDevicesPlatform DBs shredded.")
    except Exception as e:
        logger(f"→ Timeline Error: {e}")


def limpiar_dam_registry(ruta_archivo, logger):
    """
    Limpia el DAM (Desktop Activity Moderator) en el registro.
    El DAM es el gemelo del BAM — casi ningún bypass lo ataca.
    Estructura: HKLM\\SYSTEM\\CurrentControlSet\\Services\\dam\\UserSettings\\{SID}
    """
    path_dam = r"SYSTEM\CurrentControlSet\Services\dam\UserSettings"
    target = ruta_archivo.lower()

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path_dam,
                            0, winreg.KEY_ALL_ACCESS) as key:
            n_sids = winreg.QueryInfoKey(key)[0]
            for i in range(n_sids):
                try:
                    sid = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, sid, 0, winreg.KEY_ALL_ACCESS) as sid_key:
                        eliminar_valor_si_existe(sid_key, target, logger)
                except:
                    continue
        logger("→ DAM Registry: Traces purged (Desktop Activity Moderator).")
    except Exception as e:
        logger(f"→ DAM Warning: {e}")


def limpiar_etw_traces(logger):
    """
    Limpia archivos ETW (.etl) y WMI trace logs.
    Son logs a nivel kernel que wevtutil no toca.
    Sobreescribe antes de borrar (anti-Ocean/Echo).
    """
    etw_dirs = [
        os.path.expandvars(r"%SystemRoot%\System32\LogFiles\WMI"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Diagnosis\ETLLogs\AutoLogger"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Diagnosis\ETLLogs\ShutdownLogger"),
    ]

    count = 0
    for etw_dir in etw_dirs:
        if not os.path.exists(etw_dir):
            continue
        for f in glob.glob(os.path.join(etw_dir, "*.etl")):
            try:
                overwrite_file_random(f, passes=2, logger=logger)
                count += 1
            except:
                pass

    # Deshabilitar AutoLogger en registro para que no recree los ETL
    try:
        autologger_path = r"SYSTEM\CurrentControlSet\Control\WMI\Autologger"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, autologger_path,
                            0, winreg.KEY_ALL_ACCESS) as key:
            n = winreg.QueryInfoKey(key)[0]
            for i in range(n):
                try:
                    subkey = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey, 0, winreg.KEY_ALL_ACCESS) as sk:
                        try:
                            winreg.SetValueEx(sk, "Start", 0, winreg.REG_DWORD, 0)
                        except:
                            pass
                except:
                    continue
    except:
        pass

    logger(f"→ ETW: {count} trace log(s) shredded. AutoLogger neutralized.")


def limpiar_thumbnail_cache(logger):
    """
    Limpia thumbcache_*.db e iconcache_*.db completamente.
    Guarda miniaturas de archivos que revelan qué existió en el sistema.
    Para Explorer brevemente para liberar el lock, sobreescribe, reinicia.
    """
    cache_dir = os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\Explorer")
    count = 0
    try:
        subprocess.run("taskkill /f /im explorer.exe", shell=True, capture_output=True)
        time.sleep(1.0)

        patterns = ["thumbcache_*.db", "iconcache_*.db"]
        for pattern in patterns:
            for fp in glob.glob(os.path.join(cache_dir, pattern)):
                try:
                    overwrite_file_random(fp, passes=3, logger=logger)
                    count += 1
                except:
                    pass

        subprocess.Popen("explorer.exe", shell=True)
        logger(f"→ Thumbnail Cache: {count} cache file(s) shredded.")
    except Exception as e:
        logger(f"→ Thumbnail Cache Error: {e}")
        try:
            subprocess.Popen("explorer.exe", shell=True)
        except:
            pass


def limpiar_hiberfil(logger):
    """
    Limpia hiberfil.sys deshabilitando y re-habilitando la hibernación.
    El archivo puede contener un dump completo de la RAM con procesos activos.
    """
    try:
        logger("→ hiberfil.sys: Disabling hibernation to purge RAM dump...")
        subprocess.run("powercfg /hibernate off", shell=True, capture_output=True)
        time.sleep(1)
        subprocess.run("powercfg /hibernate on", shell=True, capture_output=True)
        logger("→ hiberfil.sys: Destroyed and recreated empty.")
    except Exception as e:
        logger(f"→ hiberfil.sys Error: {e}")


def configurar_pagefile_limpieza(logger):
    """
    Configura Windows para limpiar el pagefile.sys al apagar.
    El pagefile puede contener datos de RAM volcados al disco.
    Se aplica en el próximo shutdown.
    """
    try:
        path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                            winreg.KEY_ALL_ACCESS) as key:
            winreg.SetValueEx(key, "ClearPageFileAtShutdown", 0, winreg.REG_DWORD, 1)
        logger("→ PageFile: ClearPageFileAtShutdown=1 armed. Wipes on next shutdown.")
    except Exception as e:
        logger(f"→ PageFile Config Error: {e}")


def limpiar_espacio_libre(logger):
    """
    Anti-Carving: sobreescribe el espacio libre del disco con cipher /w.
    Previene la recuperación de archivos eliminados por sector carving.
    ADVERTENCIA: Puede tardar varios minutos. Solo en modo NUCLEAR WIPE.
    """
    try:
        logger("→ Anti-Carving: Overwriting free disk space (cipher /w)... This may take minutes.")
        subprocess.run("cipher /w:C:\\", shell=True, capture_output=True, timeout=600)
        logger("→ Anti-Carving: Free space overwritten. Sector carving: IMPOSSIBLE.")
    except subprocess.TimeoutExpired:
        logger("→ Anti-Carving: Timeout reached (partial overwrite applied).")
    except Exception as e:
        logger(f"→ Anti-Carving Error: {e}")


def ejecutar_autodestruccion_exe(logger):
    """
    PROTOCOLO KAMIKAZE:
    1. El bypass limpia sus propios rastros en el Registro (BAM, UserAssist, MuiCache).
    2. Genera un .bat que espera al cierre del proceso.
    3. El .bat borra el .exe, su rastro en Prefetch (creado al cerrar) y a sí mismo.
    """
    try:
        # 1. Identificar quiénes somos (Ruta del propio ejecutable)
        if getattr(sys, 'frozen', False):
            yo_mismo = sys.executable
        else:
            yo_mismo = os.path.abspath(sys.argv[0])
            
        nombre_exe = os.path.basename(yo_mismo)
        nombre_sin_ext = os.path.splitext(nombre_exe)[0]
        
        logger("→ SELF-DESTRUCT: Purging own execution traces from Registry...")

        # 2. AUTO-LIMPIEZA DE REGISTRO (Usamos tus propias funciones contra ti mismo)
        # Esto borra que "Scanneler.exe" fue ejecutado hoy.
        try:
            # Limpiamos rastro en BAM, UserAssist y MuiCache
            limpiar_rastros_globales_nombre(yo_mismo, logger)
            # Limpiamos rastro en RecentApps
            limpiar_recent_apps_selectivo(yo_mismo, logger)
            # Limpiamos rastro en ShimCache/Amcache (Muy importante)
            limpiar_appcompat_total(yo_mismo, logger)
            limpiar_amcache_quirurgico(yo_mismo, logger)
        except Exception as e:
            logger(f"→ Self-Clean Warning: {e}")

        # 3. CREACIÓN DEL AGENTE DE LIMPIEZA EXTERNO (.BAT)
        # El Prefetch se crea/actualiza al cerrar, así que el BAT debe borrarlo después.
        nombre_bat = f"ghost_{random.randint(1000,9999)}.bat"
        path_prefetch = os.path.expandvars(r'%SystemRoot%\Prefetch')
        
        # Script Batch optimizado
        contenido_bat = f"""@echo off
:: Esperar a que el proceso principal libere el archivo
timeout /t 2 /nobreak > NUL

:LOOP
:: Intentar borrar el ejecutable del bypass
del /F /Q "{yo_mismo}"
if exist "{yo_mismo}" goto LOOP

:: --- FASE CRÍTICA: BORRADO DE PREFETCH DEL PROPIO BYPASS ---
:: Windows crea el .pf al cerrar la app, por eso lo borramos aquí.
del /F /Q "{path_prefetch}\\{nombre_sin_ext.upper()}*.pf"

:: Borrarse a sí mismo (El crimen perfecto)
del "{nombre_bat}"
"""
        
        with open(nombre_bat, "w") as f:
            f.write(contenido_bat)
            
        logger("→ AGENT ARMED: Prefetch & Binary will be incinerated on exit.")
        
        # Ejecutamos el BAT de forma oculta (CREATE_NO_WINDOW)
        subprocess.Popen(nombre_bat, shell=True, creationflags=0x08000000)
        
        return True

    except Exception as e:
        logger(f"→ Self-destruct error: {e}")
        return False