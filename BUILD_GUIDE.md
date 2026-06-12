# Panduan Build dan Rilis - Accurate Format Converter

Dokumen ini berisi langkah-langkah lengkap untuk melakukan build aplikasi, penandatanganan digital (Digital Signing), hingga pembuatan installer. Ikuti urutan ini setiap kali ingin merilis versi terbaru.

---

## 1. Persiapan Awal
Sebelum mulai, pastikan hal berikut sudah dilakukan:
1. Update Kode: Pastikan semua fitur sudah ditest, khusus untuk parsing BCA dan Panin pastikan logika berjalan sesuai `FORMAT_SPEC.md`.
2. Versi: Update nomor versi pada file `version.txt` secara manual.

---

## 2. Proses Build Executable
Lakukan proses kompilasi ulang untuk membuat versi mandiri (standalone executable). Disarankan untuk selalu menggunakan flag `--clean` agar tidak ada sisa cache yang menempel.

**PENTING (ANTI-BLOAT):** Anda WAJIB memanggil `python` langsung dari dalam folder Virtual Environment (`.\.venv\Scripts\python.exe`) seperti di bawah ini. JANGAN SEKALI-KALI menggunakan perintah `python` biasa karena PyInstaller akan membungkus library global yang tidak diperlukan (membuat file bengkak hingga ratusan MB).

Jalankan perintah ini secara berurutan di terminal (PowerShell):
```powershell
# 1. Hapus sisa build lama (opsional tapi sangat disarankan)
Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue

# 2. Jalankan kompilasi dengan memanggil Python dari dalam VENV
.\.venv\Scripts\python.exe -m PyInstaller accurate_format_converter.spec --clean
.\.venv\Scripts\python.exe -m PyInstaller launcher.spec --clean
```

---

## 3. Menyiapkan Folder Distribusi
Setelah build selesai, file hasilnya akan ada di folder `dist\`.
Salin file konfigurasi versi agar installer mengenali versi terbaru:
```powershell
Copy-Item version.txt dist\version.txt -Force
```

---

## 4. Digital Signing Tahap 1 (Aplikasi)
Aplikasi bisa ditandatangani menggunakan *Self-Signed Certificate* (.pfx) untuk menyematkan identitas Anda selaku *developer* pada file *executable*.
Meskipun sifatnya *self-signed*, ini langkah baik agar *file* terlihat lebih profesional. Jalankan `signtool` untuk kedua aplikasi `.exe` yang baru saja di-build:
```powershell
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe" sign /f "assets\khairudinfahmi.pfx" /p rensa2026 /fd SHA256 /t http://timestamp.digicert.com "dist\Accurate_Format_Converter.exe" "dist\Launcher.exe"
```

---

## 5. Membuat Installer
Buka Inno Setup compiler melalui Command Line untuk membuat Installer yang siap dibagikan ke pengguna:
```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" accurate_converter_installer.iss
```
File hasil installer akan dibuat di dalam folder `Output\` dengan nama `Accurate_Converter_Setup_v4.0.exe` (atau sesuai versi).

---

## 6. Digital Signing Tahap 2 (Installer)
File installer `.exe` juga HARUS ditandatangani secara digital agar saat user mengunduh tidak terkena peringatan keamanan.
```powershell
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe" sign /f "assets\khairudinfahmi.pfx" /p rensa2026 /fd SHA256 /t http://timestamp.digicert.com "Output\Accurate_Converter_Setup_v4.0.exe"
```

---

## 7. Rilis dan Publikasi
1. Upload file `Output\Accurate_Converter_Setup_v4.0.exe` ke halaman **GitHub Releases**.
2. Masuk ke Gist GitHub dan perbaharui file `update_info.json`:
   - Ganti `latest_version` dengan versi baru (misal: `"4.0.0"`).
   - Ganti `download_url` dengan direct link (akhiran `.exe`) dari GitHub Releases yang baru di-upload.
3. Begitu metadata ini disimpan, aplikasi pengguna lama akan secara otomatis mendeteksi update.
