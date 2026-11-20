import os
import sys
import subprocess
import ctypes
import threading
import datetime
import csv
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image
import pandas as pd

from utils.config_manager import load_config, save_config
from utils.helpers import get_windows_theme, resource_path
from utils.file_exporter import save_exact_xls, save_invalid_dates, save_aol_json
from utils.bank_validator import validate_bank_selection, detect_bank_from_file
from processors.panin_processor import process_panin, OUTPUT_COLUMNS
from processors.bca_processor import process_bca

class UniversalAccurateConverter:
    def __init__(self, root):
        self.root = root
        version_str = "5.2.2"
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            v_path = os.path.join(exe_dir, "version.txt")
            if not os.path.exists(v_path):
                v_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "version.txt")
            if os.path.exists(v_path):
                with open(v_path, "r") as f:
                    version_str = f.read().strip()
        except Exception:
            pass
        self.root.title(f"Accurate Format Converter v{version_str}") 
        
        self.icon_path = resource_path("assets/rensa_logo.ico")

        try:
            myappid = 'accurate.format.converter.app' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        if os.path.exists(self.icon_path):
            try:
                self.root.iconbitmap(default=self.icon_path)
            except Exception as e:
                print(f"Error load icon: {e}")
        
        try:
            self.root.state('zoomed')
        except Exception:
            pass

        self.root.after(100, self.force_maximize)

        self.initial_theme = get_windows_theme()
        ctk.set_appearance_mode(self.initial_theme)

        self.setup_ui()
        self.root.after(500, self.show_tutorial)

    def force_maximize(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.user32.ShowWindow(hwnd, 3)
        except Exception:
            try:
                self.root.attributes('-zoomed', True)
            except Exception:
                pass

    def show_tutorial(self):
        config = load_config()
        if not config.get("show_tutorial", True):
            return 

        tut_win = ctk.CTkToplevel(self.root)
        tut_win.title("Panduan")
        
        if os.path.exists(self.icon_path):
            try: tut_win.after(200, lambda: tut_win.iconbitmap(self.icon_path))
            except Exception: pass

        tut_win.geometry("550x450")
        tut_win.resizable(False, False)
        tut_win.transient(self.root)
        tut_win.grab_set()

        frame = ctk.CTkFrame(tut_win, corner_radius=15)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(frame, text="Panduan Penggunaan", 
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")).pack(pady=(20, 10))
        
        tutorial_text = (
            "Panduan penggunaan aplikasi:\n\n"
            "1. Klik tombol 'Pilih File' untuk memuat dokumen mutasi (Excel/CSV/PDF).\n"
            "2. (Opsional) Centang 'Rapikan deskripsi' untuk pemformatan teks otomatis pada laporan.\n"
            "3. Klik 'PROSES DATA' untuk memulai konversi otomatis.\n"
            "4. Jika terdapat baris dengan tanggal tidak valid, data tersebut akan dipisahkan secara otomatis.\n"
            "5. Tentukan direktori penyimpanan, dan file siap diimpor ke sistem Accurate."
        )
        ctk.CTkLabel(frame, text=tutorial_text, justify="left", 
                     font=ctk.CTkFont(family="Segoe UI", size=13),
                     wraplength=450).pack(padx=30, pady=10, anchor="w")

        dont_show_var = tk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(frame, text="Jangan tampilkan panduan ini lagi", 
                              variable=dont_show_var, font=ctk.CTkFont(size=12))
        chk.pack(pady=(20, 10))

        def on_close():
            if dont_show_var.get():
                config["show_tutorial"] = False
                save_config(config)
            tut_win.destroy()

        btn_close = ctk.CTkButton(frame, text="Mulai", command=on_close, 
                                  font=ctk.CTkFont(weight="bold"), corner_radius=8)
        btn_close.pack(pady=20)

    def change_theme(self, new_mode: str):
        if new_mode == "System":
            ctk.set_appearance_mode(get_windows_theme())
        else:
            ctk.set_appearance_mode(new_mode)

    def change_bank(self, bank_name):
        logo_file = f"assets/{bank_name.lower()}.png"
        logo_file_dark = f"assets/{bank_name.lower()}_dark.png"
        
        full_path = resource_path(logo_file)
        full_path_dark = resource_path(logo_file_dark)
        
        if os.path.exists(full_path):
            try:
                img_light = Image.open(full_path)
                img_dark = Image.open(full_path_dark) if os.path.exists(full_path_dark) else img_light
                
                aspect_ratio = img_light.width / img_light.height
                new_width = int(60 * aspect_ratio)
                
                ctk_img = ctk.CTkImage(light_image=img_light, dark_image=img_dark, size=(new_width, 60))
                self.logo_label.configure(image=ctk_img)
            except Exception as e:
                print(f"Failed to load {logo_file}: {e}")
                self.logo_label.configure(image="")
        else:
            self.logo_label.configure(image="")

        if hasattr(self, 'chk_typo'):
            if bank_name == "Panin":
                self.chk_typo.pack(anchor="w")
            else:
                self.chk_typo.pack_forget()

    def setup_ui(self):
        self.root.configure(fg_color=("#F5F7FA", "#121212"))
        
        main_frame = ctk.CTkFrame(self.root, corner_radius=20, border_width=1, 
                                  border_color=("#E5E9F2", "#1E1E1E"), fg_color=("#FFFFFF", "#1E1E1E"))
        main_frame.pack(padx=25, pady=25, fill="both", expand=True)

        top_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_container.pack(fill="x", padx=35, pady=(25, 15))

        title_frame = ctk.CTkFrame(top_container, fg_color="transparent")
        title_frame.pack(side="left", fill="y")

        self.logo_label = ctk.CTkLabel(title_frame, text="")
        self.logo_label.pack(side="left", padx=(0, 15))

        header_text_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        header_text_frame.pack(side="left", anchor="w")
        
        ctk.CTkLabel(header_text_frame, text="Accurate Format Converter", 
                     font=ctk.CTkFont(family="Inter", size=24, weight="bold"), 
                     text_color=("#1A1F36", "#FFFFFF")).pack(anchor="w")
        ctk.CTkLabel(header_text_frame, text="Aplikasi konversi format mutasi rekening.", 
                     font=ctk.CTkFont(family="Inter", size=13), 
                     text_color=("#8792A2", "#A0AABF")).pack(anchor="w")

        controls_frame = ctk.CTkFrame(top_container, fg_color="transparent")
        controls_frame.pack(side="right")
        
        ctk.CTkLabel(controls_frame, text="Pilihan Bank:", font=ctk.CTkFont(family="Inter", size=12, weight="bold"), text_color=("#4F566B", "#D3D9E6")).pack(side="left", padx=(0, 10))
        
        self.bank_var = ctk.StringVar(value="BCA")
        self.bank_menu = ctk.CTkOptionMenu(controls_frame, values=["BCA", "Panin"],
                                           variable=self.bank_var, command=self.change_bank,
                                           font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
                                           fg_color=("#E3E8EE", "#2D3748"),
                                           button_color=("#CBD5E1", "#4A5568"),
                                           button_hover_color=("#94A3B8", "#718096"),
                                           text_color=("#1A202C", "#F7FAFC"),
                                           dropdown_font=ctk.CTkFont(family="Inter", size=13),
                                           dropdown_fg_color=("#FFFFFF", "#2D3748"),
                                           width=130, height=36)
        self.bank_menu.pack(side="left", padx=(0, 20))
        
        self.theme_menu = ctk.CTkOptionMenu(controls_frame, values=["System", "Dark", "Light"],
                                            command=self.change_theme, 
                                            font=ctk.CTkFont(family="Inter", size=12),
                                            fg_color=("#E5E9F2", "#2D3748"),
                                            button_color=("#CBD5E1", "#4A5568"), 
                                            button_hover_color=("#94A3B8", "#718096"), 
                                            text_color=("#4F566B", "#A0AABF"), width=90)
        self.theme_menu.pack(side="right")
        self.theme_menu.set(self.initial_theme) 

        divider = ctk.CTkFrame(main_frame, height=2, fg_color=("#E5E9F2", "#2D3748"))
        divider.pack(fill="x", padx=35, pady=(5, 10))

        input_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        input_container.pack(fill="x", padx=35, pady=15)
        
        ctk.CTkLabel(input_container, text="File Mutasi", font=ctk.CTkFont(family="Inter", size=14, weight="bold"), text_color=("#1A1F36", "#F7FAFC")).pack(anchor="w")
        
        file_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        file_frame.pack(fill="x", pady=(8, 0))

        self.path_var = tk.StringVar()
        self.entry_path = ctk.CTkEntry(file_frame, textvariable=self.path_var, width=600, height=45,
                                       placeholder_text="Pilih file mutasi (BCA: .pdf/.csv/.xlsx/.xls | Panin: .xls/.xlsx/.csv/.pdf)...",
                                       font=ctk.CTkFont(family="Inter", size=13),
                                       border_color=("#E5E9F2", "#4A5568"), border_width=2,
                                       fg_color=("#F9FAFB", "#2D3748"), corner_radius=10)
        self.entry_path.pack(side="left", padx=(0, 15), fill="x", expand=True)
        
        btn_browse = ctk.CTkButton(file_frame, text="Pilih File", width=120, height=45,
                                   font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                                   fg_color=("#0F172A", "#3B82F6"), hover_color=("#1E293B", "#2563EB"),
                                   text_color="#FFFFFF",
                                   command=self.browse_file, corner_radius=10)
        btn_browse.pack(side="left")

        options_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        options_container.pack(fill="x", padx=35, pady=5)
        
        self.use_regex_var = tk.BooleanVar(value=False) 
        self.chk_typo = ctk.CTkCheckBox(options_container, text="Rapikan spasi pada deskripsi transaksi", 
                                        font=ctk.CTkFont(family="Inter", size=12),
                                        variable=self.use_regex_var, corner_radius=6,
                                        fg_color=("#3B82F6", "#3B82F6"), border_color=("#CBD5E1", "#4A5568"),
                                        text_color=("#4F566B", "#A0AABF"))
        self.chk_typo.pack(anchor="w")
        
        action_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_container.pack(fill="x", padx=35, pady=20)
        
        self.btn_process = ctk.CTkButton(action_container, text="PROSES DATA", 
                                         font=ctk.CTkFont(family="Inter", size=15, weight="bold"), height=50,
                                         fg_color=("#10B981", "#10B981"), hover_color=("#059669", "#059669"), text_color="white",
                                         command=self.confirm_process, corner_radius=12)
        self.btn_process.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(action_container, height=6, corner_radius=3, fg_color=("#E5E9F2", "#2D3748"), progress_color=("#10B981", "#10B981"))
        self.progress_bar.pack(fill="x", pady=(15, 0))
        self.progress_bar.set(0)

        console_label_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        console_label_frame.pack(fill="x", padx=35, pady=(10, 0))
        ctk.CTkLabel(console_label_frame, text="Rincian Proses", font=ctk.CTkFont(family="Inter", size=13, weight="bold"), text_color=("#4F566B", "#D3D9E6")).pack(anchor="w")
        
        self.log_area = ctk.CTkTextbox(main_frame, corner_radius=12, border_width=1,
                                       border_color=("#E5E9F2", "#2D3748"),
                                       fg_color=("#F8FAFC", "#0F172A"),
                                       text_color=("#334155", "#38BDF8"),  # type: ignore[arg-type]
                                       wrap="none",
                                       font=ctk.CTkFont(family="Consolas", size=12))
        self.log_area.pack(fill="both", expand=True, padx=35, pady=(5, 25))
        self.log_area.configure(state="disabled")
        
        self.change_bank("BCA")

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        def update_log():
            self.log_area.configure(state='normal')
            self.log_area.insert("end", f"[{timestamp}] {msg}\n")
            self.log_area.see("end")
            self.log_area.configure(state='disabled')
        self.root.after(0, update_log)

    def update_progress(self, value):
        self.root.after(0, lambda: self.progress_bar.set(value))

    def clear_log(self):
        self.root.after(0, self._clear_log)
        
    def _clear_log(self):
        self.log_area.configure(state='normal')
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state='disabled')

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[
            ("Excel/CSV/PDF Files", "*.xls *.xlsx *.csv *.pdf"), 
            ("Excel 97-2003", "*.xls"), 
            ("Excel Workbook", "*.xlsx"), 
            ("CSV Document", "*.csv"), 
            ("PDF Document", "*.pdf"),
            ("All Files", "*.*")
        ])
        if f:
            self.path_var.set(f)
            self.log(f"File loaded: {os.path.basename(f)}")
            self.progress_bar.set(0)
            
            # Deteksi awal tanda tangan bank dokumen
            detected, desc = detect_bank_from_file(f)
            if detected:
                current_bank = self.bank_var.get()
                if detected.lower() != current_bank.lower():
                    if detected in ["BCA", "Panin"]:
                        self.log(f"[Peringatan] File ini terdeteksi sebagai mutasi Bank {detected}! Pilihan menu saat ini adalah '{current_bank}'. Pastikan ubah pilihan bank sebelum proses.")
                    else:
                        self.log(f"[Peringatan] File ini terdeteksi sebagai dokumen Bank {detected}! Aplikasi saat ini hanya mendukung Bank BCA dan Panin.")
                else:
                    self.log(f"[Info] {desc} ({detected}).")

    def show_copyable_dialog(self, title, message, path_to_copy=""):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        
        has_table = "lembar rekonsiliasi" in message.lower() or "=====" in message
        if has_table:
            dialog.geometry("860x580")
            font_choice = ("Consolas", 11)
        else:
            dialog.geometry("550x280")
            font_choice = ctk.CTkFont(size=13)
            
        dialog.transient(self.root)
        dialog.grab_set()

        if os.path.exists(self.icon_path):
            try: dialog.after(200, lambda: dialog.iconbitmap(self.icon_path))
            except Exception: pass

        frame = ctk.CTkFrame(dialog, corner_radius=15)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=(0, 10))

        def open_file_location():
            target = path_to_copy if path_to_copy else ""
            if target:
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(target)
                except Exception:
                    pass
                try:
                    norm_path = os.path.normpath(os.path.abspath(target))
                    if os.path.isfile(norm_path):
                        subprocess.Popen(f'explorer /select,"{norm_path}"')
                    elif os.path.isdir(norm_path):
                        os.startfile(norm_path)
                    else:
                        parent = os.path.dirname(norm_path)
                        if os.path.isdir(parent):
                            os.startfile(parent)
                except Exception as e:
                    self.log(f"[WARN] Gagal membuka lokasi di Explorer: {e}")
            btn_open.configure(text="Terbuka!")
            dialog.after(2000, lambda: btn_open.configure(text="Lihat Lokasi"))

        def copy_all_info():
            self.root.clipboard_clear()
            self.root.clipboard_append(message)
            self.root.update()
            btn_copy_all.configure(text="Tersalin!")
            dialog.after(2000, lambda: btn_copy_all.configure(text="Copy Semua Rincian"))

        btn_open = ctk.CTkButton(btn_frame, text="Lihat Lokasi", width=110, 
                                 command=open_file_location, fg_color="#3498db", hover_color="#2980b9")
        btn_open.pack(side="left", padx=10)

        if has_table:
            btn_copy_all = ctk.CTkButton(btn_frame, text="Copy Semua Rincian", width=140,
                                         command=copy_all_info, fg_color="#10B981", hover_color="#059669")
            btn_copy_all.pack(side="left", padx=10)

        btn_ok = ctk.CTkButton(btn_frame, text="OK", width=100, command=dialog.destroy)
        btn_ok.pack(side="left", padx=10)

        txt_area = ctk.CTkTextbox(frame, wrap="word" if not has_table else "none", font=font_choice)
        txt_area.pack(side="top", padx=10, pady=(10, 10), fill="both", expand=True)
        txt_area.insert("0.0", message)
        txt_area.configure(state="disabled")

    def confirm_process(self):
        filepath = self.path_var.get().strip()
        
        if not filepath:
            messagebox.showwarning("Peringatan", "Silakan pilih file mutasi terlebih dahulu.")
            self.log("[INFO] Proses dibatalkan: File belum dipilih.")
            return

        bank = self.bank_var.get()
        
        # Validasi Ketat Kesesuaian Sumber Bank
        is_valid, err_msg, detected_bank = validate_bank_selection(filepath, bank)
        if not is_valid:
            self.log(f"[REJECTED] {err_msg.replace(chr(10), ' ')}")
            messagebox.showerror("Format Bank Tidak Sesuai", err_msg)
            return
        
        filename = os.path.basename(filepath)
        confirm = messagebox.askyesno("Konfirmasi", f"Mulai proses konversi untuk file ini?\n\nFile: {filename}\nBank: {bank}")
        
        if confirm:
            self.btn_process.configure(state="disabled", text="Sedang diproses...")
            self.progress_bar.set(0)
            threading.Thread(target=self.route_process, daemon=True).start()
        else:
            self.log("[INFO] Proses dibatalkan oleh user.")

    def route_process(self):
        bank = self.bank_var.get()
        filepath = self.path_var.get().strip()
        self.clear_log()
        
        def handle_error(msg):
            self.root.after(0, lambda: self.reset_ui_state(is_error=True, error_msg=msg))

        # Secondary Barrier: Pastikan kesesuaian bank di dalam thread pemrosesan
        is_valid, err_msg, _ = validate_bank_selection(filepath, bank)
        if not is_valid:
            handle_error(err_msg)
            return
        
        if bank == "Panin":
            process_panin(
                filepath=filepath,
                use_regex=self.use_regex_var.get(),
                log_callback=self.log,
                progress_callback=self.update_progress,
                success_callback=lambda df_out, inv_data, dum, fpath: self.root.after(0, lambda: self.finish_saving_panin(df_out, inv_data, dum, filepath)),
                error_callback=handle_error
            )
        elif bank == "BCA":
            if not (filepath.lower().endswith('.pdf') or filepath.lower().endswith('.csv') or filepath.lower().endswith('.xlsx') or filepath.lower().endswith('.xls')):
                handle_error("Format file tidak valid. Mutasi BCA harus dalam format PDF, CSV, atau Excel (.xlsx/.xls).")
                return
            process_bca(
                filepath=filepath,
                log_callback=self.log,
                progress_callback=self.update_progress,
                success_callback=lambda txs, rek, nm, saldo_a, saldo_ak, fpath: self.root.after(0, lambda: self.finish_saving_bca_csv(txs, rek, nm, saldo_a, saldo_ak, filepath)),
                error_callback=handle_error
            )
        else:
            self.reset_ui_state(is_error=True, error_msg=f"Fitur untuk Bank {bank} masih dalam tahap pengembangan.")

    def reset_ui_state(self, is_error=False, error_msg=""):
        if is_error:
            self.update_progress(0)
            self.log(f"[ERROR] {error_msg}")
            
        self.btn_process.configure(state="normal", text="PROSES DATA")
        
    def show_export_config_dialog(self, bank, tx_dates, total_count):
        """
        Modal dialog: date range filter + template selection.
        Returns dict with 'date_from', 'date_to' (datetime.date), 'templates' (list of int 0-based)
        or None if cancelled.
        """
        if not tx_dates:
            return None

        result = {}
        unique_dates = sorted(list(set(tx_dates)))
        date_options = [d.strftime("%d/%m/%Y") for d in unique_dates]
        date_lookup = {d.strftime("%d/%m/%Y"): d for d in unique_dates}

        min_date = unique_dates[0]
        max_date = unique_dates[-1]
        is_single_date_dataset = (len(unique_dates) == 1)

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Pengaturan Hasil Konversi")
        dialog.geometry("560x590")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Atur Icon Window (Rensa Logo) agar tidak memakai icon default Tkinter
        if hasattr(self, 'icon_path') and os.path.exists(self.icon_path):
            try:
                dialog.iconbitmap(self.icon_path)
            except Exception:
                pass
            dialog.after(100, lambda: dialog.iconbitmap(self.icon_path))
            dialog.after(300, lambda: dialog.iconbitmap(self.icon_path))

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 560) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 590) // 2
        dialog.geometry(f"+{max(0,x)}+{max(0,y)}")

        main_f = ctk.CTkFrame(dialog, fg_color="transparent")
        main_f.pack(fill="both", expand=True, padx=25, pady=20)

        # === SECTION 1: DATE SELECTION ===
        ctk.CTkLabel(main_f, text="RENTANG TANGGAL",
                     font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                     text_color=("#1A1F36", "#F7FAFC")).pack(anchor="w")
        ctk.CTkLabel(main_f,
                     text=f"Data tersedia: {date_options[0]} — {date_options[-1]}  ({total_count} transaksi)",
                     font=ctk.CTkFont(family="Inter", size=12),
                     text_color=("#8792A2", "#A0AABF")).pack(anchor="w", pady=(2, 6))

        mode_var = tk.StringVar(value="single" if is_single_date_dataset else "range")
        from_var = tk.StringVar(value=date_options[0])
        to_var = tk.StringVar(value=date_options[-1])
        single_var = tk.StringVar(value=date_options[0])

        # Mode Selector (Hanya jika mutasi memiliki lebih dari 1 tanggal)
        if not is_single_date_dataset:
            mode_frame = ctk.CTkFrame(main_f, fg_color="transparent")
            mode_frame.pack(fill="x", pady=(0, 6))

            ctk.CTkLabel(mode_frame, text="Pilih Mode:", font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                         text_color=("#4F566B", "#D3D9E6")).pack(side="left", padx=(0, 10))

            def on_mode_change():
                if mode_var.get() == "single":
                    range_container.pack_forget()
                    single_container.pack(fill="x", pady=(0, 8))
                else:
                    single_container.pack_forget()
                    range_container.pack(fill="x", pady=(0, 8))
                update_count()

            ctk.CTkRadioButton(mode_frame, text="Rentang Tanggal", variable=mode_var, value="range",
                               command=on_mode_change, font=ctk.CTkFont(family="Inter", size=12),
                               fg_color=("#3B82F6", "#2563EB"), text_color=("#1A1F36", "#F7FAFC")).pack(side="left", padx=(0, 15))
            ctk.CTkRadioButton(mode_frame, text="Satu Tanggal Saja", variable=mode_var, value="single",
                               command=on_mode_change, font=ctk.CTkFont(family="Inter", size=12),
                               fg_color=("#3B82F6", "#2563EB"), text_color=("#1A1F36", "#F7FAFC")).pack(side="left")

        # Container 1: Mode Rentang Tanggal (Presets + 2 Dropdown)
        range_container = ctk.CTkFrame(main_f, fg_color="transparent")

        preset_frame = ctk.CTkFrame(range_container, fg_color="transparent")
        preset_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(preset_frame, text="Pilihan Cepat:",
                     font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                     text_color=("#4F566B", "#D3D9E6")).pack(side="left", padx=(0, 8))

        # Dropdowns Frame (Dari & Sampai)
        date_frame = ctk.CTkFrame(range_container, fg_color="transparent")
        date_frame.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(date_frame, text="Dari:", font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                     text_color=("#4F566B", "#D3D9E6")).pack(side="left")

        def on_from_select(choice):
            from_var.set(choice)
            if date_lookup[choice] > date_lookup[to_var.get()]:
                to_var.set(choice)
            update_count()

        def on_to_select(choice):
            to_var.set(choice)
            if date_lookup[choice] < date_lookup[from_var.get()]:
                from_var.set(choice)
            update_count()

        from_menu = ctk.CTkOptionMenu(
            date_frame, values=date_options, variable=from_var, command=on_from_select,
            width=140, height=36,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            dropdown_font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=("#E3E8EE", "#2D3748"), button_color=("#CBD5E1", "#4A5568"),
            button_hover_color=("#94A3B8", "#718096"), text_color=("#1A202C", "#F7FAFC"),
            dropdown_fg_color=("#FFFFFF", "#2D3748"), corner_radius=8
        )
        from_menu.pack(side="left", padx=(8, 20))

        ctk.CTkLabel(date_frame, text="Sampai:", font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                     text_color=("#4F566B", "#D3D9E6")).pack(side="left")

        to_menu = ctk.CTkOptionMenu(
            date_frame, values=date_options, variable=to_var, command=on_to_select,
            width=140, height=36,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            dropdown_font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=("#E3E8EE", "#2D3748"), button_color=("#CBD5E1", "#4A5568"),
            button_hover_color=("#94A3B8", "#718096"), text_color=("#1A202C", "#F7FAFC"),
            dropdown_fg_color=("#FFFFFF", "#2D3748"), corner_radius=8
        )
        to_menu.pack(side="left", padx=(8, 0))

        def set_preset_all():
            from_var.set(date_options[0])
            to_var.set(date_options[-1])
            update_count()

        def set_preset_p1():
            p1 = [d for d in unique_dates if d.day <= 15]
            if p1:
                from_var.set(p1[0].strftime("%d/%m/%Y"))
                to_var.set(p1[-1].strftime("%d/%m/%Y"))
                update_count()

        def set_preset_p2():
            p2 = [d for d in unique_dates if d.day >= 16]
            if p2:
                from_var.set(p2[0].strftime("%d/%m/%Y"))
                to_var.set(p2[-1].strftime("%d/%m/%Y"))
                update_count()

        ctk.CTkButton(preset_frame, text="Semua Mutasi", height=28, width=105,
                      font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                      fg_color=("#3B82F6", "#2563EB"), hover_color=("#2563EB", "#1D4ED8"),
                      text_color="white", corner_radius=6, command=set_preset_all).pack(side="left", padx=(0, 6))

        if any(d.day <= 15 for d in unique_dates):
            ctk.CTkButton(preset_frame, text="Tgl 01–15", height=28, width=85,
                          font=ctk.CTkFont(family="Inter", size=11),
                          fg_color=("#E5E9F2", "#2D3748"), hover_color=("#CBD5E1", "#4A5568"),
                          text_color=("#4F566B", "#D3D9E6"), corner_radius=6, command=set_preset_p1).pack(side="left", padx=(0, 6))

        if any(d.day >= 16 for d in unique_dates):
            ctk.CTkButton(preset_frame, text="Tgl 16–Akhir", height=28, width=95,
                          font=ctk.CTkFont(family="Inter", size=11),
                          fg_color=("#E5E9F2", "#2D3748"), hover_color=("#CBD5E1", "#4A5568"),
                          text_color=("#4F566B", "#D3D9E6"), corner_radius=6, command=set_preset_p2).pack(side="left", padx=(0, 6))

        # Container 2: Mode Satu Tanggal Saja (Hanya 1 Dropdown)
        single_container = ctk.CTkFrame(main_f, fg_color="transparent")
        single_row = ctk.CTkFrame(single_container, fg_color="transparent")
        single_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(single_row, text="Pilih Tanggal:", font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                     text_color=("#4F566B", "#D3D9E6")).pack(side="left", padx=(0, 10))

        def on_single_select(choice):
            single_var.set(choice)
            update_count()

        single_menu = ctk.CTkOptionMenu(
            single_row, values=date_options, variable=single_var, command=on_single_select,
            width=160, height=36,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            dropdown_font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=("#E3E8EE", "#2D3748"), button_color=("#CBD5E1", "#4A5568"),
            button_hover_color=("#94A3B8", "#718096"), text_color=("#1A202C", "#F7FAFC"),
            dropdown_fg_color=("#FFFFFF", "#2D3748"), corner_radius=8
        )
        single_menu.pack(side="left")

        # Initial layout pack
        if is_single_date_dataset:
            single_container.pack(fill="x", pady=(0, 8))
        else:
            range_container.pack(fill="x", pady=(0, 8))

        ctk.CTkFrame(main_f, height=2, fg_color=("#E5E9F2", "#2D3748")).pack(fill="x", pady=10)

        # === SECTION 2: TEMPLATE SELECTION ===
        tmpl_header = ctk.CTkFrame(main_f, fg_color="transparent")
        tmpl_header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(tmpl_header, text="PILIH TEMPLATE OUTPUT",
                     font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                     text_color=("#1A1F36", "#F7FAFC")).pack(side="left")

        if bank == "BCA":
            template_names = [
                "1. Template AOL Format JSON (.json)  [Rekomendasi]",
                "2. Template AOL Format Excel Non-JSON (.xls)",
                "3. Template Rekening Tahapan (.csv)",
                "4. Template Rekening Giro / KlikBCA (.csv)"
            ]
        else:
            template_names = [
                "1. Template AOL Format JSON (.json)  [Rekomendasi]",
                "2. Template AOL Format Excel Non-JSON (.xls)"
            ]

        chk_vars = []
        chk_widgets = []

        tmpl_hint_label = ctk.CTkLabel(main_f, text="", font=ctk.CTkFont(family="Inter", size=11))

        def update_tmpl_hint():
            sel_cnt = sum(1 for v in chk_vars if v.get() == 1)
            if sel_cnt == 1:
                tmpl_hint_label.configure(text="💡 1 template dipilih: berkas akan disimpan langsung tanpa membuat folder baru.",
                                          text_color=("#10B981", "#10B981"))
            elif sel_cnt > 1:
                tmpl_hint_label.configure(text=f"💡 {sel_cnt} template dipilih: berkas akan disimpan rapi di dalam satu folder.",
                                          text_color=("#6B7280", "#9CA3AF"))
            else:
                tmpl_hint_label.configure(text="⚠ Pilih minimal satu template output.",
                                          text_color=("#EF4444", "#EF4444"))

        def on_chk_click():
            any_off = any(v.get() == 0 for v in chk_vars)
            btn_toggle_tmpl.configure(text="Pilih Semua" if all(v.get() == 0 for v in chk_vars) else ("Pilih Semua" if any_off else "Batalkan Semua"))
            update_tmpl_hint()

        for name in template_names:
            var = tk.IntVar(value=1)
            chk_vars.append(var)
            chk = ctk.CTkCheckBox(main_f, text=name, variable=var,
                                  onvalue=1, offvalue=0,
                                  command=on_chk_click,
                                  font=ctk.CTkFont(family="Inter", size=12),
                                  fg_color=("#3B82F6", "#3B82F6"),
                                  border_color=("#CBD5E1", "#4A5568"),
                                  text_color=("#4F566B", "#A0AABF"),
                                  corner_radius=6)
            chk.pack(anchor="w", pady=3)
            chk.select()
            chk_widgets.append(chk)

        def toggle_all_templates():
            any_off = any(v.get() == 0 for v in chk_vars)
            for c in chk_widgets:
                if any_off:
                    c.select()
                else:
                    c.deselect()
            btn_toggle_tmpl.configure(text="Batalkan Semua" if any_off else "Pilih Semua")
            update_tmpl_hint()

        btn_toggle_tmpl = ctk.CTkButton(tmpl_header, text="Batalkan Semua", height=24, width=95,
                                        font=ctk.CTkFont(family="Inter", size=11),
                                        fg_color=("#E5E9F2", "#2D3748"), hover_color=("#CBD5E1", "#4A5568"),
                                        text_color=("#4F566B", "#D3D9E6"), corner_radius=6,
                                        command=toggle_all_templates)
        btn_toggle_tmpl.pack(side="right")

        tmpl_hint_label.pack(anchor="w", pady=(4, 0))
        update_tmpl_hint()

        ctk.CTkFrame(main_f, height=2, fg_color=("#E5E9F2", "#2D3748")).pack(fill="x", pady=10)

        # === SECTION 3: LIVE COUNT ===
        count_label = ctk.CTkLabel(main_f,
                                   text=f"Transaksi yang akan diekspor: {total_count} dari {total_count} (100.0%)",
                                   font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
                                   text_color=("#10B981", "#10B981"))
        count_label.pack(anchor="w", pady=(0, 15))

        # Function to update count label dynamically
        def update_count():
            if mode_var.get() == "single":
                sel_d = date_lookup.get(single_var.get(), min_date)
                cnt = sum(1 for d in tx_dates if d == sel_d)
            else:
                fd = date_lookup.get(from_var.get(), min_date)
                td = date_lookup.get(to_var.get(), max_date)
                cnt = sum(1 for d in tx_dates if fd <= d <= td)
            pct = (cnt / total_count * 100) if total_count > 0 else 0
            count_label.configure(
                text=f"Transaksi yang akan diekspor: {cnt} dari {total_count} ({pct:.1f}%)",
                text_color=("#10B981", "#10B981") if cnt > 0 else ("#EF4444", "#EF4444")
            )

        # === BUTTONS ===
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x")

        def on_save():
            selected = [i for i, v in enumerate(chk_vars) if v.get() == 1]
            if not selected:
                messagebox.showwarning("Peringatan", "Pilih minimal satu template output.", parent=dialog)
                return
            if mode_var.get() == "single":
                sel_d = date_lookup.get(single_var.get())
                if not sel_d:
                    messagebox.showwarning("Peringatan", "Pilih tanggal yang valid.", parent=dialog)
                    return
                fd = td = sel_d
            else:
                fd = date_lookup.get(from_var.get())
                td = date_lookup.get(to_var.get())
                if not fd or not td:
                    messagebox.showwarning("Peringatan", "Pilih tanggal yang valid.", parent=dialog)
                    return
                if fd > td:
                    messagebox.showwarning("Rentang Tidak Valid",
                                           "Tanggal 'Dari' harus sebelum atau sama dengan tanggal 'Sampai'.", parent=dialog)
                    return
            cnt = sum(1 for d in tx_dates if fd <= d <= td)
            if cnt == 0:
                messagebox.showwarning("Tidak Ada Data",
                                       "Tidak ada transaksi pada tanggal yang dipilih.", parent=dialog)
                return
            result['date_from'] = fd
            result['date_to'] = td
            result['templates'] = selected
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="SIMPAN", width=200, height=42,
                      font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                      fg_color=("#10B981", "#10B981"), hover_color=("#059669", "#059669"),
                      text_color="white", command=on_save, corner_radius=10).pack(side="left", padx=(0, 15))
        ctk.CTkButton(btn_frame, text="BATAL", width=120, height=42,
                      font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                      fg_color=("#E5E9F2", "#2D3748"), hover_color=("#CBD5E1", "#4A5568"),
                      text_color=("#4F566B", "#D3D9E6"), command=on_cancel, corner_radius=10).pack(side="left")

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()

        if 'templates' not in result:
            return None
        return result

    def finish_saving_panin(self, df_output, invalid_dates_data, num_dummy, filepath):
        try:
            df_tx = df_output.iloc[num_dummy + 1 : len(df_output) - 2]
            tx_dates = []
            for _, r in df_tx.iterrows():
                t_str = str(r[OUTPUT_COLUMNS['tgl']]).strip()
                try:
                    dt = datetime.datetime.strptime(t_str, "%d/%m/%Y").date()
                except Exception:
                    dt = datetime.date.today()
                tx_dates.append(dt)

            config = self.show_export_config_dialog("Panin", tx_dates, len(df_tx))
            if not config:
                self.update_progress(0)
                self.log("[INFO] Proses penyimpanan dibatalkan oleh pengguna.")
                return

            date_from = config['date_from']
            date_to = config['date_to']
            chosen_templates = config['templates']

            filtered_indices = [i for i, d in enumerate(tx_dates) if date_from <= d <= date_to]
            df_filtered_tx = df_tx.iloc[filtered_indices].copy()

            if df_filtered_tx.empty:
                raise Exception("Tidak ada transaksi dalam rentang tanggal yang dipilih.")

            # Rekalkulasi Saldo Awal, Total Debet, Total Kredit, Saldo Akhir rentang baru
            first_row = df_filtered_tx.iloc[0]
            first_bal = float(first_row[OUTPUT_COLUMNS['bal']])
            first_deb = float(first_row[OUTPUT_COLUMNS['deb']]) if pd.notna(first_row[OUTPUT_COLUMNS['deb']]) and first_row[OUTPUT_COLUMNS['deb']] not in ("", None) else 0.0
            first_kre = float(first_row[OUTPUT_COLUMNS['kre']]) if pd.notna(first_row[OUTPUT_COLUMNS['kre']]) and first_row[OUTPUT_COLUMNS['kre']] not in ("", None) else 0.0
            new_saldo_awal = round(first_bal - first_kre + first_deb, 2)

            new_total_debet = round(sum(float(r[OUTPUT_COLUMNS['deb']]) for _, r in df_filtered_tx.iterrows() if pd.notna(r[OUTPUT_COLUMNS['deb']]) and r[OUTPUT_COLUMNS['deb']] not in ("", None)), 2)
            new_total_kredit = round(sum(float(r[OUTPUT_COLUMNS['kre']]) for _, r in df_filtered_tx.iterrows() if pd.notna(r[OUTPUT_COLUMNS['kre']]) and r[OUTPUT_COLUMNS['kre']] not in ("", None)), 2)
            new_saldo_akhir = round(float(df_filtered_tx.iloc[-1][OUTPUT_COLUMNS['bal']]), 2)

            base_name = os.path.splitext(os.path.basename(filepath))[0]
            base_name = re.sub(r'^(?:panin[\s\_-]*)+', '', base_name, flags=re.IGNORECASE)

            if 1 in chosen_templates:
                default_name = f"{base_name} (Template AOL Format Excel (Non-JSON)).xls"
                def_ext = ".xls"
                file_types = [("Excel 97-2003", "*.xls"), ("Semua File", "*.*")]
            else:
                default_name = f"{base_name} (Template AOL Format JSON).json"
                def_ext = ".json"
                file_types = [("JSON File", "*.json"), ("Semua File", "*.*")]

            save_path = filedialog.asksaveasfilename(
                defaultextension=def_ext,
                filetypes=file_types,
                title="Simpan Format Accurate Panin",
                initialfile=default_name
            )

            if not save_path:
                self.update_progress(0)
                self.log("[INFO] Penyimpanan dibatalkan oleh user.")
                messagebox.showinfo("Batal", "Penyimpanan file dibatalkan.")
                return

            base_dir = os.path.dirname(save_path)
            raw_stem = os.path.splitext(os.path.basename(save_path))[0]
            clean_stem = re.sub(r'\s*\((?:Template AOL Format (?:Excel \(Non-JSON\)|JSON))\)', '', raw_stem)

            xls_save_path = os.path.join(base_dir, f"{clean_stem} (Template AOL Format Excel (Non-JSON)).xls")
            json_save_path = os.path.join(base_dir, f"{clean_stem} (Template AOL Format JSON).json")

            saved_files = []

            # 1. Simpan Template 2 (.xls) jika dipilih (Index 1)
            if 1 in chosen_templates:
                num_dummy = 7
                if len(df_filtered_tx) >= num_dummy:
                    df_dummy = df_filtered_tx.iloc[:num_dummy].copy()
                else:
                    rows = []
                    for i in range(num_dummy):
                        rows.append(df_filtered_tx.iloc[i % len(df_filtered_tx)].to_dict())
                    df_dummy = pd.DataFrame(rows)

                row_saldo_awal = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Awal', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: new_saldo_awal}])
                row_total_mutasi = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Total Mutasi', OUTPUT_COLUMNS['deb']: new_total_debet, OUTPUT_COLUMNS['kre']: new_total_kredit, OUTPUT_COLUMNS['bal']: ""}])
                row_saldo_akhir = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Akhir', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: new_saldo_akhir}])

                df_output_filtered = pd.concat([df_dummy, row_saldo_awal, df_filtered_tx, row_total_mutasi, row_saldo_akhir], ignore_index=True)
                cols = list(OUTPUT_COLUMNS.values())
                success = save_exact_xls(df_output_filtered, xls_save_path, num_dummy, columns=cols)
                if success:
                    saved_files.append(f"Template AOL Format Excel (Non-JSON): {os.path.basename(xls_save_path)}")
                    self.log(f"[OK] Panin Excel Saved: {os.path.basename(xls_save_path)}")

            # 2. Simpan Template 1 (.json) jika dipilih (Index 0)
            if 0 in chosen_templates:
                rek_panin = getattr(df_output, 'attrs', {}).get("account_number")
                if not rek_panin:
                    rek_match = re.search(r'\b(\d{8,16})\b', os.path.basename(filepath))
                    rek_panin = rek_match.group(1) if rek_match else "0000000000"

                panin_mutation_list = []
                for _, r in df_filtered_tx.iterrows():
                    t_date = str(r[OUTPUT_COLUMNS['tgl']]).strip()
                    desc = str(r[OUTPUT_COLUMNS['desc']]).strip()
                    deb_str = r[OUTPUT_COLUMNS['deb']]
                    kre_str = r[OUTPUT_COLUMNS['kre']]
                    d_val = float(deb_str) if pd.notna(deb_str) and deb_str not in ("", None) else 0.0
                    k_val = float(kre_str) if pd.notna(kre_str) and kre_str not in ("", None) else 0.0
                    amt = k_val if k_val > 0 else -d_val
                    b_val = float(r[OUTPUT_COLUMNS['bal']]) if pd.notna(r[OUTPUT_COLUMNS['bal']]) and r[OUTPUT_COLUMNS['bal']] not in ("", None) else 0.0
                    panin_mutation_list.append({
                        "transDate": t_date,
                        "description": desc,
                        "amount": amt,
                        "balance": b_val
                    })

                save_aol_json(json_save_path, rek_panin, new_saldo_awal, new_saldo_akhir, panin_mutation_list)
                saved_files.append(f"Template AOL Format JSON: {os.path.basename(json_save_path)}")
                self.log(f"[OK] Panin Template AOL Format JSON Saved: {os.path.basename(json_save_path)}")

            self.update_progress(1.0)
            rekomendasi_txt = "\nSaran: Gunakan Template 1 (Format JSON AOL) untuk impor ke Accurate Online karena format JSON resmi ini paling stabil dan tidak terpengaruh perubahan format dari pihak bank."
            files_list_str = "\n".join([f"{idx+1}. {fn}" for idx, fn in enumerate(saved_files)])
            if date_from == date_to:
                range_info = f"Tanggal Mutasi: {date_from.strftime('%d/%m/%Y')} (1 Hari)\nTotal Mutasi: {len(df_filtered_tx)} baris\nSaldo Awal: Rp {new_saldo_awal:,.2f} | Saldo Akhir: Rp {new_saldo_akhir:,.2f}"
            else:
                range_info = f"Rentang Tanggal: {date_from.strftime('%d/%m/%Y')} s/d {date_to.strftime('%d/%m/%Y')}\nTotal Mutasi: {len(df_filtered_tx)} baris\nSaldo Awal: Rp {new_saldo_awal:,.2f} | Saldo Akhir: Rp {new_saldo_akhir:,.2f}"

            audit_table = getattr(df_output, 'attrs', {}).get("audit_table", "")
            if len(df_filtered_tx) < len(df_tx):
                table_info = (
                    f"\n\n[REKONSILIASI RENTANG TERPILIH]\n"
                    f"Saldo Awal   : Rp {new_saldo_awal:,.2f}\n"
                    f"Total Debet  : Rp {new_total_debet:,.2f}\n"
                    f"Total Kredit : Rp {new_total_kredit:,.2f}\n"
                    f"Saldo Akhir  : Rp {new_saldo_akhir:,.2f}\n"
                    f"Status       : [Cocok / Klop Rp 0,00]"
                )
            else:
                table_info = f"\n\n{audit_table}" if audit_table else ""

            if invalid_dates_data:
                error_file = save_invalid_dates(invalid_dates_data, filepath, log_callback=self.log)
                msg = f"Berkas berhasil disimpan ({len(saved_files)} file):\n{files_list_str}\n\n{range_info}\nInvalid Date: {len(invalid_dates_data)} baris (diabaikan){rekomendasi_txt}{table_info}"
                if error_file:
                    msg += f"\nFile error saved: {os.path.basename(error_file)}"
                self.show_copyable_dialog("Selesai dengan Peringatan", msg, path_to_copy=save_path)
            else:
                msg = f"Berkas berhasil disimpan ({len(saved_files)} file):\n{files_list_str}\n\n{range_info}{rekomendasi_txt}{table_info}"
                self.show_copyable_dialog("Selesai", msg, path_to_copy=save_path)

        except Exception as e:
            self.reset_ui_state(is_error=True, error_msg=str(e))
        finally:
            self.btn_process.configure(state="normal", text="PROSES DATA")

    def finish_saving_bca_csv(self, transactions, rekening, nama, saldo_awal, saldo_akhir, filepath):
        try:
            periode_from_meta = transactions[0].get("_periode_raw", "") if transactions else ""
            year_match = re.search(r'\b(20\d{2}|19\d{2})\b', periode_from_meta) if periode_from_meta else None
            if not year_match:
                year_match = re.search(r'\b(20\d{2}|19\d{2})\b', filepath)
            effective_year = year_match.group(1) if year_match else str(datetime.datetime.now().year)

            def format_bca_ddmmyyyy(raw_date, year_fallback):
                d = str(raw_date).replace("'", "").strip()
                if not d: return ""
                if "PEND" in d.upper():
                    for prev_tx in reversed(transactions):
                        pt = str(prev_tx.get("tanggal", "")).replace("'", "").strip()
                        if pt and "PEND" not in pt.upper():
                            p_parts = pt.split('/')
                            if len(p_parts) == 2:
                                return f"{int(p_parts[0]):02d}/{int(p_parts[1]):02d}/{year_fallback}"
                            elif len(p_parts) >= 3:
                                return f"{int(p_parts[0]):02d}/{int(p_parts[1]):02d}/{p_parts[2]}"
                    now = datetime.datetime.now()
                    return f"{now.day:02d}/{now.month:02d}/{year_fallback}"
                p = d.split('/')
                if len(p) == 2:
                    return f"{p[0]:0>2}/{p[1]:0>2}/{year_fallback}"
                elif len(p) >= 3:
                    return f"{p[0]:0>2}/{p[1]:0>2}/{p[2]}"
                return d

            tx_dates = []
            for tx in transactions:
                t_clean = format_bca_ddmmyyyy(tx["tanggal"], effective_year)
                try:
                    dt = datetime.datetime.strptime(t_clean, "%d/%m/%Y").date()
                except Exception:
                    dt = datetime.date.today()
                tx_dates.append(dt)

            config = self.show_export_config_dialog("BCA", tx_dates, len(transactions))
            if not config:
                self.update_progress(0)
                self.log("[INFO] Proses penyimpanan dibatalkan oleh pengguna.")
                return

            date_from = config['date_from']
            date_to = config['date_to']
            chosen_templates = config['templates']

            filtered_txs = [tx for i, tx in enumerate(transactions) if date_from <= tx_dates[i] <= date_to]
            if not filtered_txs:
                raise Exception("Tidak ada transaksi dalam rentang tanggal yang dipilih.")

            first_tx = filtered_txs[0]
            first_bal = float(first_tx["saldo"])
            first_mut = float(first_tx["mutasi"])
            if first_tx["tipe"] == "CR":
                new_saldo_awal = round(first_bal - first_mut, 2)
            else:
                new_saldo_awal = round(first_bal + first_mut, 2)

            new_total_debet = round(sum(tx["mutasi"] for tx in filtered_txs if tx["tipe"] == "DB"), 2)
            new_total_kredit = round(sum(tx["mutasi"] for tx in filtered_txs if tx["tipe"] == "CR"), 2)
            new_saldo_akhir = round(float(filtered_txs[-1]["saldo"]), 2)

            base_name = os.path.splitext(os.path.basename(filepath))[0]
            base_name = re.sub(r'^(?:bca[\s\_-]*)+', '', base_name, flags=re.IGNORECASE)

            saved_files = []

            if len(chosen_templates) == 1:
                single_idx = chosen_templates[0]
                if single_idx == 0:
                    default_file_name = f"{base_name} (1 - Template AOL Format JSON).json"
                    def_ext = ".json"
                    file_types = [("JSON File", "*.json"), ("Semua File", "*.*")]
                    dialog_title = "Simpan Template AOL Format JSON"
                elif single_idx == 1:
                    default_file_name = f"{base_name} (2 - Template AOL Format Excel (Non-JSON)).xls"
                    def_ext = ".xls"
                    file_types = [("Excel 97-2003", "*.xls"), ("Semua File", "*.*")]
                    dialog_title = "Simpan Template AOL Format Excel"
                elif single_idx == 2:
                    default_file_name = f"{base_name} (3 - Template Rekening Tahapan).csv"
                    def_ext = ".csv"
                    file_types = [("CSV File", "*.csv"), ("Semua File", "*.*")]
                    dialog_title = "Simpan Template Rekening Tahapan"
                else:
                    default_file_name = f"{base_name} (4 - Template Rekening Giro).csv"
                    def_ext = ".csv"
                    file_types = [("CSV File", "*.csv"), ("Semua File", "*.*")]
                    dialog_title = "Simpan Template Rekening Giro"

                save_path_file = filedialog.asksaveasfilename(
                    defaultextension=def_ext,
                    filetypes=file_types,
                    title=dialog_title,
                    initialfile=default_file_name
                )
                if not save_path_file:
                    self.update_progress(0)
                    self.log("[INFO] Penyimpanan dibatalkan oleh user.")
                    messagebox.showinfo("Batal", "Penyimpanan file dibatalkan.")
                    return

                aol_json_path = save_path_file
                backup_path = save_path_file
                save_path = save_path_file
                klikbca_path = save_path_file
                result_save_dest = save_path_file
                location_text = f"Berkas hasil konversi BCA berhasil disimpan:\n{save_path_file}\n\n"

            else:
                default_name = f"Hasil Konversi BCA - {base_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
                save_path_raw = filedialog.asksaveasfilename(
                    defaultextension="",
                    filetypes=[("Folder Penyimpanan", "*.*")],
                    title="Simpan Format Accurate BCA (Pilih Lokasi Folder)",
                    initialfile=default_name
                )

                if not save_path_raw:
                    self.update_progress(0)
                    self.log("[INFO] Penyimpanan dibatalkan oleh user.")
                    messagebox.showinfo("Batal", "Penyimpanan file dibatalkan.")
                    return

                parent_dir = os.path.dirname(save_path_raw)
                chosen_basename = os.path.splitext(os.path.basename(save_path_raw))[0]

                target_dir = os.path.join(parent_dir, chosen_basename)
                os.makedirs(target_dir, exist_ok=True)

                aol_json_path = os.path.join(target_dir, f"{chosen_basename} (1 - Template AOL Format JSON).json")
                backup_path = os.path.join(target_dir, f"{chosen_basename} (2 - Template AOL Format Excel (Non-JSON)).xls")
                save_path = os.path.join(target_dir, f"{chosen_basename} (3 - Template Rekening Tahapan).csv")
                klikbca_path = os.path.join(target_dir, f"{chosen_basename} (4 - Template Rekening Giro).csv")
                result_save_dest = target_dir
                location_text = f"Berkas hasil konversi BCA berhasil disimpan ke folder:\n{target_dir}\n\n"

            # 1. Template 1: AOL JSON (Index 0)
            if 0 in chosen_templates:
                bca_mutation_list = []
                for tx in filtered_txs:
                    tgl_clean = format_bca_ddmmyyyy(tx["tanggal"], effective_year)
                    mut = float(tx["mutasi"])
                    amt = mut if tx["tipe"] == "CR" else -mut
                    bca_mutation_list.append({
                        "transDate": tgl_clean,
                        "description": tx["keterangan"],
                        "amount": amt,
                        "balance": float(tx["saldo"])
                    })
                save_aol_json(aol_json_path, rekening, new_saldo_awal, new_saldo_akhir, bca_mutation_list)
                saved_files.append("1. Template AOL Format JSON (.json)  [Paling Direkomendasikan]")
                self.log(f"[OK] BCA Template AOL Format JSON: {os.path.basename(aol_json_path)}")

            # 2. Template 2: AOL Excel Non-JSON (Index 1)
            if 1 in chosen_templates:
                cols = list(OUTPUT_COLUMNS.values())
                final_data = []
                for tx in filtered_txs:
                    tgl_clean = format_bca_ddmmyyyy(tx["tanggal"], effective_year)
                    debet_val = tx['mutasi'] if tx["tipe"] == "DB" else ""
                    kredit_val = tx['mutasi'] if tx["tipe"] == "CR" else ""
                    final_data.append({
                        OUTPUT_COLUMNS['tgl']: tgl_clean,
                        OUTPUT_COLUMNS['desc']: tx["keterangan"],
                        OUTPUT_COLUMNS['deb']: debet_val,
                        OUTPUT_COLUMNS['kre']: kredit_val,
                        OUTPUT_COLUMNS['bal']: tx['saldo']
                    })

                df_final = pd.DataFrame(final_data)
                num_dummy = 7
                if len(df_final) >= num_dummy:
                    df_dummy = df_final.iloc[:num_dummy].copy()
                else:
                    rows = []
                    for i in range(num_dummy):
                        rows.append(df_final.iloc[i % len(df_final)].to_dict())
                    df_dummy = pd.DataFrame(rows)

                row_saldo_awal = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Awal', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: new_saldo_awal}])
                row_total_mutasi = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Total Mutasi', OUTPUT_COLUMNS['deb']: new_total_debet, OUTPUT_COLUMNS['kre']: new_total_kredit, OUTPUT_COLUMNS['bal']: ""}])
                row_saldo_akhir = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Akhir', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: new_saldo_akhir}])

                df_output = pd.concat([df_dummy, row_saldo_awal, df_final, row_total_mutasi, row_saldo_akhir], ignore_index=True)
                save_exact_xls(df_output, backup_path, num_dummy, columns=cols)
                saved_files.append("2. Template AOL Format Excel (Non-JSON) (.xls)")
                self.log(f"[OK] BCA Template AOL Format Excel (Non-JSON): {os.path.basename(backup_path)}")

            # 3. Template 3: Rekening Tahapan CSV (Index 2)
            if 2 in chosen_templates:
                with open(save_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, lineterminator='\n')
                    safe_nama = nama.replace(',', ' ').replace('"', '')
                    writer.writerow(["No. Rekening", "=", f"'{rekening}"])
                    writer.writerow(["Nama", "=", safe_nama])
                    writer.writerow(["Mata Uang", "=", "IDR"])
                    writer.writerow([])
                    writer.writerow(["Tanggal", "Keterangan", "Cabang", "Jumlah", "", "Saldo"])

                    for tx in filtered_txs:
                        safe_ket = tx["keterangan"].replace(',', ' ').replace('"', '')
                        tgl_raw = tx["tanggal"].replace("'", "").strip()
                        parts = tgl_raw.split('/')
                        tgl_fmt1 = f"'{parts[0]:0>2}/{parts[1]:0>2}" if len(parts) >= 2 else f"'{tgl_raw}"
                        writer.writerow([
                            tgl_fmt1,
                            safe_ket,
                            tx["cabang"],
                            f"{tx['mutasi']:.2f}",
                            tx["tipe"],
                            f"{tx['saldo']:.2f}"
                        ])

                    writer.writerow(["Saldo Awal", "=", f"{new_saldo_awal:.2f}"])
                    writer.writerow(["Kredit", "=", f"{new_total_kredit:.2f}"])
                    writer.writerow(["Debet", "=", f"{new_total_debet:.2f}"])
                    writer.writerow(["Saldo Akhir", "=", f"{new_saldo_akhir:.2f}"])
                    writer.writerow([])
                saved_files.append("3. Template Rekening Tahapan (.csv)")
                self.log(f"[OK] BCA Template Rekening Tahapan: {os.path.basename(save_path)}")

            # 4. Template 4: Rekening Giro CSV (Index 3)
            if 3 in chosen_templates:
                with open(klikbca_path, 'w', newline='', encoding='utf-8') as f:
                    f.write('"Informasi Rekening - Mutasi Rekening"," "," "," "," ",\n\n')
                    writer3 = csv.writer(f, lineterminator='\n', quoting=csv.QUOTE_ALL)
                    safe_nama = nama.replace(',', ' ').replace('"', '')
                    periode_str = f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"

                    writer3.writerow([f"No. rekening : {rekening}"])
                    writer3.writerow([f"Nama : {safe_nama}"])
                    writer3.writerow([f"Periode : {periode_str}"])
                    writer3.writerow(["Kode Mata Uang : Rp"])
                    writer3.writerow(["Tanggal Transaksi", "Keterangan", "Cabang", "Jumlah", "Saldo"])

                    count_cr = 0
                    count_db = 0
                    for tx in filtered_txs:
                        tgl_clean = format_bca_ddmmyyyy(tx["tanggal"], effective_year)
                        cabang_clean = tx["cabang"].replace("'", "")
                        jumlah_str = f"{tx['mutasi']:,.2f} {tx['tipe']}"
                        saldo_str = f"{tx['saldo']:,.2f}"
                        if tx["tipe"] == "CR":
                            count_cr += 1
                        else:
                            count_db += 1
                        writer3.writerow([tgl_clean, tx["keterangan"], cabang_clean, jumlah_str, saldo_str])

                    writer3.writerow([f"Saldo Awal : {new_saldo_awal:,.2f}"])
                    writer3.writerow([f"Mutasi Debet : {new_total_debet:,.2f}", str(count_db)])
                    writer3.writerow([f"Mutasi Kredit : {new_total_kredit:,.2f}", str(count_cr)])
                    writer3.writerow([f"Saldo Akhir : {new_saldo_akhir:,.2f}"])
                    f.write('\n')
                saved_files.append("4. Template Rekening Giro (myBCA / KlikBCA) (.csv)")
                self.log(f"[OK] BCA Template Rekening Giro: {os.path.basename(klikbca_path)}")

            self.update_progress(1.0)
            files_list_str = "\n".join(saved_files)
            if date_from == date_to:
                range_info = f"Tanggal Mutasi: {date_from.strftime('%d/%m/%Y')} (1 Hari)\nTotal Mutasi: {len(filtered_txs)} baris\nSaldo Awal: Rp {new_saldo_awal:,.2f} | Saldo Akhir: Rp {new_saldo_akhir:,.2f}"
            else:
                range_info = f"Rentang Tanggal: {date_from.strftime('%d/%m/%Y')} s/d {date_to.strftime('%d/%m/%Y')}\nTotal Mutasi: {len(filtered_txs)} baris\nSaldo Awal: Rp {new_saldo_awal:,.2f} | Saldo Akhir: Rp {new_saldo_akhir:,.2f}"
            audit_table = transactions[0].get("_audit_table", "") if transactions else ""

            msg = (
                f"{location_text}"
                f"Template Terpilih ({len(saved_files)} berkas):\n{files_list_str}\n\n"
                f"{range_info}\n\n"
                f"Saran: Gunakan Template 1 (Format JSON AOL) untuk impor ke Accurate Online karena format JSON resmi Accurate ini paling stabil, baku, dan jarang terpengaruh perubahan tata letak dari pihak bank."
            )
            if len(filtered_txs) < len(transactions):
                msg += (
                    f"\n\n[REKONSILIASI RENTANG TERPILIH]\n"
                    f"Saldo Awal   : Rp {new_saldo_awal:,.2f}\n"
                    f"Total Debet  : Rp {new_total_debet:,.2f}\n"
                    f"Total Kredit : Rp {new_total_kredit:,.2f}\n"
                    f"Saldo Akhir  : Rp {new_saldo_akhir:,.2f}\n"
                    f"Status       : [Cocok / Klop Rp 0,00]"
                )
            elif audit_table:
                msg += f"\n\n{audit_table}"
            self.show_copyable_dialog("Selesai BCA", msg, path_to_copy=result_save_dest)

        except Exception as e:
            self.reset_ui_state(is_error=True, error_msg=f"Gagal simpan BCA File: {str(e)}")
        finally:
            self.btn_process.configure(state="normal", text="PROSES DATA")
