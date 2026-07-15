# 🤖 AI SYSTEM RULES - ACCURATE FORMAT CONVERTER

> **CRITICAL WARNING FOR AI AGENTS**: 
> File ini adalah **SUMBER KEBENARAN MUTLAK (SINGLE SOURCE OF TRUTH)** untuk keseluruhan arsitektur proyek "Accurate Format Converter". 
> Anda **DILARANG KERAS** mengubah logika parsing, struktur output, atau konfigurasi build/spec yang sudah didefinisikan di sini tanpa persetujuan eksplisit dari pengguna. Jika Anda menemui kebingungan, rujuklah pada aturan di bawah ini.

---

## 1. STRUKTUR DAN ARSITEKTUR PROYEK
Aplikasi ini memiliki arsitektur 2-lapis (2-Tier) dengan model distribusi **Shared Directory (`onedir`)**:
1. **Launcher (`launcher.py`)**: Aplikasi kecil (Tkinter) yang bertugas mengecek update dari GitHub Gist. Jika ada update berupa file `.exe` installer, Launcher akan membersihkan *environment variables* PyInstaller (`_MEIPASS`/`_PYI_`) dan memicu eksekusi installer secara langsung via `ShellExecuteW` (`/VERYSILENT /NORESTART /DIR=...`) tanpa melibatkan PowerShell atau jendela terminal apa pun, lalu menutup dirinya sendiri.
2. **Main App (`main.py` -> `ui/app_window.py`)**: Aplikasi konverter utama.

### Hierarki Direktori Penting:
*   `src/processors/bca_processor.py`: Logika ekstraksi PDF/CSV BCA.
*   `src/processors/panin_processor.py`: Logika ekstraksi PDF/XLS/CSV Panin.
*   `src/utils/helpers.py`: Pembersihan string, format mata uang, toleransi tanggal.
*   `accurate_format_converter.spec`: Aturan PyInstaller tunggal (*unified spec*) yang mengompilasi `Accurate_Format_Converter.exe` dan `Launcher.exe` ke dalam satu folder bersama (`dist/Accurate_Format_Converter` - model `onedir`).

---

## 2. ATURAN MUTLAK: STRUKTUR OUTPUT (FORMAT_SPEC)
Aplikasi ini ditujukan untuk mengimpor data ke **Accurate Online**. Format output (baik XLS maupun CSV) **HARUS EXACTLY 5 KOLOM** dengan urutan dan nama header baku:
1.  `tanggal` (Format `DD/MM/YYYY`)
2.  `transaksi` (String/teks keterangan)
3.  `debet` (Angka murni/float, 0 jika kosong)
4.  `kredit` (Angka murni/float, 0 jika kosong)
5.  `Saldo` (Angka murni/float)

**Pantangan Output:**
*   Tidak boleh ada teks kosong `""` atau `"NaN"` pada kolom `tanggal`.
*   Semua simbol mata uang `Rp`, `,`, dan `.` ribuan harus bersih.

---

## 3. ATURAN MUTLAK: PARSING BCA (`bca_processor.py`)
BCA memiliki format PDF yang kompleks, serta mendukung input CSV (seperti ekspor KlikBCA). 
PENTING: BCA menghasilkan **3 file output sekaligus** (CSV Accurate, XLS Formatter, dan KlikBCA CSV).
Untuk input PDF, AI tidak boleh merusak sistem prioritas (3-Phase) berikut:

1.  **Sistem Koordinat (X0):**
    *   `x0 < 85`: Kolom Tanggal.
    *   `85 <= x0 < 330`: Kolom Keterangan/Transaksi.
    *   `330 <= x0 < 480`: Kolom Mutasi (Nilai Uang) DAN Penanda Mutasi (`DB` / `CR`).
    *   `x0 >= 480`: Kolom Saldo.
2.  **Sistem Penentuan Debet/Kredit (Prioritas 3 Lapis):**
    *   **Priority 1 (Mutasi Marker):** AI harus mencari kata `"DB"` atau `"CR"` yang secara spesifik jatuh pada koordinat `330 <= x0 < 480`. Jika ada `"DB"` di area ini, itu PASTI debet.
    *   **Priority 2 (Description Fallback):** Jika marker tidak terbaca, gunakan _keyword matching_ dari deskripsi.
        *   `DB Keywords`: "DB DEBIT DOMESTIK", "DB", "BIAYA", "BYR VIA", dsb.
        *   `CR Keywords`: "CR", "BUNGA", "TRSF E-BANKING CR".
    *   **Phase 2 (Saldo Mathematics):** Pengecekan akhir. Jika `Saldo_Sebelumnya - Saldo_Sekarang != 0`, selisih tersebut menentukan D/C yang sebenarnya untuk mengoreksi anomali di Priority 1 & 2.

---

## 4. ATURAN MUTLAK: PARSING PANIN & EXPORT LOGIC
Panin memori memiliki edge case dan toleransi yang harus diperhatikan:
1.  **Padding/Dummy Rows:** Hasil akhir data Panin **DIWAJIBKAN** memiliki `num_dummy = 7` baris pertama berupa duplikasi data transaksi awal sebelum baris "Saldo Awal". Ini adalah _hack_ spesifik agar mesin import Accurate Online tidak memotong baris mutasi penting (karena sistem Accurate sering melewatkan baris awal Panin).
2.  **Penanganan Tanggal Invalid:** Baik di BCA maupun Panin, jika fungsi `parse_date_tolerant` (di `helpers.py`) gagal memparsing tanggal di sebuah baris, baris tersebut **TIDAK BOLEH** dibuang begitu saja. Baris itu dikirim ke koleksi `invalid_dates_data` dan di-export secara terpisah menjadi file `*_invalid_dates.csv` lewat fungsi `save_invalid_dates`.
3.  **Simpan File (File Exporter):** Fungsi `save_exact_xls` digunakan agar file XLS akhir benar-benar mematuhi standar Excel 97-2003 (`xlwt`) yang disukai oleh Accurate, bukan format `.xlsx` modern (`openpyxl`).

---

## 5. ATURAN MUTLAK: PROSES BUILD & PACKAGING (`BUILD_GUIDE.md`)
AI **DILARANG** mengubah cara build aplikasi. Ikuti aturan ini 100%:

### A. Arsitektur Shared Directory (`onedir`) & Ukuran Build
Aplikasi ini dibangun dengan model **`onedir` (`exclude_binaries=True`)** agar tidak ada lagi ekstraksi DLL/dependensi ke folder `Temp` Windows yang memicu pemblokiran Windows Defender atau memori penuh (`_MEI`).
*   **Wajib mutlak** memanggil Python dari dalam VENV (`.\.venv\Scripts\python.exe -m PyInstaller ...`). Menjalankan script aktivasi (`Activate.ps1`) seringkali gagal karena sistem proteksi eksekusi PowerShell di Windows, sehingga PyInstaller tembus mengambil library global.
*   Kedua executable (`Accurate_Format_Converter.exe` dan `Launcher.exe`) berbagi folder `_internal` yang sama di `dist/Accurate_Format_Converter`.
*   **Ukuran Wajar:** Ukuran folder `dist/Accurate_Format_Converter` mentah adalah **~160 MB**, sedangkan ukuran file Installer terkompresi (`Output/Accurate_Converter_Setup_v4.2.exe`) dari Inno Setup adalah **~66 MB** (persisnya ~69 MB dengan `pandas`, `numpy`, `xlrd`, & `openpyxl` lengkap terbundel).

### B. Patch Kritis PyInstaller (Mypyc `charset_normalizer` & Keamanan PFX)
Dalam file `accurate_format_converter.spec`, ada dua aturan yang SANGAT KRITIS:
1. **Patch `charset_normalizer`:** Library `charset_normalizer` menggunakan ekstensi C `mypyc` yang memiliki hash acak (contoh: `81d243bd2c585b0f4821__mypyc.pyd`). PyInstaller tidak bisa melihatnya.
**Jangan pernah menghapus blok kode ini di `.spec`:**
```python
import charset_normalizer
import os, glob
site_packages = os.path.dirname(os.path.dirname(charset_normalizer.__file__))
for f in glob.glob(os.path.join(site_packages, '*__mypyc*.pyd')):
    binaries.append((f, '.'))
```
Tanpa kode ini, aplikasi akan *crash* `ModuleNotFoundError` di komputer user.
2. **Filter Keamanan Aset PFX:** Pastikan pembungkus aset di `.spec` **hanya** memasukkan gambar dan ikon (`assets/*.png`, `assets/*.ico`) serta **TIDAK BOLEH** membundel file kunci privat `khairudinfahmi.pfx` ke dalam direktori distribusi.

### Deployment / Build
- **Wajib menggunakan script `build_all.ps1`**. JANGAN PERNAH menyuruh pengguna menjalankan PyInstaller, signtool, atau Inno Setup compiler (ISCC) secara manual. Script sakti ini sudah meng-handle semuanya secara otomatis.
- File installer selalu dihasilkan di folder `Output/` dan membundel seluruh isi direktori `dist/Accurate_Format_Converter/*`.

### Aturan Keamanan (Digital Signature)
Gunakan sertifikat *Self-Signed* `assets\khairudinfahmi.pfx` dengan password `rensa2026`. File utama dan file Installer (`Output\Accurate_Converter_Setup_v4.2.exe` dari Inno Setup) **HARUS** di-sign.

---

**Pesan Penutup untuk AI:**
Dengan membaca `AI.md` ini, Anda telah menyinkronkan memori (context) Anda dengan perjuangan panjang yang telah dilewati oleh pengguna untuk membuat program ini stabil, ringan, dan bebas bug. Jaga standar ini.
