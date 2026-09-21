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
        session=mock_session,
    )

    candidate = client.check_latest_candidate("1.0.0")
    assert candidate is not None
    assert candidate.version == "1.2.0"
    assert candidate.release_notes == "重要升級"

    # 若當前版本已是 1.2.0
    cand2 = client.check_latest_candidate("1.2.0")
    assert cand2 is None


def test_app_update_client_download_info():
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

    client = AppUpdateClient(session=mock_session)
    info = client.get_download_info("1.2.0")
    assert info.owner == "cminl"
    assert info.version == "1.2.0"
    assert info.size == 52428800
    assert "arm64" in info.file_path
