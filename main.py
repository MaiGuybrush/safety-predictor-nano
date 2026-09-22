#!/usr/bin/env python3
"""Argus Safety Predictor Nano - Root Thin Entrypoint.

This is the lightweight entrypoint for executing the application directly
or packaging with PyInstaller. All application logic resides in the `argus` package.
"""

import os
import sys
import zipimport


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


if __name__ == "__main__":
    if "--report-issue" in sys.argv or "-r" in sys.argv:
        from argus.integration.report_issue import run_cli
        cli_args = [arg for arg in sys.argv[1:] if arg not in ("--report-issue", "-r")]
        sys.exit(run_cli(cli_args))
    else:
        from argus.main import main
        main()
