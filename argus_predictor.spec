# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

# Resolve repository root
SPECPATH = os.path.abspath(SPECPATH)
sys.path.insert(0, os.path.join(SPECPATH, 'scripts'))

# Build argus bytecode zip for business logic decoupling
try:
    from build_delta_package import build_argus_zip
    argus_zip = os.path.join(SPECPATH, 'build', 'argus.zip')
    build_argus_zip(argus_zip, src_dir=os.path.join(SPECPATH, 'src'))
except Exception as e:
    print(f"[argus_predictor.spec] Warning: Could not prebuild argus.zip: {e}")
    argus_zip = os.path.join(SPECPATH, 'build', 'argus.zip')

datas = [
    ('src/argus/web/templates', 'argus/web/templates'),
    ('templates', 'templates'),
    ('config.yaml', '.'),
    ('ums-api-config.json', '.'),
    ('docs/user-manual/book', 'docs/user-manual/book'),
]
if os.path.isfile(argus_zip):
    datas.append((argus_zip, '.'))

binaries = []
hiddenimports = []

# Collect heavy third-party runtimes (PyTorch, Ultralytics, Flask, etc.)
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('flask')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('argus_eventlog')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ums_client')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=['.', 'src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['argus'],
    noarchive=False,
    optimize=0,
)

# Decouple argus business code from PYZ so it is loaded from _internal/argus.zip
a.pure = [x for x in a.pure if not x[0].startswith('argus')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='argus_predictor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='argus_predictor',
)
