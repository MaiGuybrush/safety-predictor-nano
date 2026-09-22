import queue
import time
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
    mgr = UpdateManager(current_version="1.0.0")
    res = mgr.check_for_updates(mock_available=True)
    assert res["status"] == "ok"
    # 等待背景檢查執行完畢
    time.sleep(1.0)
    status = mgr.get_status()
    assert status["state"] == UpdateState.AVAILABLE
    assert status["is_delta"] is True
    assert status["package_type"] == "delta"
    assert status["target_version"] == "1.1.0"
    assert status["total_bytes"] == 2516582


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

