import unittest
import os
import sys
import tempfile
import csv
import datetime
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from processors.bca_processor import _reconcile_bca_transactions, _process_bca_csv
from processors.panin_processor import process_panin, OUTPUT_COLUMNS
from processors.panin_scan_processor import process_panin_scanned_pdf
from utils.helpers import clean_currency, parse_date_tolerant

class TestBalanceMathAndDirectionGuard(unittest.TestCase):

    def test_bca_reconciler_single_step(self):
        """Test BCA reconciler koreksi baris tunggal yang terbalik."""
        txs = [{"tanggal": "'01/01", "keterangan": "TEST TRF", "cabang": "'0000", "mutasi": 500000.0, "tipe": "DB", "saldo_printed": 1500000.0}]
        reconciled, bal, count, deb, kre = _reconcile_bca_transactions(txs, 1000000.0, lambda m: None)
        
        self.assertEqual(reconciled[0]["tipe"], "CR")
        self.assertEqual(deb, 0.0)
        self.assertEqual(kre, 500000.0)
        self.assertEqual(bal, 1500000.0)
        self.assertEqual(reconciled[0]["saldo"], 1500000.0)

    def test_bca_reconciler_cluster_multi_transaction(self):
        """Test Look-Ahead Cluster Solver untuk transaksi beruntun tanpa saldo perantara."""
        txs = [
            {"tanggal": "'05/01", "keterangan": "BELANJA", "cabang": "'0000", "mutasi": 2000000.0, "tipe": "CR", "saldo_printed": None},
            {"tanggal": "'05/01", "keterangan": "SETORAN", "cabang": "'0000", "mutasi": 7000000.0, "tipe": "CR", "saldo_printed": None},
            {"tanggal": "'05/01", "keterangan": "BIAYA", "cabang": "'0000", "mutasi": 1500000.0, "tipe": "CR", "saldo_printed": 13500000.0},
        ]
        reconciled, bal, count, deb, kre = _reconcile_bca_transactions(txs, 10000000.0, lambda m: None)
        
        self.assertEqual(reconciled[0]["tipe"], "DB")
        self.assertEqual(reconciled[1]["tipe"], "CR")
        self.assertEqual(reconciled[2]["tipe"], "DB")
        self.assertEqual(deb, 3500000.0)
        self.assertEqual(kre, 7000000.0)
        self.assertEqual(bal, 13500000.0)

    def test_bca_csv_missing_or_attached_markers(self):
        """Test BCA CSV jika penanda mutasi tanpa spasi atau hilang, saldo mengoreksi."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as f:
            f.write("No. rekening : 1234567890\n")
            f.write("Nama : NASABAH TEST\n")
            f.write("Periode : 01/01/2026 - 31/01/2026\n")
            f.write("Saldo Awal : 5,000,000.00\n")
            f.write("Saldo Akhir : 6,200,000.00\n")
            f.write('"Tanggal Transaksi","Keterangan","Cabang","Jumlah","Saldo"\n')
            f.write('"05/01","TRANSFER CR","0000","2,000,000.00CR","7,000,000.00"\n')
            f.write('"06/01","TARIKAN ATM","0000","800,000.00","6,200,000.00"\n')
            f_path = f.name

        try:
            results = []
            def succ_cb(txs, rek, nm, sa, sak, fp):
                results.append((txs, sa, sak))
                
            def err_cb(e):
                self.fail(str(e))
                
            _process_bca_csv(f_path, lambda m: None, lambda p: None, succ_cb, err_cb)
            
            self.assertEqual(len(results), 1)
            txs, sa, sak = results[0]
            self.assertEqual(len(txs), 2)
            self.assertEqual(txs[0]["tipe"], "CR")
            self.assertEqual(txs[0]["mutasi"], 2000000.0)
            self.assertEqual(txs[0]["saldo"], 7000000.0)
            self.assertEqual(txs[1]["tipe"], "DB")
            self.assertEqual(txs[1]["mutasi"], 800000.0)
            self.assertEqual(txs[1]["saldo"], 6200000.0)
            self.assertEqual(sak, 6200000.0)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_panin_excel_direction_guard_auto_swap(self):
        """Test Panin Excel/CSV jika kolom debet dan kredit tertukar di baris tertentu."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as f:
            f.write("TANGGAL,DESKRIPSI,DEBET,KREDIT,SALDO\n")
            f.write("01/01/2026,SALDO AWAL DUMMY,,10000000,10000000\n")
            f.write("02/01/2026,UANG MASUK TERTUKAR,5000000,,15000000\n")
            f.write("03/01/2026,UANG KELUAR TERTUKAR,,3000000,12000000\n")
            f_path = f.name

        try:
            results = []
            def succ_cb(df_out, inv, dummy, fp):
                results.append(df_out)
                
            def err_cb(e):
                self.fail(str(e))
                
            process_panin(f_path, False, lambda m: None, lambda p: None, succ_cb, err_cb)
            
            self.assertEqual(len(results), 1)
            df = results[0]
            row_in = df.iloc[9]
            self.assertEqual(row_in[OUTPUT_COLUMNS['desc']], "UANG MASUK TERTUKAR")
            self.assertEqual(row_in[OUTPUT_COLUMNS['kre']], 5000000.0)
            self.assertEqual(row_in[OUTPUT_COLUMNS['deb']], "")
            self.assertEqual(float(row_in[OUTPUT_COLUMNS['bal']]), 15000000.0)
            
            row_out = df.iloc[10]
            self.assertEqual(row_out[OUTPUT_COLUMNS['desc']], "UANG KELUAR TERTUKAR")
            self.assertEqual(row_out[OUTPUT_COLUMNS['deb']], 3000000.0)
            self.assertEqual(row_out[OUTPUT_COLUMNS['kre']], "")
            self.assertEqual(float(row_out[OUTPUT_COLUMNS['bal']]), 12000000.0)
            
            row_tot = df.iloc[-2]
            self.assertEqual(row_tot[OUTPUT_COLUMNS['deb']], 3000000.0)
            self.assertEqual(row_tot[OUTPUT_COLUMNS['kre']], 15000000.0)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_panin_scanned_benchmarks(self):
        """Memverifikasi bahwa dokumen scan fisik 4-hal dan 22-hal 100% klop Rp 0.00."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p4 = os.path.join(repo_root, "Scanned Document.pdf")
        p22 = os.path.join(repo_root, "CamScanner 04-09-2026 10.20.pdf")
        
        for p_file, exp_count, exp_bal in [(p4, 75, 89084592.01), (p22, 372, 25637580.91)]:
            if os.path.exists(p_file):
                results = []
                def succ_cb(df, inv, dummy, fp):
                    results.append((df, dummy))
                def err_cb(e):
                    self.fail(str(e))
                process_panin_scanned_pdf(p_file, lambda m: None, lambda p: None, succ_cb, err_cb)
                
                self.assertEqual(len(results), 1)
                df, dummy = results[0]
                tx_df = df.iloc[dummy+1 : -2]
                self.assertEqual(len(tx_df), exp_count)
                
                last_bal = float(df.iloc[-1][OUTPUT_COLUMNS['bal']])
                self.assertAlmostEqual(last_bal, exp_bal, places=2)
                
                for _, r in tx_df.iterrows():
                    d = clean_currency(r[OUTPUT_COLUMNS['deb']])
                    k = clean_currency(r[OUTPUT_COLUMNS['kre']])
                    self.assertTrue((d > 0 and k == 0) or (k > 0 and d == 0))

    def test_panin_sample_xls_file(self):
        """Memverifikasi file sample Scanned Document (Template Excel Formatter).xls."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p_xls = os.path.join(repo_root, "Scanned Document (Template Excel Formatter).xls")
        if os.path.exists(p_xls):
            results = []
            def succ_cb(df, inv, dummy, fp):
                results.append((df, dummy))
            def err_cb(e):
                self.fail(str(e))
            process_panin(p_xls, False, lambda m: None, lambda p: None, succ_cb, err_cb)
            self.assertEqual(len(results), 1)
            df, dummy = results[0]
            self.assertEqual(dummy, 7)
            tx_df = df.iloc[dummy+1 : -2]
            self.assertGreater(len(tx_df), 0)
            
            # Cek invarian Debet vs Kredit
            for _, r in tx_df.iterrows():
                d = clean_currency(r[OUTPUT_COLUMNS['deb']])
                k = clean_currency(r[OUTPUT_COLUMNS['kre']])
                self.assertTrue((d > 0 and k == 0) or (k > 0 and d == 0))

    def test_clean_currency_edge_cases(self):
        """Test clean_currency menangani trailing minus, multi-titik desimal, dan nilai negatif."""
        self.assertEqual(clean_currency("500,000.00-"), 500000.0)
        self.assertEqual(clean_currency("-500,000.00"), 500000.0)
        self.assertEqual(clean_currency("(500,000.00)"), 500000.0)
        self.assertEqual(clean_currency("10.000.00"), 10000.0)
        self.assertEqual(clean_currency("1.500.000,50"), 1500000.5)
        self.assertEqual(clean_currency("1,500,000.50"), 1500000.5)
        self.assertEqual(clean_currency("1.500.000"), 1500000.0)

    def test_parse_date_tolerant_edge_cases(self):
        """Test parse_date_tolerant menangani Timestamp, string berjam, bulan Indonesia, dan serial Excel."""
        # 1. Objek Timestamp & date
        t1 = parse_date_tolerant(pd.Timestamp("2026-01-15"))
        assert isinstance(t1, pd.Timestamp)
        self.assertEqual(t1.strftime('%d/%m/%Y'), "15/01/2026")
        t2 = parse_date_tolerant(datetime.date(2026, 1, 15))
        assert isinstance(t2, pd.Timestamp)
        self.assertEqual(t2.strftime('%d/%m/%Y'), "15/01/2026")
        
        # 2. String dengan komponen jam
        t3 = parse_date_tolerant("2026-01-15 00:00:00")
        assert isinstance(t3, pd.Timestamp)
        self.assertEqual(t3.strftime('%d/%m/%Y'), "15/01/2026")
        t4 = parse_date_tolerant("15/01/2026 14:30:00")
        assert isinstance(t4, pd.Timestamp)
        self.assertEqual(t4.strftime('%d/%m/%Y'), "15/01/2026")
        
        # 3. Bulan tekstual Indonesia
        t5 = parse_date_tolerant("15-Okt-2024")
        assert isinstance(t5, pd.Timestamp)
        self.assertEqual(t5.strftime('%d/%m/%Y'), "15/10/2024")
        t6 = parse_date_tolerant("15 Mei 2025")
        assert isinstance(t6, pd.Timestamp)
        self.assertEqual(t6.strftime('%d/%m/%Y'), "15/05/2025")
        
        # 4. Angka serial integer Excel
        t7 = parse_date_tolerant(45300) # 2024-01-09
        assert isinstance(t7, pd.Timestamp)
        self.assertEqual(t7.strftime('%d/%m/%Y'), "09/01/2024")
        t8 = parse_date_tolerant("45300")
        assert isinstance(t8, pd.Timestamp)
        self.assertEqual(t8.strftime('%d/%m/%Y'), "09/01/2024")

    def test_bca_large_cluster_solver(self):
        """Test Look-Ahead Cluster Solver menangani cluster besar (>12 transaksi) via Single-Flip & Double-Flip."""
        txs = []
        for i in range(14):
            t_type = "DB" if i == 7 else "CR"
            txs.append({"tanggal": "'10/01", "keterangan": f"TX {i+1}", "cabang": "'0000", "mutasi": 100000.0, "tipe": t_type, "saldo_printed": None})
        txs.append({"tanggal": "'10/01", "keterangan": "TX 15", "cabang": "'0000", "mutasi": 100000.0, "tipe": "CR", "saldo_printed": 11500000.0})
        
        reconciled, bal, count, deb, kre = _reconcile_bca_transactions(txs, 10000000.0, lambda m: None)
        
        self.assertEqual(bal, 11500000.0)
        self.assertEqual(deb, 0.0)
        self.assertEqual(kre, 1500000.0)
        self.assertEqual(reconciled[7]["tipe"], "CR")

    def test_panin_row0_keyword_guard(self):
        """Test Guard Baris Pertama Panin mengoreksi transaksi pertama jika salah kolom di sumber."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as f:
            f.write("TANGGAL,DESKRIPSI,DEBET,KREDIT,SALDO\n")
            f.write("01/01/2026,BIFAST FROM FLIPTECH,1000000,,1000000\n")
            f.write("02/01/2026,SETORAN TUNAI,,500000,1500000\n")
            f_path = f.name

        try:
            results = []
            def succ_cb(df_out, inv, dummy, fp):
                results.append(df_out)
            def err_cb(e):
                self.fail(str(e))
            process_panin(f_path, False, lambda m: None, lambda p: None, succ_cb, err_cb)
            self.assertEqual(len(results), 1)
            df = results[0]
            # Baris 1 data asli ada di indeks dummy(7) + 1 (Saldo Awal) = 8
            row_0 = df.iloc[8]
            self.assertEqual(row_0[OUTPUT_COLUMNS['kre']], 1000000.0)
            self.assertEqual(row_0[OUTPUT_COLUMNS['deb']], "")
            
            # Saldo awal harus 0.0 (1,000,000 - 1,000,000)
            row_sa = df.iloc[7]
            self.assertEqual(float(row_sa[OUTPUT_COLUMNS['bal']]), 0.0)
            # Verifikasi audit_table disematkan ke df.attrs
            self.assertIn("audit_table", df.attrs)
            self.assertIn("LEMBAR REKONSILIASI MUTASI BANK DAN SALDO KAS", df.attrs["audit_table"])
            self.assertIn("TERDAPAT PENYESUAIAN MUTASI", df.attrs["audit_table"])
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_audit_reconciliation_table_formatter(self):
        """Pengujian penyusunan tabel lembar rekonsiliasi kas dan mutasi bank."""
        from utils.helpers import format_audit_reconciliation_table
        
        # Skenario 1: Rekonsiliasi Klop
        src_metrics = {
            "label": "File Sumber Bank",
            "saldo_awal": 500000.0,
            "debet": 250000.0,
            "kredit": 750000.0,
            "saldo_akhir": 1000000.0,
            "count_deb": 4,
            "count_kre": 6,
            "count": 10
        }
        out_metrics = {
            "label": "Hasil Accurate",
            "saldo_awal": 500000.0,
            "debet": 250000.0,
            "kredit": 750000.0,
            "saldo_akhir": 1000000.0,
            "count_deb": 4,
            "count_kre": 6,
            "count": 10
        }
        table_str = format_audit_reconciliation_table("BCA", src_metrics, out_metrics, notes="Semua cocok.")
        self.assertIn("[COCOK / KLOP]", table_str)
        self.assertIn("SEMUA MUTASI DAN SALDO 100% KLOP", table_str)
        self.assertIn("Total Transaksi Debet", table_str)
        self.assertIn("Total Transaksi Kredit", table_str)
        self.assertIn("Semua cocok.", table_str)
        self.assertNotIn("ZERO VARIANCE", table_str)
        self.assertNotIn("AUDIT TRAIL", table_str)

        # Test 2: Catatan list
        table_with_list = format_audit_reconciliation_table("Panin", src_metrics, out_metrics, notes=["Koreksi 1", "Koreksi 2"])
        self.assertIn("* Koreksi 1", table_with_list)
        self.assertIn("* Koreksi 2", table_with_list)

        # Test 3: Terdeteksi delta selisih
        src_diff = dict(src_metrics, debet=200000.0)
        table_diff = format_audit_reconciliation_table("BCA", src_diff, out_metrics)
        self.assertIn("SELISIH: Rp 50,000.00", table_diff)
        self.assertIn("TERDAPAT PENYESUAIAN MUTASI", table_diff)

if __name__ == '__main__':
    unittest.main()
