import os
import sys
import ctypes
import threading
import datetime
import csv
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from utils.config_manager import load_config, save_config
from utils.helpers import get_windows_theme, resource_path
from utils.file_exporter import save_exact_xls, save_invalid_dates
from processors.panin_processor import process_panin, OUTPUT_COLUMNS
from processors.bca_processor import process_bca

class UniversalAccurateConverter:
    def __init__(self, root):
        self.root = root
        version_str = "4.4.0"
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
        except:
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
            except:
                pass

    def show_tutorial(self):
        config = load_config()
        if not config.get("show_tutorial", True):
            return 

        tut_win = ctk.CTkToplevel(self.root)
        tut_win.title("Panduan")
        
        if os.path.exists(self.icon_path):
            try: tut_win.after(200, lambda: tut_win.iconbitmap(self.icon_path))
            except: pass

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
        
        self.bank_var = ctk.StringVar(value="Panin")
        self.bank_menu = ctk.CTkOptionMenu(controls_frame, values=["Panin", "BCA", "Mandiri"],
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
                                       placeholder_text="Pilih file mutasi (Panin: .xls/.xlsx/.csv/.pdf | BCA: .pdf/.csv)...", 
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
        chk_typo = ctk.CTkCheckBox(options_container, text="Rapikan deskripsi (Khusus Panin)", 
                                   font=ctk.CTkFont(family="Inter", size=12),
                                   variable=self.use_regex_var, corner_radius=6,
                                   fg_color=("#3B82F6", "#3B82F6"), border_color=("#CBD5E1", "#4A5568"),
                                   text_color=("#4F566B", "#A0AABF"))
        chk_typo.pack(anchor="w")
        
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
                                       font=ctk.CTkFont(family="Consolas", size=12))
        self.log_area.pack(fill="both", expand=True, padx=35, pady=(5, 25))
        self.log_area.configure(state="disabled")
        
        self.change_bank("Panin")

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

    def show_copyable_dialog(self, title, message, path_to_copy=""):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry("550x280")
        dialog.transient(self.root)
        dialog.grab_set()

        if os.path.exists(self.icon_path):
            try: dialog.after(200, lambda: dialog.iconbitmap(self.icon_path))
            except: pass

        frame = ctk.CTkFrame(dialog, corner_radius=15)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=(0, 10))

        def copy_to_clipboard():
            self.root.clipboard_clear()
            self.root.clipboard_append(path_to_copy if path_to_copy else message)
            self.root.update()
            btn_copy.configure(text="Tersalin!")
            dialog.after(2000, lambda: btn_copy.configure(text="Copy Lokasi"))

        btn_copy = ctk.CTkButton(btn_frame, text="Copy Lokasi", width=100, 
                                 command=copy_to_clipboard, fg_color="#3498db", hover_color="#2980b9")
        btn_copy.pack(side="left", padx=10)

        btn_ok = ctk.CTkButton(btn_frame, text="OK", width=100, command=dialog.destroy)
        btn_ok.pack(side="left", padx=10)

        txt_area = ctk.CTkTextbox(frame, wrap="word", font=ctk.CTkFont(size=13))
        txt_area.pack(side="top", padx=10, pady=(10, 10), fill="both", expand=True)
        txt_area.insert("0.0", message)
        txt_area.configure(state="disabled")

    def confirm_process(self):
        filepath = self.path_var.get().strip()
        
        if not filepath:
            messagebox.showwarning("Peringatan", "Silakan pilih file mutasi terlebih dahulu.")
            self.log("[INFO] Proses dibatalkan: File belum dipilih.")
            return
        
        filename = os.path.basename(filepath)
        confirm = messagebox.askyesno("Konfirmasi", f"Mulai proses konversi untuk file ini?\n\nFile: {filename}")
        
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
            if not (filepath.lower().endswith('.pdf') or filepath.lower().endswith('.csv')):
                handle_error("Format file tidak valid. Mutasi BCA harus dalam format PDF atau CSV.")
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
            default_name = f"{base_name} (Template Excel Formatter).xls"
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
                    
                    if invalid_dates_data:
                        error_file = save_invalid_dates(invalid_dates_data, filepath, log_callback=self.log)
                        msg = f"File berhasil disimpan!\nLokasi:\n{save_path}\n\nValid: {len(df_output) - 3 - num_dummy} baris\nDummy: {num_dummy} baris\nInvalid Date: {len(invalid_dates_data)} baris (diabaikan)"
                        if error_file:
                            msg += f"\nFile error saved: {os.path.basename(error_file)}"
                        self.show_copyable_dialog("Selesai dengan Peringatan", msg, path_to_copy=save_path)
                    else:
                        msg = f"File berhasil disimpan!\nLokasi:\n{save_path}\n\nValid: {len(df_output) - 3 - num_dummy} baris\nDummy: {num_dummy} baris"
                        self.show_copyable_dialog("Selesai", msg, path_to_copy=save_path)
                else:
                    raise Exception("Export failed.")
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
                f"Ekstraksi {len(transactions)} transaksi BCA berhasil!\n\nSistem akan menyimpan TIGA file (Rekening Tahapan, Excel Formatter, Rekening Giro) ke dalam SATU FOLDER khusus agar rapi.\n\nSilakan tentukan nama folder penyimpanan."
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
                
                # Definisikan 3 path file baru
                save_path = os.path.join(target_dir, f"{chosen_basename} (1 - Template Rekening Tahapan).csv")
                backup_path = os.path.join(target_dir, f"{chosen_basename} (2 - Template Excel Formatter).xls")
                klikbca_path = os.path.join(target_dir, f"{chosen_basename} (3 - Template Rekening Giro).csv")
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
                        writer.writerow([
                            tx["tanggal"],
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

                # === BACKUP: Save XLS ===
                import pandas as pd
                cols = list(OUTPUT_COLUMNS.values())
                final_data = []
                
                for tx in transactions:
                    tgl_clean = tx["tanggal"].replace("'", "") + "/" + str(datetime.datetime.now().year) if len(tx["tanggal"]) > 1 else ""
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
                self.log(f"Menambahkan {num_dummy} baris kosong (Dummy Format Accurate).")

                row_saldo_awal = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Awal', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: saldo_awal}])
                row_total_mutasi = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Total Mutasi', OUTPUT_COLUMNS['deb']: total_debet, OUTPUT_COLUMNS['kre']: total_kredit, OUTPUT_COLUMNS['bal']: ""}])
                row_saldo_akhir = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Akhir', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: saldo_akhir}])
                
                df_output = pd.concat([df_dummy, row_saldo_awal, df_final, row_total_mutasi, row_saldo_akhir], ignore_index=True)

                # backup_path sudah didefinisikan di atas (sebagai Excel Formatter)
                save_exact_xls(df_output, backup_path, num_dummy, columns=cols)
                
                # === FORMAT 3: KlikBCA CSV ===
                # klikbca_path sudah didefinisikan di atas
                
                with open(klikbca_path, 'w', newline='', encoding='utf-8') as f:
                    # Baris 1: Header judul (MANUAL write karena field ke-6 kosong tanpa kutip)
                    f.write('"Informasi Rekening - Mutasi Rekening"," "," "," "," ",\n')
                    
                    # Baris 2: Baris kosong
                    f.write('\n')
                    
                    # Baris 3-6: Metadata (single-cell strings)
                    writer3 = csv.writer(f, lineterminator='\n', quoting=csv.QUOTE_ALL)
                    
                    # Hitung periode: gunakan metadata asli dari CSV jika tersedia
                    periode_from_meta = transactions[0].get("_periode_raw", "") if transactions else ""
                    year = str(datetime.datetime.now().year)
                    
                    if periode_from_meta:
                        # Dari CSV input: gunakan periode asli
                        periode_str = periode_from_meta
                    else:
                        # Dari PDF input: hitung dari tanggal transaksi
                        dates = []
                        for tx in transactions:
                            raw = tx["tanggal"].replace("'", "")  # "'05/12" -> "05/12"
                            dates.append(raw)
                        if dates:
                            full_dates = [d + "/" + year for d in dates]
                            tgl_awal = full_dates[0]
                            tgl_akhir = full_dates[-1]
                        else:
                            tgl_awal = f"01/01/{year}"
                            tgl_akhir = f"31/12/{year}"
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
                        tgl_clean = tx["tanggal"].replace("'", "") + "/" + year
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

                self.update_progress(1.0)
                self.log(f"[OK] BCA CSV Saved: {os.path.basename(save_path)}")
                self.log(f"[OK] BCA Excel Formatter Saved: {os.path.basename(backup_path)}")
                self.log(f"[OK] BCA KlikBCA CSV Saved: {os.path.basename(klikbca_path)}")
                self.show_copyable_dialog("Selesai BCA", f"Tiga File BCA berhasil disimpan dalam folder:\n{target_dir}\n\n1. Template Rekening Tahapan\n2. Template Excel Formatter\n3. Template Rekening Giro\n\nTotal Data: {len(transactions)} baris", path_to_copy=target_dir)
            else:
                self.update_progress(0)
                self.log("[INFO] Penyimpanan dibatalkan oleh user.")
                messagebox.showinfo("Batal", "Penyimpanan file dibatalkan.")
        except Exception as e:
            self.reset_ui_state(is_error=True, error_msg=f"Gagal simpan BCA File: {str(e)}")
        finally:
            self.btn_process.configure(state="normal", text="PROSES DATA")
