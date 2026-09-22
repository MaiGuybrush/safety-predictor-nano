# Package Size Reduction & Incremental Update Map

## Destination

落實 Argus Nano 於樹莓派 5 上的 PyInstaller `onedir` 發布與輕量應用層增量更新機制（初次安裝完整環境，後續更新僅下載幾 MB 增量包），並規劃第二階段推論後端瘦身（剝離 PyTorch/Ultralytics 改採純 NCNN/ONNX）的架構規格。

## Notes

- 目標平台：Raspberry Pi 5 (ARM64, Linux)
- 當前打包工具：PyInstaller (`argus_predictor.spec`)
- 執行架構：優先推進「方案 A：PyInstaller onedir + 應用層增量更新」；次階段優化規劃「方案 C：剝離 PyTorch 改採純 NCNN / ONNX」
- 專案依賴參考：`requirements.txt`、`src/argus/vision/inference_engine.py`

## Decisions so far

<!-- the index — one line per closed ticket: enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [01-onedir-layout-and-spec-analysis.md](issues/01-onedir-layout-and-spec-analysis.md) — onedir 產出將 base runtime 隔離於 `_internal/`（佔比 > 99.4%），應用層代碼與前端資源僅佔 < 0.6%（~5.5MB，壓縮後 ~1.6MB），且既有路徑與 `sys._MEIPASS` 完全無縫相容。
- [02-delta-update-packaging-strategy.md](issues/02-delta-update-packaging-strategy.md) — 確立「從 PYZ 剔除業務模組 + 外置 `argus.zip` via zipimport」的解耦機制，全應用層增量更新包僅約 2.4MB（純代碼僅 150KB），節省 99% 頻寬。
- [04-phase2-pruning-pytorch-with-ncnn.md](issues/04-phase2-pruning-pytorch-with-ncnn.md) — 方案 C 驗證可行：上層合約已完全解耦，僅需 ~120 行自建純 NCNN + OpenCV NMS 即可徹底剝離 PyTorch，使初次完整安裝包自 256MB 驟降至 65~75MB，推論延遲縮減 25%。

## Not yet specified

- **更新包安全性與防呆機制**：增量包 Checksum 雜湊校驗、版本相容性檢查與異常時自動回滾（Rollback）機制。
- **UMS / 雲端 OTA 自動更新串接**：透過既有 UMS API 自動檢測新版增量更新並下載觸發。
- **純 NCNN/ONNX 離線量化與模型轉換流程**：在無 PyTorch 環境下，ARM64 邊緣端專用模型的生成與驗證工作流。

## Out of scope

- Docker 容器化分層方案（受限於目標設備環境，不作為首選）。
- 樹莓派在線編譯或在現場執行 `pip install` 網路下載依賴。
