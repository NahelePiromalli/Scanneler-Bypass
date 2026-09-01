import customtkinter as ctk
from tkinter import filedialog, messagebox, Canvas
from PIL import Image
import os
import random
import ctypes
import sys
import time
from datetime import datetime
import logic 

# --- PRE-ARRANQUE: EVITAR ERRORES DE ESCALADO ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# ==========================================================
# SISTEMA DE AUTO-ELEVACIÓN
# ==========================================================
def solicitar_admin():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        if "--elevated" not in sys.argv:
            try:
                params = " ".join(sys.argv) + " --elevated"
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            except: 
                pass
            sys.exit()

# Colores Core 2026 - Paleta "Deep Nebula"
BG_DARK = "#050507"
PANEL_BG = "#0A0A12"
BORDER_COLOR = "#1F1F33"
VIOLETA_NEON = "#8B5CF6"
MAGENTA_GLOW = "#D946EF"
GRID_COLOR = "#120B26"
ERROR_RED = "#FF4B4B"

# --- SISTEMA DE IDIOMAS 2026 ---
LANGUAGES = {
    "ES": {
        "launch": "INICIAR SISTEMA CORE",
        "admin_btn": "🛡️ PANEL ADMIN",
        "settings": "⚙️ AJUSTES",
        "nodes": "👤 NÓDULOS ACTIVOS",
        "mint": "🔑 GENERAR LICENCIAS",
        "target": "SELECCIONAR ARCHIVO",
        "execute": "EJECUTAR BYPASS NEURAL",
        "lang_title": "CONFIGURACIÓN",
        "purge": "ELIMINAR",
        "locked": "BLOQUEADO",
        "ready": "LISTO",
        "back": "← VOLVER",
        "refresh": "REFRESCAR DB",
        "unlock": "LIBERAR HWID",
        "tier": "TIPO DE PLAN",
        "amount": "CANTIDAD",
        "mint_btn": "GENERAR LLAVES",
        "success_reg": "CUENTA ACTIVADA CON ÉXITO",
        "error_reg": "ERROR DE ACTIVACIÓN"
    },
    "EN": {
        "launch": "LAUNCH CORE SYSTEM",
        "admin_btn": "🛡️ ADMIN PANEL",
        "settings": "⚙️ SETTINGS",
        "nodes": "👤 ACTIVE NODES",
        "mint": "🔑 LICENSE MINT",
        "target": "SELECT TARGET BINARY",
        "execute": "EXECUTE NEURAL BYPASS",
        "lang_title": "SETTINGS",
        "purge": "PURGE",
        "locked": "LOCKED",
        "ready": "READY",
        "back": "← BACK",
        "refresh": "REFRESH DATABASE",
        "unlock": "UNLOCK HWID",
        "tier": "MEMBERSHIP TIER",
        "amount": "QUANTITY",
        "mint_btn": "MINT LICENSES",
        "success_reg": "ACCOUNT ACTIVATED SUCCESSFULLY",
        "error_reg": "ACTIVATION ERROR"
    }
}
CURRENT_LANG = "ES"

# ==========================================================
# CLASE: ALERTA PERSONALIZADA CYBER NEON
# ==========================================================
# ==========================================================
# CLASE: ALERTA PERSONALIZADA CYBER NEON (CORREGIDA)
# ==========================================================
class CyberAlert(ctk.CTkToplevel):
    def __init__(self, master, title="SYSTEM", message="", is_error=False):
        super().__init__(master)
        self.title("")
        self.geometry("400x200")
        self.overrideredirect(True) # Quita bordes de Windows
        self.attributes("-topmost", True)
        
        # CORRECCIÓN: Usar BG_DARK en lugar de "transparent"
        # Esto evita el ValueError en versiones nuevas de CustomTkinter
        self.configure(fg_color=BG_DARK) 
        
        # Centrar en pantalla
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - 200
        y = (screen_h // 2) - 100
        self.geometry(f"400x200+{x}+{y}")

        # Contenedor Nebula
        main_color = ERROR_RED if is_error else VIOLETA_NEON
        
        # Añadimos un padding pequeño al pack para que el BG_DARK 
        # haga un efecto de sombra externa sutil
        self.frame = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=20, 
                                  border_width=2, border_color=main_color)
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Header Glow
        self.lbl_title = ctk.CTkLabel(self.frame, text=title.upper(), 
                                      font=("Inter", 16, "bold"), text_color=main_color)
        self.lbl_title.pack(pady=(20, 10))

        self.lbl_msg = ctk.CTkLabel(self.frame, text=message, font=("Inter", 13), 
                                    text_color="#FFFFFF", wraplength=350)
        self.lbl_msg.pack(pady=10)

        self.btn_ok = ctk.CTkButton(self.frame, text="OK", fg_color=main_color, 
                                    hover_color=MAGENTA_GLOW, width=120, height=35, 
                                    corner_radius=10, command=self.destroy)
        self.btn_ok.pack(pady=(10, 20))
        
        # Efecto de parpadeo inicial
        self.fade_in()

    def fade_in(self):
        self.attributes("-alpha", 0.0)
        for i in range(1, 11):
            try:
                self.attributes("-alpha", i/10)
                self.update()
                time.sleep(0.01) # Un poco más rápido para mejor respuesta
            except:
                break
            
class ScannelerBypass(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Scanneler Bypass")
        self.geometry("1000x800")
        self.configure(fg_color=BG_DARK)
        self.ruta_seleccionada = ""
        
        self.bg_canvas = Canvas(self, bg=BG_DARK, highlightthickness=0, bd=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_canvas.tag_lower("all") 
        self.draw_cyber_grid()
        self.glow_obj = self.draw_central_glow()
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (LoginFrame, InicioFrame, BypassFrame, AdminFrame):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.splash_screen = ctk.CTkFrame(self, fg_color=BG_DARK)
        self.splash_screen.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.setup_splash_screen()
        
        self.pulse_direction = 1
        self.after(1000, self.animate_glow_pulse)
        self.after(500, self.run_splash_sequence)

    def draw_cyber_grid(self):
        w, h = 1000, 800
        for i in range(0, w, 40):
            self.bg_canvas.create_line(i, 0, i, h, fill=GRID_COLOR, width=1)
        for i in range(0, h, 40):
            self.bg_canvas.create_line(0, i, w, i, fill=GRID_COLOR, width=1)

    def draw_central_glow(self):
        self.bg_canvas.create_oval(-100, -100, 400, 400, fill="#0D071F", outline="")
        self.bg_canvas.create_oval(700, 500, 1100, 900, fill="#13061A", outline="")
        return self.bg_canvas.create_oval(350, 250, 650, 550, fill="#120826", outline=VIOLETA_NEON, width=2)

    def animate_glow_pulse(self):
        try:
            current_width = float(self.bg_canvas.itemcget(self.glow_obj, "width"))
            new_width = current_width + (0.1 * self.pulse_direction)
            if new_width > 4 or new_width < 1: self.pulse_direction *= -1
            self.bg_canvas.itemconfig(self.glow_obj, width=new_width)
            self.after(50, self.animate_glow_pulse)
        except: pass

    def setup_splash_screen(self):
        try:
            if os.path.exists("Scanneler.png"):
                logo_raw = Image.open("Scanneler.png")
                logo_img = ctk.CTkImage(logo_raw, size=(220, 220))
                ctk.CTkLabel(self.splash_screen, image=logo_img, text="").pack(pady=(150, 20))
            else: raise Exception
        except:
            ctk.CTkLabel(self.splash_screen, text="[ SCANNELER ]", font=("Inter", 60, "bold"), text_color=VIOLETA_NEON).pack(pady=(200, 20))
        
        self.splash_text = ctk.CTkLabel(self.splash_screen, text="INICIALIZANDO BYPASS...", font=("Inter", 14, "bold"))
        self.splash_text.pack(pady=10)
        self.splash_progress = ctk.CTkProgressBar(self.splash_screen, progress_color=VIOLETA_NEON, width=400, height=8)
        self.splash_progress.set(0)
        self.splash_progress.pack(pady=20)

    def run_splash_sequence(self):
        steps = ["LOADING VIRTUAL KERNEL...", "CONNECTING TO RENDER API...", "ESTABLISHING DATABASE LINK...", "READY"]
        for i, step in enumerate(steps):
            self.splash_text.configure(text=step)
            self.splash_progress.set((i + 1) / len(steps))
            self.update()
            time.sleep(0.5)
        self.splash_screen.destroy()
        self.show_frame(LoginFrame)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

# ==========================================================
# CLASE: LOGIN
# ==========================================================
class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.login_content = ctk.CTkFrame(self, width=420, height=580, fg_color=PANEL_BG, corner_radius=30, border_width=2, border_color=BORDER_COLOR)
        self.login_content.place(relx=0.5, rely=0.5, anchor="center")

        try:
            logo_raw = Image.open("Scanneler.png")
            logo_img = ctk.CTkImage(logo_raw, size=(180, 180))
            ctk.CTkLabel(self.login_content, image=logo_img, text="").pack(pady=(40, 0))
        except:
            ctk.CTkLabel(self.login_content, text="S C A N N E L E R", font=("Inter", 28, "bold"), text_color=VIOLETA_NEON).pack(pady=(40, 5))

        ctk.CTkLabel(self.login_content, text="S E C U R E   A C C E S S   P R O T O C O L", font=("Inter", 10, "bold"), text_color="#4B5563").pack()

        self.entry_user = ctk.CTkEntry(self.login_content, width=320, height=50, placeholder_text="USERNAME", 
                                       justify="center", fg_color="#08080E", border_color=BORDER_COLOR, text_color=VIOLETA_NEON) 
        self.entry_user.pack(pady=(30, 15))

        self.entry_pass = ctk.CTkEntry(self.login_content, width=320, height=50, placeholder_text="PASSWORD", 
                                       show="*", justify="center", fg_color="#08080E", border_color=BORDER_COLOR, text_color=VIOLETA_NEON) 
        self.entry_pass.pack(pady=10)

        self.lbl_status = ctk.CTkLabel(self.login_content, text="SYSTEM IDLE", font=("Consolas", 11), text_color="#4B5563")
        self.lbl_status.pack(pady=10)

        ctk.CTkButton(self.login_content, text="INITIALIZE LOGIN", font=("Inter", 14, "bold"), fg_color=VIOLETA_NEON, hover_color=MAGENTA_GLOW, height=50, width=320, corner_radius=15, command=self.handle_auth).pack(pady=(15, 10))
        ctk.CTkButton(self.login_content, text="REDEEM LICENSE KEY", font=("Inter", 12), fg_color="transparent", text_color="#8B8B9E", border_width=1, border_color=BORDER_COLOR, height=40, width=320, corner_radius=15, command=self.open_redeem_window).pack(pady=5)

    def handle_auth(self):
        u, p = self.entry_user.get().strip(), self.entry_pass.get().strip()
        if not u or not p: return
        self.lbl_status.configure(text="AUTHENTICATING...", text_color=VIOLETA_NEON)
        self.update()
        result = logic.db_validate_login(u, p)
        if isinstance(result, (list, tuple)) and result[0]:
            role = str(result[2]).lower()
            if role in ["admin", "super_admin"]:
                self.controller.frames[InicioFrame].btn_admin.place(relx=0.5, rely=0.75, anchor="center")
            self.controller.show_frame(InicioFrame)
        else:
            msg = str(result[1]) if isinstance(result, (list, tuple)) else "ERROR"
            self.lbl_status.configure(text=msg.upper(), text_color=ERROR_RED)

    def open_redeem_window(self):
        redeem_win = ctk.CTkToplevel(self)
        redeem_win.title("License Activation")
        redeem_win.geometry("450x620")
        redeem_win.configure(fg_color=BG_DARK)
        redeem_win.attributes("-topmost", True)
        
        main_box = ctk.CTkFrame(redeem_win, fg_color=PANEL_BG, corner_radius=25, border_width=1, border_color=BORDER_COLOR)
        main_box.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(main_box, text="ACTIVATE KEY", font=("Inter", 26, "bold"), text_color=VIOLETA_NEON).pack(pady=(30, 20))
        
        entries = []
        placeholders = ["LICENSE KEY", "NEW USERNAME", "PASSWORD", "CONFIRM PASSWORD"]
        for p in placeholders:
            e = ctk.CTkEntry(main_box, width=320, height=45, placeholder_text=p, justify="center", fg_color="#08080E", border_color=BORDER_COLOR, text_color=VIOLETA_NEON)
            if "PASSWORD" in p: e.configure(show="*")
            e.pack(pady=10)
            entries.append(e)

        lbl_err = ctk.CTkLabel(main_box, text="", font=("Inter", 11), text_color=ERROR_RED)
        lbl_err.pack(pady=5)

        def process():
            if entries[2].get() != entries[3].get():
                lbl_err.configure(text="PASSWORDS DO NOT MATCH")
                return
            success, msg = logic.db_redeem_key(entries[1].get().strip(), entries[0].get().strip(), entries[2].get().strip())
            if success:
                # REEMPLAZADO: Alerta personalizada
                CyberAlert(self, title="SYSTEM", message=LANGUAGES[CURRENT_LANG]["success_reg"])
                redeem_win.destroy()
            else:
                lbl_err.configure(text=str(msg).upper())

        ctk.CTkButton(main_box, text="ACTIVATE NOW", font=("Inter", 14, "bold"), fg_color=VIOLETA_NEON, height=50, width=320, corner_radius=15, command=process).pack(pady=30)

# ==========================================================
# CLASE: INICIO
# ==========================================================
class InicioFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # --- BACKGROUND MATRIX ANIMATION ---
        self.matrix_canvas = Canvas(self, bg=BG_DARK, highlightthickness=0, bd=0)
        self.matrix_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.matrix_chars = "0123456789ABCDEF@#$%&*"
        self.drops = [0] * 50  

        self.main_ui_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_ui_container.place(relx=0, rely=0, relwidth=1, relheight=1)

        # --- LOGO & TITLES ---
        try:
            logo_raw = Image.open("Scanneler.png")
            self.logo_img = ctk.CTkImage(logo_raw, size=(280, 280))
            ctk.CTkLabel(self.main_ui_container, image=self.logo_img, text="").place(relx=0.5, rely=0.32, anchor="center")
        except: pass

        self.lbl_bypass = ctk.CTkLabel(self.main_ui_container, text="S C A N N E L E R   B Y P A S S", font=("Inter", 22, "bold"), text_color=VIOLETA_NEON)
        self.lbl_bypass.place(relx=0.5, rely=0.52, anchor="center")

        # --- MAIN BUTTONS ---
        self.btn_main = ctk.CTkButton(self.main_ui_container, text=LANGUAGES[CURRENT_LANG]["launch"], font=("Inter", 14, "bold"), fg_color=VIOLETA_NEON, width=260, height=60, corner_radius=15, command=lambda: controller.show_frame(BypassFrame))
        self.btn_main.place(relx=0.25, rely=0.75, anchor="center")
        
        self.btn_admin = ctk.CTkButton(self.main_ui_container, text=LANGUAGES[CURRENT_LANG]["admin_btn"], font=("Inter", 13, "bold"), fg_color="#300a0a", border_width=2, border_color=ERROR_RED, text_color=ERROR_RED, width=220, height=50, corner_radius=15, command=lambda: controller.show_frame(AdminFrame))
        self.btn_admin.place_forget() 

        self.btn_settings = ctk.CTkButton(self.main_ui_container, text=LANGUAGES[CURRENT_LANG]["settings"], font=("Inter", 13, "bold"), fg_color="#14141F", border_width=1, border_color=BORDER_COLOR, width=200, height=50, corner_radius=15, command=self.show_settings_panel)
        self.btn_settings.place(relx=0.74, rely=0.75, anchor="center")

        # --- SETTINGS PANEL (CENTRALIZADO) ---
        self.settings_panel = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=30, border_width=2, border_color=BORDER_COLOR)
        self.settings_panel.place(relx=1.5, rely=0.5, anchor="center", relwidth=0.48, relheight=0.85)
        
        self.lbl_set_title = ctk.CTkLabel(self.settings_panel, text=LANGUAGES[CURRENT_LANG]["lang_title"], font=("Inter", 24, "bold"), text_color=VIOLETA_NEON)
        self.lbl_set_title.pack(pady=(20, 10))

        # Idiomas
        lang_frame = ctk.CTkFrame(self.settings_panel, fg_color="transparent")
        lang_frame.pack(pady=5)
        ctk.CTkButton(lang_frame, text="ESPAÑOL", fg_color="#1A1A2E", width=120, height=35, command=lambda: self.change_lang("ES")).pack(side="left", padx=5)
        ctk.CTkButton(lang_frame, text="ENGLISH", fg_color="#1A1A2E", width=120, height=35, command=lambda: self.change_lang("EN")).pack(side="left", padx=5)
        
        # --- SECCIÓN: BINDEO DE HOTKEY ---
        ctk.CTkLabel(self.settings_panel, text="GLOBAL HOTKEY BIND", font=("Inter", 12, "bold"), text_color=VIOLETA_NEON).pack(pady=(15, 5))
        
        self.btn_bind = ctk.CTkButton(
            self.settings_panel, 
            text="CLICK TO BIND BYPASS", 
            fg_color="#14141F", 
            border_width=1, 
            border_color=BORDER_COLOR,
            height=40, 
            command=self.iniciar_escucha_bind
        )
        self.btn_bind.pack(pady=5, padx=40, fill="x")

        # --- SECCIÓN: DEEP SCAN (AVANZADO) ---
        ctk.CTkLabel(self.settings_panel, text="ADVANCED ENGINE", font=("Inter", 12, "bold"), text_color=VIOLETA_NEON).pack(pady=(15, 5))
        
        self.sw_deep_scan = ctk.CTkSwitch(
            self.settings_panel, 
            text="ENABLE DEEP REGISTRY SCAN",
            font=("Inter", 11),
            progress_color=VIOLETA_NEON,
            command=self.toggle_deep_scan
        )
        self.sw_deep_scan.pack(pady=5)
        
        self.lbl_warning = ctk.CTkLabel(
            self.settings_panel, 
            text="Note: Enabling this may slow down the bypass\nby 10-20 seconds (System Hive Search).",
            font=("Inter", 10, "italic"),
            text_color="gray"
        )
        self.lbl_warning.pack(pady=(0, 10))

        self.btn_set_back = ctk.CTkButton(self.settings_panel, text=LANGUAGES[CURRENT_LANG]["back"], fg_color="transparent", text_color="gray", command=self.hide_settings_panel)
        self.btn_set_back.pack(pady=(15, 10))

        # --- ANIMATIONS INITIALIZATION ---
        self.after(10, self.update_matrix)
        self.after(100, self.animate_button_flicker)

    # ==========================================================
    # LÓGICA DE CONFIGURACIÓN
    # ==========================================================
    def toggle_deep_scan(self):
        """Activa o desactiva la búsqueda global en el registro."""
        # CORRECCIÓN: Modificar directamente la variable en el archivo de lógica
        logic.DEEP_SCAN_ENABLED = self.sw_deep_scan.get() == 1
        
        if logic.DEEP_SCAN_ENABLED:
            self.lbl_warning.configure(text_color=MAGENTA_GLOW)
            # Opcional: Feedback en consola para saber que funcionó
            print("[SYSTEM] DEEP SCAN ENGINE: ARMED") 
        else:
            self.lbl_warning.configure(text_color="gray")
            print("[SYSTEM] DEEP SCAN ENGINE: DISARMED")

    def iniciar_escucha_bind(self):
        self.btn_bind.configure(text="PRESS ANY KEY...", fg_color=MAGENTA_GLOW, border_color=MAGENTA_GLOW)
        self.after(100, self.capturar_tecla)

    def capturar_tecla(self):
        try:
            import keyboard
            evento = keyboard.read_event(suppress=True)
            if evento.event_type == "down":
                tecla_presionada = evento.name
                self.btn_bind.configure(text=f"BOUND TO: {tecla_presionada.upper()}", fg_color="#1A1A2E", border_color=VIOLETA_NEON)
                
                bypass_func = self.controller.frames[BypassFrame].handle_wipe
                log_func = self.controller.frames[BypassFrame].log
                
                logic.registrar_bind_global(tecla_presionada, bypass_func, log_func)
        except Exception as e:
            print(f"Error capturando bind: {e}")

    # ==========================================================
    # ANIMACIONES & UI
    # ==========================================================
    def update_matrix(self):
        self.matrix_canvas.delete("chars")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 1:
            char_w = 20
            num_cols = w // char_w
            if len(self.drops) != num_cols: self.drops = [random.randint(-20, 0) for _ in range(num_cols)]
            for i in range(len(self.drops)):
                char = random.choice(self.matrix_chars)
                x, y = i * char_w, self.drops[i] * 20
                color = random.choice(["#2D1B4E", "#4C1D95", VIOLETA_NEON, "#C084FC"])
                self.matrix_canvas.create_text(x, y, text=char, fill=color, font=("Consolas", 14), tags="chars")
                if y > h and random.random() > 0.975: self.drops[i] = 0
                else: self.drops[i] += 1
        self.matrix_canvas.tag_lower("chars")
        self.after(50, self.update_matrix)

    def animate_button_flicker(self):
        if random.random() > 0.85:
            flash_v, flash_r = random.choice([VIOLETA_NEON, "#FFFFFF"]), random.choice([ERROR_RED, "#300a0a"])
            self.btn_main.configure(fg_color=flash_v)
            if self.btn_admin.winfo_viewable():
                self.btn_admin.configure(border_color=flash_r, text_color=flash_r)
        else:
            self.btn_main.configure(fg_color=VIOLETA_NEON)
            self.btn_admin.configure(border_color=ERROR_RED, text_color=ERROR_RED)
        self.after(random.randint(150, 400), self.animate_button_flicker)

    def show_settings_panel(self):
        self.settings_panel.place(relx=0.5, rely=0.5, anchor="center")
        self.main_ui_container.place_forget()

    def hide_settings_panel(self):
        self.settings_panel.place(relx=1.5, rely=0.5)
        self.main_ui_container.place(relx=0, rely=0, relwidth=1, relheight=1)

    def change_lang(self, lang_code):
        global CURRENT_LANG
        CURRENT_LANG = lang_code
        self.refresh_all_uis()
        self.hide_settings_panel()

    def refresh_all_uis(self):
        self.btn_main.configure(text=LANGUAGES[CURRENT_LANG]["launch"])
        self.btn_admin.configure(text=LANGUAGES[CURRENT_LANG]["admin_btn"])
        self.btn_settings.configure(text=LANGUAGES[CURRENT_LANG]["settings"])
        self.lbl_set_title.configure(text=LANGUAGES[CURRENT_LANG]["lang_title"])
        self.btn_set_back.configure(text=LANGUAGES[CURRENT_LANG]["back"])
        
        # Actualización dinámica de elementos del bypass si existen
        if BypassFrame in self.controller.frames:
            bf = self.controller.frames[BypassFrame]
            bf.btn_sel.configure(text=LANGUAGES[CURRENT_LANG]["target"])
            bf.btn_exe.configure(text=LANGUAGES[CURRENT_LANG]["execute"])

# ==========================================================
# CLASE: ADMIN
# ==========================================================
class AdminFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.admin_box = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=30, border_width=2, border_color=BORDER_COLOR)
        self.admin_box.pack(padx=40, pady=40, fill="both", expand=True)

        header = ctk.CTkFrame(self.admin_box, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=30)
        
        self.btn_back = ctk.CTkButton(header, text=LANGUAGES[CURRENT_LANG]["back"], width=80, 
                                       fg_color="#1A1A2E", text_color="#8B8B9E", corner_radius=10, 
                                       command=lambda: controller.show_frame(InicioFrame))
        self.btn_back.pack(side="left")
        
        self.lbl_head = ctk.CTkLabel(header, text="COMMAND CENTER", font=("Inter", 26, "bold"), text_color="#FFFFFF")
        self.lbl_head.pack(side="left", padx=30)

        self.tabs = ctk.CTkTabview(self.admin_box, segmented_button_selected_color=VIOLETA_NEON, 
                                   segmented_button_unselected_color="#08080E", fg_color="#08080E", corner_radius=20)
        self.tabs.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        self.tab_users = self.tabs.add(LANGUAGES[CURRENT_LANG]["nodes"])
        self.tab_keys = self.tabs.add(LANGUAGES[CURRENT_LANG]["mint"])

        self.users_list_container = ctk.CTkScrollableFrame(self.tab_users, fg_color="transparent")
        self.users_list_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        controls = ctk.CTkFrame(self.tab_users, fg_color="transparent")
        controls.pack(fill="x", pady=10)
        
        self.btn_refresh = ctk.CTkButton(controls, text=LANGUAGES[CURRENT_LANG]["refresh"], 
                                         fg_color=VIOLETA_NEON, height=40, corner_radius=12, command=self.refresh_users)
        self.btn_refresh.pack(side="left", padx=10, expand=True)
        
        self.btn_unlock = ctk.CTkButton(controls, text=LANGUAGES[CURRENT_LANG]["unlock"], 
                                        fg_color="#14141F", border_width=1, border_color=BORDER_COLOR, 
                                        height=40, corner_radius=12, command=self.handle_hwid_reset)
        self.btn_unlock.pack(side="left", padx=10, expand=True)

        self.setup_keys_tab()

    def setup_keys_tab(self):
        for widget in self.tab_keys.winfo_children(): widget.destroy()
        f = ctk.CTkFrame(self.tab_keys, fg_color="transparent")
        f.pack(expand=True)
        
        ctk.CTkLabel(f, text=LANGUAGES[CURRENT_LANG]["tier"], font=("Inter", 12, "bold"), text_color=VIOLETA_NEON).pack(pady=5)
        self.memb_var = ctk.StringVar(value="Monthly")
        ctk.CTkOptionMenu(f, values=["Weekly", "Monthly", "Yearly", "Lifetime"], variable=self.memb_var, 
                          fg_color="#14141F", button_color=VIOLETA_NEON, width=250).pack(pady=10)
        
        ctk.CTkLabel(f, text=LANGUAGES[CURRENT_LANG]["amount"], font=("Inter", 12, "bold"), text_color=VIOLETA_NEON).pack(pady=5)
        self.amount_var = ctk.StringVar(value="1")
        ctk.CTkEntry(f, width=250, justify="center", textvariable=self.amount_var, 
                     fg_color="#08080E", border_color=BORDER_COLOR, text_color=VIOLETA_NEON).pack(pady=10)
        
        ctk.CTkButton(f, text=LANGUAGES[CURRENT_LANG]["mint_btn"], fg_color=MAGENTA_GLOW, 
                      font=("Inter", 14, "bold"), height=50, width=250, corner_radius=15, 
                      command=self.run_generation).pack(pady=30)
        
        self.key_output = ctk.CTkTextbox(self.tab_keys, height=140, fg_color="#050507", 
                                         border_width=1, border_color=BORDER_COLOR, corner_radius=15)
        self.key_output.pack(fill="x", padx=40, pady=10)

    def refresh_users(self):
        for widget in self.users_list_container.winfo_children(): widget.destroy()
        users = logic.db_get_all_users()
        if not users:
            ctk.CTkLabel(self.users_list_container, text="EMPTY NODE LIST", text_color="#4B5563").pack(pady=50)
            return

        for u in users:
            uname, plan, hwid = u.get('username', 'UNK'), u.get('membresia', 'N/A'), u.get('hwid', 'NONE')
            card = ctk.CTkFrame(self.users_list_container, fg_color="#11111E", height=60, corner_radius=15, border_width=1, border_color=BORDER_COLOR)
            card.pack(fill="x", pady=5, padx=5)
            card.pack_propagate(False)

            ctk.CTkLabel(card, text=uname.upper(), font=("Inter", 13, "bold"), width=160, anchor="w").pack(side="left", padx=20)
            st_color = ERROR_RED if hwid != "NONE" else VIOLETA_NEON
            st_text = LANGUAGES[CURRENT_LANG]["locked"] if hwid != "NONE" else LANGUAGES[CURRENT_LANG]["ready"]
            ctk.CTkLabel(card, text="●" if hwid != "NONE" else "○", text_color=st_color, width=20).pack(side="left")
            ctk.CTkLabel(card, text=st_text, font=("Consolas", 10), text_color="#8B8B9E").pack(side="left", padx=5)
            
            p_var = ctk.StringVar(value=plan)
            ctk.CTkOptionMenu(card, values=["Weekly", "Monthly", "Yearly", "Lifetime"], variable=p_var, width=100, height=28, font=("Inter", 10), command=lambda v, n=uname: self.update_user_plan(n, v)).pack(side="left", padx=30)
            ctk.CTkButton(card, text=LANGUAGES[CURRENT_LANG]["purge"], fg_color="#2D0A0A", hover_color=ERROR_RED, text_color="#FF8080", width=70, height=30, corner_radius=10, font=("Inter", 10, "bold"), command=lambda n=uname: self.delete_user_confirm(n)).pack(side="right", padx=20)

    def update_user_plan(self, username, new_plan):
        success, msg = logic.db_update_membership(username, new_plan)
        if success: self.refresh_users()
        else: CyberAlert(self, title="ERROR", message=msg, is_error=True)

    def delete_user_confirm(self, username):
        confirm_msg = "¿Eliminar permanentemente?" if CURRENT_LANG == "ES" else "Permanently delete?"
        if messagebox.askyesno(LANGUAGES[CURRENT_LANG]["purge"], f"{confirm_msg} {username}"):
            success, msg = logic.db_delete_user(username)
            if success: self.refresh_users()
            else: CyberAlert(self, title="ERROR", message=msg, is_error=True)

    def handle_hwid_reset(self):
        prompt = "Usuario a desbloquear:" if CURRENT_LANG == "ES" else "Username to unlock:"
        d = ctk.CTkInputDialog(text=prompt, title="HWID Bypass")
        target = d.get_input()
        if target:
            success, msg = logic.db_reset_hwid(target.strip())
            if success: self.refresh_users()
            else: CyberAlert(self, title="ERROR", message=msg, is_error=True)

    def run_generation(self):
        success, keys = logic.db_generate_key(self.memb_var.get(), int(self.amount_var.get()))
        if success:
            self.key_output.delete("0.0", "end")
            for k in keys: self.key_output.insert("end", f"{k}\n")

# ==========================================================
# CLASE: BYPASS
# ==========================================================
# ==========================================================
# CLASE: BYPASS (Actualizada con Filtro de Archivos)
# ==========================================================
# ==========================================================
# CLASE: BYPASS (GHOST PROTOCOL 2026 - FINAL VERSION)
# ==========================================================
class BypassFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Panel principal
        self.panel = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=30, border_width=2, border_color=BORDER_COLOR)
        self.panel.pack(padx=60, pady=60, fill="both", expand=True)

        # Botón de desconexión
        ctk.CTkButton(self.panel, text="← DISCONNECT", fg_color="transparent", text_color="#8B8B9E", 
                      command=lambda: controller.show_frame(InicioFrame)).pack(anchor="nw", padx=30, pady=30)
        
        # Selección de Objetivo
        self.btn_sel = ctk.CTkButton(self.panel, text=LANGUAGES[CURRENT_LANG]["target"], fg_color="#14141F", 
                                     border_width=1, border_color=VIOLETA_NEON, height=45, corner_radius=12, 
                                     command=self.handle_select)
        self.btn_sel.pack(pady=5)
        
        # Consola de logs
        self.txt_console = ctk.CTkTextbox(self.panel, height=250, fg_color="#050507", text_color=VIOLETA_NEON, 
                                          font=("Consolas", 12), border_width=1, border_color=BORDER_COLOR, corner_radius=20)
        self.txt_console.pack(fill="x", padx=60, pady=15)

        # Barra de progreso
        self.progress = ctk.CTkProgressBar(self.panel, progress_color=VIOLETA_NEON, width=550, height=10)
        self.progress.set(0)
        self.progress.pack(pady=10)

        # --- KERNEL STATUS + SCANNER INTERCEPT ---
        status_row = ctk.CTkFrame(self.panel, fg_color="transparent")
        status_row.pack(fill="x", padx=60, pady=(0, 4))

        # Indicador de estado del driver kernel
        self.lbl_kernel_status = ctk.CTkLabel(
            status_row,
            text="◌ KERNEL: USER-MODE",
            font=("Consolas", 11, "bold"),
            text_color="#555577"
        )
        self.lbl_kernel_status.pack(side="left", padx=(0, 20))

        # Scanner intercept toggle
        self._intercept_var = ctk.BooleanVar(value=False)
        self.chk_intercept = ctk.CTkCheckBox(
            status_row,
            text="🛡 SCANNER INTERCEPT",
            variable=self._intercept_var,
            font=("Inter", 11, "bold"),
            text_color="#8B5CF6",
            fg_color="#8B5CF6",
            hover_color="#6D28D9",
            border_color="#4C1D95",
            command=self._toggle_scanner_intercept
        )
        self.chk_intercept.pack(side="left")

        # Alerta de scanner detectado (oculta por defecto)
        self.lbl_scanner_alert = ctk.CTkLabel(
            self.panel,
            text="",
            font=("Consolas", 12, "bold"),
            text_color="#FF4B4B"
        )
        self.lbl_scanner_alert.pack(pady=(0, 4))
        self._alert_blink_job = None

        # Botón de ejecución principal (WIPE)
        self.btn_exe = ctk.CTkButton(self.panel, text=LANGUAGES[CURRENT_LANG]["execute"], fg_color=VIOLETA_NEON, 
                                     font=("Inter", 20, "bold"), height=65, width=400, corner_radius=20, 
                                     command=self.handle_wipe)
        self.btn_exe.pack(pady=10)

        # Botón de Autodestrucción
        self.btn_self_destruct = ctk.CTkButton(
            self.panel, text="☢ SELF-DESTRUCT PROTOCOL", fg_color="transparent", border_width=2,
            border_color=ERROR_RED, text_color=ERROR_RED, font=("Inter", 12, "bold"),
            hover_color="#300a0a", height=40, width=200, corner_radius=12, command=self.handle_self_destruct
        )
        self.btn_self_destruct.pack(pady=(5, 5))

        # Botón NUCLEAR WIPE — limpieza pesada: cipher /w + SRUM + VSS
        self.btn_nuclear = ctk.CTkButton(
            self.panel, text="☣ NUCLEAR WIPE (SLOW — FULL DISK SANITIZE)",
            fg_color="transparent", border_width=2,
            border_color="#FF8C00", text_color="#FF8C00", font=("Inter", 11, "bold"),
            hover_color="#2D1400", height=38, width=360, corner_radius=12,
            command=self.handle_nuclear_wipe
        )
        self.btn_nuclear.pack(pady=(0, 10))

    def log(self, message):
        self.txt_console.insert("end", f"[>] {message}\n")
        self.txt_console.see("end")
        self.update()

    def handle_select(self):
        path = filedialog.askopenfilename(
            title="Select Target",
            filetypes=[("Executable Files", "*.exe"), ("Dynamic Link Libraries", "*.dll")]
        )
        if path:
            self.controller.ruta_seleccionada = os.path.normpath(path)
            self.log(f"Target Acquired: {os.path.basename(path)}")

    def handle_wipe(self):
        """Pipeline de invisibilidad total (GHOST PROTOCOL 2026 ULTRA KERNEL)."""
        if not self.controller.ruta_seleccionada:
            CyberAlert(self, title="SYSTEM", message="Select target first.", is_error=True)
            return
        
        target = self.controller.ruta_seleccionada
        self.btn_exe.configure(state="disabled")
        self.txt_console.delete("0.0", "end")
        self.log("INITIATING ULTRA-GOD-TIER ANTI-SS PROTOCOL...")

        # --- Inicializar driver kernel (intento, fallback graceful) ---
        self.log("⚡ Attempting Ring-0 initialization...")
        kernel_armed = logic.inicializar_kernel_driver(self.log)
        self._update_kernel_status(kernel_armed)

# --- CONSTRUCCIÓN DINÁMICA DE FASES ---
        fases = []

        # CORRECCIÓN 1: Usar 'logic.DEEP_SCAN_ENABLED' para evitar crash
        if logic.DEEP_SCAN_ENABLED:
            fases.append((0.03, "DEEP SCAN: Searching all Registry Hives (Slow Mode)",
                         lambda: logic.deep_registry_search_cleaner(target, self.log)))

        # --- GHOST PROTOCOL 2026 ULTRA — 10 FASES + KERNEL ---
        fases.extend([
            # FASE 0 — PRE-LIMPIEZA DESTRUCTIVA: Cerrar todas las puertas de recuperación
            (0.08, "Phase 0: Killing Shadow Copies & Recovery Vectors", lambda: (
                logic.eliminar_shadow_copies(self.log),
                logic.limpiar_hiberfil(self.log),
                logic.configurar_pagefile_limpieza(self.log)
            )),

            # FASE 0.5 [KERNEL] — Operaciones Ring-0 (si WinPmem está armado)
            (0.14, "Phase 0.5 [KERNEL]: $LogFile Zero + MFT Entry + Cluster Overwrite + RAM Scrub", lambda: (
                logic.limpiar_logfile_ntfs_kernel(self.log),
                logic.overwrite_clusters_kernel(target, self.log),
                logic.limpiar_mft_entry_kernel(target, self.log),
                logic.scrub_ram_kernel(target, self.log)
            )),

            # FASE 1 — ORIGEN: Eliminar evidencia web antes de tocar nada más
            (0.20, "Phase 1: Sanitizing Web Origin, Downloads & Browser Artifacts", lambda: (
                logic.limpiar_rastros_globales_nombre(target, self.log),
                logic.limpiar_historial_descarga_internet(target, self.log)
            )),


            # FASE 2 — TELEMETRÍA Y ACTIVIDAD DE USUARIO
            (0.25, "Phase 2: Purging Telemetry, UserAssist, DAM & Timeline", lambda: (
                logic.limpiar_shell_experience(self.log),
                logic.limpiar_userassist_selectivo(target, self.log),
                logic.limpiar_recent_apps_selectivo(target, self.log),
                logic.limpiar_dam_registry(target, self.log),
                logic.limpiar_timeline_activity(self.log)
            )),

            # FASE 3 — INTERFAZ, RED Y ARTEFACTOS VISUALES
            (0.38, "Phase 3: Clearing Clipboard, LNKs, Thumbnails & Network Stack", lambda: (
                logic.limpiar_clipboard(self.log),
                logic.limpiar_lnk_recientes(target, self.log),
                logic.limpiar_jump_lists_especificas(self.log),
                logic.flush_dns_y_arp(self.log),
                logic.limpiar_thumbnail_cache(self.log)
            )),

            # FASE 4 — REGISTRO QUIRÚRGICO
            (0.50, "Phase 4: Surgical AppCompat, Amcache Registry & MuiCache", lambda: (
                logic.limpiar_appcompat_total(target, self.log),
                logic.limpiar_amcache_quirurgico(target, self.log),
                logic.limpiar_muicache_admin(target, self.log),
                logic.limpiar_task_cache(target, self.log)
            )),

            # FASE 5 — AMCACHE.HVE REAL + CRASH REPORTS + SEARCH INDEX
            (0.62, "Phase 5: Amcache.hve Real Hive, WER Reports & Search Index", lambda: (
                logic.limpiar_amcache_hive_real(target, self.log),
                logic.limpiar_wer_reports(target, self.log),
                logic.limpiar_search_index(self.log)
            )),

            # FASE 6 — SRUM + ETW (TELEMETRÍA A NIVEL KERNEL)
            (0.72, "Phase 6: SRUM Database & ETW Kernel Trace Logs", lambda: (
                logic.limpiar_srum(self.log),
                logic.limpiar_etw_traces(self.log)
            )),

            # FASE 7 — OFUSCACIÓN DE MFT Y TIEMPO
            (0.82, "Phase 7: TimeStomp & MFT Camouflage", lambda: (
                logic.limpiar_ads_archivo(target, self.log),
                logic.time_stomp_archivo(target, self.log),
                logic.camuflar_mft(os.path.dirname(target), self.log)
            )),

            # FASE 8 — DESTRUCCIÓN FÍSICA (DoD 3-pass)
            (0.91, "Phase 8: DoD 3-Pass Cryptographic Shredding", lambda: (
                time.sleep(0.8),
                logic.shred_y_destruir(target, self.log),
                logic.limpiar_icon_cache(self.log)
            )),

            # FASE 9 — LIMPIEZA FINAL: borrar rastros de la propia limpieza
            (1.00, "Phase 9: Final Wipe — Journal, Events, Prefetch & Console", lambda: (
                logic.deep_wipe_usn_journal(self.log),
                logic.limpiar_event_logs_creacion(self.log),
                logic.limpiar_everything_service(self.log),
                time.sleep(0.5),
                logic.limpiar_historial_consola(self.log)
            ))
        ])

        # --- EJECUCIÓN SECUENCIAL ---
        for p, d, f in fases:
            self.log(f"Phase: {d}")
            try:
                f()
            except Exception as e:
                self.log(f"Warning: {e}")
            self.progress.set(p)
            self.update()
            # Ajuste de tiempo para que el usuario pueda leer el progreso
            time.sleep(0.4 if not logic.DEEP_SCAN_ENABLED else 0.2)

        # --- Descargar driver kernel y limpiar sus rastros ---
        logic.terminar_kernel_driver(self.log)
        self._update_kernel_status(False)

        self.controller.ruta_seleccionada = ""
        CyberAlert(self, title="ULTRA GHOST", message="System sanitized for SS. Target annihilated.")
        self.btn_exe.configure(state="normal")
        self.progress.set(0)

    def _update_kernel_status(self, armed: bool):
        """Actualiza el indicador de estado del driver en la UI."""
        try:
            if armed:
                self.lbl_kernel_status.configure(
                    text="⚡ KERNEL: ARMED",
                    text_color="#00FF88"
                )
            else:
                self.lbl_kernel_status.configure(
                    text="◌ KERNEL: USER-MODE",
                    text_color="#555577"
                )
        except Exception:
            pass

    def _toggle_scanner_intercept(self):
        """Activa/desactiva el sistema de interceptación de scanners."""
        if self._intercept_var.get():
            # Activar
            logic.activar_scanner_intercept(
                logger=self.log,
                on_detect_cb=self._on_scanner_detected,
                on_clear_cb=self._on_scanner_cleared
            )
            self.chk_intercept.configure(text_color="#00FF88")
            self.log("🛡 Scanner Intercept ARMED — Monitoring for Ocean/Echo/EAC/BE/Vanguard...")
        else:
            # Desactivar
            logic.desactivar_scanner_intercept(self.log)
            self._stop_blink()
            self.lbl_scanner_alert.configure(text="")
            self.chk_intercept.configure(text_color="#8B5CF6")
            self.log("◌ Scanner Intercept disabled.")

    def _on_scanner_detected(self, scanner_name: str, proc_name: str, pid: int):
        """Callback de la GUI cuando se detecta un scanner."""
        self.lbl_scanner_alert.configure(
            text=f"⚠ {scanner_name.upper()} DETECTED (PID {pid}) — INTERCEPTING ⚠"
        )
        self._start_blink()

    def _on_scanner_cleared(self):
        """Callback cuando el scanner termina."""
        self._stop_blink()
        self.lbl_scanner_alert.configure(text="✓ Scanner gone — Spoofing removed")
        self.after(3000, lambda: self.lbl_scanner_alert.configure(text=""))

    def _start_blink(self):
        """Inicia la animación de parpadeo rojo en la alerta."""
        self._stop_blink()
        self._blink_state = True
        self._do_blink()

    def _stop_blink(self):
        if self._alert_blink_job:
            try:
                self.after_cancel(self._alert_blink_job)
            except Exception:
                pass
            self._alert_blink_job = None

    def _do_blink(self):
        try:
            if self._blink_state:
                self.lbl_scanner_alert.configure(text_color="#FF4B4B")
            else:
                self.lbl_scanner_alert.configure(text_color="#330000")
            self._blink_state = not self._blink_state
            self._alert_blink_job = self.after(500, self._do_blink)
        except Exception:
            pass

    def handle_nuclear_wipe(self):
        """
        NUCLEAR WIPE — Limpieza total del disco sin archivo objetivo.
        Borra VSS, SRUM, Search Index, ETW, Timeline, Thumbnail Cache
        y sobreescribe el espacio libre completo (cipher /w).
        Operación lenta (varios minutos). No requiere selección de archivo.
        """
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "☣ NUCLEAR WIPE",
            "This will:\n"
            "• Delete ALL Shadow Copies (VSS)\n"
            "• Shred SRUM database\n"
            "• Destroy Windows Search Index\n"
            "• Wipe ETW kernel trace logs\n"
            "• Clear Windows Timeline & Thumbnail cache\n"
            "• Overwrite all free disk space (cipher /w)\n\n"
            "⚠ This may take 10-30 minutes.\n"
            "Proceed?"
        )
        if not confirm:
            return

        self.btn_nuclear.configure(state="disabled")
        self.btn_exe.configure(state="disabled")
        self.txt_console.delete("0.0", "end")
        self.log("☣ INITIATING NUCLEAR WIPE PROTOCOL...")

        fases_nuclear = [
            (0.10, "Nuclear Phase 1: Annihilating Shadow Copies (VSS)",
             lambda: logic.eliminar_shadow_copies(self.log)),
            (0.25, "Nuclear Phase 2: Shredding SRUM Telemetry Database",
             lambda: logic.limpiar_srum(self.log)),
            (0.40, "Nuclear Phase 3: Destroying Windows Search Index",
             lambda: logic.limpiar_search_index(self.log)),
            (0.55, "Nuclear Phase 4: Wiping ETW Kernel Trace Logs",
             lambda: logic.limpiar_etw_traces(self.log)),
            (0.65, "Nuclear Phase 5: Clearing Timeline & Thumbnail Cache",
             lambda: (
                 logic.limpiar_timeline_activity(self.log),
                 logic.limpiar_thumbnail_cache(self.log)
             )),
            (0.75, "Nuclear Phase 6: Purging hiberfil & PageFile Config",
             lambda: (
                 logic.limpiar_hiberfil(self.log),
                 logic.configurar_pagefile_limpieza(self.log)
             )),
            (0.85, "Nuclear Phase 7: Final Event Log & Journal Wipe",
             lambda: (
                 logic.limpiar_event_logs_creacion(self.log),
                 logic.deep_wipe_usn_journal(self.log),
                 logic.limpiar_historial_consola(self.log)
             )),
            (1.00, "Nuclear Phase 8: Anti-Carving — Overwriting Free Disk Space (cipher /w)...",
             lambda: logic.limpiar_espacio_libre(self.log)),
        ]

        for p, desc, fn in fases_nuclear:
            self.log(f"Phase: {desc}")
            try:
                fn()
            except Exception as e:
                self.log(f"Warning: {e}")
            self.progress.set(p)
            self.update()
            time.sleep(0.3)

        CyberAlert(self, title="NUCLEAR WIPE", message="Full disk sanitization complete.\nCarving recovery: IMPOSSIBLE.")
        self.btn_nuclear.configure(state="normal")
        self.btn_exe.configure(state="normal")
        self.progress.set(0)

    def handle_self_destruct(self):
        """Secuencia final de suicidio del binario."""
        if not messagebox.askyesno("GHOST PROTOCOL", "Confirm total nuclear purge of Scanneler?"):
            return

        self.log("INITIATING SELF-PURGE PROTOCOL...")
        yo_mismo = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]

        try:
            # Borrarnos a nosotros mismos de los chivatos antes de morir
            logic.limpiar_registro_selectivo(yo_mismo, self.log)
            logic.limpiar_userassist_selectivo(yo_mismo, self.log)
            logic.limpiar_shimcache_quirurgico(yo_mismo, self.log)
            logic.limpiar_amcache_quirurgico(yo_mismo, self.log)
            logic.limpiar_historial_consola(self.log)
            logic.deep_wipe_usn_journal(self.log)
        except: pass

        self.log("TRACES PURGED. EXECUTING BINARY SUICIDE...")
        self.update()
        time.sleep(1.5)

        if logic.ejecutar_autodestruccion_exe(self.log):
            self.controller.destroy()
            sys.exit()

if __name__ == "__main__":
    solicitar_admin()
    app = ScannelerBypass()
    
    def animate_flicker():
        if hasattr(app.frames[InicioFrame], 'lbl_bypass'):
            app.frames[InicioFrame].lbl_bypass.configure(text_color=random.choice(["#FFFFFF", VIOLETA_NEON, "#A78BFA"]))
        app.after(200, animate_flicker)
    
    animate_flicker()
    app.mainloop()