import pandas as pd
try:
    import xlrd  # pyright: ignore[reportUnusedImport]
    import openpyxl  # pyright: ignore[reportUnusedImport]
    _ = (xlrd, openpyxl)
except ImportError:
    pass
from utils.helpers import clean_currency, clean_desc, parse_date_tolerant

OUTPUT_COLUMNS = {
    'tgl': 'tanggal',
    'desc': 'transaksi',
    'deb': 'debet',
    'kre': 'kredit',
    'bal': 'Saldo'
}

def process_panin(filepath, use_regex, log_callback, progress_callback, success_callback, error_callback):
    try:
        log_callback("-" * 45)
        log_callback("Memulai proses konversi Panin...")
        log_callback("-" * 45)
        
        progress_callback(0.05)
        
        # Guard Check: Tolak jika terdeteksi dokumen bank lain (misal BCA, Mandiri)
        from utils.bank_validator import detect_bank_from_file
        detected_bank, reason = detect_bank_from_file(filepath)
        if detected_bank and detected_bank != "Panin":
            raise Exception(f"File ini terdeteksi sebagai dokumen mutasi BANK {detected_bank.upper()}, bukan BANK PANIN ({reason}). Silakan ubah pilihan bank ke '{detected_bank}'.")
        
        df_temp = None
        file_ext = filepath.lower()
        
        if file_ext.endswith('.xlsx'):
            try: 
                log_callback("Reading XLSX engine (openpyxl)...")
                df_temp = pd.read_excel(filepath, header=None, engine='openpyxl')
            except Exception as e: 
                log_callback(f"XLSX read err: {e}")
        elif file_ext.endswith('.csv'):
            try: 
                log_callback("Reading CSV engine...")
                df_temp = pd.read_csv(filepath, header=None, sep=None, engine='python', on_bad_lines='skip')
            except Exception as e:
                log_callback(f"CSV read err: {e}")
        elif file_ext.endswith('.pdf'):
            try:
                from processors.panin_scan_processor import is_scanned_pdf, process_panin_scanned_pdf
                if is_scanned_pdf(filepath):
                    process_panin_scanned_pdf(filepath, log_callback, progress_callback, success_callback, error_callback)
                    return
            except Exception as scan_detect_err:
                log_callback(f"[INFO] Scan check: {scan_detect_err}")

            try:
                import pdfplumber
                import re
                log_callback("Membaca PDF...")
                
                pdf_data = []
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
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
                        
                        y_blocks = []
                        current_tx = []
                        for line in lines:
                            text_line = " ".join([w['text'] for w in line])
                            if "Detil Rekening" in text_line or "Nomor Rekening :" in text_line or "Nama :" in text_line or "Mata Uang :" in text_line: continue
                            if "Silahkan Pilih Periode" in text_line or "Mutasi Bulanan :" in text_line or "Catatan:" in text_line: continue
                            if "Informasi mutasi harian" in text_line or "Mutasi bulanan menunjukkan" in text_line: continue
                            if "Tanggal Deskripsi Debit Kredit Saldo" in text_line: continue
                            
                            has_date = False
                            for w in line:
                                if w['x0'] < 100 and re.match(r'\d{2}/\d{2}/\d{4}', w['text']):
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
                            debit_val = "0"
                            kredit_val = "0"
                            saldo_val = "0"
                            
                            for line in tx_lines:
                                for w in line:
                                    if w['x0'] < 130 and re.match(r'\d{2}/\d{2}/\d{4}', w['text']):
                                        date = w['text']
                                    elif 130 <= w['x0'] < 250:
                                        desc_parts.append(w['text'])
                                    elif 250 <= w['x0'] < 360:
                                        if re.match(r'[\d\,]+\.\d{2}', w['text']):
                                            debit_val = w['text']
                                        else:
                                            desc_parts.append(w['text'])
                                    elif 360 <= w['x0'] < 460:
                                        if re.match(r'[\d\,]+\.\d{2}', w['text']):
                                            kredit_val = w['text']
                                        else:
                                            desc_parts.append(w['text'])
                                    elif w['x0'] >= 460:
                                        if re.match(r'[\d\,]+\.\d{2}', w['text']):
                                            saldo_val = w['text']
                            
                            if not date: continue
                            desc = " ".join(desc_parts).strip()
                            pdf_data.append([date, desc, debit_val, kredit_val, saldo_val])
                            
                if pdf_data:
                    df_temp = pd.DataFrame([["tanggal", "transaksi", "debit", "kredit", "saldo"]] + pdf_data)
                else:
                    log_callback("-" * 45)
                    log_callback("Total Transaksi Valid: 0")
                    log_callback("Saldo Awal: 0.00")
                    log_callback("Saldo Akhir: 0.00")
                    log_callback("-" * 45)
                    raise Exception("File PDF berhasil dibaca, namun tidak ditemukan data transaksi Panin. Pastikan file yang dipilih adalah mutasi rekening Panin yang valid.")
                    
            except Exception as e:
                # Jangan print stack error jika itu adalah exception kustom kita
                if "File PDF berhasil dibaca, namun tidak ditemukan" in str(e):
                    raise e
                log_callback(f"PDF read err: {e}")
                raise Exception(f"Gagal baca PDF: {e}")
        else:
            try: 
                log_callback("Reading standard Excel (.xls)...")
                df_temp = pd.read_excel(filepath, header=None)
            except Exception as e: 
                raise Exception(f"Format file tidak didukung atau rusak. Pastikan file adalah mutasi Panin yang valid.\n(Detail Error: {e})")
        
        if df_temp is None or df_temp.empty: 
            raise Exception("Data kosong atau corrupt.")

        progress_callback(0.1) 

        log_callback(f"Jumlah tipe kolom file mentah: {df_temp.shape[1]}")
        raw_rows = df_temp.astype(str).values.tolist()
        
        header_idx = None
        col_map = {} 
        for i, row in enumerate(raw_rows): 
            r_str = " ".join([str(x).lower() for x in row])
            if "tanggal" in r_str and ("kredit" in r_str or "debet" in r_str or "debit" in r_str):
                header_idx = i
                log_callback(f"[OK] Header terdeteksi di index {i+1}")
                for idx, cell in enumerate(row):
                    val = str(cell).lower().strip()
                    if 'tanggal' in val: col_map['tgl'] = idx
                    elif 'uraian' in val or 'transaksi' in val or 'deskripsi' in val: col_map['desc'] = idx
                    elif 'debit' in val or 'debet' in val: col_map['deb'] = idx
                    elif 'kredit' in val: col_map['kre'] = idx
                    elif 'saldo' in val: col_map['bal'] = idx
                log_callback(f"Col map: {col_map}")
                break
        
        if header_idx is None: 
            raise Exception("Gagal mendeteksi header tabel. Pastikan file memiliki kolom Tanggal, Debet, dan Kredit yang sesuai dengan format mutasi Panin.")

        final_data = []
        invalid_dates_data = []
        
        idx_tgl = col_map.get('tgl')
        idx_desc = col_map.get('desc')
        idx_deb = col_map.get('deb')
        idx_kre = col_map.get('kre')
        idx_bal = col_map.get('bal')

        total_rows_to_process = len(raw_rows) - (header_idx + 1)

        for i in range(header_idx+1, len(raw_rows)):
            
            current_step = i - header_idx
            if current_step % max(1, total_rows_to_process // 50) == 0: 
                progress_value = 0.1 + (0.8 * (current_step / total_rows_to_process))
                progress_callback(progress_value)
            
            row = raw_rows[i]
            if len(row) <= max(idx_tgl or 0, idx_desc or 0, idx_deb or 0, idx_kre or 0, idx_bal or 0): continue 
            tgl_raw = row[idx_tgl] if idx_tgl is not None and len(row) > idx_tgl else ""
            if not any(c.isdigit() for c in str(tgl_raw)): continue 

            try:
                val_deb = row[idx_deb] if idx_deb is not None and len(row) > idx_deb else "0"
                val_kre = row[idx_kre] if idx_kre is not None and len(row) > idx_kre else "0"
                val_bal = row[idx_bal] if idx_bal is not None and len(row) > idx_bal else "0"
                
                debit = clean_currency(val_deb)
                kredit = clean_currency(val_kre)
                saldo = clean_currency(val_bal)
                
                if debit == 0 and kredit == 0:
                    if idx_deb is not None and len(row) > idx_deb+1:
                        d_try = clean_currency(row[idx_deb+1])
                        if d_try > 0: 
                            log_callback(f"Row {i+1}: Kolom debit bergeser (Fixed)")
                            debit = d_try
                    if idx_kre is not None and len(row) > idx_kre+1:
                        k_try = clean_currency(row[idx_kre+1])
                        if k_try > 0: 
                            log_callback(f"Row {i+1}: Kolom kredit bergeser (Fixed)")
                            kredit = k_try

                if debit == 0 and kredit == 0: continue 

                desc = clean_desc(row[idx_desc], use_regex) if idx_desc is not None and len(row) > idx_desc else ""
                parsed_date = parse_date_tolerant(tgl_raw, log_callback)
                
                if pd.isna(parsed_date):
                    invalid_dates_data.append({'baris_excel': i+1, 'tanggal_raw': tgl_raw, 'deskripsi': desc[:100], 'debit': debit, 'kredit': kredit, 'saldo': saldo})
                    log_callback(f"[WARN] Row {i+1}: Format tanggal invalid -> {tgl_raw}")
                    continue
                
                log_msg = f"Row {i+1} | "
                if debit > 0: log_msg += f"D: {debit:,.2f} "
                if kredit > 0: log_msg += f"K: {kredit:,.2f} "
                log_msg += f"T: {parsed_date.strftime('%d/%m/%Y')}" # type: ignore
                log_callback(log_msg)

                final_data.append({
                    OUTPUT_COLUMNS['tgl']: parsed_date.strftime('%d/%m/%Y'), # type: ignore
                    OUTPUT_COLUMNS['desc']: desc,
                    OUTPUT_COLUMNS['deb']: debit if debit != 0 else "",
                    OUTPUT_COLUMNS['kre']: kredit if kredit != 0 else "",
                    OUTPUT_COLUMNS['bal']: saldo,
                    'real_deb': debit, 'real_kre': kredit, 'date_obj': parsed_date 
                })
            except Exception as e:
                log_callback(f"[ERR] Row {i+1}: {str(e)}")
                continue

        progress_callback(0.9) 

        if not final_data: raise Exception("Tidak ada dataset valid yang bisa diekstrak.")

        log_callback("-" * 45)
        log_callback("-" * 45)
        log_callback("Berhasil di Ekstraksi:")
        log_callback(f"Total baris diproses : {total_rows_to_process}")
        log_callback(f"Transaksi valid      : {len(final_data)}")
        log_callback(f"Tanggal invalid      : {len(invalid_dates_data)}")
        log_callback("-" * 45)
        
        df_final = pd.DataFrame(final_data)
        df_final[OUTPUT_COLUMNS['tgl']] = df_final['date_obj'].dt.strftime('%d/%m/%Y') # type: ignore
        
        if len(df_final) > 0:
            first_row = df_final.iloc[0]
            saldo_row_1 = float(first_row[OUTPUT_COLUMNS['bal']])
            deb_row_1 = float(first_row['real_deb'])
            kre_row_1 = float(first_row['real_kre'])
            
            saldo_awal_val = saldo_row_1 - kre_row_1 + deb_row_1
            total_kredit = df_final['real_kre'].sum()
            total_debet = df_final['real_deb'].sum()
            saldo_akhir_val = df_final.iloc[-1][OUTPUT_COLUMNS['bal']]
            
            num_dummy = 7
            # Loop ulang data transaksi sampai genap 7 baris
            if len(df_final) >= num_dummy:
                df_dummy = df_final.iloc[:num_dummy].copy()
            else:
                rows = []
                for i in range(num_dummy):
                    rows.append(df_final.iloc[i % len(df_final)].to_dict())
                df_dummy = pd.DataFrame(rows)
            log_callback(f"Menambahkan {num_dummy} baris kosong (Dummy Format Accurate).")
            
            df_dummy = df_dummy.drop(columns=['real_deb', 'real_kre', 'date_obj'], errors='ignore')
            df_final = df_final.drop(columns=['real_deb', 'real_kre', 'date_obj'])
            
            row_saldo_awal = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Awal', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: saldo_awal_val}])
            row_total_mutasi = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Total Mutasi', OUTPUT_COLUMNS['deb']: total_debet, OUTPUT_COLUMNS['kre']: total_kredit, OUTPUT_COLUMNS['bal']: ""}])
            row_saldo_akhir = pd.DataFrame([{OUTPUT_COLUMNS['tgl']: '', OUTPUT_COLUMNS['desc']: 'Saldo Akhir', OUTPUT_COLUMNS['deb']: "", OUTPUT_COLUMNS['kre']: "", OUTPUT_COLUMNS['bal']: saldo_akhir_val}])
            
            df_output = pd.concat([df_dummy, row_saldo_awal, df_final, row_total_mutasi, row_saldo_akhir], ignore_index=True)

            log_callback(f"Saldo Awal   : {saldo_awal_val:,.2f}")
            log_callback(f"Total Debit  : {total_debet:,.2f}")
            log_callback(f"Total Kredit : {total_kredit:,.2f}")
            log_callback(f"Saldo Akhir  : {saldo_akhir_val:,.2f}")
            log_callback("-" * 45)
            
            progress_callback(0.95)
            
            success_callback(df_output, invalid_dates_data, num_dummy, filepath)

        else:
            raise Exception("Tidak ada output yang bisa disimpan.")

    except Exception as e:
        error_callback(str(e))
