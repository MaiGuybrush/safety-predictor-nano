# ADR-005：PyInstaller 部署需在 ARM64 環境建置

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-11 |
| **決策者** | 開發團隊 |
| **相關文件** | [AGENTS.md](../../AGENTS.md) |

---

## 情境與問題

系統以 PyInstaller 打包為單一執行檔（`argus_predictor`）部署至 Raspberry Pi 5。開發者通常在 x86/x64 Windows 或 macOS 機器上工作，需要決定建置環境的約束。

## 決策選項

### 選項 A（已採用）：強制要求在 ARM64 環境建置
明確規定 PyInstaller 打包必須在 ARM64 環境（Raspberry Pi 5 或 ARM64 VM）上執行。

### 選項 B：使用 Docker 跨平台建置
使用 Docker + QEMU 在 x86 機器上模擬 ARM64 環境進行交叉建置。

### 選項 C：使用 GitHub Actions ARM64 Runner
設定 CI/CD 在 ARM64 雲端 Runner（如 GitHub Actions `ubuntu-22.04-arm`）自動建置。

## 決策

**採用選項 A（強制在 ARM64 環境建置）。**

## 理由

1. **PyInstaller 不支援交叉編譯**：PyInstaller 收集的共享函式庫（`.so` 檔案）為平台相關的原生二進位，x86 建置的執行檔無法在 ARM64 上執行。
2. **避免模擬環境的不確定性**：QEMU 模擬可能導致建置成功但執行時崩潰的問題，排查困難。
3. **符合邊緣裝置部署慣例**：RPi 5 資源充足（8GB RAM）可直接執行建置流程，無需額外基礎設施。

## 取捨與風險

- **開發者不便**：需要 SSH 至 RPi 5 或 ARM64 VM 才能打包，增加建置步驟。
- **未來改善路徑**：可採用選項 C（ARM64 CI Runner）自動化建置，現階段手動建置已足夠。
- **文件化**：此限制已明確記錄於 `AGENTS.md` 的「Build/Deploy」章節。

## 附記

執行時期約束：`argus_predictor` 執行時嚴格要求 `config.yaml` 與模型檔案（`.pt` 或 `_ncnn_model/` 資料夾）位於相同工作目錄。
