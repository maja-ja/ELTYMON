import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
import os
from io import BytesIO
from PIL import Image, ImageOps
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown
st.set_page_config(page_title="AI 教育工作站 (Etymon + Handout)", page_icon="🏫", layout="wide")

def inject_custom_css():
    """
    全域樣式注入：
    1. 專業教育感配色 (深藍/灰/白)。
    2. 手機版 RWD 自動適配。
    3. 頂部導航鈕美化。
    4. PayPal/綠界/BMC 贊助按鈕樣式。
    """
    st.markdown("""
        <style>
            /* --- 1. 全域字體與背景 --- */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+TC:wght@400;500;700&display=swap');
            
            html, body, [data-testid="ststAppViewContainer"] {
                font-family: 'Inter', 'Noto Sans TC', sans-serif;
                background-color: #FFFFFF;
            }

            /* --- 2. Etymon 百科卡片視覺 (去 AI 腔調) --- */
            .hero-word { 
                font-size: 3rem; 
                font-weight: 800; 
                color: #1A237E; 
                margin-bottom: 0px;
                letter-spacing: -0.03em;
                line-height: 1.2;
            }
            
            /* 邏輯拆解區：專業漸層 */
            .breakdown-wrapper {
                background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
                padding: 20px 25px; 
                border-radius: 12px; 
                color: white !important;
                margin: 15px 0;
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            }
            
            /* 專家心法區：簡潔內斂 */
            .vibe-box { 
                background-color: #F8FAFC; 
                padding: 18px; 
                border-radius: 10px; 
                border-left: 6px solid #3B82F6; 
                color: #1E293B !important; 
                margin: 15px 0;
                font-size: 15px;
                line-height: 1.6;
            }

            /* --- 3. 贊助按鈕系統 --- */
            .sponsor-container {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin: 15px 0;
            }
            .sponsor-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                padding: 10px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                text-decoration: none !important;
                transition: all 0.2s ease;
                border: none;
            }
            .sponsor-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            
            /* 品牌配色 */
            .btn-paypal { background-color: #003087; color: white !important; }
            .btn-ecpay { background-color: #00A650; color: white !important; }
            .btn-bmc { background-color: #FFDD00; color: #000000 !important; }
            .btn-icon { width: 18px; height: 18px; }

            /* --- 4. 頂部導航鈕 (Radio 模擬 Segmented Control) --- */
            div[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlock"] > div[role="radiogroup"] {
                background-color: #F1F5F9;
                padding: 5px;
                border-radius: 12px;
                justify-content: center;
            }
            div[role="radiogroup"] label {
                background-color: transparent;
                padding: 8px 20px !important;
                border-radius: 8px !important;
                transition: 0.3s;
            }
            div[role="radiogroup"] label[data-baseweb="radio"] div:first-child { display: none; } /* 隱藏圓圈 */
            div[role="radiogroup"] label[data-checked="true"] {
                background-color: #FFFFFF !important;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            }

            /* --- 5. 手機版 RWD 適配 (關鍵) --- */
            @media (max-width: 640px) {
                /* 縮小標題防止跑版 */
                .hero-word { font-size: 2rem !important; }
                
                /* 讓按鈕在手機上更好點擊 */
                .stButton button {
                    width: 100% !important;
                    height: 45px !important;
                    border-radius: 10px !important;
                }
                
                /* 調整卡片間距 */
                .stMainContainer { padding: 10px !important; }
                
                /* 讓 Tabs 在手機上可以橫向滑動 */
                .stTabs [data-baseweb="tab-list"] {
                    gap: 10px !important;
                }
                .stTabs[data-baseweb="tab"] {
                    padding: 8px 12px !important;
                    font-size: 14px !important;
                }
                
                /* 隱藏手機版側邊欄的部分裝飾 */
                [data-testid="stSidebarNav"] { display: none; }
            }

            /* --- 6. 深色模式適應 --- */
            @media (prefers-color-scheme: dark) {
                html, body, [data-testid="stAppViewContainer"] { background-color: #0F172A; }
                .hero-word { color: #60A5FA !important; }
                .vibe-box { background-color: #1E293B !important; color: #E2E8F0 !important; }
                .stMarkdown p, .stMarkdown li { color: #CBD5E1 !important; }
                div[role="radiogroup"] { background-color: #1E293B; }
                div[role="radiogroup"] label[data-checked="true"] { background-color: #334155 !important; }
            }
        </style>
    """, unsafe_allow_html=True)
def get_gemini_keys():
    """
    獲取並隨機打亂 API Keys (支援字串、列表或字串形式的列表)
    優先讀取 GEMINI_FREE_KEYS，若無則讀取 GEMINI_API_KEY
    """
    # 1. 嘗試獲取 keys，優先順序：列表群 > 單一 Key
    raw_keys = st.secrets.get("GEMINI_FREE_KEYS") or st.secrets.get("GEMINI_API_KEY")
    
    if not raw_keys:
        return[]

    # 2. 統一格式化為 List
    if isinstance(raw_keys, str):
        # 處理像是 "key1,key2,key3" 或 "[key1, key2]" 的字串格式
        if "," in raw_keys:
            # 移除可能存在的括號並依逗號分割
            keys =[k.strip().replace('"', '').replace("'", "") for k in raw_keys.strip("[]").split(",")]
        else:
            keys =[raw_keys]
    elif isinstance(raw_keys, list):
        keys = raw_keys
    else:
        return[]

    # 3. 過濾空值並打亂順序
    valid_keys = [k for k in keys if k and isinstance(k, str)]
    random.shuffle(valid_keys)
    
    return valid_keys
def fix_content(text):
    """
    優化版內容修復：
    1. 安全處理空值與無效字串。
    2. 智慧修復換行：保留段落結構，同時支援 Markdown 換行。
    3. LaTeX 保護：避免破壞數學公式的倒斜線。
    4. 移除 JSON 殘留的轉義引號，但保留內容原本的引號。
    """
    # 1. 基礎清洗與空值檢查
    if text is None:
        return ""
    
    # 轉為字串並去除首尾空白
    text = str(text).strip()
    
    # 檢查無效內容 (大小寫不敏感)
    if text.lower() in["無", "nan", "", "null", "none"]:
        return ""
    
    # 2. 處理 JSON 雙重轉義 (將 \\n 變為 \n)
    # 這是最常見的 LLM 輸出問題，文字裡的換行被變成了字面上的 "\n"
    if '\\n' in text:
        text = text.replace('\\n', '\n')

    # 3. 處理 LaTeX 雙重轉義 (將 \\ 變為 \，但需小心)
    # 如果是數學公式，通常不需要把所有的 \\ 都變成 \，因為 LaTeX 換行有時需要 \\
    # 但為了顯示正常，我們通常將明顯的錯誤修正
    if '\\\\' in text:
        # 簡單策略：先還原成單斜線，讓 MathJax 自己處理
        text = text.replace('\\\\', '\\')

    # 4. 智慧去引號 (只去除「非內容本身」的包裹引號)
    # 如果字串開頭和結尾都有引號，且中間沒有未轉義的同類引號，才視為包裹符號
    # 這裡採用較保守的策略：只去除首尾各一個，避免誤刪
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ['"', "'"]:
        text = text[1:-1]

    # 5. Markdown 換行處理
    # 將標準換行符號 \n 轉換為 Markdown 的強制換行 (兩空格 + \n)
    # 但避免破壞已經是 Markdown 格式的換行 (如列表或代碼塊)
    lines = text.split('\n')
    # 如果該行不是列表項 (- 或 *) 或標題 (#)，則在行尾加上兩個空白以強制換行
    processed_lines =[]
    for line in lines:
        line = line.strip() # 去除行內多餘空白
        if not line: 
            # 保留空行作為段落分隔
            processed_lines.append("") 
            continue
            
        # 檢查是否為特殊格式 (列表、標題、引用)，這些不需要強制換行
        if line.startswith(('-', '*', '#', '>', '1.', '2.')):
             processed_lines.append(line)
        else:
             processed_lines.append(line + "  ") # 強制換行
    
    return "\n".join(processed_lines) # 快取 1 小時，避免重複打 API
def generate_audio_base64(text):
    """
    將 gTTS 生成邏輯獨立出來並加上快取
    這樣頁面重整時，相同的單字不用重新請求 Google API
    """
    if not text: return None
    
    # 清洗文字：只保留英文、數字、基本標點，避免 TTS 唸出亂碼
    clean_text = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    clean_text = " ".join(clean_text.split()).strip()
    
    if not clean_text: return None

    try:
        tts = gTTS(text=clean_text, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        return base64.b64encode(fp.getvalue()).decode()
    except Exception as e:
        print(f"TTS 生成失敗 ({text}): {e}")
        return None

def speak(text, key_suffix=""):
    """
    TTS 發音生成 (優化版：含快取與錯誤處理)
    """
    # 1. 嘗試生成或獲取快取的音訊 Base64
    audio_base64 = generate_audio_base64(text)
    
    if not audio_base64:
        # 如果生成失敗，顯示一個禁用的按鈕或不顯示
        return

    # 2. 生成唯一的 HTML ID
    unique_id = f"audio_{hash(text)}_{key_suffix}".replace("-", "")
    
    # 3. 優化後的 HTML/CSS
    html_code = f"""
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        .btn {{ 
            background: linear-gradient(to bottom, #ffffff, #f8f9fa); 
            border: 1px solid #dee2e6; 
            border-radius: 6px; 
            padding: 6px 12px; 
            cursor: pointer; 
            display: inline-flex; 
            align-items: center; 
            gap: 6px; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            font-size: 13px; 
            font-weight: 500;
            color: #495057; 
            transition: all 0.2s ease; 
            box-shadow: 0 1px 2px rgba(0,0,0,0.05); 
            outline: none;
            user-select: none;
            -webkit-user-select: none;
            width: 100%;
            justify-content: center;
        }}
        .btn:hover {{ 
            background: #f1f3f5; 
            border-color: #ced4da; 
            color: #212529;
            transform: translateY(-1px);
        }}
        .btn:active {{ 
            background: #e9ecef; 
            transform: translateY(0); 
            box-shadow: none;
        }}
        .btn:focus {{
            box-shadow: 0 0 0 2px rgba(13, 110, 253, 0.25);
            border-color: #86b7fe;
        }}
        /* 播放中的動畫效果 (選用) */
        .playing {{
            border-color: #86b7fe;
            color: #0d6efd;
            background: #e7f1ff;
        }}
    </style>
    </head>
    <body>
        <button class="btn" id="btn_{unique_id}" onclick="playAudio()">
            <span>🔊</span> 聽發音
        </button>
        <audio id="{unique_id}" style="display:none" preload="none">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        </audio>

        <script>
            function playAudio() {{
                var audio = document.getElementById('{unique_id}');
                var btn = document.getElementById('btn_{unique_id}');
                
                if (audio.paused) {{
                    audio.play();
                    btn.classList.add('playing');
                    btn.innerHTML = '<span>🔊</span> 播放中...';
                }} else {{
                    audio.pause();
                    audio.currentTime = 0;
                    btn.classList.remove('playing');
                    btn.innerHTML = '<span>🔊</span> 聽發音';
                }}
                
                audio.onended = function() {{
                    btn.classList.remove('playing');
                    btn.innerHTML = '<span>🔊</span> 聽發音';
                }};
            }}
        </script>
    </body>
    </html>
    """
    
    # 這裡的高度設為 45 確保按鈕陰影不會被切掉
    components.html(html_code, height=45)
def get_spreadsheet_url():
    """
    從 Secrets 獲取 Google Sheets URL
    支援兩種常見的設定格式：st.connections 或直接在 gsheets 下
    """
    try:
        # 優先嘗試 st.connection 的標準格式
        return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except KeyError:
        # 嘗試舊版或簡易版格式
        try:
            return st.secrets["gsheets"]["spreadsheet"]
        except KeyError:
            st.error("❌ 未設定 Google Sheets URL，請檢查 .streamlit/secrets.toml")
            return ""

def log_user_intent(label):
    """
    靜默紀錄用戶意願 (Metrics)
    優化：加入簡單的時間戳記，並避免因讀取失敗導致程式中斷
    """
    if not label: return

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        if not url: return

        # 1. 嘗試讀取現有數據
        try: 
            # 設定 ttl=0 確保讀到最新數據，避免計數回溯
            m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
            
            # 確保 count 欄位是整數，處理可能存在的空值或錯誤格式
            if 'count' not in m_df.columns:
                m_df['count'] = 0
            m_df['count'] = pd.to_numeric(m_df['count'], errors='coerce').fillna(0).astype(int)
            
        except Exception: 
            # 如果工作表不存在或讀取失敗，初始化一個新的 DataFrame
            m_df = pd.DataFrame(columns=['label', 'count', 'last_updated'])
        
        # 2. 更新計數邏輯
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if label in m_df['label'].values:
            # 更新現有標籤
            idx = m_df[m_df['label'] == label].index
            m_df.loc[idx, 'count'] += 1
            m_df.loc[idx, 'last_updated'] = current_time
        else:
            # 新增標籤
            new_record = pd.DataFrame([{
                'label': label, 
                'count': 1, 
                'last_updated': current_time
            }])
            m_df = pd.concat([m_df, new_record], ignore_index=True)
            
        # 3. 寫回 Google Sheets
        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)
        
    except Exception as e:
        # 在 Console 輸出錯誤以便除錯，但不中斷前端顯示
        print(f"⚠️ Metrics logging failed for '{label}': {e}")

# 定義 12 核心欄位 (與試算表完全一致)
CORE_COLS =[
'word', 'category', 'roots', 'breakdown', 'definition', 
    'meaning', 'native_vibe', 'example', 'synonym_nuance', 
    'usage_warning', 'memory_hook', 'phonetic'
]

@st.cache_data(ttl=600)
def load_db():
    CORE_COLS =[
'word', 'category', 'roots', 'breakdown', 'definition', 
    'meaning', 'native_vibe', 'example', 'synonym_nuance', 
    'usage_warning', 'memory_hook', 'phonetic'
]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        # 關鍵修改：指定 worksheet="Sheet2"
        df = conn.read(spreadsheet=url, worksheet="Sheet2", ttl=0)
        
        # 補齊缺失欄位
        for col in CORE_COLS:
            if col not in df.columns:
                df[col] = "無"
        
        return df.dropna(subset=['word']).fillna("無")[CORE_COLS].reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        return pd.DataFrame(columns=CORE_COLS)

def submit_report(row_data):
    """
    優化版回報系統：加入時間戳記與狀態標記
    """
    try:
        # 請確認此 URL 具有寫入權限
        FEEDBACK_URL = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 準備回報內容
        # 如果 row_data 是 Series 則轉為 dict
        if isinstance(row_data, pd.Series):
            report_dict = row_data.to_dict()
        else:
            report_dict = row_data.copy()
            
        # 加入回報專用欄位
        report_dict['report_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
        report_dict['report_status'] = "待處理" # 初始化狀態
        
        # 讀取現有回報
        try: 
            existing = conn.read(spreadsheet=FEEDBACK_URL, ttl=0)
        except: 
            existing = pd.DataFrame()
            
        # 合併並更新
        updated = pd.concat([existing, pd.DataFrame([report_dict])], ignore_index=True)
        conn.update(spreadsheet=FEEDBACK_URL, data=updated)
        
        st.toast(f"🛠️ 已收到「{report_dict.get('word')}」的回報，我們會盡快處理！", icon="✅")
        return True
    except Exception as e:
        st.error(f"❌ 回報發送失敗：{e}")
        return False
def generate_random_topics(primary_cat, aux_cats=[], count=5):
    """
    讓 AI 根據選定領域推薦值得解碼的『繁體中文』主題清單。
    要求：純文字、無星號、無編號。
    """
    keys = get_gemini_keys()
    if not keys: return ""

    combined_cats = " + ".join([primary_cat] + aux_cats)
    
    prompt = f"""
    你是一位博學的知識策展人。
    請針對「{combined_cats}」這個領域組合，推薦 {count} 個具備深度學習價值、且能產生有趣跨界洞察的「繁體中文」主題或概念。
    
    【絕對要求】：
    1. 只輸出主題名稱，每個主題一行。
    2. 必須使用「繁體中文」。
    3. 嚴禁任何開場白、結尾、編號或解釋。
    4. 嚴禁使用任何 Markdown 格式，絕對不能出現「**」或「-」符號。
    5. 嚴禁出現任何標點符號。
    
    範例輸出：
    熵增定律
    賽局理論
    薪資的起源
    """

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            if response and response.text:
                # 二次清洗：移除所有星號、減號與多餘空白，確保存入資料庫時是乾淨的中文
                clean_text = response.text.replace("*", "").replace("-", "").strip()
                return clean_text
        except:
            continue
    return ""
def ai_decode_and_save(input_text, primary_cat, aux_cats=[]):
    """
    核心解碼函式 (Pro 整合版)：
    1. 跨領域交叉分析：主領域 + 輔助視角。
    2. 深度去 AI 化：禁止廢話，直擊知識本質。
    3. LaTeX 安全處理：強制雙重轉義防止渲染錯誤。
    4. 12 核心欄位對齊。
    """
    keys = get_gemini_keys()
    if not keys:
        st.error("❌ 找不到 API Key，請檢查 Secrets 設定。")
        return None

    # 組合分類標籤
    combined_cats = " + ".join([primary_cat] + aux_cats)
    
    # --- 核心生成指令 (System Prompt) ---
    SYSTEM_PROMPT = f"""
    Role: 全領域知識解構專家 (Interdisciplinary Polymath Decoder).
    Task: 針對輸入內容進行深度拆解，輸出高品質 JSON。
    
    【核心視角】：
    以「{primary_cat}」為框架，揉合「{', '.join(aux_cats) if aux_cats else '通用百科'}」視角進行交叉解碼。
    
    【🚫 絕對禁令 - 減少 AI 腔調】：
    - 嚴禁任何開場白或結尾語（如：好的、這是我為您準備的...）。
    - 嚴禁機器人式的過渡句。直接進入知識點，口吻要像冷靜、博學的資深教授。
    - 嚴禁在 JSON 之外輸出任何文字。

    【📐 輸出規範】：
    1. 必須輸出純 JSON 格式，嚴禁包含 ```json 標籤。
    2. LaTeX 雙重轉義：所有 LaTeX 指令必須使用「雙反斜線」。範例："\\\\frac{{a}}{{b}}"。
    3. 換行處理：JSON 內部的換行統一使用 "\\\\n"。

    【📋 欄位定義 (12 核心欄位)】：
    1. word: 核心概念名稱。
    2. category: "{combined_cats}"。
    3. roots: 底層邏輯/核心公式 (LaTeX，不加 $ 符號)。
    4. breakdown: 結構拆解 (3-5 邏輯步驟，用 \\\\n 分隔)。
    5. definition: 直覺定義 (ELI5，不准說「這代表...」，直接說明本質)。
    6. meaning: 本質意義 (一句話點破核心痛點)。
    7. native_vibe: 專家心法 (體現跨領域碰撞出的內行洞察)。
    8. example: 實際應用場景 (優先選擇跨領域案例)。
    9. synonym_nuance: 相似概念辨析。
    10. usage_warning: 邊界條件與誤區。
    11. memory_hook: 記憶金句 (具畫面感的口訣)。
    12. phonetic: 術語發音背景或詞源簡述。
    """

    final_prompt = f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」"

    # 嘗試使用 API Key 進行生成
    for key in keys:
        try:
            genai.configure(api_key=key)
            # 使用 1.5-flash 兼顧速度與邏輯穩定性
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            response = model.generate_content(
                final_prompt,
                generation_config={
                    "temperature": 0.2, # 降低隨機性，確保格式穩定
                    "top_p": 0.95,
                    "max_output_tokens": 2048,
                }
            )
            
            if response and response.text:
                raw_res = response.text
                
                # 1. 清洗 Markdown 標籤 (預防萬一 AI 還是加了)
                clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_res.strip(), flags=re.MULTILINE)
                
                # 2. 驗證 JSON 合法性並補齊欄位
                try:
                    parsed_data = json.loads(clean_json, strict=False)
                    
                    CORE_COLS =[
                        'word', 'category', 'roots', 'breakdown', 'definition', 
                        'meaning', 'native_vibe', 'example', 'synonym_nuance', 
                        'usage_warning', 'memory_hook', 'phonetic'
                    ]
                    
                    # 確保 12 欄位完整，缺失則補「無」
                    for col in CORE_COLS:
                        if col not in parsed_data:
                            parsed_data[col] = "無"
                    
                    # 強制寫入正確的分類標籤
                    parsed_data['category'] = combined_cats
                    
                    # 回傳標準化的 JSON 字串
                    return json.dumps(parsed_data, ensure_ascii=False)
                    
                except json.JSONDecodeError as je:
                    # 嘗試修復常見的換行符號導致的 JSON 錯誤
                    try:
                        fixed_json = clean_json.replace('\n', '\\n')
                        return json.dumps(json.loads(fixed_json), ensure_ascii=False)
                    except:
                        print(f"JSON 解析失敗: {je}")
                        continue
                        
        except Exception as e:
            print(f"⚠️ API Key 嘗試失敗: {e}")
            continue
    
    return None
def show_encyclopedia_card(row):
    """
    最終版百科卡片 (移除內部返回鍵):
    - 專為新的導航堆疊邏輯設計，由父頁面管理返回。
    - 12 核心欄位精準排版，去 AI 腔調。
    - LaTeX 深度優化，防止紅字。
    - 一鍵生成專業講義。
    """
    # --- 1. 變數提取與安全清洗 ---
    r_word = str(row.get('word', '未命名主題'))
    r_cat = str(row.get('category', '一般'))
    r_phonetic = fix_content(row.get('phonetic', "")) 
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_meaning = str(row.get('meaning', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_ex = fix_content(row.get('example', ""))
    r_nuance = fix_content(row.get('synonym_nuance', ""))
    r_warning = fix_content(row.get('usage_warning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))

    # --- 2. LaTeX 核心原理處理 ---
    raw_roots = fix_content(row.get('roots', ""))
    clean_roots = raw_roots.replace('$', '').strip()
    r_roots = f"$${clean_roots}$$" if clean_roots and clean_roots != "無" else "*(無公式或原理資料)*"

    # --- 3. 標題與發音區 ---
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    
    c_sub1, c_sub2 = st.columns([1, 3])
    with c_sub1:
        st.caption(f"🏷️ {r_cat}")
    with c_sub2:
        if r_phonetic and r_phonetic != "無":
            st.caption(f" | /{r_phonetic}/")

    # --- 4. 🧬 邏輯拆解 ---
    if r_breakdown and r_breakdown != "無":
        st.markdown(f"""
            <div class='breakdown-wrapper'>
                <h4 style='color: white; margin-top: 0; font-size: 1.1rem;'>🧬 結構拆解 / 邏輯步驟</h4>
                <div style='color: white; font-weight: 500; line-height: 1.6;'>{r_breakdown}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.write("") 

    # --- 5. 核心內容區 ---
    col_left, col_right = st.columns(2, gap="large")
    
    with col_left:
        st.markdown("### 🎯 直覺定義 (ELI5)")
        st.write(r_def) 
        if r_ex and r_ex != "無":
            st.info(f"💡 **應用實例：**\n{r_ex}")
        
    with col_right:
        st.markdown("### 💡 核心原理")
        st.markdown(r_roots)
        st.markdown(f"**🔍 本質意義：**\n{r_meaning}")
        if r_hook and r_hook != "無":
            st.markdown(f"**🪝 記憶金句：**\n`{r_hook}`")

    # --- 6. 🌊 專家視角 ---
    if r_vibe and r_vibe != "無":
        st.markdown(f"""
            <div class='vibe-box'>
                <h4 style='margin-top:0; color: #1E40AF;'>🌊 專家視角 / 跨界洞察</h4>
                {r_vibe}
            </div>
        """, unsafe_allow_html=True)

    # --- 7. 🔍 深度百科 ---
    with st.expander("🔎 更多細節 (辨析與邊界條件)"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：**\n{r_nuance}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：**\n{r_warning}")

    st.write("---")

    # --- 8. 功能操作區 ---
    op1, op2, op3 = st.columns([1, 1, 1.5])
    
    with op1:
        speak(r_word, f"card_{r_word}")
        
    with op2:
        if st.button("🚩 報錯/建議", key=f"rep_{r_word}", use_container_width=True):
            submit_report(row)
            
    with op3:
        if st.button("📄 生成專題講義", key=f"jump_ho_{r_word}", type="primary", use_container_width=True):
            log_user_intent(f"handout_{r_word}") 
            
            inherited_draft = f"""# 專題講義：{r_word}
領域：{r_cat}
## 🧬 邏輯結構
{r_breakdown}
## 🎯 核心定義 (ELI5)
{r_def}
## 💡 科學原理/底層邏輯
{r_roots}
**本質意義**：{r_meaning}
---
## 🚀 應用實例
{r_ex}
## 🌊 專家心法
{r_vibe}
---
**💡 記憶秘訣**：{r_hook}
"""
            st.session_state.manual_input_content = inherited_draft
            st.session_state.preview_editor = inherited_draft
            st.session_state.final_handout_title = f"{r_word} 專題講義"
            st.session_state.app_mode = "📄 講義排版"
            st.rerun()

    # --- 9. 💖 贊助支持 (元大銀行版) ---
    st.write("---")
    st.caption("💡 覺得這個解碼對你有幫助嗎？支持我們維持伺服器運作：")
    with st.expander("☕ 贊助開發者 (元大銀行轉帳)"):
        st.markdown("感謝你的支持！你的贊助將 100% 用於支付 AI API 與伺服器費用。")
        st.markdown("**🏦 銀行：元大銀行 (806)**")
        st.code("20102710511667", language="text")
def page_etymon_lab():
    """
    🔬 跨領域批量解碼實驗室
    功能：批量解碼、隨機靈感(純淨中文)、跨界分析、自動同步 Sheet2、手機優化。
    """
    st.title("🔬 跨領域解碼實驗室")
    st.caption("輸入多個主題並選擇領域視角，系統將進行深度邏輯拆解並自動同步至雲端 Sheet2。")

    # 1. 定義 12 核心欄位 (嚴格對齊 Sheet2 順序)
    CORE_COLS =[
        'word', 'category', 'roots', 'breakdown', 'definition', 
        'meaning', 'native_vibe', 'example', 'synonym_nuance', 
        'usage_warning', 'memory_hook', 'phonetic'
    ]

    # 2. 專業領域清單
    CATEGORIES = {
        "語言與邏輯":["英語辭源", "語言邏輯", "符號學", "修辭學"],
        "科學與技術":["物理科學", "生物醫學", "神經科學", "量子力學", "人工智慧", "數學邏輯"],
        "人文與社會":["歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "古希臘神話", "考古發現"],
        "商業與職場":["商業商戰", "金融投資", "產品設計", "數位行銷", "職場政治", "管理學", "賽局理論"],
        "生活與藝術":["餐飲文化", "社交禮儀", "藝術美學", "影視文學", "運動健身", "流行文化", "心理療癒"]
    }
    FLAT_CATEGORIES = [item for sublist in CATEGORIES.values() for item in sublist]

    # --- UI 佈局：領域選擇 ---
    with st.container(border=True):
        col_cat1, col_cat2 = st.columns(2)
        with col_cat1:
            primary_cat = st.selectbox("🎯 主核心領域", FLAT_CATEGORIES, index=0)
        with col_cat2:
            aux_cats = st.multiselect("🧩 輔助分析視角", FLAT_CATEGORIES, help="選擇輔助領域進行交叉分析")

        # 組合最終分類標籤
        display_category = primary_cat + (" + " + " + ".join(aux_cats) if aux_cats else "")
        st.markdown(f"**當前解碼視角：** `{display_category}`")

    st.write("")

    # --- 【關鍵修正】：Session State 初始化 ---
    if 'batch_input_area' not in st.session_state:
        st.session_state['batch_input_area'] = ""

    # --- UI 佈局：輸入區 ---
    col_input_h, col_gen_h = st.columns([3, 1])
    with col_input_h:
        st.markdown("**📝 待解碼主題清單** (每行一個概念)")
    with col_gen_h:
        # --- 功能：隨機靈感生成 (繁體中文、無符號) ---
        if st.button("🎲 隨機靈感", use_container_width=True, help="讓 AI 推薦 5 個中文主題"):
            with st.spinner("正在策展中文主題..."):
                # 呼叫優化後的隨機生成函式 (需確保該函式已定義)
                random_topics = generate_random_topics(primary_cat, aux_cats, count=5)
                if random_topics:
                    st.session_state['batch_input_area'] = random_topics
                    st.rerun()

    # 多行輸入框 (綁定 Session State Key)
    raw_input = st.text_area(
        "主題輸入區域",
        key="batch_input_area",
        placeholder="例如：\n熵增定律\n薪資的起源\n賽局理論",
        height=180,
        label_visibility="collapsed"
    )

    # 進階設定
    with st.expander("⚙️ 批量處理參數"):
        force_refresh = st.checkbox("🔄 強制刷新 (覆蓋 Sheet2 已存在的資料)")
        delay_sec = st.slider("API 請求間隔 (秒)", 0.5, 3.0, 1.0)

    st.write("---")

    # --- 執行批量解碼 ---
    if st.button("🚀 啟動批量深度解碼", type="primary", use_container_width=True):
        # 1. 處理輸入清單 (支援換行、英文逗號、中文逗號)
        input_list =[w.strip() for w in re.split(r'[\n,，]', raw_input) if w.strip()]
        
        if not input_list:
            st.warning("請先輸入或生成主題清單。")
            return

        # 2. 連接 Google Sheets 並讀取 Sheet2
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        try:
            existing_data = conn.read(spreadsheet=url, worksheet="Sheet2", ttl=0)
            # 確保現有資料包含所有核心欄位
            for col in CORE_COLS:
                if col not in existing_data.columns: existing_data[col] = "無"
        except:
            existing_data = pd.DataFrame(columns=CORE_COLS)

        # 3. 批量處理迴圈
        new_records =[]
        total = len(input_list)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, word in enumerate(input_list):
            status_text.markdown(f"⏳ **正在處理 ({i+1}/{total}):** `{word}`")
            
            # 檢查是否已存在 (不分大小寫)
            is_exist = False
            if not existing_data.empty:
                is_exist = (existing_data['word'].astype(str).str.lower() == word.lower().strip()).any()

            if is_exist and not force_refresh:
                status_text.markdown(f"⏩ **跳過已存在項目:** `{word}`")
            else:
                # 呼叫 AI 解碼函式 (12 欄位 + 去 AI 腔調)
                raw_res = ai_decode_and_save(word, primary_cat, aux_cats)
                
                if raw_res:
                    try:
                        res_data = json.loads(raw_res)
                        # 補齊 12 欄位並強制對齊
                        row = {col: res_data.get(col, "無") for col in CORE_COLS}
                        row['category'] = display_category # 強制寫入組合分類
                        new_records.append(row)
                    except:
                        st.error(f"❌ `{word}` 解析失敗")
                
                time.sleep(delay_sec)
            
            progress_bar.progress((i + 1) / total)

        # 4. 批量同步至雲端 Sheet2
        if new_records:
            status_text.markdown("💾 **正在同步至雲端 Sheet2...**")
            new_df = pd.DataFrame(new_records)
            
            # 強制刷新邏輯：先移除舊的重複項
            if force_refresh and not existing_data.empty:
                new_words_lower = [r['word'].lower().strip() for r in new_records]
                existing_data = existing_data[~existing_data['word'].str.lower().str.strip().isin(new_words_lower)]
            
            # 合併並確保欄位順序
            updated_df = pd.concat([existing_data, new_df], ignore_index=True)[CORE_COLS]
            
            try:
                conn.update(spreadsheet=url, worksheet="Sheet2", data=updated_df)
                st.success(f"🎉 批量處理完成！成功同步 {len(new_records)} 筆資料至 Sheet2。")
                st.balloons()
                
                # 顯示最後一個結果預覽
                with st.expander("📝 查看本次生成結果摘要", expanded=True):
                    st.table(new_df[['word', 'category', 'definition']])
            except Exception as e:
                st.error(f"❌ 雲端同步失敗: {e}")
                # 提供備份下載
                csv = updated_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載備份 CSV (防止資料遺失)", csv, "sheet2_backup.csv", "text/csv")
        else:
            st.info("清單中的主題已存在，且未開啟強制刷新。")
        
        status_text.empty()
# ==========================================
# Etymon 模組: 頁面邏輯 (優化版)
# ==========================================
def page_etymon_home(df):
    """
    Etymon Decoder 門戶首頁
    功能：數據儀表板、隨機啟發卡片、深層跳轉邏輯 (設定 back_to 狀態)。
    """
    # 1. 標題與副標題
    st.markdown("<h1 style='text-align: center; color: #1A237E;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B; font-size: 1.1rem;'>深度知識解構與跨領域邏輯圖書館</p>", unsafe_allow_html=True)
    st.write("---")
    
    # 2. 數據儀表板
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("📚 知識庫總量", f"{len(df)} 筆")
        with c2:
            st.metric("🏷️ 涵蓋領域", f"{df['category'].nunique()} 類")
        with c3:
            unique_roots = df['roots'].nunique()
            st.metric("🧬 核心邏輯", f"{unique_roots} 組")
    else:
        st.info("目前資料庫尚無資料，請前往實驗室進行首次解碼。")
        return

    st.write("")

    # 3. 隨機啟發區
    col_h, col_btn = st.columns([4, 1])
    with col_h:
        st.subheader("💡 今日隨機啟發")
    with col_btn:
        if st.button("🔄 換一批", use_container_width=True):
            if 'home_sample' in st.session_state:
                del st.session_state.home_sample
            st.rerun()
    
    # 保持隨機抽取穩定
    if 'home_sample' not in st.session_state:
        st.session_state.home_sample = df.sample(min(3, len(df)))
    
    sample = st.session_state.home_sample
    cols = st.columns(3)
    
    for i, (index, row) in enumerate(sample.iterrows()):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"### {row['word']}")
                st.caption(f"🏷️ {row['category']}")
                
                # 預覽內容：顯示「本質意義」
                meaning_text = fix_content(row['meaning'])
                if len(meaning_text) > 45:
                    meaning_text = meaning_text[:45] + "..."
                st.markdown(f"**本質：**\n{meaning_text}")
                
                st.write("") # 間距
                
                # --- 功能按鈕區 ---
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    speak(row['word'], f"home_{i}")
                with b_col2:
                    if st.button("🚩 有誤", key=f"h_rep_{i}_{row['word']}", use_container_width=True):
                        submit_report(row)
                
                # --- 【核心跳轉邏輯】 ---
                if st.button("🔍 查看詳情", key=f"h_det_{i}_{row['word']}", type="primary", use_container_width=True):
                    # 1. 設定目標單字
                    st.session_state.curr_w = row.to_dict()
                    # 2. 設定跳轉目標頁面
                    st.session_state.etymon_page = "📖 學習搜尋"
                    # 3. 記錄「最初的起點」，以便後續能返回此處
                    st.session_state.back_to = "🏠 首頁概覽"
                    # 4. 執行跳轉
                    st.rerun()

    st.write("---")
    
    # 4. 底部引導
    st.markdown("""
        <div style='text-align: center; color: #94A3B8; font-size: 0.9rem;'>
            👈 提示：點擊頂部「📖 學習搜尋」可查看完整清單，或使用「🧠 記憶挑戰」測試您的邏輯記憶。
        </div>
    """, unsafe_allow_html=True)
def page_etymon_learn(df):
    """
    知識庫探索 (最終旗艦版)：
    1. 統一導航：從首頁跳轉可一鍵返回首頁。
    2. 詳情模式：直接顯示跳轉過來的單字百科卡片。
    3. 探索模式：隨機探索可篩選領域，並進入詳情。
    4. 搜尋模式：可按領域篩選、多欄位關鍵字搜尋。
    """
    st.title("📖 知識庫探索")
    
    if df.empty:
        st.warning("目前資料庫是空的，請先前往實驗室新增內容。")
        return

    # --- 1. 【統一返回邏輯】：返回最初的起點 ---
    # 只要 back_to 狀態存在 (代表是從首頁跳轉過來的)，就顯示這個按鈕
    if st.session_state.get("back_to"):
        col_back, _ = st.columns([1, 2])
        with col_back:
            if st.button(f"⬅️ 返回{st.session_state.back_to}", use_container_width=True):
                target = st.session_state.back_to
                st.session_state.back_to = None      # 清除來源紀錄
                st.session_state.curr_w = None       # 清除當前單字快取
                st.session_state.etymon_page = target # 跳轉回來源頁面 (例如首頁概覽)
                st.rerun()

    # --- 2. 【核心顯示邏輯】：顯示單字詳情 或 顯示探索/搜尋列表 ---
    
    # --- 模式 A：顯示單字詳情 (curr_w 存在) ---
    if st.session_state.get('curr_w'):
        # 呼叫百科卡片 (該卡片內部已移除返回鍵，由本頁統一管理)
        show_encyclopedia_card(st.session_state.curr_w)
        
        # 提供“關閉詳情，回到列表”的按鈕
        st.write("")
        if st.button("🔍 關閉詳情，回到搜尋列表", use_container_width=True):
            st.session_state.curr_w = None # 只清除當前單字，保留 back_to 狀態
            st.rerun()
            
    # --- 模式 B：顯示探索與搜尋列表 (curr_w 不存在) ---
    else:
        tab_explore, tab_search = st.tabs(["🎲 隨機探索", "🔍 搜尋與列表"])
        
        # --- Tab 1: 隨機探索 ---
        with tab_explore:
            col_cat, col_btn = st.columns([2, 1])
            with col_cat:
                cats = ["全部領域"] + sorted(df['category'].unique().tolist())
                sel_cat = st.selectbox("選擇學習領域", cats, key="explore_cat_sel")
            
            with col_btn:
                st.write("") # 對齊
                if st.button("🎲 抽下一個", use_container_width=True, type="primary"):
                    f_df = df if sel_cat == "全部領域" else df[df['category'] == sel_cat]
                    if not f_df.empty:
                        # 將抽到的單字存入 curr_w，進入詳情模式
                        st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
                        # 隨機探索時，來源設為學習搜尋頁本身
                        st.session_state.back_to = "📖 學習搜尋" 
                    else:
                        st.session_state.curr_w = None
                    st.rerun()

            if not st.session_state.get('curr_w'): # 只有在未顯示單字時才顯示提示
                st.info("請點擊「🎲 抽下一個」開始探索，或切換至「🔍 搜尋與列表」進行查找。")

        # --- Tab 2: 搜尋與列表 ---
        with tab_search:
            # --- 【新增】：篩選與搜尋控制項 ---
            col_input, col_cat_filter = st.columns([2, 1])
            
            with col_input:
                search_query = st.text_input("🔍 關鍵字搜尋", placeholder="輸入單字、定義或本質意義...", key="search_input")
            
            with col_cat_filter:
                # 建立領域清單 (包含 "所有領域")
                cats_for_search = ["所有領域"] + sorted(df['category'].unique().tolist())
                sel_cat_search = st.selectbox("篩選領域", cats_for_search, key="search_cat_selector")

            # --- 根據下拉選單的選擇，決定要操作的基礎 DataFrame ---
            if sel_cat_search == "所有領域":
                base_df_for_display = df
            else:
                base_df_for_display = df[df['category'] == sel_cat_search]

            # --- 搜尋邏輯應用在已篩選的 DataFrame 上 ---
            if search_query:
                q = search_query.strip().lower()
                # 全欄位檢索：在 word, definition, category, meaning 中搜尋
                mask = (
                    base_df_for_display['word'].str.contains(q, case=False, na=False) |
                    base_df_for_display['definition'].str.contains(q, case=False, na=False) |
                    base_df_for_display['category'].str.contains(q, case=False, na=False) |
                    base_df_for_display['meaning'].str.contains(q, case=False, na=False)
                )
                
                res_df = base_df_for_display[mask]
                
                if not res_df.empty:
                    st.success(f"在「{sel_cat_search}」中找到 {len(res_df)} 筆結果：")
                    # 顯示搜尋結果，每個結果都可點擊進入詳情
                    for _, row in res_df.iterrows():
                        with st.container(border=True):
                            # 提供按鈕讓用戶點擊進入單字詳情模式
                            st.markdown(f"**{row['word']}** ( {row['category']} )")
                            meaning_prev = fix_content(row['meaning'])
                            st.caption(f"{meaning_prev[:80]}...")
                            if st.button("查看完整詳情", key=f"search_det_{row['word']}", use_container_width=True):
                                st.session_state.curr_w = row.to_dict()
                                st.session_state.back_to = "📖 學習搜尋" # 从搜索列表进入详情
                                st.rerun()
                else:
                    st.error(f"在「{sel_cat_search}」中找不到與「{search_query}」相關的內容。")
            else:
                # --- 預設列表也只顯示已篩選的內容 ---
                st.write(f"### 📚 「{sel_cat_search}」 知識清單")
                st.dataframe(
                    base_df_for_display[['word', 'category', 'meaning']], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "word": "主題", 
                        "category": "領域視角", 
                        "meaning": "本質意義"
                    }
                )
def fix_image_orientation(image):
    """
    修正圖片轉向：自動偵測手機拍攝時的 EXIF 資訊並轉正。
    """
    try: 
        image = ImageOps.exif_transpose(image)
    except Exception: 
        pass
    return image

def get_image_base64(image, max_dim=1200):
    """
    圖片轉 Base64 (優化版)：
    1. 自動縮放：避免高解析度圖片導致 PDF 生成過慢。
    2. 格式轉換：確保相容於 JPEG 格式。
    3. 體積優化：平衡畫質與傳輸速度。
    """
    if image is None: 
        return ""
    
    try:
        # 複製一份避免修改到原始物件
        img = image.copy()
        
        # 效能優化：若圖片長邊超過限制，則等比例縮小
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        buffered = BytesIO()
        # 處理透明背景 (RGBA) 轉為 RGB，避免 JPEG 存檔失敗
        if img.mode in ("RGBA", "P"): 
            img = img.convert("RGB")
            
        # 壓縮品質設為 85 (Pro 級平衡點)，並開啟優化
        img.save(buffered, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        print(f"圖片處理失敗: {e}")
        return ""
def handout_ai_generate(image, manual_input, instruction):
    """
    Handout AI 核心 (Pro 專業版)：
    1. 嚴格執行去 AI 腔調約束，直接輸出講義內容。
    2. 強化 LaTeX 與 Markdown 的排版安全性。
    3. 支援自動章節換頁標籤。
    """
    keys = get_gemini_keys()
    if not keys: 
        return "❌ 錯誤：未偵測到有效的 API Key。"

    # --- 專業講義架構指令 (去 AI 腔調版) ---
    SYSTEM_PROMPT = """
    Role: 專業教材架構師 (Educational Content Architect).
    Task: 將原始素材轉化為結構嚴謹、排版精美的 A4 講義。
    
    【⚠️ 輸出禁令 - 務必遵守】：
    - **禁止任何開場白與結尾**：嚴禁出現「好的」、「這是我為您準備的」、「希望這份講義對你有幫助」等任何對話式文字。
    - **直接開始**：輸出的第一個字必須是講義標題（# 標題）。
    
    【📐 排版規範】：
    1. **標題層級**：主標題用 #，章節用 ##，重點用 ###。
    2. **行內公式 (Inline Math)**：變數、短公式必須包裹在單個錢字號中，例如：$E=mc^2$。嚴禁在行內使用 $$。
    3. **區塊公式 (Block Math)**：長公式或核心定理必須獨立一行並使用 $$ 包裹，例如：
       $$ \int_{a}^{b} f(x) dx $$
    4. **換頁邏輯**：若內容較長，請在主要章節結束處插入 `[換頁]` 標籤。
    5. **列表格式**：使用標準 Markdown `-` 或 `1.`，確保列表內文字精煉。

    【語氣要求】：
    - 學術、客觀、精確。
    - 減少形容詞，增加動詞與邏輯連接詞。
    """
    
    # 組合輸入素材
    content_parts = [SYSTEM_PROMPT]
    
    if manual_input:
        content_parts.append(f"【原始素材內容】：\n{manual_input}")
    
    if instruction:
        content_parts.append(f"【特定排版要求】：{instruction}")
    
    if image:
        # 確保傳入的是 PIL Image 物件
        content_parts.append("【參考圖片素材】：")
        content_parts.append(image)

    last_error = None
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # 設定生成參數，降低隨機性以確保排版穩定
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.95,
                "max_output_tokens": 4096,
            }
            
            response = model.generate_content(
                content_parts, 
                generation_config=generation_config
            )
            
            if response and response.text:
                # 最終檢查：移除可能殘留的 Markdown 代碼塊標籤
                final_text = response.text.strip()
                final_text = re.sub(r'^```markdown\s*|\s*```$', '', final_text, flags=re.MULTILINE)
                return final_text
                
        except Exception as e:
            last_error = e
            print(f"⚠️ Key 嘗試失敗: {e}")
            continue
    
    return f"AI 生成中斷。最後錯誤訊息: {str(last_error)}"
def generate_printable_html(title, text_content, img_b64, img_width_percent, auto_download=False):
    """
    專業講義渲染引擎 (Pro 版)：
    1. 支援 MathJax CHTML 高品質公式渲染。
    2. 自動處理 [換頁] 標籤與圖片嵌入。
    3. 整合 PayPal/贊助資訊於講義頁尾。
    """
    # 基礎清理
    text_content = text_content.strip()
    
    # 處理換頁符號：轉換為 CSS 分頁標籤
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>')
    
    # Markdown 轉 HTML (支援表格與代碼塊)
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables', 'nl2br'])
    
    date_str = time.strftime("%Y-%m-%d")
    
    # 圖片區塊處理
    img_section = ""
    if img_b64:
        img_section = f'''
        <div class="img-wrapper">
            <img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;">
        </div>
        '''
    
    # 自動下載腳本
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 1000); };" if auto_download else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Roboto+Mono&display=swap" rel="stylesheet">
        
        <!-- MathJax 3.2.2 CHTML 配置 -->
        <script>
            window.MathJax = {{
                tex: {{ 
                    inlineMath: [['$', '$']], 
                    displayMath: [['$$', '$$']],
                    processEscapes: true,
                    tags: 'ams'
                }},
                chtml: {{ 
                    scale: 1.05,
                    displayAlign: 'center'
                }}
            }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
        
        <!-- html2pdf.js 核心 -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ 
                font-family: 'Noto Sans TC', sans-serif; 
                line-height: 1.75; 
                padding: 0; margin: 0; 
                background-color: #F3F4F6; 
                display: flex; flex-direction: column; align-items: center; 
            }}
            
            /* A4 紙張模擬 */
            #printable-area {{ 
                background: white; 
                width: 210mm; 
                min-height: 297mm; 
                margin: 30px 0; 
                padding: 25mm 25mm; 
                box-sizing: border-box; 
                position: relative; 
                box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            }}
            
            /* 內容樣式 */
            .content {{ font-size: 16px; text-align: justify; color: #1F2937; }}
            
            /* 標題設計 */
            h1 {{ color: #1E3A8A; text-align: center; font-size: 28px; border-bottom: 2px solid #1E3A8A; padding-bottom: 15px; margin-top: 0; }}
            h2 {{ color: #1E40AF; border-left: 6px solid #3B82F6; padding-left: 12px; margin-top: 35px; margin-bottom: 15px; font-size: 22px; }}
            h3 {{ color: #2563EB; font-weight: 700; margin-top: 25px; margin-bottom: 10px; font-size: 18px; }}
            
            /* 圖片容器 */
            .img-wrapper {{ text-align: center; margin: 25px 0; }}
            .img-wrapper img {{ border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}

            /* 表格樣式 */
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #E5E7EB; padding: 10px; text-align: left; }}
            th {{ background-color: #F9FAFB; }}

            /* 頁尾贊助資訊 */
            .footer {{ 
                margin-top: 60px; 
                padding-top: 20px; 
                border-top: 1px solid #E5E7EB; 
                text-align: center; 
                font-size: 12px; 
                color: #9CA3AF; 
            }}
            .footer-links {{ margin-top: 5px; font-weight: 500; color: #6B7280; }}

            /* 強制換頁控制 */
            .manual-page-break {{ page-break-before: always; height: 0; margin: 0; padding: 0; }}
            
            /* MathJax 垂直對齊修正 */
            mjx-container[jax="CHTML"][display="false"] {{
                vertical-align: baseline !important;
            }}
        </style>
    </head>
    <body>
        <div id="printable-area">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:13px; color:#9CA3AF; margin-bottom: 30px;">
                發佈日期：{date_str} | AI 教育工作站
            </div>
            
            {img_section}
            
            <div class="content">
                {html_body}
            </div>
            
            <div class="footer">
                <p>本講義由 AI 教育工作站自動生成，僅供教學參考使用。</p>
                <div class="footer-links">
                    💖 支援我們持續開發：歡迎透過元大銀行 (806) 20102710511667 隨喜贊助
                </div>
            </div>
        </div>

        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{
                    margin: 0, 
                    filename: '{title}.pdf', 
                    image: {{ type: 'jpeg', quality: 0.98 }},
                    html2canvas: {{ 
                        scale: 2, 
                        useCORS: true, 
                        letterRendering: true,
                        logging: false
                    }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                
                // 確保 MathJax 渲染完成後再執行轉換
                if (window.MathJax) {{
                    MathJax.typesetPromise().then(() => {{
                        html2pdf().set(opt).from(element).save();
                    }});
                }} else {{
                    html2pdf().set(opt).from(element).save();
                }}
            }}
            {auto_js}
        </script>
    </body>
    </html>
    """
def run_handout_app():
    # --- 新增：返回按鈕 ---
    col_back, col_space = st.columns([1, 4])
    with col_back:
        if st.button("⬅️ 返回單字解碼", use_container_width=True):
            st.session_state.app_mode = "🔬 單字解碼"
            st.rerun()
    
    st.header("🎓 AI 講義排版大師 Pro")
    st.caption("將混亂的題目圖片或筆記素材，轉化為結構嚴謹、排版精美的 A4 教材。")
    
    # 1. 權限與狀態初始化
    is_admin = st.session_state.get("is_admin", False)
    
    if "manual_input_content" not in st.session_state:
        st.session_state.manual_input_content = ""
    if "rotate_angle" not in st.session_state:
        st.session_state.rotate_angle = 0
    if "preview_editor" not in st.session_state:
        st.session_state.preview_editor = ""
    if "final_handout_title" not in st.session_state:
        st.session_state.final_handout_title = "專題講義"
    if "trigger_download" not in st.session_state:
        st.session_state.trigger_download = False

    # 2. 頁面佈局 (左側控制，右側預覽)
    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    
    # --- 左側：素材輸入與控制 ---
    with col_ctrl:
        st.subheader("1. 素材準備")
        
        # A. 圖片上傳與處理
        uploaded_file = st.file_uploader("📷 上傳題目或筆記照片 (可選)", type=["jpg", "png", "jpeg"])
        image_obj = None
        img_width = 80
        
        if uploaded_file:
            # 使用優化過的圖片處理函式
            raw_img = Image.open(uploaded_file)
            image_obj = fix_image_orientation(raw_img)
            
            # 旋轉邏輯
            if st.session_state.rotate_angle != 0:
                image_obj = image_obj.rotate(-st.session_state.rotate_angle, expand=True)
            
            c1, c2 = st.columns([1, 2])
            with c1: 
                if st.button("🔄 旋轉 90°"): 
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with c2: 
                img_width = st.slider("圖片顯示寬度 (%)", 10, 100, 80)
            
            st.image(image_obj, use_container_width=True, caption="素材預覽")

        st.divider()
        
        # B. 文字素材輸入
        st.markdown("**📝 講義原始素材**")
        st.text_area(
            "請輸入欲排版的文字內容、題目或知識點：", 
            key="manual_input_content", 
            height=250,
            placeholder="在此貼上從解碼實驗室複製的內容，或手打筆記..."
        )
        
        # C. 管理員 AI 生成區塊
        if is_admin:
            with st.expander("🛠️ AI 結構化排版 (管理員專用)", expanded=True):
                SAFE_STYLES = {
                    "📘 標準教科書": "【要求】：標題使用#，變數用$x$，長公式用$$，嚴禁純LaTeX指令。",
                    "📝 試卷解析模式": "【要求】：結構分為題目、解析、答案，選項用(A)(B)(C)(D)。",
                    "💡 知識百科模式": "【要求】：強調定義、原理與應用實例，使用豐富的 Markdown 標記。"
                }
                
                col_style, col_instr = st.columns([1, 1])
                with col_style:
                    selected_style = st.selectbox("選擇排版風格", list(SAFE_STYLES.keys()))
                with col_instr:
                    user_instr = st.text_input("補充指令", placeholder="例如：加入練習題...")

                if st.button("🚀 執行結構化生成", type="primary", use_container_width=True):
                    with st.spinner("正在優化講義架構..."):
                        final_instruction = f"{SAFE_STYLES[selected_style]}\n{user_instr}"
                        # 呼叫優化後的 AI 生成函式
                        generated_res = handout_ai_generate(image_obj, st.session_state.manual_input_content, final_instruction)
                        
                        # 更新編輯器內容
                        st.session_state.preview_editor = generated_res
                        
                        # 自動提取第一行作為標題
                        for line in generated_res.split('\n'):
                            clean_t = line.replace('#', '').strip()
                            if clean_t:
                                st.session_state.final_handout_title = clean_t
                                break
                        st.rerun()
        else:
            st.info("💡 提示：您可以直接在右側（電腦）或下方（手機）編輯器中貼上內容進行排版。AI 自動排版功能目前僅開放給管理員。")

    # --- 右側：A4 預覽與修訂 ---
    with col_prev:
        st.subheader("2. A4 預覽與修訂")
        
        # A. 下載與標題設定
        c_title, c_dl = st.columns([2, 1])
        with c_title:
            st.session_state.final_handout_title = st.text_input(
                "講義標題", 
                value=st.session_state.final_handout_title,
                placeholder="請輸入 PDF 檔名..."
            )
        with c_dl:
            st.write("") # 對齊
            if st.button("📥 下載 PDF", type="primary", use_container_width=True):
                log_user_intent(f"pdf_dl_{st.session_state.final_handout_title}")
                st.session_state.trigger_download = True
                st.rerun()
        
        # 贊助小提示
        st.caption("💖 講義下載完全免費。若覺得好用，歡迎透過側邊欄贊助支持 AI 算力支出。")

        # B. 內容修訂編輯器
        # 若編輯器為空但素材有內容，則自動同步 (初次載入)
        if not st.session_state.preview_editor and st.session_state.manual_input_content:
             st.session_state.preview_editor = st.session_state.manual_input_content

        edited_content = st.text_area(
            "📝 內容修訂 (支援 Markdown 與 LaTeX)", 
            key="preview_editor", 
            height=450,
            help="您可以在此直接修改 AI 生成的內容。使用 $...$ 包裹行內公式，$$...$$ 包裹區塊公式。"
        )
        
        # C. 即時 HTML/MathJax 預覽
        with st.container(border=True):
            st.markdown("**📄 A4 即時預覽 (模擬下載效果)**")
            
            # 轉換圖片為 Base64 (使用優化過的縮圖函式)
            img_b64 = get_image_base64(image_obj) if image_obj else ""
            
            # 呼叫優化後的 HTML 渲染引擎
            final_html = generate_printable_html(
                title=st.session_state.final_handout_title,
                text_content=edited_content, 
                img_b64=img_b64, 
                img_width_percent=img_width,
                auto_download=st.session_state.trigger_download
            )
            
            # 渲染預覽
            components.html(final_html, height=850, scrolling=True)

        # 下載觸發後的重設
        if st.session_state.trigger_download:
            st.session_state.trigger_download = False
def main():
    """
    AI 教育工作站 v5.0 - 旗艦修復版
    功能：
    1. 修復贊助按鈕顯示 (PayPal/綠界/BMC)。
    2. 頂部導航 (手機優化)。
    3. 深層跳轉與返回邏輯。
    4. 12 欄位資料庫對齊。
    """
    # 1. 注入全域 CSS 樣式 (含手機適配、按鈕美化)
    inject_custom_css()
    
    # 2. 初始化全域 Session State
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = "🔬 單字解碼"
    if 'etymon_page' not in st.session_state:
        st.session_state.etymon_page = "🏠 首頁概覽"
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    if 'curr_w' not in st.session_state:
        st.session_state.curr_w = None
    if 'back_to' not in st.session_state:
        st.session_state.back_to = None

    # ==========================================
    # 3. 側邊欄 (Sidebar)：權限與贊助
    # ==========================================
    with st.sidebar:
        # 加上名字（感謝那位網友），建立你的個人品牌槓桿
        st.title("🏫 AI 教育工作站")
        st.caption("Built by [你的名字] | 18歲自學實驗專案")
        
        # --- 🔐 管理員入口 ---
        with st.sidebar.expander("🔐 管理員登入"):
            admin_pwd_input = st.text_input("輸入管理密碼", type="password", key="admin_pwd_sidebar")
            if admin_pwd_input:
                if admin_pwd_input == st.secrets.get("ADMIN_PASSWORD"):
                    st.session_state.is_admin = True
                    st.success("🔓 管理員模式已啟動")
                else:
                    st.session_state.is_admin = False
                    st.error("❌ 密碼錯誤")

        st.markdown("---")
        
        # --- 💖 贊助支持 (元大銀行版) ---
        st.markdown("### 💖 支持電費與 AI 算力")
        
        st.caption("如果你覺得這個工具對你有幫助，歡迎隨喜贊助，支持我維持伺服器運作！")
        
        st.markdown("""
        <div style="border: 2px solid #1E3A8A; padding: 15px; border-radius: 10px; background-color: #F8FAFC; text-align: center; margin-bottom: 10px;">
            <div style="font-size: 12px; color: #64748B; font-weight: 900; letter-spacing: 1px; margin-bottom: 5px;">BANK TRANSFER</div>
            <div style="font-size: 18px; color: #1E293B; font-weight: 900;">元大銀行 (806)</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.code("20102710511667", language="text")
        
        with st.expander("為什麼使用銀行轉帳？"):
            st.write("""
                1. 學生身分申請第三方金流手續繁瑣。
                2. 平台抽成高，直接轉帳能 **100%** 用於支付 API 與伺服器費用。
                **感謝你的投食與支持！**
            """)
        
        st.markdown("---")
        auth_status = "🔴 管理員" if st.session_state.is_admin else "🟢 公開模式"
        st.caption(f"v5.0 Pro | {auth_status}")
        st.caption("© 2026 [你的名字]. All rights reserved.")
    # ==========================================
    # 4. 頂部模組導航 (手機版優化)
    # ==========================================
    modes = ["🔬 單字解碼", "📄 講義排版"]
    
    # 使用容器置中導航鈕
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    with nav_col2:
        selected_mode = st.radio(
            "切換工具模組",
            modes,
            index=modes.index(st.session_state.app_mode),
            horizontal=True,
            label_visibility="collapsed"
        )
    
    # 若模組改變，重設子頁面
    if selected_mode != st.session_state.app_mode:
        st.session_state.app_mode = selected_mode
        st.rerun()

    st.write("---")

    # ==========================================
    # 5. 路由邏輯 (Routing)
    # ==========================================
    
    if st.session_state.app_mode == "🔬 單字解碼":
        # 載入 Sheet2 資料
        df = load_db()
        
        # --- 子分頁導航 (使用橫向 radio 模擬 Tab 效果) ---
        sub_menu =["🏠 首頁概覽", "📖 學習搜尋"]
        
        selected_sub = st.radio(
            "功能選單",
            sub_menu,
            index=sub_menu.index(st.session_state.etymon_page),
            horizontal=True,
            label_visibility="collapsed"
        )
        
        if selected_sub != st.session_state.etymon_page:
            st.session_state.etymon_page = selected_sub
            st.rerun()

        st.write("") # 間距

        # --- 子頁面渲染 ---
        if st.session_state.etymon_page == "🏠 首頁概覽":
            page_etymon_home(df)
            
        elif st.session_state.etymon_page == "📖 學習搜尋":
            page_etymon_learn(df)
        
        # --- 管理員實驗室 (置底) ---
        if st.session_state.is_admin:
            st.write("---")
            with st.expander("🔬 跨領域批量解碼實驗室 (管理員專用)"):
                page_etymon_lab()
            
    elif st.session_state.app_mode == "📄 講義排版":
        # 執行講義排版模組
        run_handout_app()

# 啟動程式
if __name__ == "__main__":
    main()
