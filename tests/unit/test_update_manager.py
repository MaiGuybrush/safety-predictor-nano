import queue
import time
from unittest.mock import MagicMock, patch
from argus.integration.app_update_client import VersionInfoDTO, DownloadInfo
from argus.updates.update_manager import UpdateManager, UpdateState


def test_update_manager_initial_state():
    mgr = UpdateManager(current_version="1.0.0")
    status = mgr.get_status()
    assert status["state"] == UpdateState.IDLE
    assert status["current_version"] == "1.0.0"
    assert status["target_version"] is None
    assert status["progress"] == 0.0


def test_update_manager_set_state_and_sse_subscribe():
    mgr = UpdateManager(current_version="1.0.0")
    q = mgr.subscribe()

    # 第一筆應為初始狀態
    initial = q.get_nowait()
    assert initial["state"] == UpdateState.IDLE

    # 更新狀態
    mgr.set_state(
        UpdateState.AVAILABLE,
        target_version="1.2.0",
        message="發現更新",
        progress=0.0
    )

    item = q.get_nowait()
    assert item["state"] == UpdateState.AVAILABLE
    assert item["target_version"] == "1.2.0"

    mgr.unsubscribe(q)


def test_update_manager_mock_download():
    mgr = UpdateManager(current_version="1.0.0")
    mgr.set_state(UpdateState.AVAILABLE, target_version="1.1.0", total=1024 * 1024 * 10)

    res = mgr.start_download()
    assert res["status"] == "ok"
    assert mgr.state in (UpdateState.DOWNLOADING, UpdateState.STAGING, UpdateState.READY_TO_INSTALL)


def test_update_manager_rollback():
    mgr = UpdateManager(current_version="1.0.0")
    res = mgr.trigger_mock_rollback()
    assert res["status"] == "ok"
    assert mgr.state == UpdateState.ROLLBACK
    assert mgr.rollback_occurred is True


def test_update_manager_delta_support(tmp_path):
    import json
    staging = tmp_path / "staging"
    staging.mkdir()
    manifest = staging / "manifest.json"
    manifest.write_text(json.dumps({"package_type": "delta", "target_version": "1.1.0"}), encoding="utf-8")

    mgr = UpdateManager(current_version="1.0.0", config={"staging_dir": str(staging)})
    assert mgr.is_delta_package() is True
    assert mgr.is_delta_package(str(tmp_path / "non_existent")) is False


def test_update_manager_check_updates_delta_mock():
    mock_client = MagicMock()
    mock_candidate = VersionInfoDTO(
        version="1.1.0",
        released=True,
        auto_update=True,
        locked=False,
        release_date="2026-09-21 12:00:00",
        release_notes="◈ 系統安全性與效能維護更新 (v1.1.0)",
    )
    mock_dl = DownloadInfo(
        app_id="safety-predictor-nano",
        version="1.1.0",
        owner="release",
        file_path="/packages/argus_delta-v1.1.0-arm64.tar.gz",
        size=2516582,
        sha256="abcdef123456",
        is_delta=True,
    )
    mock_client.check_latest_candidate.return_value = mock_candidate
    mock_client.get_download_info.return_value = mock_dl

    mgr = UpdateManager(current_version="1.0.0", client=mock_client)
    res = mgr.check_for_updates()
    assert res["status"] == "ok"
    # 等待背景檢查執行完畢
    time.sleep(0.5)
    status = mgr.get_status()
    assert status["state"] == UpdateState.AVAILABLE
    assert status["is_delta"] is True
    assert status["package_type"] == "delta"
    assert status["target_version"] == "1.1.0"
    assert status["total_bytes"] == 2516582


def test_update_manager_check_updates_no_update_found():
    mock_client = MagicMock()
    mock_client.check_latest_candidate.return_value = None

    mgr = UpdateManager(current_version="1.0.0", client=mock_client)
    res = mgr.check_for_updates()
    assert res["status"] == "ok"
    time.sleep(0.5)
    status = mgr.get_status()
    assert status["state"] == UpdateState.IDLE
    assert "最新版本" in status["message"]


def test_update_manager_check_updates_client_error():
    mock_client = MagicMock()
    mock_client.check_latest_candidate.side_effect = RuntimeError("連線逾時")

    mgr = UpdateManager(current_version="1.0.0", client=mock_client)
    res = mgr.check_for_updates()
    assert res["status"] == "ok"
    time.sleep(0.5)
    status = mgr.get_status()
    assert status["state"] == UpdateState.IDLE
    assert "未成功" in status["message"]


def test_update_manager_disk_precheck_delta(tmp_path):
    from unittest.mock import MagicMock, patch
    staging = tmp_path / "staging"
    staging.mkdir()

    mgr = UpdateManager(current_version="1.0.0", config={"staging_dir": str(staging)})
    mgr.set_state(UpdateState.AVAILABLE, target_version="1.1.0", is_delta=True, total=2516582)

    # 模擬 50MB 磁碟空間 (Delta 需 20MB，足夠；若全量需 650MB，不足)
    usage_mock = MagicMock()
    usage_mock.free = 50 * 1024 * 1024

    with patch("shutil.disk_usage", return_value=usage_mock):
        res = mgr.start_download()
        assert res["status"] == "ok"
        assert mgr.state in (UpdateState.DOWNLOADING, UpdateState.STAGING, UpdateState.READY_TO_INSTALL)


def test_update_manager_trigger_restart_exit_42(tmp_path):
    from unittest.mock import MagicMock
    mgr = UpdateManager(current_version="1.0.0", config={"base_dir": str(tmp_path)})
    mgr.set_state(UpdateState.READY_TO_INSTALL, target_version="1.1.0", is_delta=True)

    exit_mock = MagicMock()
    mgr._exit_func = exit_mock

    res = mgr.trigger_restart(exit_on_restart=True)
    assert res["status"] == "ok"
    assert mgr.state == UpdateState.RESTARTING

    # 等待背景執行緒觸發 _exit_func(42)
    time.sleep(1.5)
    exit_mock.assert_called_once_with(42)

    # 檢查 .update_in_progress 已寫入
    progress_file = tmp_path / ".update_in_progress"
    assert progress_file.exists()


def test_update_manager_commit_update(tmp_path):
    mgr = UpdateManager(current_version="1.0.0", config={"base_dir": str(tmp_path)})
    progress_file = tmp_path / ".update_in_progress"
    progress_file.write_text('{"target_version": "1.1.0", "is_delta": true}', encoding="utf-8")

    mgr.target_version = "1.1.0"
    mgr.state = UpdateState.HEALTHCHECK

    res = mgr.commit_update()
    assert res["status"] == "ok"
    assert mgr.state == UpdateState.COMMITTED
    assert mgr.current_version == "1.1.0"
    assert not progress_file.exists()


def test_update_manager_configure_and_check_on_startup():
    from unittest.mock import MagicMock, patch
    mgr = UpdateManager(current_version="1.0.0")

    mock_candidate = MagicMock()
    mock_candidate.version = "1.2.0"
    mock_candidate.released = True
    mock_candidate.auto_update = True
    mock_candidate.locked = False
    mock_candidate.release_date = "2026-09-22"
    mock_candidate.release_notes = "新功能"

    mock_dl_info = MagicMock()
    mock_dl_info.is_delta = True
    mock_dl_info.size = 2000000

    with patch("argus.updates.update_manager.AppUpdateClient") as MockClientCls:
        mock_instance = MockClientCls.return_value
        mock_instance.api_key = "ums_key_123"
        mock_instance.api_key_missing = False
        mock_instance.check_latest_candidate.return_value = mock_candidate
        mock_instance.get_download_info.return_value = mock_dl_info

        cfg = {
            "enabled": True,
            "app_id": "test-app",
            "check_interval_seconds": 3600,
            "check_on_startup": True,
            "staging_dir": "custom/staging",
        }
        mgr.configure(cfg, ums_api_key="ums_key_123")
        assert mgr.auto_update_enabled is True
        assert mgr.staging_dir == "custom/staging"
        assert mgr.client is not None
        assert mgr.api_key_missing is False

        # 等待背景 check_on_startup 完成
        time.sleep(0.5)
        status = mgr.get_status()
        assert status["state"] in (UpdateState.CHECKING, UpdateState.AVAILABLE)
        assert status["target_version"] == "1.2.0"
        mgr.stop_polling()


def test_update_manager_polling_start_and_stop():
    mgr = UpdateManager(current_version="1.0.0")
    assert mgr._poll_thread is None

    mgr.start_polling(interval=300)
    assert mgr._poll_thread is not None
    assert mgr._poll_thread.is_alive()

    mgr.stop_polling()
    assert mgr._stop_polling.is_set()


def test_config_manager_auto_update_schema(tmp_path):
    from argus.core.config_manager import ConfigManager
    import yaml

    cfg_data = {
        "ums_api_key": "root_ums_key",
        "ums_fab": "T1",
        "auto_update": {
            "enabled": True,
            "temp_dir": "temp/updates",
            "check_on_startup": True,
            "check_interval_seconds": 600,
        }
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")

    mgr = ConfigManager(str(cfg_file))
    auto_cfg = mgr.get_auto_update_config()

    assert auto_cfg["enabled"] is True
    assert auto_cfg["staging_dir"] == "temp/updates"
    assert auto_cfg["check_on_startup"] is True
    assert auto_cfg["check_interval_seconds"] == 600
    assert auto_cfg["ums_api_key"] == "root_ums_key"
    assert auto_cfg["ums_fab"] == "t1"


def test_update_manager_skips_startup_and_polling_when_api_key_missing(caplog):
    import logging
    cfg = {
        "enabled": True,
        "app_id": "test-app",
        "check_interval_seconds": 3600,
        "check_on_startup": True,
        "api_key": "",
    }
    with patch("argus.updates.update_manager.AppUpdateClient") as MockClientCls:
        mock_instance = MockClientCls.return_value
        mock_instance.api_key = ""
        mock_instance.api_key_missing = True

        with caplog.at_level(logging.WARNING):
            mgr = UpdateManager(current_version="1.0.0", config=cfg)
            assert mgr.api_key_missing is True

            mgr.configure(cfg)
            assert mgr.api_key_missing is True
            # 開機檢查與定時輪詢應跳過
            assert mgr._poll_thread is None
            assert mock_instance.check_latest_candidate.call_count == 0

            # 手動呼叫 start_polling 也應直接跳過
            mgr.start_polling(interval=300)
            assert mgr._poll_thread is None

            # 手動呼叫 check_for_updates 應直接返回 error
            res = mgr.check_for_updates()
            assert res["status"] == "error"
            assert "未設定 API KEY，無法進行更新檢查，請至設定頁配置 auto_update.api_key" in res["message"]
            assert mock_instance.check_latest_candidate.call_count == 0


