import os
import subprocess
import sys
import pytest


def test_main_delegate_bypass_with_allow_direct(monkeypatch):
    """驗證 main.py 帶有 --allow-direct 參數時跳過委派直接執行。"""
    from main import delegate_to_managed_runner

    monkeypatch.delenv("ARGUS_MANAGED_RUNNER", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--allow-direct", "--probe"])
    # 執行後 --allow-direct 應被移除且不調用 sys.exit 或轉發
    delegate_to_managed_runner()
    assert "--allow-direct" not in sys.argv
    assert "--probe" in sys.argv


def test_main_delegate_bypass_when_already_managed(monkeypatch):
    """驗證 main.py 在已由 ARGUS_MANAGED_RUNNER=1 託管的環境下跳過委派直接運行。"""
    from main import delegate_to_managed_runner

    monkeypatch.setenv("ARGUS_MANAGED_RUNNER", "1")
    monkeypatch.setattr(sys, "argv", ["main.py", "--custom-arg"])
    # 不應調用 sys.exit
    delegate_to_managed_runner()


def test_main_delegate_triggers_runner(monkeypatch, tmp_path):
    """驗證 main.py 在未託管且未帶 --allow-direct 時，呼叫 subprocess 委派至守護腳本。"""
    from main import delegate_to_managed_runner

    monkeypatch.delenv("ARGUS_MANAGED_RUNNER", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--run-service"])

    called_cmd = []

    def mock_subprocess_run(cmd, cwd=None):
        called_cmd.append((cmd, cwd))
        class MockResult:
            returncode = 0
        return MockResult()

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    exit_code_captured = []
    def mock_exit(code):
        exit_code_captured.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", mock_exit)

    with pytest.raises(SystemExit):
        delegate_to_managed_runner()

    assert len(called_cmd) == 1
    assert exit_code_captured == [0]
    cmd_args = called_cmd[0][0]
    # 在 Windows 下應為 ['cmd.exe', '/c', '...run.bat', '--run-service']
    # 在 Linux 下應為 ['bash', '...run.sh', '--run-service']
    assert any("run.bat" in str(arg) or "run.sh" in str(arg) for arg in cmd_args)
    assert "--run-service" in cmd_args
