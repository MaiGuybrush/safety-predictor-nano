import os
import sys
import json
import logging
from urllib.parse import urlsplit
from typing import List, Dict, Any, Optional

import requests

import ums_config

logger = logging.getLogger("issue_service_client")

# 預設 Gitea 專案設定
DEFAULT_REPO_OWNER = "guy.mai"
DEFAULT_REPO_NAME = "safety-predictor-nano"
DEFAULT_TIMEOUT = 30
DEFAULT_GITEA_TIMEOUT = 15

# 預設 Fallback API Gateway 主機
DEFAULT_GATEWAY_HOSTS = [
    "http://tncimweb1.cminl.oa",
    "http://tncimweb2.cminl.oa",
]


class IssueServiceError(Exception):
    """診斷回報服務基礎例外。"""
    pass


class FileUploadError(IssueServiceError):
    """診斷封包上傳至 FileServiceCore 失敗。"""
    pass


class GiteaIssueError(IssueServiceError):
    """透過 Gateway 建立 Gitea Issue 失敗。"""
    pass


class GatewayConnectionError(IssueServiceError):
    """所有 API Gateway 候選主機皆無法連線。"""
    pass


def resolve_gateway_hosts(
    ums_api_config: Optional[dict] = None,
    ip_addresses: Optional[List[str]] = None,
) -> List[str]:
    """根據本機 IP 與 ums-api-config.json 動態解析可用的 API Gateway 主機清單。

    回傳範例：['http://tncimweb1.cminl.oa', 'http://tncimweb2.cminl.oa']
    若解析失敗或無可用主機，則 fallback 至預設主機。
    """
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
        except Exception as e:
            logger.warning(f"[IssueServiceClient] 解析端點主機失敗 {ep}: {e}")

    if not hosts:
        hosts = list(DEFAULT_GATEWAY_HOSTS)

    return hosts


class IssueServiceClient:
    """API Gateway 診斷封包上傳與 Gitea Issue 自動建立客戶端。

    支援透明容錯切換（Failover），依序嘗試候選 Gateway 主機。
    """

    def __init__(
        self,
        gateway_hosts: Optional[List[str]] = None,
        repo_owner: str = DEFAULT_REPO_OWNER,
        repo_name: str = DEFAULT_REPO_NAME,
        timeout: int = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ):
        if gateway_hosts is None:
            self.gateway_hosts = resolve_gateway_hosts()
        elif isinstance(gateway_hosts, str):
            self.gateway_hosts = [h.strip().rstrip("/") for h in gateway_hosts.split(",") if h.strip()]
        else:
            self.gateway_hosts = [str(h).strip().rstrip("/") for h in gateway_hosts if str(h).strip()]

        if not self.gateway_hosts:
            self.gateway_hosts = list(DEFAULT_GATEWAY_HOSTS)

        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.timeout = timeout
        self.active_index = 0
        self.session = session or requests.Session()

    def _ordered_hosts(self) -> List[str]:
        """從當前 active_index 依序嘗試所有主機。"""
        n = len(self.gateway_hosts)
        return [self.gateway_hosts[(self.active_index + i) % n] for i in range(n)]

    def upload_diagnostic_file(
        self,
        zip_path: str,
        report_id: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """將本機 ZIP 診斷封包上傳至 API Gateway 的 FileServiceCore。

        參數：
        - zip_path: 本機 ZIP 檔案路徑
        - report_id: 報告唯一識別代碼（例如 260915153000_err）
        - timeout: 請求逾時秒數（預設使用客戶端 timeout）

        回傳字典：
        {
            "status": "success",
            "host": "http://...",
            "download_url": "http://.../FileServiceCore/File?...",
            "report_id": report_id,
            "zip_filename": "...",
            "response": {...}
        }
        """
        if not os.path.isfile(zip_path):
            raise FileNotFoundError(f"診斷封包檔案不存在: {zip_path}")

        zip_filename = os.path.basename(zip_path)
        req_timeout = timeout if timeout is not None else self.timeout

        hosts = self._ordered_hosts()
        last_err = None

        for host in hosts:
            upload_url = (
                f"{host}/FileServiceCore/File"
                f"?srcName=ErrorReport&filePath=.%2Fsafety-nano%2F{report_id}&flatten=false&overwrite=true"
            )
            download_url = (
                f"{host}/FileServiceCore/File"
                f"?srcName=ErrorReport&filePath=.%2Fsafety-nano%2F{report_id}%2F{zip_filename}"
            )

            try:
                logger.info(f"[IssueServiceClient] 嘗試上傳診斷封包至 {host}...")
                with open(zip_path, "rb") as f:
                    files = {
                        "files": (zip_filename, f, "application/x-zip-compressed")
                    }
                    headers = {"accept": "*/*"}
                    resp = self.session.post(
                        upload_url,
                        files=files,
                        headers=headers,
                        timeout=req_timeout,
                    )

                if resp.status_code in (200, 201):
                    try:
                        resp_data = resp.json()
                    except Exception:
                        resp_data = {"raw": resp.text}

                    # 檢查 FileServiceCore 回傳結構中的 error 欄位
                    if isinstance(resp_data, dict) and resp_data.get("error"):
                        err_detail = resp_data.get("error")
                        logger.warning(f"[IssueServiceClient] 上傳回應中包含錯誤: {err_detail}")
                        raise FileUploadError(f"檔案服務回應錯誤: {err_detail}")

                    # 記憶目前成功的 host index
                    self.active_index = self.gateway_hosts.index(host)
                    logger.info(f"[IssueServiceClient] 診斷封包上傳成功: {download_url}")
                    return {
                        "status": "success",
                        "host": host,
                        "download_url": download_url,
                        "report_id": report_id,
                        "zip_filename": zip_filename,
                        "response": resp_data,
                    }
                else:
                    logger.warning(
                        f"[IssueServiceClient] 上傳至 {host} 回應狀態碼異常: "
                        f"{resp.status_code}, 內容: {resp.text[:200]}"
                    )
                    last_err = FileUploadError(
                        f"上傳 HTTP 狀態碼異常 ({resp.status_code}): {resp.text[:200]}"
                    )
            except Exception as e:
                logger.warning(f"[IssueServiceClient] 連線主機 {host} 上傳失敗: {e}")
                last_err = e

        raise GatewayConnectionError(
            f"所有 Gateway 主機皆上傳失敗: {self.gateway_hosts}. 最後錯誤: {last_err}"
        ) from last_err

    def create_gitea_issue(
        self,
        title: str,
        description: str,
        download_url: str,
        sysinfo: Optional[dict] = None,
        report_id: Optional[str] = None,
        zip_filename: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """透過 API Gateway 呼叫 Gitea REST API 建立 Issue。

        API Gateway 會自動附加 Gitea 權限 Token，客戶端不需提供。

        回傳字典：
        {
            "status": "success",
            "issue_number": 45,
            "issue_url": "http://.../guy.mai/safety-predictor-nano/issues/45",
            "title": "[使用者回報] ...",
            "host": "http://...",
            "raw_response": {...}
        }
        """
        req_timeout = timeout if timeout is not None else DEFAULT_GITEA_TIMEOUT

        # 組裝結構化標題
        clean_title = (title or "未命名問題回報").strip()
        if not clean_title.startswith("["):
            issue_title = f"[使用者回報] {clean_title}"
        else:
            issue_title = clean_title

        # 組裝 Markdown 內容
        body_lines = [
            "## 問題描述",
            description.strip() if description and description.strip() else "(未提供詳細描述)",
            "",
            "## 診斷附件",
            f"- 下載連結: [點此下載診斷封包]({download_url})",
        ]
        if zip_filename:
            body_lines.append(f"- 封包檔案: `{zip_filename}`")
        if report_id:
            body_lines.append(f"- 報告識別碼: `{report_id}`")

        body_lines.extend([
            "",
            "## 系統環境摘要",
            "```json",
            json.dumps(sysinfo, indent=2, ensure_ascii=False) if sysinfo else "{}",
            "```",
        ])
        issue_body = "\n".join(body_lines)

        payload = {
            "title": issue_title,
            "body": issue_body,
        }
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        hosts = self._ordered_hosts()
        last_err = None

        for host in hosts:
            api_url = (
                f"{host}/ApiGateway/git-server/api/v1/repos/"
                f"{self.repo_owner}/{self.repo_name}/issues"
            )

            try:
                logger.warning(f"[IssueServiceClient] 嘗試向 {host} 建立 Gitea Issue... url={api_url}")
                resp = self.session.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=req_timeout,
                )

                if resp.status_code in (200, 201):
                    resp_json = resp.json()
                    self.active_index = self.gateway_hosts.index(host)

                    issue_number = resp_json.get("number")
                    issue_url = resp_json.get("html_url")
                    logger.info(
                        f"[IssueServiceClient] Gitea Issue 建立成功: #{issue_number} - {issue_url}"
                    )
                    return {
                        "status": "success",
                        "issue_number": issue_number,
                        "issue_url": issue_url,
                        "title": resp_json.get("title", issue_title),
                        "host": host,
                        "raw_response": resp_json,
                    }
                else:
                    logger.warning(
                        f"[IssueServiceClient] 建立 Issue 至 {host} 回應失敗: "
                        f"{resp.status_code}, 內容: {resp.text[:200]}"
                    )
                    last_err = GiteaIssueError(
                        f"建立 Issue HTTP 狀態碼異常 ({resp.status_code}): {resp.text[:200]}"
                    )
            except Exception as e:
                logger.warning(f"[IssueServiceClient] 連線主機 {host} 建立 Issue 失敗: {e}")
                last_err = e

        raise GatewayConnectionError(
            f"所有 Gateway 主機皆建立 Issue 失敗: {self.gateway_hosts}. 最後錯誤: {last_err}"
        ) from last_err

    def report_diagnostic_bundle(
        self,
        title: str,
        description: str,
        zip_path: str,
        report_id: Optional[str] = None,
        sysinfo: Optional[dict] = None,
    ) -> dict:
        """一鍵完成：上傳診斷封包並建立 Gitea Issue。

        回傳整合後的 Issue 與上傳結果。
        """
        if not report_id:
            from datetime import datetime
            report_id = f"{datetime.now().strftime('%y%m%d%H%M%S')}_err"

        upload_res = self.upload_diagnostic_file(zip_path=zip_path, report_id=report_id)
        download_url = upload_res["download_url"]
        zip_filename = upload_res["zip_filename"]

        issue_res = self.create_gitea_issue(
            title=title,
            description=description,
            download_url=download_url,
            sysinfo=sysinfo,
            report_id=report_id,
            zip_filename=zip_filename,
        )

        return {
            "status": "success",
            "issue_number": issue_res["issue_number"],
            "issue_url": issue_res["issue_url"],
            "download_url": download_url,
            "report_id": report_id,
            "zip_filename": zip_filename,
            "gateway_host": upload_res["host"],
        }


# =====================================================================
# 頂層快速函式 (Top-level Helper Functions)
# =====================================================================

def upload_diagnostic_file(
    zip_path: str,
    report_id: str,
    gateway_hosts: Optional[List[str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """便捷函式：上傳診斷 ZIP 檔。"""
    client = IssueServiceClient(gateway_hosts=gateway_hosts, timeout=timeout)
    return client.upload_diagnostic_file(zip_path=zip_path, report_id=report_id)


def create_gitea_issue(
    title: str,
    description: str,
    download_url: str,
    sysinfo: Optional[dict] = None,
    report_id: Optional[str] = None,
    zip_filename: Optional[str] = None,
    gateway_hosts: Optional[List[str]] = None,
    timeout: int = DEFAULT_GITEA_TIMEOUT,
) -> dict:
    """便捷函式：建立 Gitea Issue。"""
    client = IssueServiceClient(gateway_hosts=gateway_hosts, timeout=timeout)
    return client.create_gitea_issue(
        title=title,
        description=description,
        download_url=download_url,
        sysinfo=sysinfo,
        report_id=report_id,
        zip_filename=zip_filename,
    )


def report_diagnostic_issue(
    title: str,
    description: str,
    zip_path: str,
    report_id: Optional[str] = None,
    sysinfo: Optional[dict] = None,
    gateway_hosts: Optional[List[str]] = None,
) -> dict:
    """便捷函式：一站式上傳並建立 Issue。"""
    client = IssueServiceClient(gateway_hosts=gateway_hosts)
    return client.report_diagnostic_bundle(
        title=title,
        description=description,
        zip_path=zip_path,
        report_id=report_id,
        sysinfo=sysinfo,
    )
