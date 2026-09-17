# 規格：自動搜尋 argus agent 並匯入 camera rtsp 列表

- **Gitea Issue**: [#47](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/47)
- **Status**: ready-for-agent
- **Labels**: `ready-for-agent`, `Kind/Feature`

## 需求描述

* argus-agent API 預設使用 8080 port，若已被占用會自 8082~8090 依序找第一個可用的 port。
  - 範例：`http://localhost:8080`

* argus-agent 狀態檢查：
  - `GET /api/health`
  - 回傳範例：
    ```json
    { "status": "ok", "offline": false }
    ```

* 取得 RTSP 串流列表：
  - `GET /api/rtsp-streams`
  - 回傳範例：
    ```json
    [
      { "id": "cam-aabbccddee11", "name": "cam1", "rtspUrl": "rtsp://127.0.0.1:8554/cam-aabbccddee11", "type": "camera" },
      { "id": "hls-aaaa", "name": "hls1", "rtspUrl": "rtsp://127.0.0.1:8554/hls-aaaa", "type": "hls" }
    ]
    ```
