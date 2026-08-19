import pytest
import os
import tempfile
import yaml
from unittest.mock import patch
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


def test_fullscreen_modal_alarm_css_and_elements(client):
    """驗證 index.html 包含 alarm-pulse 動畫、alarm-active CSS class 及 ROI 告警相應元素與 JavaScript 邏輯。"""
    resp = client.get('/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # 1. 檢查 CSS 警示樣式
    assert '@keyframes alarm-pulse' in html
    assert '.fullscreen-modal.alarm-active' in html

    # 2. 檢查全螢幕 Modal 與 Canvas 標籤
    assert 'id="fullscreen-modal"' in html
    assert 'id="fullscreen-canvas"' in html
    assert 'id="zone-status-badge"' in html
    assert 'id="zone-trigger-mode-select"' in html
    assert 'id="zone-sensitivity-range"' in html
    assert 'updateTriggerModeUI' in html

    # 3. 檢查 JavaScript 核心幾何判定與告警繪圖邏輯
    assert 'hasAlarmInZone' in html
    assert '[ALARM]' in html
    assert '[ ROI:' in html
    assert '- INTRUSION' in html
    assert 'ZONE: ALARM TRIGGERED' in html


def test_is_point_in_polygon_logic():
    """以 Python 模擬驗證前端採用的標準 2D Ray-Casting 幾何演算法正確性。"""
    def is_point_in_polygon(point, polygon):
        if not polygon or len(polygon) < 3:
            return False
        x, y = point[0], point[1]
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i][0], polygon[i][1]
            xj, yj = polygon[j][0], polygon[j][1]
            intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
            if intersect:
                inside = not inside
            j = i
        return inside

    # 定義一個 [0.2, 0.2] 到 [0.8, 0.8] 的矩形 ROI
    poly = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]

    # 區域內部點
    assert is_point_in_polygon([0.5, 0.5], poly) is True
    assert is_point_in_polygon([0.3, 0.3], poly) is True

    # 區域外部點
    assert is_point_in_polygon([0.1, 0.5], poly) is False
    assert is_point_in_polygon([0.9, 0.9], poly) is False
    assert is_point_in_polygon([0.5, 0.0], poly) is False

    # 異常多邊形
    assert is_point_in_polygon([0.5, 0.5], []) is False
    assert is_point_in_polygon([0.5, 0.5], [[0, 0], [1, 1]]) is False
