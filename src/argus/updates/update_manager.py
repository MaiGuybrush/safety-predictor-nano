"""update_manager.py - 自動更新狀態機與生命週期管理器

管理軟體更新之全生命週期：
1. 版本檢查 (CHECKING -> AVAILABLE / IDLE) 整合 AppUpdateClient 或模擬展示
2. 下載與進度追蹤 (DOWNLOADING -> STAGING -> READY_TO_INSTALL)
3. 重啟程序觸發 (RESTARTING / Exit Code 42)
4. 健康檢查與回滾反饋 (HEALTHCHECK -> COMMITTED / ROLLBACK / FAILED)
5. SSE 事件串流廣播 (支援多客戶端即時進度同步)
"""

import datetime
import json
import logging
import os
import queue
import shutil
import subprocess
import sys
import tarfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from argus import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "1.0.0"

from argus.integration.app_update_client import (
    AppUpdateClient,
    DownloadInfo,
    VersionInfoDTO,
    DEFAULT_APP_ID,
    DEFAULT_BASE_URL,
)
from argus.updates.delta_updater import DeltaUpdater, DeltaManifest, compute_sha256

logger = logging.getLogger("system")


class UpdateState:
    IDLE = "IDLE"
    CHECKING = "CHECKING"
    AVAILABLE = "AVAILABLE"
    DOWNLOADING = "DOWNLOADING"
    STAGING = "STAGING"
    READY_TO_INSTALL = "READY_TO_INSTALL"
    RESTARTING = "RESTARTING"
    HEALTHCHECK = "HEALTHCHECK"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    ROLLBACK = "ROLLBACK"


class UpdateManager:
    """自動更新管理服務：維護全域更新狀態機與 SSE 推播。"""

    def __init__(
        self,
        current_version: str = APP_VERSION,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AppUpdateClient] = None,
    ):
        self._lock = threading.RLock()
        self.current_version = current_version
        self.config = config or {}
        self.state = UpdateState.IDLE
        self.target_version: Optional[str] = None
        self.release_date: Optional[str] = None
        self.release_notes: Optional[str] = None
        self.progress: float = 0.0
        self.downloaded_bytes: int = 0
        self.total_bytes: int = 0
        self.speed_bytes_sec: float = 0.0
        self.speed_text: str = ""
        self.message: str = "系統運作正常，無更新任務"
        self.error: Optional[str] = None
        self.mode: str = "notify" if self.config.get("mode", 2) == 2 else "unattended"
        self.rollback_occurred: bool = False
        self.restart_countdown: Optional[int] = None
        self.auto_update_enabled: bool = bool(self.config.get("enabled", True))

        # 下載候選與暫存路徑
        self.latest_candidate: Optional[VersionInfoDTO] = None
        self.download_info: Optional[DownloadInfo] = None
        self.staging_dir = self.config.get("staging_dir", "updates/staging")
        self.downloaded_archive_path: Optional[str] = None

        # 注入或初始化 client
        self._api_key_missing: bool = False
        self.client = client
        if self.client is None and self.config:
            self.client = AppUpdateClient(
                app_id=self.config.get("app_id", DEFAULT_APP_ID),
                base_urls=self.config.get("base_urls"),
                base_url_path=self.config.get("base_url_path", DEFAULT_BASE_URL),
                channel=self.config.get("channel", "stable"),
                api_key=self.config.get("api_key"),
                fab=self.config.get("ums_fab"),
                timeout=self.config.get("timeout_seconds", 30),
                max_retries=self.config.get("max_retries", 3),
                query_timeout=self.config.get("query_timeout_seconds", 5),
                query_max_retries=self.config.get("query_max_retries", 1),
                chunk_size=self.config.get("download_chunk_size", 1048576),
            )
        if self.api_key_missing:
            logger.warning("[UpdateManager] 未設定 API KEY 無法進行自動更新")

        # Delta 增量更新引擎
        self.base_dir = os.path.abspath(self.config.get("base_dir", "."))
        self.delta_updater = DeltaUpdater(base_dir=self.base_dir)
        self.is_delta: bool = False
        self.exit_code_on_restart: int = 42
        self._exit_func: Callable[[int], None] = sys.exit

        # 優先從 base_dir 或執行環境探測 version.txt
        self._probe_version_file()

        # 檢測回滾告警標記 (.rollback_alert) 與更新進行中標記 (.update_in_progress)
        self._check_rollback_alert()
        self._check_update_in_progress()

        # SSE 訂閱者清單 (每個訂閱者擁有獨立的 Queue)
        self._subscribers: List[queue.Queue] = []
        self._subscribers_lock = threading.Lock()

        # 背景執行緒
        self._task_thread: Optional[threading.Thread] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_polling = threading.Event()

    @property
    def api_key_missing(self) -> bool:
        if self.client is not None:
            return getattr(self.client, "api_key_missing", False) is True
        return getattr(self, "_api_key_missing", False) is True

    @api_key_missing.setter
    def api_key_missing(self, val: bool):
        self._api_key_missing = (val is True)
        if self.client is not None and hasattr(self.client, "api_key_missing"):
            try:
                self.client.api_key_missing = (val is True)
            except Exception:
                pass

    def configure(
        self,
        config: Dict[str, Any],
        ums_api_key: Optional[str] = None,
        ums_fab: Optional[str] = None,
    ):
        """由主程序配置或熱重載更新管理員設定，並管理背景輪詢與開機檢查。"""
        with self._lock:
            self.config = config or {}
            self.staging_dir = self.config.get("staging_dir", "updates/staging")
            self.auto_update_enabled = bool(self.config.get("enabled", True))
            self.mode = "notify" if self.config.get("mode", 2) == 2 else "unattended"

            client_api_key = self.config.get("api_key")
            resolved_fab = ums_fab or self.config.get("ums_fab")
            self.client = AppUpdateClient(
                app_id=self.config.get("app_id", DEFAULT_APP_ID),
                base_urls=self.config.get("base_urls"),
                base_url_path=self.config.get("base_url_path", DEFAULT_BASE_URL),
                channel=self.config.get("channel", "stable"),
                api_key=client_api_key,
                fab=resolved_fab,
                timeout=self.config.get("timeout_seconds", 30),
                max_retries=self.config.get("max_retries", 3),
                query_timeout=self.config.get("query_timeout_seconds", 5),
                query_max_retries=self.config.get("query_max_retries", 1),
                chunk_size=self.config.get("download_chunk_size", 1048576),
            )
            if self.api_key_missing:
                logger.warning("[UpdateManager] 未設定 API KEY 無法進行自動更新")

        if self.auto_update_enabled and not self.api_key_missing:
            self.start_polling(interval=self.config.get("check_interval_seconds", 3600))
            if self.config.get("check_on_startup", True):
                logger.info("[UpdateManager] 開機啟動，觸發 check_on_startup 版本檢查")
                self.check_for_updates()
        else:
            self.stop_polling()

        self._notify_subscribers()

    def start_polling(self, interval: int = 3600):
        """啟動背景定時輪詢執行緒。"""
        if getattr(self, "api_key_missing", False):
            logger.info("[UpdateManager] 未設定 API KEY，跳過背景版本輪詢")
            return

        interval = max(300, int(interval))
        with self._lock:
            if self._poll_thread and self._poll_thread.is_alive():
                return
            self._stop_polling.clear()

            def _poll_worker():
                logger.info(f"[UpdateManager] 背景版本輪詢已啟動 (週期: {interval} 秒)")
                while not self._stop_polling.wait(timeout=interval):
                    if not self.auto_update_enabled or getattr(self, "api_key_missing", False):
                        break
                    if self.state in (UpdateState.IDLE, UpdateState.AVAILABLE, UpdateState.FAILED):
                        try:
                            logger.debug("[UpdateManager] 定時觸發版本檢查...")
                            self.check_for_updates()
                        except Exception as ex:
                            logger.warning(f"[UpdateManager] 背景定時輪詢檢查異常: {ex}")
                logger.info("[UpdateManager] 背景版本輪詢已停止")

            self._poll_thread = threading.Thread(target=_poll_worker, daemon=True, name="UpdateManagerPoller")
            self._poll_thread.start()

    def stop_polling(self):
        """停止背景定時輪詢執行緒。"""
        self._stop_polling.set()
        with self._lock:
            self._poll_thread = None

    def _probe_version_file(self):
        """探測執行端環境目錄之 version.txt，若存在則優先採用。"""
        candidates = [
            os.path.join(self.base_dir, "version.txt"),
            os.path.join(self.base_dir, "_internal", "version.txt"),
        ]
        if os.path.abspath(".") != self.base_dir:
            candidates.append(os.path.abspath("version.txt"))
            candidates.append(os.path.abspath("_internal/version.txt"))

        for path in candidates:
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        ver = f.read().strip()
                    if ver:
                        self.current_version = ver
                        logger.info(f"[UpdateManager] 自 version.txt 成功載入當前版本號: v{ver} ({path})")
                        return
                except Exception as ex:
                    logger.debug(f"[UpdateManager] 讀取 {path} 失敗: {ex}")

    def _check_update_in_progress(self):
        """檢查系統啟動時是否存在 .update_in_progress 標記檔。"""
        progress_path = os.path.join(self.base_dir, ".update_in_progress")
        if not os.path.isfile(progress_path) and os.path.isfile(".update_in_progress"):
            progress_path = os.path.abspath(".update_in_progress")
        if os.path.isfile(progress_path):
            try:
                with open(progress_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.target_version = data.get("target_version")
                self.is_delta = bool(data.get("is_delta", False))
                self.state = UpdateState.HEALTHCHECK
                self.message = f"新版本進程啟動 (v{self.target_version})，執行 30 秒健康狀態評估..."
                logger.info(f"[UpdateManager] 偵測到更新中標記，進入健康判定窗口: {data}")
            except Exception as e:
                logger.warning(f"[UpdateManager] 讀取 .update_in_progress 異常: {e}")

    def _check_rollback_alert(self):
        """檢查系統啟動時是否存在 .rollback_alert 標記檔。"""
        alert_path = os.path.join(self.base_dir, ".rollback_alert")
        if not os.path.isfile(alert_path) and os.path.isfile(".rollback_alert"):
            alert_path = os.path.abspath(".rollback_alert")
        if os.path.isfile(alert_path):
            try:
                with open(alert_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                self.rollback_occurred = True
                self.error = f"自動回滾告警: {content}"
                logger.warning(f"[UpdateManager] 偵測到回滾警示: {content}")
            except Exception:
                self.rollback_occurred = True

    def clear_rollback_alert(self):
        """操作員於 Web UI 確認後清除回滾警示標記。"""
        with self._lock:
            self.rollback_occurred = False
            self.error = None
            for p in {os.path.join(self.base_dir, ".rollback_alert"), os.path.abspath(".rollback_alert")}:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        self._notify_subscribers()


    def get_status(self) -> Dict[str, Any]:
        """取得當前更新狀態之唯讀字典副本。"""
        with self._lock:
            return {
                "state": self.state,
                "current_version": self.current_version,
                "target_version": self.target_version,
                "release_date": self.release_date,
                "release_notes": self.release_notes,
                "progress": round(self.progress, 1),
                "downloaded_bytes": self.downloaded_bytes,
                "total_bytes": self.total_bytes,
                "speed_bytes_sec": self.speed_bytes_sec,
                "speed_text": self.speed_text,
                "message": self.message,
                "error": self.error,
                "mode": self.mode,
                "is_delta": self.is_delta,
                "package_type": "delta" if self.is_delta else "full",
                "rollback_occurred": self.rollback_occurred,
                "restart_countdown": self.restart_countdown,
                "auto_update_enabled": self.auto_update_enabled,
                "api_key_missing": getattr(self, "api_key_missing", False),
                "timestamp": time.time(),
            }

    def _notify_subscribers(self):
        """將當前狀態序列化廣播給所有 SSE 監聽客戶端。"""
        payload = self.get_status()
        with self._subscribers_lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead_queues.append(q)
            for dead in dead_queues:
                if dead in self._subscribers:
                    self._subscribers.remove(dead)

    def subscribe(self) -> queue.Queue:
        """為新連線的 SSE 客戶端註冊訂閱 Queue，並立即推送當前狀態。"""
        q = queue.Queue(maxsize=50)
        with self._subscribers_lock:
            self._subscribers.append(q)
        q.put(self.get_status())
        return q

    def unsubscribe(self, q: queue.Queue):
        """移除斷線客戶端的訂閱 Queue。"""
        with self._subscribers_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def set_state(
        self,
        state: str,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        downloaded: Optional[int] = None,
        total: Optional[int] = None,
        speed_text: Optional[str] = None,
        error: Optional[str] = None,
        target_version: Optional[str] = None,
        release_notes: Optional[str] = None,
        release_date: Optional[str] = None,
        is_delta: Optional[bool] = None,
    ):
        """更新狀態機屬性並觸發 SSE 廣播。"""
        with self._lock:
            self.state = state
            if message is not None:
                self.message = message
            if progress is not None:
                self.progress = float(progress)
            if downloaded is not None:
                self.downloaded_bytes = downloaded
            if total is not None:
                self.total_bytes = total
            if speed_text is not None:
                self.speed_text = speed_text
            if error is not None:
                self.error = error
            if target_version is not None:
                self.target_version = target_version
            if release_notes is not None:
                self.release_notes = release_notes
            if release_date is not None:
                self.release_date = release_date
            if is_delta is not None:
                self.is_delta = bool(is_delta)

        self._notify_subscribers()


    def check_for_updates(self) -> Dict[str, Any]:
        """手動或定時觸發版本檢查。一律透過 AppUpdateClient 查詢最新版本。"""
        if getattr(self, "api_key_missing", False):
            return {
                "status": "error",
                "message": "未設定 API KEY，無法進行更新檢查，請至設定頁配置 auto_update.api_key",
            }

        with self._lock:
            if self.state in (UpdateState.CHECKING, UpdateState.DOWNLOADING, UpdateState.STAGING, UpdateState.RESTARTING):
                return {"status": "busy", "message": f"目前更新狀態為 {self.state}，請稍候", "data": self.get_status()}

            self.state = UpdateState.CHECKING
            self.message = "正在向 App Management API 查詢最新版本..."
            self.error = None
        self._notify_subscribers()

        def _do_check():
            try:
                candidate = None
                if self.client is not None:
                    # 呼叫真實 Client
                    try:
                        candidate = self.client.check_latest_candidate(self.current_version)
                    except Exception as client_err:
                        logger.warning(f"[UpdateManager] Client 查詢新版本異常: {client_err}")
                        raise client_err

                    if candidate:
                        try:
                            dl_info = self.client.get_download_info(candidate.version)
                            with self._lock:
                                self.download_info = dl_info
                                self.is_delta = dl_info.is_delta
                                self.total_bytes = dl_info.size
                        except Exception as ex:
                            logger.debug(f"[UpdateManager] 預取下載資訊失敗: {ex}")
                            with self._lock:
                                self.is_delta = False
                                self.total_bytes = 104857600
                else:
                    logger.warning("[UpdateManager] 未設定 AppUpdateClient，無法進行版本檢查")

                with self._lock:
                    if candidate:
                        self.latest_candidate = candidate
                        self.target_version = candidate.version
                        self.release_date = candidate.release_date or "最新發布"
                        self.release_notes = candidate.release_notes or "版本更新維護"
                        self.state = UpdateState.AVAILABLE
                        if self.is_delta:
                            self.message = f"發現新版本 {self.target_version} (📦 增量更新 ~{(self.total_bytes / (1024*1024)):.1f} MB)，可進行下載"
                        else:
                            self.message = f"發現新版本 {self.target_version}，可進行下載"
                        self.downloaded_bytes = 0
                        self.progress = 0.0
                    else:
                        self.state = UpdateState.IDLE
                        self.message = f"目前已是最新版本 ({self.current_version})"
            except Exception as e:
                logger.warning(f"[UpdateManager] 版本檢查失敗: {e}")
                with self._lock:
                    self.state = UpdateState.IDLE
                    self.message = f"版本檢查未成功: {e}"
            finally:
                self._notify_subscribers()

        threading.Thread(target=_do_check, daemon=True).start()
        return {"status": "ok", "message": "已觸發版本檢查", "data": self.get_status()}

    def start_download(self, mock_speed_mbps: float = 12.0) -> Dict[str, Any]:
        """觸發下載新版本並解壓縮至 Staging 目錄。"""
        with self._lock:
            if self.state not in (UpdateState.AVAILABLE, UpdateState.FAILED):
                return {"status": "error", "message": f"目前狀態 ({self.state}) 不支援觸發下載", "data": self.get_status()}

            # 磁碟預檢空間需求：Delta 僅需 20MB，全量需 2.5 倍約 650MB
            required_space = 20 * 1024 * 1024 if self.is_delta else max(int((self.total_bytes or 104857600) * 2.5), 650 * 1024 * 1024)
            staging_check_dir = os.path.dirname(os.path.abspath(self.staging_dir))
            try:
                free_space = shutil.disk_usage(staging_check_dir).free
                if free_space < required_space:
                    self.state = UpdateState.FAILED
                    err_msg = f"磁碟剩餘空間不足: 需要 {required_space / (1024*1024):.1f} MB，但僅剩 {free_space / (1024*1024):.1f} MB"
                    self.error = err_msg
                    self.message = err_msg
                    self._notify_subscribers()
                    return {"status": "error", "message": err_msg, "data": self.get_status()}
            except Exception as e:
                logger.warning(f"[UpdateManager] 預檢磁碟空間異常: {e}")

            self.state = UpdateState.DOWNLOADING
            self.progress = 0.0
            self.downloaded_bytes = 0
            if not self.total_bytes:
                self.total_bytes = 2516582 if self.is_delta else 104857600
            self.message = "開始下載增量更新包..." if self.is_delta else "開始下載更新安裝包..."
            self.error = None
        self._notify_subscribers()

        def _progress_cb(downloaded: int, total: int, speed: float, speed_txt: str):
            with self._lock:
                self.downloaded_bytes = downloaded
                self.total_bytes = total
                self.progress = (downloaded / max(1, total)) * 100.0
                self.speed_bytes_sec = speed
                self.speed_text = speed_txt
                mb_curr = downloaded / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                prefix = "正在下載增量補丁..." if self.is_delta else "正在下載更新包..."
                self.message = f"{prefix} ({mb_curr:.1f} MB / {mb_tot:.1f} MB, {speed_txt})"
            self._notify_subscribers()

        def _do_download():
            try:
                # 判斷是否使用真實 Client 下載
                real_download_success = False
                if self.client and self.target_version:
                    try:
                        download_info = self.client.get_download_info(self.target_version)
                        self.download_info = download_info
                        self.is_delta = download_info.is_delta
                        self.total_bytes = download_info.size
                        os.makedirs("updates", exist_ok=True)
                        if self.is_delta:
                            pkg_name = f"argus_delta-v{self.target_version}-arm64.tar.gz"
                        else:
                            pkg_name = f"{self.client.app_id}-v{self.target_version}-arm64.tar.gz"
                        dest_archive = os.path.join("updates", pkg_name)
                        self.client.download_package(download_info, dest_archive, progress_callback=_progress_cb)
                        self.downloaded_archive_path = dest_archive
                        real_download_success = True
                    except Exception as ex:
                        if self.client and not self.client.api_key_missing:
                            # 正式環境有配置 API KEY，下載失敗或校驗失敗必須立即報錯，不可走模擬展示
                            raise RuntimeError(f"更新包下載或校驗失敗: {ex}") from ex
                        logger.warning(f"[UpdateManager] 模擬模式下載切換為展示流程: {ex}")

                if not real_download_success:
                    # 平滑模擬下載流程
                    total = self.total_bytes or (2516582 if self.is_delta else 104857600)
                    downloaded = 0
                    chunk = 1024 * 256 if self.is_delta else 1024 * 1024 * 5
                    start_t = time.time()
                    while downloaded < total:
                        time.sleep(0.1 if self.is_delta else 0.3)
                        with self._lock:
                            if self.state != UpdateState.DOWNLOADING:
                                break
                            downloaded = min(total, downloaded + chunk)
                            self.downloaded_bytes = downloaded
                            self.progress = (downloaded / total) * 100.0
                            elapsed = max(0.01, time.time() - start_t)
                            speed = downloaded / elapsed
                            self.speed_bytes_sec = speed
                            self.speed_text = f"{speed / (1024 * 1024):.1f} MB/s"
                            mb_curr = downloaded / (1024 * 1024)
                            mb_tot = total / (1024 * 1024)
                            prefix = "正在下載增量補丁..." if self.is_delta else "正在下載更新包..."
                            self.message = f"{prefix} ({mb_curr:.1f} MB / {mb_tot:.1f} MB, {self.speed_text})"
                        self._notify_subscribers()

                # 解壓縮與 Staging 驗證階段
                with self._lock:
                    self.state = UpdateState.STAGING
                    self.progress = 100.0
                    self.message = "下載完成，正在解壓並驗證 Delta 補丁完整性..." if self.is_delta else "下載完成，正在解壓縮並驗證暫存目錄檔案完整性..."
                self._notify_subscribers()

                # 下載封包整體 SHA256 雜湊校驗
                if self.downloaded_archive_path and os.path.isfile(self.downloaded_archive_path):
                    if self.download_info and self.download_info.sha256 and str(self.download_info.sha256).strip():
                        actual_archive_sha = compute_sha256(self.downloaded_archive_path)
                        expected_archive_sha = str(self.download_info.sha256).strip().lower()
                        if actual_archive_sha != expected_archive_sha:
                            raise RuntimeError(
                                f"檔案校驗失敗: 下載更新包雜湊不符 (預期 {self.download_info.sha256}，實際 {actual_archive_sha})"
                            )

                    # 若有實際封包則解壓至 staging 目錄
                    os.makedirs(self.staging_dir, exist_ok=True)
                    try:
                        with tarfile.open(self.downloaded_archive_path, "r:*") as tar:
                            if sys.version_info >= (3, 12):
                                tar.extractall(path=self.staging_dir, filter="data")
                            else:
                                tar.extractall(path=self.staging_dir)
                    except Exception as e:
                        raise RuntimeError(f"解壓更新封包失敗: {e}") from e

                # 識別是否為 Delta package
                if self.is_delta_package(self.staging_dir) or (self.downloaded_archive_path and self.is_delta_package(self.downloaded_archive_path)):
                    self.is_delta = True

                # 若為 Delta package，呼叫 install.sh --delta 或 DeltaUpdater 執行局部原子替換與雜湊校驗
                if self.is_delta and os.path.exists(self.staging_dir):
                    logger.info(f"[UpdateManager] 執行 Delta 局部原子替換與校驗 (staging={self.staging_dir})")
                    delta_res = self.run_install_delta(self.staging_dir)
                    if isinstance(delta_res, dict) and delta_res.get("status") != "ok":
                        err_msg = delta_res.get("error") or delta_res.get("message") or "Delta 局部原子替換失敗"
                        raise RuntimeError(f"Delta 增量替換失敗: {err_msg}")
                elif os.path.exists(self.staging_dir):
                    # 全量包或一般包若包含 manifest.json，執行檔案雜湊校驗
                    manifest_file = os.path.join(self.staging_dir, "manifest.json")
                    if os.path.isfile(manifest_file):
                        manifest = DeltaManifest.from_manifest_file(manifest_file)
                        payload_dir = os.path.join(self.staging_dir, "payload")
                        if os.path.isdir(payload_dir) and manifest.files:
                            valid, mismatches = manifest.verify_payload(payload_dir)
                            if not valid:
                                raise RuntimeError(f"檔案校驗失敗: {'; '.join(mismatches)}")

                time.sleep(0.5)

                with self._lock:
                    self.state = UpdateState.READY_TO_INSTALL
                    if self.is_delta:
                        self.message = f"增量補丁 {self.target_version} 已就緒，請點擊立即重啟套用"
                    else:
                        self.message = f"新版本 {self.target_version} 已就緒，請點擊立即重啟套用"
                self._notify_subscribers()

                # 若更新模式為無人值守 (mode == 1)，延遲 3 秒直接自動觸發重啟
                if self.mode == "unattended":
                    time.sleep(3.0)
                    self.trigger_restart()

            except Exception as e:
                logger.error(f"[UpdateManager] 更新準備或校驗失敗: {e}")
                with self._lock:
                    self.state = UpdateState.FAILED
                    self.error = str(e)
                    self.message = f"更新失敗: {e}"
                self._notify_subscribers()

        self._task_thread = threading.Thread(target=_do_download, daemon=True)
        self._task_thread.start()
        return {"status": "ok", "message": "已開始下載更新包", "data": self.get_status()}

    def run_install_delta(self, delta_source: Optional[str] = None) -> Dict[str, Any]:
        """執行 Delta 局部原子替換：優先呼叫 scripts/install.sh --delta，若無 bash 環境則使用 DeltaUpdater。"""
        source = delta_source or self.staging_dir
        
        script_candidates = [
            os.path.join(self.base_dir, "scripts", "install.sh"),
            os.path.join(self.base_dir, "install.sh"),
            os.path.abspath("scripts/install.sh"),
        ]
        install_sh = next((p for p in script_candidates if os.path.isfile(p)), None)

        bash_exe = None
        # 在 Windows 環境下避免調用 bash scripts/install.sh（因路徑斜線問題易報錯），直接使用 Python DeltaUpdater
        if sys.platform != "win32":
            for candidate in [shutil.which("bash"), shutil.which("sh")]:
                if candidate and os.path.isfile(candidate):
                    bash_exe = candidate
                    break

        if bash_exe and install_sh:
            try:
                cmd = [bash_exe, install_sh, "--delta", source]
                res = subprocess.run(
                    cmd,
                    cwd=self.base_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0:
                    logger.info("[UpdateManager] install.sh --delta 執行成功")
                    return {"status": "ok", "method": "install.sh", "output": res.stdout}
                else:
                    logger.warning(f"[UpdateManager] install.sh --delta 返回非零代碼 ({res.returncode}): {res.stderr}")
            except Exception as e:
                logger.warning(f"[UpdateManager] 調用 install.sh --delta 異常: {e}")

        # Fallback to Python DeltaUpdater (校驗失敗拋出異常，向上冒泡)
        return self.apply_delta_update(source)

    def trigger_restart(self, exit_on_restart: Optional[bool] = None) -> Dict[str, Any]:
        """觸發重啟與版本目錄原子替換。"""
        with self._lock:
            if self.state != UpdateState.READY_TO_INSTALL:
                return {"status": "error", "message": f"目前狀態 ({self.state}) 尚未就緒安裝", "data": self.get_status()}

            self.state = UpdateState.RESTARTING
            self.restart_countdown = 30
            self.message = "系統正在重啟並套用新版本，請稍候..."
        self._notify_subscribers()

        def _do_restart():
            logger.info("AutoUpdate: Triggering restart sequence (Exit code 42 for run.sh)")
            # 寫入進行中標記
            targets = [os.path.join(self.base_dir, ".update_in_progress")]
            if os.path.abspath(".") != self.base_dir:
                targets.append(".update_in_progress")
            for p in targets:
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "target_version": self.target_version,
                            "timestamp": time.time(),
                            "backup_dir": self.config.get("backup_dir", "argus_predictor_bak"),
                            "is_delta": self.is_delta,
                        }))
                except Exception:
                    pass

            time.sleep(1.0)

            # 若指定 exit_on_restart 或非 pytest 測試環境，呼叫 sys.exit(42)
            should_exit = exit_on_restart if exit_on_restart is not None else (not os.environ.get("PYTEST_CURRENT_TEST"))
            if should_exit:
                logger.info(f"AutoUpdate: Invoking sys.exit({self.exit_code_on_restart}) for outer runner loop restart")
                self._exit_func(self.exit_code_on_restart)
                return

            # 模擬流程推進：HEALTHCHECK -> COMMITTED -> IDLE
            with self._lock:
                self.state = UpdateState.HEALTHCHECK
                self.message = "新版本進程啟動，執行 30 秒健康狀態評估..."
            self._notify_subscribers()

            time.sleep(1.0)
            self.commit_update()

            time.sleep(1.0)
            with self._lock:
                self.state = UpdateState.IDLE
                self.message = "系統運作正常"
            self._notify_subscribers()

        threading.Thread(target=_do_restart, daemon=True).start()
        return {"status": "ok", "message": "已觸發重啟序列", "data": self.get_status()}

    def commit_update(self) -> Dict[str, Any]:
        """三階段健康檢查通過後，確立 (Commit) 更新完成並移除標記檔。"""
        with self._lock:
            targets = [os.path.join(self.base_dir, ".update_in_progress")]
            if os.path.abspath(".") != self.base_dir:
                targets.append(".update_in_progress")
            for p in targets:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

            if self.target_version:
                self.current_version = self.target_version
                self.target_version = None
            self.state = UpdateState.COMMITTED
            self.message = f"系統已成功升級至 v{self.current_version} 並通過健康檢查！"
            self.progress = 0.0
            self.downloaded_bytes = 0
            self.total_bytes = 0
            try:
                log_dirs = [os.path.join(self.base_dir, "logs")] if self.base_dir and self.base_dir != "." else []
                log_dirs.append("logs")
                for ld in set(log_dirs):
                    os.makedirs(ld, exist_ok=True)
                    with open(os.path.join(ld, "update.log"), "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.datetime.now().isoformat()}] [COMMITTED] 成功升級至 v{self.current_version} (is_delta={self.is_delta})\n")
            except Exception:
                pass
        self._notify_subscribers()
        return {"status": "ok", "message": "更新確立完成", "data": self.get_status()}


    def is_delta_package(self, path: Optional[str] = None) -> bool:
        """檢查指定路徑或 staging 目錄是否為 Delta 增量包。"""
        target = path or self.staging_dir
        if not target or not os.path.exists(target):
            return False
        try:
            if os.path.isdir(target):
                m_file = os.path.join(target, "manifest.json")
                if os.path.isfile(m_file):
                    m = DeltaManifest.from_manifest_file(m_file)
                    return m.package_type == "delta"
            elif os.path.isfile(target):
                m = DeltaManifest.from_archive(target)
                return m.package_type == "delta"
        except Exception:
            return False
        return False

    def apply_delta_update(self, delta_source: str) -> Dict[str, Any]:
        """透過 Delta 更新引擎執行局域原子置換。"""
        return self.delta_updater.apply_delta(
            delta_source=delta_source,
            current_base_version=self.current_version,
        )

    def trigger_mock_rollback(self) -> Dict[str, Any]:
        """模擬回滾情境（供測試與原型驗證）。"""
        with self._lock:
            self.state = UpdateState.ROLLBACK
            self.rollback_occurred = True
            self.message = "新版本健康檢查逾時未就緒，已自動回滾至上一版本！"
            self.error = "HealthCheckTimeout: /api/health 未於 30 秒內回傳 healthy 狀態"
            if self.delta_updater.has_patch_backup():
                try:
                    self.delta_updater.rollback()
                except Exception as e:
                    logger.warning(f"[UpdateManager] Delta 局部回滾異常: {e}")
            try:
                with open(".rollback_alert", "w", encoding="utf-8") as f:
                    f.write(self.error)
            except Exception:
                pass
        self._notify_subscribers()
        return {"status": "ok", "message": "已模擬回滾狀態", "data": self.get_status()}


GLOBAL_UPDATE_MANAGER = UpdateManager()
