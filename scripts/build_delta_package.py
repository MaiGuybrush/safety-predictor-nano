#!/usr/bin/env python3
"""scripts/build_delta_package.py - Argus Delta 增量更新包建置工具.

職責：
1. 編譯 `src/argus` 為 bytecode zip 檔 (`argus.zip`)。
2. 收集 Web 模板、mdBook 使用者手冊及版本識別資訊。
3. 產生 `manifest.json` 記錄 target_version、min_compatible_base 與各檔案 SHA256 雜湊。
4. 打包產出 `dist/argus_delta-v{VERSION}-{ARCH}.tar.gz` 及其 `.sha256` 校驗檔。
5. 確保發布包體積符合標準（含手冊 < 3.5MB，純代碼修復 < 250KB）。
"""

import argparse
import datetime
import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from typing import Dict, Optional, Tuple


def compute_sha256(filepath: str) -> str:
    """計算檔案 SHA-256 雜湊值。"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_project_version(src_dir: str = "src") -> str:
    """自 src/argus/__init__.py 解析目前應用程式版本號。"""
    init_path = os.path.join(src_dir, "argus", "__init__.py")
    if os.path.isfile(init_path):
        with open(init_path, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    return "1.0.0"


def build_argus_zip(
    output_zip: str,
    src_dir: str = "src",
    include_source: bool = True,
) -> str:
    """將 src/argus 編譯為 bytecode zip 檔。

    Args:
        output_zip: 輸出的 zip 檔案路徑。
        src_dir: 來源程式碼目錄 (預設: "src")。
        include_source: 是否在 zip 中保留 .py 原始碼（有利於 Traceback 行號顯示）。

    Returns:
        str: 產出之 zip 檔案絕對路徑。
    """
    output_zip = os.path.abspath(output_zip)
    os.makedirs(os.path.dirname(output_zip), exist_ok=True)
    argus_root = os.path.join(src_dir, "argus")

    if not os.path.isdir(argus_root):
        raise FileNotFoundError(f"找不到 argus 業務模組目錄: {argus_root}")

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(
            output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            for root, _, files in os.walk(argus_root):
                for file in files:
                    if not file.endswith(".py"):
                        continue
                    full_path = os.path.join(root, file)
                    rel_from_src = os.path.relpath(full_path, src_dir)
                    # 統一以正斜線儲存 zip 路徑
                    zip_arcname_pyc = rel_from_src.replace("\\", "/") + "c"
                    zip_arcname_py = rel_from_src.replace("\\", "/")

                    # 編譯 bytecode
                    cfile_name = f"{file}c"
                    cfile_path = os.path.join(temp_dir, cfile_name)
                    try:
                        py_compile.compile(
                            full_path,
                            cfile_path,
                            doraise=True,
                            optimize=0,
                        )
                        zf.write(cfile_path, arcname=zip_arcname_pyc)
                    finally:
                        if os.path.exists(cfile_path):
                            try:
                                os.remove(cfile_path)
                            except OSError:
                                pass

                    if include_source:
                        zf.write(full_path, arcname=zip_arcname_py)

    return output_zip


def build_delta_package(
    version: Optional[str] = None,
    min_compatible_base: Optional[str] = None,
    arch: str = "arm64",
    output_dir: str = "dist",
    code_only: bool = False,
    include_manual: bool = True,
    include_templates: bool = True,
    src_dir: str = "src",
) -> Tuple[str, str]:
    """建置 Delta 增量補丁封裝包 (.tar.gz) 與其 .sha256 校驗檔。

    Args:
        version: 目標版本號（預設自 __init__.py 取得）。
        min_compatible_base: 最低相容基礎版號（預設 "1.0.0"）。
        arch: 目標架構（預設 "arm64"）。
        output_dir: 輸出目錄（預設 "dist"）。
        code_only: 純代碼修復模式（不含 manual 與 templates，體積 < 250KB）。
        include_manual: 是否收錄 mdBook 使用者手冊。
        include_templates: 是否收錄 Web templates。
        src_dir: 原始碼根目錄。

    Returns:
        Tuple[str, str]: (tar_gz_path, sha256_path)
    """
    if not version:
        version = get_project_version(src_dir)
    if not min_compatible_base:
        min_compatible_base = "1.0.0"

    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    package_name = f"argus_delta-v{version}-{arch}"
    tar_path = os.path.join(output_dir, f"{package_name}.tar.gz")
    sha256_path = os.path.join(output_dir, f"{package_name}.tar.gz.sha256")

    with tempfile.TemporaryDirectory() as staging_dir:
        payload_dir = os.path.join(staging_dir, "payload")
        internal_dir = os.path.join(payload_dir, "_internal")
        os.makedirs(internal_dir, exist_ok=True)

        # 1. 建立 argus.zip
        zip_output_path = os.path.join(internal_dir, "argus.zip")
        build_argus_zip(zip_output_path, src_dir=src_dir, include_source=True)

        # 2. 版本識別檔
        version_txt_path = os.path.join(payload_dir, "version.txt")
        with open(version_txt_path, "w", encoding="utf-8") as f:
            f.write(f"{version}\n")

        # 3. 模板收集
        if not code_only and include_templates:
            # src/argus/web/templates
            src_tpl = os.path.join(src_dir, "argus", "web", "templates")
            if os.path.isdir(src_tpl):
                dest_tpl1 = os.path.join(internal_dir, "argus", "web", "templates")
                os.makedirs(os.path.dirname(dest_tpl1), exist_ok=True)
                shutil.copytree(src_tpl, dest_tpl1, dirs_exist_ok=True)

            # templates/
            root_tpl = os.path.abspath("templates")
            if os.path.isdir(root_tpl):
                dest_tpl2 = os.path.join(internal_dir, "templates")
                shutil.copytree(root_tpl, dest_tpl2, dirs_exist_ok=True)

        # 4. mdBook 離線手冊收集
        if not code_only and include_manual:
            book_dir = os.path.join("docs", "user-manual", "book")
            if not os.path.isdir(book_dir):
                # 嘗試執行 mdbook build
                manual_src = os.path.join("docs", "user-manual")
                if os.path.isdir(manual_src):
                    try:
                        subprocess.run(
                            ["mdbook", "build", manual_src],
                            check=True,
                            capture_output=True,
                        )
                    except Exception:
                        pass
            if os.path.isdir(book_dir):
                dest_book = os.path.join(internal_dir, "docs", "user-manual", "book")
                os.makedirs(os.path.dirname(dest_book), exist_ok=True)
                shutil.copytree(book_dir, dest_book, dirs_exist_ok=True)

        # 5. 掃描收集 payload 檔案清單並計算 SHA-256
        files_manifest: Dict[str, Dict[str, object]] = {}
        for root, _, files in os.walk(payload_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_to_payload = os.path.relpath(full_path, payload_dir).replace("\\", "/")
                file_sha = compute_sha256(full_path)
                file_size = os.path.getsize(full_path)
                files_manifest[rel_to_payload] = {
                    "sha256": file_sha,
                    "size": file_size,
                }

        # 6. 產生 manifest.json
        manifest_data = {
            "package_type": "delta",
            "target_version": version,
            "min_compatible_base": min_compatible_base,
            "arch": arch,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "code_only": code_only,
            "file_count": len(files_manifest),
            "files": files_manifest,
        }

        manifest_path = os.path.join(staging_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        # 7. 打包成 .tar.gz (包含 manifest.json 與 payload/)
        with tarfile.open(tar_path, "w:gz", compresslevel=9) as tf:
            tf.add(manifest_path, arcname="manifest.json")
            tf.add(payload_dir, arcname="payload")

    # 8. 產出 .sha256 檔
    archive_sha256 = compute_sha256(tar_path)
    with open(sha256_path, "w", encoding="utf-8") as f:
        f.write(f"{archive_sha256}  {os.path.basename(tar_path)}\n")

    # 9. 體積校驗與紀錄
    package_size_bytes = os.path.getsize(tar_path)
    size_mb = package_size_bytes / (1024 * 1024)
    size_kb = package_size_bytes / 1024

    if code_only:
        max_kb = 250
        if size_kb > max_kb:
            print(f"警告: 純代碼增量包大小 ({size_kb:.2f} KB) 超過建議上限 ({max_kb} KB)")
    else:
        max_mb = 3.5
        if size_mb > max_mb:
            print(f"警告: 完整增量包大小 ({size_mb:.2f} MB) 超過建議上限 ({max_mb} MB)")

    # 確保 Windows cp950 等主控台不會因 Unicode 字符報錯
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:
            pass

    print("====================================================================")
    print(" [OK] Delta 增量更新包建置成功！")
    print(f" 檔案名稱: {os.path.basename(tar_path)}")
    print(f" 檔案路徑: {tar_path}")
    print(f" 檔案大小: {size_mb:.2f} MB ({size_kb:.1f} KB)")
    print(f" SHA-256 : {archive_sha256}")
    print(f" 校驗檔案: {sha256_path}")
    print(f" 目標版本: v{version} (相容基準 >= v{min_compatible_base})")
    print(f" 包含檔案: {len(files_manifest)} 個項目")
    print("====================================================================")

    return tar_path, sha256_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Argus Safety Predictor Nano - Delta 增量更新包建置工具"
    )
    parser.add_argument("-v", "--version", help="指定目標版本號 (預設自 __init__.py 讀取)")
    parser.add_argument("--min-compatible-base", default="1.0.0", help="指定最低相容基準版本")
    parser.add_argument("--arch", default="arm64", help="指定目標架構 (預設: arm64)")
    parser.add_argument("-o", "--output-dir", default="dist", help="輸出目錄 (預設: dist)")
    parser.add_argument("--code-only", action="store_true", help="純代碼修復模式 (< 250KB)")
    parser.add_argument("--no-manual", action="store_true", help="不收錄 mdBook 使用者手冊")
    parser.add_argument("--no-templates", action="store_true", help="不收錄 Web templates")
    parser.add_argument("--zip-only", help="僅建置 argus.zip 輸出至指定路徑並退出")

    args = parser.parse_args()

    if args.zip_only:
        out = build_argus_zip(args.zip_only)
        print(f"[OK] argus.zip 建立成功: {out}")
        return 0

    include_manual = not (args.code_only or args.no_manual)
    include_templates = not (args.code_only or args.no_templates)

    build_delta_package(
        version=args.version,
        min_compatible_base=args.min_compatible_base,
        arch=args.arch,
        output_dir=args.output_dir,
        code_only=args.code_only,
        include_manual=include_manual,
        include_templates=include_templates,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
