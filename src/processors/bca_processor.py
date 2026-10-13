import re
import csv
import itertools
import pdfplumber
from utils.helpers import clean_currency

def _reconcile_bca_transactions(transactions, saldo_awal, log_callback):
    """
    Rekonsiliasi matematis saldo berjenjang dengan Look-Ahead Cluster Solver:
    - Jika saldo tercetak ada di setiap baris: evaluasi langsung per baris.
    - Jika ada baris tanpa saldo tercetak sebelum baris dengan saldo tercetak (cluster multi-transaksi):
      selesaikan kombinasi tanda (+ / -) mutasi agar total perubahan sama persis dengan saldo akhir cluster.
    """
    current_balance = saldo_awal
    n = len(transactions)
    i = 0
    valid_count = 0
    
    while i < n:
        j = i
        while j < n and transactions[j].get("saldo_printed") is None:
            j += 1
            
        if j < n:
            target_balance = transactions[j]["saldo_printed"]
            expected_diff = round(target_balance - current_balance, 2)
            cluster_len = j - i + 1
            
            # Cek apakah tebakan awal sudah cocok
            current_sum = sum((tx["mutasi"] if tx["tipe"] == "CR" else -tx["mutasi"]) for tx in transactions[i:j+1])
            if abs(current_sum - expected_diff) > 0.01:
                solved = False
                
                # Strategi 1: Single-Flip Solver O(N) - jika hanya 1 transaksi yang salah tanda
                for idx_c in range(cluster_len):
                    tx_c = transactions[i + idx_c]
                    # Jika saat ini CR dihitung +m, bila diubah jadi DB perubahannya -2m
                    delta = -2 * tx_c["mutasi"] if tx_c["tipe"] == "CR" else 2 * tx_c["mutasi"]
                    if abs((current_sum + delta) - expected_diff) < 0.01:
                        tx_c["tipe"] = "DB" if tx_c["tipe"] == "CR" else "CR"
                        solved = True
                        break
                
                # Strategi 2: Double-Flip Solver O(N^2) - jika ada 2 transaksi yang salah tanda
                if not solved and cluster_len > 1:
                    for idx_a, idx_b in itertools.combinations(range(cluster_len), 2):
                        tx_a = transactions[i + idx_a]
                        tx_b = transactions[i + idx_b]
                        delta_a = -2 * tx_a["mutasi"] if tx_a["tipe"] == "CR" else 2 * tx_a["mutasi"]
                        delta_b = -2 * tx_b["mutasi"] if tx_b["tipe"] == "CR" else 2 * tx_b["mutasi"]
                        if abs((current_sum + delta_a + delta_b) - expected_diff) < 0.01:
                            tx_a["tipe"] = "DB" if tx_a["tipe"] == "CR" else "CR"
                            tx_b["tipe"] = "DB" if tx_b["tipe"] == "CR" else "CR"
                            solved = True
                            break
                            
                # Strategi 3: Combinatorial Search 2^N (untuk cluster kompleks <= 14)
                if not solved and cluster_len <= 14:
                    best_combo = None
                    min_err = 999999999.0
                    for signs in itertools.product([1, -1], repeat=cluster_len):
                        combo_sum = sum(s * tx["mutasi"] for s, tx in zip(signs, transactions[i:j+1]))
                        err = abs(combo_sum - expected_diff)
                        if err < 0.01:
                            best_combo = signs
                            min_err = err
                            break
                        elif err < min_err:
                            min_err = err
                            best_combo = signs
                            
                    if best_combo and min_err < 0.01:
                        for idx_c, s in enumerate(best_combo):
                            transactions[i + idx_c]["tipe"] = "CR" if s > 0 else "DB"
                        solved = True
                elif not solved and cluster_len == 1:
                    mut = transactions[i]["mutasi"]
                    if abs(expected_diff - mut) < 0.01:
                        transactions[i]["tipe"] = "CR"
                    elif abs(expected_diff + mut) < 0.01:
                        transactions[i]["tipe"] = "DB"
                    elif abs(abs(expected_diff) - mut) < 0.01:
                        transactions[i]["tipe"] = "CR" if expected_diff > 0 else "DB"
                        
            # Jalankan pergerakan saldo sepanjang cluster
            for k in range(i, j + 1):
                m = transactions[k]["mutasi"]
                if transactions[k]["tipe"] == "CR":
                    current_balance += m
                else:
                    current_balance -= m
                transactions[k]["saldo"] = round(current_balance, 2)
                valid_count += 1
                log_msg = f"T: {transactions[k]['tanggal'].replace('\'','')} | {transactions[k]['tipe']}: {transactions[k]['mutasi']:,.2f} | S: {transactions[k]['saldo']:,.2f}"
                log_callback(log_msg)
                
            current_balance = round(target_balance, 2)
            transactions[j]["saldo"] = current_balance
            i = j + 1
        else:
            for k in range(i, n):
                m = transactions[k]["mutasi"]
                if transactions[k]["tipe"] == "CR":
                    current_balance += m
                else:
                    current_balance -= m
                transactions[k]["saldo"] = round(current_balance, 2)
                valid_count += 1
                log_msg = f"T: {transactions[k]['tanggal'].replace('\'','')} | {transactions[k]['tipe']}: {transactions[k]['mutasi']:,.2f} | S: {transactions[k]['saldo']:,.2f}"
                log_callback(log_msg)
            break
            
    total_debet = sum(tx["mutasi"] for tx in transactions if tx["tipe"] == "DB")
    total_kredit = sum(tx["mutasi"] for tx in transactions if tx["tipe"] == "CR")
    
    return transactions, current_balance, valid_count, total_debet, total_kredit

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
        mutasi_debet_summary = None
        mutasi_kredit_summary = None
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
            elif "Mutasi Debet :" in line_str or "Mutasi Debit :" in line_str:
                match = re.search(r'Mutasi\s*Deb[ei]t\s*:\s*([\d\,\.]+)', line_str, re.IGNORECASE)
                if match: mutasi_debet_summary = clean_currency(match.group(1))
            elif "Mutasi Kredit :" in line_str:
                match = re.search(r'Mutasi\s*Kredit\s*:\s*([\d\,\.]+)', line_str, re.IGNORECASE)
                if match: mutasi_kredit_summary = clean_currency(match.group(1))
            
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
                    j_upper = jumlah_str.upper()
                    if " CR" in j_upper or j_upper.endswith("CR") or re.search(r'\bCR\b', j_upper):
                        tipe = "CR"
                        mutasi = clean_currency(re.sub(r'CR', '', j_upper, flags=re.IGNORECASE))
                    elif " DB" in j_upper or j_upper.endswith("DB") or re.search(r'\bDB\b', j_upper):
                        tipe = "DB"
                        mutasi = clean_currency(re.sub(r'DB', '', j_upper, flags=re.IGNORECASE))
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
                    
        if not transactions:
            raise Exception("File CSV berhasil dibaca, namun tidak ditemukan data transaksi BCA.")

        # --- Fase 2 (CSV): Validasi Silang Matematika Saldo (Self-Healing Fail-Safe) ---
        transactions, current_balance, valid_count, total_debet, total_kredit = _reconcile_bca_transactions(
            transactions, saldo_awal, log_callback
        )
        
        progress_callback(0.9)
        
        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan CSV BCA",
            "saldo_awal": saldo_awal,
            "debet": mutasi_debet_summary if mutasi_debet_summary is not None else total_debet,
            "kredit": mutasi_kredit_summary if mutasi_kredit_summary is not None else total_kredit,
            "saldo_akhir": saldo_akhir if saldo_akhir > 0 else current_balance,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count": valid_count
        }
        audit_table = format_audit_reconciliation_table("BCA CSV", source_summary, output_summary)
        log_callback("\n" + audit_table)
        transactions[0]["_audit_table"] = audit_table
        
        # Simpan metadata periode di transaksi pertama (untuk Format 3 generator)
        if periode_raw and transactions:
            transactions[0]["_periode_raw"] = periode_raw
            
        success_callback(transactions, rekening, nama, saldo_awal, current_balance, filepath)
        
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
                        if re.match(r'^[\d\.,]+$', t) and any(c.isdigit() for c in t) and not re.search(r'[a-zA-Z]', t):
                            debet_val = clean_currency(t)
                    elif 425 <= x0 < 490:
                        if re.match(r'^[\d\.,]+$', t) and any(c.isdigit() for c in t) and not re.search(r'[a-zA-Z]', t):
                            kredit_val = clean_currency(t)
                    elif x0 >= 490:
                        if re.match(r'^[\d\.,]+$', t) and any(c.isdigit() for c in t) and not re.search(r'[a-zA-Z]', t):
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

        # --- Fase 2 (Giro): Validasi Silang Matematika Saldo (Self-Healing Fail-Safe) ---
        transactions, current_balance, valid_count, total_debet, total_kredit = _reconcile_bca_transactions(
            transactions, saldo_awal, log_callback
        )
        
        log_callback("-" * 45)
        log_callback(f"Total Transaksi Valid: {valid_count}")
        log_callback(f"Saldo Awal: {saldo_awal:,.2f}")
        log_callback(f"Total Mutasi Debet : {total_debet:,.2f}")
        log_callback(f"Total Mutasi Kredit: {total_kredit:,.2f}")
        log_callback(f"Saldo Akhir: {current_balance:,.2f}")
        
        # Validasi Rekonsiliasi Otomatis terhadap Ringkasan Bank
        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan Giro KlikBCA",
            "saldo_awal": saldo_awal,
            "debet": mutasi_debit_summary if mutasi_debit_summary is not None else total_debet,
            "kredit": mutasi_kredit_summary if mutasi_kredit_summary is not None else total_kredit,
            "saldo_akhir": saldo_akhir if saldo_akhir is not None else current_balance,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count": valid_count
        }
        audit_table = format_audit_reconciliation_table("BCA Giro", source_summary, output_summary)
        log_callback("\n" + audit_table)
        transactions[0]["_audit_table"] = audit_table
        
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
        periode_raw = ""
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
            
            per_m = re.search(r'PERIODE\s*:?\s*([^\n\r]+)', text0, re.IGNORECASE)
            if per_m:
                periode_raw = per_m.group(1).strip()
            
            words = page0.extract_words()
            for w in words:
                if w['top'] > 70 and w['top'] < 90 and w['x0'] < 100:
                    if w['text'] not in ['NO.', 'REKENING', ':']:
                        nama += w['text'] + " "
            nama = nama.strip()[:240]
        
        if not rekening: rekening = "1234567890"
        if not nama: nama = "NASABAH BCA"

        log_callback(f"Rekening: {rekening} | Nama: {nama}")
        if periode_raw:
            log_callback(f"Periode: {periode_raw}")

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
                        wt_clean = w['text'].strip()
                        attached_m = re.search(r'^([\d\.,]+)\s*(CR|DB)$', wt_clean, re.IGNORECASE)
                        if attached_m:
                            mutasi = clean_currency(attached_m.group(1))
                            mutasi_zone_marker = attached_m.group(2).upper()
                        elif re.match(r'^[\d\.,]+$', wt_clean) and any(c.isdigit() for c in wt_clean) and not re.search(r'[a-zA-Z]', wt_clean):
                            mutasi = clean_currency(wt_clean)
                        elif wt_clean.upper() in ('DB', 'CR'):
                            mutasi_zone_marker = wt_clean.upper()
                    elif w['x0'] >= 480:
                        wt_clean = w['text'].strip()
                        if re.match(r'^[\d\.,]+$', wt_clean) and any(c.isdigit() for c in wt_clean) and not re.search(r'[a-zA-Z]', wt_clean):
                            saldo_pr = clean_currency(wt_clean)
                            
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
    
        # --- Fase 2: Koreksi tipe menggunakan saldo sebagai sumber kebenaran (Look-Ahead Cluster Solver) ---
        transactions, current_balance, valid_count, total_debet, total_kredit = _reconcile_bca_transactions(
            transactions, saldo_awal, log_callback
        )
            
        full_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        m_cr = re.search(r'MUTASI\s*CR\s*:?\s*(?:[\d]+\s+)?([\d\.,]+)', full_text, re.IGNORECASE)
        mutasi_cr_sum = clean_currency(m_cr.group(1)) if m_cr else None
        m_db = re.search(r'MUTASI\s*DB\s*:?\s*(?:[\d]+\s+)?([\d\.,]+)', full_text, re.IGNORECASE)
        mutasi_db_sum = clean_currency(m_db.group(1)) if m_db else None
        m_sa = re.search(r'SALDO\s*AKHIR\s*:?\s*([\d\.,]+)', full_text, re.IGNORECASE)
        saldo_akhir_sum = clean_currency(m_sa.group(1)) if m_sa else None

        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan BCA Tahapan",
            "saldo_awal": saldo_awal,
            "debet": mutasi_db_sum if mutasi_db_sum is not None else total_debet,
            "kredit": mutasi_cr_sum if mutasi_cr_sum is not None else total_kredit,
            "saldo_akhir": saldo_akhir_sum if saldo_akhir_sum is not None else current_balance,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count": valid_count
        }
        audit_table = format_audit_reconciliation_table("BCA Tahapan", source_summary, output_summary)
        log_callback("\n" + audit_table)
        transactions[0]["_audit_table"] = audit_table
        
        if valid_count == 0:
            raise Exception("File PDF berhasil dibaca, namun tidak ditemukan data transaksi BCA. Pastikan file yang dipilih adalah mutasi rekening BCA yang valid.")
            
        if periode_raw and transactions:
            transactions[0]["_periode_raw"] = periode_raw

        progress_callback(0.9)
        success_callback(transactions, rekening, nama, saldo_awal, current_balance, filepath)
        
    except Exception as e:
        error_callback(str(e))

def process_bca(filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        # Guard Check: Tolak jika terdeteksi dokumen bank lain (misal Panin, Mandiri)
        from utils.bank_validator import detect_bank_from_file
        detected_bank, reason = detect_bank_from_file(filepath)
        if detected_bank and detected_bank != "BCA":
            raise Exception(f"File ini terdeteksi sebagai dokumen mutasi BANK {detected_bank.upper()}, bukan BANK BCA ({reason}). Silakan ubah pilihan bank ke '{detected_bank}'.")

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
