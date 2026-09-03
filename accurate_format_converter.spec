# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import charset_normalizer
import os, glob

# --- SECURITY FIX: Restrict assets to prevent PFX certificate leakage ---
datas = [('assets/*.png', 'assets'), ('assets/*.ico', 'assets')]
binaries = []
hiddenimports = ['pdfplumber', 'fitz', 'PIL', 'PIL.Image', 'PIL._tkinter_finder', 'xlrd', 'openpyxl', 'xlwt', 'customtkinter', 'pandas', 'pypdfium2']
for pkg in ['PIL', 'charset_normalizer', 'pdfminer', 'xlrd', 'openpyxl', 'xlwt', 'customtkinter', 'pandas', 'pypdfium2']:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

site_packages = os.path.dirname(os.path.dirname(charset_normalizer.__file__))
for f in glob.glob(os.path.join(site_packages, '*__mypyc*.pyd')):
    binaries.append((f, '.'))

# --- ANALYSIS 1: Main App ---
a1 = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz1 = PYZ(a1.pure)

exe1 = EXE(
    pyz1,
    a1.scripts,
    [],
    exclude_binaries=True,
    name='Accurate_Format_Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\rensa_logo.ico'],
)

# --- ANALYSIS 2: Launcher ---
a2 = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/*.png', 'assets'), ('assets/*.ico', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz2 = PYZ(a2.pure)

exe2 = EXE(
    pyz2,
    a2.scripts,
    [],
    exclude_binaries=True,
    name='Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\rensa_logo.ico'],
)

# --- COLLECT BOTH INTO SHARED DIRECTORY ---
coll = COLLECT(
    exe1,
    a1.binaries,
    a1.zipfiles,
    a1.datas,
    exe2,
    a2.binaries,
    a2.zipfiles,
    a2.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Accurate_Format_Converter',
)
