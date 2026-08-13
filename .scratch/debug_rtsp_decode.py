"""
[DEBUG-rtsp-a1] RTSP 解碼品質診斷腳本
回饋迴路：量測每 100 幀的解碼失敗率，作為修復前後的對比基準。
用法: python .scratch/debug_rtsp_decode.py
"""
import cv2
import time
import os

# --- 設定 ---
RTSP_URL = "rtsp://127.0.0.1:8554/test_stream1"
SAMPLE_FRAMES = 100  # 採樣幀數
# -----------

# 關閉 OpenCV 的 FFmpeg 錯誤抑制，讓錯誤可見
# (main.py 設了 OPENCV_FFMPEG_LOGLEVEL=-8 會隱藏，這裡明確打開)
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "16"  # AV_LOG_ERROR

print(f"[DEBUG-rtsp-a1] 連線至 {RTSP_URL}")
print(f"[DEBUG-rtsp-a1] 採樣 {SAMPLE_FRAMES} 幀，量測解碼失敗率\n")

# 測試1: 目前設定（無 buffer 調整）
cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
if not cap.isOpened():
    print("[DEBUG-rtsp-a1] ❌ 無法連線 RTSP，請確認 go2rtc 正在執行")
    exit(1)

success = 0
fail = 0
start = time.time()

for i in range(SAMPLE_FRAMES):
    ret, frame = cap.read()
    if ret and frame is not None and frame.size > 0:
        success += 1
    else:
        fail += 1
    time.sleep(1.0 / 15)  # 模擬 15fps 消費速率

elapsed = time.time() - start
cap.release()

print(f"\n[DEBUG-rtsp-a1] === 結果 ===")
print(f"  成功幀: {success}/{SAMPLE_FRAMES} ({100*success/SAMPLE_FRAMES:.1f}%)")
print(f"  失敗幀: {fail}/{SAMPLE_FRAMES} ({100*fail/SAMPLE_FRAMES:.1f}%)")
print(f"  耗時: {elapsed:.1f}s")
print(f"\n[DEBUG-rtsp-a1] 基準線建立完成。")
print(f"[DEBUG-rtsp-a1] 修復後重新執行此腳本，對比失敗率。")
print(f"\n[DEBUG-rtsp-a1] 若失敗率 > 5%，代表 buffer/keyframe 問題仍存在。")
