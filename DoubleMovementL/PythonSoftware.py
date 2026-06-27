import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import pydirectinput

# Максимальная скорость опроса ввода
pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0.0

class MartozGamepadApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Martoz Gamepad Настройки")
        self.root.geometry("450x420")
        self.root.resizable(False, False)
        
        # Настройки по умолчанию
        self.deadzone_val = tk.IntVar(value=100) # Размер мертвой зоны от центра (512)
        self.key_up = tk.StringVar(value="w")
        self.key_down = tk.StringVar(value="s")
        self.key_left = tk.StringVar(value="a")
        self.key_right = tk.StringVar(value="d")
        self.key_btn = tk.StringVar(value="e")
        
        # Переменные для работы порта и потока
        self.ser = None
        self.is_running = False
        self.active_keys = {k: False for k in ["w", "s", "a", "d", "e"]}
        
        self.create_widgets()
        self.auto_find_port()

    def create_widgets(self):
        # --- Блок подключения ---
        conn_frame = ttk.LabelFrame(self.root, text=" Подключение ", padding=10)
        conn_frame.pack(fill="x", padx=15, y=10)
        
        ttk.Label(conn_frame, text="COM Порт:").pack(side="left", padx=5)
        self.port_cb = ttk.Combobox(conn_frame, width=15)
        self.port_cb.pack(side="left", padx=5)
        
        self.refresh_btn = ttk.Button(conn_frame, text="🔄", width=3, command=self.auto_find_port)
        self.refresh_btn.pack(side="left", padx=2)
        
        self.start_btn = ttk.Button(conn_frame, text="Старт", command=self.toggle_service)
        self.start_btn.pack(side="right", padx=5)

        # --- Блок настройки чувствительности ---
        sens_frame = ttk.LabelFrame(self.root, text=" Чувствительность джойстика ", padding=10)
        sens_frame.pack(fill="x", padx=15, y=10)
        
        ttk.Label(sens_frame, text="Мертвая зона (люфт центра):").pack(anchor="w")
        self.dz_scale = ttk.Scale(sens_frame, from_=10, to=250, variable=self.deadzone_val, orient="horizontal", command=self.update_dz_label)
        self.dz_scale.pack(fill="x", pady=5)
        
        self.dz_label = ttk.Label(sens_frame, text=f"Текущее значение: {self.deadzone_val.get()} (диапазон покоя: {512-self.deadzone_val.get()} - {512+self.deadzone_val.get()})")
        self.dz_label.pack(anchor="w")

        # --- Блок бинда клавиш ---
        bind_frame = ttk.LabelFrame(self.root, text=" Настройка клавиш (English раскладка) ", padding=10)
        bind_frame.pack(fill="x", padx=15, y=10)
        
        # Сетка для биндов
        keys = [
            ("Вперед (Вверх):", self.key_up),
            ("Назад (Вниз):", self.key_down),#https://github.com/loanelly
            ("Влево:", self.key_left),
            ("Вправо:", self.key_right),
            ("Кнопка (D2):", self.key_btn)
        ]
        
        for i, (label_text, var) in enumerate(keys):
            ttk.Label(bind_frame, text=label_text).grid(row=i, column=0, sticky="w", pady=3, padx=5)
            ttk.Entry(bind_frame, textvariable=var, width=5, justify="center").grid(row=i, column=1, pady=3, padx=5)

        # --- Статус бар ---
        self.status_lbl = ttk.Label(self.root, text="Статус: Остановлен", foreground="red", font=("Arial", 10, "bold"))
        self.status_lbl.pack(pady=10)

    def update_dz_label(self, event=None):#https://github.com/loanelly
        val = self.deadzone_val.get()
        self.dz_label.config(text=f"Текущее значение: {val} (диапазон покоя: {512-val} - {512+val})")

    def auto_find_port(self):
        ports = list(serial.tools.list_ports.comports())#https://github.com/loanelly
        port_names = [p.device for p in ports]
        self.port_cb['values'] = port_names
        
        for p in ports:
            desc = p.description.upper()
            if "CH340" in desc or "USB-SERIAL" in desc or "ARDUINO" in desc:
                self.port_cb.set(p.device)
                return
        if port_names:
            self.port_cb.set(port_names[0])#https://github.com/loanelly

    def toggle_service(self):
        if not self.is_running:
            port = self.port_cb.get()#https://github.com/loanelly
            if not port:
                messagebox.showerror("Ошибка", "Выберите COM-порт!")
                return
            try:
                self.ser = serial.Serial(port, 115200, timeout=0.1)
                time.sleep(1.5) # Даем плате перезагрузиться
                self.is_running = True
                self.start_btn.config(text="Стоп")
                self.status_lbl.config(text="Статус: РАБОТАЕТ (Геймпад активен)", foreground="green")
                self.port_cb.config(state="disabled")
                self.refresh_btn.config(state="disabled")
                
                # Заводим чтение порта в отдельном фоновом потоке, чтобы окно не зависало
                self.thread = threading.Thread(target=self.read_serial_loop, daemon=True)
                self.thread.start()
            except Exception as e:
                messagebox.showerror("Ошибка подключения", f"Не удалось открыть порт {port}.\n{e}")
        else:
            self.stop_service()

    def stop_service(self):
        self.is_running = False
        time.sleep(0.1)
        if self.ser and self.ser.is_open:#https://github.com/loanelly
            self.ser.close()
        self.release_all_keys()#https://github.com/loanelly
        self.start_btn.config(text="Старт")#https://github.com/loanelly
        self.status_lbl.config(text="Статус: Остановлен", foreground="red")#https://github.com/loanelly
        self.port_cb.config(state="normal")
        self.refresh_btn.config(state="normal")

    def update_key_state(self, key_char, should_press):
        # Проверяем, зажата ли уже кнопка, чтобы избежать флуда командами
        if should_press and not self.active_keys.get(key_char, False):
            pydirectinput.keyDown(key_char)
            self.active_keys[key_char] = True
        elif not should_press and self.active_keys.get(key_char, False):#https://github.com/loanelly
            pydirectinput.keyUp(key_char)
            self.active_keys[key_char] = False

    def release_all_keys(self):
        for k in list(self.active_keys.keys()):#https://github.com/loanelly
            if self.active_keys[k]:#https://github.com/loanelly
                pydirectinput.keyUp(k)
                self.active_keys[k] = False

    def read_serial_loop(self):
        while self.is_running:
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    data = line.split(',')
                    
                    if len(data) == 3:
                        x_val = int(data[0])
                        y_val = int(data[1])
                        btn_val = int(data[2])

                        # Считываем актуальные настройки мертвой зоны и биндов из GUI
                        dz = self.deadzone_val.get()
                        low_boundary = 512 - dz
                        high_boundary = 512 + dz
                        
                        k_u = self.key_up.get().lower()
                        k_d = self.key_down.get().lower()
                        k_l = self.key_left.get().lower()#https://github.com/loanelly
                        k_r = self.key_right.get().lower()
                        k_b = self.key_btn.get().lower()

                        # Регистрируем новые клавиши в словаре состояний, если пользователь сменил их на лету
                        for k in [k_u, k_d, k_l, k_r, k_b]:
                            if k not in self.active_keys:
                                self.active_keys[k] = False

                        # Обработка осей (W, A, S, D)
                        self.update_key_state(k_u, y_val > high_boundary)
                        self.update_key_state(k_d, y_val < low_boundary)
                        self.update_key_state(k_r, x_val > high_boundary)
                        self.update_key_state(k_l, x_val < low_boundary)

                        # Обработка клика кнопки джойстика
                        self.update_key_state(k_b, btn_val == 1)
#https://github.com/loanelly
                except Exception:
                    pass
            time.sleep(0.002) # Легкая разгрузка процессора

    def on_close(self):
        self.stop_service()
        self.root.destroy()#https://github.com/loanelly

if __name__ == "__main__":
    root = tk.Tk()
    app = MartozGamepadApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
