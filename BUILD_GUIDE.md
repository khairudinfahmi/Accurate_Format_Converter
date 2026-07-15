# Panduan Build dan Rilis - Accurate Format Converter

Dokumen ini berisi langkah-langkah lengkap untuk melakukan kompilasi aplikasi, penandatanganan digital (*Digital Signing*), hingga pembuatan *installer* otomatis. Ikuti urutan ini setiap kali ingin merilis versi terbaru.

---

## 1. Persiapan Awal
Sebelum mulai, pastikan hal berikut sudah dilakukan:
1. **Update Kode:** Pastikan semua fitur sudah ditest, khusus untuk parsing BCA dan Panin pastikan logika berjalan sesuai `FORMAT_SPEC.md`.
2. **Nomor Versi:** Update nomor versi pada file `version.txt` secara manual. Versi ini akan digunakan oleh *Launcher* dan *Installer*.
3. **Versi Installer:** Buka file `accurate_converter_installer.iss` dan update baris `#define MyAppVersion "4.x.x"` agar sesuai dengan `version.txt`.

---

## 2. Eksekusi Build Otomatis (One-Click Build)
Kompilasi `.exe`, perakitan *Installer* (Inno Setup), dan penyematan *Digital Signature* ke dalam file agar tidak di-blokir oleh *Windows SmartScreen* kini telah diotomatisasi 100%.

Jalankan skrip PowerShell sakti ini dari *root* direktori:
```powershell
.\build_all.ps1
```

**Apa yang dilakukan skrip tersebut?**
- Memanggil `PyInstaller` melalui *virtual environment* (`.venv`) menggunakan file konfigurasi tunggal (*unified spec*) `accurate_format_converter.spec` dengan model distribusi **Shared Directory (`onedir`)**.
- Mengompilasi `Accurate_Format_Converter.exe` dan `Launcher.exe` yang berbagi folder DLL/dependensi (`_internal`) di `dist\Accurate_Format_Converter`.
- Menandatangani kedua *executable* utama tersebut menggunakan sertifikat digital (`assets\khairudinfahmi.pfx`) via PowerShell `Set-AuthenticodeSignature`.
- Mengeksekusi Inno Setup Compiler (`ISCC.exe`) untuk merakit *Installer* kompresi tinggi (`LZMA2/Ultra64`) yang membundel seluruh folder `dist\Accurate_Format_Converter`.
- Menandatangani hasil akhir *Installer* di folder `Output\`.

---

## 3. Rilis dan Publikasi (Auto-Update)
Setelah *Installer* berhasil dibuat di folder `Output\`, publikasikan rilis terbaru agar sistem *Auto-Update* di komputer klien memicunya.

1. **Upload ke GitHub Releases:**
   Gunakan GitHub CLI untuk membuat rilis baru dan mengunggah *Installer*. Pastikan Anda tidak mengatur *tag* secara lokal, biarkan GitHub yang membuatkannya agar mendapat lencana **Verified**.
   ```powershell
   gh release create v4.3.0 "Output\Accurate_Converter_Setup_v4.3.exe" --target main --title "Versi 4.3.0 (Fitur Baru)" --notes "Catatan Rilis..."
   ```
2. **Memicu Gist Manifest (Rahasia):**
   Ubah file `update_info.json` secara lokal dengan *version* dan tautan *download URL* `.exe` yang baru, lalu perbarui Gist Anda:
   ```powershell
   gh gist edit 7e47f4d086fd768f655774d1489bb776 update_info.json
   ```
3. Selesai! Saat Klien membuka *Launcher* versi lama, ia akan otomatis membaca Gist, mengunduh rilis dari GitHub, menginstal *Sertifikat Root*, dan melakukan *silent-update*.
