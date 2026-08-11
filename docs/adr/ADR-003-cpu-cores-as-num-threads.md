# ADR-003：cpu_cores 欄位兼用為 NCNN num_threads

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-11 |
| **決策者** | 開發團隊 |
| **相關 PRD** | [ncnn_support_prd.md](../prd/ncnn_support_prd.md) |

---

## 情境與問題

NCNN 推論支援多執行緒加速（`num_threads`），在 RPi 5 的 4 核心環境下設定適當的執行緒數對效能影響顯著。需要決定此參數的來源：新增獨立欄位，或沿用現有設定。

## 決策選項

### 選項 A（已採用）：沿用 `cpu_cores` 欄位
以現有 `cpu_cores` 的值傳入 `InferenceEngine` 作為 `num_threads`，不新增欄位。

### 選項 B：新增獨立的 `num_threads` 欄位
在 `config.yaml` 新增 `num_threads` 欄位，與 `cpu_cores` 分開管理。

### 選項 C：硬編碼預設值
在程式碼中固定 `num_threads = 4`，不開放設定。

## 決策

**採用選項 A（沿用 `cpu_cores`）。**

## 理由

1. **語意高度吻合**：`cpu_cores` 代表「系統分配給本應用的 CPU 核心數」，與 NCNN `num_threads` 的最佳實踐（不超過實體核心數）完全一致。
2. **設定最小化原則**：避免引入語意重疊的新欄位，降低使用者設定認知負擔。
3. **RPi 5 場景單純**：RPi 5 有 4 個 ARM Cortex-A76 核心，`cpu_cores: 4` 即為最佳值，不需要細分控制。

## 取捨與風險

- **已知限制**：若未來需要「保留部分核心給作業系統或其他服務，NCNN 僅使用部分核心」的場景，需拆分欄位。
- **緩解措施**：`InferenceEngine.__init__` 接受獨立的 `num_threads` 參數（非直接讀 config），若未來需要拆分只需修改 `main.py` 的傳入邏輯，不影響 engine 本身。
