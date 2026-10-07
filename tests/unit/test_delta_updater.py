import json
import os
import shutil
import tempfile
import pytest
from argus.updates.delta_updater import (
    DeltaManifest,
    DeltaManifestError,
    DeltaCompatibilityError,
    DeltaUpdater,
    compute_sha256,
)


def test_delta_manifest_valid():
    data = {
        "package_type": "delta",
        "target_version": "1.1.0",
        "min_compatible_base": "1.0.0",
        "arch": "arm64",
        "code_only": False,
        "files": {
            "_internal/argus.zip": {"sha256": "fakehash", "size": 1234}
        },
    }
    manifest = DeltaManifest.from_dict(data)
    assert manifest.package_type == "delta"
    assert manifest.target_version == "1.1.0"
    assert manifest.min_compatible_base == "1.0.0"
    assert manifest.arch == "arm64"
    assert manifest.file_count == 1
    assert manifest.is_compatible("1.0.0")
    assert manifest.is_compatible("1.0.5")
    assert not manifest.is_compatible("0.9.0")


def test_delta_manifest_invalid():
    # 非 delta 類型
    with pytest.raises(DeltaManifestError, match="非 Delta 增量包"):
        DeltaManifest.from_dict({"package_type": "full", "target_version": "1.0.0"})

    # 缺少 target_version
    with pytest.raises(DeltaManifestError, match="缺少有效的 target_version"):
        DeltaManifest.from_dict({"package_type": "delta"})


def test_delta_updater_apply_and_rollback():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 建立模擬執行環境
        base_dir = tmpdir
        argus_dir = os.path.join(base_dir, "argus_predictor")
        internal_dir = os.path.join(argus_dir, "_internal")
        os.makedirs(internal_dir, exist_ok=True)

        # 模擬舊版檔案
        old_zip = os.path.join(internal_dir, "argus.zip")
        with open(old_zip, "w") as f:
            f.write("old_code_v1.0.0")

        # 模擬重型動態函式庫 (PyTorch / OpenCV) - 必須嚴格保留！
        torch_dir = os.path.join(internal_dir, "torch")
        os.makedirs(torch_dir, exist_ok=True)
        torch_lib = os.path.join(torch_dir, "libtorch.so")
        with open(torch_lib, "w") as f:
            f.write("torch_binary_data")

        cv2_dir = os.path.join(internal_dir, "cv2")
        os.makedirs(cv2_dir, exist_ok=True)
        cv2_lib = os.path.join(cv2_dir, "cv2.so")
        with open(cv2_lib, "w") as f:
            f.write("cv2_binary_data")

        # 模擬舊版 version.txt
        old_ver_path = os.path.join(argus_dir, "version.txt")
        with open(old_ver_path, "w") as f:
            f.write("1.0.0\n")

        # 模擬本機設定檔與模型目錄 - 嚴格保留！
        cfg_path = os.path.join(base_dir, "config.yaml")
        with open(cfg_path, "w") as f:
            f.write("user_custom_setting: true\n")

        models_dir = os.path.join(base_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        with open(os.path.join(models_dir, "best.pt"), "w") as f:
            f.write("weights")

        # 建立模擬 Delta 更新來源
        staging_dir = os.path.join(base_dir, "staging")
        payload_dir = os.path.join(staging_dir, "payload")
        new_internal = os.path.join(payload_dir, "_internal")
        os.makedirs(new_internal, exist_ok=True)

        new_zip = os.path.join(new_internal, "argus.zip")
        with open(new_zip, "w") as f:
            f.write("new_code_v1.1.0")

        new_ver = os.path.join(payload_dir, "version.txt")
        with open(new_ver, "w") as f:
            f.write("1.1.0\n")

        manifest_data = {
            "package_type": "delta",
            "target_version": "1.1.0",
            "min_compatible_base": "1.0.0",
            "arch": "arm64",
            "code_only": True,
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
        with open(os.path.join(staging_dir, "manifest.json"), "w") as f:
            json.dump(manifest_data, f)

        updater = DeltaUpdater(base_dir=base_dir)
        assert not updater.has_patch_backup()

        # 執行 Delta 更新套用
        res_apply = updater.apply_delta(staging_dir, current_base_version="1.0.0")
        assert res_apply["status"] == "ok"
        assert res_apply["target_version"] == "1.1.0"

        # 驗證：argus.zip 與 version.txt 已被更新
        with open(old_zip, "r") as f:
            assert f.read() == "new_code_v1.1.0"
        with open(old_ver_path, "r") as f:
            assert f.read().strip() == "1.1.0"

        # 驗證：底層動態庫與配置完全未受更動
        assert os.path.isfile(torch_lib)
        with open(torch_lib, "r") as f:
            assert f.read() == "torch_binary_data"
        assert os.path.isfile(cv2_lib)
        with open(cv2_lib, "r") as f:
            assert f.read() == "cv2_binary_data"
        with open(cfg_path, "r") as f:
            assert "user_custom_setting: true" in f.read()
        assert os.path.isfile(os.path.join(models_dir, "best.pt"))

        # 驗證：.patch_bak/ 存在並含有舊版備份
        assert updater.has_patch_backup()
        patch_bak = os.path.join(internal_dir, ".patch_bak")
        assert os.path.isfile(os.path.join(patch_bak, "argus.zip"))
        with open(os.path.join(patch_bak, "argus.zip"), "r") as f:
            assert f.read() == "old_code_v1.0.0"

        # 執行局部秒級回滾
        res_rollback = updater.rollback()
        assert res_rollback["status"] == "ok"

        # 驗證：argus.zip 與 version.txt 已還原至舊版
        with open(old_zip, "r") as f:
            assert f.read() == "old_code_v1.0.0"
        with open(old_ver_path, "r") as f:
            assert f.read().strip() == "1.0.0"

        # 驗證：.patch_bak/ 已被清除且產出 .rollback_alert
        assert not updater.has_patch_backup()
        alert_file = os.path.join(base_dir, ".rollback_alert")
        assert os.path.isfile(alert_file)
        with open(alert_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "自動安全回滾至原版本" in content


def test_delta_updater_incompatible_version():
    """驗證當基底版本低於 min_compatible_base 時，apply_delta 拋出 DeltaCompatibilityError。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = tmpdir
        argus_dir = os.path.join(base_dir, "argus_predictor")
        internal_dir = os.path.join(argus_dir, "_internal")
        os.makedirs(internal_dir, exist_ok=True)

        staging_dir = os.path.join(base_dir, "staging")
        payload_dir = os.path.join(staging_dir, "payload")
        os.makedirs(payload_dir, exist_ok=True)

        manifest_data = {
            "package_type": "delta",
            "target_version": "2.0.0",
            "min_compatible_base": "1.5.0",
            "files": {},
        }
        with open(os.path.join(staging_dir, "manifest.json"), "w") as f:
            json.dump(manifest_data, f)

        updater = DeltaUpdater(base_dir=base_dir)
        with pytest.raises(DeltaCompatibilityError, match="版本不相容"):
            updater.apply_delta(staging_dir, current_base_version="1.0.0")


