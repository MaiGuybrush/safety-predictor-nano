# Architecture Decision Records (ADR) 索引

本目錄記錄 Argus Safety Predictor Nano 的重要架構決策。  
採用 [MADR](https://adr.github.io/madr/) 輕量格式。

## 狀態定義

| 狀態 | 說明 |
|------|------|
| 草稿 (Draft) | 尚未最終確認 |
| 已接受 (Accepted) | 已採用並實施 |
| 已廢棄 (Deprecated) | 曾採用，現已不適用 |
| 已取代 (Superseded) | 被其他 ADR 取代 |

## ADR 清單

| 編號 | 標題 | 狀態 | 日期 |
|------|------|------|------|
| [ADR-001](ADR-001-inference-backend-detection.md) | 推論後端選擇策略（路徑類型自動偵測） | 已接受 | 2026-08-11 |
| [ADR-002](ADR-002-ultralytics-ncnn-wrapper.md) | 使用 ultralytics NCNN 包裝層而非原生 ncnn Python API | 已接受 | 2026-08-11 |
| [ADR-003](ADR-003-cpu-cores-as-num-threads.md) | cpu_cores 欄位兼用為 NCNN num_threads | 已接受 | 2026-08-11 |
| [ADR-004](ADR-004-global-vars-cross-thread.md) | 模組級全域變數作為跨執行緒資料通道 | 已接受 | 2026-08-11 |
| [ADR-005](ADR-005-arm64-build-constraint.md) | PyInstaller 部署需在 ARM64 環境建置 | 已接受 | 2026-08-11 |
| [ADR-006](ADR-006-per-stream-model-assignment.md) | 每路 RTSP 串流綁定獨立模型（Per-Stream Model Assignment） | 已接受 | 2026-08-12 |
| [ADR-007](ADR-007-engine-instance-cache.md) | 相同模型路徑共用 InferenceEngine 實例（Engine Instance Cache） | 已接受 | 2026-08-12 |
| [ADR-008](ADR-008-round-robin-inference-scheduling.md) | 多路 RTSP 串流採 Round-Robin 推論排程 | 已接受 | 2026-08-12 |
| [ADR-009](ADR-009-sse-over-websocket-detection-channel.md) | 偵測結果通道採 SSE 而非 WebSocket | 已接受 | 2026-08-13 |
| [ADR-010](ADR-010-client-side-canvas-detection-overlay.md) | 偵測框由前端 Canvas 繪製而非伺服器端圖像標注 | 已接受 | 2026-08-13 |
| [ADR-011](ADR-011-per-stream-video-endpoint.md) | 單路全螢幕模式採獨立 /video_feed/<stream_id> 端點 | 已接受 | 2026-08-13 |
| [ADR-012](ADR-012-decoupled-stream-fps-and-inference-sampling.md) | 串流畫面 FPS 與推論抽樣率解耦及過時方框 UI 提示 | 已接受 | 2026-08-13 |
| [ADR-013](ADR-013-ums-client-model-sync.md) | 採用 ums-client 從 UMS 平台同步模型（UMS Client Model Sync） | 已接受 | 2026-08-16 |
| [ADR-014](ADR-014-argus-eventlog-integration.md) | 導入 argus-eventlog 輸出 ARGUS JSONL 事件（Argus Eventlog Integration） | 已接受 | 2026-08-16 |
| [ADR-015](ADR-015-argus-agent-heartbeat-and-camera-id-parsing.md) | 導入 argus-agent Heartbeat 登錄與 RTSP URL Camera ID 自動解析 | 已接受 | 2026-08-16 |

## 新增 ADR


1. 複製任意現有 ADR 作為模板
2. 命名規則：`ADR-NNN-短描述.md`（連字號分隔，英文）
3. 更新本索引表
