# Accurate Format Converter

Aplikasi kecil buat bantu convert file mutasi rekening bank (kayak BCA atau Panin) jadi format yang siap di-import langsung ke **Accurate Online**. 

Nggak perlu lagi ngedit-ngedit manual di Excel yang bikin pusing, aplikasi ini udah ngurusin format tanggal, posisi kolom debit/kredit, sampai nambahin baris kosong (*dummy rows*) yang diminta sama sistem Accurate.

---

## Fiturnya Apa Aja?

*   **Bisa banyak Bank & Multi-Format:** 
    *   **BCA:** Bisa membaca mutasi dari file **PDF (Tahapan & Giro)**, **Excel (.xlsx/.xls)**, maupun **CSV (myBCA & KlikBCA)**. Output BCA otomatis **dibungkus ke dalam 1 folder** yang berisi 4 file sekaligus (`1 - Template AOL Format JSON.json`, `2 - Template AOL Format Excel (Non-JSON).xls`, `3 - Template Rekening Tahapan.csv`, dan `4 - Template Rekening Giro.csv`).
    *   **Panin:** Bisa baca dari PDF (teks asli & pindaian OCR), XLS/XLSX, maupun CSV. Otomatis menghasilkan `Template AOL Format JSON (.json)` dan `Template AOL Format Excel (Non-JSON) (.xls)`.
*   **Format Resmi Accurate Online (AOL) JSON (Baru di v5.0):** Menghasilkan file `.json` resmi yang siap diimpor langsung ke menu Rekonsiliasi Bank Accurate Online dengan penyesuaian tanda mutasi (negatif untuk Debet, positif untuk Kredit) dan kepastian matematis saldo kas terverifikasi 100% klop (Rp 0.00).
*   **Format Excel Dijamin Pas:** Hasil jadinya (file XLS atau CSV) udah pas 5 kolom sesuai standar impor Accurate. Termasuk otomatis nambahin baris *dummy* biar datanya nggak kepotong pas di-import.
*   **Aman dari Tanggal Error:** Kalau ada tanggal transaksi yang aneh atau nggak kebaca, barisnya bakal dipisah ke file tersendiri biar nggak ngerusak data utama.
*   **Update Otomatis:** Kalau ada versi baru, aplikasi bakal otomatis download dan install sendiri di latar belakang tanpa ribet.
*   **Aman dari SmartScreen (Baru):** Installer secara otomatis akan menginjeksi Digital Certificate ke *Trusted Root* PC Anda sehingga terhindar dari pemblokiran Windows Defender SmartScreen.
*   **Ringan Banget:** Udah di-build pakai PyInstaller & Inno Setup dengan rapi, ukuran installernya cuma sekitar ~52 MB (termasuk engine Excel & Pandas lengkap). Tinggal pakai aja.

---

## Hal Penting yang Perlu Dipahami (Konteks "Klop" & Rekomendasi)

Meskipun angkanya sudah 100% benar, ada tiga catatan penting agar tidak salah paham saat memasukkannya ke Accurate:

1. **"Klop" di Sini Artinya Klop Konversi File (Bukan Buku Besar Accurate)**  
   Status **[Cocok / Klop]** di layar ini membuktikan bahwa file hasil konversi (CSV/XLS/JSON) sudah 100% identik dengan file asli tarikan bank (myBCA / KlikBCA / Panin). Artinya, tidak ada baris transaksi yang terlewat (*ke-skip*) dan tidak ada nominal yang berubah atau rusak akibat salah baca koma/titik saat dikonversi. Namun, Anda tetap perlu melakukan pencocokan (rekonsiliasi) dengan pencatatan jurnal di dalam Accurate setelah file ini diimpor.

2. **Sudut Pandang Debet & Kredit Menggunakan Istilah Bank**  
   Walaupun di judul tabel tertulis **Saldo Kas**, rumus yang dipakai adalah sudut pandang **Rekening Koran Bank**, di mana **Kredit = Uang Masuk (+)** dan **Debet = Uang Keluar (-)**. Ini sudah benar untuk keperluan impor mutasi bank (Smartlink e-Banking / Rekonsiliasi Bank) di Accurate Online, meskipun dalam jurnal akuntansi internal perusahaan posisinya berkebalikan (Kas/Bank bertambah di Debet dan berkurang di Kredit).

3. **Saran Pemilihan Template: Gunakan Template 1 (Format JSON AOL)**  
   Sangat disarankan mengutamakan **Template 1 (Format JSON AOL)** saat mengimpor ke Accurate Online. Format JSON resmi Accurate Online ini memiliki struktur skema data yang paling baku, stabil, dan tidak mudah terpengaruh oleh perubahan susunan kolom atau tata letak laporan dari pihak bank.

---

## Cara Pakai

Buat yang cuma mau pakai aplikasinya langsung:
1. Masuk ke halaman **[Releases](https://github.com/khairudinfahmi/Accurate_Format_Converter/releases)** di repositori ini.
2. Download file `.exe` yang paling baru (misalnya `Accurate_Converter_Setup_v5.0.0.exe`).
3. Install dan langsung jalankan. Nanti kalau ada update, aplikasinya bakal nge-update sendiri kok.

## Buat Developer

Kalau mau ikut ngembangin atau sekadar lihat-lihat kodenya, wajib banget baca dokumen-dokumen ini dulu biar nggak bingung:
1. **[`FORMAT_SPEC.md`](./FORMAT_SPEC.md)**: Ini panduan utama soal gimana struktur kolomnya dibikin biar Accurate nggak nolak pas di-import.
2. **[`BUILD_GUIDE.md`](./BUILD_GUIDE.md)**: Cara nge-build aplikasi menggunakan skrip sakti `build_all.ps1` yang sudah mengotomatisasi PyInstaller, Inno Setup, dan penyematan *Digital Signature*.
3. **[`AI.md`](./AI.md)**: Panduan arsitektur aplikasi buat referensi cepat.
