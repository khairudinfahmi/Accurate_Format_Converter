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
        version_str = "5.1.0"
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
        
    def finish_saving_panin(self, df_output, invalid_dates_data, num_dummy, filepath):
        try:
            messagebox.showinfo(
                "Ekstraksi Berhasil", 
                f"Ekstraksi {len(df_output) - 3 - num_dummy} data transaksi berhasil.\n\nSilakan pilih lokasi penyimpanan file konversi."
            )

            base_name = os.path.splitext(os.path.basename(filepath))[0]
            base_name = re.sub(r'^(?:panin[\s\_-]*)+', '', base_name, flags=re.IGNORECASE)
            default_name = f"{base_name} (Template AOL Format Excel (Non-JSON)).xls"
            save_path = filedialog.asksaveasfilename(
                defaultextension=".xls", 
                filetypes=[("Excel 97-2003", "*.xls")], 
                title="Simpan Format Accurate",
                initialfile=default_name
            )
            
            if save_path:
                cols = list(OUTPUT_COLUMNS.values())
                success = save_exact_xls(df_output, save_path, num_dummy, columns=cols)
                if success:
                    self.update_progress(1.0)
                    self.log(f"[OK] Saved: {os.path.basename(save_path)}")
                    
                    # === TAMBAHAN: Simpan format JSON AOL ===
                    json_base = os.path.splitext(save_path)[0]
                    if "(Template AOL Format Excel (Non-JSON))" in json_base:
                        json_path = json_base.replace("(Template AOL Format Excel (Non-JSON))", "(Template AOL Format JSON)") + ".json"
                    else:
                        json_path = f"{json_base} (Template AOL Format JSON).json"

                    # Ekstrak nomor rekening fallback Panin
                    rek_panin = getattr(df_output, 'attrs', {}).get("account_number")
                    if not rek_panin:
                        rek_match = re.search(r'\b(\d{8,16})\b', os.path.basename(filepath))
                        rek_panin = rek_match.group(1) if rek_match else "0000000000"

                    saldo_awal_panin = float(df_output.iloc[num_dummy][OUTPUT_COLUMNS['bal']])
                    saldo_akhir_panin = float(df_output.iloc[-1][OUTPUT_COLUMNS['bal']])

                    df_tx = df_output.iloc[num_dummy + 1 : len(df_output) - 2]
                    panin_mutation_list = []
                    for _, r in df_tx.iterrows():
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

                    try:
                        save_aol_json(json_path, rek_panin, saldo_awal_panin, saldo_akhir_panin, panin_mutation_list)
                        self.log(f"[OK] Panin Template AOL Format JSON Saved: {os.path.basename(json_path)}")
                    except Exception as json_err:
                        self.log(f"[WARN] Gagal simpan JSON Panin: {json_err}")

                    audit_table = getattr(df_output, 'attrs', {}).get("audit_table", "")
                    rekomendasi_txt = "\nSaran: Gunakan Template 1 (Format JSON AOL) untuk impor ke Accurate Online karena format JSON resmi ini paling stabil dan tidak terpengaruh perubahan format dari pihak bank."
                    if invalid_dates_data:
                        error_file = save_invalid_dates(invalid_dates_data, filepath, log_callback=self.log)
                        msg = f"Dua berkas berhasil disimpan:\n1. Template AOL Format JSON: {os.path.basename(json_path)} [Paling Direkomendasikan]\n2. Template AOL Format Excel (Non-JSON): {os.path.basename(save_path)}\n\nValid: {len(df_tx)} baris | Dummy: {num_dummy} baris\nInvalid Date: {len(invalid_dates_data)} baris (diabaikan){rekomendasi_txt}"
                        if error_file:
                            msg += f"\nFile error saved: {os.path.basename(error_file)}"
                        if audit_table:
                            msg += f"\n\n{audit_table}"
                        self.show_copyable_dialog("Selesai dengan Peringatan", msg, path_to_copy=save_path)
                    else:
                        msg = f"Dua berkas berhasil disimpan:\n1. Template AOL Format JSON: {os.path.basename(json_path)} [Paling Direkomendasikan]\n2. Template AOL Format Excel (Non-JSON): {os.path.basename(save_path)}\n\nValid: {len(df_tx)} baris | Dummy: {num_dummy} baris{rekomendasi_txt}"
                        if audit_table:
                            msg += f"\n\n{audit_table}"
                        self.show_copyable_dialog("Selesai", msg, path_to_copy=save_path)
                else:
                    raise Exception("Penyimpanan file Excel format Accurate gagal.")
            else:
                self.update_progress(0)
                self.log("[INFO] Penyimpanan dibatalkan oleh user.")
                messagebox.showinfo("Batal", "Penyimpanan file dibatalkan.")
        except Exception as e:
            self.reset_ui_state(is_error=True, error_msg=str(e))
        finally:
            self.btn_process.configure(state="normal", text="PROSES DATA")

    def finish_saving_bca_csv(self, transactions, rekening, nama, saldo_awal, saldo_akhir, filepath):
        try:
            messagebox.showinfo(
                "Ekstraksi BCA Berhasil", 
                f"Ekstraksi {len(transactions)} data transaksi BCA berhasil.\n\nSistem akan menyimpan 4 berkas hasil konversi ke dalam satu folder khusus.\n\nSilakan tentukan nama dan lokasi folder penyimpanan."
            )
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            base_name = re.sub(r'^(?:bca[\s\_-]*)+', '', base_name, flags=re.IGNORECASE)
            default_name = f"BCA_{base_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
            
            save_path_raw = filedialog.asksaveasfilename(
                defaultextension="", 
                filetypes=[("Folder Penyimpanan", "*.*")], 
                title="Simpan Format Accurate BCA (Akan dibuatkan Folder)",
                initialfile=default_name
            )
            
            if save_path_raw:
                parent_dir = os.path.dirname(save_path_raw)
                chosen_basename = os.path.splitext(os.path.basename(save_path_raw))[0]
                
                # Buat folder khusus
                folder_name = f"Hasil Konversi BCA - {chosen_basename}"
                target_dir = os.path.join(parent_dir, folder_name)
                os.makedirs(target_dir, exist_ok=True)
                
                # Definisikan 4 path file baru dengan urutan resmi
                aol_json_path = os.path.join(target_dir, f"{chosen_basename} (1 - Template AOL Format JSON).json")
                backup_path = os.path.join(target_dir, f"{chosen_basename} (2 - Template AOL Format Excel (Non-JSON)).xls")
                save_path = os.path.join(target_dir, f"{chosen_basename} (3 - Template Rekening Tahapan).csv")
                klikbca_path = os.path.join(target_dir, f"{chosen_basename} (4 - Template Rekening Giro).csv")
                # === PRIMARY: Save CSV (for Accurate import) ===
                with open(save_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, lineterminator='\n')
                    safe_nama = nama.replace(',', ' ').replace('"', '')
                    writer.writerow(["No. Rekening", "=", f"'{rekening}"])
                    writer.writerow(["Nama", "=", safe_nama])
                    writer.writerow(["Mata Uang", "=", "IDR"])
                    writer.writerow([])
                    writer.writerow(["Tanggal", "Keterangan", "Cabang", "Jumlah", "", "Saldo"])
                    
                    total_kredit = 0.0
                    total_debet = 0.0
                    for tx in transactions:
                        if tx["tipe"] == "CR": total_kredit += tx["mutasi"]
                        else: total_debet += tx["mutasi"]
                        
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
                    
                    writer.writerow(["Saldo Awal", "=", f"{saldo_awal:.2f}"])
                    writer.writerow(["Kredit", "=", f"{total_kredit:.2f}"])
                    writer.writerow(["Debet", "=", f"{total_debet:.2f}"])
                    writer.writerow(["Saldo Akhir", "=", f"{saldo_akhir:.2f}"])
                    writer.writerow([])

                # Hitung tahun efektif dari metadata dokumen jika tersedia (hindari hardcode tahun sekarang)
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

                # === BACKUP: Save XLS ===
                import pandas as pd
                cols = list(OUTPUT_COLUMNS.values())
                final_data = []
                
                for tx in transactions:
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
                # Loop ulang data transaksi sampai genap 7 baris
                if len(df_final) >= num_dummy:
                    df_dummy = df_final.iloc[:num_dummy].copy()
                else:
                    rows = []
                    for i in range(num_dummy):
                        rows.append(df_final.iloc[i % len(df_final)].to_dict())
                    df_dummy = pd.DataFrame(rows)
                self.log(f"Menambahkan {num_dummy} baris dummy (Looping Transaksi Format Accurate).")

                row_saldo_awal = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Awal', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: saldo_awal}])
                row_total_mutasi = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Total Mutasi', OUTPUT_COLUMNS['deb']: total_debet, OUTPUT_COLUMNS['kre']: total_kredit, OUTPUT_COLUMNS['bal']: ""}])
                row_saldo_akhir = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Akhir', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: saldo_akhir}])
                
                df_output = pd.concat([df_dummy, row_saldo_awal, df_final, row_total_mutasi, row_saldo_akhir], ignore_index=True)

                # backup_path sudah didefinisikan di atas (sebagai Template AOL Format Excel (Non-JSON))
                save_exact_xls(df_output, backup_path, num_dummy, columns=cols)
                
                # === FORMAT 4 (File CSV): CSV Rekening Giro (myBCA / KlikBCA) ===
                # klikbca_path sudah didefinisikan di atas
                
                with open(klikbca_path, 'w', newline='', encoding='utf-8') as f:
                    # Baris 1: Header judul (MANUAL write karena field ke-6 kosong tanpa kutip)
                    f.write('"Informasi Rekening - Mutasi Rekening"," "," "," "," ",\n')
                    
                    # Baris 2: Baris kosong
                    f.write('\n')
                    
                    # Baris 3-6: Metadata (single-cell strings)
                    writer3 = csv.writer(f, lineterminator='\n', quoting=csv.QUOTE_ALL)
                    
                    if periode_from_meta:
                        # Dari dokumen input: gunakan periode asli
                        periode_str = periode_from_meta
                    else:
                        # Hitung dari tanggal transaksi dengan tahun efektif
                        dates = []
                        for tx in transactions:
                            raw = tx["tanggal"].replace("'", "")
                            dates.append(raw)
                        if dates:
                            full_dates = [format_bca_ddmmyyyy(d, effective_year) for d in dates]
                            tgl_awal = full_dates[0]
                            tgl_akhir = full_dates[-1]
                        else:
                            tgl_awal = f"01/01/{effective_year}"
                            tgl_akhir = f"31/12/{effective_year}"
                        periode_str = f"{tgl_awal} - {tgl_akhir}"
                    
                    writer3.writerow([f"No. rekening : {rekening}"])
                    writer3.writerow([f"Nama : {safe_nama}"])
                    writer3.writerow([f"Periode : {periode_str}"])
                    writer3.writerow(["Kode Mata Uang : Rp"])
                    
                    # Baris 7: Header tabel
                    writer3.writerow(["Tanggal Transaksi", "Keterangan", "Cabang", "Jumlah", "Saldo"])
                    
                    # Baris 8+: Data transaksi
                    count_cr = 0
                    count_db = 0
                    for tx in transactions:
                        tgl_clean = format_bca_ddmmyyyy(tx["tanggal"], effective_year)
                        cabang_clean = tx["cabang"].replace("'", "")
                        jumlah_str = f"{tx['mutasi']:,.2f} {tx['tipe']}"
                        saldo_str = f"{tx['saldo']:,.2f}"
                        
                        if tx["tipe"] == "CR":
                            count_cr += 1
                        else:
                            count_db += 1
                        
                        writer3.writerow([tgl_clean, tx["keterangan"], cabang_clean, jumlah_str, saldo_str])
                    
                    # Footer
                    writer3.writerow([f"Saldo Awal : {saldo_awal:,.2f}"])
                    writer3.writerow([f"Mutasi Debet : {total_debet:,.2f}", str(count_db)])
                    writer3.writerow([f"Mutasi Kredit : {total_kredit:,.2f}", str(count_cr)])
                    writer3.writerow([f"Saldo Akhir : {saldo_akhir:,.2f}"])
                    f.write('\n')  # 1 baris kosong penutup (writerow sudah menambahkan \n)

                # === FORMAT 4: Accurate Online (AOL) JSON ===
                bca_mutation_list = []
                for tx in transactions:
                    tgl_clean = format_bca_ddmmyyyy(tx["tanggal"], effective_year)
                    mut = float(tx["mutasi"])
                    amt = mut if tx["tipe"] == "CR" else -mut
                    bca_mutation_list.append({
                        "transDate": tgl_clean,
                        "description": tx["keterangan"],
                        "amount": amt,
                        "balance": float(tx["saldo"])
                    })
                save_aol_json(aol_json_path, rekening, saldo_awal, saldo_akhir, bca_mutation_list)

                self.update_progress(1.0)
                self.log(f"[OK] BCA Template AOL Format JSON: {os.path.basename(aol_json_path)}")
                self.log(f"[OK] BCA Template AOL Format Excel (Non-JSON): {os.path.basename(backup_path)}")
                self.log(f"[OK] BCA Template Rekening Tahapan: {os.path.basename(save_path)}")
                self.log(f"[OK] BCA Template Rekening Giro: {os.path.basename(klikbca_path)}")
                audit_table = transactions[0].get("_audit_table", "") if transactions else ""
                msg = (
                    f"Empat berkas hasil konversi BCA berhasil disimpan dalam folder:\n{target_dir}\n\n"
                    f"1. Template AOL Format JSON (.json)  [Paling Direkomendasikan]\n"
                    f"2. Template AOL Format Excel (Non-JSON) (.xls)\n"
                    f"3. Template Rekening Tahapan (.csv)\n"
                    f"4. Template Rekening Giro (myBCA / KlikBCA) (.csv)\n\n"
                    f"Total Data: {len(transactions)} baris mutasi\n\n"
                    f"Saran: Gunakan Template 1 (Format JSON AOL) untuk impor ke Accurate Online karena format JSON resmi Accurate ini paling stabil, baku, dan jarang terpengaruh perubahan tata letak dari pihak bank."
                )
                if audit_table:
                    msg += f"\n\n{audit_table}"
                self.show_copyable_dialog("Selesai BCA", msg, path_to_copy=target_dir)
            else:
                self.update_progress(0)
                self.log("[INFO] Penyimpanan dibatalkan oleh user.")
                messagebox.showinfo("Batal", "Penyimpanan file dibatalkan.")
        except Exception as e:
            self.reset_ui_state(is_error=True, error_msg=f"Gagal simpan BCA File: {str(e)}")
        finally:
            self.btn_process.configure(state="normal", text="PROSES DATA")
