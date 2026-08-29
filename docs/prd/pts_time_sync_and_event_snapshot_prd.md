# PRD: PTS 時間戳同步、事件單次截圖與資料保留機制

## Problem Statement

在安防與智慧廠區的影像監控整合情境中，AI 邊緣推論端（Consumer A）與 NVR 歷史錄影端（Consumer B）若各自使用本機系統時間紀錄事件，會因為解碼緩衝、佇列排隊及推論計算耗時產生數百毫秒至數秒的時鐘偏差（Clock Skew），導致事後調閱錄影與回溯事件畫面時無法達到影格等級（Frame-accurate）的精準對齊。此外，既有系統在告警事件發生時缺乏自動捕獲現場原始影像的截圖機制，且長時間運行產生的日誌與影像檔缺乏自動化的留存過期清理機制，可能導致儲存空間耗盡。

## Solution

在 AI 偵測端導入基於串流原生 PTS（Presentation Timestamp）的時間基準對齊架構：
1. 偵測端解碼串流時同步擷取訊框原始 PTS（以 Wallclock Unix Epoch 秒數為基準），若串流無有效 PTS 則自動 Fallback 至系統時間。
2. 事件日誌（JSONL）中的 `timestamp` 一律使用由訊框 PTS 精確轉換之 ISO 8601 UTC 毫秒字串，確保與 NVR 錄影檔案的第一訊框 PTS 處於完全相同的時序座標系。
3. 建立事件單次截圖功能：當事件首度觸發時，以非同步佇列儲存當前原始乾淨訊框（Clean Frame），並在 JSONL metadata 中記錄相對截圖路徑；在同一事件持續期間不重複截圖。
4. 導入事件資料留存週期管理（Event Retention Cleaner），透過背景排程定期自動清理超過指定保存天數的日誌與截圖檔案。

## User Stories

1. As a security system operator, I want AI event logs to record accurate millisecond timestamps sourced directly from the stream PTS, so that alarm timestamps match video timestamps with sub-frame precision.
2. As an NVR integration engineer, I want the AI detection timestamps to share the same wallclock time base as the NVR segment recordings, so that seek calculations (`event_pts - seg_start_pts`) can retrieve the exact alarm frame without visual skew.
3. As a plant safety auditor, I want a clean snapshot of the scene automatically captured at the exact moment a safety violation occurs, so that I have clear visual evidence of the initial incident.
4. As an edge device maintainer, I want snapshot images to be encoded and saved asynchronously in a background worker thread, so that heavy disk I/O does not degrade real-time YOLO inference frame rates.
5. As a safety investigator, I want each continuous violation event to produce exactly one snapshot on its initial trigger rather than spamming screenshots every frame, so that storage is saved and event evidence remains concise and deduplicated.
6. As an NVR API client, I want the event start log in JSONL to contain the relative file path of the snapshot image, so that external review portals can directly locate and download the evidence image.
7. As a plant safety manager, I want the event snapshot image to be clean and unannotated, so that raw visual context is preserved and bounding boxes can be dynamically overlaid by frontend applications.
8. As a system administrator, I want to configure the event retention period (`event_retention_days`) via the Web UI dashboard, so that I can control disk retention according to factory compliance policies.
9. As a system administrator, I want files older than the retention threshold to be automatically purged daily in a separate background thread, so that edge storage never runs out of capacity.
10. As a field technician deploying streams without wallclock metadata or using local test videos, I want the system to automatically fallback to system epoch time for timestamps and snapshots, so that detection and logging continue reliably under all stream sources.
11. As an API client reading daily event logs, I want log lines to cleanly roll over across UTC dates based on the true event timestamp, so that cross-midnight events are organized in the correct daily files.
12. As a quality assurance engineer, I want to verify that an event that ends and restarts produces a fresh snapshot with a distinct timestamp and event reference, so that distinct incidents are accurately tracked independently.

## Implementation Decisions

- The stream capture handler fetches the Presentation Timestamp (`cv2.CAP_PROP_POS_MSEC / 1000.0`) synchronously upon retrieving each decoded frame, and bundles them into `(frame, pts)` tuples.
- If the extracted PTS value is non-positive (`pts <= 0`), invalid, or unavailable, the handler falls back to system epoch time (`time.time()`).
- All event actions (`EventStart`, `EventFrame`, `EventEnd`) format their `timestamp` attribute as an ISO 8601 string in UTC timezone with 3-digit millisecond precision (e.g. `YYYY-MM-DDTHH:MM:SS.mmmZ`).
- Event producer maintains an internal tracking state dictionary per `(stream_key, label)`. When a new event starts, an `EventStart` is dispatched and the clean frame and target snapshot filepath are pushed into an asynchronous snapshot queue.
- A dedicated daemon snapshot worker thread consumes items from the queue and persists JPEG images without blocking inference.
- Snapshot naming follows `{pts:.3f}_{event_ref}.jpg` stored under `recordings/{camera_id}/snapshots/`. While the event continues, no additional snapshots are triggered.
- The event metadata schema (`EventMeta`) is extended with an optional `snapshot_path` field populated with the relative path `snapshots/{pts:.3f}_{event_ref}.jpg`.
- A new configuration property `event_retention_days` (default: 30 days, integer >= 1) is introduced. A background retention cleaner thread runs daily and purges files older than the threshold under `recordings/{camera_id}/`.

## Testing Decisions

- Tests must focus exclusively on external observable behavior: queue payloads, JSONL line schemas, timestamp formats, filesystem snapshot creation, and retention deletion.
- Target Test Coverage:
  1. Event Producer & Timestamp Formatting Test (ISO 8601 UTC ms and fallback).
  2. Snapshot Creation & Deduplication Test (Single snapshot on start, no duplicates during frames, new snapshot after restart, meta.snapshot_path).
  3. Retention Cleaner Test (Purging old files, keeping new files).
  4. Web UI & Config Validation Test (Parsing and persisting `event_retention_days`).
- Prior Art: `test_event_producer.py`, `test_system_logger_and_reduction.py`.

## Out of Scope

- Modifying the upstream RTSP gateway (`go2rtc`) configuration or inject scripts.
- Modifying NVR storage cutting (`ffmpeg -c copy`) or NVR side databases.
- Real-time video encoding/saving of entire continuous clips.
- Drawing/burning bounding boxes into the snapshot images (snapshots must remain clean frames).

## Further Notes

- Path separators for relative paths in JSONL metadata must use forward slashes `/` for POSIX/web client consistency.
- Snapshot saving and retention cleanup run as background daemon threads to prevent any memory leaks or hanging shutdown sequences.
