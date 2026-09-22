"""test_delta_update_flow.py - 端到端 Delta 增量更新與原子回滾閉環測試 (Issue #85)

驗證從版本輪詢、Delta 封包優先配對、局部原子置換 (install.sh --delta)、
重啟 Exit Code 42 到 30 秒健康狀態評估與 Commit 的完整生命週期。
"""

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile
from unittest.mock import MagicMock, patch
from werkzeug.serving import make_server
import threading

import pytest
import requests

from argus.integration.app_update_client import (
    AppUpdateClient,
    DownloadInfo,
    VersionInfoDTO,
)
from argus.updates.delta_updater import compute_sha256, DeltaUpdater
from argus.updates.update_manager import UpdateManager, UpdateState, GLOBAL_UPDATE_MANAGER
from argus.web import web_ui


def create_test_delta_archive(tar_path: str, target_version: str = "1.1.0") -> str:
    """建立標準 Delta .tar.gz 增量更新包 (包含 manifest.json 與 payload/)，體積約 2.4 MB。"""
    with tempfile.TemporaryDirectory() as staging:
        payload_dir = os.path.join(staging, "payload")
        internal_dir = os.path.join(payload_dir, "_internal")
        tpl_dir = os.path.join(internal_dir, "argus", "web", "templates")
        docs_dir = os.path.join(internal_dir, "docs", "user-manual", "book")

        os.makedirs(tpl_dir, exist_ok=True)
        os.makedirs(docs_dir, exist_ok=True)

        # 1. 產生新版 argus.zip，填充適當大小使其總體積接近 2.4MB
        new_zip_path = os.path.join(internal_dir, "argus.zip")
        with zipfile.ZipFile(new_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("argus/__init__.py", f'__version__ = "{target_version}"\n')
            # 填入約 2.3MB 數據以反映 2.4MB 真實增量更新包
            zf.writestr("argus/_payload_pad.bin", os.urandom(2300000))

        # 2. 前端模板與手冊
        new_tpl_path = os.path.join(tpl_dir, "index.html")
        with open(new_tpl_path, "w", encoding="utf-8") as f:
            f.write(f"<html><body>Argus WebUI v{target_version} (Delta Applied)</body></html>")

        new_doc_path = os.path.join(docs_dir, "index.html")
        with open(new_doc_path, "w", encoding="utf-8") as f:
            f.write(f"<html><body>Manual v{target_version}</body></html>")

        # 3. version.txt
        new_ver_path = os.path.join(payload_dir, "version.txt")
        with open(new_ver_path, "w", encoding="utf-8") as f:
            f.write(f"{target_version}\n")

        # 4. manifest.json
        manifest_data = {
            "target_version": target_version,
            "min_compatible_base": "1.0.0",
            "arch": "arm64",
            "package_type": "delta",
            "code_only": False,
            "files": {
                "_internal/argus.zip": {
                    "sha256": compute_sha256(new_zip_path),
                    "size": os.path.getsize(new_zip_path),
                },
                "_internal/argus/web/templates/index.html": {
                    "sha256": compute_sha256(new_tpl_path),
                    "size": os.path.getsize(new_tpl_path),
                },
                "_internal/docs/user-manual/book/index.html": {
                    "sha256": compute_sha256(new_doc_path),
                    "size": os.path.getsize(new_doc_path),
                },
                "version.txt": {
                    "sha256": compute_sha256(new_ver_path),
                    "size": os.path.getsize(new_ver_path),
                },
            },
        }
        manifest_file = os.path.join(staging, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        os.makedirs(os.path.dirname(os.path.abspath(tar_path)), exist_ok=True)
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(manifest_file, arcname="manifest.json")
            tar.add(payload_dir, arcname="payload")

    return tar_path


def setup_mock_sandbox(sandbox_dir: str):
    """建立模擬之邊緣端完整運行環境。"""
    argus_dir = os.path.join(sandbox_dir, "argus_predictor")
    internal_dir = os.path.join(argus_dir, "_internal")
    scripts_dir = os.path.join(sandbox_dir, "scripts")
    models_dir = os.path.join(sandbox_dir, "models")
    logs_dir = os.path.join(sandbox_dir, "logs")

    os.makedirs(internal_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    # 複製專案當前之 install.sh 至測試沙盒
    src_install_sh = os.path.abspath("scripts/install.sh")
    dest_install_sh = os.path.join(scripts_dir, "install.sh")
    shutil.copy2(src_install_sh, dest_install_sh)

    # 1. 舊版業務代碼 (argus.zip)
    old_zip = os.path.join(internal_dir, "argus.zip")
    with open(old_zip, "w", encoding="utf-8") as f:
        f.write("old_business_logic_v1.0.0")

    # 2. 舊版前端 Web 模板
    old_tpl_dir = os.path.join(internal_dir, "argus", "web", "templates")
    os.makedirs(old_tpl_dir, exist_ok=True)
    with open(os.path.join(old_tpl_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write("<html>old_ui_v1.0.0</html>")

    # 3. 舊版版本標記
    with open(os.path.join(argus_dir, "version.txt"), "w", encoding="utf-8") as f:
        f.write("1.0.0\n")

    # 4. 龐大重型動態函式庫 (PyTorch、OpenCV) - 必須嚴格保留不動！
    torch_dir = os.path.join(internal_dir, "torch")
    os.makedirs(torch_dir, exist_ok=True)
    torch_lib = os.path.join(torch_dir, "libtorch.so")
    with open(torch_lib, "w", encoding="utf-8") as f:
        f.write("heavy_torch_binary_content_bytes")

    cv2_dir = os.path.join(internal_dir, "cv2")
    os.makedirs(cv2_dir, exist_ok=True)
    cv2_lib = os.path.join(cv2_dir, "cv2.so")
    with open(cv2_lib, "w", encoding="utf-8") as f:
        f.write("heavy_cv2_binary_content_bytes")

    # 5. 本機客製配置檔 (config.yaml) 與模型、日誌 - 必須嚴格保留！
    cfg_path = os.path.join(sandbox_dir, "config.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("confidence_threshold: 0.85\nzone: factory_cleanroom\n")

    return {
        "sandbox_dir": sandbox_dir,
        "argus_dir": argus_dir,
        "internal_dir": internal_dir,
        "old_zip": old_zip,
        "torch_lib": torch_lib,
        "cv2_lib": cv2_lib,
        "cfg_path": cfg_path,
        "install_sh": dest_install_sh,
    }


def test_app_update_client_prefers_delta_package_and_fallback():
    """驗證 Acceptance Criteria 1 & 2:
    1. 優先選取 Delta 封包 (argus_delta-*.tar.gz)，下載總量約 2.4MB。
    2. 若伺服器無增量包，自動無縫安全降級 (Fallback) 至全量包。
    """
    mock_session = MagicMock(spec=requests.Session)

    # 情境 1: 伺服器同時提供全量與 Delta 增量包
    mock_resp_delta = MagicMock()
    mock_resp_delta.status_code = 200
    mock_resp_delta.json.return_value = {
        "owner": "cminl",
        "filesInfo": [
            {
                "fileName": "safety-predictor-nano-v1.1.0-arm64.tar.gz",
                "filePath": "dist/v1.1.0/safety-predictor-nano-v1.1.0-arm64.tar.gz",
                "size": 268435456,  # 256MB 全量包
            },
            {
                "fileName": "argus_delta-v1.1.0-arm64.tar.gz",
                "filePath": "dist/v1.1.0/argus_delta-v1.1.0-arm64.tar.gz",
                "size": 2516582,  # 2.4MB 增量補丁
            },
        ],
    }
    mock_session.request.return_value = mock_resp_delta

    client = AppUpdateClient(session=mock_session)
    info = client.get_download_info("1.1.0")
    assert info.is_delta is True
    assert info.size == 2516582
    assert "delta" in info.file_path.lower()

    # 情境 2: 伺服器僅提供全量包，自動安全降級使用全量包
    mock_resp_full = MagicMock()
    mock_resp_full.status_code = 200
    mock_resp_full.json.return_value = {
        "owner": "cminl",
        "filesInfo": [
            {
                "fileName": "safety-predictor-nano-v1.1.0-arm64.tar.gz",
                "filePath": "dist/v1.1.0/safety-predictor-nano-v1.1.0-arm64.tar.gz",
                "size": 268435456,
            }
        ],
    }
    mock_session.request.return_value = mock_resp_full

    info_fallback = client.get_download_info("1.1.0")
    assert info_fallback.is_delta is False
    assert info_fallback.size == 268435456
    assert "arm64" in info_fallback.file_path.lower()


def test_delta_update_full_lifecycle_e2e(tmp_path):
    """驗證 Acceptance Criteria 1~5:
    端到端驗證版本檢查、Delta 優先下載 (~2.4MB)、Web UI / SSE 狀態展示、
    局部原子替換 (install.sh --delta)、Exit Code 42 觸發與 30 秒健康狀態確立 Commit。
    """
    sandbox_dir = str(tmp_path / "sandbox")
    env = setup_mock_sandbox(sandbox_dir)

    # 1. 建立真實 2.4MB Delta 封包
    server_tar_path = str(tmp_path / "server_files" / "argus_delta-v1.1.0-arm64.tar.gz")
    create_test_delta_archive(server_tar_path, target_version="1.1.0")
    delta_size = os.path.getsize(server_tar_path)
    assert 2000000 < delta_size < 3500000  # 約 2.4 MB

    # 2. 建立 Mock API Client
    mock_session = MagicMock(spec=requests.Session)

    # 模擬 /Version 端點
    mock_ver_resp = MagicMock()
    mock_ver_resp.status_code = 200
    mock_ver_resp.json.return_value = [
        {
            "version": "1.1.0",
            "released": True,
            "autoUpdate": True,
            "locked": False,
            "releaseDate": "2026-09-22 10:00:00",
            "releaseNotes": "◈ 輕量 Delta 增量更新發布 (v1.1.0)",
        }
    ]

    # 模擬 /DownloadInfo 端點
    mock_dl_resp = MagicMock()
    mock_dl_resp.status_code = 200
    mock_dl_resp.json.return_value = {
        "owner": "cminl",
        "filesInfo": [
            {
                "fileName": "argus_delta-v1.1.0-arm64.tar.gz",
                "filePath": "dist/v1.1.0/argus_delta-v1.1.0-arm64.tar.gz",
                "size": delta_size,
            },
            {
                "fileName": "safety-predictor-nano-v1.1.0-arm64.tar.gz",
                "filePath": "dist/v1.1.0/safety-predictor-nano-v1.1.0-arm64.tar.gz",
                "size": 268435456,
            }
        ]
    }

    def mock_request(method, url, **kwargs):
        if "Version" in url:
            return mock_ver_resp
        if "DownloadInfo" in url:
            return mock_dl_resp
        return mock_dl_resp

    mock_session.request.side_effect = mock_request

    # 模擬串流下載真實 Delta 封包檔案
    def mock_get(url, **kwargs):
        mock_file_resp = MagicMock()
        mock_file_resp.status_code = 200
        mock_file_resp.headers = {"Content-Length": str(delta_size)}
        with open(server_tar_path, "rb") as f:
            content_bytes = f.read()
        mock_file_resp.iter_content = lambda chunk_size=1048576: [content_bytes]
        mock_file_resp.__enter__.return_value = mock_file_resp
        return mock_file_resp

    mock_session.get.side_effect = mock_get

    mock_client = AppUpdateClient(
        app_id="safety-predictor-nano",
        base_urls=["http://test-gateway.cminl.oa/AppManagementApi"],
        session=mock_session,
    )

    # 3. 初始化 UpdateManager
    mgr = UpdateManager(
        current_version="1.0.0",
        config={
            "base_dir": sandbox_dir,
            "staging_dir": os.path.join(sandbox_dir, "updates", "staging"),
        },
        client=mock_client,
    )

    # 註冊 SSE 訂閱通道
    sse_queue = mgr.subscribe()

    # 4. 階段一：版本檢查 (CHECKING -> AVAILABLE)
    check_res = mgr.check_for_updates()
    assert check_res["status"] == "ok"
    time.sleep(0.5)

    status = mgr.get_status()
    assert status["state"] == UpdateState.AVAILABLE
    assert status["target_version"] == "1.1.0"
    assert status["is_delta"] is True
    assert status["package_type"] == "delta"
    assert status["total_bytes"] == delta_size

    # 5. 階段二：驗證 Web UI API 與 SSE 即時推播通道
    # 同步全域更新管理器供 Web UI 測試
    with patch("argus.web.web_ui.GLOBAL_UPDATE_MANAGER", mgr):
        web_ui.app.config["TESTING"] = True
        with web_ui.app.test_client() as test_client:
            # 5.1 /api/update/status 必須帶有 Delta 與真實大小
            api_status = test_client.get("/api/update/status").get_json()
            assert api_status["is_delta"] is True
            assert api_status["package_type"] == "delta"
            assert api_status["total_bytes"] == delta_size

            # 5.2 /api/update/stream (SSE) 推播之資料
            sse_resp = test_client.get("/api/update/stream")
            sse_chunk = next(sse_resp.response).decode("utf-8")
            assert "data:" in sse_chunk
            sse_data = json.loads(sse_chunk.replace("data:", "").strip())
            assert sse_data["is_delta"] is True
            assert sse_data["package_type"] == "delta"

            # 5.3 Web UI 主頁面包含 Delta 徽章與標籤元素
            ui_html = test_client.get("/").get_data(as_text=True)
            assert 'id="up-delta-badge"' in ui_html
            assert 'id="up-package-type"' in ui_html
            assert 'id="up-package-size"' in ui_html

    # 6. 階段三：觸發下載並執行局部原子置換 (install.sh --delta)
    down_res = mgr.start_download()
    assert down_res["status"] == "ok"
    time.sleep(1.5)  # 等待下載、解壓與 install.sh --delta 執行

    status_ready = mgr.get_status()
    assert status_ready["state"] == UpdateState.READY_TO_INSTALL
    assert mgr.is_delta is True

    # 驗證局部原子置換成效：
    # (a) 業務代碼已更新 (argus.zip 內包含 v1.1.0)
    with zipfile.ZipFile(env["old_zip"], "r") as zf:
        ver_py = zf.read("argus/__init__.py").decode("utf-8")
        assert '1.1.0' in ver_py

    # (b) 存在 .patch_bak/ 局部備份
    patch_bak = os.path.join(env["internal_dir"], ".patch_bak")
    assert os.path.isdir(patch_bak)
    assert os.path.isfile(os.path.join(patch_bak, "argus.zip"))

    # (c) 重型動態函式庫 (PyTorch、OpenCV) 嚴格未受波及
    with open(env["torch_lib"], "r", encoding="utf-8") as f:
        assert f.read() == "heavy_torch_binary_content_bytes"
    with open(env["cv2_lib"], "r", encoding="utf-8") as f:
        assert f.read() == "heavy_cv2_binary_content_bytes"

    # (d) 使用者本機配置檔 (config.yaml) 嚴格未受覆蓋
    with open(env["cfg_path"], "r", encoding="utf-8") as f:
        assert "factory_cleanroom" in f.read()

    # 7. 階段四：觸發重啟並驗證 Exit Code 42
    exit_mock = MagicMock()
    mgr._exit_func = exit_mock

    restart_res = mgr.trigger_restart(exit_on_restart=True)
    assert restart_res["status"] == "ok"
    assert mgr.state == UpdateState.RESTARTING

    time.sleep(1.5)
    exit_mock.assert_called_once_with(42)

    # 驗證寫入 .update_in_progress
    progress_file = os.path.join(sandbox_dir, ".update_in_progress")
    assert os.path.isfile(progress_file)
    with open(progress_file, "r", encoding="utf-8") as f:
        prog_data = json.load(f)
    assert prog_data["target_version"] == "1.1.0"
    assert prog_data["is_delta"] is True

    # 8. 階段五：新版進程喚起與 30 秒健康檢查確立 (Commit)
    # 模擬服務重啟：新 UpdateManager 偵測到 .update_in_progress 進入 HEALTHCHECK
    new_mgr = UpdateManager(
        current_version="1.0.0",
        config={
            "base_dir": sandbox_dir,
            "staging_dir": os.path.join(sandbox_dir, "updates", "staging"),
        },
    )
    assert new_mgr.state == UpdateState.HEALTHCHECK
    assert new_mgr.target_version == "1.1.0"

    # 模擬 30 秒窗口內 /api/health 探針探測
    with patch("argus.web.web_ui.GLOBAL_UPDATE_MANAGER", new_mgr):
        with web_ui.app.test_client() as probe_client:
            probe_resp = probe_client.get("/api/health")
            assert probe_resp.status_code == 200
            health_json = probe_resp.get_json()
            assert health_json["status"] == "healthy"

    # 驗證升級確立：.update_in_progress 已移除，狀態確立為 COMMITTED，版本變更為 1.1.0
    assert not os.path.isfile(progress_file)
    assert new_mgr.state == UpdateState.COMMITTED
    assert new_mgr.current_version == "1.1.0"

    # 驗證日誌記錄 [COMMITTED]
    update_log_path = os.path.join(sandbox_dir, "logs", "update.log")
    if os.path.isfile(update_log_path):

        with open(update_log_path, "r", encoding="utf-8") as f:
            log_content = f.read()
            assert "[COMMITTED]" in log_content
            assert "1.1.0" in log_content

    mgr.unsubscribe(sse_queue)



def test_delta_update_healthcheck_failure_auto_rollback(tmp_path):
    """驗證升級異常健康檢查超時後觸發 Delta 局部秒級回滾與告警標記。"""
    sandbox_dir = str(tmp_path / "sandbox")
    env = setup_mock_sandbox(sandbox_dir)

    server_tar_path = str(tmp_path / "server_files" / "argus_delta-v1.1.0-arm64.tar.gz")
    create_test_delta_archive(server_tar_path, target_version="1.1.0")

    # 套用 Delta 更新
    updater = DeltaUpdater(base_dir=sandbox_dir)
    updater.apply_delta(server_tar_path, current_base_version="1.0.0")

    # 驗證升級後有備份
    assert updater.has_patch_backup()

    mgr = UpdateManager(
        current_version="1.0.0",
        config={"base_dir": sandbox_dir},
    )
    # 模擬健康檢查失敗觸發回滾
    res = mgr.trigger_mock_rollback()
    assert res["status"] == "ok"
    assert mgr.state == UpdateState.ROLLBACK
    assert mgr.rollback_occurred is True

    # 驗證局部秒級回滾成功：argus.zip 還原為舊版
    with open(env["old_zip"], "r", encoding="utf-8") as f:
        assert f.read() == "old_business_logic_v1.0.0"

    # 驗證產生 .rollback_alert
    alert_path = os.path.join(sandbox_dir, ".rollback_alert")
    assert os.path.isfile(alert_path)

    # 驗證 /api/health 回傳 rollback_occurred 為 True
    with patch("argus.web.web_ui.GLOBAL_UPDATE_MANAGER", mgr):
        with web_ui.app.test_client() as probe_client:
            probe_resp = probe_client.get("/api/health")
            assert probe_resp.status_code == 200
            assert probe_resp.get_json()["rollback_occurred"] is True


class ServerThread(threading.Thread):
    def __init__(self, app, port=8197):
        super().__init__()
        self.daemon = True
        self.port = port
        self.server = make_server('127.0.0.1', port, app, threaded=True)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def test_delta_update_modal_browser_e2e():
    """使用 Playwright 端到端驗證 Web UI 更新彈窗呈現 Delta 標籤與 2.4 MB 大小。"""
    from playwright.sync_api import sync_playwright

    # 設定 UpdateManager 為 Delta 可更新狀態
    GLOBAL_UPDATE_MANAGER.set_state(
        UpdateState.AVAILABLE,
        target_version="1.1.0",
        is_delta=True,
        total=2516582,
        release_notes="◈ 輕量 Delta 增量更新發布 (v1.1.0)",
    )

    port = 8197
    server = ServerThread(web_ui.app, port=port)
    server.start()
    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/")

            # 1. 驗證導覽列更新徽章
            badge = page.locator("#update-badge-btn")
            badge.wait_for(state="visible", timeout=5000)
            badge_text = page.locator("#update-badge-text").inner_text()
            assert "1.1.0" in badge_text
            assert "2.4 MB" in badge_text or "增量" in badge_text

            # 2. 點擊徽章開啟更新彈窗
            badge.click()
            overlay = page.locator("#update-modal-overlay")
            overlay.wait_for(state="visible", timeout=3000)

            # 3. 驗證更新彈窗內容
            target_ver = page.locator("#up-target-version").inner_text()
            assert "1.1.0" in target_ver

            delta_badge = page.locator("#up-delta-badge")
            assert delta_badge.is_visible()
            assert "Delta" in delta_badge.inner_text() or "增量" in delta_badge.inner_text()

            pkg_type = page.locator("#up-package-type").inner_text()
            assert "增量更新" in pkg_type

            pkg_size = page.locator("#up-package-size").inner_text()
            assert "2.4 MB" in pkg_size

            # 4. 關閉彈窗
            close_btn = page.locator(".up-close-btn")
            close_btn.click()
            time.sleep(0.3)
            assert not overlay.is_visible()

            browser.close()
    finally:
        server.shutdown()


