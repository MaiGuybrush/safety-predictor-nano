import os
import tempfile
import threading
import time
import yaml
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

import web_ui

class ServerThread(threading.Thread):
    def __init__(self, app, port=8189):
        threading.Thread.__init__(self)
        self.port = port
        self.server = make_server('127.0.0.1', port, app, threaded=True)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def test_floating_action_bar_dirty_state_and_ajax_save_e2e():
    temp_dir = tempfile.TemporaryDirectory()
    config_path = os.path.join(temp_dir.name, "config.yaml")
    initial_config = {
        "mode": "rtsp",
        "fps_limit": 2,
        "cpu_cores": 4,
        "conf_threshold": 0.25,
        "model_path": "best.onnx",
        "model_format": "auto",
        "streams": [
            {"url": "rtsp://127.0.0.1:8554/stream1", "label": "大門入口", "camera_id": "cam-01"},
            {"url": "rtsp://127.0.0.1:8554/stream2", "label": "後門側門", "camera_id": "cam-02"}
        ]
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(initial_config, f, allow_unicode=True)

    old_config_file = web_ui.CONFIG_FILE
    web_ui.CONFIG_FILE = config_path

    server = ServerThread(web_ui.app, port=8199)
    server.start()
    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
            page.on("pageerror", lambda err: print(f"[Browser Error] {err}"))
            page.goto("http://127.0.0.1:8199/")

            # 1. Initial state: Floating Action Bar not visible, no '*' badge
            fab = page.locator("#floating-action-bar")
            assert not fab.evaluate("el => el.classList.contains('visible')")
            assert "*" not in page.locator("#master-stream-name-0").inner_text()
            assert "*" not in page.locator("#master-stream-name-1").inner_text()

            # 2. Global param edit -> FAB visible
            fps_input = page.locator("input[name='fps_limit']")
            fps_input.fill("5")
            page.wait_for_timeout(200)
            assert fab.evaluate("el => el.classList.contains('visible')")

            # 3. Stream detail edit -> '*' on stream 0
            label_input = page.locator("#detail-input-label")
            label_input.fill("大門正門(修改中)")
            page.wait_for_timeout(200)
            assert "*" in page.locator("#master-stream-name-0").inner_text()
            assert "*" not in page.locator("#master-stream-name-1").inner_text()

            # 4. Switch to stream 1 and edit
            page.locator("#master-stream-list .master-stream-item").nth(1).click()
            page.wait_for_timeout(200)
            camid_input = page.locator("#detail-input-camid")
            camid_input.fill("cam-02-custom")
            page.wait_for_timeout(200)
            assert "*" in page.locator("#master-stream-name-0").inner_text()
            assert "*" in page.locator("#master-stream-name-1").inner_text()

            # 5. Click discard changes -> all reverts, FAB hides
            page.locator("#fab-discard-btn").click()
            page.wait_for_timeout(400)
            assert not fab.evaluate("el => el.classList.contains('visible')")
            assert "*" not in page.locator("#master-stream-name-0").inner_text()
            assert "*" not in page.locator("#master-stream-name-1").inner_text()
            assert fps_input.input_value() == "2"

            # 6. Re-edit and save via AJAX
            fps_input.fill("8")
            page.locator("#master-stream-list .master-stream-item").nth(0).click()
            page.wait_for_timeout(200)
            label_input = page.locator("#detail-input-label")
            label_input.fill("大門新命名")
            page.wait_for_timeout(200)
            assert fab.evaluate("el => el.classList.contains('visible')")

            # Click save
            page.locator("#fab-save-btn").click()
            page.wait_for_timeout(600)

            # Toast should appear with success message
            toast = page.locator(".hud-toast.success")
            assert toast.is_visible()
            assert "設定已成功儲存並生效" in toast.inner_text()

            # FAB should now be hidden and '*' cleared
            assert not fab.evaluate("el => el.classList.contains('visible')")
            assert "*" not in page.locator("#master-stream-name-0").inner_text()

            # Verify config.yaml was updated on disk
            with open(config_path, "r", encoding="utf-8") as f:
                saved = yaml.safe_load(f)
            assert saved["fps_limit"] == 8
            assert saved["streams"][0]["label"] == "大門新命名"

            browser.close()
    finally:
        server.shutdown()
        server.join()
        web_ui.CONFIG_FILE = old_config_file
        temp_dir.cleanup()


def test_initial_page_load_with_stream_ums_model_does_not_trigger_dirty():
    """驗證當 config.yaml 包含 stream 級別之 ums_model 時，初始載入不會誤判為 dirty。"""
    temp_dir = tempfile.TemporaryDirectory()
    config_path = os.path.join(temp_dir.name, "config.yaml")
    initial_config = {
        "mode": "rtsp",
        "fps_limit": 2,
        "cpu_cores": 4,
        "conf_threshold": 0.15,
        "model_path": r"models\local\stocker",
        "model_format": "auto",
        "streams": [
            {
                "url": "rtsp://127.0.0.1:8554/camera_wallclock",
                "label": "Stocker02",
                "camera_id": "",
                "auto_camera_id": "",
                "model": r"models\yolo8n\v4\best.onnx",
                "ums_model": {
                    "name": "yolo8n",
                    "version": "latest"
                }
            }
        ]
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(initial_config, f, allow_unicode=True)

    old_config_file = web_ui.CONFIG_FILE
    web_ui.CONFIG_FILE = config_path

    server = ServerThread(web_ui.app, port=8198)
    server.start()
    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://127.0.0.1:8198/")

            # Wait for any asynchronous UMS loading to complete
            page.wait_for_timeout(1000)

            # Floating Action Bar MUST NOT be visible on initial load
            fab = page.locator("#floating-action-bar")
            assert not fab.evaluate("el => el.classList.contains('visible')")

            # Stream #0 MUST NOT have '*' dirty badge on initial load
            assert "*" not in page.locator("#master-stream-name-0").inner_text()

            browser.close()
    finally:
        server.shutdown()
        server.join()
        web_ui.CONFIG_FILE = old_config_file
        temp_dir.cleanup()

