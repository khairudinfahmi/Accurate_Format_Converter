import unittest
import os
import sys
import tempfile
import csv
import datetime
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from processors.bca_processor import _reconcile_bca_transactions, _process_bca_csv, process_bca
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
        """Memverifikasi file sample Scanned Document (Template AOL Format Excel (Non-JSON)).xls."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p_xls = os.path.join(repo_root, "Scanned Document (Template AOL Format Excel (Non-JSON)).xls")
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
            self.assertIn("Lembar Rekonsiliasi Mutasi Bank dan Saldo Kas", df.attrs["audit_table"])
            self.assertIn("Terdapat penyesuaian mutasi", df.attrs["audit_table"])
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
        self.assertIn("[Cocok / Klop]", table_str)
        self.assertIn("Semua mutasi dan saldo 100% klop", table_str)
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
        self.assertIn("Selisih: Rp 50,000.00", table_diff)
        self.assertIn("Terdapat penyesuaian mutasi", table_diff)

    def test_save_aol_json_schema_compliance(self):
        """Verifikasi bahwa output save_aol_json 100% mematuhi struktur sample-file-aol-format-json.json"""
        import json
        from utils.file_exporter import save_aol_json

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        official_sample_path = os.path.join(repo_root, "templatehasilkonversi", "sample-file-aol-format-json.json")
        
        with open(official_sample_path, "r", encoding="utf-8") as f:
            official_data = json.load(f)

        # Kunci root kanonikal
        expected_root_keys = set(official_data.keys())
        expected_item_keys = set(official_data["mutationList"][0].keys())

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tf:
            test_json_path = tf.name

        try:
            mutations = [
                {"transDate": "10/01/2026", "description": "SETORAN CUSTOMER A", "amount": 2500000.0, "balance": 12500000.0},
                {"transDate": "12/01/2026", "description": "BAYAR LISTRIK & AIR", "amount": -750000.0, "balance": 11750000.0},
                {"transDate": "15/01/2026", "description": "BIAYA ADMIN BANK", "amount": -15000.0, "balance": 11735000.0}
            ]
            save_aol_json(test_json_path, "07101999", 10000000.0, 11735000.0, mutations)

            with open(test_json_path, "r", encoding="utf-8") as f:
                generated_data = json.load(f)

            # 1. Verifikasi kunci root
            self.assertEqual(set(generated_data.keys()), expected_root_keys)
            self.assertEqual(generated_data["accountNumber"], "07101999")
            self.assertEqual(generated_data["openingBalance"], 10000000.0)
            self.assertEqual(generated_data["closingBalance"], 11735000.0)
            self.assertEqual(len(generated_data["mutationList"]), 3)

            # 2. Verifikasi kunci item mutasi
            for item in generated_data["mutationList"]:
                self.assertEqual(set(item.keys()), expected_item_keys)
                self.assertIsInstance(item["transDate"], str)
                self.assertIsInstance(item["description"], str)
                self.assertIsInstance(item["amount"], (int, float))
                self.assertIsInstance(item["balance"], (int, float))

            # 3. Verifikasi tanda: Debet harus negatif, Kredit harus positif
            self.assertGreater(generated_data["mutationList"][0]["amount"], 0)
            self.assertLess(generated_data["mutationList"][1]["amount"], 0)
            self.assertLess(generated_data["mutationList"][2]["amount"], 0)

            # 4. Verifikasi persamaan saldo kas Accurate Online
            calculated_closing = generated_data["openingBalance"] + sum(m["amount"] for m in generated_data["mutationList"])
            self.assertAlmostEqual(calculated_closing, generated_data["closingBalance"], places=2)

        finally:
            if os.path.exists(test_json_path):
                os.remove(test_json_path)

    def test_bca_and_panin_json_integration(self):
        """Verifikasi bahwa transaksi hasil processor BCA dan Panin dapat diekspor ke format JSON AOL dengan matematis klop."""
        import json
        from utils.file_exporter import save_aol_json

        # 1. BCA Dataset
        txs = [
            {"tanggal": "'05/01", "keterangan": "SETORAN TUNAI", "cabang": "'0000", "mutasi": 2000000.0, "tipe": "CR", "saldo": 7000000.0},
            {"tanggal": "'06/01", "keterangan": "TARIKAN ATM", "cabang": "'0000", "mutasi": 800000.0, "tipe": "DB", "saldo": 6200000.0}
        ]
        bca_mutations = []
        for tx in txs:
            mut = float(tx["mutasi"])
            amt = mut if tx["tipe"] == "CR" else -mut
            bca_mutations.append({
                "transDate": "05/01/2026",
                "description": str(tx["keterangan"]),
                "amount": amt,
                "balance": float(tx["saldo"])
            })

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tf:
            bca_json_path = tf.name

        try:
            save_aol_json(bca_json_path, "1234567890", 5000000.0, 6200000.0, bca_mutations)
            with open(bca_json_path, "r", encoding="utf-8") as f:
                res = json.load(f)
            self.assertEqual(res["accountNumber"], "1234567890")
            self.assertEqual(res["openingBalance"], 5000000.0)
            self.assertEqual(res["closingBalance"], 6200000.0)
            self.assertEqual(len(res["mutationList"]), 2)
            self.assertEqual(res["mutationList"][0]["amount"], 2000000.0)
            self.assertEqual(res["mutationList"][1]["amount"], -800000.0)
            self.assertEqual(res["openingBalance"] + sum(m["amount"] for m in res["mutationList"]), 6200000.0)
        finally:
            if os.path.exists(bca_json_path):
                os.remove(bca_json_path)

    def test_all_10_real_bank_mutation_files(self):
        """Uji ekstensif: 10/10 file asli di folder filemutasiaslibankasli/ harus 100% lulus konversi, 
        selisih Rp 0.00, dan kompatibel diekspor ke schema Accurate Online (AOL) JSON."""
        import glob
        from utils.file_exporter import save_aol_json
        import json

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder_path = os.path.join(repo_root, "filemutasiaslibankasli")
        files = sorted(glob.glob(os.path.join(folder_path, "*")))

        if not os.path.exists(folder_path) or not files:
            self.skipTest(f"Direktori uji mutasi bank asli {folder_path} tidak ditemukan")

        self.assertEqual(len(files), 10, f"Diharapkan 10 file mutasi asli di {folder_path}, ditemukan {len(files)}")

        for fpath in files:
            fname = os.path.basename(fpath)
            with self.subTest(file=fname):
                results = []
                errors = []

                def on_success(txs, rek, nm, sa, sak, fp):
                    results.append((txs, rek, nm, sa, sak))

                def on_error(err):
                    errors.append(err)

                process_bca(
                    filepath=fpath,
                    log_callback=lambda m: None,
                    progress_callback=lambda p: None,
                    success_callback=on_success,
                    error_callback=on_error
                )

                self.assertEqual(len(errors), 0, f"Error saat memproses {fname}: {errors}")
                self.assertEqual(len(results), 1, f"Hasil proses kosong untuk {fname}")

                txs, rek, nm, saldo_awal, saldo_akhir = results[0]
                self.assertGreater(len(txs), 0, f"Tidak ada transaksi ditemukan di {fname}")

                # 1. Verifikasi Checksum Saldo Kas (Diff harus Rp 0.00)
                calculated_sk = saldo_awal + sum(t["mutasi"] if t["tipe"] == "CR" else -t["mutasi"] for t in txs)
                diff = round(calculated_sk - saldo_akhir, 2)
                self.assertEqual(diff, 0.0, f"Selisih saldo kas tidak Rp 0.00 pada {fname}: SA={saldo_awal}, SK={saldo_akhir}, Calc={calculated_sk}, Diff={diff}")

                # 2. Verifikasi Ekspor AOL JSON
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tf:
                    temp_json = tf.name

                try:
                    mutations = []
                    for t in txs:
                        tgl_clean = t["tanggal"].replace("'", "").strip()
                        mut = float(t["mutasi"])
                        amt = mut if t["tipe"] == "CR" else -mut
                        mutations.append({
                            "transDate": tgl_clean,
                            "description": str(t["keterangan"]),
                            "amount": amt,
                            "balance": float(t["saldo"])
                        })

                    save_aol_json(temp_json, rek, saldo_awal, saldo_akhir, mutations)
                    with open(temp_json, 'r', encoding='utf-8') as jf:
                        aol_data = json.load(jf)

                    self.assertEqual(aol_data["accountNumber"], rek)
                    self.assertEqual(aol_data["openingBalance"], saldo_awal)
                    self.assertEqual(aol_data["closingBalance"], saldo_akhir)
                    self.assertEqual(len(aol_data["mutationList"]), len(txs))

                    calc_aol = aol_data["openingBalance"] + sum(m["amount"] for m in aol_data["mutationList"])
                    self.assertAlmostEqual(calc_aol, aol_data["closingBalance"], places=2)
                finally:
                    if os.path.exists(temp_json):
                        os.remove(temp_json)

    def test_bca_multipage_tahapan_glenn_pdf(self):
        """Verifikasi bahwa file BCA Tahapan multi-halaman (23 halaman, 253 transaksi) 100% klop Rp 0.00 dan bebas header/footer bleed"""
        from processors.bca_processor import process_bca

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_pdf = os.path.join(repo_root, "sample", "BCA_GLENN GERRY UMBOH_BALI.pdf")
        if not os.path.exists(sample_pdf):
            self.skipTest("Berkas sample BCA_GLENN GERRY UMBOH_BALI.pdf tidak ditemukan")

        results = []
        errors = []
        process_bca(
            sample_pdf,
            log_callback=lambda m: None,
            progress_callback=lambda p: None,
            success_callback=lambda txs, rek, nm, sa, sak, fp: results.append((txs, rek, nm, sa, sak)),
            error_callback=lambda e: errors.append(e)
        )

        self.assertEqual(len(errors), 0, f"Error saat memproses sample BCA Tahapan: {errors}")
        self.assertEqual(len(results), 1)
        txs, rek, nm, sa, sak = results[0]

        self.assertEqual(len(txs), 253)
        self.assertEqual(sa, 0.0)
        self.assertEqual(sak, 13605852.98)

        total_deb = sum(t["mutasi"] for t in txs if t["tipe"] == "DB")
        total_kre = sum(t["mutasi"] for t in txs if t["tipe"] == "CR")
        self.assertEqual(round(total_deb, 2), 350553211.99)
        self.assertEqual(round(total_kre, 2), 364159064.97)

        calc_sk = sa + sum(t["mutasi"] if t["tipe"] == "CR" else -t["mutasi"] for t in txs)
        self.assertEqual(round(calc_sk - sak, 2), 0.0)

        # Pastikan transaksi terakhir adalah Pajak Bunga dengan nominal benar (612.99, bukan 33.0)
        last_tx = txs[-1]
        self.assertIn("PAJAK BUNGA", last_tx["keterangan"].upper())
        self.assertEqual(last_tx["mutasi"], 612.99)
        self.assertEqual(last_tx["tipe"], "DB")

    def test_pend_date_resolution_and_clean_desc(self):
        """Verifikasi bahwa file TRIA CSV dengan status 'PEND' otomatis diselesaikan menjadi tanggal valid 15/10/2026 dan deskripsi dibersihkan"""
        from processors.bca_processor import process_bca
        from utils.file_exporter import save_aol_json
        import re
        import json

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tria_file = os.path.join(repo_root, "filemutasiaslibankasli", "TRIAAGUS9103_1831201137.CSV")
        if not os.path.exists(tria_file):
            self.skipTest("Berkas TRIAAGUS9103_1831201137.CSV tidak ditemukan")

        results = []
        errors = []
        process_bca(
            tria_file,
            log_callback=lambda m: None,
            progress_callback=lambda p: None,
            success_callback=lambda txs, rek, nm, sa, sak, fp: results.append((txs, rek, nm, sa, sak)),
            error_callback=lambda e: errors.append(e)
        )

        self.assertEqual(len(errors), 0, f"Error saat process_bca: {errors}")
        self.assertEqual(len(results), 1)
        txs, rek, nm, sa, sak = results[0]

        # 1. Pastikan saldo awal & akhir sesuai dokumen
        self.assertEqual(sa, 153631583.66)
        self.assertEqual(sak, 77536075.46)
        self.assertEqual(len(txs), 74)

        # 2. Pastikan tidak ada transaksi yang berstatus PEND
        pend_count = sum(1 for t in txs if "PEND" in str(t["tanggal"]).upper())
        self.assertEqual(pend_count, 0, "Ditemukan transaksi dengan tanggal 'PEND'")

        # 3. Pastikan 5 transaksi paling bawah diselesaikan ke 15/10/2026
        for t in txs[-5:]:
            tgl = str(t["tanggal"]).replace("'", "").strip()
            self.assertEqual(tgl, "15/10/2026")

        # 4. Pastikan deskripsi dibersihkan (ada ' - ', 'BIF TRANSFER', pemisah nominal/teks)
        self.assertTrue(any("BI-FAST CR - BIF TRANSFER" in t["keterangan"] for t in txs))
        self.assertTrue(any("TRSF E-BANKING CR - " in t["keterangan"] for t in txs))
        self.assertTrue(any("310000.00 MELLISA" in t["keterangan"] for t in txs))

        # 5. Pastikan ekspor JSON tidak mengandung PEND dan seluruh transDate valid
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tf:
            tria_json = tf.name

        try:
            mutations = []
            for t in txs:
                mut = float(t["mutasi"])
                mutations.append({
                    "transDate": str(t["tanggal"]).replace("'", "").strip(),
                    "description": t["keterangan"],
                    "amount": mut if t["tipe"] == "CR" else -mut,
                    "balance": float(t["saldo"])
                })
            save_aol_json(tria_json, rek, sa, sak, mutations)

            with open(tria_json, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for m in data["mutationList"]:
                self.assertNotIn("PEND", m["transDate"])
                self.assertTrue(bool(re.match(r'^\d{2}/\d{2}/\d{4}$', m["transDate"])))

            # 5 transaksi terakhir di JSON harus bertanggal 15/10/2026
            for m in data["mutationList"][-5:]:
                self.assertEqual(m["transDate"], "15/10/2026")
        finally:
            if os.path.exists(tria_json):
                os.remove(tria_json)

    def test_clean_bca_description_unit(self):
        """Verifikasi pembersihan deskripsi BCA per modul fungsi clean_bca_description"""
        from processors.bca_processor import clean_bca_description

        # E-Banking CR
        c1 = clean_bca_description("TRSF E-BANKING CR 0110/FTSCY/WS95271         310000.00MELLISA PUTRI ST")
        self.assertIn("TRSF E-BANKING CR - ", c1)
        self.assertIn("310000.00 MELLISA", c1)

        # Virtual Account DB
        c2 = clean_bca_description("TRSF E-BANKING DB 0110/FTFVA/WS9532120886/META ADS    -                 -                 14003515649")
        self.assertIn("TRSF E-BANKING DB - ", c2)
        self.assertIn("WS95321 20886/", c2)
        self.assertIn("- -", c2)

        # BI-FAST
        c3 = clean_bca_description("BI-FAST CR TRANSFER   DR 009 TAURIN")
        self.assertIn("BI-FAST CR - BIF TRANSFER", c3)

        # QRIS (KR OTOMATIS)
        c4 = clean_bca_description("KR OTOMATIS TANGGAL :03/10    MID : 885001895042RENSAWALLPAPER ANTQR :    1111000.00DDR:       7564.90")
        self.assertIn("KR OTOMATIS - MID :", c4)
        self.assertIn("885001895042 RENSAWALLPAPER", c4)
        self.assertIn("ANT QR :", c4)
        self.assertIn("1111000.00 DDR:", c4)

        # EDC (KARTU KREDIT)
        c5 = clean_bca_description("KARTU KREDIT MID:001895040     RENSAWALLPAPERSAMATGH:00002181600.00ADM:00000040360.00")
        self.assertIn("KARTU KREDIT - MID:001895040", c5)
        self.assertIn("RENSAWALLPAPERSAMA TGH:", c5)
        self.assertIn(".00 ADM:", c5)

if __name__ == '__main__':
    unittest.main()


