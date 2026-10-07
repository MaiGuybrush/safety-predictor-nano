import os
import sys

__version__ = "1.0.0"

def _resolve_version() -> str:
    """探測執行端環境目錄之 version.txt，若存在則優先採用。"""
    candidates = []
    # 1. 凍結環境 (PyInstaller)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "version.txt"))
        candidates.append(os.path.join(exe_dir, "_internal", "version.txt"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "version.txt"))

    # 2. 目前工作目錄與父目錄
    candidates.append(os.path.join(os.getcwd(), "version.txt"))
    candidates.append(os.path.join(os.getcwd(), "_internal", "version.txt"))

    # 3. 模組所在位置的相對路徑
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, "..", "..", "version.txt"))
    candidates.append(os.path.join(base_dir, "version.txt"))

    for path in candidates:
        norm_path = os.path.normpath(path)
        if os.path.isfile(norm_path):
            try:
                with open(norm_path, "r", encoding="utf-8") as f:
                    ver = f.read().strip()
                if ver:
                    return ver
            except Exception:
                continue
    return __version__

__version__ = _resolve_version()

