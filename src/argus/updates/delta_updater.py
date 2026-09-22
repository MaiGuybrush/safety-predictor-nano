"""delta_updater.py - Argus Delta 增量更新引擎與原子回滾管理器.

職責：
1. Delta 增量包 (manifest.json, payload/) 規格驗證、相容性判定與完整性校驗。
2. 局域原子置換 (In-place Atomic Delta Replacement)：
   - 備份現行 _internal/argus.zip、Web 模板、手冊與 version.txt 至 _internal/.patch_bak/。
   - 嚴格保留底層重型動態函式庫 (PyTorch、OpenCV、NumPy 等) 與使用者配置 (config.yaml, models/, logs/) 不動。
   - 透過暫存檔與原子搬移替換新版 argus.zip 及靜態資源。
3. 輕量秒級局部回滾 (Local Fast Rollback)：
   - 若偵測到 .patch_bak/，秒級精確還原舊版業務模組與靜態資源（免搬移 1GB 全量目錄）。
   - 產出 .rollback_alert 告警標記。
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("system")


def compute_sha256(filepath: str) -> str:
    """計算檔案 SHA-256 雜湊值。"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class DeltaManifestError(Exception):
    """Delta 清單檔案驗證錯誤。"""
    pass


class DeltaCompatibilityError(Exception):
    """Delta 增量包相容性錯誤。"""
    pass


class DeltaManifest:
    """Delta 增量包之 manifest.json 資料結構與驗證器。"""

    def __init__(
        self,
        target_version: str,
        min_compatible_base: str = "1.0.0",
        arch: str = "arm64",
        package_type: str = "delta",
        created_at: Optional[str] = None,
        code_only: bool = False,
        file_count: int = 0,
        files: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.target_version = target_version
        self.min_compatible_base = min_compatible_base
        self.arch = arch
        self.package_type = package_type
        self.created_at = created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.code_only = code_only
        self.file_count = file_count
        self.files = files or {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeltaManifest":
        """從字典反序列化並執行完整性檢查。"""
        if not isinstance(data, dict):
            raise DeltaManifestError("manifest 內容必須為 JSON 物件")

        pkg_type = data.get("package_type")
        if pkg_type != "delta":
            raise DeltaManifestError(f"非 Delta 增量包 (package_type={pkg_type})")

        target_version = data.get("target_version")
        if not target_version or not isinstance(target_version, str):
            raise DeltaManifestError("manifest.json 缺少有效的 target_version")

        min_base = data.get("min_compatible_base", "1.0.0")
        arch = data.get("arch", "arm64")
        created_at = data.get("created_at")
        code_only = bool(data.get("code_only", False))
        files = data.get("files", {})

        return cls(
            target_version=target_version,
            min_compatible_base=min_base,
            arch=arch,
            package_type=pkg_type,
            created_at=created_at,
            code_only=code_only,
            file_count=len(files),
            files=files,
        )

    @classmethod
    def from_manifest_file(cls, filepath: str) -> "DeltaManifest":
        """讀取本機 manifest.json 檔案。"""
        if not os.path.isfile(filepath):
            raise DeltaManifestError(f"找不到 manifest.json: {filepath}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as ex:
            raise DeltaManifestError(f"manifest.json 格式無效: {ex}") from ex

    @classmethod
    def from_archive(cls, archive_path: str) -> "DeltaManifest":
        """自 .tar.gz 壓縮檔中提取並解析 manifest.json。"""
        if not os.path.isfile(archive_path):
            raise FileNotFoundError(f"找不到更新封包檔案: {archive_path}")
        try:
            with tarfile.open(archive_path, "r:*") as tar:
                try:
                    member = tar.getmember("manifest.json")
                except KeyError:
                    raise DeltaManifestError("封包內缺少 manifest.json 檔") from None

                f = tar.extractfile(member)
                if f is None:
                    raise DeltaManifestError("無法讀取封包內之 manifest.json")
                data = json.load(f)
                return cls.from_dict(data)
        except tarfile.TarError as ex:
            raise DeltaManifestError(f"壓縮檔讀取異常: {ex}") from ex

    def is_compatible(self, base_version: str) -> bool:
        """依據 SemVer 規則驗證目前基底版本是否相容於 min_compatible_base。"""
        def parse_v(v: str) -> Tuple[int, ...]:
            clean = v.lstrip("vV").split("-")[0].split("+")[0]
            parts = clean.split(".")
            res = []
            for p in parts:
                res.append(int(p) if p.isdigit() else 0)
            while len(res) < 3:
                res.append(0)
            return tuple(res[:3])

        try:
            current_t = parse_v(base_version)
            min_t = parse_v(self.min_compatible_base)
            return current_t >= min_t
        except Exception:
            return True

    def verify_payload(self, payload_dir: str) -> Tuple[bool, List[str]]:
        """檢查 payload/ 內的各檔案雜湊是否與 manifest.json 一致。"""
        mismatches = []
        for rel_path, meta in self.files.items():
            full_path = os.path.join(payload_dir, rel_path)
            if not os.path.isfile(full_path):
                mismatches.append(f"缺少檔案: {rel_path}")
                continue

            expected_sha = meta.get("sha256")
            if expected_sha:
                actual_sha = compute_sha256(full_path)
                if actual_sha.lower() != expected_sha.lower():
                    mismatches.append(
                        f"雜湊不符 {rel_path}: 預期 {expected_sha}，實際 {actual_sha}"
                    )
        return len(mismatches) == 0, mismatches


class DeltaUpdater:
    """Delta 增量替換引擎與回滾執行器。"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = os.path.abspath(base_dir)

    def resolve_target_dirs(self) -> Tuple[str, str]:
        """判定目標運行目錄與 _internal 路徑。

        Returns:
            Tuple[str, str]: (target_dir, internal_dir)
        """
        argus_predictor_dir = os.path.join(self.base_dir, "argus_predictor")
        argus_internal = os.path.join(argus_predictor_dir, "_internal")

        if os.path.isdir(argus_internal):
            return argus_predictor_dir, argus_internal

        direct_internal = os.path.join(self.base_dir, "_internal")
        if os.path.isdir(direct_internal):
            return self.base_dir, direct_internal

        # 若都不存在，預設以 argus_predictor 為目標
        return argus_predictor_dir, argus_internal

    def has_patch_backup(self) -> bool:
        """檢查是否存在有效的 Delta 增量備份目錄 (.patch_bak/)。"""
        _, internal_dir = self.resolve_target_dirs()
        patch_bak = os.path.join(internal_dir, ".patch_bak")
        if os.path.isdir(patch_bak):
            # 至少含有 argus.zip 或 version.txt
            if os.path.isfile(os.path.join(patch_bak, "argus.zip")) or os.path.isfile(
                os.path.join(patch_bak, "version.txt")
            ):
                return True
        return False

    def inspect_package(self, archive_or_dir: str) -> DeltaManifest:
        """解析封包之 manifest.json。"""
        if os.path.isdir(archive_or_dir):
            manifest_file = os.path.join(archive_or_dir, "manifest.json")
            return DeltaManifest.from_manifest_file(manifest_file)
        return DeltaManifest.from_archive(archive_or_dir)

    def apply_delta(
        self,
        delta_source: str,
        current_base_version: Optional[str] = None,
        verify_checksums: bool = True,
    ) -> Dict[str, Any]:
        """套用 Delta 增量更新。

        步驟：
        1. 解壓縮或定位 manifest.json 與 payload/
        2. 相容性比對 (min_compatible_base)
        3. 備份舊版業務代碼至 _internal/.patch_bak/
        4. 局域原子置換 (僅覆蓋 argus.zip、模板、手冊與 version.txt)
        5. 確保動態函式庫 (torch, cv2) 與本機配置完全不受影響

        Args:
            delta_source: tar.gz 封包路徑或已解壓之暫存目錄。
            current_base_version: 當前系統基礎版本號。
            verify_checksums: 是否強制核驗檔案雜湊。

        Returns:
            Dict[str, Any]: 套用結果摘要。
        """
        target_dir, internal_dir = self.resolve_target_dirs()

        if not os.path.isdir(internal_dir):
            raise FileNotFoundError(
                f"找不到底層安裝環境 (_internal 目錄不存在: {internal_dir})，無法進行 Delta 增量更新。請先執行完整安裝。"
            )

        with tempfile.TemporaryDirectory() as temp_unpack:
            if os.path.isfile(delta_source):
                logger.info(f"[DeltaUpdater] 解壓縮更新封包: {delta_source}")
                with tarfile.open(delta_source, "r:*") as tar:
                    tar.extractall(path=temp_unpack)
                root_staging = temp_unpack
            elif os.path.isdir(delta_source):
                root_staging = delta_source
            else:
                raise FileNotFoundError(f"找不到 Delta 更新來源: {delta_source}")

            manifest_path = os.path.join(root_staging, "manifest.json")
            manifest = DeltaManifest.from_manifest_file(manifest_path)

            if current_base_version and not manifest.is_compatible(current_base_version):
                raise DeltaCompatibilityError(
                    f"版本不相容: 目標補丁需要基礎版本 >= {manifest.min_compatible_base}，目前版本為 {current_base_version}"
                )

            payload_dir = os.path.join(root_staging, "payload")
            if not os.path.isdir(payload_dir):
                raise DeltaManifestError("Delta 增量包缺少 payload/ 目錄")

            if verify_checksums and manifest.files:
                valid, mismatches = manifest.verify_payload(payload_dir)
                if not valid:
                    raise DeltaManifestError(f"檔案校驗失敗: {'; '.join(mismatches)}")

            # ----------------------------------------------------------
            # 建立 .patch_bak/ 備份
            # ----------------------------------------------------------
            patch_bak = os.path.join(internal_dir, ".patch_bak")
            shutil.rmtree(patch_bak, ignore_errors=True)
            os.makedirs(patch_bak, exist_ok=True)

            # 備份舊版 argus.zip
            old_zip = os.path.join(internal_dir, "argus.zip")
            if os.path.isfile(old_zip):
                shutil.copy2(old_zip, os.path.join(patch_bak, "argus.zip"))

            # 備份 Web 模板
            old_web_tpl = os.path.join(internal_dir, "argus", "web", "templates")
            if os.path.isdir(old_web_tpl):
                bak_web_tpl = os.path.join(patch_bak, "argus", "web", "templates")
                os.makedirs(os.path.dirname(bak_web_tpl), exist_ok=True)
                shutil.copytree(old_web_tpl, bak_web_tpl, dirs_exist_ok=True)

            old_root_tpl = os.path.join(internal_dir, "templates")
            if os.path.isdir(old_root_tpl):
                bak_root_tpl = os.path.join(patch_bak, "templates")
                shutil.copytree(old_root_tpl, bak_root_tpl, dirs_exist_ok=True)

            # 備份 docs
            old_docs = os.path.join(internal_dir, "docs")
            if os.path.isdir(old_docs):
                bak_docs = os.path.join(patch_bak, "docs")
                shutil.copytree(old_docs, bak_docs, dirs_exist_ok=True)

            # 備份 version.txt
            old_ver = os.path.join(target_dir, "version.txt")
            if os.path.isfile(old_ver):
                shutil.copy2(old_ver, os.path.join(patch_bak, "version.txt"))
            elif os.path.isfile(os.path.join(self.base_dir, "version.txt")):
                shutil.copy2(
                    os.path.join(self.base_dir, "version.txt"),
                    os.path.join(patch_bak, "version.txt"),
                )

            # ----------------------------------------------------------
            # 局域原子置換 (In-place Replacement)
            # ----------------------------------------------------------
            # 1. 置換 argus.zip
            new_zip = os.path.join(payload_dir, "_internal", "argus.zip")
            if os.path.isfile(new_zip):
                tmp_zip = os.path.join(internal_dir, "argus.zip.tmp")
                shutil.copy2(new_zip, tmp_zip)
                os.replace(tmp_zip, os.path.join(internal_dir, "argus.zip"))

            # 2. 置換 Web 模板
            new_web_tpl = os.path.join(payload_dir, "_internal", "argus", "web", "templates")
            if os.path.isdir(new_web_tpl):
                dest_web_tpl = os.path.join(internal_dir, "argus", "web", "templates")
                os.makedirs(dest_web_tpl, exist_ok=True)
                shutil.copytree(new_web_tpl, dest_web_tpl, dirs_exist_ok=True)

            new_root_tpl = os.path.join(payload_dir, "_internal", "templates")
            if os.path.isdir(new_root_tpl):
                dest_root_tpl = os.path.join(internal_dir, "templates")
                os.makedirs(dest_root_tpl, exist_ok=True)
                shutil.copytree(new_root_tpl, dest_root_tpl, dirs_exist_ok=True)

            # 3. 置換手冊
            new_docs = os.path.join(payload_dir, "_internal", "docs")
            if os.path.isdir(new_docs):
                dest_docs = os.path.join(internal_dir, "docs")
                os.makedirs(dest_docs, exist_ok=True)
                shutil.copytree(new_docs, dest_docs, dirs_exist_ok=True)

            # 4. 更新版本標記
            new_ver = os.path.join(payload_dir, "version.txt")
            if os.path.isfile(new_ver):
                shutil.copy2(new_ver, os.path.join(target_dir, "version.txt"))
                if os.path.isfile(os.path.join(self.base_dir, "version.txt")):
                    shutil.copy2(new_ver, os.path.join(self.base_dir, "version.txt"))

            return {
                "status": "ok",
                "target_version": manifest.target_version,
                "backup_dir": patch_bak,
                "target_dir": target_dir,
                "files_updated": list(manifest.files.keys()),
            }

    def rollback(self) -> Dict[str, Any]:
        """秒級還原 Delta 增量更新。"""
        target_dir, internal_dir = self.resolve_target_dirs()
        patch_bak = os.path.join(internal_dir, ".patch_bak")

        if not os.path.isdir(patch_bak):
            raise FileNotFoundError(f"找不到 Delta 備份目錄: {patch_bak}，無法執行局部回滾")

        # 1. 還原 argus.zip
        bak_zip = os.path.join(patch_bak, "argus.zip")
        if os.path.isfile(bak_zip):
            tmp_zip = os.path.join(internal_dir, "argus.zip.tmp")
            shutil.copy2(bak_zip, tmp_zip)
            os.replace(tmp_zip, os.path.join(internal_dir, "argus.zip"))

        # 2. 還原 Web 模板
        bak_web_tpl = os.path.join(patch_bak, "argus", "web", "templates")
        if os.path.isdir(bak_web_tpl):
            dest_web_tpl = os.path.join(internal_dir, "argus", "web", "templates")
            shutil.rmtree(dest_web_tpl, ignore_errors=True)
            os.makedirs(os.path.dirname(dest_web_tpl), exist_ok=True)
            shutil.copytree(bak_web_tpl, dest_web_tpl, dirs_exist_ok=True)

        bak_root_tpl = os.path.join(patch_bak, "templates")
        if os.path.isdir(bak_root_tpl):
            dest_root_tpl = os.path.join(internal_dir, "templates")
            shutil.rmtree(dest_root_tpl, ignore_errors=True)
            shutil.copytree(bak_root_tpl, dest_root_tpl, dirs_exist_ok=True)

        # 3. 還原手冊
        bak_docs = os.path.join(patch_bak, "docs")
        if os.path.isdir(bak_docs):
            dest_docs = os.path.join(internal_dir, "docs")
            shutil.rmtree(dest_docs, ignore_errors=True)
            shutil.copytree(bak_docs, dest_docs, dirs_exist_ok=True)

        # 4. 還原 version.txt
        bak_ver = os.path.join(patch_bak, "version.txt")
        if os.path.isfile(bak_ver):
            shutil.copy2(bak_ver, os.path.join(target_dir, "version.txt"))
            if os.path.isfile(os.path.join(self.base_dir, "version.txt")):
                shutil.copy2(bak_ver, os.path.join(self.base_dir, "version.txt"))

        # 清除備份目錄
        shutil.rmtree(patch_bak, ignore_errors=True)

        # 產生回滾告警標記
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        alert_msg = f"系統未通過健康檢查，已於 {timestamp_str} 自動安全回滾至原版本"
        alert_path = os.path.join(self.base_dir, ".rollback_alert")
        try:
            with open(alert_path, "w", encoding="utf-8") as f:
                f.write(alert_msg + "\n")
        except Exception as e:
            logger.warning(f"無法寫入 .rollback_alert: {e}")

        return {
            "status": "ok",
            "message": "Delta 局部回滾完成",
            "alert": alert_msg,
            "target_dir": target_dir,
        }


def main():
    """CLI 工具進入點。"""
    parser = argparse.ArgumentParser(description="Argus Delta 增量更新與原子回滾工具")
    parser.add_argument("--delta", type=str, help="Delta 增量封包檔案 (.tar.gz) 或解壓目錄")
    parser.add_argument("--rollback", action="store_true", help="執行局部秒級回滾")
    parser.add_argument("--target-dir", type=str, default=".", help="目標程式根目錄")
    parser.add_argument("--current-version", type=str, default=None, help="當前版本號")

    args = parser.parse_args()
    updater = DeltaUpdater(base_dir=args.target_dir)

    if args.rollback:
        try:
            res = updater.rollback()
            print(f"[✓] 回滾成功: {res['message']}")
            sys.exit(0)
        except Exception as e:
            print(f"[✗] 回滾失敗: {e}", file=sys.stderr)
            sys.exit(1)

    if args.delta:
        try:
            res = updater.apply_delta(
                args.delta, current_base_version=args.current_version
            )
            print(f"[✓] Delta 更新套用成功: 目標版本 v{res['target_version']}")
            sys.exit(0)
        except Exception as e:
            print(f"[✗] Delta 更新失敗: {e}", file=sys.stderr)
            sys.exit(1)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
