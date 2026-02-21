# 🏫 AI 教育工作站 (AI Educational Workstation)(app.py)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Gemini API](https://img.shields.io/badge/Powered%20by-Google%20Gemini-orange)](https://ai.google.dev/)

**AI 教育工作站** 是一個基於 Streamlit 開發的整合型教育工具，旨在透過 AI 技術協助教育工作者與學習者進行深度知識解構與教材製作。專案包含兩大核心模組：**Etymon Decoder (單字解碼)** 與 **Handout Pro (講義排版)**。

---

## ✨ 核心功能

### 1. 🔬 Etymon Decoder (跨領域單字解碼)
將複雜的概念進行邏輯拆解，並以跨領域視角重新詮釋。
- **深度解構**：自動生成定義、底層邏輯、結構拆解、專家視角與記憶金句。
- **多維度分析**：支援選擇「語言邏輯」、「科學技術」、「商業職場」等不同視角進行交叉分析。
- **雲端同步**：與 Google Sheets (Sheet2) 即時雙向同步，建立永久知識庫。
- **語音輔助**：整合 gTTS，提供單字發音功能。
- **搜尋與探索**：具備關鍵字搜尋、隨機抽卡探索與分類篩選功能。

### 2. 📄 Handout AI (智慧講義排版)
將零散的筆記或圖片轉化為專業的 A4 教學講義。
- **AI 結構化排版**：貼上筆記或上傳圖片，AI 自動整理成結構嚴謹的 Markdown 格式。
- **LaTeX 支援**：完美渲染數學公式 ($E=mc^2$) 與複雜定理。
- **圖片整合**：支援圖片旋轉、縮放與自動嵌入。
- **PDF 輸出**：一鍵生成包含頁首、頁尾與版權宣告的 A4 PDF 講義。

---

## 🛠️ 安裝與設定

### 1. 環境需求
確保您的系統已安裝 Python 3.8 或以上版本。

### 2. 安裝依賴套件
```bash
pip install streamlit pandas gTTS google-generativeai st-gsheets-connection Pillow markdown

### 3. 設定 Secrets (關鍵步驟)

本專案依賴 Google Gemini API 與 Google Sheets。請在專案根目錄建立 `.streamlit/secrets.toml` 檔案，並填入以下資訊：

```toml
# .streamlit/secrets.toml

# Google Gemini API Key (可填入單個字串或字串列表以輪詢)
GEMINI_API_KEY = "YOUR_GOOGLE_API_KEY"
# 或者使用多組 Key (選用)
# GEMINI_FREE_KEYS = ["KEY_1", "KEY_2", "KEY_3"]

# 管理員密碼 (用於解鎖批量解碼與 AI 排版功能)
ADMIN_PASSWORD = "your_admin_password"

# Google Sheets 連線設定
[connections.gsheets]
spreadsheet = "YOUR_GOOGLE_SHEET_URL"

# 若使用 Service Account (建議用於寫入權限)
# type = "service_account"
# project_id = "..."
# private_key_id = "..."
# private_key = "..."
# client_email = "..."

```

> **注意**：您的 Google Sheet 必須包含兩個工作表：
> 1. `Sheet2`：用於儲存知識庫資料。
> 2. `metrics`：用於紀錄使用者行為數據（選用）。
> 3. 請確保 Service Account 擁有該試算表的編輯權限。
> 
> 

### 4. 啟動應用程式

```bash
streamlit run app.py

```

---

## 📖 使用指南

### 📱 介面導航

程式針對 **桌面版** 與 **手機版** 進行了 RWD 響應式優化。

* **頂部導航**：可在「單字解碼」與「講義排版」模組間切換。
* **側邊欄**：包含管理員登入入口與贊助連結。

### 🔐 管理員模式

在側邊欄輸入設定的 `ADMIN_PASSWORD` 即可解鎖：

1. **批量解碼實驗室**：一次輸入多個主題，AI 自動背景執行並寫入資料庫。
2. **AI 講義生成**：在講義模組中使用 AI 自動優化筆記結構。

### 📥 講義輸出

* 在「講義排版」模式中，您可以即時預覽 A4 效果。
* 點擊「下載 PDF」按鈕，系統將透過瀏覽器端 (html2pdf.js) 生成 PDF 檔案。

---

## 📂 專案結構

```text
.
├── app.py                  # 主程式碼
├── requirements.txt        # 依賴套件清單
├── .streamlit/
│   └── secrets.toml        # API Keys 與設定檔 (不應上傳至 Git)
└── README.md               # 說明文件

```

---

## ⚠️ 注意事項

* **API 配額**：本程式使用 Google Gemini 模型，請留意 API 使用配額限制。
* **資料庫**：建議定期備份 Google Sheets 資料。
* **LaTeX**：講義排版使用 MathJax 渲染，輸入公式時請遵循 LaTeX 標準語法。

---

## 🤝 貢獻與支持

歡迎提交 Pull Request 或 Issue 來改善這個專案。如果您覺得這個工具有幫助，歡迎透過應用程式內的贊助連結支持開發者的算力支出。

---
💡 開發動機：為什麼 Notion 與 ChatGPT 滿足不了我？

在數位學習的時代，我們手邊已經有 ChatGPT、Notion、Google Docs 等強大的工具。但在實際的教學與學習場景中，我發現我的時間全都浪費在「搬運資料」上。

現有工具的痛點在於**「工作流是碎裂的」**：

1. AI 只是對話框，不是「累積資產」的資料庫

痛點： 當我在 ChatGPT 或 Gemini 查詢一個複雜單字或概念時，AI 給了很棒的拆解。但關掉網頁後，這些知識就淹沒在歷史紀錄中了。如果我要複習，我必須手動複製貼上到 Notion 或 Excel，非常反直覺。

我的解法 (Etymon Decoder)： 我不只要 AI 幫我解答，我還要它自動幫我「歸檔」。透過整合 Google Sheets 雙向同步，AI 生成的結構化知識（底層邏輯、記憶金句）會直接寫入雲端資料庫，自動變成專屬的單字卡與知識庫。

2. 「排版」與「數學公式」的複製貼上噩夢

痛點： 教學講義中常包含數學公式或程式碼。從 AI 複製這些內容到 Word 或 Google Docs 時，LaTeX 格式經常跑版，圖片還得另外手動插入並排版，光是「把筆記變成能印出來的 A4 講義」就要耗費半小時。

我的解法 (Handout Pro)： 我需要一個「所見即所得、一鍵成書」的工具。貼上生肉筆記，系統不僅透過 AI 自動梳理結構，還能完美渲染 LaTeX 數學公式，並直接透過瀏覽器一鍵匯出包含頁首/頁尾的專業 A4 PDF，把 30 分鐘的排版時間縮短到 3 秒鐘。

3. 缺乏「教育專屬」的提示詞框架

痛點： 通用型 AI 每次都需要重新輸入落落長的 Prompt，才能得到我想要的「跨領域視角」或「邏輯拆解」。

我的解法： 我將教育者需要的 Prompt 邏輯直接寫死在系統底層。使用者只需點擊「語言邏輯」或「科學技術」按鈕，系統就能給出高度專業的交叉分析，大幅降低 AI 的使用門檻。

總結來說：
我開發這個 AI 教育工作站，是因為我不想再當一個在多個網頁間切換、複製貼上的「資料搬運工」。我要打造一個**「輸入思維 ➡️ 自動結構化 ➡️ 永久儲存 ➡️ 一鍵輸出」**的自動化生產線。


**Built with ❤️ using Streamlit & Gemini**

