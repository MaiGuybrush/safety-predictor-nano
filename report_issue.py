#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""獨立離線手動回報 CLI 工具 (Offline CLI Reporter).

當系統無法正常啟動 Web UI 時，維運人員可直接執行此工具
進行診斷封包收集、上傳至 API Gateway FileServiceCore，
並自動於 Gitea 建立 Issue。
"""

import os
import sys
import argparse
import logging
from typing import Optional, List

import diagnostic_collector
import issue_service_client

logger = logging.getLogger("report_issue")


def create_parser() -> argparse.ArgumentParser:
    """建立命令列參數解析器。"""
    parser = argparse.ArgumentParser(
        prog="report_issue",
        description="Argus Safety Predictor Nano - 離線手動診斷回報工具",
    )
    parser.add_argument(
        "-t", "--title",
        type=str,
        default="",
        help="問題標題（未提供且為互動模式時將提示輸入）",
    )
    parser.add_argument(
        "-d", "--desc", "--description",
        dest="description",
        type=str,
        default="",
        help="問題詳細說明描述（未提供且為互動模式時將提示輸入）",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="非互動模式（不提示輸入，若未提供標題將採用預設標題）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="issue-bundles",
        help="診斷封包本機輸出目錄（預設: issue-bundles）",
    )
    parser.add_argument(
        "--logs-dir",
        type=str,
        default="logs",
        help="日誌目錄（預設: logs）",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置檔路徑（預設: config.yaml）",
    )
    parser.add_argument(
        "--gateway-hosts",
        type=str,
        default=None,
        help="自訂 API Gateway 主機（多台以逗號分隔，例如 http://tncimweb1.cminl.oa,http://tncimweb2.cminl.oa）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP 連線超時秒數（預設: 30 秒）",
    )
    return parser


def prompt_user_input(title: str, description: str) -> tuple[str, str]:
    """若在互動模式下缺少標題或描述，提示使用者輸入。"""
    print("\n=======================================================")
    print("  Argus Safety Predictor Nano - 診斷與問題回報精靈")
    print("=======================================================\n")

    if not title:
        try:
            val = input("請輸入問題標題 [預設: 手動回報系統異常診斷]: ").strip()
            title = val if val else "手動回報系統異常診斷"
        except (KeyboardInterrupt, EOFError):
            print("\n已取消操作。")
            sys.exit(1)

    if not description:
        try:
            print("\n請輸入問題詳細狀況描述（輸入完成後按 Enter；若無特別說明可直接 Enter）:")
            desc_val = input("> ").strip()
            description = desc_val if desc_val else "現場維運人員手動觸發回報，系統發生異常或無法正常啟動。"
        except (KeyboardInterrupt, EOFError):
            print("\n已取消操作。")
            sys.exit(1)

    return title, description


def run_cli(args: Optional[List[str]] = None) -> int:
    """執行離線回報 CLI 流程。

    :param args: 命令列參數列表（若為 None 則讀取 sys.argv[1:]）
    :return: 結束代碼 (0 代表成功，非 0 代表失敗)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    title = (parsed_args.title or "").strip()
    description = (parsed_args.description or "").strip()

    # 判斷是否需要互動式輸入
    if not parsed_args.non_interactive and (not title or not description):
        # 檢查 stdin 是否為 tty
        if sys.stdin.isatty():
            title, description = prompt_user_input(title, description)
        else:
            if not title:
                title = "手動回報系統異常診斷"
            if not description:
                description = "現場維運人員非互動模式回報，無額外描述。"
    else:
        if not title:
            title = "手動回報系統異常診斷"
        if not description:
            description = "現場維運人員手動回報，無額外詳細描述。"

    print(f"\n[1/3] 正在收集診斷日誌與環境資訊 (脫敏處理中)...")
    try:
        bundle_info = diagnostic_collector.collect_diagnostic_bundle(
            output_dir=parsed_args.output_dir,
            logs_dir=parsed_args.logs_dir,
            config_path=parsed_args.config,
        )
    except Exception as e:
        print(f"[錯誤] 收集診斷封包失敗: {e}", file=sys.stderr)
        return 1

    zip_path = bundle_info["zip_path"]
    zip_filename = bundle_info["zip_filename"]
    size_mb = round(bundle_info["size_bytes"] / (1024 * 1024), 2)
    report_id = bundle_info["report_id"]
    sysinfo = bundle_info["sysinfo"]
    files_included = bundle_info["files_included"]

    print(f"      封包建立完成: {zip_path} ({size_mb} MB)")
    print(f"      包含檔案: {', '.join(files_included)}")
    print(f"      回報代碼: {report_id}")

    # 解析 Gateway hosts
    gateway_hosts = None
    if parsed_args.gateway_hosts:
        gateway_hosts = [h.strip() for h in parsed_args.gateway_hosts.split(",") if h.strip()]

    client = issue_service_client.IssueServiceClient(
        gateway_hosts=gateway_hosts,
        timeout=parsed_args.timeout,
    )

    print(f"\n[2/3] 正在透過 API Gateway 上傳診斷封包...")
    try:
        upload_result = client.upload_diagnostic_file(
            zip_path=zip_path,
            report_id=report_id,
        )
        download_url = upload_result["download_url"]
        gateway_used = upload_result["host"]
        print(f"      上傳成功至 Gateway: {gateway_used}")
        print(f"      下載連結: {download_url}")
    except Exception as e:
        print(f"\n[錯誤] 診斷封包上傳失敗: {e}", file=sys.stderr)
        print(f"[提示] 診斷封包已儲存於本機: {zip_path}")
        print(f"       若處於無網路或隔離環境，請手動複製該封包進行排查。\n", file=sys.stderr)
        return 2

    print(f"\n[3/3] 正在於 Gitea 自動建立 Issue...")
    try:
        issue_result = client.create_gitea_issue(
            title=title,
            description=description,
            download_url=download_url,
            sysinfo=sysinfo,
            report_id=report_id,
            zip_filename=zip_filename,
        )
        issue_number = issue_result.get("issue_number")
        issue_url = issue_result.get("issue_url")

        print("\n=======================================================")
        print("  診斷封包上傳與 Issue 建立完成！")
        print("=======================================================")
        print(f"  Issue 編號: #{issue_number}")
        print(f"  Issue 網址: {issue_url}")
        print(f"  封包下載:   {download_url}")
        print(f"  本機封包:   {zip_path}")
        print("=======================================================\n")
        return 0

    except Exception as e:
        print(f"\n[錯誤] 建立 Gitea Issue 失敗: {e}", file=sys.stderr)
        print(f"[提示] 封包已成功上傳至: {download_url}")
        print(f"       本機封包路徑: {zip_path}")
        print(f"       您可直接將上述下載連結手動填入 Issue 中。\n", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(run_cli())
