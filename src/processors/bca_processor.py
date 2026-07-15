import re
import csv
import pdfplumber
from utils.helpers import clean_currency

def _process_bca_csv(filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        log_callback("-" * 45)
        log_callback("Memulai proses konversi BCA (dari CSV)...")
        log_callback("-" * 45)
        progress_callback(0.1)
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            lines = list(reader)
        
        rekening = "1234567890"
        nama = "NASABAH BCA"
        saldo_awal = 0.0
        saldo_akhir = 0.0
        periode_raw = ""
        transactions = []
        
        data_started = False
        
        for i, row in enumerate(lines):
            if not row:
                continue
            
            line_str = "".join(row)
            
            if "No. rekening :" in line_str:
                match = re.search(r'No\.\s*rekening\s*:\s*(\d+)', line_str, re.IGNORECASE)
                if match: rekening = match.group(1)
            elif "Nama :" in line_str:
                match = re.search(r'Nama\s*:\s*(.*)', line_str, re.IGNORECASE)
                if match: nama = match.group(1).strip()
            elif "Periode :" in line_str:
                match = re.search(r'Periode\s*:\s*(.*)', line_str, re.IGNORECASE)
                if match: periode_raw = match.group(1).strip()
            elif "Saldo Awal :" in line_str:
                match = re.search(r'Saldo Awal\s*:\s*([\d\,\.]+)', line_str, re.IGNORECASE)
                if match: saldo_awal = clean_currency(match.group(1))
            elif "Saldo Akhir :" in line_str:
                match = re.search(r'Saldo Akhir\s*:\s*([\d\,\.]+)', line_str, re.IGNORECASE)
                if match: saldo_akhir = clean_currency(match.group(1))
            
            if len(row) >= 5 and "Tanggal Transaksi" in row[0] and "Keterangan" in row[1]:
                data_started = True
                continue
                
            if data_started:
                if len(row) >= 5 and re.match(r'\d{2}/\d{2}', row[0]):
                    tgl_match = re.search(r'(\d{2}/\d{2})', row[0])
                    tgl_clean = tgl_match.group(1) if tgl_match else row[0]
                    
                    desc = row[1]  # Preserve trailing spaces (jangan strip)
                    cabang = row[2].strip()
                    
                    jumlah_str = row[3].strip()
                    mutasi = 0.0
                    tipe = "CR"
                    if " CR" in jumlah_str.upper():
                        tipe = "CR"
                        mutasi = clean_currency(jumlah_str.upper().replace(" CR", ""))
                    elif " DB" in jumlah_str.upper():
                        tipe = "DB"
                        mutasi = clean_currency(jumlah_str.upper().replace(" DB", ""))
                    else:
                        mutasi = clean_currency(jumlah_str)
                    
                    saldo = clean_currency(row[4])
                    
                    transactions.append({
                        "tanggal": "'" + tgl_clean,
                        "keterangan": desc,
                        "cabang": "'" + cabang,
                        "mutasi": mutasi,
                        "tipe": tipe,
                        "saldo_printed": saldo,
                        "saldo": saldo
                    })
                    
        progress_callback(0.9)
        
        valid_count = len(transactions)
        log_callback("-" * 45)
        log_callback(f"Total Transaksi Valid: {valid_count}")
        log_callback(f"Saldo Awal: {saldo_awal:,.2f}")
        log_callback(f"Saldo Akhir: {saldo_akhir:,.2f}")
        log_callback("-" * 45)
        
        if valid_count == 0:
            raise Exception("File CSV berhasil dibaca, namun tidak ditemukan data transaksi BCA.")
        
        # Simpan metadata periode di transaksi pertama (untuk Format 3 generator)
        if periode_raw and transactions:
            transactions[0]["_periode_raw"] = periode_raw
            
        success_callback(transactions, rekening, nama, saldo_awal, saldo_akhir, filepath)
        
    except Exception as e:
        error_callback(str(e))

def process_bca(filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        if filepath.lower().endswith('.csv'):
            _process_bca_csv(filepath, log_callback, progress_callback, success_callback, error_callback)
            return

        log_callback("-" * 45)
        log_callback("Memulai proses konversi BCA...")
        log_callback("-" * 45)
        progress_callback(0.1)

        saldo_awal = 0.0
        rekening = ""
        nama = ""
        transactions = []
        all_lines = []
        
        with pdfplumber.open(filepath) as pdf:
            total_pages = len(pdf.pages)
            log_callback(f"PDF terdeteksi: {total_pages} halaman.")
            
            page0 = pdf.pages[0]
            text0 = page0.extract_text()
            if text0:
                lines = text0.split('\n')
                for line in lines:
                    if 'NO. REKENING' in line.upper():
                        match = re.search(r'NO\.\s*REKENING\s*:\s*(\d+)', line, re.IGNORECASE)
                        if match: rekening = match.group(1)
                
                words = page0.extract_words()
                for w in words:
                    if w['top'] > 70 and w['top'] < 90 and w['x0'] < 100:
                        if w['text'] not in ['NO.', 'REKENING', ':']:
                            nama += w['text'] + " "
                nama = nama.strip()[:240]
            
            if not rekening: rekening = "1234567890"
            if not nama: nama = "NASABAH BCA"

            log_callback(f"Rekening: {rekening} | Nama: {nama}")

            for page_idx, page in enumerate(pdf.pages):
                progress_callback(0.1 + (0.7 * (page_idx / total_pages)))
                words = page.extract_words()
                words.sort(key=lambda w: (round(w['top'], 1), w['x0']))
                
                lines = []
                current_y = -1
                current_line = []
                for w in words:
                    y = round(w['top'], 1)
                    if current_y == -1: current_y = y
                    if abs(y - current_y) > 3:
                        if current_line: lines.append(current_line)
                        current_line = []
                        current_y = y
                    current_line.append(w)
                if current_line: lines.append(current_line)
                
                for line in lines:
                    text_line = " ".join([w['text'] for w in line])
                    
                    if "SALDO AWAL" in text_line:
                        for w in reversed(line):
                            if w['x0'] > 480:
                                saldo_awal = clean_currency(w['text'])
                                break
                        continue
                        
                    if "TANGGAL KETERANGAN CBG MUTASI SALDO" in text_line: continue
                    if "MUTASI CR :" in text_line and "SALDO AKHIR :" in text_line: continue
                    if "Bersambung ke " in text_line: continue
                    
                    all_lines.append(line)
            
            y_blocks = []
            current_tx = []
            for line in all_lines:
                has_date = False
                for w in line:
                    is_date_fmt = bool(re.search(r'\d{2}/\d{2}', w['text'])) or "PEND" in w['text'].upper()
                    if w['x0'] < 85 and is_date_fmt:
                        has_date = True
                        break
                        
                if has_date:
                    if current_tx: y_blocks.append(current_tx)
                    current_tx = [line]
                else:
                    if current_tx: current_tx.append(line)
                    
            if current_tx: y_blocks.append(current_tx)
            
            for tx_lines in y_blocks:
                date = ""
                desc_parts = []
                mutasi = 0.0
                saldo_pr = None
                mutasi_zone_marker = None  # Marker DB/CR yang dicetak BCA di zona mutasi
                
                for line in tx_lines:
                    for w in line:
                        is_date_fmt = bool(re.search(r'\d{2}/\d{2}', w['text'])) or "PEND" in w['text'].upper()
                        if w['x0'] < 85 and is_date_fmt:
                            match = re.search(r'\d{2}/\d{2}', w['text'])
                            date = match.group(0) if match else "PEND"
                        elif 60 <= w['x0'] < 330:
                            desc_parts.append(w['text'])
                        elif 330 <= w['x0'] < 480:
                            if re.match(r'[\d\,]+\.\d{2}', w['text']):
                                mutasi = clean_currency(w['text'])
                            elif w['text'].strip().upper() in ('DB', 'CR'):
                                mutasi_zone_marker = w['text'].strip().upper()
                        elif w['x0'] >= 480:
                            if re.match(r'[\d\,]+\.\d{2}', w['text']):
                                saldo_pr = clean_currency(w['text'])
                                
                if not date: continue
                desc = " ".join(desc_parts).strip()
                if len(desc) > 240: desc = desc[:240]
                
                # --- Fase 1: Deteksi awal tipe via keyword + marker PDF ---
                tipe = "CR"
                desc_upper = desc.upper()
                
                # Prioritas 1: Marker DB/CR dari zona mutasi PDF (paling akurat)
                if mutasi_zone_marker == "DB":
                    tipe = "DB"
                elif mutasi_zone_marker == "CR":
                    tipe = "CR"
                # Prioritas 2: Deteksi via keyword di deskripsi
                elif desc_upper.startswith("DB ") or " DB" in desc_upper \
                   or "BIAYA" in desc_upper or "PAJAK" in desc_upper \
                   or "TARIKAN" in desc_upper or "POTONGAN" in desc_upper \
                   or "KARTU DEBIT" in desc_upper or "PEMBAYARAN" in desc_upper \
                   or "PEMBELIAN" in desc_upper or "SWITCHING DB" in desc_upper \
                   or "BYR VIA" in desc_upper:
                    tipe = "DB"
                elif " CR" in desc_upper or "SETORAN" in desc_upper or "BUNGA" in desc_upper:
                    tipe = "CR"
                    
                transactions.append({
                    "tanggal": "'" + date,
                    "keterangan": desc,
                    "cabang": "'0000",
                    "mutasi": mutasi,
                    "tipe": tipe,
                    "saldo_printed": saldo_pr
                })
        
        # --- Fase 2: Koreksi tipe menggunakan saldo sebagai sumber kebenaran ---
        current_balance = saldo_awal
        valid_count = 0
        for tx in transactions:
            mutasi_val = tx["mutasi"]
            
            if tx["saldo_printed"] is not None:
                actual = round(tx["saldo_printed"], 2)
                prev = round(current_balance, 2)
                diff = round(actual - prev, 2)
                
                # Tentukan tipe berdasarkan pergerakan saldo (sumber kebenaran)
                if abs(diff - mutasi_val) < 0.01:
                    # Saldo naik sebesar mutasi = CR (uang masuk)
                    tx["tipe"] = "CR"
                elif abs(diff + mutasi_val) < 0.01:
                    # Saldo turun sebesar mutasi = DB (uang keluar)
                    tx["tipe"] = "DB"
                # Jika tidak cocok keduanya, pertahankan tipe dari keyword
                
                current_balance = actual
            else:
                # Tidak ada saldo tercetak, gunakan tipe dari keyword
                if tx["tipe"] == "CR":
                    current_balance += mutasi_val
                else:
                    current_balance -= mutasi_val
            
            tx["saldo"] = round(current_balance, 2)
            valid_count += 1
            
            log_msg = f"T: {tx['tanggal'].replace('\'','')} | {tx['tipe']}: {tx['mutasi']:,.2f} | S: {tx['saldo']:,.2f}"
            log_callback(log_msg)
            
        log_callback("-" * 45)
        log_callback(f"Total Transaksi Valid: {valid_count}")
        log_callback(f"Saldo Awal: {saldo_awal:,.2f}")
        log_callback(f"Saldo Akhir: {current_balance:,.2f}")
        log_callback("-" * 45)
        
        if valid_count == 0:
            raise Exception("File PDF berhasil dibaca, namun tidak ditemukan data transaksi BCA. Pastikan file yang dipilih adalah mutasi rekening BCA yang valid.")
            
        progress_callback(0.9)
        success_callback(transactions, rekening, nama, saldo_awal, current_balance, filepath)
        
    except Exception as e:
        error_callback(str(e))
