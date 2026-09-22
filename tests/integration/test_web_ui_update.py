import json
import pytest
from argus.web.web_ui import app
from argus.updates.update_manager import GLOBAL_UPDATE_MANAGER, UpdateState


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["web_ui"] is True
    assert data["inference_ready"] is True


def test_api_update_status(client):
    GLOBAL_UPDATE_MANAGER.set_state(UpdateState.IDLE, message="就緒", is_delta=False)
    response = client.get("/api/update/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["state"] == UpdateState.IDLE
    assert "current_version" in data
    assert "progress" in data
    assert "is_delta" in data
    assert data["package_type"] == "full"

    GLOBAL_UPDATE_MANAGER.set_state(UpdateState.AVAILABLE, is_delta=True, total=2516582)
    res2 = client.get("/api/update/status")
    data2 = res2.get_json()
    assert data2["is_delta"] is True
    assert data2["package_type"] == "delta"
    assert data2["total_bytes"] == 2516582


def test_api_update_check_and_download_flow(client):
    # 1. 觸發檢查
    resp_check = client.post("/api/update/check", json={"mock_available": True})
    assert resp_check.status_code == 200
    check_data = resp_check.get_json()
    assert check_data["status"] == "ok"

    # 手動設定為 AVAILABLE (Delta 增量更新) 以便直接測試下載
    GLOBAL_UPDATE_MANAGER.set_state(
        UpdateState.AVAILABLE,
        target_version="1.1.0",
        message="發現新版本 (Delta Patch)",
        total=2516582,
        is_delta=True,
    )

    # 2. 觸發下載
    resp_down = client.post("/api/update/download")
    assert resp_down.status_code == 200
    down_data = resp_down.get_json()
    assert down_data["status"] == "ok"
    assert GLOBAL_UPDATE_MANAGER.state in (UpdateState.DOWNLOADING, UpdateState.STAGING, UpdateState.READY_TO_INSTALL)
    assert GLOBAL_UPDATE_MANAGER.is_delta is True


def test_api_update_restart(client):
    GLOBAL_UPDATE_MANAGER.set_state(UpdateState.READY_TO_INSTALL, target_version="1.1.0", is_delta=True)
    resp_restart = client.post("/api/update/restart")
    assert resp_restart.status_code == 200
    restart_data = resp_restart.get_json()
    assert restart_data["status"] == "ok"
    assert GLOBAL_UPDATE_MANAGER.state in (UpdateState.RESTARTING, UpdateState.HEALTHCHECK, UpdateState.COMMITTED, UpdateState.IDLE)


def test_api_update_stream_sse(client):
    GLOBAL_UPDATE_MANAGER.set_state(UpdateState.AVAILABLE, message="SSE Delta 測試", is_delta=True, total=2516582)
    response = client.get("/api/update/stream")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["Content-Type"]
    chunk = next(response.response)
    text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
    assert "data:" in text
    payload = json.loads(text.replace("data:", "").strip())
    assert "state" in payload
    assert payload["is_delta"] is True
    assert payload["package_type"] == "delta"
    assert payload["total_bytes"] == 2516582


def test_web_ui_index_contains_update_modal(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="update-modal-overlay"' in html
    assert 'id="update-restart-overlay"' in html
    assert 'id="update-badge-btn"' in html
    assert 'id="app-current-version-tag"' in html
    assert 'id="up-delta-badge"' in html
    assert 'id="up-package-type"' in html
    assert 'id="up-package-size"' in html
    assert 'openUpdateModal()' in html


