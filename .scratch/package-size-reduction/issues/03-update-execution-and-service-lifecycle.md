Type: grilling
Status: open
Blocked by: 01, 02

## Question

增量更新包在邊緣端（Raspberry Pi 5）上的部署與生命週期管理流程應如何設計？
1. 更新觸發途徑：透過 Web UI 上傳更新包、手動執行更新 script、或是背景排程自動拉取？
2. 檔案佔用與安全覆蓋：當 `argus_predictor` 正在背景運行時，Linux 下替換正在載入的 Python/資源檔案是否需要先停止服務？
3. 服務重啟與回滾機制：更新覆蓋後如何透過 systemd 重啟服務？若新版啟動失敗，如何自動/手動回滾至上一可用版本？
