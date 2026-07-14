# Accurate Format Converter

Aplikasi kecil buat bantu convert file mutasi rekening bank (kayak BCA atau Panin) jadi format yang siap di-import langsung ke **Accurate Online**. 

Nggak perlu lagi ngedit-ngedit manual di Excel yang bikin pusing, aplikasi ini udah ngurusin format tanggal, posisi kolom debit/kredit, sampai nambahin baris kosong (*dummy rows*) yang diminta sama sistem Accurate.

---

## Fiturnya Apa Aja?

*   **Bisa banyak Bank:** 
    *   **BCA:** Bisa baca mutasi dari file PDF. Logikanya udah diatur sedemikian rupa supaya bisa bedain mana uang masuk (CR) dan keluar (DB) dengan tepat.
    *   **Panin:** Bisa baca dari PDF, XLS, maupun CSV. Udah ditangani juga misal ada kolom Excel yang agak geser.
*   **Format Dijamin Pas:** Hasil jadinya (file XLS atau CSV) udah pas 5 kolom sesuai standar impor Accurate. Termasuk otomatis nambahin 7 baris *dummy* biar datanya nggak kepotong pas di-import.
*   **Aman dari Tanggal Error:** Kalau ada tanggal transaksi yang aneh atau nggak kebaca, barisnya bakal dipisah ke file tersendiri biar nggak ngerusak data utama.
*   **Update Otomatis:** Kalau ada versi baru, aplikasi bakal otomatis download dan install sendiri di latar belakang tanpa ribet.
*   **Ringan Banget:** Udah di-build pakai PyInstaller dengan rapi, sizenya cuma sekitar 68MB. Tinggal pakai aja.

## Cara Pakai

Buat yang cuma mau pakai aplikasinya langsung:
1. Masuk ke halaman **[Releases](https://github.com/khairudinfahmi/Accurate_Format_Converter/releases)** di repositori ini.
2. Download file `.exe` yang paling baru (misalnya `Accurate_Converter_Setup_v4.1.exe`).
3. Install dan langsung jalankan. Nanti kalau ada update, aplikasinya bakal nge-update sendiri kok.

## Buat Developer

Kalau mau ikut ngembangin atau sekadar lihat-lihat kodenya, wajib banget baca dokumen-dokumen ini dulu biar nggak bingung:
1. **[`FORMAT_SPEC.md`](./FORMAT_SPEC.md)**: Ini panduan utama soal gimana struktur kolomnya dibikin biar Accurate nggak nolak pas di-import.
2. **[`BUILD_GUIDE.md`](./BUILD_GUIDE.md)**: Cara nge-build aplikasi ini jadi `.exe` yang ringan dan cara nambahin *Self-Signed Signature* (menggunakan file `.pfx`).
3. **[`AI.md`](./AI.md)**: Panduan arsitektur aplikasi buat referensi cepat.

