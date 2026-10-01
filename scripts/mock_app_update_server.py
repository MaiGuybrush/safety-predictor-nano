#!/usr/bin/env python3
"""scripts/mock_app_update_server.py - 本機 App Management API 模擬伺服器.

用途：
配合 Issue #82 Delta 增量更新手動驗證流程（軌道 B：沙盒模擬），提供一鍵啟動的輕量級 Mock API 伺服器。
無需任何外部依賴庫（僅使用 Python 標準庫 http.server），即可模擬中心化版本分發與二進位串流下載。

支援功能：
1. GET /AppManagementApi/App/{appId}/Version (或 /Version/nocache)
2. GET /AppManagementApi/File/{appId}/DownloadInfo
3. GET /AppManagementApi/File/{appId} (二進位串流下載)
4. 模式切換：
   - 預設模式：同時提供 Delta 增量包 (約 2.4MB) 與全量包 (256MB)
   - --full-only：僅提供全量包，供測試自動降級 (Fallback)
   - --corrupt：提供損毀之 Delta 封包，供測試校驗與防護
   - --version <ver>：自訂發布目標版本（預設 1.1.0）
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import tarfile
import tempfile
import urllib.parse
import zipfile


def create_dummy_delta_package(target_path: str, version: str = "1.1.0", corrupt: bool = False) -> str:
    """建立符合 Issue #82 規格之輕量 Delta 增量更新包 (約 2.4 MB)。"""
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with tempfile.TemporaryDirectory() as staging:
        payload_dir = os.path.join(staging, "payload")
        internal_dir = os.path.join(payload_dir, "_internal")
        tpl_dir = os.path.join(internal_dir, "argus", "web", "templates")
        docs_dir = os.path.join(internal_dir, "docs", "user-manual", "book")

        os.makedirs(tpl_dir, exist_ok=True)
        os.makedirs(docs_dir, exist_ok=True)

        # 1. 業務模組 argus.zip
        zip_path = os.path.join(internal_dir, "argus.zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("argus/__init__.py", f'__version__ = "{version}"\n')
            zf.writestr("argus/_mock_pad.bin", b"X" * 2350000)

        # 2. 前端模板與手冊
        tpl_path = os.path.join(tpl_dir, "index.html")
        with open(tpl_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- Argus WebUI v{version} Delta Applied -->")

        doc_path = os.path.join(docs_dir, "index.html")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- User Manual v{version} -->")

        # 3. 版本號
        ver_path = os.path.join(payload_dir, "version.txt")
        with open(ver_path, "w", encoding="utf-8") as f:
            f.write(f"{version}\n")

        # 4. manifest.json
        manifest_data = {
            "target_version": version,
            "min_compatible_base": "1.0.0",
            "arch": "arm64",
            "package_type": "delta",
            "code_only": False,
            "files": {
                "_internal/argus.zip": {
                    "sha256": "fake_sha_if_corrupt" if corrupt else "valid",
                    "size": os.path.getsize(zip_path),
                },
                "version.txt": {
                    "sha256": "valid",
                    "size": os.path.getsize(ver_path),
                },
            },
        }
        manifest_path = os.path.join(staging, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        with tarfile.open(target_path, "w:gz") as tar:
            tar.add(manifest_path, arcname="manifest.json")
            tar.add(payload_dir, arcname="payload")

    return target_path


class MockAppUpdateHandler(http.server.BaseHTTPRequestHandler):
    target_version = "1.1.0"
    mode_full_only = False
    mode_corrupt = False
    delta_file_path = ""
    app_id = "safety-predictor-nano"

    def log_message(self, format, *args):
        sys.stderr.write(f"[MockUpdateServer] {self.address_string()} - {format % args}\n")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. 查詢版本資訊：/AppManagementApi/App/{appId}/Version[/nocache]
        if f"/App/{self.app_id}/Version" in path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            resp = [
                {
                    "version": self.target_version,
                    "released": True,
                    "autoUpdate": True,
                    "locked": False,
                    "releaseDate": "2026-09-22 12:00:00",
                    "releaseNotes": f"◈ Argus Safety Predictor Nano v{self.target_version} 發布 (含 Delta 增量補丁)",
                    "releaseFab": "ALL",
                }
            ]
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            return

        # 2. 查詢下載資訊：/AppManagementApi/File/{appId}/DownloadInfo
        if f"/File/{self.app_id}/DownloadInfo" in path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            files_info = []
            if not self.mode_full_only:
                delta_size = os.path.getsize(self.delta_file_path) if os.path.isfile(self.delta_file_path) else 2516582
                files_info.append({
                    "fileName": f"argus_delta-v{self.target_version}-arm64.tar.gz",
                    "filePath": f"dist/v{self.target_version}/argus_delta-v{self.target_version}-arm64.tar.gz",
                    "size": delta_size,
                })

            files_info.append({
                "fileName": f"safety-predictor-nano-v{self.target_version}-arm64.tar.gz",
                "filePath": f"dist/v{self.target_version}/safety-predictor-nano-v{self.target_version}-arm64.tar.gz",
                "size": 268435456,  # 256MB
            })

            resp = {
                "owner": "cminl",
                "filesInfo": files_info,
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            return

        # 3. 二進位分塊下載：/AppManagementApi/File/{appId}
        if path.rstrip("/") == f"/AppManagementApi/File/{self.app_id}":
            file_path_param = query.get("filePath", [""])[0]
            if "delta" in file_path_param.lower() and not self.mode_full_only:
                if not os.path.isfile(self.delta_file_path):
                    self.send_error(404, "Delta file not found")
                    return
                file_size = os.path.getsize(self.delta_file_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/gzip")
                self.send_header("Content-Length", str(file_size))
                self.end_headers()
                with open(self.delta_file_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return
            else:
                # 模擬全量包下載或未知請求 (此處生成假數據流)
                simulated_size = 268435456
                self.send_response(200)
                self.send_header("Content-Type", "application/gzip")
                self.send_header("Content-Length", str(simulated_size))
                self.end_headers()
                chunk_1mb = b"0" * 1048576
                for _ in range(simulated_size // 1048576):
                    self.wfile.write(chunk_1mb)
                return

        # 其他未識別路由
        self.send_error(404, f"Path Not Found: {path}")


def main():
    parser = argparse.ArgumentParser(description="Argus Mock App Management API Server")
    parser.add_argument("--port", type=int, default=8190, help="監聽通訊埠 (預設: 8190)")
    parser.add_argument("--host", default="0.0.0.0", help="監聽位址 (預設: 0.0.0.0)")
    parser.add_argument("--version", default="1.1.0", help="目標發布版本 (預設: 1.1.0)")
    parser.add_argument("--full-only", action="store_true", help="僅提供全量包，測試 Fallback 機制")
    parser.add_argument("--corrupt", action="store_true", help="提供損毀封包，測試異常攔截與回滾")
    parser.add_argument("--app-id", default="safety-predictor-nano", help="App ID")
    parser.add_argument("--pkg-dir", default="updates/mock_repo", help="本地暫存模擬包路徑")
    args = parser.parse_args()

    delta_pkg_name = f"argus_delta-v{args.version}-arm64.tar.gz"
    delta_full_path = os.path.abspath(os.path.join(args.pkg_dir, delta_pkg_name))

    print("====================================================================")
    print(f" Argus Mock App Management API Server")
    print(f" • 監聽端點: http://{args.host}:{args.port}/AppManagementApi")
    print(f" • 目標版本: v{args.version}")
    print(f" • 發布模式: {'僅全量 (Full Only - Fallback Test)' if args.full_only else '雙模提供 (Delta 優先)'}")
    if args.corrupt:
        print(" • 異常狀態: 啟用損毀檔案模擬 (Corrupt Simulation)")
    print("====================================================================")

    if not args.full_only:
        print(f"[*] 正在生成測試用 Delta 增量更新包: {delta_full_path} ...")
        create_dummy_delta_package(delta_full_path, version=args.version, corrupt=args.corrupt)
        print(f"[✓] Delta 封包準備完成，大小: {os.path.getsize(delta_full_path):,} bytes")

    MockAppUpdateHandler.target_version = args.version
    MockAppUpdateHandler.mode_full_only = args.full_only
    MockAppUpdateHandler.mode_corrupt = args.corrupt
    MockAppUpdateHandler.delta_file_path = delta_full_path
    MockAppUpdateHandler.app_id = args.app_id

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer((args.host, args.port), MockAppUpdateHandler)
    try:
        print(f"[✓] Mock API 伺服器就緒，按 Ctrl+C 可停止服務。\n")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] 正在關閉 Mock API 伺服器...")
        server.shutdown()
        print("[✓] 服務已終止。")


if __name__ == "__main__":
    main()
