# 🤖 AI SYSTEM RULES - ACCURATE FORMAT CONVERTER

> **CRITICAL WARNING FOR AI AGENTS**: 
> File ini adalah **SUMBER KEBENARAN MUTLAK (SINGLE SOURCE OF TRUTH)** untuk keseluruhan arsitektur proyek "Accurate Format Converter". 
> Anda **DILARANG KERAS** mengubah logika parsing, struktur output, atau konfigurasi build/spec yang sudah didefinisikan di sini tanpa persetujuan eksplisit dari pengguna. Jika Anda menemui kebingungan, rujuklah pada aturan di bawah ini.

---

## 1. STRUKTUR DAN ARSITEKTUR PROYEK
Aplikasi ini memiliki arsitektur 2-lapis (2-Tier):
1. **Launcher (`launcher.py`)**: Aplikasi kecil (Tkinter) yang bertugas mengecek update dari GitHub Gist. Jika ada update, ia akan mendownload installer senyap, menggunakan skrip PowerShell (`install_update.ps1`) untuk mematikan proses lama dan menimpa file di direktori berjalan menggunakan argumen `/DIR`, lalu memulai ulang launcher.
2. **Main App (`main.py` -> `ui/app_window.py`)**: Aplikasi konverter utama.

### Hierarki Direktori Penting:
*   `src/processors/bca_processor.py`: Logika ekstraksi PDF/XLS BCA.
*   `src/processors/panin_processor.py`: Logika ekstraksi PDF/XLS/CSV Panin.
*   `src/utils/helpers.py`: Pembersihan string, format mata uang, toleransi tanggal.
*   `accurate_format_converter.spec`: Aturan PyInstaller Aplikasi Utama.
*   `launcher.spec`: Aturan PyInstaller Launcher.

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
BCA memiliki format PDF yang paling kompleks. AI tidak boleh merusak sistem prioritas (3-Phase) berikut:

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

### A. Isu Ukuran Membengkak (The Bloat Issue)
Aplikasi ini hanya membutuhkan dependensi ringan (Pandas, PDFPlumber, Tkinter). **Jangan pernah memanggil PyInstaller menggunakan Python Global.** 
*   **Wajib mutlak** memanggil Python dari dalam VENV (`.\.venv\Scripts\python.exe -m PyInstaller ...`). Menjalankan script aktivasi (`Activate.ps1`) seringkali gagal karena sistem proteksi eksekusi PowerShell di Windows, sehingga PyInstaller tembus mengambil library global.
*   Jika AI melihat ukuran file build 200MB+, itu artinya PyInstaller salah menarik library seperti `torch`, `scipy`, atau `opencv`. Ukuran wajar adalah **~68 MB**.

### B. Patch Kritis PyInstaller (Mypyc `charset_normalizer`)
Dalam file `accurate_format_converter.spec`, ada patch dinamis yang SANGAT KRITIS. Library `charset_normalizer` menggunakan ekstensi C `mypyc` yang memiliki hash acak (contoh: `81d243bd2c585b0f4821__mypyc.pyd`). PyInstaller tidak bisa melihatnya.
**Jangan pernah menghapus blok kode ini di `.spec`:**
```python
import charset_normalizer
import os, glob
site_packages = os.path.dirname(os.path.dirname(charset_normalizer.__file__))
for f in glob.glob(os.path.join(site_packages, '*__mypyc*.pyd')):
    binaries.append((f, '.'))
```
Tanpa kode ini, aplikasi akan *crash* `ModuleNotFoundError` di komputer user.

### C. Digital Signing
Gunakan sertifikat `assets\khairudinfahmi.pfx` dengan password `rensa2026`. File utama dan file Installer (`Output\Accurate_Converter_Setup_v4.0.exe` dari Inno Setup) **HARUS** di-sign.

---

**Pesan Penutup untuk AI:**
Dengan membaca `AI.md` ini, Anda telah menyinkronkan memori (context) Anda dengan perjuangan panjang yang telah dilewati oleh pengguna untuk membuat program ini stabil, ringan, dan bebas bug. Jaga standar ini.
