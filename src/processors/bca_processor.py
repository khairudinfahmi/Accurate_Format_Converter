import os
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
        
        basename = os.path.basename(filepath)
        rekening = "1234567890"
        rek_m = re.search(r'(?:MutasiRekening_|No\.?\s*Rekening[\s:=]*\'?)(\d{8,16})', basename, re.IGNORECASE)
        if rek_m:
            rekening = rek_m.group(1)

        nama = "NASABAH BCA"
        saldo_awal = None
        saldo_akhir = None
        mutasi_debet_summary = None
        mutasi_kredit_summary = None
        periode_raw = ""
        transactions = []

        raw_lines = []
        with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
            for line in f:
                l = line.strip()
                if l.startswith('"') and l.endswith('"') and '""' in l:
                    l = l[1:-1].replace('""', '"')
                raw_lines.append(l)

        reader = list(csv.reader(raw_lines))
        data_started = False
        header_cols = {}

        for row in reader:
            if not row or not any(row):
                continue
            line_str = " ".join(row)

            # Metadata parsing (toleran ':' maupun '=')
            if "No. rekening" in line_str or "No. Rekening" in line_str:
                m = re.search(r'No\.?\s*rekening\s*(?::|=)\s*\'?(\d+)', line_str, re.IGNORECASE)
                if m: rekening = m.group(1)
            elif "Nama" in line_str and ("=" in line_str or ":" in line_str):
                m = re.search(r'Nama\s*(?::|=)\s*([^\n\r,]+)', line_str, re.IGNORECASE)
                if m: nama = m.group(1).strip()
            elif "Periode" in line_str and ("=" in line_str or ":" in line_str):
                m = re.search(r'Periode\s*(?::|=)\s*([^\n\r,]+)', line_str, re.IGNORECASE)
                if m: periode_raw = m.group(1).strip()
            elif "Saldo Awal" in line_str:
                m = re.search(r'Saldo\s*Awal\s*(?::|=)\s*\'?([\d\,\.]+)', line_str, re.IGNORECASE)
                if m: saldo_awal = clean_currency(m.group(1))
            elif "Saldo Akhir" in line_str:
                m = re.search(r'Saldo\s*Akhir\s*(?::|=)\s*\'?([\d\,\.]+)', line_str, re.IGNORECASE)
                if m: saldo_akhir = clean_currency(m.group(1))
            elif "Mutasi Debet" in line_str or "Debet" in line_str:
                m = re.search(r'(?:Mutasi\s*)?Deb[ei]t\s*(?::|=)\s*\'?([\d\,\.]+)', line_str, re.IGNORECASE)
                if m: mutasi_debet_summary = clean_currency(m.group(1))
            elif "Mutasi Kredit" in line_str or "Kredit" in line_str:
                m = re.search(r'(?:Mutasi\s*)?Kredit\s*(?::|=)\s*\'?([\d\,\.]+)', line_str, re.IGNORECASE)
                if m: mutasi_kredit_summary = clean_currency(m.group(1))

            # Table Header Check
            row_lower = [c.lower().strip() for c in row]
            if not data_started and any('tanggal' in c for c in row_lower) and any(c in ('keterangan', 'uraian') for c in row_lower):
                data_started = True
                for idx, c in enumerate(row_lower):
                    if 'tanggal' in c: header_cols['tgl'] = idx
                    elif 'keterangan' in c or 'uraian' in c: header_cols['desc'] = idx
                    elif 'cabang' in c: header_cols['cab'] = idx
                    elif 'mutasi' in c or 'jumlah' in c: header_cols['mut'] = idx
                    elif 'jenis' in c or 'tipe' in c: header_cols['type'] = idx
                    elif 'saldo' in c: header_cols['bal'] = idx
                continue

            if data_started:
                # Stop / lewati jika baris ringkasan footer tercapai
                if any(k in line_str.upper() for k in ["SALDO AWAL", "SALDO AKHIR", "MUTASI DEBET", "MUTASI KREDIT"]):
                    continue

                col_tgl_idx = header_cols.get('tgl', 0)
                if len(row) <= col_tgl_idx:
                    continue
                tgl_cell = row[col_tgl_idx].strip()
                if not any(ch.isdigit() for ch in tgl_cell) and "PEND" not in tgl_cell.upper():
                    continue

                # Format Tanggal
                t_m = re.search(r'(\d{2}/\d{2}(?:/\d{4})?)', tgl_cell)
                tgl_clean = t_m.group(1) if t_m else ("PEND" if "PEND" in tgl_cell.upper() else tgl_cell)

                desc = row[header_cols['desc']] if 'desc' in header_cols and len(row) > header_cols['desc'] else ""
                cab_raw = row[header_cols['cab']].replace("'", "").strip() if 'cab' in header_cols and len(row) > header_cols['cab'] else "0000"
                cab_clean = f"{int(float(cab_raw)):04d}" if re.match(r'^\d+(\.0+)?$', cab_raw) else cab_raw

                # Mutasi & Tipe
                mutasi_val = 0.0
                tipe_val = "CR"

                if 'type' in header_cols and len(row) > header_cols['type'] and header_cols['type'] is not None:
                    mutasi_val = clean_currency(row[header_cols['mut']])
                    t_str = row[header_cols['type']].upper().strip()
                    tipe_val = "DB" if "DB" in t_str else "CR"
                else:
                    # Cek varian 6 kolom (misal template BCA format 1: Tanggal, Keterangan, Cabang, Jumlah, Tipe, Saldo)
                    if len(row) >= 6 and row[4].strip().upper() in ('CR', 'DB'):
                        tipe_val = row[4].strip().upper()
                        mutasi_val = clean_currency(row[3])
                    else:
                        mut_str = row[header_cols['mut']].upper() if 'mut' in header_cols and len(row) > header_cols['mut'] else ""
                        if " CR" in mut_str or mut_str.endswith("CR") or re.search(r'\bCR\b', mut_str):
                            tipe_val = "CR"
                            mutasi_val = clean_currency(re.sub(r'CR', '', mut_str, flags=re.IGNORECASE))
                        elif " DB" in mut_str or mut_str.endswith("DB") or re.search(r'\bDB\b', mut_str):
                            tipe_val = "DB"
                            mutasi_val = clean_currency(re.sub(r'DB', '', mut_str, flags=re.IGNORECASE))
                        else:
                            tipe_val = "CR"
                            mutasi_val = clean_currency(mut_str)

                saldo_val = clean_currency(row[header_cols['bal']]) if 'bal' in header_cols and len(row) > header_cols['bal'] else 0.0

                transactions.append({
                    "tanggal": "'" + tgl_clean,
                    "keterangan": desc,
                    "cabang": "'" + (cab_clean if cab_clean else "0000"),
                    "mutasi": mutasi_val,
                    "tipe": tipe_val,
                    "saldo_printed": saldo_val,
                    "saldo": saldo_val
                })

        if not transactions:
            raise Exception("File CSV berhasil dibaca, namun tidak ditemukan data transaksi BCA.")

        # Hitung Saldo Awal jika tidak ada di header
        if saldo_awal is None:
            first_tx = transactions[0]
            if first_tx.get("saldo_printed") is not None:
                if first_tx["tipe"] == "CR":
                    saldo_awal = round(first_tx["saldo_printed"] - first_tx["mutasi"], 2)
                else:
                    saldo_awal = round(first_tx["saldo_printed"] + first_tx["mutasi"], 2)
            else:
                saldo_awal = 0.0

        # --- Fase 2 (CSV): Validasi Silang Matematika Saldo (Self-Healing Fail-Safe) ---
        transactions, current_balance, valid_count, total_debet, total_kredit = _reconcile_bca_transactions(
            transactions, saldo_awal, log_callback
        )
        
        progress_callback(0.9)
        
        out_count_deb = sum(1 for tx in transactions if tx["tipe"] == "DB")
        out_count_kre = sum(1 for tx in transactions if tx["tipe"] == "CR")

        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan CSV BCA",
            "saldo_awal": saldo_awal,
            "debet": mutasi_debet_summary if mutasi_debet_summary is not None else total_debet,
            "kredit": mutasi_kredit_summary if mutasi_kredit_summary is not None else total_kredit,
            "saldo_akhir": saldo_akhir if (saldo_akhir and saldo_akhir > 0) else current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
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

def _process_bca_excel(filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        log_callback("-" * 45)
        log_callback("Memulai proses konversi BCA (dari Excel)...")
        log_callback("-" * 45)
        progress_callback(0.1)

        basename = os.path.basename(filepath)
        rekening = "1234567890"
        rek_m = re.search(r'(?:MutasiRekening_|No\.?\s*Rekening[\s:=]*\'?)(\d{8,16})', basename, re.IGNORECASE)
        if rek_m:
            rekening = rek_m.group(1)

        nama = "NASABAH BCA"
        saldo_awal = None
        saldo_akhir = None
        periode_raw = ""
        date_m = re.search(r'(\d{4})(\d{2})(\d{2})', basename)
        if date_m:
            periode_raw = f"{date_m.group(3)}/{date_m.group(2)}/{date_m.group(1)}"
        transactions = []

        import pandas as pd
        df = pd.read_excel(filepath)

        header_row_idx = None
        for r in range(min(10, len(df))):
            row_str = " ".join([str(x).lower() for x in df.iloc[r].values])
            if "tanggal" in row_str and ("mutasi" in row_str or "jumlah" in row_str or "saldo" in row_str):
                header_row_idx = r
                break

        if header_row_idx is not None:
            df.columns = df.iloc[header_row_idx]
            df = df.iloc[header_row_idx + 1:].reset_index(drop=True)

        col_map = {}
        for c in df.columns:
            cs = c.lower().strip()
            if 'tanggal' in cs: col_map['tgl'] = c
            elif 'keterangan' in cs or 'uraian' in cs: col_map['desc'] = c
            elif 'cabang' in cs: col_map['cab'] = c
            elif 'mutasi' in cs or 'jumlah' in cs: col_map['mut'] = c
            elif 'jenis' in cs or 'tipe' in cs: col_map['type'] = c
            elif 'saldo' in cs: col_map['bal'] = c

        if 'tgl' not in col_map or 'mut' not in col_map or 'bal' not in col_map:
            raise Exception("Kolom tabel mutasi BCA (Tanggal, Mutasi/Jumlah, Saldo) tidak lengkap di file Excel.")

        for _, row in df.iterrows():
            tgl_raw = str(row[col_map['tgl']]).strip()
            if not any(ch.isdigit() for ch in tgl_raw) and "PEND" not in tgl_raw.upper():
                continue

            t_m = re.search(r'(\d{2}/\d{2}(?:/\d{4})?)', tgl_raw)
            if t_m:
                tgl_clean = t_m.group(1)
            elif "PEND" in tgl_raw.upper():
                tgl_clean = "PEND"
            else:
                tgl_clean = tgl_raw

            desc = str(row[col_map['desc']]).strip() if 'desc' in col_map else ""
            cab_raw = str(row[col_map['cab']]).strip() if 'cab' in col_map else "0000"
            cab_clean = f"{int(float(cab_raw)):04d}" if re.match(r'^\d+(\.0+)?$', cab_raw) else cab_raw

            mutasi_val = clean_currency(row[col_map['mut']])
            tipe_val = "CR"
            if 'type' in col_map:
                t_str = str(row[col_map['type']]).upper().strip()
                tipe_val = "DB" if "DB" in t_str else "CR"
            else:
                m_str = str(row[col_map['mut']]).upper()
                tipe_val = "DB" if "DB" in m_str else "CR"

            saldo_val = clean_currency(row[col_map['bal']])

            transactions.append({
                "tanggal": "'" + tgl_clean,
                "keterangan": desc,
                "cabang": "'" + (cab_clean if cab_clean else "0000"),
                "mutasi": mutasi_val,
                "tipe": tipe_val,
                "saldo_printed": saldo_val,
                "saldo": saldo_val
            })

        if not transactions:
            raise Exception("File Excel berhasil dibaca, namun tidak ditemukan baris transaksi BCA.")

        # Hitung Saldo Awal backward dari baris pertama jika tidak ada di header
        if saldo_awal is None:
            first_tx = transactions[0]
            if first_tx.get("saldo_printed") is not None:
                if first_tx["tipe"] == "CR":
                    saldo_awal = round(first_tx["saldo_printed"] - first_tx["mutasi"], 2)
                else:
                    saldo_awal = round(first_tx["saldo_printed"] + first_tx["mutasi"], 2)
            else:
                saldo_awal = 0.0

        transactions, current_balance, valid_count, total_debet, total_kredit = _reconcile_bca_transactions(
            transactions, saldo_awal, log_callback
        )

        progress_callback(0.9)

        out_count_deb = sum(1 for tx in transactions if tx["tipe"] == "DB")
        out_count_kre = sum(1 for tx in transactions if tx["tipe"] == "CR")

        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan Excel BCA",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
            "count": valid_count
        }
        audit_table = format_audit_reconciliation_table("BCA Excel", source_summary, output_summary)
        log_callback("\n" + audit_table)
        transactions[0]["_audit_table"] = audit_table

        if periode_raw and transactions:
            transactions[0]["_periode_raw"] = periode_raw

        success_callback(transactions, rekening, nama, saldo_awal, current_balance, filepath)

    except Exception as e:
        error_callback(str(e))

def _process_bca_giro_pdf(pdf, filepath, log_callback, progress_callback, success_callback, error_callback):
    try:
        log_callback("-" * 45)
        log_callback("Memulai proses konversi BCA (Format Giro / myBCA / KlikBCA)...")
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
        
        out_count_deb = sum(1 for tx in transactions if tx["tipe"] == "DB")
        out_count_kre = sum(1 for tx in transactions if tx["tipe"] == "CR")

        # Validasi Rekonsiliasi Otomatis terhadap Ringkasan Bank
        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan myBCA / KlikBCA",
            "saldo_awal": saldo_awal,
            "debet": mutasi_debit_summary if mutasi_debit_summary is not None else total_debet,
            "kredit": mutasi_kredit_summary if mutasi_kredit_summary is not None else total_kredit,
            "saldo_akhir": saldo_akhir if saldo_akhir is not None else current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
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

        out_count_deb = sum(1 for tx in transactions if tx["tipe"] == "DB")
        out_count_kre = sum(1 for tx in transactions if tx["tipe"] == "CR")

        from utils.helpers import format_audit_reconciliation_table
        source_summary = {
            "label": "Ringkasan BCA Tahapan",
            "saldo_awal": saldo_awal,
            "debet": mutasi_db_sum if mutasi_db_sum is not None else total_debet,
            "kredit": mutasi_cr_sum if mutasi_cr_sum is not None else total_kredit,
            "saldo_akhir": saldo_akhir_sum if saldo_akhir_sum is not None else current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
            "count": valid_count
        }
        output_summary = {
            "label": "Hasil Format Accurate",
            "saldo_awal": saldo_awal,
            "debet": total_debet,
            "kredit": total_kredit,
            "saldo_akhir": current_balance,
            "count_deb": out_count_deb,
            "count_kre": out_count_kre,
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
            raise Exception(f"File ini terdeteksi sebagai dokumen mutasi Bank {detected_bank}, bukan Bank BCA ({reason}). Silakan ubah pilihan bank ke '{detected_bank}'.")

        if filepath.lower().endswith(('.xlsx', '.xls')):
            _process_bca_excel(filepath, log_callback, progress_callback, success_callback, error_callback)
            return

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
