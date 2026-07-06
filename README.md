# AI 雙軌資金配置與回測決策系統

**AI Dual-Strategy Asset Allocation & Backtesting Copilot**

針對 1–2 個月短線波段週期的 AI 輔助量化策略系統。核心精神：**策略由數學規則執行、風控由硬規則把關、AI 負責分析與解釋、使用者保留最終決策權。**

本系統不預測漲跌，而是用網格與價值平均兩種數學策略、硬規則風控與 AI 分析，協助使用者紀律化配置資金、控制風險、解讀策略表現。

## 目前範圍：V1 MVP

回測 + 風控檢查 + AI 策略建議 + AI 參數優化 + AI 回測分析 + Streamlit 介面 + REST API + Next.js 前端 + CSV/Markdown 匯出。**不接實單交易。**

- 兩種策略：波動套利網格（Grid）、動態價值平均（Value Averaging）
- 大盤 60MA 風控、跌破區間、資金使用率、最大回撤等硬規則
- AI 層可切換 Claude / OpenAI / Gemini / Ollama；**無金鑰時自動使用規則式離線報告**
- AI 參數優化（網格搜尋）協助挑選策略參數
- 兩種介面：Streamlit（單機）與 FastAPI REST API + Next.js 前端
- 資料來源：yfinance（優先）/ CSV（離線）

詳見 [設計文件](docs/superpowers/specs/2026-06-09-backtesting-copilot-mvp-design.md)。

## 安裝

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[ai,dev]"
copy .env.example .env   # 填入金鑰；留空則離線運行
```

## 執行

```powershell
# 測試
pytest

# Streamlit 介面
streamlit run src/backtesting_copilot/app/streamlit_app.py

# REST API（FastAPI，預設 http://localhost:8000，文件在 /docs）
uvicorn backtesting_copilot.app.api.main:app --reload --app-dir src
```

### Next.js 前端

```powershell
cd frontend
npm install
npm run dev   # http://localhost:3000，需先啟動上方 REST API
```

主要 API 端點（皆掛在 `/api` 前綴下）：

- `POST /api/backtest`：執行回測
- `POST /api/optimize`：AI 參數優化（網格搜尋）
- `GET  /api/advisor`：AI 策略建議

## 架構

```
使用者輸入 → AI 策略建議 → AI 參數優化 → 參數驗證 → 策略引擎(網格/價值平均)
  → 風控引擎 → 回測引擎 → AI 回測分析 → 使用者確認 → (V2+) 模擬/半自動交易

介面層：Streamlit（單機） 或 Next.js 前端 → FastAPI REST API → 上述核心流程
```

## 開發階段

- **V1（目前）**：AI 回測分析版
- V2：AI 模擬交易版（定時更新、通知系統、REST API）
- V3：半自動下單版（券商 API）
- V4：全自動小額實驗版

## 風險聲明

本系統不保證獲利；歷史回測不代表未來績效。網格策略在單邊下跌時可能累積浮虧，價值平均策略在連續下跌時可能快速消耗資金。AI 建議不可作為唯一決策來源。
