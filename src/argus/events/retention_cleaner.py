import os
import time
import threading
import logging

logger = logging.getLogger("RetentionCleaner")


def clean_expired_records(base_dir, retention_days=30, now=None):
    """
    掃描 recordings/{camera_id}/ 下的 events/ 與 snapshots/ 目錄，
    比對檔案修改時間（mtime）並刪除超過 retention_days 的舊檔案。
    
    回傳被刪除的檔案路徑列表。
    """
    try:
        retention_days = int(retention_days)
    except (ValueError, TypeError):
        retention_days = 30

    if retention_days < 1:
        retention_days = 30
        
    current_time = now if now is not None else time.time()
    cutoff_time = current_time - (retention_days * 86400.0)
    deleted_files = []

    if not base_dir or not os.path.exists(base_dir):
        return deleted_files

    # 遍歷 base_dir 下的所有子目錄
    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            # 僅清理 events 與 snapshots 中的檔案，或者在 recordings 結構下的 .jsonl 與 .jpg / .jpeg
            lower_name = filename.lower()
            if lower_name.endswith(".jsonl") or lower_name.endswith(".jpg") or lower_name.endswith(".jpeg"):
                file_path = os.path.join(root, filename)
                try:
                    mtime = os.path.getmtime(file_path)
                    if mtime < cutoff_time:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                except OSError as e:
                    logger.warning(f"Failed to check or remove file {file_path}: {e}")

    if deleted_files:
        logger.info(f"[RetentionCleaner] Cleaned {len(deleted_files)} expired files older than {retention_days} days.")
    return deleted_files


class RetentionCleanerService:
    """獨立背景 Daemon 執行緒，於啟動時執行一次清理，並每 24 小時定期檢查。"""
    def __init__(self, config_mgr, base_dir=None, interval_seconds=86400):
        self.config_mgr = config_mgr
        import sys
        if base_dir:
            self.base_dir = base_dir
        else:
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(sys.argv[0]))
            self.base_dir = os.path.normpath(os.path.join(exe_dir, "recordings"))
            
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="RetentionCleanerService",
            daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def _run(self):
        # 啟動時立即執行一次清理
        self._perform_cleanup()
        
        while not self._stop_event.is_set():
            # 分段 wait，便於即時響應 stop
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            self._perform_cleanup()

    def _perform_cleanup(self):
        try:
            days = self.config_mgr.get_event_retention_days() if hasattr(self.config_mgr, "get_event_retention_days") else 30
            clean_expired_records(self.base_dir, retention_days=days)
        except Exception as e:
            logger.error(f"[RetentionCleaner] Error during cleanup: {e}")
