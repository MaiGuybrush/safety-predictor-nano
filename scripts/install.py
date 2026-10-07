#!/usr/bin/env python3
"""scripts/install.py - Argus Safety Predictor Nano 跨平台獨立安裝與回滾執行器.

職責：
1. 支援全新安裝 (Fresh Install) 與全量解壓升級 (--full <archive_or_dir>)。
2. 支援 Delta 增量補丁升級 (--delta <archive_or_dir>)：
   - 檢驗 manifest.json、package_type == "delta" 與檔案 sha256。
   - 局域原子置換：嚴格保留底層 _internal/ 中的動態函式庫。
   - 自動備份業務模組 argus.zip、Web 模板、手冊及 version.txt 至 _internal/.patch_bak/。
   - 使用標準 os.replace 進行原子替換。
3. 支援快速雙模回滾 (--rollback)：
   - 優先偵測 .patch_bak/ 執行秒級局部還原。
   - 若無 Delta 備份則回退至全量目錄還原 (argus_predictor_bak/)。
   - 還原完成後寫入 .rollback_alert 標記檔。
4. 升級時非破壞性零資料遺失：
   - 嚴格保留使用者既有 config.yaml、models/ 與 logs/。
5. 支援在非 Linux / Windows 環境下跨平台安全執行（含 chmod 權限容錯處理）。
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import zipfile
from typing import Dict, Optional, Tuple

# 確保跨平台主控台環境正確輸出 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="[install.py] %(message)s",
)
logger = logging.getLogger("install")


def compute_sha256(filepath: str) -> str:
    """計算檔案 SHA-256 雜湊值。"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_target_directories(base_dir: str) -> Tuple[str, str]:
    """決定 target_dir (argus_predictor 或 .) 與 internal_dir (_internal)。"""
    target_dir = os.path.join(base_dir, "argus_predictor")
    internal_dir = os.path.join(target_dir, "_internal")

    if os.path.isdir(internal_dir):
        return target_dir, internal_dir

    root_internal = os.path.join(base_dir, "_internal")
    if os.path.isdir(root_internal):
        return base_dir, root_internal

    # 預設位置
    return target_dir, internal_dir


def extract_archive_if_needed(source_path: str, extract_to: str) -> str:
    """若來源為 .tar.gz / .zip 則解壓縮至 extract_to，否則直接返回目錄路徑。"""
    source_path = os.path.abspath(source_path)
    if os.path.isdir(source_path):
        return source_path

    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"指定的套件路徑不存在: {source_path}")

    os.makedirs(extract_to, exist_ok=True)
    if tarfile.is_tarfile(source_path):
        logger.info(f"正在解壓縮 tar 歸檔: {source_path} -> {extract_to}")
        with tarfile.open(source_path, "r:*") as tf:
            tf.extractall(extract_to)
        return extract_to
    elif zipfile.is_zipfile(source_path):
        logger.info(f"正在解壓縮 zip 歸檔: {source_path} -> {extract_to}")
        with zipfile.ZipFile(source_path, "r") as zf:
            zf.extractall(extract_to)
        return extract_to
    else:
        raise ValueError(f"不支援的歸檔檔案格式: {source_path}")


def do_rollback(base_dir: str) -> int:
    """執行自動回滾程序。"""
    logger.info("執行自動回滾程序...")
    target_dir, internal_dir = find_target_directories(base_dir)
    patch_bak = os.path.join(internal_dir, ".patch_bak")

    # 1. 優先檢查是否存在 Delta 增量局部備份 (.patch_bak/)
    if os.path.isdir(patch_bak):
        logger.info(f"偵測到 Delta 增量備份 ({patch_bak}/)，執行局部秒級還原...")

        # 還原 argus.zip
        bak_zip = os.path.join(patch_bak, "argus.zip")
        if os.path.isfile(bak_zip):
            tmp_zip = os.path.join(internal_dir, "argus.zip.tmp")
            shutil.copy2(bak_zip, tmp_zip)
            os.replace(tmp_zip, os.path.join(internal_dir, "argus.zip"))
            logger.info("[✓] argus.zip 已原子還原至原版本")

        # 還原 Web 模板
        bak_web_tpl = os.path.join(patch_bak, "argus", "web", "templates")
        if os.path.isdir(bak_web_tpl):
            dest_tpl = os.path.join(internal_dir, "argus", "web", "templates")
            shutil.rmtree(dest_tpl, ignore_errors=True)
            os.makedirs(os.path.dirname(dest_tpl), exist_ok=True)
            shutil.copytree(bak_web_tpl, dest_tpl)

        bak_tpl = os.path.join(patch_bak, "templates")
        if os.path.isdir(bak_tpl):
            dest_tpl2 = os.path.join(internal_dir, "templates")
            shutil.rmtree(dest_tpl2, ignore_errors=True)
            shutil.copytree(bak_tpl, dest_tpl2)

        # 還原手冊
        bak_docs = os.path.join(patch_bak, "docs")
        if os.path.isdir(bak_docs):
            dest_docs = os.path.join(internal_dir, "docs")
            shutil.rmtree(dest_docs, ignore_errors=True)
            shutil.copytree(bak_docs, dest_docs)

        # 還原 version.txt
        bak_ver = os.path.join(patch_bak, "version.txt")
        if os.path.isfile(bak_ver):
            for v_target in [os.path.join(target_dir, "version.txt"), os.path.join(base_dir, "version.txt")]:
                if os.path.exists(v_target) or v_target == os.path.join(target_dir, "version.txt"):
                    shutil.copy2(bak_ver, v_target)
            with open(bak_ver, "r", encoding="utf-8") as f:
                ver_content = f.read().strip()
            logger.info(f"[✓] 版本資訊已還原至: {ver_content}")

        # 還原維運腳本
        bak_scripts = os.path.join(patch_bak, "scripts")
        if os.path.isdir(bak_scripts):
            dest_scripts = os.path.join(target_dir, "scripts")
            if not os.path.isdir(dest_scripts):
                dest_scripts = os.path.join(base_dir, "scripts")
            os.makedirs(dest_scripts, exist_ok=True)
            for item in os.listdir(bak_scripts):
                s_item = os.path.join(bak_scripts, item)
                d_item = os.path.join(dest_scripts, item)
                if os.path.isfile(s_item):
                    shutil.copy2(s_item, d_item)

        # 清除備份目錄
        shutil.rmtree(patch_bak, ignore_errors=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        alert_file = os.path.join(base_dir, ".rollback_alert")
        with open(alert_file, "w", encoding="utf-8") as f:
            f.write(f"系統未通過健康檢查，已於 {timestamp} 自動安全回滾至原版本\n")

        print("====================================================================")
        print(" [✓] Delta 局部回滾完成！已快速復原至穩定版本。")
        print("====================================================================")
        return 0

    # 2. 若無 Delta 備份，則執行全量備份還原 (argus_predictor_bak/)
    bak_full_dir = os.path.join(base_dir, "argus_predictor_bak")
    if not os.path.isdir(bak_full_dir):
        logger.error("錯誤: 找不到備份目錄 argus_predictor_bak/ 或 .patch_bak/，無法執行回滾。")
        return 1

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target_argus = os.path.join(base_dir, "argus_predictor")
    if os.path.isdir(target_argus):
        failed_dir = os.path.join(base_dir, f"argus_predictor_failed_{timestamp}")
        logger.info(f"隔離損毀版本至 {failed_dir}/")
        os.replace(target_argus, failed_dir)

    logger.info(f"還原備份版本 {bak_full_dir}/ -> {target_argus}/")
    os.replace(bak_full_dir, target_argus)

    # 若備份內有獨立 config.yaml 則還原
    bak_config = os.path.join(bak_full_dir, "config.yaml")
    if os.path.isfile(bak_config):
        shutil.copy2(bak_config, os.path.join(base_dir, "config.yaml"))

    alert_file = os.path.join(base_dir, ".rollback_alert")
    with open(alert_file, "w", encoding="utf-8") as f:
        f.write(f"系統未通過健康檢查，已於 {timestamp} 自動安全回滾至原版本\n")

    logger.info("全量回滾完成！")
    return 0


def do_delta_install(package_path: Optional[str], base_dir: str) -> int:
    """執行 Delta 局部增量安裝與原子置換。"""
    print("====================================================================")
    print(" Argus Safety Predictor Nano Delta 增量更新程序")
    print(" 模式: [增量補丁 (Delta Patch)] 僅更新業務模組與前端靜態資源")
    print("====================================================================")

    target_dir, internal_dir = find_target_directories(base_dir)
    if not os.path.isdir(internal_dir):
        logger.error(
            f"錯誤: 找不到現有安裝環境 ({internal_dir} 不存在)，無法執行 Delta 增量更新。請先執行完整安裝。"
        )
        return 1

    staging_temp_dir = None
    delta_root = None

    if package_path:
        package_path = os.path.abspath(package_path)
        if os.path.isfile(package_path):
            staging_temp_dir = tempfile.mkdtemp(prefix="argus_delta_staging_")
            try:
                delta_root = extract_archive_if_needed(package_path, staging_temp_dir)
            except Exception as e:
                logger.error(f"解壓增量包失敗: {e}")
                if staging_temp_dir:
                    shutil.rmtree(staging_temp_dir, ignore_errors=True)
                return 1
        elif os.path.isdir(package_path):
            delta_root = package_path
        else:
            logger.error(f"錯誤: 指定之 Delta 增量包路徑不存在: {package_path}")
            return 1
    else:
        candidates = [
            os.path.join(base_dir, "updates", "staging"),
            base_dir,
        ]
        for cand in candidates:
            if os.path.isfile(os.path.join(cand, "manifest.json")):
                delta_root = cand
                break
        if not delta_root:
            logger.error("錯誤: 未指定 Delta 增量包且找不到暫存目錄 updates/staging/manifest.json")
            return 1

    manifest_path = os.path.join(delta_root, "manifest.json")
    if not os.path.isfile(manifest_path):
        logger.error("錯誤: 找不到 manifest.json，不是有效的 Delta 增量包。")
        if staging_temp_dir:
            shutil.rmtree(staging_temp_dir, ignore_errors=True)
        return 1

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        logger.error(f"解析 manifest.json 失敗: {e}")
        if staging_temp_dir:
            shutil.rmtree(staging_temp_dir, ignore_errors=True)
        return 1

    if manifest.get("package_type") != "delta":
        logger.error("錯誤: manifest.json 標記之 package_type 不是 delta。")
        if staging_temp_dir:
            shutil.rmtree(staging_temp_dir, ignore_errors=True)
        return 1

    payload_dir = os.path.join(delta_root, "payload")
    if not os.path.isdir(payload_dir):
        logger.error("錯誤: Delta 增量包內找不到 payload/ 目錄。")
        if staging_temp_dir:
            shutil.rmtree(staging_temp_dir, ignore_errors=True)
        return 1

    # 校驗 Manifest 檔案雜湊
    files_manifest: Dict[str, Dict[str, object]] = manifest.get("files", {})
    for rel_path, meta in files_manifest.items():
        expected_sha = meta.get("sha256")
        expected_size = meta.get("size")
        full_fpath = os.path.join(payload_dir, os.path.normpath(rel_path))
        if not os.path.isfile(full_fpath):
            logger.error(f"檔案完整性錯誤: 清單內檔案不存在 {rel_path}")
            if staging_temp_dir:
                shutil.rmtree(staging_temp_dir, ignore_errors=True)
            return 1
        if expected_size is not None and os.path.getsize(full_fpath) != expected_size:
            logger.error(f"檔案大小不符: {rel_path}")
            if staging_temp_dir:
                shutil.rmtree(staging_temp_dir, ignore_errors=True)
            return 1
        if expected_sha and compute_sha256(full_fpath) != expected_sha:
            logger.error(f"SHA-256 雜湊值不符: {rel_path}")
            if staging_temp_dir:
                shutil.rmtree(staging_temp_dir, ignore_errors=True)
            return 1

    # 建立 .patch_bak/ 局部備份
    patch_bak = os.path.join(internal_dir, ".patch_bak")
    logger.info(f"正在建立 Delta 備份至 {patch_bak}/...")
    shutil.rmtree(patch_bak, ignore_errors=True)
    os.makedirs(patch_bak, exist_ok=True)

    current_zip = os.path.join(internal_dir, "argus.zip")
    if os.path.isfile(current_zip):
        shutil.copy2(current_zip, os.path.join(patch_bak, "argus.zip"))

    cur_web_tpl = os.path.join(internal_dir, "argus", "web", "templates")
    if os.path.isdir(cur_web_tpl):
        dest_bak_tpl = os.path.join(patch_bak, "argus", "web", "templates")
        os.makedirs(os.path.dirname(dest_bak_tpl), exist_ok=True)
        shutil.copytree(cur_web_tpl, dest_bak_tpl)

    cur_tpl = os.path.join(internal_dir, "templates")
    if os.path.isdir(cur_tpl):
        shutil.copytree(cur_tpl, os.path.join(patch_bak, "templates"))

    cur_docs = os.path.join(internal_dir, "docs")
    if os.path.isdir(cur_docs):
        shutil.copytree(cur_docs, os.path.join(patch_bak, "docs"))

    for ver_src in [os.path.join(target_dir, "version.txt"), os.path.join(base_dir, "version.txt")]:
        if os.path.isfile(ver_src):
            shutil.copy2(ver_src, os.path.join(patch_bak, "version.txt"))
            break

    cur_scripts = os.path.join(target_dir, "scripts")
    if not os.path.isdir(cur_scripts):
        cur_scripts = os.path.join(base_dir, "scripts")
    if os.path.isdir(cur_scripts):
        dest_bak_scripts = os.path.join(patch_bak, "scripts")
        os.makedirs(dest_bak_scripts, exist_ok=True)
        for item in os.listdir(cur_scripts):
            sf = os.path.join(cur_scripts, item)
            if os.path.isfile(sf):
                shutil.copy2(sf, os.path.join(dest_bak_scripts, item))

    # 執行局域原子替換
    logger.info(f"正在套用 Delta 載荷至 {target_dir} (底層重型動態函式庫嚴格保留)...")

    # 1. 原子替換 argus.zip
    new_zip = os.path.join(payload_dir, "_internal", "argus.zip")
    if os.path.isfile(new_zip):
        tmp_zip = os.path.join(internal_dir, "argus.zip.tmp")
        shutil.copy2(new_zip, tmp_zip)
        os.replace(tmp_zip, os.path.join(internal_dir, "argus.zip"))
        logger.info("[✓] argus.zip 已原子替換至新版本")

    # 2. 替換 Web 模板
    new_web_tpl = os.path.join(payload_dir, "_internal", "argus", "web", "templates")
    if os.path.isdir(new_web_tpl):
        dest_tpl = os.path.join(internal_dir, "argus", "web", "templates")
        os.makedirs(os.path.dirname(dest_tpl), exist_ok=True)
        shutil.copytree(new_web_tpl, dest_tpl, dirs_exist_ok=True)

    new_root_tpl = os.path.join(payload_dir, "_internal", "templates")
    if os.path.isdir(new_root_tpl):
        dest_root_tpl = os.path.join(internal_dir, "templates")
        os.makedirs(dest_root_tpl, exist_ok=True)
        shutil.copytree(new_root_tpl, dest_root_tpl, dirs_exist_ok=True)

    # 3. 替換手冊
    new_manual = os.path.join(payload_dir, "_internal", "docs", "user-manual", "book")
    if os.path.isdir(new_manual):
        dest_manual = os.path.join(internal_dir, "docs", "user-manual", "book")
        os.makedirs(dest_manual, exist_ok=True)
        shutil.copytree(new_manual, dest_manual, dirs_exist_ok=True)

    # 4. 替換版本資訊
    new_ver = os.path.join(payload_dir, "version.txt")
    if os.path.isfile(new_ver):
        shutil.copy2(new_ver, os.path.join(target_dir, "version.txt"))
        if os.path.isfile(os.path.join(base_dir, "version.txt")):
            shutil.copy2(new_ver, os.path.join(base_dir, "version.txt"))
        with open(new_ver, "r", encoding="utf-8") as f:
            v_str = f.read().strip()
        logger.info(f"[✓] 版本資訊已更新至: {v_str}")

    # 5. 替換維運腳本
    new_scripts = os.path.join(payload_dir, "scripts")
    if os.path.isdir(new_scripts):
        dest_scripts = os.path.join(target_dir, "scripts")
        if not os.path.isdir(dest_scripts):
            dest_scripts = os.path.join(base_dir, "scripts")
        os.makedirs(dest_scripts, exist_ok=True)
        for item in os.listdir(new_scripts):
            sf = os.path.join(new_scripts, item)
            df = os.path.join(dest_scripts, item)
            if os.path.isfile(sf):
                shutil.copy2(sf, df)
                if hasattr(os, "chmod") and (item.endswith(".sh") or item.endswith(".py")):
                    try:
                        os.chmod(df, os.stat(df).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    except Exception:
                        pass
        logger.info("[✓] 維運腳本 (scripts/) 已更新至新版本")

    # 清除解壓暫存
    if staging_temp_dir:
        shutil.rmtree(staging_temp_dir, ignore_errors=True)

    print("====================================================================")
    print(" [✓] Delta 增量補丁套用完成！")
    print(" 既有重型動態函式庫、config.yaml、models/ 與 logs/ 皆完整保留未受更動。")
    print(f" 備份已留存於 {patch_bak}/ (若需還原可執行 install.py --rollback)")
    print("====================================================================")
    return 0


def do_full_install(package_path: Optional[str], base_dir: str) -> int:
    """執行全量升級或初次安裝模式。"""
    target_dir = os.path.join(base_dir, "argus_predictor")
    config_file = os.path.join(base_dir, "config.yaml")
    is_upgrade = os.path.isdir(target_dir) or os.path.isfile(config_file)

    print("====================================================================")
    print(" Argus Safety Predictor Nano 部署與安裝程序")
    if is_upgrade:
        print(" 模式: [全量升級模式 (Full Upgrade)] 零資料遺失防護已啟動")
    else:
        print(" 模式: [初次安裝 (Fresh Install)]")
    print("====================================================================")

    # 1. 全量升級備份
    if is_upgrade and os.path.isdir(target_dir):
        bak_dir = os.path.join(base_dir, "argus_predictor_bak")
        logger.info(f"正在備份目前運行環境至 {bak_dir}/...")
        shutil.rmtree(bak_dir, ignore_errors=True)
        shutil.copytree(target_dir, bak_dir)
        if os.path.isfile(config_file):
            shutil.copy2(config_file, os.path.join(bak_dir, "config.yaml"))
        logger.info("備份建立完成。")

    # 2. 解壓載荷
    staging_temp_dir = None
    payload_dir = None

    if package_path:
        package_path = os.path.abspath(package_path)
        if os.path.isfile(package_path):
            staging_temp_dir = tempfile.mkdtemp(prefix="argus_full_staging_")
            try:
                payload_dir = extract_archive_if_needed(package_path, staging_temp_dir)
            except Exception as e:
                logger.error(f"解壓全量更新包失敗: {e}")
                if staging_temp_dir:
                    shutil.rmtree(staging_temp_dir, ignore_errors=True)
                return 1
        elif os.path.isdir(package_path):
            payload_dir = package_path
        else:
            logger.error(f"錯誤: 指定之全量套件路徑不存在: {package_path}")
            return 1
    else:
        for cand in [
            os.path.join(base_dir, "payload"),
            os.path.join(base_dir, "updates", "staging", "payload"),
            os.path.join(base_dir, "updates", "staging"),
        ]:
            if os.path.isdir(cand):
                payload_dir = cand
                break

    if payload_dir and os.path.isdir(payload_dir):
        logger.info(f"正在從 {payload_dir} 同步最新檔案至 {target_dir}/...")
        os.makedirs(target_dir, exist_ok=True)
        shutil.copytree(payload_dir, target_dir, dirs_exist_ok=True)

    if staging_temp_dir:
        shutil.rmtree(staging_temp_dir, ignore_errors=True)

    # 3. 配置檔防覆蓋保護
    if not os.path.isfile(config_file):
        default_cfg = os.path.join(target_dir, "config.default.yaml")
        if os.path.isfile(default_cfg):
            logger.info("建立初始 config.yaml...")
            shutil.copy2(default_cfg, config_file)
    else:
        logger.info("保留既有使用者自訂 config.yaml，不予覆蓋。")

    # 建立目錄
    for d in ["models", "logs", os.path.join("updates", "staging")]:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)

    print("====================================================================")
    print(" [✓] 安裝/升級處理完成！")
    print("====================================================================")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Argus Safety Predictor Nano 跨平台獨立安裝與回滾執行器"
    )
    parser.add_argument("--delta", nargs="?", const="", help="套用 Delta 增量補丁 (可選指定 .tar.gz 路徑或目錄)")
    parser.add_argument("--rollback", action="store_true", help="執行快速回滾程序 (支援 Delta 秒級與全量備份)")
    parser.add_argument("--full", nargs="?", const="", help="執行全量更新 (可選指定安裝包路徑或目錄)")
    parser.add_argument("-y", "--yes", "--non-interactive", action="store_true", help="非互動模式")
    parser.add_argument("--dir", default=".", help="目標安裝基準目錄 (預設為當前目錄)")

    args = parser.parse_args()

    base_dir = os.path.abspath(args.dir)

    if args.rollback:
        return do_rollback(base_dir)
    elif args.delta is not None:
        delta_path = args.delta if args.delta else None
        return do_delta_install(delta_path, base_dir)
    elif args.full is not None:
        full_path = args.full if args.full else None
        return do_full_install(full_path, base_dir)
    else:
        # 預設模式：判定全量安裝/升級
        return do_full_install(None, base_dir)


if __name__ == "__main__":
    sys.exit(main())
