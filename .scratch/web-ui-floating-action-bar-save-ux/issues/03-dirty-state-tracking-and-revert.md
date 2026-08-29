# Issue #40: 前端 Dirty State 變更追蹤、串流未儲存標記與一鍵還原

Type: task
Status: resolved

**Role:** resolved

**What to build:**
在前端 JavaScript 建立初始載入快照（Snapshot），即時監聽左側所有全域參數與右側串流詳細設定（URL、Label、Camera ID、自訂模型）之修改。偵測到變更時自動滑出浮動儲存條，並在左側對應串流項目旁即時標記 `*`。切換不同串流檢視時完整保留各串流的記憶體草稿。實作「放棄變更」功能，一鍵將所有欄位與串流資料還原至初始快照並收合浮動條。

**Blocked by:**
- Issue #39 (feat: 前端全域浮動儲存條與 Toast UI 元件)

**Acceptance criteria:**
- [x] 記錄載入時的初始表單與串流快照。
- [x] 修改任何全域參數或串流欄位時，浮動儲存條自動加上 `.visible` 滑出。
- [x] 修改特定串流詳細設定時，左側對應串流項目顯示 `*` 標記。
- [x] 多路串流切換時保留各自修改狀態與標記。
- [x] 點擊「放棄變更」能精準還原所有設定至快照並收合浮動條。
