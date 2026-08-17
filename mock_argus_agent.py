#!/usr/bin/env python3
"""
Mock Argus Agent HTTP Server
----------------------------
用於單機開發與測試時，模擬本機 argus-agent 的 Local API (預設埠號 8080)。
接收並驗證來自 safety-predictor-nano (或 argus-eventlog) 發送的心跳請求 POST /api/ai-ap/heartbeat。

使用方式:
    python mock_argus_agent.py [--port 8080] [--host 0.0.0.0]
"""

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

# 記錄接收到的總心跳次數
heartbeat_counter = 0


class MockArgusAgentHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 覆寫預設的日誌格式，保持 console 輸出整潔
        pass

    def _send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_GET(self):
        if self.path in ("/", "/health", "/api/ai-ap/heartbeat"):
            self._send_json_response(200, {
                "status": "ok",
                "service": "Mock Argus Agent Server",
                "heartbeats_received": heartbeat_counter
            })
        else:
            self._send_json_response(404, {"error": "Not Found", "path": self.path})

    def do_POST(self):
        global heartbeat_counter

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        if self.path == "/api/ai-ap/heartbeat":
            heartbeat_counter += 1
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                payload = json.loads(post_data.decode("utf-8")) if post_data else {}
            except Exception as e:
                payload = {"_raw_body": post_data.decode("utf-8", errors="replace"), "_error": str(e)}

            print(f"\n[MOCK AGENT] {now_str} | Heartbeat #{heartbeat_counter} Received")
            print("-" * 60)
            if isinstance(payload, dict):
                ap_name = payload.get("apName", "N/A")
                instance = payload.get("instance", "N/A")
                camera_id = payload.get("cameraId", "N/A")
                version = payload.get("version", "N/A")
                output_path = payload.get("eventOutputPath", "N/A")
                status = payload.get("status", "N/A")

                print(f"  • AP Name         : {ap_name}")
                print(f"  • Instance        : {instance}")
                print(f"  • Camera ID       : {camera_id}")
                print(f"  • Version         : {version}")
                print(f"  • Status          : {status}")
                print(f"  • Event Output    : {output_path}")
                print(f"  • Full Payload    : {json.dumps(payload, ensure_ascii=False)}")
            else:
                print(f"  • Raw Body        : {payload}")
            print("-" * 60)

            self._send_json_response(200, {
                "status": "ok",
                "message": "Heartbeat registered successfully",
                "count": heartbeat_counter
            })
        else:
            self._send_json_response(404, {
                "error": "Endpoint not found",
                "path": self.path
            })


def run_server(host="0.0.0.0", port=8080):
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockArgusAgentHandler)
    print(f"============================================================")
    print(f"  Mock Argus Agent Server started on http://{host}:{port}")
    print(f"  Listening for POST requests on /api/ai-ap/heartbeat")
    print(f"  Press Ctrl+C to stop")
    print(f"============================================================")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[MOCK AGENT] Stopping server gracefully...")
        httpd.server_close()
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Argus Agent HTTP Server")
    parser.add_argument("-p", "--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("-H", "--host", type=str, default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
