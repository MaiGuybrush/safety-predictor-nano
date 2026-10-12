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
    ('scripts/run.sh', 'scripts'),
    ('scripts/install.sh', 'scripts'),
    ('scripts/install.py', 'scripts'),
    ('scripts/ask_and_report.sh', 'scripts'),
    ('scripts/ask_and_report.bat', 'scripts'),
    ('scripts/run.bat', 'scripts'),
]
if os.path.isfile(argus_zip):
    datas.append((argus_zip, '.'))

binaries = []
hiddenimports = []
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('flask')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('argus_eventlog')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ums_client')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# onnx / onnxruntime 為必要依賴（Ultralytics 以套件 metadata 檢查，缺 metadata 會觸發
# AutoUpdate 並遞迴啟動執行檔，見 issue #95）。缺少時建置直接失敗，不靜默略過。
from PyInstaller.utils.hooks import copy_metadata
for _pkg in ('onnx', 'onnxruntime'):
    try:
        __import__(_pkg)
        tmp_ret = collect_all(_pkg)
        datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
        datas += copy_metadata(_pkg)
    except Exception as _e:
        raise SystemExit(
            f"[argus_predictor.spec] ERROR: 必要依賴 '{_pkg}' 無法打包 ({_e})。"
            "請先安裝 requirements.txt 中的 onnx / onnxruntime。"
        )


a = Analysis(
    ['main.py'],
    pathex=['.', 'src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ['scripts.probe_package'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['argus', 'triton'],
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
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name='argus_predictor',
)

# 確保守護與維運腳本同步部署至 dist/argus_predictor/scripts/ (遵循 ADR-005 與 ADR-019)
import shutil
dist_scripts = os.path.join(SPECPATH, 'dist', 'argus_predictor', 'scripts')
os.makedirs(dist_scripts, exist_ok=True)
for sname in ['run.sh', 'run.bat', 'install.sh', 'install.py', 'ask_and_report.sh', 'ask_and_report.bat']:
    src_s = os.path.join(SPECPATH, 'scripts', sname)
    if os.path.isfile(src_s):
        shutil.copy2(src_s, os.path.join(dist_scripts, sname))

