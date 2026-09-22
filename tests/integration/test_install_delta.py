import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import pytest
from argus.updates.delta_updater import compute_sha256, DeltaUpdater


def get_bash_executable():
    """尋找可用之 bash 執行檔 (支援 Windows Git Bash / WSL / Linux native)。"""
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    if os.path.isfile(git_bash):
        return git_bash
    which_bash = shutil.which("bash")
    if which_bash:
        return which_bash
    which_sh = shutil.which("sh")
    if which_sh:
        return which_sh
    return None


@pytest.fixture
def bash_exe():
    exe = get_bash_executable()
    if not exe:
        pytest.skip("此測試環境無可用的 bash / sh 直譯器")
    return exe


def to_bash_path(path: str) -> str:
    """轉換 Windows 路徑為 Git Bash / Unix 格式路徑。"""
    clean_path = os.path.abspath(path).replace("\\", "/")
    # 例如 D:/... 轉為 /d/... 或保留 D:/ (Git Bash 皆相容)
    if len(clean_path) >= 2 and clean_path[1] == ":":
        drive = clean_path[0].lower()
        return f"/{drive}{clean_path[2:]}"
    return clean_path


def create_mock_environment(sandbox_dir: str):
    """建立模擬之邊緣端正式運行環境。"""
    argus_dir = os.path.join(sandbox_dir, "argus_predictor")
    internal_dir = os.path.join(argus_dir, "_internal")
    scripts_dir = os.path.join(sandbox_dir, "scripts")
    models_dir = os.path.join(sandbox_dir, "models")
    logs_dir = os.path.join(sandbox_dir, "logs")

    os.makedirs(internal_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    # 複製專案當前之 install.sh 至測試沙盒
    src_install_sh = os.path.abspath("scripts/install.sh")
    dest_install_sh = os.path.join(scripts_dir, "install.sh")
    shutil.copy2(src_install_sh, dest_install_sh)

    # 1. 舊版業務代碼 (argus.zip)
    old_zip = os.path.join(internal_dir, "argus.zip")
    with open(old_zip, "w") as f:
        f.write("old_business_logic_v1.0.0")

    # 2. 舊版前端 Web 模板
    old_tpl_dir = os.path.join(internal_dir, "argus", "web", "templates")
    os.makedirs(old_tpl_dir, exist_ok=True)
    with open(os.path.join(old_tpl_dir, "index.html"), "w") as f:
        f.write("<html>old_ui_v1.0.0</html>")

    # 3. 舊版手冊 docs
    old_docs_dir = os.path.join(internal_dir, "docs", "user-manual", "book")
    os.makedirs(old_docs_dir, exist_ok=True)
    with open(os.path.join(old_docs_dir, "index.html"), "w") as f:
        f.write("old_manual_v1.0.0")

    # 4. 舊版版本標記
    with open(os.path.join(argus_dir, "version.txt"), "w") as f:
        f.write("1.0.0\n")

    # 5. 龐大重型動態函式庫 (PyTorch、OpenCV) - 必須嚴格保留不動！
    torch_dir = os.path.join(internal_dir, "torch")
    os.makedirs(torch_dir, exist_ok=True)
    torch_lib = os.path.join(torch_dir, "libtorch.so")
    with open(torch_lib, "w") as f:
        f.write("heavy_torch_binary_content_bytes")

    cv2_dir = os.path.join(internal_dir, "cv2")
    os.makedirs(cv2_dir, exist_ok=True)
    cv2_lib = os.path.join(cv2_dir, "cv2.so")
    with open(cv2_lib, "w") as f:
        f.write("heavy_cv2_binary_content_bytes")

    # 6. 本機客製配置檔 (config.yaml) 與模型、日誌 - 必須嚴格保留！
    cfg_path = os.path.join(sandbox_dir, "config.yaml")
    with open(cfg_path, "w") as f:
        f.write("confidence_threshold: 0.88\nzone: factory_a\n")

    model_path = os.path.join(models_dir, "yolov8n.pt")
    with open(model_path, "w") as f:
        f.write("model_weights_data")

    log_path = os.path.join(logs_dir, "system.log")
    with open(log_path, "w") as f:
        f.write("[INFO] system started\n")

    return {
        "sandbox_dir": sandbox_dir,
        "scripts_dir": scripts_dir,
        "install_sh": dest_install_sh,
        "argus_dir": argus_dir,
        "internal_dir": internal_dir,
        "old_zip": old_zip,
        "torch_lib": torch_lib,
        "cv2_lib": cv2_lib,
        "cfg_path": cfg_path,
        "model_path": model_path,
        "log_path": log_path,
    }


def create_delta_tar_gz(output_tar_gz: str, target_version: str = "1.1.0") -> str:
    """建立測試用之標準 Delta .tar.gz 增量更新包。"""
    with tempfile.TemporaryDirectory() as staging:
        payload_dir = os.path.join(staging, "payload")
        internal_dir = os.path.join(payload_dir, "_internal")
        tpl_dir = os.path.join(internal_dir, "argus", "web", "templates")
        docs_dir = os.path.join(internal_dir, "docs", "user-manual", "book")

        os.makedirs(tpl_dir, exist_ok=True)
        os.makedirs(docs_dir, exist_ok=True)

        new_zip = os.path.join(internal_dir, "argus.zip")
        with open(new_zip, "w") as f:
            f.write(f"new_business_logic_v{target_version}")

        new_tpl = os.path.join(tpl_dir, "index.html")
        with open(new_tpl, "w") as f:
            f.write(f"<html>new_ui_v{target_version}</html>")

        new_docs = os.path.join(docs_dir, "index.html")
        with open(new_docs, "w") as f:
            f.write(f"new_manual_v{target_version}")

        new_ver = os.path.join(payload_dir, "version.txt")
        with open(new_ver, "w") as f:
            f.write(f"{target_version}\n")

        manifest_data = {
            "package_type": "delta",
            "target_version": target_version,
            "min_compatible_base": "1.0.0",
            "arch": "arm64",
            "code_only": False,
            "file_count": 4,
            "files": {
                "_internal/argus.zip": {
                    "sha256": compute_sha256(new_zip),
                    "size": os.path.getsize(new_zip),
                },
                "_internal/argus/web/templates/index.html": {
                    "sha256": compute_sha256(new_tpl),
                    "size": os.path.getsize(new_tpl),
                },
                "_internal/docs/user-manual/book/index.html": {
                    "sha256": compute_sha256(new_docs),
                    "size": os.path.getsize(new_docs),
                },
                "version.txt": {
                    "sha256": compute_sha256(new_ver),
                    "size": os.path.getsize(new_ver),
                },
            },
        }
        manifest_path = os.path.join(staging, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        with tarfile.open(output_tar_gz, "w:gz") as tar:
            tar.add(manifest_path, arcname="manifest.json")
            tar.add(payload_dir, arcname="payload")

    return output_tar_gz


def test_install_delta_success_and_preservation(bash_exe):
    """驗證 install.sh --delta 正確識別、僅覆蓋業務與前端檔案，並保留龐大函式庫與本機設定。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = create_mock_environment(tmpdir)
        delta_tar = os.path.join(tmpdir, "argus_delta-v1.1.0-arm64.tar.gz")
        create_delta_tar_gz(delta_tar, target_version="1.1.0")

        # 執行 install.sh --delta
        cmd = [
            bash_exe,
            to_bash_path(env["install_sh"]),
            "--delta",
            to_bash_path(delta_tar),
        ]
        start_time = time.time()
        proc = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - start_time

        assert proc.returncode == 0, f"install.sh --delta 失敗: {proc.stderr}\nstdout: {proc.stdout}"
        # 驗證整體執行順暢 (Windows 下 MSYS 行程啟動約 1~5s)
        assert elapsed < 15.0

        # 1. 驗證業務代碼已更新至新版
        with open(env["old_zip"], "r") as f:
            assert f.read() == "new_business_logic_v1.1.0"

        # 2. 驗證版本資訊已更新
        ver_file = os.path.join(env["argus_dir"], "version.txt")
        with open(ver_file, "r") as f:
            assert f.read().strip() == "1.1.0"

        # 3. 驗證前端資產已更新
        tpl_file = os.path.join(env["internal_dir"], "argus", "web", "templates", "index.html")
        with open(tpl_file, "r") as f:
            assert f.read() == "<html>new_ui_v1.1.0</html>"

        # 4. 驗證龐大動態函式庫 (torch, cv2) 嚴格保留未被更動或刪除
        assert os.path.isfile(env["torch_lib"])
        with open(env["torch_lib"], "r") as f:
            assert f.read() == "heavy_torch_binary_content_bytes"

        assert os.path.isfile(env["cv2_lib"])
        with open(env["cv2_lib"], "r") as f:
            assert f.read() == "heavy_cv2_binary_content_bytes"

        # 5. 驗證本機配置與模型未受影響
        with open(env["cfg_path"], "r") as f:
            assert "confidence_threshold: 0.88" in f.read()
        assert os.path.isfile(env["model_path"])
        assert os.path.isfile(env["log_path"])

        # 6. 驗證 .patch_bak/ 備份已建立
        patch_bak = os.path.join(env["internal_dir"], ".patch_bak")
        assert os.path.isdir(patch_bak)
        assert os.path.isfile(os.path.join(patch_bak, "argus.zip"))
        with open(os.path.join(patch_bak, "argus.zip"), "r") as f:
            assert f.read() == "old_business_logic_v1.0.0"


def test_install_delta_rollback_success(bash_exe):
    """驗證 install.sh --rollback 在秒級內精確還原舊版業務代碼與靜態資源，並產出 .rollback_alert。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = create_mock_environment(tmpdir)
        delta_tar = os.path.join(tmpdir, "argus_delta-v1.1.0-arm64.tar.gz")
        create_delta_tar_gz(delta_tar, target_version="1.1.0")

        # 1. 先執行升級
        cmd_upgrade = [
            bash_exe,
            to_bash_path(env["install_sh"]),
            "--delta",
            to_bash_path(delta_tar),
        ]
        proc_up = subprocess.run(
            cmd_upgrade,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc_up.returncode == 0

        # 2. 執行回滾 install.sh --rollback
        cmd_rollback = [
            bash_exe,
            to_bash_path(env["install_sh"]),
            "--rollback",
        ]
        start_time = time.time()
        proc_rb = subprocess.run(
            cmd_rollback,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - start_time

        assert proc_rb.returncode == 0, f"install.sh --rollback 失敗: {proc_rb.stderr}\nstdout: {proc_rb.stdout}"
        assert elapsed < 15.0

        # 3. 驗證業務模組與靜態資源精確還原至舊版
        with open(env["old_zip"], "r") as f:
            assert f.read() == "old_business_logic_v1.0.0"

        ver_file = os.path.join(env["argus_dir"], "version.txt")
        with open(ver_file, "r") as f:
            assert f.read().strip() == "1.0.0"

        tpl_file = os.path.join(env["internal_dir"], "argus", "web", "templates", "index.html")
        with open(tpl_file, "r") as f:
            assert f.read() == "<html>old_ui_v1.0.0</html>"

        # 4. 驗證龐大動態函式庫依然完好無損
        assert os.path.isfile(env["torch_lib"])
        assert os.path.isfile(env["cv2_lib"])

        # 5. 驗證 .patch_bak 已被清理
        patch_bak = os.path.join(env["internal_dir"], ".patch_bak")
        assert not os.path.exists(patch_bak)

        # 6. 驗證產出 .rollback_alert 標記
        alert_path = os.path.join(tmpdir, ".rollback_alert")
        assert os.path.isfile(alert_path)
        with open(alert_path, "r", encoding="utf-8") as f:
            alert_content = f.read()
            assert "自動安全回滾至原版本" in alert_content


def test_install_delta_rejects_invalid_package(bash_exe):
    """驗證 install.sh --delta 遇到非 Delta 封包時拒絕執行並退出失敗。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = create_mock_environment(tmpdir)

        # 建立一個不是 delta 的 tar.gz
        invalid_tar = os.path.join(tmpdir, "invalid.tar.gz")
        with tempfile.TemporaryDirectory() as fake_staging:
            fake_manifest = os.path.join(fake_staging, "manifest.json")
            with open(fake_manifest, "w") as f:
                json.dump({"package_type": "full", "target_version": "1.0.0"}, f)
            with tarfile.open(invalid_tar, "w:gz") as tar:
                tar.add(fake_manifest, arcname="manifest.json")

        cmd = [
            bash_exe,
            to_bash_path(env["install_sh"]),
            "--delta",
            to_bash_path(invalid_tar),
        ]
        proc = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode != 0
        assert "package_type 不是 delta" in proc.stderr or "package_type 不是 delta" in proc.stdout

        # 驗證原系統不受任何破壞
        with open(env["old_zip"], "r") as f:
            assert f.read() == "old_business_logic_v1.0.0"
