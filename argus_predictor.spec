# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('src/argus/web/templates', 'argus/web/templates'),
    ('templates', 'templates'),
    ('config.yaml', '.'),
    ('ums-api-config.json', '.'),
    ('docs/user-manual/book', 'docs/user-manual/book'),
]
binaries = []
hiddenimports = [
    'argus',
    'argus.main',
    'argus.core.config_manager',
    'argus.capture.stream_handler',
    'argus.capture.video_handler',
    'argus.capture.grid_composer',
    'argus.vision.inference_engine',
    'argus.compliance.compliance_engine',
    'argus.events.stats_logger',
    'argus.events.event_producer',
    'argus.events.retention_cleaner',
    'argus.events.diagnostic_collector',
    'argus.integration.model_sync',
    'argus.integration.ums_config',
    'argus.integration.failover_ums_client',
    'argus.integration.state_poller',
    'argus.integration.issue_service_client',
    'argus.integration.report_issue',
    'argus.web.web_ui',
]
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('flask')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('argus_eventlog')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ums_client')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['src/argus/main.py'],
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
    name='argus_predictor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
