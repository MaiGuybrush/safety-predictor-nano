"""同步模組：讀取 config.yaml 的 ums_model 宣告，向 UMS 平台抓模型並寫回 config.yaml。

對外唯一入口 sync_all()，開機流程（main.py）與 Web UI 手動端點（web_ui.py）
共用同一份邏輯，皆不需感知 UMS API 細節。
"""
import threading
import time
from pathlib import Path

MODELS_DIR = "models"

_last_report = {"timestamp": None, "success": [], "failed": []}
# Serializes sync_all() so a boot-time sync and a manual /sync_models POST
# can't race on the same download destination or config.yaml write.
_sync_lock = threading.Lock()


def get_last_report():
    return _last_report


def _select_version(model_info, version):
    if version == "latest":
        for v in model_info.versions:
            if v.status == "Active":
                return v
        raise RuntimeError(f"模型 {model_info.model_name} 沒有 Active 版本")
    for v in model_info.versions:
        if v.version_number == version:
            return v
    raise RuntimeError(f"模型 {model_info.model_name} 找不到版本 {version}")


def _land_artifact(downloaded_path, model_name):
    """依 Artifact 格式判斷規則落地成 InferenceEngine 認得的路徑。

    智慧優先順序：
    1. 若為資料夾：
       a. 搜尋 ONNX (*.onnx, 如 best.onnx) -> 回傳具體檔案路徑 (CPU/Edge 效能最佳)
       b. 搜尋 PyTorch (*.pt, 如 best.pt) -> 回傳具體檔案路徑
       c. 搜尋 NCNN 目錄 (含 model.ncnn.param / *.ncnn.bin) -> 回傳資料夾路徑
       d. 搜尋 model.bin -> 更名為 <model_name>.pt 並回傳
       e. fallback -> 回傳資料夾路徑
    2. 若為單一檔案：
       a. 若副檔名為 .pt 或 .onnx -> 原樣回傳
       b. 其他副檔名（如 model.bin）-> 更名為 <model_name>.pt 並回傳
    """
    path = Path(downloaded_path)
    if path.is_dir():
        # 1. Check for ONNX
        onnx_files = sorted(path.glob("*.onnx"))
        if onnx_files:
            for f in onnx_files:
                if f.name.lower() == "best.onnx":
                    return str(f)
            return str(onnx_files[0])

        # 2. Check for PyTorch (.pt)
        pt_files = sorted(path.glob("*.pt"))
        if pt_files:
            for f in pt_files:
                if f.name.lower() == "best.pt":
                    return str(f)
            return str(pt_files[0])

        # 3. Check for NCNN
        if (path / "model.ncnn.param").exists() or list(path.glob("*.ncnn.param")) or list(path.glob("*.ncnn.bin")):
            return str(path)

        # 4. Check for model.bin inside folder
        bin_file = path / "model.bin"
        if bin_file.exists():
            renamed = path / f"{model_name}.pt"
            bin_file.replace(renamed)
            return str(renamed)

        return str(path)

    if path.suffix.lower() in (".pt", ".onnx"):
        return str(path)

    renamed = path.with_name(f"{model_name}.pt")
    path.replace(renamed)
    return str(renamed)


def sync_all(config_manager, client=None):
    """解析 config_manager 目前的 ums_model 宣告，抓模型並寫回。

    永不拋例外中止呼叫端；單一目標失敗只記錄在回傳的 report["failed"] 裡，
    其餘目標與既有 model_path/streams[].model 不受影響。

    同一時間只允許一個 sync_all() 執行（_sync_lock），避免開機同步與手動
    /sync_models 端點並發時互相覆蓋下載檔案或 config.yaml 寫入。
    """
    global _last_report
    with _sync_lock:
        report = _sync_all_locked(config_manager, client)
        _last_report = report
        return report


def _sync_all_locked(config_manager, client):
    targets = config_manager.get_ums_targets()
    report = {"timestamp": time.time(), "success": [], "failed": []}

    if not targets:
        return report

    if client is None:
        try:
            import os
            from ums_client import UmsApiClient
            base_url = os.environ.get("UMS_BASE_URL") or config_manager.get("ums_base_url") or "http://tncimweb.cminl.oa/umsapiproxy/fab4ums"
            api_key = os.environ.get("UMS_API_KEY") or config_manager.get("ums_api_key")
            if api_key:
                client = UmsApiClient(api_key=api_key, base_url=base_url)
            else:
                client = UmsApiClient.from_env()
        except Exception as e:
            for t in targets:
                report["failed"].append({"key": t["key"], "name": t["name"], "version": t["version"], "error": str(e)})
            return report

    models_by_name = None
    fetch_error = None
    downloaded = {}
    updates = {}

    for target in targets:
        key, name, version = target["key"], target["name"], target["version"]
        cache_key = (name, version)
        try:
            if cache_key in downloaded:
                path = downloaded[cache_key]
            else:
                if models_by_name is None and fetch_error is None:
                    try:
                        models_by_name = {m.model_name: m for m in client.fetch_my_models()}
                    except Exception as e:
                        fetch_error = e
                if fetch_error is not None:
                    raise fetch_error
                model_info = models_by_name.get(name)
                if model_info is None:
                    raise RuntimeError(f"UMS 平台找不到模型 {name}")
                version_info = _select_version(model_info, version)
                dest_dir = Path(MODELS_DIR) / name / f"v{version_info.version_number}"
                downloaded_path = client.download_version(version_info.version_id, dest_dir=dest_dir)
                path = _land_artifact(downloaded_path, name)
                downloaded[cache_key] = path
            updates[key] = path
            report["success"].append({"key": key, "name": name, "version": version, "path": path})
        except Exception as e:
            report["failed"].append({"key": key, "name": name, "version": version, "error": str(e)})

    if updates:
        config_manager.update_model_paths(updates)

    return report
