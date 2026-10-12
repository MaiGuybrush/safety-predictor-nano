# ADR-020: ncnn 為選用依賴，onnx / onnxruntime 為必要依賴

- 狀態：已採用
- 關聯：issue #95、#96

## 背景
打包探針 (`--probe`) 曾因 `ncnn` import 失敗而整體 FAIL，但 ONNX 推論實際正常。
`ncnn` 僅在載入 NCNN 格式模型（`inference_engine.py` 的 NCNN 分支）時才需要。

## 查證結論
- PyPI `ncnn` 1.0.20260526 提供 Windows (win_amd64 / win_arm64) 與 Linux aarch64 的 wheel
  （含 CPython 3.14），因此**兩個平台皆可安裝**；先前 Windows 打包產物缺少 ncnn，
  原因是建置環境未安裝，而非平台不支援。
- `.pt`、`.onnx` 推論不需要 `ncnn`。

## 決策
| 套件 | 性質 | 打包行為 | 探針行為 |
|---|---|---|---|
| onnx / onnxruntime | 必要 | 缺少則建置失敗，並打包 metadata | 缺少或 metadata 缺失 → FAIL |
| ncnn | 選用 | 有安裝則收集，缺少則警告 | 缺少 → 警告 (⚠️)，不 FAIL |

- `requirements.txt` 仍列出 `ncnn`，不加平台標記（兩平台皆有 wheel）。
- 需支援 NCNN 模型的部署（含 Raspberry Pi 5 ARM64），建置前須確認 `pip install ncnn` 成功。

## 待於目標平台驗證
- Pi 5 打包後 `--probe` 顯示 ncnn ✅，並實際載入 NCNN 模型推論。
