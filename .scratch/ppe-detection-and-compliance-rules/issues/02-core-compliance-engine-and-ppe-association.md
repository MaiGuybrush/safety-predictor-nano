# Issue 02: Core Compliance Engine & PPE Association

Type: task
Status: resolved
Blocked by: 01

## Description
建立 `compliance_engine.py` 核心模組，實作以下功能：
1. **類別標準化**：根據 `ppe_class_mapping` 將偵測框類別統一。
2. **PPE 關聯比對演算法**：
   - 計算 `head`, `helmet`, `vest` 與 `person` 偵測框的空間包含度 (Loose Box Containment) 與 IoU。
   - 支援 `direct_negative` 模式（區域或人體框內出現 `no_helmet` / `no_vest` 判定違規）。
   - 支援 `head_anchor` 模式（檢測到 `head` 時檢查安全帽配戴狀態，兼顧彎腰與遮擋防誤判）。
3. **複合條件規則矩陣評估**：
   - 比對當前 Zone、外部設備狀態 (`external_states`)、現場目標（如 `cone`, `guardrail`, `person`）與必要 PPE。
   - 輸出豐富化偵測物件 (`enriched_detections`) 與違規事件清單 (`violations`)。

## Acceptance Criteria
- 實作完整幾何運算，彎腰/蹲下時不誤判。
- 支援宣告式條件比對，單次比對耗時 < 0.2ms。
- 完成單元測試 `test_compliance_engine.py`。

## Answer
已完成 `compliance_engine.py` 核心模組實作與單元測試：
1. **幾何計算核心 (`box_area`, `box_intersection`, `box_containment`, `box_iou`, `box_center`, `is_point_in_box`)**：
   - 實作浮點數空間包含度與 IoU 運算，支援任意尺度偵測框。
2. **目標類別正規化 (`normalize_label`)**：
   - 依據 `ppe_class_mapping` 映射自訂類別名稱至標準名稱。
3. **PPE 雙模關聯比對 (`associate_ppe_for_person`)**：
   - `head_anchor`：以頭部為錨點，比對安全帽重疊率與包含度，並在彎腰/蹲下或頭部遮擋時結合人體上半身安全帽訊號，避免誤判。
   - `direct_negative`：支援直接以 `no_helmet`/`no_vest` 負樣本標籤進行即時違規判定。
4. **宣告式工安條件矩陣評估 (`evaluate_rules` & `evaluate`)**：
   - 完整支援 `when: {external_state, zone, detected}` 多維條件觸發。
   - 支援 `require_any`、`require_all` 與 `require_ppe` 驗證，並輸出 `enriched_detections`、`rule_events` 及 `compliance_summary`。
5. **測試與效能驗證**：
   - 建立 `tests/test_compliance_engine.py` 涵蓋幾何、雙模 PPE、規則矩陣及效能測試；1000 次評估總耗時 < 0.05s（單次耗時遠小於 0.2ms 門檻）。全專案測試全數 PASS。
