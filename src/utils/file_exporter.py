import os
import xlwt
import datetime
import pandas as pd
try:
    import openpyxl  # pyright: ignore[reportUnusedImport]
    _ = openpyxl
except ImportError:
    pass

TARGET_SHEET_NAME = "Sheet1" 

def save_exact_xls(dataframe, filepath, num_dummy, columns):
    book = xlwt.Workbook(encoding='utf-8')
    sheet = book.add_sheet(TARGET_SHEET_NAME)
    
    style_header = xlwt.easyxf('font: bold on, height 220; align: horiz center; pattern: pattern solid, fore_colour gray25')
    style_text = xlwt.easyxf(num_format_str='@') 
    style_num = xlwt.easyxf(num_format_str='#,##0.00') 
    style_general = xlwt.easyxf(num_format_str='General')
    
    str_dummy = 'font: colour red, italic on; pattern: pattern solid, fore_colour gray25;'
    style_text_dummy = xlwt.easyxf(str_dummy, num_format_str='@')
    style_num_dummy = xlwt.easyxf(str_dummy, num_format_str='#,##0.00')
    style_general_dummy = xlwt.easyxf(str_dummy, num_format_str='General')
    
    str_sep = 'pattern: pattern solid, fore_colour light_yellow; font: bold on;'
    style_text_sep = xlwt.easyxf(str_sep, num_format_str='@')
    style_num_sep = xlwt.easyxf(str_sep, num_format_str='#,##0.00')
    style_general_sep = xlwt.easyxf(str_sep, num_format_str='General')
        
    for col_idx, col_name in enumerate(columns):
        sheet.write(0, col_idx, col_name, style_header)
        sheet.col(col_idx).width = 256 * (60 if col_idx == 1 else 18)

    df_ordered = dataframe[columns]
    for row_idx, row in enumerate(df_ordered.values):
        excel_row = row_idx + 1
        if row_idx < num_dummy:
            s_text, s_num, s_gen = style_text_dummy, style_num_dummy, style_general_dummy
        elif row_idx == num_dummy:
            s_text, s_num, s_gen = style_text_sep, style_num_sep, style_general_sep
        else:
            s_text, s_num, s_gen = style_text, style_num, style_general

        sheet.write(excel_row, 0, str(row[0]) if pd.notna(row[0]) and row[0] else "", s_text)
        sheet.write(excel_row, 1, str(row[1]) if pd.notna(row[1]) else "", s_text)
        
        def write_number_safe(col_idx, val, st_num, st_gen):
            if pd.isna(val) or val == "" or val is None: sheet.write(excel_row, col_idx, "", st_gen)
            else:
                try: sheet.write(excel_row, col_idx, float(val), st_num)
                except Exception: sheet.write(excel_row, col_idx, val, st_gen)

        write_number_safe(2, row[2], s_num, s_gen)
        write_number_safe(3, row[3], s_num, s_gen)
        write_number_safe(4, row[4], s_num, s_gen)
    
    try:
        book.save(filepath)
        return True
    except Exception as e:
        raise Exception(f"Failed to save excel: {e}")

def save_invalid_dates(invalid_data, source_file, log_callback=print):
    try:
        source_dir = os.path.dirname(source_file)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        error_file = os.path.join(source_dir, f"tanggal_tidak_valid_{timestamp}.xlsx")
        df_invalid = pd.DataFrame(invalid_data)
        df_invalid.to_excel(error_file, index=False)
        return error_file
    except Exception as e:
        log_callback(f"Gagal generate error file: {e}")
        return None
