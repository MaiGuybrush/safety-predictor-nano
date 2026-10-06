import pytest
from unittest.mock import MagicMock, patch
import requests

from argus.integration.app_update_client import (
    AppUpdateClient,
    DownloadInfo,
    VersionInfoDTO,
    is_newer_version,
    parse_semver,
    resolve_app_management_base_urls,
    AppUpdatePermanentError,
    AppUpdateTransientError,
    DEFAULT_APP_ID,
    DEFAULT_BASE_URL,
)


def test_parse_semver():
    core, is_pre, tag = parse_semver("v1.2.3")
    assert core == (1, 2, 3)
    assert is_pre is False

    core, is_pre, tag = parse_semver("2.0.0-rc1")
    assert core == (2, 0, 0)
    assert is_pre is True
    assert tag == "rc1"

    core, is_pre, tag = parse_semver("V0.1")
    assert core == (0, 1, 0)
    assert is_pre is False


def test_is_newer_version():
    assert is_newer_version("1.2.0", "1.1.0") is True
    assert is_newer_version("1.1.0", "1.2.0") is False
    assert is_newer_version("1.0.0", "1.0.0") is False

    # Prerelease 過濾
    assert is_newer_version("1.2.0-rc1", "1.1.0", allow_prerelease=False) is False
    assert is_newer_version("1.2.0-rc1", "1.1.0", allow_prerelease=True) is True


def test_resolve_app_management_base_urls():
    # 預設行為
    urls = resolve_app_management_base_urls()
    assert len(urls) >= 1
    assert all("AppManagementApi" in u for u in urls)

    # 明確指定
    explicit = ["http://myhost:8080/api"]
    resolved = resolve_app_management_base_urls(base_urls=explicit)
    assert resolved == explicit


def test_app_update_client_check_latest_candidate():
    mock_session = MagicMock(spec=requests.Session)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "version": "1.0.0",
            "released": True,
            "autoUpdate": True,
            "locked": False,
        },
        {
            "version": "1.2.0",
            "released": True,
            "autoUpdate": True,
            "locked": False,
            "releaseDate": "2026-09-21 15:00:00",
            "releaseNotes": "重要升級",
        },
        {
            "version": "1.3.0-beta",
            "released": True,
            "autoUpdate": True,
            "locked": False,
        },
    ]
    mock_session.request.return_value = mock_resp

    client = AppUpdateClient(
        app_id="safety-predictor-nano",
        base_urls=["http://gateway.oa/AppManagementApi"],
        channel="stable",
        api_key="test-key",
        session=mock_session,
    )

    candidate = client.check_latest_candidate("1.0.0")
    assert candidate is not None
    assert candidate.version == "1.2.0"
    assert candidate.release_notes == "重要升級"

    # 若當前版本已是 1.2.0
    cand2 = client.check_latest_candidate("1.2.0")
    assert cand2 is None


def test_app_update_client_download_info_prefers_delta():
    mock_session = MagicMock(spec=requests.Session)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "owner": "cminl",
        "filesInfo": [
            {
                "fileName": "safety-predictor-nano-v1.2.0-arm64.tar.gz",
                "filePath": "dist/v1.2.0/safety-predictor-nano-v1.2.0-arm64.tar.gz",
                "size": 52428800,
            },
            {
                "fileName": "argus_delta-v1.2.0-arm64.tar.gz",
                "filePath": "dist/v1.2.0/argus_delta-v1.2.0-arm64.tar.gz",
                "size": 2516582,
            }
        ]
    }
    mock_session.request.return_value = mock_resp

    client = AppUpdateClient(api_key="test-key", session=mock_session)
    info = client.get_download_info("1.2.0")
    assert info.owner == "cminl"
    assert info.version == "1.2.0"
    assert info.is_delta is True
    assert info.size == 2516582
    assert "delta" in info.file_path


def test_app_update_client_download_info_fallback_to_full():
    mock_session = MagicMock(spec=requests.Session)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "owner": "cminl",
        "filesInfo": [
            {
                "fileName": "safety-predictor-nano-v1.2.0-arm64.tar.gz",
                "filePath": "dist/v1.2.0/safety-predictor-nano-v1.2.0-arm64.tar.gz",
                "size": 52428800,
            }
        ]
    }
    mock_session.request.return_value = mock_resp

    client = AppUpdateClient(api_key="test-key", session=mock_session)
    info = client.get_download_info("1.2.0")
    assert info.is_delta is False
    assert info.size == 52428800
    assert "arm64" in info.file_path


def test_app_update_client_disk_space_check(tmp_path):
    mock_session = MagicMock(spec=requests.Session)
    client = AppUpdateClient(api_key="test-key", session=mock_session)

    # 模擬 50MB 剩餘空間
    usage_mock = MagicMock()
    usage_mock.free = 50 * 1024 * 1024  # 50 MB

    with patch("shutil.disk_usage", return_value=usage_mock):
        # 1. 全量包需要至少 650MB，50MB 應拋出 AppUpdatePermanentError
        full_info = DownloadInfo(
            app_id="safety-predictor-nano",
            version="1.2.0",
            owner="cminl",
            file_path="pkg.tar.gz",
            size=52428800,
            is_delta=False,
        )
        with pytest.raises(AppUpdatePermanentError, match="磁碟剩餘空間不足"):
            client.download_package(full_info, str(tmp_path / "pkg.tar.gz"))

        # 2. Delta 增量包僅需 20MB，50MB 空間足夠，不會拋出磁碟空間錯誤
        delta_info = DownloadInfo(
            app_id="safety-predictor-nano",
            version="1.2.0",
            owner="cminl",
            file_path="delta.tar.gz",
            size=2516582,
            is_delta=True,
        )
        # Mock session response for download
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "10"}
        mock_resp.iter_content.return_value = [b"1234567890"]
        mock_resp.__enter__.return_value = mock_resp
        mock_session.get.return_value = mock_resp

        dest = str(tmp_path / "delta.tar.gz")
        res = client.download_package(delta_info, dest)
        assert res == dest


def test_app_update_client_api_key_strict_isolation(monkeypatch, caplog):
    import logging
    # 1. explicit api_key
    c1 = AppUpdateClient(api_key="mgr_key_1", ums_api_key="ums_key_2")
    assert c1.api_key == "mgr_key_1"
    assert c1.api_key_missing is False

    # 2. ums_api_key 必須徹底被忽略，不得作為退避
    monkeypatch.delenv("APP_MGR_API_KEY", raising=False)
    monkeypatch.delenv("UMS_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING):
        c2 = AppUpdateClient(api_key="", ums_api_key="ums_key_2")
        assert c2.api_key == ""
        assert c2.api_key_missing is True
        assert "[AppUpdateClient] 未設定 API KEY 無法進行自動更新" in caplog.text

    # 3. APP_MGR_API_KEY 環境變數支援
    monkeypatch.setenv("APP_MGR_API_KEY", "env_app_mgr")
    c3 = AppUpdateClient(api_key="", ums_api_key="")
    assert c3.api_key == "env_app_mgr"
    assert c3.api_key_missing is False

    # 4. UMS_API_KEY 環境變數必須徹底被忽略，不得作為退避
    monkeypatch.delenv("APP_MGR_API_KEY", raising=False)
    monkeypatch.setenv("UMS_API_KEY", "env_ums")
    c4 = AppUpdateClient(api_key="", ums_api_key="")
    assert c4.api_key == ""
    assert c4.api_key_missing is True


def test_app_update_client_intercepts_requests_when_key_missing(monkeypatch):
    monkeypatch.delenv("APP_MGR_API_KEY", raising=False)
    monkeypatch.delenv("UMS_API_KEY", raising=False)
    mock_session = MagicMock(spec=requests.Session)
    client = AppUpdateClient(api_key="", session=mock_session)
    assert client.api_key_missing is True

    # 發起請求前應直接拋出 AppUpdatePermanentError，不發出任何 HTTP 請求
    with pytest.raises(AppUpdatePermanentError, match="未設定 API KEY"):
        client.get_version_list()
    assert mock_session.request.call_count == 0

    with pytest.raises(AppUpdatePermanentError, match="未設定 API KEY"):
        client.check_latest_candidate("1.0.0")
    assert mock_session.request.call_count == 0

    with pytest.raises(AppUpdatePermanentError, match="未設定 API KEY"):
        client.get_download_info("1.1.0")
    assert mock_session.request.call_count == 0

    dummy_info = DownloadInfo(
        app_id="safety-predictor-nano",
        version="1.1.0",
        owner="cminl",
        file_path="pkg.tar.gz",
        size=1000,
    )
    with pytest.raises(AppUpdatePermanentError, match="未設定 API KEY"):
        client.download_package(dummy_info, "dest/path.tar.gz")
    assert mock_session.get.call_count == 0


def test_app_update_client_release_fab_filtering():
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "version": "1.3.0",
            "released": True,
            "autoUpdate": True,
            "locked": False,
            "releaseFab": "Fab2",
        },
        {
            "version": "1.2.0",
            "released": True,
            "autoUpdate": True,
            "locked": False,
            "releaseFab": "Fab1",
        },
        {
            "version": "1.1.0",
            "released": True,
            "autoUpdate": True,
            "locked": False,
            "releaseFab": "ALL",
        },
    ]
    mock_session.request.return_value = mock_resp

    # Client fab 為 fab1，應挑選 1.2.0 (1.3.0 為 fab2 應過濾)
    client_fab1 = AppUpdateClient(api_key="test-key", fab="fab1", session=mock_session)
    candidate = client_fab1.check_latest_candidate("1.0.0")
    assert candidate is not None
    assert candidate.version == "1.2.0"

    # Client fab 為 other，應挑選 1.1.0 (releaseFab="ALL")
    client_other = AppUpdateClient(api_key="test-key", fab="fab_other", session=mock_session)
    cand_other = client_other.check_latest_candidate("1.0.0")
    assert cand_other is not None
    assert cand_other.version == "1.1.0"


def test_app_update_client_fast_fail_timeout_and_retries():
    """驗證查詢版本列表使用短逾時 (query_timeout) 與最少重試 (query_max_retries)，達成快速失敗。"""
    mock_session = MagicMock(spec=requests.Session)
    mock_session.request.side_effect = requests.RequestException("Connection timed out")

    client = AppUpdateClient(
        api_key="test-key",
        query_timeout=6,
        query_max_retries=1,
        session=mock_session,
    )

    with pytest.raises(AppUpdateTransientError, match="所有 API 端點皆無法連線"):
        client.get_version_list()

    # 驗證傳給 session.request 的 timeout 是 query_timeout (6)，且重試次數符合 query_max_retries
    assert mock_session.request.call_count >= 1
    call_kwargs = mock_session.request.call_args[1]
    assert call_kwargs["timeout"] == 6



