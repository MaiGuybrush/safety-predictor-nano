import pytest
import os
import tempfile
import yaml
from web_ui import app
import web_ui


@pytest.fixture
def client():
    app.config['TESTING'] = True
    temp_dir = tempfile.TemporaryDirectory()
    config_path = os.path.join(temp_dir.name, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump({"mode": "rtsp", "streams": [{"url": "rtsp://127.0.0.1:8554/stream1"}]}, f)

    old_config_file = web_ui.CONFIG_FILE
    web_ui.CONFIG_FILE = config_path
    with app.test_client() as client:
        yield client
    web_ui.CONFIG_FILE = old_config_file
    temp_dir.cleanup()


def test_responsive_css_breakpoints_and_font_scaling(client):
    """驗證 index.html 包含 ADR-016 與 PRD 所規範的 4 階響應式斷點與垂直高度約束樣式。"""
    resp = client.get('/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # 1. 檢查基礎字級與 sys-core 基本設定
    assert 'font-size: 135%;' in html
    assert 'grid-template-columns: 400px 1fr;' in html

    # 2. 檢查 4 階寬度斷點
    assert '@media (max-width: 1439px)' in html
    assert '@media (max-width: 1199px)' in html
    assert '@media (max-width: 991px)' in html
    assert '@media (max-width: 767px)' in html

    # 3. 檢查斷點字級與欄寬階梯
    assert 'font-size: 110%;' in html
    assert 'grid-template-columns: 350px 1fr;' in html
    assert 'font-size: 95%;' in html
    assert 'grid-template-columns: 310px 1fr;' in html
    assert 'font-size: 85%;' in html
    assert 'grid-template-columns: 280px 1fr;' in html

    # 4. 檢查低高度螢幕約束 (Height <= 720px)
    assert '@media (max-height: 720px) and (min-width: 768px)' in html
    assert 'font-size: 88%;' in html

    # 5. 檢查極窄螢幕 (< 768px) 垂直堆疊
    assert 'flex-direction: column;' in html
