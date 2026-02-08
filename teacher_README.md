# 🎓 LectureGen Pro | 智慧講義生成系統說明書

**LectureGen Pro** 是一套專為補教老師與家教設計的備課工具。它結合了 Google Gemini Pro (Vision) 的 AI 圖像辨識能力與 Google Sheets 雲端資料庫，協助您快速將手寫/截圖的題目轉化為專業詳解，並一鍵合成 PDF 講義。

---

## 🛠️ 第一章：系統環境準備

在開始之前，您需要準備以下三項資源：

1.  **Google 帳號**：用於建立雲端資料庫 (Sheets) 與申請 AI 金鑰。
2.  **Streamlit Community Cloud 帳號** (推薦)：用於免費託管網頁，讓您隨時隨地都能用手機或平板備課。
3.  **GitHub 帳號** (若使用雲端部署)：用於存放程式碼。

---

## ⚙️ 第二章：資料庫與 API 設定 (核心步驟)

### 步驟 1：建立 Google Sheet 資料庫
1.  前往 [Google Sheets](https://docs.google.com/spreadsheets) 建立一個新的試算表。
2.  **權限設定**：將試算表的「共用」權限設為「知道連結的使用者可以是**編輯者**」(或稍後授權給 Streamlit 的服務帳號)。
3.  建立兩個分頁 (Worksheets)，名稱與欄位必須完全一致：

**分頁 A 名稱：`questions` (存放題目)**
| id | image_name | exam_point | notes | concepts | explanation | timestamp |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| (留空) | (留空) | (留空) | (留空) | (留空) | (留空) | (留空) |

**分頁 B 名稱：`concepts` (存放觀念)**
| topic | intro | deep_dive | related_qs | years |
| :--- | :--- | :--- | :--- | :--- |
| 牛頓定律 | F=ma... | 這裡輸入詳細解說... | 110學測, 108指考 | 2021, 2019 |

> **注意**：請保留第一列為標題列，不要刪除。

### 步驟 2：取得 Google Gemini API Key
1.  前往 [Google AI Studio](https://aistudio.google.com/app/apikey)。
2.  點擊 **Create API key**。
3.  複製這串以 `AIza` 開頭的密鑰，稍後會用到。

---

## 🚀 第三章：程式部署與啟動

### 方法 A：使用 Streamlit Community Cloud (推薦，雲端使用)

1.  將前述提供的 Python 程式碼儲存為 `app.py`，並連同 `requirements.txt` 上傳到您的 GitHub Repository。
    *   `requirements.txt` 內容應包含：
        ```text
        streamlit
        pandas
        google-generativeai
        st-gsheets-connection
        Pillow
        ```
2.  登入 [Streamlit Cloud](https://share.streamlit.io/)，點擊 **New app**，選擇剛才的 GitHub Repo。
3.  點擊下方的 **Advanced settings** (進階設定)，找到 **Secrets** 區塊。
4.  將以下內容貼入 Secrets 編輯框，並替換成您的資料：

```toml
[connections.gsheets]
spreadsheet = "您的 Google Sheet 網址"

[GEMINI]
API_KEY = "您的 Google Gemini API Key (AIza開頭那串)"
```

5.  點擊 **Deploy** (部署)。系統會自動安裝依賴並啟動網頁。

### 方法 B：本地端執行 (電腦版)

1.  安裝 Python (建議 3.9 以上)。
2.  開啟終端機 (Terminal/CMD)，安裝套件：
    ```bash
    pip install streamlit pandas google-generativeai st-gsheets-connection Pillow
    ```
3.  在專案資料夾中建立 `.streamlit` 資料夾，並在裡面建立 `secrets.toml` 檔案，內容同上方 Secrets 設定。
4.  執行程式：
    ```bash
    streamlit run app.py
    ```

---

## 📖 第四章：功能操作指南

### 1️⃣ 題目登錄 (Input Page)
這是您的「AI 助教區」。
1.  **上傳圖片**：點擊 Browse files 上傳題目的截圖或照片。
2.  **輸入考點**：簡單輸入核心概念 (例如：`動量守恆`)。
3.  **輸入注意點**：寫下學生常犯錯的地方 (例如：`注意正負號定義`)。
4.  **點擊「✨ 讓 AI 生成詳解」**：
    *   AI 會讀取圖片文字與圖形，結合您給的考點，寫出一段「名師口吻」的詳解。
    *   生成後，您可以在下方文字框手動修改 AI 寫得不完美的地方。
5.  **存檔**：確認無誤後，點擊「💾 存入題庫」。

### 2️⃣ 觀念庫管理 (Library Page)
這是您的「知識倉庫」。
1.  **搜尋**：上方搜尋框可即時過濾觀念。
2.  **編輯/新增**：
    *   直接在下方的表格 (Data Editor) 點兩下即可編輯。
    *   若要新增一列，點擊表格工具列的 `+` 號。
    *   輸入：`topic` (標題)、`intro` (定義)、`deep_dive` (詳細解說)、`years` (歷屆年份)。
3.  **更新**：編輯完畢後，務必點擊下方的「💾 更新觀念庫」按鈕以同步回 Google Sheets。

### 3️⃣ 講義生成 (Generator Page)
這是「輸出成品」的地方，類似購物車概念。
1.  **左側 - 選擇素材**：
    *   **本次新增題目**：勾選您剛剛在上傳頁面處理好的題目 (包含暫存的圖片)。
    *   **觀念庫**：從下拉選單中搜尋並加入相關的觀念卡。
2.  **右側 - 即時預覽**：
    *   系統會自動將勾選的內容排版。
    *   觀念會排在「第一部分」，題目會排在「第二部分」。
3.  **下載 PDF**：
    *   確認預覽無誤後，點擊底部的 **「📥 下載 PDF 講義」**。
    *   系統會將網頁內容轉為 A4 格式的 PDF 檔案供您列印。

---

## ⚠️ 常見問題與注意事項

**Q1: 圖片上傳後，過了一天重開網頁，為什麼講義生成區看不到昨天的題目圖片？**
*   **A**: 為了保持 Google Sheets 的讀取速度，目前的設計是「題目文字存雲端，圖片存暫存記憶體 (Session)」。
*   **解法**：如果您需要製作講義，建議在「上傳題目 -> 生成詳解 -> 輸出 PDF」這三個動作在同一次操作中完成。若需長期儲存圖片，需修改程式碼串接外部圖床 (如 Imgur)。

**Q2: AI 生成出現 Error？**
*   **A**: 請檢查 `secrets.toml` 中的 `API_KEY` 是否正確，或是否超過 Google 免費版的使用額度 (每分鐘限制)。

**Q3: PDF 的數學公式顯示不出來？**
*   **A**: AI 會嘗試用 LaTeX 生成公式 (如 `$x^2$`)。目前的簡易 PDF 轉換器對複雜 LaTeX 支援度有限。若公式亂碼，建議在「詳解編輯區」手動將公式改為易讀的文字符號。

**Q4: Google Sheet 顯示 "Connection Error"？**
*   **A**: 請確認您的 Google Sheet 是否有開啟「共用連結」，或者您的 `secrets.toml` 格式是否正確。
