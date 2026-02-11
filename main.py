import pygame
import pyautogui
import sys
import ctypes
import tkinter as tk
from tkinter import ttk
import json
import os
import time
import threading
import winreg

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit()

appdata_path = os.getenv('APPDATA')
app_folder = os.path.join(appdata_path, "GamePadtoMouse")
if not os.path.exists(app_folder):
    os.makedirs(app_folder)
config_file = os.path.join(app_folder, "config.json")

ACTIONS = [
    "Left Click", "Right Click", "Middle Click",
    "Hold Click (Drag)", "Scroll Up", "Scroll Down",
    "Windows Key", "Enter Key", "Tab Key", "Close App"
]

app_data = {
    "mapping": {},
    "speed": 15,
    "scroll_speed": 10,
    "drag_active": False,
    "assigning_mode": False,
    "pending_action": None,
    "cooldown": 0,
    "autostart": False
}

def fast_move(x, y):
    ctypes.windll.user32.mouse_event(0x0001, int(x), int(y), 0, 0)
def click_down(): ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
def click_up(): ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)

def load_config():
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                app_data.update(data)
        except: pass

def save_config():
    try:
        with open(config_file, 'w') as f:
            json.dump({k: app_data[k] for k in ["mapping", "speed", "scroll_speed", "autostart"]}, f, indent=4)
    except: pass

def toggle_autostart(status):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "GamePadToMouse"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if status:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, sys.executable)
        else:
            try: winreg.DeleteValue(key, app_name)
            except: pass
        winreg.CloseKey(key)
        app_data["autostart"] = status
        save_config()
    except: pass

class GamePadApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GamePad to Mouse")
        self.geometry("850x650")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        load_config()
        pygame.init()
        pygame.joystick.init()
        self.joysticks = []
        self.refresh_joysticks()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(self, bg="#2c3e50", width=220)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="GAMEPAD\nMOUSE", bg="#2c3e50", fg="white", font=("Segoe UI", 16, "bold"), pady=30).pack(fill="x")
        self.create_menu_btn("📊 Status Monitor", lambda: self.show_page("Status"))
        self.create_menu_btn("🎮 Button Mapping", lambda: self.show_page("Mapping"))
        self.create_menu_btn("⚙️ Settings", lambda: self.show_page("Settings"))

        self.main_area = tk.Frame(self, bg="#ecf0f1")
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.columnconfigure(0, weight=1)
        self.main_area.rowconfigure(0, weight=1)

        self.frames = {}
        self.frames["Status"] = self.page_status(self.main_area)
        self.frames["Mapping"] = self.page_mapping(self.main_area)
        self.frames["Settings"] = self.page_settings(self.main_area)

        self.show_page("Status")
        self.setup_tray()
        self.game_loop()

    def refresh_joysticks(self):
        pygame.joystick.quit()
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        for j in self.joysticks: j.init()

    def create_menu_btn(self, txt, cmd):
        tk.Button(self.sidebar, text=txt, command=cmd, bg="#34495e", fg="white", bd=0, font=("Segoe UI", 11), anchor="w", padx=20, pady=15).pack(fill="x", pady=2)

    def show_page(self, name): self.frames[name].tkraise()

    def page_status(self, parent):
        f = tk.Frame(parent, bg="#ecf0f1")
        f.grid(row=0, column=0, sticky="nsew")
        tk.Label(f, text="Status Monitor", font=("Segoe UI", 24, "bold"), bg="#ecf0f1").pack(pady=30)
        self.lbl_conn = tk.Label(f, text="Detecting...", font=("Segoe UI", 14), bg="#bdc3c7", width=40, pady=10)
        self.lbl_conn.pack(pady=10)
        box = tk.Frame(f, bg="white", bd=2, relief="solid", padx=20, pady=20)
        box.pack(pady=30, fill="x", padx=50)
        self.lbl_mon_btn = tk.Label(box, text="-", font=("Segoe UI", 22, "bold"), bg="white", fg="orange")
        self.lbl_mon_btn.pack()
        self.lbl_mon_act = tk.Label(box, text="-", font=("Segoe UI", 16), bg="white", fg="blue")
        self.lbl_mon_act.pack()
        return f

    def page_mapping(self, parent):
        f = tk.Frame(parent, bg="#ecf0f1")
        f.grid(row=0, column=0, sticky="nsew")
        tk.Label(f, text="Mapping", font=("Segoe UI", 20, "bold"), bg="#ecf0f1").pack(pady=20)
        canvas = tk.Canvas(f, bg="white")
        scroll = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg="white")
        self.list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)
        self.ui_buttons = []
        for acc in ACTIONS:
            r = tk.Frame(self.list_frame, bg="white", pady=5)
            r.pack(fill="x")
            tk.Label(r, text=acc, width=25, anchor="w", font=("Segoe UI", 10, "bold"), bg="white").pack(side="left")
            btn = tk.Button(r, text="ASSIGN", bg="#2c3e50", fg="white", command=lambda a=acc: self.start_assignment(a))
            btn.pack(side="right")
            lbl = tk.Label(r, text="---", fg="gray", bg="white", width=25)
            lbl.pack(side="right", padx=10)
            self.ui_buttons.append({"action": acc, "btn": btn, "lbl": lbl})
        self.update_mapping_ui()
        return f

    def page_settings(self, parent):
        f = tk.Frame(parent, bg="#ecf0f1")
        f.grid(row=0, column=0, sticky="nsew")
        tk.Label(f, text="Settings", font=("Segoe UI", 20, "bold"), bg="#ecf0f1").pack(pady=30)
        s1 = tk.Scale(f, from_=5, to=100, label="Mouse Speed", orient="horizontal", length=300, command=lambda v: self.upd("speed", v))
        s1.set(app_data["speed"]); s1.pack()
        s2 = tk.Scale(f, from_=1, to=50, label="Continuous Scroll Speed", orient="horizontal", length=300, command=lambda v: self.upd("scroll_speed", v))
        s2.set(app_data["scroll_speed"]); s2.pack()
        self.auto_var = tk.BooleanVar(value=app_data["autostart"])
        tk.Checkbutton(f, text="Start with Windows", variable=self.auto_var, command=lambda: toggle_autostart(self.auto_var.get()), bg="#ecf0f1", font=("Segoe UI", 11)).pack(pady=20)
        return f

    def upd(self, key, v): app_data[key] = int(v); save_config()

    def start_assignment(self, acc):
        app_data["assigning_mode"] = True
        app_data["pending_action"] = acc
        for b in self.ui_buttons:
            if b["action"] == acc: b["btn"].config(text="PRESS BUTTON...", bg="orange")
            else: b["btn"].config(state="disabled")

    def update_mapping_ui(self):
        inv_map = {v: k for k, v in app_data["mapping"].items()}
        for b in self.ui_buttons:
            b["btn"].config(text="ASSIGN", bg="#2c3e50", state="normal")
            aid = inv_map.get(b["action"])
            b["lbl"].config(text=str(aid) if aid else "Unassigned", fg="green" if aid else "gray")

    def game_loop(self):
        if pygame.joystick.get_count() != len(self.joysticks): self.refresh_joysticks()
        if not self.joysticks:
            self.lbl_conn.config(text="No Controller Found", bg="#e74c3c")
            self.after(1000, self.game_loop); return
        self.lbl_conn.config(text=f"{len(self.joysticks)} Controller(s) Active", bg="#2ecc71")

        if app_data["cooldown"] > 0: app_data["cooldown"] -= 1
        
        pygame.event.pump()
        events = pygame.event.get()
        for event in events:
            iid = None
            if event.type == pygame.JOYBUTTONDOWN: iid = f"ID{event.joy}_BTN{event.button}"
            elif event.type == pygame.JOYHATMOTION and event.value != (0,0): iid = f"ID{event.joy}_HAT{event.value}"
            
            if iid:
                self.lbl_mon_btn.config(text=iid)
                if app_data["assigning_mode"]:
                    app_data["mapping"] = {k: v for k, v in app_data["mapping"].items() if v != app_data["pending_action"]}
                    app_data["mapping"][iid] = app_data["pending_action"]; save_config()
                    app_data["assigning_mode"] = False; self.update_mapping_ui(); app_data["cooldown"] = 50
                else:
                    acc = app_data["mapping"].get(iid)
                    if acc and "Scroll" not in acc: self.lbl_mon_act.config(text=acc); self.exec_acc(acc)

        for j in self.joysticks:
            rx, ry = j.get_axis(0), j.get_axis(1)
            if abs(rx) > 0.1 or abs(ry) > 0.1: fast_move(rx * app_data["speed"], ry * app_data["speed"])
            
            for iid_key, acc_val in app_data["mapping"].items():
                if f"ID{j.get_id()}_BTN" in iid_key:
                    btn_num = int(iid_key.split("BTN")[1])
                    if j.get_button(btn_num):
                        if acc_val == "Scroll Up": pyautogui.scroll(app_data["scroll_speed"])
                        elif acc_val == "Scroll Down": pyautogui.scroll(-app_data["scroll_speed"])

        self.after(8, self.game_loop)

    def exec_acc(self, acc):
        if acc == "Left Click": click_down(); click_up()
        elif acc == "Right Click": pyautogui.rightClick()
        elif acc == "Middle Click": pyautogui.middleClick()
        elif acc == "Hold Click (Drag)":
            if not app_data["drag_active"]: click_down(); app_data["drag_active"] = True
            else: click_up(); app_data["drag_active"] = False
        elif acc == "Windows Key": pyautogui.press('win')
        elif acc == "Enter Key": pyautogui.press('enter')
        elif acc == "Tab Key": pyautogui.press('tab')
        elif acc == "Close App": self.quit_app()
        app_data["cooldown"] = 15

    def setup_tray(self):
        try:
            img = Image.open(sys.executable)
        except:
            img = Image.new('RGB', (64, 64), (44, 62, 80))
            d = ImageDraw.Draw(img); d.rectangle([16, 16, 48, 48], fill="white")
        self.tray = pystray.Icon("GP2M", img, "GamePad to Mouse", pystray.Menu(pystray.MenuItem("Show", self.show_win), pystray.MenuItem("Exit", self.quit_app)))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def show_win(self, icon=None, item=None): self.after(0, self.deiconify)
    def minimize_to_tray(self): self.withdraw()
    def quit_app(self, icon=None, item=None):
        if hasattr(self, 'tray'): self.tray.stop()
        click_up(); self.destroy(); sys.exit()

if __name__ == "__main__": GamePadApp().mainloop()