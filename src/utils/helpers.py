import sys
import os
import re
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
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(base_path, relative_path)

def clean_currency(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    
    if not val: return 0.0
    s = str(val).strip().lower()
    if s in ['nan', 'none', '', '-', 'null']: return 0.0
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
            if parts[-1] == '0': pass 
            elif len(parts[-1]) != 2: s = s.replace('.', '')
            else: pass 
        return float(s)
    except:
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

def parse_date_tolerant(date_str, log_callback=print):
    try:
        s = str(date_str).strip()
        if not s or s.lower() in ['nan', 'none', 'null']: return pd.NaT
        s = re.sub(r'[^\d\/\-\.]', '', s)
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%d-%m-%y', '%d.%m.%y', '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d']:
            try: return pd.to_datetime(s, format=fmt, dayfirst=True)
            except: continue
        numbers = re.findall(r'\d+', s)
        if len(numbers) >= 3:
            day, month, year = numbers[0], numbers[1], numbers[2]
            if len(year) == 2: year = '20' + year if int(year) < 50 else '19' + year
            elif len(year) == 1: year = '200' + year
            day = int(day) if int(day) <= 31 else 1
            month = int(month) if int(month) <= 12 else 1
            try: return pd.to_datetime(f"{int(day):02d}/{int(month):02d}/{year}", dayfirst=True, errors='coerce')
            except: return pd.NaT
        return pd.NaT
    except Exception as e:
        log_callback(f"Error parsing date '{date_str}': {e}")
        return pd.NaT
