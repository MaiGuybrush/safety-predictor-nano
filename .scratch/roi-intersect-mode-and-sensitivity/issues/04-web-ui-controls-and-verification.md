# 04 — Web UI 控制項整合與全鏈路回歸驗證 (Web UI Controls & Full-Stack E2E Verification)

**What to build:**
在 Web UI 全螢幕 ROI 劃設面板與右側 Detail 檢查器中，新增「觸發模式」下拉選單（中心點 / 邊界相交）與「敏感度（0%~100%）」調節滑桿。完成使用者於前端設定、點擊儲存、後端即時熱重載生效（< 0.2 秒）、全套單元測試回歸與使用者手冊文件更新。

**Blocked by:** 03 — 推論結果屬性附加與前端即時告警渲染

**Status:** resolved

- [x] Web UI 全螢幕面板與 Detail 檢查器新增觸發模式下拉選單（`center` / `intersect`）
- [x] Web UI 新增敏感度調節滑桿（0% ~ 100%，對應 sensitivity 0.0 ~ 1.0）
- [x] 儲存 ROI 時正確發送包含 `trigger_mode` 與 `sensitivity` 的 payload
- [x] 載入既有 ROI 設定時正確回填觸發模式與敏感度數值
- [x] 驗證儲存後後端即時熱重載（Hot Reload）立即生效
- [x] 更新使用者手冊 `docs/user-manual/src/05-roi-and-fullscreen.md`
- [x] 全套單元測試回歸全數通過

## Answer
在 `templates/index.html` 完成了觸發模式選單（Center / Intersect）與敏感度滑桿（0% ~ 100%）UI 控制項，與 `/zone/<stream_url>` POST / GET 雙向同步；更新了使用者操作手冊 `docs/user-manual/src/05-roi-and-fullscreen.md`；全套 110 項測試全部通過。
