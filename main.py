#!/usr/bin/env python3
"""Argus Safety Predictor Nano - Root Thin Entrypoint.

This is the lightweight entrypoint for executing the application directly
or packaging with PyInstaller. All application logic resides in the `argus` package.
"""

import os
import sys
import zipimport

# 永遠停用 Ultralytics AutoUpdate：打包環境中 sys.executable 為本執行檔，
# pip install 會導致應用程式被重複啟動（issue #95）。需在 import ultralytics 之前設定。
os.environ["YOLO_AUTOINSTALL"] = "false"


def mount_argus_zip(custom_path: str = None) -> bool:
    """Mount _internal/argus.zip via zipimport if available.

    This enables runtime business logic decoupling: in frozen PyInstaller onedir
    builds or delta-patched installations, argus business modules are loaded
    directly from `_internal/argus.zip` rather than being hardcoded into the ELF PYZ.

    Returns:
        bool: True if an argus.zip was discovered and mounted, False otherwise.
    """
    candidates = []
    if custom_path:
        candidates.append(custom_path)

    # 1. PyInstaller frozen environment (_MEIPASS / executable directory)
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "argus.zip"))
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "_internal", "argus.zip"))
        candidates.append(os.path.join(exe_dir, "argus.zip"))

    # 2. Local directory candidates (development, testing, or local staging)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, "_internal", "argus.zip"))
    candidates.append(os.path.join(base_dir, "argus.zip"))
    candidates.append(os.path.join(os.getcwd(), "_internal", "argus.zip"))
    candidates.append(os.path.join(os.getcwd(), "argus.zip"))

    for zip_path in candidates:
        if os.path.isfile(zip_path):
            norm_path = os.path.normpath(os.path.abspath(zip_path))
            if norm_path not in sys.path:
                try:
                    zipimport.zipimporter(norm_path)
                    sys.path.insert(0, norm_path)
                    return True
                except Exception:
                    continue
            else:
                return True
    return False


# Automatically mount argus.zip before any domain module imports
mount_argus_zip()


import subprocess


def delegate_to_managed_runner() -> None:
    """自動委派至守護腳本 (run.bat / run.sh) 執行。

    防呆機制：確保程序由具備 Exit Code 42 自動置換與異常崩潰回滾能力的
    外層守護迴圈進行管理，避免操作員直接呼叫 python main.py 導致更新無法重啟。
    """
    # 支援透過 --allow-direct 參數或 ARGUS_MANAGED_RUNNER=1 跳過委派
    if os.environ.get("ARGUS_MANAGED_RUNNER") == "1":
        return

    if "--allow-direct" in sys.argv:
        sys.argv.remove("--allow-direct")
        return

    # 特殊診斷或單次指令不強求委派
    if any(arg in sys.argv for arg in ("--probe", "--report-issue", "-r", "--help", "-h")):
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    is_windows = sys.platform == "win32"

    runner_path = None
    runner_cmd = []

    if is_windows:
        # Windows: 優先尋找 run.bat
        cand_bat = [
            os.path.join(base_dir, "run.bat"),
            os.path.abspath("run.bat"),
            os.path.join(base_dir, "scripts", "run.bat"),
        ]
        for p in cand_bat:
            if os.path.isfile(p):
                runner_path = p
                runner_cmd = ["cmd.exe", "/c", p] + sys.argv[1:]
                break
    else:
        # Linux / POSIX: 優先尋找 scripts/run.sh 或 run.sh
        cand_sh = [
            os.path.join(base_dir, "scripts", "run.sh"),
            os.path.join(base_dir, "run.sh"),
            os.path.abspath("scripts/run.sh"),
        ]
        for p in cand_sh:
            if os.path.isfile(p):
                runner_path = p
                runner_cmd = ["bash", p] + sys.argv[1:]
                break

    if runner_path and runner_cmd:
        print(f"[main.py] 偵測到未由守護腳本託管 (ARGUS_MANAGED_RUNNER 未設定)。")
        print(f"[main.py] 自動轉交至外層守護腳本執行: {runner_path}")
        try:
            # 委派至外層守護腳本執行並繼承標準輸出入，並以該腳本之 Exit Code 退出當前進程
            res = subprocess.run(runner_cmd, cwd=base_dir)
            sys.exit(res.returncode)
        except Exception as e:
            print(f"[main.py] 自動轉發守護腳本失敗 ({e})，降級為直接運行。")


if __name__ == "__main__":
    delegate_to_managed_runner()

    if "--probe" in sys.argv:
        # 打包完整性探針：驗證所有 import 與資料檔是否正確打包
        # 用法：./argus_predictor --probe [--json]
        json_out = "--json" in sys.argv
        from scripts.probe_package import run_probe
        sys.exit(run_probe(json_output=json_out))
    elif "--report-issue" in sys.argv or "-r" in sys.argv:
        from argus.integration.report_issue import run_cli
        cli_args = [arg for arg in sys.argv[1:] if arg not in ("--report-issue", "-r")]
        sys.exit(run_cli(cli_args))
    else:
        from argus.main import main
        main()
