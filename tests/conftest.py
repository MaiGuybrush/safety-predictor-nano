"""tests/conftest.py - Pytest 全域測試守護與資源清理機制

提供 session 與 function 級別之 teardown hook 與守護機制：
1. 自動清理殘留的 StreamHandler, StatePoller, EventWriter, Heartbeat 等背景執行緒
2. 恢復 web_ui, event_producer 等全域狀態
3. 非守護 (non-daemon) 執行緒安全防禦，防止行程退出時在 threading._shutdown() 發生 0% CPU 懸掛
4. Session 完成時的守護退出看門狗 (Watchdog)
"""

import os
import sys
import time
import threading
import gc
import pytest

# Ensure repository root is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@pytest.fixture(autouse=True)
def resource_teardown_guard():
    """Function 級別資源清理守護：
    在每個測試執行前後監控執行緒與連線資源，並在測試完成後主動釋放殘留資源。
    """
    initial_threads = set(threading.enumerate())
    
    yield
    
    # 1. 重置 web_ui 活躍連線計數與快照狀態
    try:
        from argus.web import web_ui

        if hasattr(web_ui, "_clients_lock"):
            with web_ui._clients_lock:
                web_ui.ACTIVE_VIDEO_CLIENTS = 0
    except ImportError:
        pass

    # 2. 清理 event_producer 狀態
    try:
        from argus.events import event_producer

        if hasattr(event_producer, "_state"):
            event_producer._state.clear()
    except ImportError:
        pass

    # 3. 停止全域 StatePoller (若有被啟動)
    try:
        from argus.integration.state_poller import GLOBAL_STATE_POLLER
        if GLOBAL_STATE_POLLER and GLOBAL_STATE_POLLER.is_alive():
            GLOBAL_STATE_POLLER.stop()
    except (ImportError, Exception):
        pass

    # 4. 停止全域 UpdateManager 背景輪詢 (若有被啟動)
    try:
        from argus.updates.update_manager import GLOBAL_UPDATE_MANAGER
        if GLOBAL_UPDATE_MANAGER:
            GLOBAL_UPDATE_MANAGER.stop_polling()
    except (ImportError, Exception):
        pass

    # 4. 清理測試殘留的更新標記檔
    for dot_file in [".update_in_progress", ".rollback_alert"]:
        p = os.path.join(ROOT_DIR, dot_file)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    # 5. 檢查測試執行期間新增的未終止執行緒

    current_threads = set(threading.enumerate())
    new_threads = current_threads - initial_threads
    for t in new_threads:
        if t.is_alive() and not t.daemon and t != threading.main_thread():
            # 將非 daemon 執行緒標記為 daemon，防止主行程退出時被 join 阻塞懸掛
            t.daemon = True


def pytest_sessionfinish(session, exitstatus):
    """Session 結束時執行清理與退出看門狗：
    強制將所有殘留的子執行緒標註為 daemon，並啟動 5 秒看門狗確保進程在 0% CPU 時能如期終止。
    """
    # 強制垃圾回收以釋放未關閉之 VideoCapture 與 Socket
    gc.collect()

    main_t = threading.main_thread()
    for t in threading.enumerate():
        if t != main_t and t.is_alive():
            if not t.daemon:
                t.daemon = True

    # 啟動終止守護看門狗 (Watchdog)
    # 若 pytest 結束後 Python 解釋器在 C 擴充 (OpenCV/FFmpeg) 或第三方資源釋放時死鎖，
    # 5 秒後以 exitstatus 強制結束進程，徹底避免 0% CPU 懸掛。
    def _watchdog():
        time.sleep(5.0)
        os._exit(exitstatus)

    watchdog_thread = threading.Thread(target=_watchdog, name="PytestExitWatchdog", daemon=True)
    watchdog_thread.start()
