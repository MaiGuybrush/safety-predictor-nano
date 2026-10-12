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


def test_run_bat_working_directory_lock_windows(tmp_path):
    """驗證 Windows 環境下 scripts/run.bat 能正確鎖定工作目錄至程式根目錄而非 scripts/。"""
    if sys.platform != "win32":
        pytest.skip("Windows batch script test only applies to win32")

    base_dir = tmp_path / "app_root"
    scripts_dir = base_dir / "scripts"
    scripts_dir.mkdir(parents=True)

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_bat = os.path.join(repo_root, "scripts", "run.bat")
    with open(src_bat, "r", encoding="utf-8") as f:
        bat_content = f.read()

    test_bat = scripts_dir / "run.bat"
    test_bat.write_text(bat_content, encoding="utf-8")

    # 建立假的 main.py，印出當前目錄並正常退出 (Exit 0)
    fake_main = base_dir / "main.py"
    fake_main.write_text("import os; print('CWD_IS:' + os.getcwd()); exit(0)\n", encoding="utf-8")

    # 在 scripts 目錄下執行 scripts/run.bat
    res = subprocess.run(
        ["cmd.exe", "/c", str(test_bat)],
        cwd=str(scripts_dir),
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0
    assert f"Working directory locked to: {str(base_dir)}" in res.stdout
    assert f"CWD_IS:{str(base_dir)}" in res.stdout

