import datetime
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
import pytest

from argus.updates.delta_updater import compute_sha256


INSTALL_PY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "install.py"))


def run_install_cli(args, cwd):
    """執行 scripts/install.py CLI 並回傳 CompletedProcess"""
    cmd = [sys.executable, INSTALL_PY_PATH] + args
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def test_install_script_help():
    """驗證 --help 參數正常輸出支援的選項"""
    result = run_install_cli(["--help"], cwd=os.getcwd())
    assert result.returncode == 0
    assert "--delta" in result.stdout
    assert "--rollback" in result.stdout
    assert "--full" in result.stdout


def test_install_script_delta_and_rollback():
    """驗證 scripts/install.py 之 --delta 局部套用與 --rollback 秒級還原功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = tmpdir
        argus_dir = os.path.join(base_dir, "argus_predictor")
        internal_dir = os.path.join(argus_dir, "_internal")
        os.makedirs(internal_dir, exist_ok=True)

        # 1. 建立初始環境 (v1.0.0)
        old_zip = os.path.join(internal_dir, "argus.zip")
        with zipfile.ZipFile(old_zip, "w") as zf:
            zf.writestr("module.py", "version_1_0_0")

        old_ver = os.path.join(argus_dir, "version.txt")
        with open(old_ver, "w", encoding="utf-8") as f:
            f.write("1.0.0\n")

        # 2. 建立 Delta 增量包 (v1.1.0)
        staging_dir = os.path.join(base_dir, "staging_pack")
        payload_dir = os.path.join(staging_dir, "payload")
        new_internal = os.path.join(payload_dir, "_internal")
        os.makedirs(new_internal, exist_ok=True)

        new_zip = os.path.join(new_internal, "argus.zip")
        with zipfile.ZipFile(new_zip, "w") as zf:
            zf.writestr("module.py", "version_1_1_0")

        new_ver = os.path.join(payload_dir, "version.txt")
        with open(new_ver, "w", encoding="utf-8") as f:
            f.write("1.1.0\n")

        manifest_data = {
            "package_type": "delta",
            "target_version": "1.1.0",
            "min_compatible_base": "1.0.0",
            "arch": "arm64",
            "files": {
                "_internal/argus.zip": {
                    "sha256": compute_sha256(new_zip),
                    "size": os.path.getsize(new_zip),
                },
                "version.txt": {
                    "sha256": compute_sha256(new_ver),
                    "size": os.path.getsize(new_ver),
                },
            },
        }
        manifest_file = os.path.join(staging_dir, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # 打包為 .tar.gz
        delta_tar = os.path.join(base_dir, "delta-v1.1.0.tar.gz")
        with tarfile.open(delta_tar, "w:gz") as tf:
            tf.add(manifest_file, arcname="manifest.json")
            tf.add(payload_dir, arcname="payload")

        # 3. 測試執行 --delta <tar.gz>
        res = run_install_cli(["--delta", delta_tar], cwd=base_dir)
        assert res.returncode == 0, f"Delta install failed: {res.stderr}\n{res.stdout}"
        assert "Delta" in res.stdout

        # 驗證置換結果
        with zipfile.ZipFile(old_zip, "r") as zf:
            assert zf.read("module.py").decode() == "version_1_1_0"
        with open(old_ver, "r", encoding="utf-8") as f:
            assert f.read().strip() == "1.1.0"

        # 驗證備份存在
        bak_dir = os.path.join(internal_dir, ".patch_bak")
        assert os.path.isdir(bak_dir)
        assert os.path.isfile(os.path.join(bak_dir, "argus.zip"))
        assert os.path.isfile(os.path.join(bak_dir, "version.txt"))

        # 4. 測試執行 --rollback
        res_rb = run_install_cli(["--rollback"], cwd=base_dir)
        assert res_rb.returncode == 0, f"Rollback failed: {res_rb.stderr}\n{res_rb.stdout}"

        # 驗證已秒級還原
        with zipfile.ZipFile(old_zip, "r") as zf:
            assert zf.read("module.py").decode() == "version_1_0_0"
        with open(old_ver, "r", encoding="utf-8") as f:
            assert f.read().strip() == "1.0.0"

        # 驗證 alert 標記檔與 .patch_bak 已清除
        alert_file = os.path.join(base_dir, ".rollback_alert")
        assert os.path.isfile(alert_file)
        with open(alert_file, "r", encoding="utf-8") as f:
            assert "自動安全回滾至原版本" in f.read()
        assert not os.path.exists(bak_dir)


def test_install_script_full_switch_and_rollback():
    """驗證 scripts/install.py 之 --full 全量切換與全量備份還原"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = tmpdir
        argus_dir = os.path.join(base_dir, "argus_predictor")
        os.makedirs(argus_dir, exist_ok=True)
        old_bin = os.path.join(argus_dir, "binary.bin")
        with open(old_bin, "w", encoding="utf-8") as f:
            f.write("old_binary_v1")

        # 建立全量更新包目錄或 tar.gz
        full_dir = os.path.join(base_dir, "full_pkg")
        os.makedirs(full_dir, exist_ok=True)
        new_bin = os.path.join(full_dir, "binary.bin")
        with open(new_bin, "w", encoding="utf-8") as f:
            f.write("new_binary_v2")

        full_tar = os.path.join(base_dir, "full-v2.0.0.tar.gz")
        with tarfile.open(full_tar, "w:gz") as tf:
            tf.add(new_bin, arcname="binary.bin")

        # 執行 --full
        res = run_install_cli(["--full", full_tar], cwd=base_dir)
        assert res.returncode == 0, f"Full install failed: {res.stderr}\n{res.stdout}"

        # 驗證 argus_predictor_bak 備份存在且內容置換
        bak_dir = os.path.join(base_dir, "argus_predictor_bak")
        assert os.path.isdir(bak_dir)
        assert os.path.isfile(os.path.join(bak_dir, "binary.bin"))
        with open(os.path.join(bak_dir, "binary.bin"), "r", encoding="utf-8") as f:
            assert f.read() == "old_binary_v1"

        with open(old_bin, "r", encoding="utf-8") as f:
            assert f.read() == "new_binary_v2"

        # 執行 --rollback (無 .patch_bak，應回退至全量還原)
        res_rb = run_install_cli(["--rollback"], cwd=base_dir)
        assert res_rb.returncode == 0, f"Full rollback failed: {res_rb.stderr}\n{res_rb.stdout}"

        # 驗證原版本還原
        with open(old_bin, "r", encoding="utf-8") as f:
            assert f.read() == "old_binary_v1"
        assert not os.path.exists(bak_dir)
        assert os.path.isfile(os.path.join(base_dir, ".rollback_alert"))


def test_install_script_corrupted_manifest_fails():
    """驗證當 manifest.json 損壞或 sha256 雜湊不符時，install.py 應拒絕更新並返回非零狀態碼"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = tmpdir
        argus_dir = os.path.join(base_dir, "argus_predictor")
        internal_dir = os.path.join(argus_dir, "_internal")
        os.makedirs(internal_dir, exist_ok=True)

        staging_dir = os.path.join(base_dir, "staging_pack")
        payload_dir = os.path.join(staging_dir, "payload")
        new_internal = os.path.join(payload_dir, "_internal")
        os.makedirs(new_internal, exist_ok=True)

        new_zip = os.path.join(new_internal, "argus.zip")
        with open(new_zip, "w") as f:
            f.write("corrupted_content")

        file_size = os.path.getsize(new_zip)
        manifest_data = {
            "package_type": "delta",
            "target_version": "1.1.0",
            "files": {
                "_internal/argus.zip": {
                    "sha256": "wrong_sha256_hash_value_1234567890",
                    "size": file_size,
                }
            },
        }
        manifest_file = os.path.join(staging_dir, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        delta_tar = os.path.join(base_dir, "corrupt-delta.tar.gz")
        with tarfile.open(delta_tar, "w:gz") as tf:
            tf.add(manifest_file, arcname="manifest.json")
            tf.add(payload_dir, arcname="payload")

        res = run_install_cli(["--delta", delta_tar], cwd=base_dir)
        assert res.returncode != 0
        output_text = res.stdout + res.stderr
        assert "雜湊值不符" in output_text or "不符" in output_text or "SHA-256" in output_text
