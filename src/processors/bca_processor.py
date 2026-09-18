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

def _process_bca_giro_pdf(pdf, filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        log_callback("-" * 45)
        log_callback("Memulai proses konversi BCA (Format Giro / KlikBCA Bisnis)...")
        log_callback("-" * 45)
        progress_callback(0.1)

        total_pages = len(pdf.pages)
        log_callback(f"PDF terdeteksi: {total_pages} halaman.")

        page0 = pdf.pages[0]
        text0 = page0.extract_text() or ""
        
        rekening = "1234567890"
        nama = "NASABAH BCA"
        periode_raw = ""
        
        rek_m = re.search(r'(?:Nomor\s*Rekening|No\.\s*Rekening)\s*:?\s*(\d+)', text0, re.IGNORECASE)
        if rek_m:
            rekening = rek_m.group(1)
            
        nama_m = re.search(r'Nama\s*Rekening\s*:?\s*([^\n\r]+)', text0, re.IGNORECASE)
        if nama_m:
            nama = nama_m.group(1).strip()[:240]
            
        per_m = re.search(r'Periode\s*:?\s*([^\n\r]+)', text0, re.IGNORECASE)
        if per_m:
            periode_raw = per_m.group(1).strip()
            
        log_callback(f"Rekening: {rekening} | Nama: {nama}")
        if periode_raw:
            log_callback(f"Periode: {periode_raw}")

        saldo_awal = None
        saldo_akhir = None
        mutasi_kredit_summary = None
        mutasi_debit_summary = None
        full_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        sa_m = re.search(r'Saldo\s*Awal\s*:?\s*([\d\,\.]+)', full_text, re.IGNORECASE)
        if sa_m:
            saldo_awal = clean_currency(sa_m.group(1))
        sk_m = re.search(r'Saldo\s*Akhir\s*:?\s*([\d\,\.]+)', full_text, re.IGNORECASE)
        if sk_m:
            saldo_akhir = clean_currency(sk_m.group(1))
        mk_m = re.search(r'Mutasi\s*Kredit\s*:?\s*([\d\,\.]+)', full_text, re.IGNORECASE)
        if mk_m:
            mutasi_kredit_summary = clean_currency(mk_m.group(1))
        md_m = re.search(r'Mutasi\s*Debit\s*:?\s*([\d\,\.]+)', full_text, re.IGNORECASE)
        if md_m:
            mutasi_debit_summary = clean_currency(md_m.group(1))

        raw_tx_blocks = []
        for page_idx, page in enumerate(pdf.pages):
            progress_callback(0.1 + (0.7 * (page_idx / total_pages)))
            words = page.extract_words()
            words.sort(key=lambda w: (round(w['top'], 1), w['x0']))
            
            lines = []
            current_y = -1
            current_line = []
            for w in words:
                y = round(w['top'], 1)
                if current_y == -1:
                    current_y = y
                if abs(y - current_y) > 3:
                    if current_line:
                        lines.append(current_line)
                    current_line = []
                    current_y = y
                current_line.append(w)
            if current_line:
                lines.append(current_line)
                
            for line in lines:
                text_line = " ".join([w['text'] for w in line])
                upper_line = text_line.upper()
                
                if "DETAIL MUTASI" in upper_line: continue
                if "TANGGAL EFEKTIF" in upper_line or "KETERANGAN CABANG" in upper_line: continue
                if "TOTAL TRANSAKSI" in upper_line: continue
                if "SALDO AWAL" in upper_line or "MUTASI KREDIT" in upper_line or "MUTASI DEBIT" in upper_line or "SALDO AKHIR" in upper_line: continue
                if "DI-REQUEST OLEH" in upper_line or "MUTASI REKENING" in upper_line: continue
                if "NAMA REKENING" in upper_line or "NOMOR REKENING" in upper_line or "JENIS REKENING" in upper_line or "PERIODE" in upper_line: continue
                
                has_date_start = False
                for w in line:
                    if w['x0'] < 115 and re.match(r'^\d{2}/\d{2}', w['text']):
                        has_date_start = True
                        break
                        
                if has_date_start:
                    raw_tx_blocks.append([line])
                else:
                    if raw_tx_blocks:
                        raw_tx_blocks[-1].append(line)
                        
        transactions = []
        for tx_block in raw_tx_blocks:
            date = ""
            desc_parts = []
            cabang = "0000"
            debet_val = 0.0
            kredit_val = 0.0
            saldo_pr = None
            
            for line in tx_block:
                for w in line:
                    t = w['text'].strip()
                    x0 = w['x0']
                    
                    if 60 <= x0 < 115 and re.match(r'^\d{2}/\d{2}', t):
                        m = re.search(r'^\d{2}/\d{2}', t)
                        if m and not date:
                            date = m.group(0)
                    elif 140 <= x0 < 280:
                        desc_parts.append(t)
                    elif 280 <= x0 < 315 and re.match(r'^\d{4}$', t):
                        cabang = t
                    elif 360 <= x0 < 425:
                        if re.match(r'^[\d\,]+\.\d{2}$', t):
                            debet_val = clean_currency(t)
                    elif 425 <= x0 < 490:
                        if re.match(r'^[\d\,]+\.\d{2}$', t):
                            kredit_val = clean_currency(t)
                    elif x0 >= 490:
                        if re.match(r'^[\d\,]+\.\d{2}$', t):
                            saldo_pr = clean_currency(t)
                            
            if not date:
                continue
                
            desc = " ".join(desc_parts).strip()
            if len(desc) > 240:
                desc = desc[:240]
                
            if debet_val > 0:
                tipe = "DB"
                mutasi = debet_val
            elif kredit_val > 0:
                tipe = "CR"
                mutasi = kredit_val
            else:
                tipe = "CR"
                mutasi = 0.0
                
            transactions.append({
                "tanggal": "'" + date,
                "keterangan": desc,
                "cabang": "'" + cabang,
                "mutasi": mutasi,
                "tipe": tipe,
                "saldo_printed": saldo_pr
            })
            
        if not transactions:
            raise Exception("File PDF berhasil dibaca, namun tidak ditemukan transaksi mutasi BCA Giro yang valid.")
            
        if saldo_awal is None:
            first_tx = transactions[0]
            if first_tx["saldo_printed"] is not None:
                if first_tx["tipe"] == "DB":
                    saldo_awal = round(first_tx["saldo_printed"] + first_tx["mutasi"], 2)
                else:
                    saldo_awal = round(first_tx["saldo_printed"] - first_tx["mutasi"], 2)
            else:
                saldo_awal = 0.0

        current_balance = saldo_awal
        valid_count = 0
        for tx in transactions:
            mutasi_val = tx["mutasi"]
            
            # --- Fase 2 (Giro): Validasi Silang Matematika Saldo (Self-Healing Fail-Safe) ---
            if tx["saldo_printed"] is not None:
                actual = round(tx["saldo_printed"], 2)
                prev = round(current_balance, 2)
                diff = round(actual - prev, 2)
                
                # Koreksi jika terjadi pergeseran kolom atau anomali cetak
                if abs(diff - mutasi_val) < 0.01:
                    tx["tipe"] = "CR"
                elif abs(diff + mutasi_val) < 0.01:
                    tx["tipe"] = "DB"
                elif abs(abs(diff) - mutasi_val) < 0.01:
                    tx["tipe"] = "CR" if diff > 0 else "DB"
                    
                current_balance = actual
            else:
                if tx["tipe"] == "CR":
                    current_balance += mutasi_val
                else:
                    current_balance -= mutasi_val
                current_balance = round(current_balance, 2)
                
            tx["saldo"] = current_balance
            valid_count += 1
            
            log_msg = f"T: {tx['tanggal'].replace('\'','')} | {tx['tipe']}: {tx['mutasi']:,.2f} | S: {tx['saldo']:,.2f}"
            log_callback(log_msg)
            
        total_debet = sum(tx["mutasi"] for tx in transactions if tx["tipe"] == "DB")
        total_kredit = sum(tx["mutasi"] for tx in transactions if tx["tipe"] == "CR")
        
        log_callback("-" * 45)
        log_callback(f"Total Transaksi Valid: {valid_count}")
        log_callback(f"Saldo Awal: {saldo_awal:,.2f}")
        log_callback(f"Total Mutasi Debet : {total_debet:,.2f}")
        log_callback(f"Total Mutasi Kredit: {total_kredit:,.2f}")
        log_callback(f"Saldo Akhir: {current_balance:,.2f}")
        
        # Validasi Rekonsiliasi Otomatis terhadap Ringkasan Bank
        if mutasi_debit_summary is not None and abs(total_debet - mutasi_debit_summary) < 0.01:
            log_callback(f"[AUDIT] Mutasi Debit 100% cocok dengan ringkasan bank (Rp {total_debet:,.2f})")
        if mutasi_kredit_summary is not None and abs(total_kredit - mutasi_kredit_summary) < 0.01:
            log_callback(f"[AUDIT] Mutasi Kredit 100% cocok dengan ringkasan bank (Rp {total_kredit:,.2f})")
        if saldo_akhir is not None and abs(current_balance - saldo_akhir) < 0.01:
            log_callback(f"[AUDIT] Saldo Akhir 100% cocok dengan ringkasan bank (Rp {current_balance:,.2f})")
        log_callback("-" * 45)

        if periode_raw and transactions:
            transactions[0]["_periode_raw"] = periode_raw

        progress_callback(0.9)
        success_callback(transactions, rekening, nama, saldo_awal, current_balance, filepath)

    except Exception as e:
        error_callback(str(e))

def _process_bca_tahapan_pdf(pdf, filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        log_callback("-" * 45)
        log_callback("Memulai proses konversi BCA (Format Tahapan / Individu)...")
        log_callback("-" * 45)
        progress_callback(0.1)

        saldo_awal = 0.0
        rekening = ""
        nama = ""
        transactions = []
        all_lines = []
        
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
                
                if "SALDO AWAL" in text_line.upper():
                    for w in reversed(line):
                        if w['x0'] > 480:
                            saldo_awal = clean_currency(w['text'])
                            break
                    continue
                    
                if "TANGGAL KETERANGAN CBG MUTASI SALDO" in text_line.upper(): continue
                if "MUTASI CR :" in text_line.upper() and "SALDO AKHIR :" in text_line.upper(): continue
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
                    tx["tipe"] = "CR"
                elif abs(diff + mutasi_val) < 0.01:
                    tx["tipe"] = "DB"
                
                current_balance = actual
            else:
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

def process_bca(filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        if filepath.lower().endswith('.csv'):
            _process_bca_csv(filepath, log_callback, progress_callback, success_callback, error_callback)
            return

        with pdfplumber.open(filepath) as pdf:
            page0 = pdf.pages[0]
            text0 = page0.extract_text() or ""
            upper0 = text0.upper()
            
            is_giro = "DETAIL MUTASI" in upper0 or ("DEBIT" in upper0 and "KREDIT" in upper0 and "NO REFERENSI" in upper0) or "JENIS REKENING GIRO" in upper0
            
            if is_giro:
                _process_bca_giro_pdf(pdf, filepath, log_callback, progress_callback, success_callback, error_callback)
            else:
                _process_bca_tahapan_pdf(pdf, filepath, log_callback, progress_callback, success_callback, error_callback)
                
    except Exception as e:
        error_callback(str(e))
