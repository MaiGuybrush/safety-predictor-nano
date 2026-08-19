import logging
import os
from pathlib import Path

try:
    from ums_client import UmsApiClient, ModelInfo, ModelVersionInfo
except ImportError:
    UmsApiClient = None
    ModelInfo = None
    ModelVersionInfo = None

from config_manager import DEFAULT_UMS_BASE_URLS

logger = logging.getLogger("ums_failover")


class FailoverUmsClient:
    """UMS 多端點透明容錯切換客戶端 (Failover UMS Client)。

    相容 UmsApiClient 介面，在呼叫失敗（如連線逾時、網路中斷、HTTP 5xx）時
    自動依序嘗試備援端點，並在成功時記憶當前 Active 端點。
    """

    def __init__(self, base_urls=None, api_key=None, timeout=10, client_factory=None):
        if base_urls is None:
            urls = list(DEFAULT_UMS_BASE_URLS)
        elif isinstance(base_urls, str):
            urls = [u.strip() for u in base_urls.split(",") if u.strip()]
        elif isinstance(base_urls, (list, tuple)):
            urls = [str(u).strip() for u in base_urls if str(u).strip()]
        else:
            urls = list(DEFAULT_UMS_BASE_URLS)

        if not urls:
            urls = list(DEFAULT_UMS_BASE_URLS)

        self.base_urls = urls
        self.api_key = api_key if api_key is not None else os.environ.get("UMS_API_KEY", "")
        self.timeout = timeout
        self.active_index = 0
        self._client_factory = client_factory

    @classmethod
    def from_env(cls, timeout=10, client_factory=None):
        """從環境變數 UMS_BASE_URL / UMS_BASE_URLS 與 UMS_API_KEY 建立 client。"""
        env_urls = os.environ.get("UMS_BASE_URL") or os.environ.get("UMS_BASE_URLS")
        api_key = os.environ.get("UMS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "缺少環境變數：UMS_API_KEY。請設定 UMS_API_KEY（UMS 平台 API Key）。"
            )
        return cls(base_urls=env_urls, api_key=api_key, timeout=timeout, client_factory=client_factory)

    def _get_client_for_url(self, base_url, timeout=None):
        to = timeout if timeout is not None else self.timeout
        if self._client_factory is not None:
            return self._client_factory(base_url, self.api_key, to)
        if UmsApiClient is None:
            raise RuntimeError("ums_client 套件未安裝")
        return UmsApiClient(base_url=base_url, api_key=self.api_key, timeout=to)

    def _call_with_failover(self, method_name, *args, **kwargs):
        num_urls = len(self.base_urls)
        start_idx = self.active_index
        errors = []

        for attempt in range(num_urls):
            current_idx = (start_idx + attempt) % num_urls
            url = self.base_urls[current_idx]

            try:
                client = self._get_client_for_url(url)
                method = getattr(client, method_name)
                result = method(*args, **kwargs)

                if current_idx != self.active_index:
                    logger.info(
                        f"[UMS Failover] Switched active endpoint from [{self.active_index}] "
                        f"{self.base_urls[self.active_index]} to [{current_idx}] {url}"
                    )
                    self.active_index = current_idx

                return result
            except Exception as e:
                logger.warning(
                    f"[UMS Failover] Endpoint [{current_idx}] {url} failed on {method_name}: {e}. "
                    f"Trying next endpoint..."
                )
                errors.append(f"[{url}]: {e}")

        raise RuntimeError(
            f"所有 UMS 端點皆連線失敗 ({num_urls} 個端點): " + "; ".join(errors)
        )

    def fetch_my_models(self):
        """依序嘗試端點取得所有可用模型清單。"""
        return self._call_with_failover("fetch_my_models")

    def get_chunk_urls(self, version_id: int):
        """依序嘗試端點取得指定版本的 chunk URL 清單。"""
        return self._call_with_failover("get_chunk_urls", version_id)

    def download_version(self, version_id: int, dest_dir: Path, progress_cb=None):
        """依序嘗試端點下載並解壓縮模型檔案。"""
        return self._call_with_failover(
            "download_version",
            version_id,
            dest_dir=dest_dir,
            progress_cb=progress_cb
        )

    def test_endpoints(self, timeout=None):
        """逐一測試所有配置端點之連線狀況與模型數量。"""
        results = []
        to = timeout if timeout is not None else self.timeout
        for u in self.base_urls:
            try:
                client = self._get_client_for_url(u, timeout=to)
                models = client.fetch_my_models()
                results.append({
                    "url": u,
                    "status": "ok",
                    "models_count": len(models),
                    "message": f"連線成功，共取得 {len(models)} 個模型"
                })
            except Exception as e:
                results.append({
                    "url": u,
                    "status": "error",
                    "message": str(e),
                    "error": str(e)
                })
        return results
