# Effort: Argus Camera ID Auto-fill & Warning (Issue #18)

## Notes
實作 Web UI RTSP URL 解析 `cam-xxx` 自動帶入 `camera_id`、清空自動復原、不一致即時顯示警告提示與提供一鍵還原按鈕。

## Decisions so far
- **URL 解析一致性**：前端使用 `parseArgusCameraId` 模擬後端 `argus_eventlog._parse_camera_id` 邏輯。
- **自動帶入與保留自訂**：URL 變更時，若 `camera_id` 為空或為先前自動帶入值則自動帶入；若為使用者自訂則保留並顯示警告。
- **清空視為重設**：若清空 `camera_id` 且 URL 含有 `cam-xxx`，自動帶回解析值。
- **即時警示與一鍵還原**：在 `camera_id` 欄位下方提供橘黃色警告文字與 `[ 還原為 cam-xxx ]` 按鈕。

## Map
- [01-camera-id-autofill-and-warning.md](file:///D:/Projects/argus/safty-predictor-nano/.scratch/argus-camera-id-autofill-warning/issues/01-camera-id-autofill-and-warning.md)
