# Fix: PTS 相對毫秒誤判定為絕對 Epoch 導致事件時間跳轉至 1970 年 (#46)

## 問題描述
在接入一般 RTSP 串流或本地影片時，OpenCV `cv2.CAP_PROP_POS_MSEC` 回傳的是串流起算的相對經過毫秒數（例如 3.652s、109.966s），而非絕對 Unix Epoch 時間。原邏輯僅以 `pts > 0` 作為判斷，導致自第 2 幀起將相對秒數誤轉為 `1970-01-01` 時間戳並寫入 `SafetyNano_<camera_id>_19700101.jsonl`。

## 修正方案
1. 定義標準 Unix Epoch 下限 `MIN_VALID_EPOCH_PTS = 946684800.0`（2000-01-01 00:00:00 UTC）。
2. 在 `event_producer.py`、`stream_handler.py`、`video_handler.py` 中嚴格檢驗 PTS 是否大於等於該門檻；若為相對 PTS 則自動 Fallback 至當前系統時間 `time.time()`。
3. 補齊相對 PTS fallback 與多影格序列之單元與回歸測試。
