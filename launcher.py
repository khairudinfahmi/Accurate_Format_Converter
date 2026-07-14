import os
import sys
import json
import urllib.request
import zipfile
import threading
import subprocess
import shutil
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import tempfile

# ==============================================================
# KONFIGURASI PENTING
# ==============================================================
# URL RAW ke file update_info.json di GitHub Gist.
UPDATE_INFO_URL = "https://gist.githubusercontent.com/khairudinfahmi/7e47f4d086fd768f655774d1489bb776/raw/update_info.json"
MAIN_APP_EXE = "Accurate_Format_Converter.exe"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def get_local_version():
    try:
        # Mendapatkan path versi lokal dari direktori eksekusi aplikasi
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        v_path = os.path.join(exe_dir, "version.txt")
        if os.path.exists(v_path):
            with open(v_path, "r") as f:
                return f.read().strip()
    except Exception as e:
        print(e)
    return "0.0.0" # Jika file tidak ditemukan, asumsikan versi terendah

def parse_version(v_str):
    # Konversi string versi menjadi tuple untuk komparasi
    return tuple(map(int, (v_str.split("."))))

class LauncherApp:
    def __init__(self, root):
        self.root = root        
        self.local_version = get_local_version()
        self.root.title(f"Accurate Format Converter v{self.local_version} - Launcher")
        self.root.geometry("400x160")
        self.root.resizable(False, False)
        
        # Pusatkan posisi jendela pada layar
        self.root.eval('tk::PlaceWindow . center')
        
        icon_path = resource_path("assets/rensa_logo.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(default=icon_path)
            except Exception:
                pass
        
        self.status_var = tk.StringVar(value="Mengecek server untuk pembaruan...")
        self.label = ttk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 10))
        self.label.pack(pady=(25, 10))
        
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=320, mode="determinate")
        self.progress.pack(pady=10)
        
        self.exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        # Memulai pengecekan di thread terpisah agar UI tetap responsif
        threading.Thread(target=self.run_update_logic, daemon=True).start()

    def update_ui(self, msg, progress_val=None):
        def _update():
            self.status_var.set(msg)
            if progress_val is not None:
                self.progress["value"] = progress_val
        self.root.after(0, _update)

    def launch_main_app(self):
        target_exe = os.path.join(self.exe_dir, MAIN_APP_EXE)
        if os.path.exists(target_exe):
            # Clean PyInstaller environment variables for the child process to prevent initialization crash
            child_env = os.environ.copy()
            for key in list(child_env.keys()):
                if key.startswith("_MEIPASS") or key.startswith("_PYI_"):
                    child_env.pop(key, None)
            subprocess.Popen([target_exe], cwd=self.exe_dir, env=child_env)
        else:
            messagebox.showerror("Error", f"Aplikasi utama ({MAIN_APP_EXE}) tidak ditemukan di folder ini!")
        self.root.after(0, self.root.destroy)

    def run_update_logic(self):
        try:
            # 1. Periksa versi pada server
            req = urllib.request.Request(UPDATE_INFO_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
            server_version = data.get("latest_version", "0.0.0")
            download_url = data.get("download_url", "")
            release_notes = data.get("release_notes", "")
            
            if parse_version(server_version) > parse_version(self.local_version):
                # Pembaruan tersedia
                ans = messagebox.askyesno(
                    "Pembaruan Tersedia",
                    f"Versi terbaru ditemukan!\nVersi Anda: {self.local_version}\nVersi Baru: {server_version}\n\nFitur Baru:\n{release_notes}\n\nApakah Anda ingin memperbarui sekarang?"
                )
                if ans:
                    self.perform_update(download_url)
                else:
                    self.launch_main_app()
            else:
                self.update_ui("Aplikasi sudah menggunakan versi terbaru. Menjalankan aplikasi...", 100)
                self.root.after(1000, self.launch_main_app)
                
        except Exception as e:
            # Jalankan aplikasi secara luring jika gagal memeriksa pembaruan
            print(f"Update check failed: {e}")
            self.update_ui("Gagal memeriksa pembaruan. Menjalankan aplikasi secara luring...", 100)
            self.root.after(1000, self.launch_main_app)

    def perform_update(self, url):
        try:
            self.update_ui("Mengunduh pembaruan... (Mohon tunggu)", 0)
            temp_dir = tempfile.gettempdir()
            
            # Hapus whitespace tersembunyi pada URL
            url = url.strip()
            
            is_exe_installer = url.lower().endswith(".exe")
            download_dest = os.path.join(temp_dir, "Update_Installer.exe" if is_exe_installer else "update_temp.zip")
            
            if os.path.exists(download_dest):
                try: os.remove(download_dest)
                except: pass
            
            # Download file
            import ssl
            context = ssl._create_unverified_context()
            # Gunakan header yang lebih lengkap
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/octet-stream, */*'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30, context=context) as response:
                total_size = int(response.info().get('Content-Length', -1))
                downloaded = 0
                block_size = 1024 * 8
                
                with open(download_dest, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        downloaded += len(buffer)
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            self.update_ui(f"Mengunduh pembaruan... {percent}%", percent)

            if is_exe_installer:
                self.update_ui("Memasang pembaruan secara otomatis...", 100)
                
                # Clear PyInstaller environment variables before spawning installer
                # to prevent the installer and its child launcher from inheriting them
                for key in list(os.environ.keys()):
                    if key.startswith("_MEIPASS") or key.startswith("_PYI_"):
                        os.environ.pop(key, None)
                
                import ctypes
                installer_args = f'/VERYSILENT /SUPPRESSMSGBOXES /FORCECLOSEAPPLICATIONS /NORESTART /DIR="{self.exe_dir}"'
                ctypes.windll.shell32.ShellExecuteW(
                    None, "open", download_dest, 
                    installer_args, 
                    "", 1
                )
                self.root.after(0, self.root.destroy)
                return

            # ============== JIKA FORMAT PEMBARUAN ADALAH ARSIP (ZIP/DLL) =================
            zip_path = download_dest
            self.update_ui("Mengekstrak pembaruan...", 100)
            self.progress.configure(mode="indeterminate")
            self.progress.start(15)

            # Mengekstrak arsip ke direktori sementara
            temp_extract_dir = os.path.join(temp_dir, "update_extracted_temp")
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
            os.makedirs(temp_extract_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            self.progress.stop()
            self.progress.configure(mode="determinate", value=100)
            self.update_ui("Pembaruan siap dipasang. Meminta akses Administrator...", 100)
            
            # Membuat skrip PowerShell untuk menimpa file dengan hak akses Administrator (UAC)
            ps_script_path = os.path.join(temp_dir, "install_update.ps1")
            
            # Skrip PowerShell dengan penanganan galat dan terminasi paksa
            ps_code = f"""
Add-Type -AssemblyName PresentationFramework
$logPath = "$env:TEMP\\update_debug.log"
"Mulai proses update..." | Out-File $logPath

try {{
    "Mematikan aplikasi lama..." | Out-File $logPath -Append
    Stop-Process -Name "Accurate_Format_Converter", "Launcher" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    "Menimpa file..." | Out-File $logPath -Append
    Copy-Item -Path "{temp_extract_dir}\\*" -Destination "{self.exe_dir}" -Recurse -Force -ErrorAction Stop

    "Membersihkan temp..." | Out-File $logPath -Append
    Remove-Item -Path "{temp_extract_dir}" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "{zip_path}" -Force -ErrorAction SilentlyContinue

    [System.Windows.MessageBox]::Show("Pembaruan Berhasil Dipasang! Aplikasi akan dimuat ulang.", "Update Sukses", 0, [System.Windows.MessageBoxImage]::Information)

    "Menjalankan aplikasi baru..." | Out-File $logPath -Append
    Start-Process -FilePath "{os.path.join(self.exe_dir, MAIN_APP_EXE)}"
}} catch {{
    $err = $_.Exception.Message
    "ERROR: $err" | Out-File $logPath -Append
    [System.Windows.MessageBox]::Show("Gagal Replace File! Error: $err", "Update Gagal", 0, [System.Windows.MessageBoxImage]::Error)
}} finally {{
    Remove-Item -Path $PSCommandPath -Force -ErrorAction SilentlyContinue
}}
"""
            with open(ps_script_path, "w", encoding="utf-8") as f:
                f.write(ps_code)

            messagebox.showinfo("Pembaruan Diunduh", "Pembaruan berhasil diunduh! Aplikasi akan meminta izin Administrator untuk memasang file.")

            # Clear PyInstaller environment variables before spawning PowerShell
            for key in list(os.environ.keys()):
                if key.startswith("_MEIPASS") or key.startswith("_PYI_"):
                    os.environ.pop(key, None)

            # Mengeksekusi PowerShell dengan hak akses Administrator via ctypes API (UAC Trigger)
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", f'-ExecutionPolicy Bypass -WindowStyle Hidden -File "{ps_script_path}"', "", 0)
            
            self.root.after(0, self.root.destroy) # Menutup instans launcher saat ini untuk menghindari konflik

        except Exception as e:
            self.progress.stop()
            messagebox.showerror("Pembaruan Gagal", f"Terjadi kesalahan saat mengunduh/mengekstrak pembaruan:\\n{str(e)}\\n\\nAplikasi akan berjalan dengan versi saat ini.")
            try:
                if 'zip_path' in locals() and os.path.exists(zip_path):
                    os.remove(zip_path)
            except: pass
            self.launch_main_app()

if __name__ == "__main__":
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()
