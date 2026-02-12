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

# --- VERIFICACIÓN DE LOGIC ---
try:
    import logic
except Exception as e:
    root = ctk.CTk()
    root.withdraw()
    messagebox.showerror("Logic Error", f"Fatal error in logic.py: {e}")
    sys.exit()

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

# Colores Core 2026
BG_DARK = "#050507"
VIOLETA_NEON = "#8B5CF6"
MAGENTA_GLOW = "#D946EF"
GRID_COLOR = "#1A1033"
ERROR_RED = "#FF4B4B"

class ScannelerBypass(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Scanneler Bypass // God Tier Core")
        self.geometry("1000x800")
        self.configure(fg_color=BG_DARK)
        self.ruta_seleccionada = ""
        
        # --- CAPA BASE: EL CANVAS ---
        self.bg_canvas = Canvas(self, bg=BG_DARK, highlightthickness=0, bd=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_canvas.tag_lower("all") 
        
        self.draw_cyber_grid()
        self.glow_obj = self.draw_central_glow()
        
        # --- CONTENEDOR PRINCIPAL DE NAVEGACIÓN ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Diccionario para gestionar los paneles (Frames)
        self.frames = {}
        
        for F in (LoginFrame, InicioFrame, BypassFrame, AdminFrame):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        # --- PANTALLA DE SPLASH (CON LOGO RESTAURADO) ---
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
        # CARGA DE LOGO RESTAURADA
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
# CLASE: LOGIN (CON REDEEM KEY RESTAURADO)
# ==========================================================
class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.login_content = ctk.CTkFrame(self, width=420, height=580, fg_color="#0D0D12", corner_radius=25, border_width=1, border_color="#1F1F23")
        self.login_content.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self.login_content, text="SCANNELER AUTH", font=("Inter", 28, "bold"), text_color=VIOLETA_NEON).pack(pady=(40, 5))
        ctk.CTkLabel(self.login_content, text="BYPASS EDITION // RENDER API", font=("Inter", 10), text_color="#4B5563").pack()

        self.entry_user = ctk.CTkEntry(self.login_content, width=320, height=45, placeholder_text="USERNAME", justify="center") 
        self.entry_user.pack(pady=(40, 10))

        self.entry_pass = ctk.CTkEntry(self.login_content, width=320, height=45, placeholder_text="PASSWORD", show="*", justify="center") 
        self.entry_pass.pack(pady=10)

        self.lbl_status = ctk.CTkLabel(self.login_content, text="IDLE", font=("Consolas", 11), text_color="gray")
        self.lbl_status.pack(pady=5)

        ctk.CTkButton(self.login_content, text="LOGIN SYSTEM", font=("Inter", 14, "bold"), fg_color=VIOLETA_NEON, hover_color=MAGENTA_GLOW, height=45, width=320, command=self.handle_auth).pack(pady=(20, 10))

        # BOTÓN REDEEM RESTAURADO
        ctk.CTkButton(self.login_content, text="REDEEM & BIND HWID", font=("Inter", 12), fg_color="transparent", text_color="gray", border_width=1, border_color="#1F1F23", height=35, width=320, command=self.open_redeem_window).pack(pady=5)

    def handle_auth(self):
        u, p = self.entry_user.get(), self.entry_pass.get()
        if not u or not p: return

        self.lbl_status.configure(text="AUTHENTICATING...", text_color=VIOLETA_NEON)
        self.update()
        
        result = logic.db_validate_login(u, p)
        if isinstance(result, (list, tuple)) and result[0]:
            role = str(result[2]).lower()
            # Compatible con admin y super_admin
            if "admin" in role:
                self.controller.frames[InicioFrame].btn_admin.pack(pady=10)
            self.controller.show_frame(InicioFrame)
        else:
            msg = str(result[1]) if isinstance(result, (list, tuple)) else "ERROR"
            self.lbl_status.configure(text=msg.upper(), text_color=ERROR_RED)

    def open_redeem_window(self):
        redeem_win = ctk.CTkToplevel(self)
        redeem_win.title("Redeem License")
        redeem_win.geometry("450x600")
        redeem_win.configure(fg_color=BG_DARK)
        redeem_win.attributes("-topmost", True)
        redeem_win.resizable(False, False)

        ctk.CTkLabel(redeem_win, text="REDEEM KEY", font=("Inter", 24, "bold"), text_color=VIOLETA_NEON).pack(pady=(30, 20))
        
        k_val = ctk.CTkEntry(redeem_win, width=320, height=40, placeholder_text="LICENSE KEY", justify="center")
        k_val.pack(pady=10)
        u_val = ctk.CTkEntry(redeem_win, width=320, height=40, placeholder_text="NEW USERNAME", justify="center")
        u_val.pack(pady=10)
        p_val = ctk.CTkEntry(redeem_win, width=320, height=40, placeholder_text="PASSWORD", show="*", justify="center")
        p_val.pack(pady=10)
        cp_val = ctk.CTkEntry(redeem_win, width=320, height=40, placeholder_text="CONFIRM PASSWORD", show="*", justify="center")
        cp_val.pack(pady=10)

        lbl_err = ctk.CTkLabel(redeem_win, text="", font=("Inter", 11), text_color=ERROR_RED)
        lbl_err.pack(pady=5)

        def process():
            if p_val.get() != cp_val.get():
                lbl_err.configure(text="PASSWORDS DO NOT MATCH")
                return
            success, msg = logic.db_redeem_key(u_val.get(), k_val.get(), p_val.get())
            if success:
                messagebox.showinfo("Success", "Account activated!")
                redeem_win.destroy()
            else:
                lbl_err.configure(text=str(msg).upper())

        ctk.CTkButton(redeem_win, text="ACTIVATE LICENSE", font=("Inter", 14, "bold"), fg_color=VIOLETA_NEON, height=45, width=320, command=process).pack(pady=30)

# ==========================================================
# CLASE: INICIO
# ==========================================================
class InicioFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.lbl_title = ctk.CTkLabel(self, text="SCANNELER", font=("Inter", 85, "bold"))
        self.lbl_title.pack(pady=(150, 5))
        ctk.CTkLabel(self, text="B Y P A S S   P R O T O C O L", font=("Inter", 15, "bold"), text_color="#4B5563").pack(pady=(0, 60))
        
        ctk.CTkButton(self, text="INITIALIZE CORE", font=("Inter", 16, "bold"), fg_color=VIOLETA_NEON, hover_color=MAGENTA_GLOW, width=300, height=60, command=lambda: controller.show_frame(BypassFrame)).pack(pady=20)
        
        self.btn_admin = ctk.CTkButton(self, text="🛡️ ADMIN PANEL", font=("Inter", 14, "bold"), fg_color="#1F1F23", border_width=1, border_color=MAGENTA_GLOW, width=300, height=45, command=lambda: controller.show_frame(AdminFrame))

# ==========================================================
# CLASE: ADMIN (CON RESET HWID Y MEMBRESÍAS)
# ==========================================================
class AdminFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.admin_box = ctk.CTkFrame(self, fg_color="#0D0D12", corner_radius=25, border_width=1, border_color="#1F1F23")
        self.admin_box.pack(padx=40, pady=40, fill="both", expand=True)

        header = ctk.CTkFrame(self.admin_box, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        ctk.CTkButton(header, text="← BACK", width=80, fg_color="transparent", text_color="gray", command=lambda: controller.show_frame(InicioFrame)).pack(side="left")
        ctk.CTkLabel(header, text="MASTER CONTROL PANEL", font=("Inter", 24, "bold"), text_color=MAGENTA_GLOW).pack(side="left", padx=20)

        self.tabs = ctk.CTkTabview(self.admin_box, segmented_button_selected_color=VIOLETA_NEON, fg_color="#050507")
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.tab_users = self.tabs.add("👤 USUARIOS")
        self.tab_keys = self.tabs.add("🔑 LICENCIAS")

        # --- TAB: USUARIOS ---
        self.user_box = ctk.CTkTextbox(self.tab_users, font=("Consolas", 12), text_color="#A78BFA", fg_color="#0D0D12")
        self.user_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        btn_frame = ctk.CTkFrame(self.tab_users, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        
        ctk.CTkButton(btn_frame, text="REFRESCAR LISTA", fg_color=VIOLETA_NEON, command=self.refresh_users).pack(side="left", padx=10, expand=True)
        ctk.CTkButton(btn_frame, text="RESET HWID", fg_color="#EF4444", hover_color="#B91C1C", command=self.handle_hwid_reset).pack(side="left", padx=10, expand=True)

        # --- TAB: KEYS ---
        self.config_frame = ctk.CTkFrame(self.tab_keys, fg_color="transparent")
        self.config_frame.pack(expand=True, fill="both", padx=50)

        ctk.CTkLabel(self.config_frame, text="DURACIÓN", font=("Inter", 13, "bold"), text_color=VIOLETA_NEON).pack(pady=(20, 5))
        self.memb_var = ctk.StringVar(value="Monthly")
        self.memb_menu = ctk.CTkOptionMenu(self.config_frame, values=["Weekly", "Monthly", "Yearly", "Lifetime"], 
                                           variable=self.memb_var, fg_color="#1F1F23", button_color=VIOLETA_NEON)
        self.memb_menu.pack(pady=10)

        ctk.CTkLabel(self.config_frame, text="CANTIDAD", font=("Inter", 13, "bold"), text_color=VIOLETA_NEON).pack(pady=(10, 5))
        self.amount_var = ctk.StringVar(value="1")
        self.amount_entry = ctk.CTkEntry(self.config_frame, width=120, justify="center", textvariable=self.amount_var)
        self.amount_entry.pack(pady=10)

        ctk.CTkButton(self.config_frame, text="GENERAR", font=("Inter", 14, "bold"), 
                      fg_color=MAGENTA_GLOW, height=45, width=280, command=self.run_generation).pack(pady=30)
        
        self.key_output = ctk.CTkTextbox(self.tab_keys, height=180, fg_color="#0D0D12", border_width=1, border_color="#1F1F23")
        self.key_output.pack(fill="x", padx=40, pady=10)

    def refresh_users(self):
        self.user_box.delete("0.0", "end")
        users = logic.db_get_all_users()
        if isinstance(users, list):
            for u in users:
                hwid_status = "LOCKED" if u.get('hwid') != 'NONE' else "FREE"
                self.user_box.insert("end", f"▶ USER: {u.get('username')} | PLAN: {u.get('membresia')} | HWID: {hwid_status}\n")
        else:
            self.user_box.insert("end", "Error de conexión.")

    def handle_hwid_reset(self):
        dialog = ctk.CTkInputDialog(text="Username a resetear:", title="HWID Reset")
        target = dialog.get_input()
        if target:
            success, msg = logic.db_reset_hwid(target)
            if success: messagebox.showinfo("Éxito", msg); self.refresh_users()
            else: messagebox.showerror("Error", msg)

    def run_generation(self):
        tipo = self.memb_var.get()
        try:
            cant = int(self.amount_var.get())
        except:
            messagebox.showerror("Error", "Cantidad inválida")
            return

        success, keys = logic.db_generate_key(membresia=tipo, amount=cant)
        if success:
            self.key_output.delete("0.0", "end")
            self.key_output.insert("end", f"--- {tipo.upper()} KEYS ---\n")
            for k in keys: self.key_output.insert("end", f"{k}\n")
            messagebox.showinfo("Admin", f"Generadas {cant} llaves")
        else:
            messagebox.showerror("Error", "API Error")

# ==========================================================
# CLASE: BYPASS
# ==========================================================
class BypassFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.panel = ctk.CTkFrame(self, fg_color="#0D0D12", corner_radius=25, border_width=1, border_color="#1F1F23")
        self.panel.pack(padx=60, pady=60, fill="both", expand=True)

        ctk.CTkButton(self.panel, text="← BACK", fg_color="transparent", command=lambda: controller.show_frame(InicioFrame)).pack(anchor="nw", padx=20, pady=20)
        
        self.btn_sel = ctk.CTkButton(self.panel, text="TARGET_BIN", fg_color="#1A1A1F", border_width=1, border_color=VIOLETA_NEON, command=self.handle_select)
        self.btn_sel.pack(pady=10)
        
        self.txt_console = ctk.CTkTextbox(self.panel, height=250, fg_color="#050507", text_color=VIOLETA_NEON, font=("Consolas", 12))
        self.txt_console.pack(fill="x", padx=50, pady=20)

        self.progress = ctk.CTkProgressBar(self.panel, progress_color=VIOLETA_NEON, width=500)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.btn_exe = ctk.CTkButton(self.panel, text="EXECUTE BYPASS", fg_color=VIOLETA_NEON, font=("Inter", 18, "bold"), height=55, command=self.handle_wipe)
        self.btn_exe.pack(pady=10)

    def handle_select(self):
        path = filedialog.askopenfilename()
        if path:
            self.controller.ruta_seleccionada = os.path.normpath(path)
            self.txt_console.insert("end", f"[!] Target: {os.path.basename(path)}\n")

    def handle_wipe(self):
        if not self.controller.ruta_seleccionada:
            messagebox.showwarning("System", "Select target.")
            return
        self.btn_exe.configure(state="disabled")
        fases = [(0.25, "Neutralizing Registry", lambda: logic.limpiar_shimcache(print)), (1.0, "Complete", lambda: logic.restore_system_time(print))]
        for p, d, f in fases:
            self.txt_console.insert("end", f"Phase: {d}\n"); f()
            self.progress.set(p); self.update(); time.sleep(0.3)
        self.btn_exe.configure(state="normal")

if __name__ == "__main__":
    solicitar_admin()
    app = ScannelerBypass()
    
    def animate_flicker():
        if hasattr(app.frames[InicioFrame], 'lbl_title'):
            app.frames[InicioFrame].lbl_title.configure(text_color=random.choice([VIOLETA_NEON, "#FFFFFF", MAGENTA_GLOW]))
        app.after(250, animate_flicker)
    
    animate_flicker()
    app.mainloop()