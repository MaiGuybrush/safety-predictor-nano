import os
import sys
import json
import socket
import logging

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)

DEFAULT_UMS_API_CONFIG = {
    "api.oa": [
        "http://tncimweb1.cminl.oa/umsapiproxy/fab4ums",
        "http://tncimweb2.cminl.oa/umsapiproxy/fab4ums"
    ],
    "domainDefine": {}
}


def load_ums_api_config(config_dir=None, file_path=None):
    """讀取 UMS API 集中組態檔 (ums-api-config.json)。
    優先順序：
    1. 明確傳入的 file_path（若存在）
    2. 當前工作目錄下的 ums-api-config.json
    3. 指定 config_dir 下的 ums-api-config.json
    4. PyInstaller 凍結環境 (_MEIPASS) 下的 ums-api-config.json
    5. 程式碼模組同層的 ums-api-config.json
    6. Fallback 至內建最小組態 (DEFAULT_UMS_API_CONFIG)
    """
    candidates = []
    if file_path:
        candidates.append(os.path.abspath(file_path))

    candidates.append(os.path.join(os.getcwd(), "ums-api-config.json"))

    if config_dir:
        candidates.append(os.path.join(os.path.abspath(config_dir), "ums-api-config.json"))

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "ums-api-config.json"))

    module_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(module_dir, "ums-api-config.json"))

    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                logger.warning(f"[UmsConfig] 讀取組態檔 {path} 失敗: {e}")

    return dict(DEFAULT_UMS_API_CONFIG)


def get_device_ipv4_addresses():
    """列舉本機所有非 Loopback、有效且運作中的 IPv4 介面位址。"""
    addresses = []
    if psutil is not None:
        try:
            net_stats = psutil.net_if_stats()
            net_addrs = psutil.net_if_addrs()
            for iface, addrs in net_addrs.items():
                stats = net_stats.get(iface)
                if stats is not None and not stats.isup:
                    continue
                for snic in addrs:
                    if snic.family == socket.AF_INET:
                        ip = snic.address
                        if ip and not ip.startswith("127.") and ip != "0.0.0.0":
                            if ip not in addresses:
                                addresses.append(ip)
        except Exception as e:
            logger.warning(f"[UmsConfig] psutil 掃描網卡失敗: {e}")

    if not addresses:
        try:
            hostname = socket.gethostname()
            _, _, ips = socket.gethostbyname_ex(hostname)
            for ip in ips:
                if ip and not ip.startswith("127.") and ip != "0.0.0.0":
                    if ip not in addresses:
                        addresses.append(ip)
        except Exception as e:
            logger.warning(f"[UmsConfig] socket 掃描網卡失敗: {e}")

    return addresses


def detect_fab_from_ips(ip_addresses, domain_define=None, ums_api_config=None):
    """根據 IPv4 位址清單與 domainDefine 規則比對廠區。
    採嚴格網段前綴比對（prefix + '.'，防止 10.2 誤匹配 10.26）。
    多網卡命中取首個，皆未命中則預設為 'oa'。
    """
    if not ip_addresses:
        return "oa"

    if domain_define is None:
        if ums_api_config is None:
            ums_api_config = load_ums_api_config()
        domain_define = ums_api_config.get("domainDefine", {})

    if not isinstance(domain_define, dict):
        return "oa"

    for ip in ip_addresses:
        ip = str(ip).strip()
        if not ip:
            continue
        for fab, prefixes in domain_define.items():
            if not isinstance(prefixes, list):
                continue
            for prefix in prefixes:
                prefix = str(prefix).strip()
                if not prefix:
                    continue
                norm_prefix = prefix if prefix.endswith(".") else (prefix + ".")
                if ip.startswith(norm_prefix):
                    return str(fab).strip().lower()

    return "oa"


def get_all_fabs_and_endpoints(ums_api_config=None):
    """從 UMS API 組態解析所有可用廠區及其對應的主備端點清單。
    回傳字典格式: { "oa": [...], "fab1": [...], ... }
    """
    if ums_api_config is None:
        ums_api_config = load_ums_api_config()

    fabs_map = {}
    for key, val in ums_api_config.items():
        if key.startswith("api.") and isinstance(val, list):
            fab_name = key[4:].strip().lower()
            endpoints = [str(u).strip() for u in val if str(u).strip()]
            if endpoints:
                fabs_map[fab_name] = endpoints

    if "oa" not in fabs_map:
        fabs_map["oa"] = list(DEFAULT_UMS_API_CONFIG["api.oa"])

    return fabs_map


def get_ums_endpoints_for_fab(fab, ums_api_config=None):
    """根據廠區代碼取得主備端點 URL 列表。若查無該廠區則 fallback 至 'oa'。"""
    fabs_map = get_all_fabs_and_endpoints(ums_api_config)
    fab_clean = str(fab or "oa").strip().lower()
    if fab_clean.startswith("api."):
        fab_clean = fab_clean[4:]

    if fab_clean in fabs_map:
        return list(fabs_map[fab_clean])

    if "oa" in fabs_map:
        return list(fabs_map["oa"])

    return list(DEFAULT_UMS_API_CONFIG["api.oa"])


FAB_DISPLAY_NAMES = {
    "oa": "OA (辦公網段)",
    "fab1": "FAB 1",
    "fab2": "FAB 2",
    "fab3": "FAB 3",
    "fab4": "FAB 4",
    "fab5": "FAB 5",
    "fab6": "FAB 6",
    "fab7": "FAB 7",
    "fab8": "FAB 8",
    "fabt1": "FAB T1",
    "fabt2": "FAB T2",
    "fabt3": "FAB T3",
    "fabt6": "FAB T6",
    "fabts1": "FAB TS1",
    "lcm": "LCM",
}


def format_fab_display_name(fab):
    """格式化廠區代碼為友善顯示名稱。"""
    fab_clean = str(fab or "").strip().lower()
    if fab_clean.startswith("api."):
        fab_clean = fab_clean[4:]
    return FAB_DISPLAY_NAMES.get(fab_clean, fab_clean.upper())
