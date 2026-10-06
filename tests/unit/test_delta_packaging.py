"""tests/unit/test_delta_packaging.py - Unit tests for Delta packaging and zipimport decoupling.

Verifies:
1. Compilation of `src/argus` into bytecode zip file (`argus.zip`).
2. Mounting of `argus.zip` via zipimport in `main.py` and loading of domain modules.
3. Decoupling configuration in `argus_predictor.spec`.
4. Automated building of Delta package (`argus_delta-v{VERSION}-arm64.tar.gz`) and `.sha256`.
5. Delta package size constraints (< 3.5MB full, < 250KB code-only).
6. Manifest schema, version metadata, and file checksum verification.
"""

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile
import pytest

from main import mount_argus_zip


def _compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class TestDeltaPackaging:
    """Tests for Delta package build script and packaging decoupler."""

    @pytest.fixture(autouse=True)
    def setup_tmpdir(self, tmp_path):
        self.tmp_dir = str(tmp_path)

    def test_build_argus_zip(self):
        from scripts.build_delta_package import build_argus_zip

        output_zip = os.path.join(self.tmp_dir, "argus.zip")
        built_path = build_argus_zip(output_zip, src_dir="src")

        assert os.path.isfile(built_path)
        assert os.path.getsize(built_path) > 50000  # At least 50KB

        with zipfile.ZipFile(built_path, "r") as zf:
            namelist = zf.namelist()
            # Must contain compiled bytecode
            assert any(name.startswith("argus/") and name.endswith(".pyc") for name in namelist)
            assert "argus/__init__.pyc" in namelist or "argus/__init__.py" in namelist
            assert "argus/main.pyc" in namelist or "argus/main.py" in namelist
            assert "argus/core/config_manager.pyc" in namelist or "argus/core/config_manager.py" in namelist
            assert "argus/web/web_ui.pyc" in namelist or "argus/web/web_ui.py" in namelist

    def test_zipimport_mount_and_module_loading(self):
        from scripts.build_delta_package import build_argus_zip

        # Create isolated zip with a dummy version
        output_zip = os.path.join(self.tmp_dir, "isolated_argus.zip")
        build_argus_zip(output_zip, src_dir="src")

        # Mount the zip explicitly
        mounted = mount_argus_zip(output_zip)
        assert mounted is True
        assert output_zip in sys.path or os.path.normpath(os.path.abspath(output_zip)) in sys.path

        # Verify domain modules can be loaded from zip
        import argus
        import argus.core.config_manager
        import argus.vision.inference_engine
        import argus.compliance.compliance_engine

        assert hasattr(argus, "__version__")
        assert argus.core.config_manager.ConfigManager is not None

    def test_spec_file_business_code_decoupled(self):
        """Verify argus_predictor.spec decouples argus business logic from PYZ."""
        spec_path = os.path.abspath("argus_predictor.spec")
        assert os.path.isfile(spec_path)

        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Analysis must exclude argus
        assert "excludes=" in content
        assert "'argus'" in content

        # 2. Pure list filtering must purge any argus modules from PYZ
        assert "a.pure = [x for x in a.pure if not x[0].startswith('argus')]" in content

        # 3. Must use onedir COLLECT
        assert "COLLECT(" in content

        # 4. Entrypoint must be main.py
        assert "['main.py']" in content

        # 5. Must include deployment scripts in datas and copy to dist scripts dir
        assert "'scripts/run.sh'" in content
        assert "'scripts/install.sh'" in content
        assert "'scripts/ask_and_report.sh'" in content
        assert "dist_scripts" in content


    def test_version_alignment_guardrail(self):
        """Verify build_delta_package raises ValueError when version mismatches src/argus/__init__.py."""
        from scripts.build_delta_package import build_delta_package

        dist_dir = os.path.join(self.tmp_dir, "dist_mismatch")
        with pytest.raises(ValueError, match="版本衝突錯誤"):
            build_delta_package(
                version="9.9.9",
                src_dir="src",
                output_dir=dist_dir,
            )

    def test_build_delta_package_full(self):
        """Verify building full delta package with templates and mdbook."""
        from scripts.build_delta_package import build_delta_package, get_project_version

        # 準備獨立自訂版本的 src_dir 以模擬 bump version 後的建置
        custom_src = os.path.join(self.tmp_dir, "custom_src")
        shutil.copytree("src", custom_src)
        init_file = os.path.join(custom_src, "argus", "__init__.py")
        with open(init_file, "w", encoding="utf-8") as f:
            f.write('__version__ = "1.2.3"\n')

        dist_dir = os.path.join(self.tmp_dir, "dist")
        tar_path, sha256_path = build_delta_package(
            version="1.2.3",
            min_compatible_base="1.0.0",
            arch="arm64",
            output_dir=dist_dir,
            code_only=False,
            include_manual=True,
            include_templates=True,
            src_dir=custom_src,
        )

        assert os.path.isfile(tar_path)
        assert os.path.isfile(sha256_path)
        assert tar_path.endswith("argus_delta-v1.2.3-arm64.tar.gz")
        assert sha256_path.endswith(".sha256")

        # Check sha256 checksum file content
        with open(sha256_path, "r", encoding="utf-8") as f:
            checksum_line = f.read().strip()
        expected_sha = _compute_sha256(tar_path)
        assert expected_sha in checksum_line

        # Check file size limit (< 3.5 MB)
        tar_size_mb = os.path.getsize(tar_path) / (1024 * 1024)
        assert tar_size_mb < 3.5, f"Delta package size {tar_size_mb:.2f} MB exceeds 3.5 MB"

        # Inspect archive contents
        with tarfile.open(tar_path, "r:gz") as tf:
            names = tf.getnames()
            assert "manifest.json" in names
            assert "payload/_internal/argus.zip" in names
            assert "payload/version.txt" in names
            assert any(name.startswith("payload/scripts/") for name in names)

            # Extract and inspect manifest.json
            manifest_file = tf.extractfile("manifest.json")
            assert manifest_file is not None
            manifest = json.loads(manifest_file.read().decode("utf-8"))

            assert manifest["package_type"] == "delta"
            assert manifest["target_version"] == "1.2.3"
            assert manifest["min_compatible_base"] == "1.0.0"
            assert manifest["arch"] == "arm64"
            assert "files" in manifest
            assert "_internal/argus.zip" in manifest["files"]

            # Validate internal argus.zip SHA256 matches manifest entry
            argus_zip_entry = manifest["files"]["_internal/argus.zip"]
            argus_zip_file = tf.extractfile("payload/_internal/argus.zip")
            assert argus_zip_file is not None
            zip_bytes = argus_zip_file.read()
            calc_zip_sha = hashlib.sha256(zip_bytes).hexdigest()
            assert calc_zip_sha == argus_zip_entry["sha256"]

            # Validate __version__ injected into argus.zip
            import io
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as inner_zf:
                assert "argus/__init__.py" in inner_zf.namelist()
                init_content = inner_zf.read("argus/__init__.py").decode("utf-8")
                assert '__version__ = "1.2.3"' in init_content

    def test_build_delta_package_code_only(self):
        """Verify building pure code-fix delta package (< 250 KB)."""
        from scripts.build_delta_package import build_delta_package

        custom_src = os.path.join(self.tmp_dir, "custom_src_code_only")
        shutil.copytree("src", custom_src)
        init_file = os.path.join(custom_src, "argus", "__init__.py")
        with open(init_file, "w", encoding="utf-8") as f:
            f.write('__version__ = "1.2.4"\n')

        dist_dir = os.path.join(self.tmp_dir, "dist_code_only")
        tar_path, sha256_path = build_delta_package(
            version="1.2.4",
            min_compatible_base="1.0.0",
            arch="arm64",
            output_dir=dist_dir,
            code_only=True,
            src_dir=custom_src,
        )

        assert os.path.isfile(tar_path)
        tar_size_kb = os.path.getsize(tar_path) / 1024
        assert tar_size_kb < 250, f"Code-only delta package size {tar_size_kb:.2f} KB exceeds 250 KB"

        # Check archive contents
        with tarfile.open(tar_path, "r:gz") as tf:
            names = tf.getnames()
            assert "manifest.json" in names
            assert "payload/_internal/argus.zip" in names
            # Manual should NOT be included in code-only mode
            assert not any("user-manual" in name for name in names)

            manifest_file = tf.extractfile("manifest.json")
            assert manifest_file is not None
            manifest = json.loads(manifest_file.read().decode("utf-8"))
            assert manifest["target_version"] == "1.2.4"
            assert manifest["code_only"] is True

    def test_cli_execution(self):
        """Verify executing scripts/build_delta_package.py via CLI."""
        import subprocess
        from scripts.build_delta_package import get_project_version

        curr_ver = get_project_version("src")
        out_dir = os.path.join(self.tmp_dir, "cli_test_out")
        cmd = [
            sys.executable,
            "scripts/build_delta_package.py",
            "-v",
            curr_ver,
            "--code-only",
            "-o",
            out_dir,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"CLI build failed: {res.stderr}"
        expected_tar = os.path.join(out_dir, f"argus_delta-v{curr_ver}-arm64.tar.gz")
        assert os.path.isfile(expected_tar)
        assert os.path.isfile(expected_tar + ".sha256")

