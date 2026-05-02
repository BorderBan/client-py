import os
import hashlib
import json
import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading

# --- КОНФИГУРАЦИЯ ---
SERVER_URL = "https://server1.borderban.ru/mods/"
CONFIG_FILE = Path.home() / ".factorio_sync_config.json"

def get_file_hash(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Factorio Mod Sync")
        self.root.geometry("500x250")

        self.config = self.load_config()
        self.setup_ui()

    def load_config(self):
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
        return {"mods_path": ""}

    def save_config(self, mods_path):
        CONFIG_FILE.write_text(json.dumps({"mods_path": mods_path}))

    def setup_ui(self):
        # Выбор пути
        tk.Label(self.root, text="Путь к папке mods:").pack(pady=(10, 0))
        self.path_var = tk.StringVar(value=self.config["mods_path"])
        entry_frame = tk.Frame(self.root)
        entry_frame.pack(fill="x", padx=20, pady=5)
        tk.Entry(entry_frame, textvariable=self.path_var).pack(side="left", fill="x", expand=True)
        tk.Button(entry_frame, text="Обзор", command=self.select_path).pack(side="right", padx=5)

        # Статус и Прогресс
        self.status_label = tk.Label(self.root, text="Готов к работе", fg="blue")
        self.status_label.pack(pady=(10, 0))

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10)

        self.sync_btn = tk.Button(self.root, text="СИНХРОНИЗИРОВАТЬ", command=self.start_sync_thread,
                                  bg="#2c3e50", fg="white", font=("Arial", 10, "bold"), height=2)
        self.sync_btn.pack(pady=10)

    def select_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)
            self.save_config(path)

    def update_status(self, text, value=None):
        self.status_label.config(text=text)
        if value is not None:
            self.progress["value"] = value
        self.root.update_idletasks()

    def start_sync_thread(self):
        # Запускаем в отдельном потоке, чтобы GUI не фризился
        thread = threading.Thread(target=self.run_sync)
        thread.start()

    def run_sync(self):
        mods_path = self.path_var.get()
        if not mods_path:
            messagebox.showwarning("Внимание", "Сначала выберите папку с модами!")
            return

        self.sync_btn.config(state="disabled")
        try:
            # 1. Получение манифеста
            self.update_status("Получение списка модов с сервера...", 5)
            response = requests.get(f"{SERVER_URL}mods_list.json", timeout=15)
            response.raise_for_status()
            server_manifest = response.json()

            local_mods = Path(mods_path)
            if not local_mods.exists():
                local_mods.mkdir(parents=True, exist_ok=True)

            mod_status = {}

            # --- ЭТАП ОЧИСТКИ (Удаление лишнего) ---
            self.update_status("Очистка старых модов...", 10)
            local_files = list(local_mods.glob("*.zip"))
            for local_file in local_files:
                if local_file.name not in server_manifest:
                    print(f"Удаление лишнего файла: {local_file.name}")
                    local_file.unlink()
                    mod_status[local_file.name] = "удалено"
            # ---------------------------------------

            # 2. Синхронизация (Загрузка нужного)
            total_mods = len(server_manifest)
            current_mod_idx = 0

            for filename, server_hash in server_manifest.items():
                current_mod_idx += 1
                self.update_status(f"Синхронизация: {current_mod_idx}/{total_mods}",
                                   20 + (current_mod_idx / total_mods) * 80)

                local_file = local_mods / filename
                file_exists = local_file.exists()

                if not file_exists:
                    needs_download = True
                    mod_status[filename] = "добавлено"
                elif get_file_hash(local_file) != server_hash:
                    needs_download = True
                    mod_status[filename] = "обновлено"
                else:
                    needs_download = False
                    mod_status[filename] = "без изменений"

                if needs_download:
                    self.update_status(f"Загрузка: {filename}...", self.progress["value"])
                    with requests.get(f"{SERVER_URL}{filename}", stream=True) as r:
                        r.raise_for_status()
                        with open(local_file, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)

            self.update_status("Синхронизация завершена!", 100)

            # --- СОРТИРОВКА И ВЫВОД ОТЧЕТА ---
            sort_order = {
                "без изменений": 1,
                "обновлено": 2,
                "добавлено": 3,
                "удалено": 4
            }
            sorted_mods = sorted(mod_status.items(), key=lambda item: sort_order.get(item[1], 5))

            # Безопасный вызов отрисовки UI из фонового потока
            self.root.after(0, self.show_report, sorted_mods)

        except Exception as e:
            self.update_status("Ошибка!", 0)
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.root.after(0, lambda: self.sync_btn.config(state="normal"))

    def show_report(self, sorted_mods):
        report_win = tk.Toplevel(self.root)
        report_win.title("Отчет о синхронизации")
        report_win.geometry("400x300") # Компактный размер

        # Текстовое поле с темным фоном для читаемости цветного текста
        text_widget = tk.Text(report_win, font=("Consolas", 10), bg="#1e1e1e", fg="white", wrap="none")
        scrollbar_y = ttk.Scrollbar(report_win, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar_y.set)

        scrollbar_y.pack(side="right", fill="y")
        text_widget.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # Настраиваем цветовые теги
        text_widget.tag_config("добавлено", foreground="#55ff55")     # Светло-зеленый
        text_widget.tag_config("удалено", foreground="#ff5555")       # Светло-красный
        text_widget.tag_config("обновлено", foreground="#ffff55")     # Желтый
        text_widget.tag_config("без изменений", foreground="#888888") # Серый

        # Заполняем поле
        for mod, status in sorted_mods:
            text_widget.insert(tk.END, f"{mod}: ")
            text_widget.insert(tk.END, f"{status}\n", status)

        text_widget.config(state="disabled") # Только чтение

if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    root.mainloop()
