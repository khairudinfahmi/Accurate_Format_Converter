import sys
import os
import re
import datetime
import pandas as pd
import winreg

def get_windows_theme():
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(registry_key, "AppsUseLightTheme")
        return "Light" if value == 1 else "Dark"
    except Exception:
        return "Dark"

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    return os.path.join(base_path, relative_path)

def clean_currency(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return abs(float(val))
    
    if not val: return 0.0
    s = str(val).strip().lower()
    if s in ['nan', 'none', '', '-', 'null']: return 0.0
    
    # Tangani minus di belakang (format mainframe/AS400: '500,000.00-')
    if s.endswith('-'):
        s = '-' + s[:-1].strip()
        
    s = re.sub(r'[^\d.,-]', '', s)
    if not s: return 0.0
    try:
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'): s = s.replace('.', '').replace(',', '.')
            else: s = s.replace(',', '')
        elif ',' in s:
            if len(s) - s.rfind(',') - 1 == 3: s = s.replace(',', '')
            else: s = s.replace(',', '.')
        elif '.' in s:
            parts = s.split('.')
            if len(parts) > 2:
                # Multi-titik: cek jika bagian terakhir adalah 2 desimal (misal 10.000.00)
                if len(parts[-1]) == 2:
                    s = ''.join(parts[:-1]) + '.' + parts[-1]
                else:
                    s = ''.join(parts)
            else:
                if parts[-1] == '0': pass 
                elif len(parts[-1]) != 2: s = s.replace('.', '')
                else: pass 
        return abs(float(s))
    except Exception:
        return 0.0

def clean_desc(val, use_regex=False):
    s = str(val)
    if s.lower() in ['nan', 'none', '']: return ""
    if not use_regex: return s.strip()
    s = s.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
    s = re.sub(r'([A-Z])([A-Z][a-z])', r'\1 \2', s)
    s = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', s)
    s = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', s)
    return s.strip()

MONTH_MAP = {
    'jan': 1, 'januari': 1, 'feb': 2, 'februari': 2, 'mar': 3, 'maret': 3,
    'apr': 4, 'april': 4, 'mei': 5, 'may': 5, 'jun': 6, 'juni': 6,
    'jul': 7, 'juli': 7, 'agu': 8, 'agustus': 8, 'ags': 8, 'aug': 8,
    'sep': 9, 'september': 9, 'okt': 10, 'oktober': 10, 'oct': 10,
    'nov': 11, 'november': 11, 'des': 12, 'desember': 12, 'dec': 12
}

def parse_date_tolerant(date_str, log_callback=print):
    try:
        if date_str is None or pd.isna(date_str):
            return pd.NaT
        if isinstance(date_str, pd.Timestamp):
            return date_str.normalize()
        if isinstance(date_str, datetime.datetime):
            return pd.Timestamp(date_str).normalize()
        if isinstance(date_str, datetime.date):
            return pd.Timestamp(date_str)

        # Excel serial integer date (misal: 45300)
        if isinstance(date_str, (int, float)) and 30000 <= date_str <= 65000:
            return pd.to_datetime('1899-12-30') + pd.to_timedelta(int(date_str), 'D')

        s = str(date_str).strip()
        if not s or s.lower() in ['nan', 'none', 'null', 'nat']:
            return pd.NaT

        # Cek jika string adalah angka serial Excel (misal "45300" atau "45300.0")
        if re.match(r'^\d{5}(?:\.0+)?$', s):
            val_int = int(float(s))
            if 30000 <= val_int <= 65000:
                return pd.to_datetime('1899-12-30') + pd.to_timedelta(val_int, 'D')

        # Pisahkan komponen waktu jika ada (misal: "2026-01-15 00:00:00" -> "2026-01-15")
        s_date = s.split(' ')[0] if ' ' in s else s
        s_date = s_date.split('T')[0] if 'T' in s_date else s_date

        # Cek format bulan tekstual Indonesia/Inggris (misal: "15-Okt-2024", "15 Mei 2025")
        text_m = re.search(r'(\d{1,2})[\s\-\/\.]([a-zA-Z]+)[\s\-\/\.](\d{2,4})', s)
        if text_m:
            d_p, m_str, y_p = text_m.group(1), text_m.group(2).lower()[:3], text_m.group(3)
            if m_str in MONTH_MAP:
                m_p = MONTH_MAP[m_str]
                if len(y_p) == 2: y_p = '20' + y_p if int(y_p) < 50 else '19' + y_p
                return pd.to_datetime(f"{int(d_p):02d}/{m_p:02d}/{y_p}", format='%d/%m/%Y')

        s_clean = re.sub(r'[^\d\/\-\.]', '', s_date)
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%d-%m-%y', '%d.%m.%y', '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d']:
            try: return pd.to_datetime(s_clean, format=fmt, dayfirst=True)
            except Exception: continue
        numbers = re.findall(r'\d+', s_clean)
        if len(numbers) >= 3:
            day, month, year = numbers[0], numbers[1], numbers[2]
            if len(year) == 2: year = '20' + year if int(year) < 50 else '19' + year
            elif len(year) == 1: year = '200' + year
            day = int(day) if int(day) <= 31 else 1
            month = int(month) if int(month) <= 12 else 1
            try: return pd.to_datetime(f"{day:02d}/{month:02d}/{year}", dayfirst=True)
            except Exception: return pd.NaT
        return pd.NaT
    except Exception as e:
        log_callback(f"Error parsing date '{date_str}': {e}")
        return pd.NaT

def format_audit_reconciliation_table(bank_name, source_metrics, output_metrics, notes=None):
    """
    Menghasilkan Lembar Audit Rekonsiliasi Finansial Berdampingan (Side-by-Side):
    Membandingkan Saldo Awal, Total Debet, Total Kredit, Saldo Akhir, dan Frekuensi Transaksi
    antara Dokumen Sumber Bank dengan File Hasil Konversi Accurate.
    """
    sa_src = source_metrics.get("saldo_awal")
    sa_out = output_metrics.get("saldo_awal", 0.0)
    deb_src = source_metrics.get("debet", 0.0)
    deb_out = output_metrics.get("debet", 0.0)
    kre_src = source_metrics.get("kredit", 0.0)
    kre_out = output_metrics.get("kredit", 0.0)
    sk_src = source_metrics.get("saldo_akhir")
    sk_out = output_metrics.get("saldo_akhir", 0.0)
    cnt_src = source_metrics.get("count", 0)
    cnt_out = output_metrics.get("count", 0)
    
    src_label = source_metrics.get("label", "Dokumen Sumber Bank")
    out_label = output_metrics.get("label", "Hasil Accurate")
    
    # Delta calculations
    diff_deb = round(abs(deb_out - deb_src), 2)
    diff_kre = round(abs(kre_out - kre_src), 2)
    diff_sa = round(abs(sa_out - sa_src), 2) if sa_src is not None else 0.0
    diff_sk = round(abs(sk_out - sk_src), 2) if sk_src is not None else 0.0
    diff_cnt = abs(cnt_out - cnt_src)
    
    status_deb = "[100% MATCH] (KLOP)" if diff_deb < 0.01 else f"[SELISIH: Rp {diff_deb:,.2f}]"
    status_kre = "[100% MATCH] (KLOP)" if diff_kre < 0.01 else f"[SELISIH: Rp {diff_kre:,.2f}]"
    status_sa = "[100% MATCH] (KLOP)" if (sa_src is None or diff_sa < 0.01) else f"[SELISIH: Rp {diff_sa:,.2f}]"
    status_sk = "[100% MATCH] (KLOP)" if (sk_src is None or diff_sk < 0.01) else f"[SELISIH: Rp {diff_sk:,.2f}]"
    status_cnt = "[100% MATCH] (KLOP)" if diff_cnt == 0 else f"[SELISIH: {diff_cnt} BARIS]"
    
    sa_src_str = f"Rp {sa_src:>14,.2f}" if sa_src is not None else "  (Dihitung Mundur)"
    sk_src_str = f"Rp {sk_src:>14,.2f}" if sk_src is not None else f"Rp {sk_out:>14,.2f}"
    
    line_w = 88
    border = "=" * line_w
    sep = "-" * line_w
    
    lines = [
        border,
        f"        LEMBAR AUDIT REKONSILIASI MUTASI BANK & SALDO KAS ({bank_name.upper()})",
        border,
        f" Rincian Rekening       | {src_label[:22]:<22} | {out_label[:22]:<22} | Status Rekonsiliasi",
        sep,
        f" 1. Saldo Awal Kas      | {sa_src_str:<22} | Rp {sa_out:>14,.2f}   | {status_sa}",
        f" 2. Mutasi Uang Keluar  | Rp {deb_src:>14,.2f}   | Rp {deb_out:>14,.2f}   | {status_deb}",
        f"    (Total Debet)       |                        |                        |",
        f" 3. Mutasi Uang Masuk   | Rp {kre_src:>14,.2f}   | Rp {kre_out:>14,.2f}   | {status_kre}",
        f"    (Total Kredit)      |                        |                        |",
        f" 4. Saldo Akhir Kas     | {sk_src_str:<22} | Rp {sk_out:>14,.2f}   | {status_sk}",
        f" 5. Jumlah Baris Mutasi | {cnt_src:>5} transaksi        | {cnt_out:>5} transaksi        | {status_cnt}",
        sep,
        f" PERSAMAAN SALDO KAS    : Saldo Awal ({sa_out:,.2f}) + Uang Masuk/Kredit ({kre_out:,.2f})",
        f"                        - Uang Keluar/Debet ({deb_out:,.2f}) = Saldo Akhir ({sk_out:,.2f})",
    ]
    
    all_matched = (diff_deb < 0.01 and diff_kre < 0.01 and diff_sa < 0.01 and diff_sk < 0.01 and diff_cnt == 0)
    if all_matched:
        lines.append(" STATUS REKONSILIASI    : [KLOP 100% PERSIS - TIDAK ADA SELISIH (SELISIH Rp 0.00 / ZERO VARIANCE)]")
    else:
        lines.append(" STATUS REKONSILIASI    : [TERDAPAT PENYESUAIAN AUDIT - PERIKSA CATATAN DI BAWAH]")
        
    if notes:
        lines.append(sep)
        lines.append(" CATATAN PENYESUAIAN MUTASI (AUDIT TRAIL):")
        note_list = [notes] if isinstance(notes, str) else notes
        for note in note_list:
            lines.append(f" * {note}")
            
    lines.append(border)
    return "\n".join(lines)
