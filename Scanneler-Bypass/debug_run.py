import sys
print("[1] Iniciando diagnóstico...")

try:
    import requests
    print("[2] Librería 'requests' OK")
except ImportError:
    print("[!] ERROR: No tienes instalada la librería 'requests'. Ejecuta: pip install requests")

try:
    import customtkinter
    print("[3] Librería 'customtkinter' OK")
except ImportError:
    print("[!] ERROR: No tienes instalada la librería 'customtkinter'. Ejecuta: pip install customtkinter")

try:
    print("[4] Intentando importar logic.py...")
    import logic
    print("[5] Importación de logic.py EXITOSA")
except Exception as e:
    print(f"[!] ERROR CRÍTICO EN LOGIC.PY: {e}")
    import traceback
    traceback.print_exc()

print("[6] Fin del diagnóstico.")
input("Presiona Enter para cerrar...")