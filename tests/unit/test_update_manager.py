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
