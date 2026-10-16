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
    Menghasilkan Lembar Rekonsiliasi Mutasi Bank dan Saldo Kas Berdampingan:
    Membandingkan Saldo Awal, Total Debet, Total Kredit, Saldo Akhir, serta
    Rincian Jumlah Transaksi Debet, Kredit, dan Total Mutasi.
    """
    COL1_W = 26
    COL2_W = 24
    COL3_W = 24
    COL4_W = 18

    sa_src = source_metrics.get("saldo_awal")
    sa_out = output_metrics.get("saldo_awal", 0.0)
    deb_src = source_metrics.get("debet", 0.0)
    deb_out = output_metrics.get("debet", 0.0)
    kre_src = source_metrics.get("kredit", 0.0)
    kre_out = output_metrics.get("kredit", 0.0)
    sk_src = source_metrics.get("saldo_akhir")
    sk_out = output_metrics.get("saldo_akhir", 0.0)

    cnt_deb_src = source_metrics.get("count_deb", 0)
    cnt_deb_out = output_metrics.get("count_deb", 0)
    cnt_kre_src = source_metrics.get("count_kre", 0)
    cnt_kre_out = output_metrics.get("count_kre", 0)
    cnt_tot_src = source_metrics.get("count", cnt_deb_src + cnt_kre_src)
    cnt_tot_out = output_metrics.get("count", cnt_deb_out + cnt_kre_out)

    src_label = source_metrics.get("label", "Dokumen Sumber Bank")
    out_label = output_metrics.get("label", "Hasil Accurate")

    # Perhitungan selisih pembukuan
    diff_deb = round(abs(deb_out - deb_src), 2)
    diff_kre = round(abs(kre_out - kre_src), 2)
    diff_sa = round(abs(sa_out - sa_src), 2) if sa_src is not None else 0.0
    diff_sk = round(abs(sk_out - sk_src), 2) if sk_src is not None else 0.0
    diff_cnt_deb = abs(cnt_deb_out - cnt_deb_src)
    diff_cnt_kre = abs(cnt_kre_out - cnt_kre_src)
    diff_cnt_tot = abs(cnt_tot_out - cnt_tot_src)

    status_sa = "[Cocok / Klop]" if (sa_src is None or diff_sa < 0.01) else f"[Selisih: Rp {diff_sa:,.2f}]"
    status_deb = "[Cocok / Klop]" if diff_deb < 0.01 else f"[Selisih: Rp {diff_deb:,.2f}]"
    status_kre = "[Cocok / Klop]" if diff_kre < 0.01 else f"[Selisih: Rp {diff_kre:,.2f}]"
    status_sk = "[Cocok / Klop]" if (sk_src is None or diff_sk < 0.01) else f"[Selisih: Rp {diff_sk:,.2f}]"
    status_cnt_deb = "[Cocok / Klop]" if diff_cnt_deb == 0 else f"[Selisih: {diff_cnt_deb} baris]"
    status_cnt_kre = "[Cocok / Klop]" if diff_cnt_kre == 0 else f"[Selisih: {diff_cnt_kre} baris]"
    status_cnt_tot = "[Cocok / Klop]" if diff_cnt_tot == 0 else f"[Selisih: {diff_cnt_tot} baris]"

    def c_curr(v):
        return f"Rp {v:>15,.2f}" if v is not None else "(Dihitung Mundur)"

    def c_cnt(n):
        return f"{n:>6} transaksi"

    def row(name, val2, val3, stat, is_header=False):
        c1 = f" {name:<{COL1_W-1}}"
        if is_header:
            c2 = f" {val2:^{COL2_W-2}} "
            c3 = f" {val3:^{COL3_W-2}} "
        else:
            c2 = f" {val2:>{COL2_W-2}} "
            c3 = f" {val3:>{COL3_W-2}} "
        c4 = f" {stat:<{COL4_W-1}}"
        return f"{c1}|{c2}|{c3}|{c4}"

    header_row = row("Pos Rekening / Mutasi", src_label, out_label, "Status Rekonsiliasi", is_header=True)
    line_w = len(header_row)
    border = "=" * line_w
    sep = "-" * line_w

    title = f"Lembar Rekonsiliasi Mutasi Bank dan Saldo Kas ({bank_name})"
    subtitle = "(Pencocokan Integritas File Sumber Bank vs File Siap Impor Accurate)"
    lines = [
        border,
        f"{title:^{line_w}}",
        f"{subtitle:^{line_w}}",
        border,
        header_row,
        sep,
        row("1. Saldo Awal Kas", c_curr(sa_src), c_curr(sa_out), status_sa),
        row("2. Mutasi Debet (Keluar)", c_curr(deb_src), c_curr(deb_out), status_deb),
        row("3. Mutasi Kredit (Masuk)", c_curr(kre_src), c_curr(kre_out), status_kre),
        row("4. Saldo Akhir Kas", c_curr(sk_src), c_curr(sk_out), status_sk),
        sep,
        row("5. Total Transaksi Debet", c_cnt(cnt_deb_src), c_cnt(cnt_deb_out), status_cnt_deb),
        row("6. Total Transaksi Kredit", c_cnt(cnt_kre_src), c_cnt(cnt_kre_out), status_cnt_kre),
        row("7. Total Semua Mutasi", c_cnt(cnt_tot_src), c_cnt(cnt_tot_out), status_cnt_tot),
        sep,
        f" Persamaan Saldo Kas      : Saldo Awal ({sa_out:,.2f}) + Total Kredit ({kre_out:,.2f})",
        f"                          - Total Debet ({deb_out:,.2f}) = Saldo Akhir ({sk_out:,.2f})",
        f"                            (Sudut Pandang Bank: Kredit = Uang Masuk +, Debet = Uang Keluar -)",
    ]

    all_matched = (
        diff_deb < 0.01 and diff_kre < 0.01 and diff_sa < 0.01 and diff_sk < 0.01
        and diff_cnt_deb == 0 and diff_cnt_kre == 0 and diff_cnt_tot == 0
    )
    if all_matched:
        lines.append(" Status Keseluruhan       : [Semua mutasi dan saldo 100% klop - Tidak ada selisih (Rp 0.00)]")
    else:
        lines.append(" Status Keseluruhan       : [Terdapat penyesuaian mutasi - Silakan periksa catatan di bawah]")

    if notes:
        lines.append(sep)
        lines.append(" Catatan Penyesuaian Mutasi:")
        note_list = [notes] if isinstance(notes, str) else notes
        for note in note_list:
            lines.append(f" * {note}")

    lines.append(sep)
    lines.append(" Panduan Penting Konteks \"Klop\" & Rekomendasi Format:")
    lines.append(" 1. Arti \"Klop\" Konversi File (Bukan Buku Besar Accurate):")
    lines.append("    Status [Cocok / Klop] membuktikan file hasil konversi sudah 100% identik dengan file")
    lines.append("    asli tarikan bank (tidak ada mutasi terlewat & nominal tidak rusak). Pencocokan jurnal")
    lines.append("    akuntansi tetap dilakukan di menu Rekonsiliasi Bank Accurate Online setelah diimpor.")
    lines.append(" 2. Sudut Pandang Rekening Koran Bank:")
    lines.append("    Menggunakan standar bank: Kredit = Uang Masuk (+) dan Debet = Uang Keluar (-).")
    lines.append("    Format ini sudah tepat untuk menu impor mutasi rekening koran (Smartlink) di Accurate.")
    lines.append(" 3. Saran Format Paling Stabil (Sangat Disarankan):")
    lines.append("    Gunakan Template 1 (Format JSON AOL) karena format JSON resmi Accurate Online ini")
    lines.append("    paling stabil, baku, dan jarang berubah-ubah dibandingkan format laporan perbankan.")
    lines.append(border)
    return "\n".join(lines)
