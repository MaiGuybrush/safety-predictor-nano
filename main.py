#!/usr/bin/env python3
"""Argus Safety Predictor Nano - Root Thin Entrypoint.

This is the lightweight entrypoint for executing the application directly
or packaging with PyInstaller. All application logic resides in the `argus` package.
"""

import sys
from argus.main import main


if __name__ == "__main__":
    if "--report-issue" in sys.argv or "-r" in sys.argv:
        from argus.integration.report_issue import run_cli
        cli_args = [arg for arg in sys.argv[1:] if arg not in ("--report-issue", "-r")]
        sys.exit(run_cli(cli_args))
    else:
        main()
