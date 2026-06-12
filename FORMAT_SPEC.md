# Spesifikasi Format Output - Accurate Format Converter

Dokumen ini adalah referensi FINAL dan WAJIB DIPATUHI untuk seluruh format output
yang dihasilkan oleh aplikasi. Format ini sudah 100% cocok dan terverifikasi
untuk di-import ke Accurate Online.

PERINGATAN KERAS: JANGAN MENGUBAH format karakter, urutan kolom, struktur baris,
tanda kutip, separator, line ending, atau logika apapun yang didokumentasikan
di bawah ini TANPA persetujuan eksplisit dari pemilik project (Fahmi).


---

## Daftar Isi

1. Arsitektur Project
2. Spesifikasi Output PANIN (Format XLS)
3. Spesifikasi Output BCA (Format CSV + XLS Backup)
4. Logika Dummy Row
5. Logika Currency & Date Parsing
6. Styling XLS (Warna, Font, Format Angka)
7. Daftar File Kritis (Jangan Diubah Strukturnya)


---

## 1. Arsitektur Project

```
Accurate_Format_Converter/
|-- main.py                          # Entry point, load UI
|-- launcher.py                      # Auto-updater launcher
|-- version.txt                      # Versi aplikasi (misal: 4.0.0)
|-- update_info.json                 # Referensi lokal info update
|-- accurate_format_converter.spec   # PyInstaller spec (App utama)
|-- launcher.spec                    # PyInstaller spec (Launcher)
|-- accurate_converter_installer.iss # Inno Setup script
|-- BUILD_GUIDE.md                   # Panduan build & rilis
|-- assets/
|   |-- rensa_logo.ico               # Icon aplikasi
|   |-- bca.png, panin.png, ...      # Gambar bank untuk UI
|   |-- khairudinfahmi.pfx           # Sertifikat digital
|   |-- khairudinfahmi_cert.cer      # Sertifikat publik
|-- src/
    |-- processors/
    |   |-- panin_processor.py       # Logika konversi Panin
    |   |-- bca_processor.py         # Logika konversi BCA
    |-- ui/
    |   |-- app_window.py            # UI utama + logika save BCA CSV
    |-- utils/
        |-- helpers.py               # clean_currency, clean_desc, parse_date_tolerant
        |-- file_exporter.py         # save_exact_xls, save_invalid_dates
        |-- config_manager.py        # load/save config user
```


---

## 2. Spesifikasi Output PANIN (Format XLS)

### 2.1 Kolom Output (Urutan Wajib)

| Index | Nama Kolom | Tipe Data   | Contoh Isi         | Keterangan                        |
|-------|------------|-------------|--------------------|------------------------------------|
| 0     | tanggal    | Text (@)    | 15/03/2026         | Format: dd/mm/yyyy                 |
| 1     | transaksi  | Text (@)    | TRANSFER DARI ...  | Deskripsi transaksi                |
| 2     | debet      | Number      | 500000.00          | Kosong ("") jika tidak ada debet   |
| 3     | kredit     | Number      | 1500000.00         | Kosong ("") jika tidak ada kredit  |
| 4     | Saldo      | Number      | 25000000.00        | Saldo setelah transaksi            |

Mapping kolom didefinisikan di panin_processor.py:
```python
OUTPUT_COLUMNS = {
    'tgl': 'tanggal',
    'desc': 'transaksi',
    'deb': 'debet',
    'kre': 'kredit',
    'bal': 'Saldo'
}
```

PENTING: Key dictionary di atas ('tgl', 'desc', 'deb', 'kre', 'bal') digunakan
secara internal. Value-nya ('tanggal', 'transaksi', 'debet', 'kredit', 'Saldo')
adalah nama kolom yang muncul di file output. JANGAN UBAH value-value ini.

### 2.2 Struktur Baris Output Panin (Urutan Wajib)

```
Row 1     : HEADER (tanggal | transaksi | debet | kredit | Saldo)
Row 2-8   : DUMMY (7 baris, data dari transaksi yang di-loop)
Row 9     : SEPARATOR "Saldo Awal" (tanggal kosong, transaksi="Saldo Awal", saldo=nilai)
Row 10+   : DATA TRANSAKSI ASLI (semua baris valid)
Row N-1   : SEPARATOR "Total Mutasi" (debet=total, kredit=total)
Row N     : SEPARATOR "Saldo Akhir" (saldo=nilai akhir)
```

### 2.3 Perhitungan Saldo Awal Panin

```python
saldo_awal = saldo_baris_pertama - kredit_baris_pertama + debit_baris_pertama
```

Rumus ini menghitung mundur dari saldo transaksi pertama untuk mendapatkan
saldo sebelum transaksi pertama terjadi.

### 2.4 Format Tanggal Panin

- Format output: dd/mm/yyyy (contoh: 15/03/2026)
- Disimpan sebagai TEXT (bukan Date object) di Excel
- Menggunakan parse_date_tolerant() yang mendukung banyak format input:
  dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy, dd/mm/yy, yyyy-mm-dd, dll.

### 2.5 Aturan Debet/Kredit Panin

- Jika debet > 0, kolom kredit HARUS kosong ("")
- Jika kredit > 0, kolom debet HARUS kosong ("")
- Jika keduanya 0, baris tersebut DIABAIKAN (tidak masuk output)
- Kolom debet/kredit disimpan sebagai Number (float) di XLS, BUKAN text


---

## 3. Spesifikasi Output BCA

BCA menghasilkan 2 file output sekaligus:
1. CSV (Primary) -- Untuk di-import ke Accurate Online
2. XLS (Backup)  -- Untuk arsip data

### 3.1 Format CSV BCA (PRIMARY - Import Accurate)

#### Header Metadata (Baris 1-4):
```csv
No. Rekening,=,'1234567890
Nama,=,NAMA NASABAH
Mata Uang,=,IDR
(baris kosong)
```

PENTING:
- Nomor rekening diawali tanda kutip tunggal: '1234567890
  Tanda kutip ini WAJIB ada agar Accurate membaca sebagai teks, bukan angka.
- Nama nasabah: koma dan tanda kutip ganda dihapus (replace ',' dan '"')
- Baris ke-4 adalah baris kosong (empty row)

#### Header Kolom (Baris 5):
```csv
Tanggal,Keterangan,Cabang,Jumlah,,Saldo
```

PENTING: Ada kolom ke-5 yang KOSONG (antara Jumlah dan Saldo).
Kolom kosong ini berisi tipe transaksi (CR/DB) di baris data.

#### Baris Data Transaksi (Baris 6+):
```csv
'05/12,TRANSFER DARI ...,0000,1500000.00,CR,25000000.00
```

| Index | Nama       | Contoh         | Keterangan                              |
|-------|------------|----------------|-----------------------------------------|
| 0     | Tanggal    | '05/12         | Diawali kutip tunggal, format dd/mm     |
| 1     | Keterangan | SETORAN TUNAI  | Koma & kutip ganda dihapus dari teks    |
| 2     | Cabang     | '0000          | Selalu '0000 (diawali kutip tunggal)    |
| 3     | Jumlah     | 1500000.00     | Float, 2 desimal, TANPA pemisah ribuan  |
| 4     | Tipe       | CR atau DB     | CR=kredit/masuk, DB=debet/keluar        |
| 5     | Saldo      | 25000000.00    | Float, 2 desimal, TANPA pemisah ribuan  |

PENTING tentang format angka di CSV:
- Angka ditulis dengan format Python f"{value:.2f}" (contoh: 1500000.00)
- TIDAK ADA pemisah ribuan (BUKAN 1,500,000.00)
- Selalu 2 digit desimal

#### Footer Ringkasan (Setelah semua data):
```csv
Saldo Awal,=,25000000.00
Kredit,=,5000000.00
Debet,=,3000000.00
Saldo Akhir,=,27000000.00
(baris kosong)
```

#### Aturan CSV:
- Line terminator: \n (LF only, BUKAN \r\n)
- Encoding: UTF-8
- Separator: Koma (standard CSV)
- Writer: csv.writer Python standar

### 3.2 Logika Deteksi CR/DB BCA

Penentuan tipe transaksi dilakukan di bca_processor.py menggunakan 2 fase:

Fase 1: Deteksi awal via marker PDF + keyword (saat parsing PDF)

Prioritas 1: Marker DB/CR dari zona mutasi PDF (paling akurat)
BCA mencetak marker "DB" atau "CR" di kolom mutasi PDF (x0: 330-480).
Jika marker ini ditemukan, langsung digunakan tanpa cek keyword.

```python
mutasi_zone_marker = None
# Dalam loop parsing word:
elif w['text'].strip().upper() in ('DB', 'CR'):
    mutasi_zone_marker = w['text'].strip().upper()

# Penentuan tipe:
if mutasi_zone_marker == "DB":
    tipe = "DB"
elif mutasi_zone_marker == "CR":
    tipe = "CR"
```

Prioritas 2: Deteksi via keyword di deskripsi (jika tidak ada marker)

```python
tipe = "CR"  # Default: kredit (uang masuk)
desc_upper = desc.upper()
if desc_upper.startswith("DB ") or " DB" in desc_upper \
   or "BIAYA" in desc_upper or "PAJAK" in desc_upper \
   or "TARIKAN" in desc_upper or "POTONGAN" in desc_upper \
   or "KARTU DEBIT" in desc_upper or "PEMBAYARAN" in desc_upper \
   or "PEMBELIAN" in desc_upper or "SWITCHING DB" in desc_upper \
   or "BYR VIA" in desc_upper:
    tipe = "DB"
elif " CR" in desc_upper or "SETORAN" in desc_upper or "BUNGA" in desc_upper:
    tipe = "CR"
```

CATATAN tentang keyword DB:
- `desc_upper.startswith("DB ")` menangkap deskripsi yang dimulai dengan "DB" 
  (contoh: "DB DEBIT DOMESTIK TRN DEBIT DOM")
- `" DB"` menangkap "DB" di tengah deskripsi (contoh: "TRSF E-BANKING DB")
- `"BYR VIA"` menangkap pembayaran via e-banking (contoh: "BYR VIA E-BANKING")

Fase 2: Koreksi menggunakan saldo sebagai sumber kebenaran utama

Setelah semua transaksi diekstrak, dilakukan pengecekan ulang:
- Jika saldo tercetak tersedia: bandingkan dengan saldo sebelumnya.
  Saldo naik sebesar mutasi = CR. Saldo turun sebesar mutasi = DB.
  Koreksi berlaku dua arah (CR->DB dan DB->CR).
- Jika saldo tercetak TIDAK tersedia: gunakan hasil dari Fase 1.
- Jika saldo tidak cocok dengan keduanya (karena ada transaksi lain
  tanpa saldo di antaranya): pertahankan tipe dari Fase 1.

### 3.3 Format XLS Backup BCA

Strukturnya SAMA dengan output Panin (lihat Bagian 2.2):
- 7 baris DUMMY
- 1 baris Saldo Awal
- Data transaksi
- 1 baris Total Mutasi
- 1 baris Saldo Akhir

Perbedaan dengan Panin:
- Tanggal BCA di XLS backup: dd/mm/yyyy (ditambahkan /tahun otomatis)
  Karena PDF BCA hanya menyediakan dd/mm, tahun diambil dari tahun saat ini.
- Kolom debet/kredit dipisah (sama seperti Panin)


---

## 4. Logika Dummy Row

### 4.1 Jumlah Dummy: SELALU 7 baris

```python
num_dummy = 7
```

Nilai ini TIDAK BOLEH diubah. Accurate Online membutuhkan tepat 7 baris
dummy di awal file untuk mencocokkan template import.

### 4.2 Cara Pengisian Dummy

Jika jumlah transaksi >= 7:
  Ambil 7 baris pertama dari data transaksi.

Jika jumlah transaksi < 7:
  Loop ulang data transaksi sampai genap 7 baris menggunakan modulo:

```python
if len(df_final) >= num_dummy:
    df_dummy = df_final.iloc[:num_dummy].copy()
else:
    rows = []
    for i in range(num_dummy):
        rows.append(df_final.iloc[i % len(df_final)].to_dict())
    df_dummy = pd.DataFrame(rows)
```

Contoh: Jika hanya ada 3 transaksi (A, B, C), dummy akan menjadi:
A, B, C, A, B, C, A (7 baris)

### 4.3 Styling Dummy di XLS

Baris dummy diberi style khusus agar mudah dibedakan:
- Font: Merah, Italic
- Background: Abu-abu (gray25)
- Format angka: #,##0.00 untuk kolom numerik


---

## 5. Logika Currency & Date Parsing

### 5.1 clean_currency(val) - helpers.py

Fungsi ini mengkonversi berbagai format angka ke float:

Aturan konversi:
1. Jika val adalah NaN, None, 'nan', 'none', '-', 'null' -> return 0.0
2. Hapus semua karakter kecuali digit, titik, koma, minus
3. Jika ada koma DAN titik:
   - Jika koma terakhir lebih kanan dari titik terakhir -> format Eropa
     (titik=ribuan, koma=desimal). Hapus titik, ganti koma jadi titik.
   - Jika sebaliknya -> format US. Hapus koma.
4. Jika hanya ada koma:
   - Jika 3 digit setelah koma terakhir -> pemisah ribuan. Hapus koma.
   - Selain itu -> desimal. Ganti koma jadi titik.
5. Jika hanya ada titik:
   - Jika digit setelah titik terakhir BUKAN 2 digit -> pemisah ribuan.
   - Jika 2 digit -> desimal (biarkan).

### 5.2 clean_desc(val, use_regex) - helpers.py

- Jika use_regex=False: hanya strip whitespace
- Jika use_regex=True: pecah kata yang menempel
  (camelCase, huruf-angka, dll.)

### 5.3 parse_date_tolerant(date_str) - helpers.py

Urutan format yang dicoba:
1. dd/mm/yyyy
2. dd-mm-yyyy
3. dd.mm.yyyy
4. dd/mm/yy
5. dd-mm-yy
6. dd.mm.yy
7. yyyy/mm/dd
8. yyyy-mm-dd
9. yyyy.mm.dd

Jika semua gagal, coba ekstrak 3 kelompok angka dan susun sebagai dd/mm/yyyy.
Jika tetap gagal, return NaT (Not a Time) dan baris tersebut masuk ke
file "tanggal_tidak_valid".


---

## 6. Styling XLS (file_exporter.py)

### 6.1 Tiga Zona Style

| Zona             | Baris            | Font            | Background    |
|------------------|------------------|-----------------|---------------|
| DUMMY            | Row 2-8 (7 brs)  | Merah, Italic   | Abu (gray25)  |
| SEPARATOR        | Row 9            | Bold            | Kuning muda   |
| DATA NORMAL      | Row 10+          | Default         | Default       |

### 6.2 Format Angka per Kolom

| Kolom      | Index | Format XLS    | Keterangan                 |
|------------|-------|---------------|----------------------------|
| tanggal    | 0     | @ (Text)      | Disimpan sebagai string    |
| transaksi  | 1     | @ (Text)      | Disimpan sebagai string    |
| debet      | 2     | #,##0.00      | Float, pemisah ribuan      |
| kredit     | 3     | #,##0.00      | Float, pemisah ribuan      |
| Saldo      | 4     | #,##0.00      | Float, pemisah ribuan      |

### 6.3 Lebar Kolom

- Kolom transaksi (index 1): 60 karakter (256 * 60)
- Kolom lainnya: 18 karakter (256 * 18)

### 6.4 Sheet Name

Selalu "Sheet1" (didefinisikan di file_exporter.py sebagai TARGET_SHEET_NAME)


---

## 7. Daftar File Kritis (Jangan Diubah Strukturnya)

File-file berikut mengandung logika format output yang sudah terverifikasi.
Setiap perubahan pada file-file ini HARUS dicek ulang kompatibilitasnya
dengan template import Accurate Online.

| File                          | Apa yang kritis                               |
|-------------------------------|------------------------------------------------|
| src/processors/panin_processor.py | OUTPUT_COLUMNS, urutan concat df_output, rumus saldo awal, format tanggal dd/mm/yyyy, logika debet/kredit kosong |
| src/processors/bca_processor.py   | Format tanggal 'dd/mm, tipe CR/DB detection, cabang '0000, logika koreksi saldo |
| src/ui/app_window.py              | CSV writer BCA (header metadata, line terminator \n, format angka f:.2f, kolom kosong antara Jumlah dan Saldo), XLS backup structure |
| src/utils/file_exporter.py        | Styling XLS (dummy merah/italic, separator kuning, format angka #,##0.00), sheet name "Sheet1" |
| src/utils/helpers.py              | clean_currency (logika koma/titik), parse_date_tolerant (urutan format) |


---

## Catatan Akhir

Dokumen ini dibuat berdasarkan kode versi 4.0.0 yang sudah 100% terverifikasi dan cocok
dengan template import Accurate Online per tanggal 12 Juni 2026.

Jika ada AI atau developer lain yang diminta mengubah kode, WAJIB baca
dokumen ini terlebih dahulu dan JANGAN mengubah format output tanpa
memahami dampaknya terhadap kompatibilitas import Accurate Online.

---
