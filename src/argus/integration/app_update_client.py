"""app_update_client.py - App Management API 客戶端

串接 App Management API (v9.2.0)，負責：
1. 查詢應用程式版本資訊 (GET /App/{appId}/Version 或 /Version/nocache)
2. 語意化版本比對 (SemVer 2.0.0)，支援 stable/beta 通道過濾
3. 取得發布檔案下載資訊 (GET /File/{appId}/DownloadInfo?version={version})
4. 串流下載二進位安裝包 (GET /File/{appId})，支援 1MB 分塊與進度回呼
5. 整合 Gateway 多節點自動容錯切換 (Failover) 與指數退避重試
"""

import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode, urlsplit

import requests

from argus.integration import ums_config

logger = logging.getLogger("app_update_client")

# 預設常數
DEFAULT_APP_ID = "safety-predictor-nano"
DEFAULT_BASE_URL = "AppManagementApi"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB
DEFAULT_GATEWAY_HOSTS = [
    "http://tncimweb1.cminl.oa",
    "http://tncimweb2.cminl.oa",
]


class AppUpdateError(Exception):
    """AppUpdateClient 基礎例外。"""
    pass


class AppUpdatePermanentError(AppUpdateError):
    """永久性錯誤（如 401 認證失敗、404 資源不存在、磁碟空間不足），不進行重試。"""
    pass


class AppUpdateTransientError(AppUpdateError):
    """暫態性錯誤（如 5xx、連線逾時），可進行指數退避重試。"""
    pass


@dataclass
class VersionInfoDTO:
    """版本清單單一版本項目。"""
    version: str
    released: bool
    auto_update: bool
    locked: bool
    release_date: str = ""
    release_notes: str = ""
    release_fab: str = ""
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class DownloadInfo:
    """下載元數據。"""
    app_id: str
    version: str
    owner: str
    file_path: str
    size: int
    sha256: Optional[str] = None
    is_delta: bool = False


def parse_semver(v_str: str):
    """解析語意化版本號 (SemVer 2.0.0)。
    回傳 ((major, minor, patch), is_prerelease, prerelease_tag)
    """
    cleaned = re.sub(r'^[vV]', '', str(v_str).strip())
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?', cleaned)
    if not match:
        # Fallback for simple 2-segment versions like 1.0
        match_simple = re.match(r'^(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?', cleaned)
        if match_simple:
            return ((int(match_simple.group(1)), int(match_simple.group(2)), 0), bool(match_simple.group(3)), match_simple.group(3) or "")
        return ((0, 0, 0), True, "invalid")

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = match.group(4)
    return ((major, minor, patch), bool(prerelease), prerelease or "")


def is_newer_version(candidate: str, current: str, allow_prerelease: bool = False) -> bool:
    """比對 candidate 版本是否比 current 版本新。"""
    cand_core, cand_pre, _ = parse_semver(candidate)
    curr_core, curr_pre, _ = parse_semver(current)

    if not allow_prerelease and cand_pre:
        return False

    if cand_core > curr_core:
        return True
    if cand_core == curr_core:
        if curr_pre and not cand_pre:
            return True
    return False


def resolve_app_management_base_urls(
    base_urls: Optional[List[str]] = None,
    base_url_path: str = DEFAULT_BASE_URL,
    ums_api_config: Optional[dict] = None,
    ip_addresses: Optional[List[str]] = None,
) -> List[str]:
    """解析 App Management API 的可用完整 base URL 清單。

    若未明確給定 base_urls，則依據本機 IP 與 ums-api-config.json 解析出 Gateway 主機，
    並拼接上 base_url_path（預設為 'AppManagementApi'）。
    """
    if base_urls:
        if isinstance(base_urls, str):
            urls = [u.strip().rstrip("/") for u in base_urls.split(",") if u.strip()]
        else:
            urls = [str(u).strip().rstrip("/") for u in base_urls if str(u).strip()]
        if urls:
            return urls

    if ums_api_config is None:
        ums_api_config = ums_config.load_ums_api_config()
    if ip_addresses is None:
        ip_addresses = ums_config.get_device_ipv4_addresses()

    fab = ums_config.detect_fab_from_ips(ip_addresses, ums_api_config=ums_api_config)
    endpoints = ums_config.get_ums_endpoints_for_fab(fab, ums_api_config=ums_api_config)

    hosts = []
    for ep in endpoints:
        if not ep or not isinstance(ep, str):
            continue
        try:
            parsed = urlsplit(ep.strip())
            if parsed.scheme and parsed.netloc:
                host_url = f"{parsed.scheme}://{parsed.netloc}"
                if host_url not in hosts:
                    hosts.append(host_url)
        except Exception:
            pass

    if not hosts:
        hosts = list(DEFAULT_GATEWAY_HOSTS)

    path_clean = base_url_path.strip().strip("/")
    return [f"{host}/{path_clean}" for host in hosts]


class AppUpdateClient:
    """App Management API 客戶端。"""

    def __init__(
        self,
        app_id: str = DEFAULT_APP_ID,
        base_urls: Optional[List[str]] = None,
        base_url_path: str = DEFAULT_BASE_URL,
        channel: str = "stable",
        api_key: Optional[str] = None,
        ums_api_key: Optional[str] = None,
        fab: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        session: Optional[requests.Session] = None,
    ):
        self.app_id = app_id.strip() if app_id else DEFAULT_APP_ID
        self.base_urls = resolve_app_management_base_urls(base_urls=base_urls, base_url_path=base_url_path)
        self.channel = channel.strip().lower() if channel else "stable"
        self.fab = fab.strip().lower() if fab else ""
        self.api_key = self._resolve_api_key(api_key, ums_api_key)
        self.api_key_missing: bool = not bool(self.api_key)
        if self.api_key_missing:
            logger.warning("[AppUpdateClient] 未設定 API KEY 無法進行自動更新")
        self.timeout = timeout
        self.max_retries = max_retries
        self.chunk_size = chunk_size
        self.session = session or requests.Session()
        self.active_index = 0

    def _resolve_api_key(self, explicit_key: Optional[str], ums_api_key: Optional[str] = None) -> str:
        """4 級 API Key 退避鏈：
        1. auto_update.api_key (explicit_key)
        2. ums_api_key
        3. 環境變數 APP_MGR_API_KEY
        4. 環境變數 UMS_API_KEY
        """
        if explicit_key and str(explicit_key).strip():
            return str(explicit_key).strip()
        if ums_api_key and str(ums_api_key).strip():
            return str(ums_api_key).strip()
        env_app_mgr = os.environ.get("APP_MGR_API_KEY", "").strip()
        if env_app_mgr:
            return env_app_mgr
        env_ums = os.environ.get("UMS_API_KEY", "").strip()
        if env_ums:
            return env_ums
        return ""

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-KEY"] = self.api_key
        return headers

    def _ordered_base_urls(self) -> List[str]:
        n = len(self.base_urls)
        return [self.base_urls[(self.active_index + i) % n] for i in range(n)]

    def _request_with_failover(self, method: str, path: str, **kwargs) -> requests.Response:
        """多節點自動 Failover 與重試請求。"""
        urls = self._ordered_base_urls()
        last_exception = None

        for base_url in urls:
            full_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
            headers = self._get_headers()
            if "headers" in kwargs:
                headers.update(kwargs.pop("headers"))

            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = self.session.request(
                        method=method,
                        url=full_url,
                        headers=headers,
                        timeout=kwargs.get("timeout", self.timeout),
                        **kwargs,
                    )
                    # 401 / 403 / 404 為永久性錯誤，不進行輪替重試
                    if resp.status_code in (401, 403):
                        raise AppUpdatePermanentError(f"API 認證授權失敗 (HTTP {resp.status_code}): {resp.text[:200]}")
                    if resp.status_code == 404:
                        raise AppUpdatePermanentError(f"目標資源不存在 (HTTP 404): {resp.text[:200]}")

                    if 200 <= resp.status_code < 300:
                        self.active_index = self.base_urls.index(base_url)
                        return resp

                    # 5xx 視為暫態錯誤
                    if resp.status_code >= 500:
                        raise AppUpdateTransientError(f"伺服器錯誤 (HTTP {resp.status_code})")

                    raise AppUpdatePermanentError(f"HTTP 狀態碼異常 ({resp.status_code}): {resp.text[:200]}")

                except AppUpdatePermanentError:
                    raise
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"[AppUpdateClient] 請求 {full_url} 失敗 (嘗試 {attempt}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries:
                        time.sleep(0.5 * (2 ** (attempt - 1)))  # 指數退避

        raise AppUpdateTransientError(f"所有 API 端點皆無法連線: {last_exception}")

    def get_version_list(self) -> List[VersionInfoDTO]:
        """查詢應用程式所有版本清單 (GET /App/{appId}/Version/nocache 或 /Version)。"""
        path = f"App/{self.app_id}/Version/nocache"
        try:
            resp = self._request_with_failover("GET", path)
        except AppUpdateError:
            # Fallback to without nocache
            path = f"App/{self.app_id}/Version"
            resp = self._request_with_failover("GET", path)

        data = resp.json()
        if not isinstance(data, list):
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                data = data["data"]
            else:
                data = [data] if isinstance(data, dict) else []

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            ver = str(item.get("version") or item.get("appVersion") or "").strip()
            if not ver:
                continue
            dto = VersionInfoDTO(
                version=ver,
                released=bool(item.get("released", item.get("isReleased", True))),
                auto_update=bool(item.get("autoUpdate", item.get("isAutoUpdate", True))),
                locked=bool(item.get("locked", False)),
                release_date=str(item.get("releaseDate") or item.get("updatedAt") or ""),
                release_notes=str(item.get("releaseNotes") or item.get("description") or item.get("changelog") or ""),
                release_fab=str(item.get("releaseFab") or item.get("fab") or ""),
                raw_data=item,
            )
            results.append(dto)

        return results

    def check_latest_candidate(self, current_version: str) -> Optional[VersionInfoDTO]:
        """過濾並找出高於 current_version 的最新發布版本。"""
        versions = self.get_version_list()
        allow_prerelease = (self.channel == "beta")

        candidates = []
        for v in versions:
            if not v.released or not v.auto_update or v.locked:
                continue
            # 廠區發布規則篩選 (release_fab)
            if v.release_fab:
                rf = v.release_fab.strip().lower()
                if rf not in ("all", "*", ""):
                    if self.fab and rf != self.fab:
                        continue
            if is_newer_version(v.version, current_version, allow_prerelease=allow_prerelease):
                candidates.append(v)

        if not candidates:
            return None

        # 排序取最新版本
        candidates.sort(key=lambda x: parse_semver(x.version)[0], reverse=True)
        return candidates[0]

    def get_download_info(self, version: str) -> DownloadInfo:
        """取得下載發布檔案元數據 (GET /File/{appId}/DownloadInfo?version={version})。"""
        path = f"File/{self.app_id}/DownloadInfo?version={version}"
        resp = self._request_with_failover("GET", path)
        data = resp.json()
        if not isinstance(data, dict):
            raise AppUpdatePermanentError(f"DownloadInfo 回應格式錯誤: {data}")

        owner = data.get("owner") or ""
        files_info = data.get("filesInfo") or data.get("files") or []

        chosen_file = None
        is_delta = False
        if isinstance(files_info, list) and files_info:
            # 1. 優先挑選 Delta 增量補丁封包 (如 argus_delta-*.tar.gz)
            for f in files_info:
                fn = str(f.get("fileName") or f.get("filePath") or "").lower()
                if "delta" in fn and (".tar.gz" in fn or ".tgz" in fn or ".zip" in fn):
                    chosen_file = f
                    is_delta = True
                    break
            # 2. 若無增量包，自動安全降級 (Fallback) 選取全量包 (優先 arm64 / .tar.gz)
            if not chosen_file:
                for f in files_info:
                    fn = str(f.get("fileName") or f.get("filePath") or "").lower()
                    if "arm64" in fn and (".tar.gz" in fn or ".tgz" in fn):
                        chosen_file = f
                        break
            if not chosen_file:
                for f in files_info:
                    fn = str(f.get("fileName") or f.get("filePath") or "").lower()
                    if ".tar.gz" in fn or ".tgz" in fn or ".zip" in fn:
                        chosen_file = f
                        break
            if not chosen_file:
                chosen_file = files_info[0]
        elif isinstance(files_info, dict):
            chosen_file = files_info
            fn = str(chosen_file.get("fileName") or chosen_file.get("filePath") or "").lower()
            if "delta" in fn:
                is_delta = True

        if not chosen_file:
            raise AppUpdatePermanentError(f"找不到可用之發布封包檔案資訊: {data}")

        file_path = chosen_file.get("filePath") or chosen_file.get("fileName") or ""
        size = int(chosen_file.get("size") or chosen_file.get("fileSize") or 0)
        sha256 = chosen_file.get("sha256") or chosen_file.get("checksum")

        return DownloadInfo(
            app_id=self.app_id,
            version=version,
            owner=owner,
            file_path=file_path,
            size=size,
            sha256=sha256,
            is_delta=is_delta,
        )

    def download_package(
        self,
        info: DownloadInfo,
        dest_path: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
    ) -> str:
        """分塊串流下載二進位安裝包 (GET /File/{appId}?owner={owner}&version={version}&filePath={filePath})。

        progress_callback 簽名: (downloaded_bytes, total_bytes, speed_bytes_sec, speed_text)
        """
        # 1. 磁碟剩餘空間檢查 (Delta 僅需 20MB，全量需 2.5 倍約 650MB)
        dest_dir = os.path.dirname(os.path.abspath(dest_path))
        os.makedirs(dest_dir, exist_ok=True)

        if info.is_delta:
            required_space = 20 * 1024 * 1024  # 20 MB
        else:
            required_space = max(int(info.size * 2.5), 650 * 1024 * 1024) if info.size > 0 else 650 * 1024 * 1024

        try:
            free_space = shutil.disk_usage(dest_dir).free
            if free_space < required_space:
                raise AppUpdatePermanentError(
                    f"磁碟剩餘空間不足: 需要 {required_space / (1024*1024):.1f} MB，但僅剩 {free_space / (1024*1024):.1f} MB"
                )
        except Exception as e:
            if isinstance(e, AppUpdatePermanentError):
                raise
            logger.warning(f"[AppUpdateClient] 檢查磁碟剩餘空間失敗: {e}")

        # 2. 構建下載請求
        params = {
            "owner": info.owner,
            "version": info.version,
            "filePath": info.file_path,
        }
        query_str = urlencode(params)
        path = f"File/{self.app_id}?{query_str}"

        temp_dest = dest_path + ".downloading"
        downloaded = 0
        total = info.size
        start_time = time.time()
        last_callback_time = 0.0

        urls = self._ordered_base_urls()
        last_exception = None

        for base_url in urls:
            full_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
            headers = self._get_headers()
            try:
                with self.session.get(full_url, headers=headers, stream=True, timeout=self.timeout) as resp:
                    if resp.status_code in (401, 403):
                        raise AppUpdatePermanentError(f"下載認證失敗 (HTTP {resp.status_code})")
                    if resp.status_code == 404:
                        raise AppUpdatePermanentError(f"下載檔案不存在 (HTTP 404)")
                    if resp.status_code != 200:
                        raise AppUpdateTransientError(f"下載伺服器回應異常 ({resp.status_code})")

                    content_length = resp.headers.get("Content-Length")
                    if content_length and int(content_length) > 0:
                        total = int(content_length)

                    with open(temp_dest, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

                                now = time.time()
                                if progress_callback and (now - last_callback_time >= 0.2 or downloaded == total):
                                    elapsed = max(0.001, now - start_time)
                                    speed = downloaded / elapsed
                                    speed_text = f"{speed / (1024 * 1024):.1f} MB/s"
                                    try:
                                        progress_callback(downloaded, total, speed, speed_text)
                                    except Exception:
                                        pass
                                    last_callback_time = now

                    # 下載完畢，原子替換
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    os.replace(temp_dest, dest_path)
                    logger.info(f"[AppUpdateClient] 下載成功儲存至 {dest_path} (大小: {downloaded} bytes)")
                    return dest_path

            except AppUpdatePermanentError:
                if os.path.exists(temp_dest):
                    os.remove(temp_dest)
                raise
            except Exception as e:
                last_exception = e
                logger.warning(f"[AppUpdateClient] 從 {full_url} 下載失敗: {e}")
                if os.path.exists(temp_dest):
                    try:
                        os.remove(temp_dest)
                    except Exception:
                        pass

        raise AppUpdateTransientError(f"所有端點下載失敗: {last_exception}")
