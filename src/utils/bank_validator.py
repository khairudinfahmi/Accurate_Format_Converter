import os
import re

def detect_bank_from_file(filepath: str) -> tuple[str | None, str]:
    """
    Mendeteksi bank sumber dari file mutasi rekening (PDF, CSV, XLS, XLSX).
    Mengembalikan (nama_bank, alasan_deteksi).
    Nama bank: 'BCA', 'Panin', 'Mandiri', 'BRI', 'BNI', atau None.
    """
    if not filepath or not os.path.exists(filepath):
        return None, "File tidak ditemukan"

    ext = os.path.splitext(filepath)[1].lower()

    # -------------------------------------------------------------
    # 1. PENDETEKSIAN DOKUMEN PDF
    # -------------------------------------------------------------
    if ext == '.pdf':
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                if not pdf.pages:
                    return None, "Dokumen PDF kosong (tanpa halaman)"

                extracted_texts = []
                # Periksa hingga 3 halaman pertama untuk menangkap metadata & header tabel
                for p in pdf.pages[:3]:
                    t = p.extract_text()
                    if t:
                        extracted_texts.append(t)

                full_text = " ".join(extracted_texts)
                upper = full_text.upper()

                # --- A. DETEKSI TANDA TANGAN BCA (GIRO & TAHAPAN) ---
                is_bca_multi_column = (
                    ("DETAIL MUTASI" in upper and "NO REFERENSI" in upper) or
                    ("KEY BCA" in upper) or
                    ("TANGGAL EFEKTIF" in upper and "TANGGAL TRANSAKSI" in upper and "CABANG" in upper) or
                    ("MUTASI REKENING" in upper and "NO REFERENSI" in upper)
                )
                is_bca_statement = (
                    ("TANGGAL KETERANGAN CBG MUTASI SALDO" in upper) or
                    ("MUTASI CR :" in upper and "SALDO AWAL :" in upper) or
                    ("MUTASI CR" in upper and "MUTASI DB" in upper and "SALDO AKHIR" in upper) or
                    ("BCA" in upper and "SALDO AWAL" in upper and "CBG" in upper) or
                    ("REKENING GIRO" in upper or "REKENING TAHAPAN" in upper)
                )
                is_bca_general = "BANK CENTRAL ASIA" in upper or "KLIKBCA" in upper or "WWW.KLIKBCA.COM" in upper

                if is_bca_multi_column or is_bca_statement or is_bca_general:
                    if is_bca_multi_column:
                        subtype = "Giro" if "GIRO" in upper else ("Tahapan" if "TAHAPAN" in upper else "")
                        detail = f"BCA Mutasi Rekening {subtype} (KlikBCA Bisnis / myBCA)".replace("  ", " ")
                    else:
                        subtype = "Giro" if ("REKENING GIRO" in upper or ("GIRO" in upper and "TAHAPAN" not in upper)) else ("Tahapan" if "TAHAPAN" in upper else "Tahapan / Giro")
                        detail = f"BCA e-Statement ({subtype})"
                    return "BCA", f"Terdeteksi {detail}"

                # --- B. DETEKSI TANDA TANGAN PANIN ---
                panin_strong_sigs = [
                    "PANIN", "PANINBANK", "BANK PANIN", "PT BANK PANIN",
                    "DETIL REKENING", "SILAHKAN PILIH PERIODE", "MUTASI BULANAN :",
                    "INFORMASI MUTASI HARIAN", "MUTASI BULANAN MENUNJUKKAN",
                    "TANGGAL DESKRIPSI DEBIT KREDIT SALDO"
                ]
                if any(sig in upper for sig in panin_strong_sigs):
                    return "Panin", "Terdeteksi e-Statement resmi Bank Panin"

                # Cek kemungkinan Panin Scanned PDF (Vektor teks minimal / Scan)
                words_count = sum(len(p.extract_words()) for p in pdf.pages[:2])
                if words_count <= 10:
                    total_pages = len(pdf.pages)
                    basename = os.path.basename(filepath).lower()
                    if total_pages in [4, 22] or "scanned" in basename or "camscanner" in basename or "panin" in basename:
                        return "Panin", "Terdeteksi dokumen hasil scan mutasi Panin"

                # --- C. DETEKSI BANK LAIN ---
                if "MANDIRI" in upper or "LIVIN" in upper or "KOPRA" in upper:
                    return "Mandiri", "Terdeteksi dokumen Bank Mandiri"
                if "BANK RAKYAT INDONESIA" in upper or "BRIMO" in upper or "BANK BRI" in upper:
                    return "BRI", "Terdeteksi dokumen Bank BRI"
                if "BANK NEGARA INDONESIA" in upper or "BNIDIRECT" in upper or "BANK BNI" in upper:
                    return "BNI", "Terdeteksi dokumen Bank BNI"

        except Exception as e:
            return None, f"Gagal membaca PDF: {e}"

    # -------------------------------------------------------------
    # 2. PENDETEKSIAN FILE CSV
    # -------------------------------------------------------------
    elif ext == '.csv':
        try:
            with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                lines = [f.readline() for _ in range(30)]
            text = "".join(lines).upper().replace('""', '"')
            base_upper = os.path.basename(filepath).upper()

            # Format CSV BCA (KlikBCA Individu, Giro, myBCA, Template BCA)
            if "NO. REKENING" in text or ("TANGGAL" in text and "KETERANGAN" in text and ("CABANG" in text or "MUTASI" in text or "SALDO" in text)):
                if "MUTASI" in text and "JENIS TRANSAKSI" in text:
                    return "BCA", "Terdeteksi format CSV resmi BCA (myBCA / KlikBCA)"
                if "JUMLAH" in text and "SALDO" in text:
                    return "BCA", "Terdeteksi template CSV mutasi BCA"
                if "TANGGAL TRANSAKSI" in text:
                    return "BCA", "Terdeteksi format CSV resmi BCA (myBCA / KlikBCA)"
                if "MUTASIREKENING_" in base_upper or "BCA" in base_upper:
                    return "BCA", "Terdeteksi format CSV mutasi BCA"

            # Format CSV Panin
            if "PANIN" in text or ("TANGGAL" in text and "SALDO" in text and ("DEBET" in text or "DEBIT" in text) and "KREDIT" in text):
                return "Panin", "Terdeteksi format CSV mutasi Panin"

            if "MANDIRI" in text:
                return "Mandiri", "Terdeteksi format CSV Bank Mandiri"

            if "MUTASIREKENING_" in base_upper:
                return "BCA", "Terdeteksi dokumen mutasi BCA"

        except Exception as e:
            return None, f"Gagal membaca CSV: {e}"

    # -------------------------------------------------------------
    # 3. PENDETEKSIAN FILE EXCEL (.XLS / .XLSX)
    # -------------------------------------------------------------
    elif ext in ['.xls', '.xlsx']:
        try:
            import pandas as pd
            base_upper = os.path.basename(filepath).upper()
            # Baca beberapa baris pertama secara toleran
            df = pd.read_excel(filepath, nrows=25, header=None)
            raw_str = " ".join(df.astype(str).values.flatten()).upper()

            if "BCA" in raw_str or "NO. REKENING :" in raw_str:
                return "BCA", "Terdeteksi data mutasi BCA dalam format Excel"

            if "MUTASI" in raw_str and "JENIS TRANSAKSI" in raw_str and "SALDO" in raw_str:
                return "BCA", "Terdeteksi data mutasi BCA (myBCA) dalam format Excel"

            if "MUTASIREKENING_" in base_upper:
                return "BCA", "Terdeteksi data mutasi BCA dalam format Excel"

            if "PANIN" in raw_str or "DETIL REKENING" in raw_str or ("TANGGAL" in raw_str and "SALDO" in raw_str and ("DEBET" in raw_str or "DEBIT" in raw_str) and "KREDIT" in raw_str):
                return "Panin", "Terdeteksi format mutasi Panin Excel"

            if "MANDIRI" in raw_str:
                return "Mandiri", "Terdeteksi format Excel Bank Mandiri"

        except Exception:
            # Fallback jika Excel engine gagal di tahap deteksi awal
            pass

    return None, "Format tidak teridentifikasi spesifik"

def validate_bank_selection(filepath: str, selected_bank: str) -> tuple[bool, str, str | None]:
    """
    Memvalidasi kesesuaian file mutasi dengan bank yang dipilih di UI.
    Mengembalikan (is_valid, pesan_error, detected_bank).
    """
    detected_bank, reason = detect_bank_from_file(filepath)

    # Kasus 1: Bank terdeteksi dan TIDAK cocok dengan bank yang dipilih
    if detected_bank and detected_bank.lower() != selected_bank.lower():
        if detected_bank in ["Mandiri", "BRI", "BNI"]:
            msg = (
                f"File yang Anda pilih terdeteksi sebagai dokumen mutasi Bank {detected_bank}.\n\n"
                f"Keterangan: {reason}\n\n"
                f"Aplikasi saat ini hanya mendukung konversi mutasi Bank BCA dan Bank Panin."
            )
        else:
            msg = (
                f"File yang Anda pilih terdeteksi sebagai dokumen mutasi Bank {detected_bank}, "
                f"bukan Bank {selected_bank}.\n\n"
                f"Keterangan: {reason}\n\n"
                f"Sistem menolak memproses untuk mencegah data rusak pada format Accurate.\n"
                f"Silakan ubah pilihan bank menjadi '{detected_bank}' pada menu di sudut kanan atas."
            )
        return False, msg, detected_bank

    # Kasus 2: Bank terdeteksi dan COCOK dengan bank yang dipilih
    if detected_bank and detected_bank.lower() == selected_bank.lower():
        return True, "", detected_bank

    # Kasus 3: Bank tidak terdeteksi secara spesifik
    ext = os.path.splitext(filepath)[1].lower()
    
    # Validasi ekstensi dasar
    if selected_bank == "BCA":
        if ext not in ['.pdf', '.csv', '.xlsx', '.xls']:
            msg = f"Format file '{ext}' tidak didukung untuk Bank BCA. Mutasi BCA harus dalam format PDF, CSV, atau Excel (.xlsx/.xls)."
            return False, msg, None
    elif selected_bank == "Panin":
        if ext not in ['.xls', '.xlsx', '.csv', '.pdf']:
            msg = f"Format file '{ext}' tidak didukung untuk Bank Panin. Format yang didukung: .xls, .xlsx, .csv, .pdf."
            return False, msg, None

    # Jika file berekstensi valid namun tanpa signature bank yang jelas (misal file CSV custom)
    return True, "", None
