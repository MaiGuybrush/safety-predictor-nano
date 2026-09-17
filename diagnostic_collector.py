import os
import sys
import copy
import json
import re
import socket
import platform
import zipfile
import traceback
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

try:
    import yaml
except ImportError:
    yaml = None

import ums_config

# URL 帳號密碼遮蔽正則 (支援密碼含特殊字元，鎖定 host 前之最後一個 @)
_AUTH_URL_RE = re.compile(r"(://[^:\s/@]+:)(.*?)(@(?=[^@\s/]+(?:[:/?]|$)))")

# 預設日誌單檔截斷上限 (預設 20MB)
DEFAULT_MAX_LOG_BYTES = 20 * 1024 * 1024


def mask_sensitive_url(url: str) -> str:
    """遮蔽 URL 中之敏感帳號密碼。"""
    if not isinstance(url, str):
        return url
    return _AUTH_URL_RE.sub(r"\1******\3", url)


def mask_api_key(key: str) -> str:
    """遮蔽 API Key，僅保留前後微量字元以利除錯。"""
    if not isinstance(key, str) or not key.strip():
        return ""
    stripped = key.strip()
    if len(stripped) <= 8:
        return "******"
    return f"{stripped[:4]}***[MASKED]***{stripped[-4:]}"


def sanitize_config(config_dict: dict) -> dict:
    """對配置字典中的敏感欄位進行深度脫敏，回傳脫敏後的字典複本。"""
    if not isinstance(config_dict, dict):
        return {}

    sanitized = copy.deepcopy(config_dict)

    def _mask_obj_recursively(obj):
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                masked_k = mask_sensitive_url(str(k)) if isinstance(k, str) else k
                new_dict[masked_k] = _mask_obj_recursively(v)
            return new_dict
        elif isinstance(obj, list):
            return [_mask_obj_recursively(item) for item in obj]
        elif isinstance(obj, str):
            return mask_sensitive_url(obj)
        return obj

    # 1. 遮蔽 UMS API Key
    if "ums_api_key" in sanitized and sanitized["ums_api_key"]:
        sanitized["ums_api_key"] = mask_api_key(str(sanitized["ums_api_key"]))

    # 2. 深度遍歷遮蔽所有欄位之敏感 URL (包含 streams 中之 url, rtsp_url, external_states 等)
    sanitized = _mask_obj_recursively(sanitized)

    return sanitized


def collect_system_info() -> dict:
    """收集本機執行環境與硬體狀態摘要。"""
    info = {
        "timestamp": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "python_version": sys.version,
        "ipv4_addresses": ums_config.get_device_ipv4_addresses(),
    }

    if psutil is not None:
        try:
            info["cpu"] = {
                "count_logical": psutil.cpu_count(logical=True),
                "count_physical": psutil.cpu_count(logical=False),
                "percent": psutil.cpu_percent(interval=None),
            }
        except Exception as e:
            info["cpu"] = {"error": str(e)}

        try:
            mem = psutil.virtual_memory()
            info["memory"] = {
                "total_mb": round(mem.total / (1024 * 1024), 2),
                "available_mb": round(mem.available / (1024 * 1024), 2),
                "percent": mem.percent,
            }
        except Exception as e:
            info["memory"] = {"error": str(e)}

        try:
            disk = psutil.disk_usage(".")
            info["disk"] = {
                "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "percent": disk.percent,
            }
        except Exception as e:
            info["disk"] = {"error": str(e)}
    else:
        info["psutil"] = "not_available"

    return info


def install_crash_handler(log_dir: str = "logs"):
    """於 sys.excepthook 註冊全域崩潰處理常式，將未攔截之 Fatal Exception 寫入 logs/crash.log。"""
    prev_excepthook = sys.excepthook

    def crash_excepthook(exc_type, exc_value, exc_traceback):
        try:
            os.makedirs(log_dir, exist_ok=True)
            crash_file = os.path.join(log_dir, "crash.log")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tb_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

            with open(crash_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 70}\n")
                f.write(f"[FATAL CRASH] Timestamp: {now_str}\n")
                f.write(f"Exception Type: {exc_type.__name__}\n")
                f.write(f"Exception Value: {exc_value}\n")
                f.write("Traceback:\n")
                f.write(tb_lines)
                f.write(f"{'=' * 70}\n")
        except Exception as handler_err:
            print(f"[CrashHandler Error] Failed to write crash log: {handler_err}", file=sys.stderr)

        if prev_excepthook is not None:
            prev_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = crash_excepthook


def _read_file_with_limit(file_path: str, max_bytes: int = DEFAULT_MAX_LOG_BYTES) -> bytes:
    """讀取檔案內容，若超過 max_bytes 則截取末端內容並加上截斷警告標註。"""
    size = os.path.getsize(file_path)
    if size <= max_bytes:
        with open(file_path, "rb") as f:
            return f.read()

    # 截取尾端
    with open(file_path, "rb") as f:
        f.seek(size - max_bytes)
        chunk = f.read()

    # 尋找第一個換行以保持行結構完整
    first_nl = chunk.find(b"\n")
    if first_nl != -1 and first_nl < 4096:
        chunk = chunk[first_nl + 1:]

    warning = (
        f"[... TRUNCATED: Original file size was {round(size / (1024 * 1024), 2)} MB. "
        f"Only last {round(max_bytes / (1024 * 1024), 2)} MB is retained in this bundle ...]\n"
    ).encode("utf-8")

    return warning + chunk


def collect_diagnostic_bundle(
    output_dir: str = "issue-bundles",
    logs_dir: str = "logs",
    config_path: str = "config.yaml",
    max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
    report_id: str = None,
) -> dict:
    """收集系統日誌、脫敏配置與系統資訊，壓縮成標準診斷 ZIP 封包。

    回傳字典：
    {
        "zip_path": 封包路徑,
        "zip_filename": 檔名 (例如 diagnostic_20260915_153000.zip),
        "size_bytes": 封包位元組大小,
        "report_id": 報告代碼 (例如 260915153000_err),
        "sysinfo": 系統狀態摘要字典,
        "files_included": 納入封包之檔案名稱清單,
    }
    """
    now = datetime.now()
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    if not report_id:
        report_id = f"{now.strftime('%y%m%d%H%M%S')}_err"

    os.makedirs(output_dir, exist_ok=True)
    zip_filename = f"diagnostic_{ts_str}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    files_included = []
    sysinfo = collect_system_info()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. 寫入系統環境資訊 sysinfo.json
        sysinfo_bytes = json.dumps(sysinfo, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("sysinfo.json", sysinfo_bytes)
        files_included.append("sysinfo.json")

        # 2. 寫入脫敏後之 config.yaml
        if os.path.isfile(config_path):
            try:
                if yaml is not None:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg_obj = yaml.safe_load(f)
                    sanitized_cfg = sanitize_config(cfg_obj)
                    cfg_bytes = yaml.safe_dump(sanitized_cfg, allow_unicode=True, sort_keys=False).encode("utf-8")
                else:
                    with open(config_path, "r", encoding="utf-8") as f:
                        raw_lines = f.readlines()
                    masked_lines = [mask_sensitive_url(line) for line in raw_lines]
                    cfg_bytes = "".join(masked_lines).encode("utf-8")

                zf.writestr("config.yaml", cfg_bytes)
                files_included.append("config.yaml")
            except Exception as e:
                err_msg = f"# Error sanitizing config.yaml: {e}\n".encode("utf-8")
                zf.writestr("config.yaml", err_msg)
                files_included.append("config.yaml (error)")

        # 3. 收集日誌檔案 (包含 crash.log, system.log, performance.log, detections.log)
        target_log_names = ["crash.log", "system.log", "performance.log", "detections.log"]
        if os.path.isdir(logs_dir):
            for log_name in target_log_names:
                full_log_path = os.path.join(logs_dir, log_name)
                if os.path.isfile(full_log_path):
                    try:
                        content_bytes = _read_file_with_limit(full_log_path, max_bytes=max_log_bytes)
                        archive_name = f"logs/{log_name}"
                        zf.writestr(archive_name, content_bytes)
                        files_included.append(archive_name)
                    except Exception as e:
                        print(f"[DiagnosticCollector] Warning reading {full_log_path}: {e}", file=sys.stderr)

    size_bytes = os.path.getsize(zip_path)

    return {
        "zip_path": os.path.abspath(zip_path),
        "zip_filename": zip_filename,
        "size_bytes": size_bytes,
        "report_id": report_id,
        "sysinfo": sysinfo,
        "files_included": files_included,
    }
