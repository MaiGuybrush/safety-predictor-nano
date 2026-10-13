#!/usr/bin/env python3
"""scripts/probe_package.py - Argus 打包完整性探針 (Package Integrity Probe).

在 PyInstaller frozen 環境內部執行，驗證所有必要 import 與資料檔是否正確打包。

用法：
    # 打包後在樹莓派上執行（最重要的驗證場景）
    ./dist/argus_predictor/argus_predictor --probe

    # JSON 輸出模式（CI 整合）
    ./dist/argus_predictor/argus_predictor --probe --json > probe_report.json
    echo "exit: $?"

    # 開發環境直接執行（驗證本機 pip 環境）
    python scripts/probe_package.py
    python scripts/probe_package.py --json
"""

import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List


# ─────────────────────────────────────────────────────────────
# 1. 探針清單定義
# ─────────────────────────────────────────────────────────────

# 第三方套件：必須全部可 import（對應 requirements.txt）
THIRD_PARTY_IMPORTS: List[str] = [
    "cv2",
    "ultralytics",
    "flask",
    "yaml",
    "psutil",
    "requests",
    "onnx",
    "onnxruntime",
    "argus_eventlog",
    "ums_client",
]

# 選用套件：僅載入 NCNN 模型或 torchvision C++ 加速時需要；
# 缺少或缺失 C++ 算子時會自動降級至純 PyTorch NMS，不算 FAIL。
OPTIONAL_THIRD_PARTY_IMPORTS: List[str] = [
    "ncnn",
    "torchvision",
]

# Ultralytics 以 importlib.metadata 檢查的套件：metadata 缺失會被誤判為未安裝
# 並觸發 AutoUpdate（打包環境下會遞迴啟動執行檔，見 issue #95）。
DEPENDENCY_METADATA: List[str] = [
    "onnx",
    "onnxruntime",
]

# argus 業務子模組：驗證 zipimport 掛載後的模組可達性
ARGUS_MODULES: List[str] = [
    "argus.core.config_manager",
    "argus.capture.stream_handler",
    "argus.capture.video_handler",
    "argus.capture.grid_composer",
    "argus.vision.inference_engine",
    "argus.compliance.compliance_engine",
    "argus.events.event_producer",
    "argus.events.stats_logger",
    "argus.events.retention_cleaner",
    "argus.events.diagnostic_collector",
    "argus.integration.model_sync",
    "argus.integration.ums_config",
    "argus.integration.app_update_client",
    "argus.integration.state_poller",
    "argus.integration.report_issue",
    "argus.updates.update_manager",
    "argus.web.web_ui",
]

# 必要資料檔／目錄（相對於執行檔目錄）
# 格式：(相對路徑, 是否為目錄, 是否為強制必要)
REQUIRED_DATA_FILES: List[tuple] = [
    ("_internal/argus.zip",                     False, True),
    ("_internal/argus/web/templates",            True,  True),
    ("_internal/docs/user-manual/book",          True,  False),  # 可選：手冊
    ("scripts/run.sh",                           False, False),  # 守護重啟腳本
    ("scripts/install.sh",                       False, False),  # 安裝/回滾腳本
    # config.yaml 與模型檔由使用者部署，不在此強制驗
]


# ─────────────────────────────────────────────────────────────
# 2. 探針執行函式
# ─────────────────────────────────────────────────────────────

def _probe_imports(modules: List[str], optional: bool = False) -> List[Dict[str, Any]]:
    """逐一 import 指定模組，回傳每個模組的結果。

    optional=True 時，import 失敗標記為 OPTIONAL_MISSING（不算 FAIL）。
    """
    results = []
    for mod in modules:
        t0 = time.perf_counter()
        try:
            importlib.import_module(mod)
            results.append({
                "module": mod,
                "status": "OK",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            })
        except Exception as e:
            results.append({
                "module": mod,
                "status": "OPTIONAL_MISSING" if optional else "FAIL",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            })
    return results


def _probe_data_files(base_dir: Path) -> List[Dict[str, Any]]:
    """檢查必要資料檔／目錄是否存在。"""
    results = []
    for rel_path, is_dir, required in REQUIRED_DATA_FILES:
        target = base_dir / rel_path
        exists = target.is_dir() if is_dir else target.is_file()
        results.append({
            "path": rel_path,
            "abs_path": str(target),
            "type": "dir" if is_dir else "file",
            "required": required,
            "status": "OK" if exists else ("MISSING" if required else "OPTIONAL_MISSING"),
        })
    return results


def _probe_dependency_metadata(packages: List[str] = None) -> List[Dict[str, Any]]:
    """驗證套件 metadata 存在（Ultralytics 以 importlib.metadata 判斷是否已安裝）。"""
    import importlib.metadata as importlib_metadata

    results = []
    for pkg in (DEPENDENCY_METADATA if packages is None else packages):
        try:
            version = importlib_metadata.version(pkg)
            results.append({"package": pkg, "status": "OK", "version": version})
        except Exception as e:
            results.append({
                "package": pkg,
                "status": "FAIL",
                "error": f"metadata not found: {e}",
            })
    return results


def _probe_onnx_smoke() -> Dict[str, Any]:
    """關閉自動安裝後，以極小 ONNX 模型驗證 onnxruntime 可實際推理。

    缺少依賴時回報 FAIL，絕不觸發 Ultralytics AutoUpdate (pip install)。
    """
    try:
        import numpy as np
        import onnx
        import onnxruntime as ort
        from onnx import TensorProto, helper
        import ultralytics.utils.checks as checks

        # 與 Ultralytics AutoBackend 載入 ONNX 時相同的依賴檢查，但禁止安裝
        checks.AUTOINSTALL = False
        if not checks.check_requirements(("onnx", "onnxruntime"), install=False):
            return {
                "status": "FAIL",
                "error": "Ultralytics 判定 onnx/onnxruntime 未安裝 (metadata 缺失)，"
                         "於打包環境會觸發 AutoUpdate",
            }

        node = helper.make_node("Identity", ["x"], ["y"])
        graph = helper.make_graph(
            [node], "probe",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 2])],
            [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
        model.ir_version = 8
        onnx.checker.check_model(model)
        session = ort.InferenceSession(
            model.SerializeToString(), providers=["CPUExecutionProvider"]
        )
        out = session.run(None, {"x": np.ones((1, 2), dtype=np.float32)})[0]
        if out.shape != (1, 2):
            return {"status": "FAIL", "error": f"unexpected output shape {out.shape}"}
        return {"status": "OK", "note": f"onnxruntime {ort.__version__} inference OK"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e), "traceback": traceback.format_exc()}


def _probe_inference_engine() -> Dict[str, Any]:
    """驗證 YOLO 推論引擎類別可達，並驗證 NMS 運算子相容性（不載入模型檔，不開攝影機）。"""
    try:
        from ultralytics import YOLO  # noqa: F401
        from argus.vision.inference_engine import _ensure_torchvision_compatibility
        _ensure_torchvision_compatibility()
        return {"status": "OK", "note": "ultralytics.YOLO & NMS operators reachable"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e), "traceback": traceback.format_exc()}


def _probe_flask_routes() -> Dict[str, Any]:
    """驗證 Flask app 模組層級物件可存取，並列出已註冊路由數量。"""
    try:
        # web_ui 在模組層級建立 app，直接 import 即觸發初始化
        import argus.web.web_ui as web_ui_mod
        app = getattr(web_ui_mod, "app", None)
        if app is None:
            return {"status": "FAIL", "error": "web_ui.app object not found"}
        route_count = len(list(app.url_map.iter_rules()))
        return {
            "status": "OK",
            "note": f"Flask app reachable, registered routes: {route_count}",
        }
    except Exception as e:
        return {"status": "FAIL", "error": str(e), "traceback": traceback.format_exc()}


def _probe_zipimport_mount() -> Dict[str, Any]:
    """確認 argus.zip 是否已正確掛載至 sys.path。"""
    zip_entries = [p for p in sys.path if p.endswith("argus.zip")]
    if zip_entries:
        return {
            "status": "OK",
            "note": f"argus.zip mounted: {zip_entries[0]}",
        }
    # 未掛載不代表失敗（開發環境直接用 src/ 路徑）
    return {
        "status": "OK",
        "note": "argus.zip not in sys.path (running from source, expected in dev env)",
    }


# ─────────────────────────────────────────────────────────────
# 3. 主探針入口
# ─────────────────────────────────────────────────────────────

def run_probe(json_output: bool = False) -> int:
    """執行完整探針並回傳 exit code（0=PASS, 1=FAIL）。"""
    is_frozen = getattr(sys, "frozen", False)

    # 判斷基準目錄：frozen 用執行檔所在目錄，開發環境用專案根目錄
    if is_frozen:
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent

    report: Dict[str, Any] = {
        "probe_version": "1.0",
        "frozen": is_frozen,
        "base_dir": str(base_dir),
        "python_version": sys.version,
        "sys_path_snapshot": sys.path[:8],  # 前 8 條，避免報告過長
        "sections": {},
    }

    all_pass = True

    # ── Section 1: zipimport 掛載確認 ──────────────────────────
    zip_result = _probe_zipimport_mount()
    report["sections"]["zipimport_mount"] = zip_result
    if zip_result["status"] != "OK":
        all_pass = False

    # ── Section 2: 第三方套件 import ───────────────────────────
    third_party = _probe_imports(THIRD_PARTY_IMPORTS)
    third_party += _probe_imports(OPTIONAL_THIRD_PARTY_IMPORTS, optional=True)
    report["sections"]["third_party_imports"] = third_party
    if any(r["status"] == "FAIL" for r in third_party):
        all_pass = False

    # ── Section 3: argus 業務模組 import ───────────────────────
    argus_mods = _probe_imports(ARGUS_MODULES)
    report["sections"]["argus_modules"] = argus_mods
    if any(r["status"] == "FAIL" for r in argus_mods):
        all_pass = False

    # ── Section 4: 必要資料檔 ──────────────────────────────────
    data_files = _probe_data_files(base_dir)
    report["sections"]["data_files"] = data_files
    # 只有 required=True 且 MISSING 才算失敗
    if any(r["status"] == "MISSING" for r in data_files):
        all_pass = False

    # ── Section 5: 推論引擎初始化 ──────────────────────────────
    meta = _probe_dependency_metadata()
    report["sections"]["dependency_metadata"] = meta
    if any(r["status"] == "FAIL" for r in meta):
        all_pass = False

    onnx_smoke = _probe_onnx_smoke()
    report["sections"]["onnx_smoke"] = onnx_smoke
    if onnx_smoke["status"] != "OK":
        all_pass = False

    inference = _probe_inference_engine()
    report["sections"]["inference_engine"] = inference
    if inference["status"] != "OK":
        all_pass = False

    # ── Section 6: Flask app 路由 ──────────────────────────────
    flask_result = _probe_flask_routes()
    report["sections"]["flask_routes"] = flask_result
    if flask_result["status"] != "OK":
        all_pass = False

    report["result"] = "PASS" if all_pass else "FAIL"

    # ── 輸出 ───────────────────────────────────────────────────
    if json_output:
        # 確保 Windows cp950 等主控台不會因 Unicode 字符報錯
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(errors="replace")
            except Exception:
                pass
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human_report(report)

    return 0 if all_pass else 1


# ─────────────────────────────────────────────────────────────
# 4. 人類可讀輸出
# ─────────────────────────────────────────────────────────────

def _print_human_report(report: Dict[str, Any]) -> None:
    """將探針結果以人類可讀格式輸出至 stdout。"""
    result = report["result"]
    result_icon = "✅ PASS" if result == "PASS" else "❌ FAIL"

    print(f"\n{'=' * 64}")
    print(f"  Argus Package Probe v{report['probe_version']} — {result_icon}")
    print(f"  Base : {report['base_dir']}")
    print(f"  Mode : {'Frozen (PyInstaller)' if report['frozen'] else 'Source (Dev)'}")
    print(f"{'=' * 64}")

    sections = report["sections"]

    # zipimport
    _print_single(sections["zipimport_mount"], "zipimport_mount")

    # third_party_imports
    print("\n[third_party_imports]")
    for item in sections["third_party_imports"]:
        if item["status"] == "OK":
            sym = "✅"
        elif item["status"] == "OPTIONAL_MISSING":
            sym = "⚠️ "
        else:
            sym = "❌"
        extra = f"  ← {item.get('error', '')}" if item["status"] != "OK" else \
                f"  ({item['elapsed_ms']} ms)"
        if item["status"] == "OPTIONAL_MISSING":
            extra += " (optional)"
        print(f"  {sym} {item['module']}{extra}")

    # argus_modules
    print("\n[argus_modules]")
    for item in sections["argus_modules"]:
        sym = "✅" if item["status"] == "OK" else "❌"
        extra = f"  ← {item.get('error', '')}" if item["status"] != "OK" else \
                f"  ({item['elapsed_ms']} ms)"
        print(f"  {sym} {item['module']}{extra}")

    # data_files
    print("\n[data_files]")
    for item in sections["data_files"]:
        if item["status"] == "OK":
            sym = "✅"
        elif item["status"] == "OPTIONAL_MISSING":
            sym = "⚠️ "
        else:
            sym = "❌"
        note = "" if item["status"] == "OK" else f"  ← {item['status']}"
        req = "" if item["required"] else " (optional)"
        print(f"  {sym} {item['path']}{req}{note}")

    # dependency_metadata
    print("\n[dependency_metadata]")
    for item in sections["dependency_metadata"]:
        if item["status"] == "OK":
            print(f"  ✅ {item['package']}  ({item['version']})")
        else:
            print(f"  ❌ {item['package']}  ← {item.get('error', '')}")

    _print_single(sections["onnx_smoke"], "onnx_smoke")

    # inference_engine & flask_routes
    _print_single(sections["inference_engine"], "inference_engine")
    _print_single(sections["flask_routes"], "flask_routes")

    print(f"\n{'=' * 64}")
    print(f"  結果：{result_icon}")
    print(f"{'=' * 64}\n")


def _print_single(item: Dict[str, Any], label: str) -> None:
    sym = "✅" if item["status"] == "OK" else "❌"
    note = item.get("note") or item.get("error", "")
    print(f"\n[{label}]")
    print(f"  {sym} {note}")


# ─────────────────────────────────────────────────────────────
# 5. CLI 入口（直接執行時）
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Argus 打包完整性探針 — 驗證所有 import 與資料檔是否正確打包"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="輸出 JSON 格式報告（適合 CI 機器解析）",
    )
    args = parser.parse_args()
    sys.exit(run_probe(json_output=args.json))
