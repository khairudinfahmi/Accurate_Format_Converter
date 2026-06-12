# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets/*', 'assets')]
binaries = []
hiddenimports = ['pdfplumber', 'fitz', 'PIL', 'PIL.Image', 'PIL._tkinter_finder']
for pkg in ['PIL', 'charset_normalizer', 'pdfminer']:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

import charset_normalizer
import os, glob
site_packages = os.path.dirname(os.path.dirname(charset_normalizer.__file__))
for f in glob.glob(os.path.join(site_packages, '*__mypyc*.pyd')):
    binaries.append((f, '.'))


a = Analysis(
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
