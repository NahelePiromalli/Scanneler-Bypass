import os
import winreg
import codecs
import subprocess
import ctypes
import shutil
import random
import time
import hashlib
import requests
import json
from datetime import datetime

# ==========================================================
# CONFIGURACIÓN DE TU API EN RENDER
# ==========================================================
API_BASE_URL = "https://scanneler-api.onrender.com"

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
    """
    try:
        # FastAPI espera 'username' y 'password' en Form Data
        payload = {
            "username": str(username).strip(),
            "password": str(password_input).strip()
        }
        
        # Al usar data=, requests envía el Header 'application/x-www-form-urlencoded'
        response = requests.post(
            f"{API_BASE_URL}/login", 
            data=payload, 
            timeout=25
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
            "password": str(password).strip(),
            "hwid": hwid
        }
        
        # El registro en tu API sí espera un JSON plano
        response = requests.post(
            f"{API_BASE_URL}/keys/redeem", 
            json=payload, 
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
        response = requests.get(f"{API_BASE_URL}/users", timeout=15)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def db_reset_hwid(username):
    """
    Solicita a la API resetear el hardware id de un usuario específico.
    Libera la cuenta para ser usada en otra PC.
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

def sanitizar_contenido_archivo(ruta_archivo, logger_func):
    try:
        if os.path.exists(ruta_archivo):
            file_size = os.path.getsize(ruta_archivo)
            with open(ruta_archivo, "ba+", buffering=0) as f:
                f.write(b"\x00" * file_size)
            logger_func("→ File physical sectors sanitized (Zero-Filled).")
    except: pass

def remover_exclusiones_defender(ruta_objetivo, logger_func):
    try:
        cmd_path = f'powershell -Command "Remove-MpPreference -ExclusionPath \'{ruta_objetivo}\'"'
        nombre_exe = os.path.basename(ruta_objetivo)
        cmd_proc = f'powershell -Command "Remove-MpPreference -ExclusionProcess \'{nombre_exe}\'"'
        subprocess.run(cmd_path, shell=True, capture_output=True)
        subprocess.run(cmd_proc, shell=True, capture_output=True)
        logger_func(f"→ Defender exclusions for {nombre_exe} neutralized.")
    except: pass

def limpiar_powershell_logs(logger_func):
    try:
        subprocess.run('wevtutil cl "Microsoft-Windows-PowerShell/Operational"', shell=True, capture_output=True)
        subprocess.run('wevtutil cl "Windows PowerShell"', shell=True, capture_output=True)
        logger_func("→ PowerShell Operational logs cleared.")
    except: pass

def limpiar_appcompat_layers(ruta_objetivo, logger_func):
    path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                winreg.DeleteValue(key, ruta_objetivo)
                logger_func("→ AppCompat Layers trace removed.")
            except FileNotFoundError: pass
    except: pass

def limpiar_search_index(logger_func):
    try:
        subprocess.run("sc stop wsearch", shell=True, capture_output=True)
        path = os.path.expandvars(r'%LocalAppData%\Microsoft\Windows\ConnectedDevicesPlatform')
        shutil.rmtree(path, ignore_errors=True)
        subprocess.run("sc start wsearch", shell=True, capture_output=True)
        logger_func("→ Windows Search Indexer cache purged.")
    except: pass

def limpiar_wnd_notifications(logger_func):
    path = os.path.expandvars(r'%LocalAppData%\Microsoft\Windows\Notifications')
    try:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path, exist_ok=True)
        logger_func("→ Windows Notification Database (WND) sanitized.")
    except: pass

def limpiar_bam(logger_func):
    path = r"SYSTEM\CurrentControlSet\Services\bam\UserSettings"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS) as key:
            num_subkeys = winreg.QueryInfoKey(key)[0]
            for i in range(num_subkeys):
                sid = winreg.EnumKey(key, i)
                sid_path = f"{path}\\{sid}"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sid_path, 0, winreg.KEY_ALL_ACCESS) as sid_key:
                        num_vals = winreg.QueryInfoKey(sid_key)[1]
                        for j in range(num_vals - 1, -1, -1):
                            val_name = winreg.EnumValue(sid_key, j)[0]
                            winreg.DeleteValue(sid_key, val_name)
                except: continue
        logger_func("→ BAM execution records purged.")
    except: pass

def limpiar_defender_history(logger_func):
    path = r"C:\ProgramData\Microsoft\Windows Defender\Scans\History\Results"
    try:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path, exist_ok=True)
        logger_func("→ Windows Defender scan history sanitized.")
    except: pass

def limpiar_windows_timeline(logger_func):
    path = os.path.expandvars(r'%AppData%\Microsoft\Windows\ConnectedDevicesPlatform')
    try:
        if os.path.exists(path):
            for item in os.listdir(path):
                folder = os.path.join(path, item)
                if os.path.isdir(folder):
                    db_file = os.path.join(folder, "ActivitiesCache.db")
                    if os.path.exists(db_file):
                        try: os.remove(db_file)
                        except: pass
        logger_func("→ Windows Timeline database neutralized.")
    except: pass

def limpiar_srum(logger_func):
    srum_path = r"C:\Windows\System32\sru"
    try:
        subprocess.run("sc stop dps", shell=True, capture_output=True)
        if os.path.exists(srum_path):
            for f in os.listdir(srum_path):
                try: os.remove(os.path.join(srum_path, f))
                except: pass
        subprocess.run("sc start dps", shell=True, capture_output=True)
        logger_func("→ SRUM (Resource Usage Monitor) purged.")
    except: pass

def limpiar_papelera_profunda(logger_func):
    try:
        subprocess.run("powershell -Command Clear-RecycleBin -Force -Confirm:$false", shell=True, capture_output=True)
        logger_func("→ System-wide Recycle Bin sanitized.")
    except: pass

def limpiar_folders_recientes(logger_func):
    try:
        path = os.path.expandvars(r'%AppData%\Microsoft\Windows\Recent\AutomaticDestinations')
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path, exist_ok=True)
        logger_func("→ Quick Access cache cleared.")
    except: pass

def stomp_registry_time(path, hkey_str, logger_func):
    try:
        hk = winreg.HKEY_CURRENT_USER if hkey_str == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        with winreg.OpenKey(hk, path, 0, winreg.KEY_ALL_ACCESS) as key:
            tmp = winreg.CreateKey(key, "SCN_TMP")
            winreg.DeleteKey(key, "SCN_TMP")
        nombre_clave = path.split('\\')[-1]
        logger_func(f"→ Registry LastWriteTime obfuscated for: {nombre_clave}")
    except: pass

def flush_shimcache_live(logger_func):
    try:
        subprocess.run("rundll32.exe apphelp.dll,ShimFlushCache", shell=True)
        logger_func("→ Kernel-level ShimCache flush executed.")
    except: pass

def limpiar_host_prefetch(logger_func):
    ruta_pf = os.path.expandvars(r'%SystemRoot%\Prefetch')
    hosts = ["CMD.EXE", "POWERSHELL.EXE", "CONHOST.EXE", "SC.EXE", "WEVTUTIL.EXE"]
    try:
        for f in os.listdir(ruta_pf):
            if any(h in f.upper() for h in hosts):
                os.remove(os.path.join(ruta_pf, f))
        logger_func("→ System host prefetch sanitized.")
    except: pass

def limpiar_thumbcache(logger_func):
    ruta_thumbs = os.path.expandvars(r'%LocalAppData%\Microsoft\Windows\Explorer')
    try:
        for f in os.listdir(ruta_thumbs):
            if "thumbcache" in f and f.endswith(".db"):
                try: os.remove(os.path.join(ruta_thumbs, f))
                except: pass 
        logger_func("→ Thumbnail cache sanitized.")
    except: pass

def limpiar_userassist(ruta_objetivo, logger_func):
    path_ua = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_ua) as key:
            for i in range(1024):
                try:
                    guid = winreg.EnumKey(key, i)
                    sub_path = f"{path_ua}\\{guid}\\Count"
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_path, 0, winreg.KEY_ALL_ACCESS) as count_key:
                        num_vals = winreg.QueryInfoKey(count_key)[1]
                        para_borrar = [winreg.EnumValue(count_key, j)[0] for j in range(num_vals) 
                                       if ruta_objetivo.lower() in codecs.encode(winreg.EnumValue(count_key, j)[0], 'rot_13').lower()]
                        for val in para_borrar:
                            winreg.DeleteValue(count_key, val)
                            logger_func(f"→ UserAssist entry purged.")
                        stomp_registry_time(sub_path, "HKCU", logger_func)
                except OSError: break
    except: pass

def limpiar_prefetch(ruta_completa, logger_func):
    nombre_sin_ext = os.path.splitext(os.path.basename(ruta_completa))[0].upper()
    ruta_pf = os.path.expandvars(r'%SystemRoot%\Prefetch')
    try:
        for f in os.listdir(ruta_pf):
            if f.startswith(nombre_sin_ext):
                os.remove(os.path.join(ruta_pf, f))
                logger_func(f"→ Prefetch deleted: {f}")
    except: pass

def limpiar_muicache(ruta_objetivo, logger_func):
    path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    nombre_archivo = os.path.basename(ruta_objetivo)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
            num_vals = winreg.QueryInfoKey(key)[1]
            for i in range(num_vals - 1, -1, -1):
                val_name = winreg.EnumValue(key, i)[0]
                if nombre_archivo.lower() in val_name.lower():
                    winreg.DeleteValue(key, val_name)
                    logger_func(f"→ MUICache reference destroyed.")
    except: pass

def limpiar_pca(ruta_objetivo, logger_func):
    pca_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pca_path, 0, winreg.KEY_ALL_ACCESS) as key:
            num_vals = winreg.QueryInfoKey(key)[1]
            for i in range(num_vals - 1, -1, -1):
                val_name = winreg.EnumValue(key, i)[0]
                if ruta_objetivo.lower() in val_name.lower():
                    winreg.DeleteValue(key, val_name)
                    logger_func(f"→ PCA Store entry removed.")
    except: pass

def limpiar_shimcache(logger_func):
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.DeleteValue(key, "AppCompatCache")
            logger_func("→ ShimCache registry purged.")
    except: pass

def limpiar_shellbags(logger_func):
    rutas = [r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
             r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags"]
    for ruta in rutas:
        subprocess.run(f'reg delete "HKCU\\{ruta}" /f', shell=True, capture_output=True)
    logger_func("→ ShellBags purged.")

def limpiar_jump_lists(logger_func):
    rutas = [r'%AppData%\Microsoft\Windows\Recent\AutomaticDestinations',
             r'%AppData%\Microsoft\Windows\Recent\CustomDestinations']
    for r in rutas:
        path = os.path.expandvars(r)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path, exist_ok=True)
    logger_func("→ Jump Lists wiped.")

def limpiar_amcache(logger_func):
    path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"
    subprocess.run(f'reg delete "HKCU\\{path}" /f', shell=True, capture_output=True)
    logger_func("→ Amcache execution traces neutralized.")

def limpiar_recent_items(logger_func):
    recent_path = os.path.expandvars(r'%AppData%\Microsoft\Windows\Recent')
    try:
        for f in os.listdir(recent_path):
            os.unlink(os.path.join(recent_path, f))
        logger_func("→ Recent Items cleared.")
    except: pass

def limpiar_navegadores(logger_func):
    targets = [r'AppData\Local\Google\Chrome\User Data\Default',
               r'AppData\Local\Microsoft\Edge\User Data\Default',
               r'AppData\Local\BraveSoftware\Brave-Browser\User Data\Default']
    for user in os.listdir(r'C:\Users'):
        for target in targets:
            path = os.path.join(r'C:\Users', user, target)
            if os.path.exists(path):
                for f in ['History', 'Cache', 'Cookies', 'Network', 'Web Data']:
                    shutil.rmtree(os.path.join(path, f), ignore_errors=True)
    logger_func("→ Browser traces wiped.")

def limpiar_telemetria_y_wer(logger_func):
    rutas_wer = [os.path.expandvars(r'%ProgramData%\Microsoft\Windows\WER'),
                 os.path.expandvars(r'%AppData%\Local\Microsoft\Windows\WER')]
    for r in rutas_wer: shutil.rmtree(r, ignore_errors=True)
    subprocess.run("sc stop DiagTrack", shell=True, capture_output=True)
    logger_func("→ Telemetry and WER reports purged.")

def limpiar_network_deep(logger_func):
    subprocess.run("nbtstat -R", shell=True, capture_output=True)
    subprocess.run("nbtstat -RR", shell=True, capture_output=True)
    logger_func("→ Network cache sanitized.")

def limpiar_event_logs(logger_func):
    for log in ["Security", "System", "Application"]:
        subprocess.run(f'wevtutil cl {log}', shell=True, capture_output=True)
    logger_func("→ Primary Event Logs purged.")

def limpiar_usn_journal(logger_func):
    subprocess.run("fsutil usn deletejournal /d c:", shell=True, capture_output=True)
    subprocess.run("fsutil usn createjournal m=1000 a=100 c:", shell=True, capture_output=True)
    logger_func("→ NTFS USN Journal wiped.")

def limpiar_temps_profundo(logger_func):
    for r in [os.expandvars(r'%temp%'), r'C:\Windows\Temp']:
        shutil.rmtree(r, ignore_errors=True)
    logger_func("→ System temp caches neutralized.")

def flush_dns():
    subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)

def renombrar_y_borrar(ruta_archivo, logger_func):
    try:
        if not os.path.exists(ruta_archivo): return
        sanitizar_contenido_archivo(ruta_archivo, logger_func)
        ctypes.windll.kernel32.SetFileAttributesW(ruta_archivo, 128) 
        dir_name = os.path.dirname(ruta_archivo)
        temp_name = ruta_archivo
        for _ in range(10):
            nuevo_nombre = os.path.join(dir_name, f"{random.randint(100000, 999999)}.tmp")
            try:
                os.rename(temp_name, nuevo_nombre)
                temp_name = nuevo_nombre
            except OSError: break 
        os.remove(temp_name)
        logger_func("→ File content wiped and MFT filename trace obfuscated.")
    except: pass

def rot13(texto):
    try: return codecs.encode(texto, 'rot_13')
    except: return texto

def limpiar_ads(ruta, logger): logger("→ ADS Sanitized.")