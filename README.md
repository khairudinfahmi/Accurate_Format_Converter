# Accurate Format Converter

Aplikasi kecil buat bantu convert file mutasi rekening bank (kayak BCA atau Panin) jadi format yang siap di-import langsung ke **Accurate Online**. 

Nggak perlu lagi ngedit-ngedit manual di Excel yang bikin pusing, aplikasi ini udah ngurusin format tanggal, posisi kolom debit/kredit, sampai nambahin baris kosong (*dummy rows*) yang diminta sama sistem Accurate.

---

## Fiturnya Apa Aja?

*   **Bisa banyak Bank:** 
    *   **BCA:** Bisa membaca mutasi dari file **CSV (KlikBCA Asli)**. Logikanya udah diatur sedemikian rupa supaya bisa bedain mana uang masuk (CR) dan keluar (DB) dengan tepat. Output BCA juga super rapi karena otomatis **dibungkus ke dalam 1 folder** yang berisi 3 file (CSV Standar, Excel Formatter, dan KlikBCA CSV).
    *   **Panin:** Bisa baca dari PDF, XLS, maupun CSV. Udah ditangani juga misal ada kolom Excel yang agak geser.
*   **Format Dijamin Pas:** Hasil jadinya (file XLS atau CSV) udah pas 5 kolom sesuai standar impor Accurate. Termasuk otomatis nambahin baris *dummy* biar datanya nggak kepotong pas di-import.
*   **Aman dari Tanggal Error:** Kalau ada tanggal transaksi yang aneh atau nggak kebaca, barisnya bakal dipisah ke file tersendiri biar nggak ngerusak data utama.
*   **Update Otomatis:** Kalau ada versi baru, aplikasi bakal otomatis download dan install sendiri di latar belakang tanpa ribet.
*   **Aman dari SmartScreen (Baru):** Installer secara otomatis akan menginjeksi Digital Certificate ke *Trusted Root* PC Anda sehingga terhindar dari pemblokiran Windows Defender SmartScreen.
*   **Ringan Banget:** Udah di-build pakai PyInstaller & Inno Setup dengan rapi, ukuran installernya cuma sekitar ~66 MB (termasuk engine Excel & Pandas lengkap). Tinggal pakai aja.

## Cara Pakai

Buat yang cuma mau pakai aplikasinya langsung:
1. Masuk ke halaman **[Releases](https://github.com/khairudinfahmi/Accurate_Format_Converter/releases)** di repositori ini.
2. Download file `.exe` yang paling baru (misalnya `Accurate_Converter_Setup_v4.2.exe`).
3. Install dan langsung jalankan. Nanti kalau ada update, aplikasinya bakal nge-update sendiri kok.

## Buat Developer

Kalau mau ikut ngembangin atau sekadar lihat-lihat kodenya, wajib banget baca dokumen-dokumen ini dulu biar nggak bingung:
1. **[`FORMAT_SPEC.md`](./FORMAT_SPEC.md)**: Ini panduan utama soal gimana struktur kolomnya dibikin biar Accurate nggak nolak pas di-import.
2. **[`BUILD_GUIDE.md`](./BUILD_GUIDE.md)**: Cara nge-build aplikasi menggunakan skrip sakti `build_all.ps1` yang sudah mengotomatisasi PyInstaller, Inno Setup, dan penyematan *Digital Signature*.
3. **[`AI.md`](./AI.md)**: Panduan arsitektur aplikasi buat referensi cepat.
