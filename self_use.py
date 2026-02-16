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
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Noto+Sans+TC:wght@400;500;700&display=swap');
            
            /* --- 全域樣式優化 --- */
            .stMainContainer { transition: background-color 0.3s ease; }
            
            /* --- Etymon Decoder 視覺元件 --- */
            .hero-word { 
                font-size: 2.5rem; 
                font-weight: 800; 
                color: #1A237E; 
                margin-bottom: 0.5rem;
                letter-spacing: -0.02em;
            }
            .vibe-box { 
                background-color: #F8FAFC; 
                padding: 1.25rem; 
                border-radius: 8px; 
                border-left: 5px solid #3B82F6; 
                color: #334155 !important; 
                margin: 1rem 0;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            }
            .breakdown-wrapper {
                background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
                padding: 1.5rem; 
                border-radius: 12px; 
                color: white !important;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }
            
            /* --- Handout Pro 樣式 --- */
            .stTextArea textarea { 
                font-size: 15px; 
                line-height: 1.6; 
                font-family: 'Consolas', 'Monaco', monospace; 
            }
            .info-card { 
                background-color: #F0F9FF; 
                border-left: 4px solid #0EA5E9; 
                padding: 1rem; 
                border-radius: 6px; 
                margin-bottom: 1.25rem; 
            }

            /* --- 贊助按鈕通用樣式 --- */
            .sponsor-container {
                display: flex;
                flex-direction: column;
                gap: 12px;
                margin-bottom: 24px;
            }
            .sponsor-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                width: 100%;
                padding: 10px 16px;
                border-radius: 8px;
                font-weight: 600;
                text-decoration: none !important;
                transition: all 0.2s ease;
                border: none;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                font-size: 14px;
            }
            .sponsor-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .sponsor-btn:active { transform: translateY(0); }
            .btn-icon { width: 18px; height: 18px; object-fit: contain; }

            /* --- 各品牌按鈕配色 --- */
            /* 綠界 ECPay */
            .btn-ecpay { background-color: #00A650; color: white !important; }
            .btn-ecpay:hover { background-color: #008f45; }

            /* Buy Me a Coffee */
            .btn-bmc { background-color: #FFDD00; color: #000 !important; }
            .btn-bmc:hover { background-color: #ffea00; }

            /* PayPal */
            .btn-paypal { background-color: #003087; color: white !important; }
            .btn-paypal:hover { background-color: #00256b; }

            /* --- 深色模式適應 --- */
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #93C5FD !important; }
                .vibe-box { 
                    background-color: #1E293B !important; 
                    color: #E2E8F0 !important; 
                    border-left-color: #60A5FA !important; 
                }
                .sponsor-title { color: #94A3B8; }
                .stMarkdown p, .stMarkdown li { color: #E2E8F0 !important; }
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
        return []

    # 2. 統一格式化為 List
    if isinstance(raw_keys, str):
        # 處理像是 "key1,key2,key3" 或 "[key1, key2]" 的字串格式
        if "," in raw_keys:
            # 移除可能存在的括號並依逗號分割
            keys = [k.strip().replace('"', '').replace("'", "") for k in raw_keys.strip("[]").split(",")]
        else:
            keys = [raw_keys]
    elif isinstance(raw_keys, list):
        keys = raw_keys
    else:
        return []

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
    if text.lower() in ["無", "nan", "", "null", "none"]:
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
    processed_lines = []
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
    
    return "\n".join(processed_lines)
@st.cache_data(show_spinner=False, ttl=3600)  # 快取 1 小時，避免重複打 API
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
CORE_COLS = [
'word', 'category', 'roots', 'breakdown', 'definition', 
    'meaning', 'native_vibe', 'example', 'synonym_nuance', 
    'usage_warning', 'memory_hook', 'phonetic'
]

@st.cache_data(ttl=600)
def load_db():
    CORE_COLS = [
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
def ai_decode_and_save(input_text, primary_cat, aux_cats=[]):
    """
    核心解碼函式 (跨領域 Pro 版)：
    1. 支援主領域 + 多重輔助領域交叉分析。
    2. 嚴格去 AI 腔調：禁止廢話，直擊本質。
    3. 確保輸出符合 12 核心欄位。
    """
    keys = get_gemini_keys()
    if not keys:
        st.error("❌ 找不到 API Key，請檢查 Secrets 設定。")
        return None

    # 構建領域描述字串
    combined_cats = " + ".join([primary_cat] + aux_cats)
    aux_context = f"、{ '、'.join(aux_cats) }" if aux_cats else ""

    # --- 深度去 AI 化與跨領域 Prompt ---
    SYSTEM_PROMPT = f"""
    Role: 跨學科知識解構專家 (Interdisciplinary Decoder).
    Task: 針對輸入內容進行深度拆解，並輸出高品質 JSON。
    
    【核心視角】：
    你必須以「{primary_cat}」為核心邏輯，並強制揉合「{aux_context}」的視角進行交叉分析。
    
    【🚫 絕對禁令 - 減少 AI 腔調】：
    - **禁止廢話**：嚴禁使用「這是一個...」、「總結來說」、「值得注意的是」、「以下是為您準備的分析」等機器人贅詞。
    - **禁止解釋指令**：直接輸出 JSON 內容，不要解釋你為什麼這樣寫。
    - **口吻要求**：冷靜、精確、具備洞察力。像是一位在黑板前直接寫下重點的資深教授。

    ## 欄位定義 (嚴格遵守 12 欄位):
    1. word: 核心概念名稱。
    2. category: "{combined_cats}"。
    3. roots: 底層邏輯/核心公式 (使用 LaTeX，雙重轉義如 "\\\\frac")。
    4. breakdown: 結構拆解 (步驟或組成，用 \\\\n 分隔)。
    5. definition: ELI5 直覺定義 (不准說「這代表...」，直接說明本質)。
    6. meaning: 本質意義 (一句話點破核心痛點)。
    7. native_vibe: 專家心法 (必須體現「{primary_cat}」與「{aux_context}」碰撞出的獨特內行見解)。
    8. example: 實際應用場景 (優先舉出跨領域結合的例子)。
    9. synonym_nuance: 相似概念辨析。
    10. usage_warning: 邊界條件與誤區。
    11. memory_hook: 記憶金句 (具畫面感的口訣)。
    12. phonetic: 術語發音背景或詞源。

    ## 輸出格式：
    僅輸出純 JSON 內容，不含 Markdown 代碼塊標籤。
    """
    
    final_prompt = f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」"

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 降低 Temperature 以減少 AI 亂發揮，增加穩定性
            response = model.generate_content(
                final_prompt,
                generation_config={"temperature": 0.2}
            )
            
            if response and response.text:
                raw_res = response.text
                
                # 1. 清洗 Markdown 標籤
                clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_res.strip(), flags=re.MULTILINE)
                
                # 2. 驗證與補齊 12 欄位
                try:
                    parsed_data = json.loads(clean_json)
                    required_cols = ['word', 'category', 'roots', 'breakdown', 'definition', 'meaning', 
                                     'native_vibe', 'example', 'synonym_nuance', 'usage_warning', 
                                     'memory_hook', 'phonetic']
                    for col in required_cols:
                        if col not in parsed_data:
                            parsed_data[col] = "無"
                    
                    # 強制寫入組合後的分類
                    parsed_data['category'] = combined_cats
                    
                    return json.dumps(parsed_data, ensure_ascii=False)
                except json.JSONDecodeError:
                    continue
                        
        except Exception as e:
            print(f"⚠️ Key 嘗試失敗: {e}")
            continue
    
    return None
def show_encyclopedia_card(row):
    """
    優化版百科卡片 (對齊 12 核心欄位)：
    修復 LaTeX 渲染、優化邏輯拆解排版、提升講義生成相容性。
    """
    # --- 1. 變數提取與清洗 (使用優化版 fix_content) ---
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
    # 移除可能導致 MathJax 報錯的字元，確保被 $$ 包裹
    clean_roots = raw_roots.replace('$', '').strip()
    r_roots = f"$${clean_roots}$$" if clean_roots and clean_roots != "無" else "*(無公式或原理資料)*"

    # --- 3. 視覺標題區 ---
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    c_sub1, c_sub2 = st.columns([1, 4])
    with c_sub1:
        st.caption(f"🏷️ {r_cat}")
    with c_sub2:
        if r_phonetic and r_phonetic != "無":
            st.caption(f" | /{r_phonetic}/")

    # --- 4. 🧬 邏輯拆解 (醒目的漸層區塊) ---
    if r_breakdown and r_breakdown != "無":
        st.markdown(f"""
            <div class='breakdown-wrapper'>
                <h4 style='color: white; margin-top: 0; font-size: 1.1rem;'>🧬 結構拆解 / 邏輯步驟</h4>
                <div style='color: white; font-weight: 500; line-height: 1.6;'>{r_breakdown}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.write("") 

    # --- 5. 核心內容區 (左右並排) ---
    col_left, col_right = st.columns(2, gap="large")
    
    with col_left:
        st.markdown("### 🎯 直覺定義 (ELI5)")
        st.write(r_def) 
        if r_ex and r_ex != "無":
            st.info(f"💡 **應用實例：**\n{r_ex}")
        
    with col_right:
        st.markdown("### 💡 核心原理")
        # 直接渲染 LaTeX 區塊
        st.markdown(r_roots)
        
        st.markdown(f"**🔍 本質意義：**\n{r_meaning}")
        if r_hook and r_hook != "無":
            st.markdown(f"**🪝 記憶金句：**\n`{r_hook}`")

    # --- 6. 🌊 專家視角 (心法) ---
    if r_vibe and r_vibe != "無":
        st.markdown(f"""
            <div class='vibe-box'>
                <h4 style='margin-top:0; color: #1E40AF;'>🌊 內行心法</h4>
                {r_vibe}
            </div>
        """, unsafe_allow_html=True)

    # --- 7. 🔍 深度百科 (細節隱藏) ---
    with st.expander("🔎 更多細節 (辨析與邊界條件)"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：**\n{r_nuance}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：**\n{r_warning}")

    st.write("---")

    # --- 8. 功能操作區 (發音、回報、跳轉) ---
    op1, op2, op3 = st.columns([1, 1, 1.5])
    
    with op1:
        speak(r_word, f"card_{r_word}")
        
    with op2:
        if st.button("🚩 報錯/建議", key=f"rep_{r_word}", use_container_width=True):
            submit_report(row)
            
    with op3:
        if st.button("📄 生成專題講義", key=f"jump_ho_{r_word}", type="primary", use_container_width=True):
            log_user_intent(f"handout_{r_word}") 
            
            # 預構建高品質講義草稿
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
            st.session_state.app_mode = "Handout Pro (講義排版)"
            st.rerun()
def page_etymon_lab():
    """
    🔬 批量解碼實驗室 (Batch Pro 版)
    支援一次輸入多個主題，自動批量處理並同步至 Sheet2。
    """
    st.title("🔬 批量解碼實驗室")
    st.caption("請在下方輸入多個主題（每行一個，或用逗號分隔），系統將自動進行批量跨領域拆解。")
    
    # 領域清單 (保持不變)
    FIXED_CATEGORIES = ["英語辭源", "語言邏輯", "物理科學", "神經科學", "量子力學", "歷史文明", "職場政治", "餐飲文化", "社交禮儀"]
    FLAT_CATEGORIES = FIXED_CATEGORIES # 簡化顯示

    # --- UI 佈局 ---
    with st.container(border=True):
        # 改用 text_area 支援多行輸入
        raw_input = st.text_area("🔍 欲解碼的主題清單：", placeholder="例如：\nSalary\nEntropy\nGame Theory", height=150)
        
        col_cat1, col_cat2 = st.columns(2)
        with col_cat1:
            primary_cat = st.selectbox("🎯 主核心領域", FLAT_CATEGORIES, index=0)
        with col_cat2:
            aux_cats = st.multiselect("🧩 輔助分析視角", FLAT_CATEGORIES)

        display_category = primary_cat + (" + " + " + ".join(aux_cats) if aux_cats else "")

    # 進階設定
    with st.expander("⚙️ 批量處理設定"):
        force_refresh = st.checkbox("🔄 強制刷新 (覆蓋已存在的單字)")
        delay_between = st.slider("延遲時間 (秒)", 0.5, 3.0, 1.0, help="避免 API 請求過快被封鎖")

    if st.button("🚀 開始批量解碼", type="primary", use_container_width=True):
        if not raw_input.strip():
            st.warning("請輸入至少一個主題。")
            return

        # 1. 處理輸入清單：支援換行或逗號分隔
        input_list = [w.strip() for w in re.split(r'[\n,，]', raw_input) if w.strip()]
        total_words = len(input_list)
        st.info(f"準備處理 {total_words} 個主題...")

        # 2. 讀取現有資料庫 (Sheet2)
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        try:
            existing_data = conn.read(spreadsheet=url, worksheet="Sheet2", ttl=0)
        except:
            existing_data = pd.DataFrame(columns=CORE_COLS)

        # 3. 批量處理迴圈
        new_rows = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, word in enumerate(input_list):
            status_text.text(f"正在處理 ({i+1}/{total_words}): {word}...")
            
            # 檢查是否已存在
            is_exist = False
            if not existing_data.empty and 'word' in existing_data.columns:
                is_exist = (existing_data['word'].astype(str).str.lower() == word.lower()).any()

            if is_exist and not force_refresh:
                status_text.text(f"⏩ 跳過已存在的單字: {word}")
            else:
                # 呼叫 AI 生成
                raw_res = ai_decode_and_save(word, primary_cat, aux_cats)
                
                if raw_res:
                    try:
                        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                        if match:
                            res_data = json.loads(match.group(0), strict=False)
                            # 補齊欄位與分類
                            for col in CORE_COLS:
                                if col not in res_data: res_data[col] = "無"
                            res_data['category'] = display_category
                            new_rows.append(res_data)
                    except:
                        st.error(f"❌ {word} 解析失敗")
                
                # 避免 API 頻率限制
                time.sleep(delay_between)
            
            # 更新進度條
            progress_bar.progress((i + 1) / total_words)

        # 4. 批量寫回資料庫
        if new_rows:
            status_text.text("💾 正在同步至雲端 Sheet2...")
            new_df = pd.DataFrame(new_rows)[CORE_COLS]
            
            if force_refresh and not existing_data.empty:
                # 移除舊的重複項
                new_words = [r['word'].lower() for r in new_rows]
                existing_data = existing_data[~existing_data['word'].str.lower().isin(new_words)]
            
            updated_df = pd.concat([existing_data, new_df], ignore_index=True)
            conn.update(spreadsheet=url, worksheet="Sheet2", data=updated_df)
            
            st.success(f"🎉 批量處理完成！成功新增/更新 {len(new_rows)} 個主題。")
            st.balloons()
        else:
            st.info("沒有新的單字需要處理。")
        
        status_text.empty()
# ==========================================
# Etymon 模組: 頁面邏輯 (優化版)
# ==========================================

def page_etymon_home(df):
    """
    Etymon 門戶首頁：數據概覽與隨機啟發
    """
    st.markdown("<h1 style='text-align: center; color: #1A237E;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>深度知識解構與底層邏輯圖書館</p>", unsafe_allow_html=True)
    st.write("---")
    
    # 1. 數據儀表板 (視覺化指標)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📚 知識庫總量", f"{len(df)} 筆")
    with c2:
        st.metric("🏷️ 涵蓋領域", f"{df['category'].nunique() if not df.empty else 0} 類")
    with c3:
        st.metric("🧬 核心邏輯", f"{df['roots'].nunique() if not df.empty else 0} 組")
    
    st.write("---")

    # 2. 隨機推薦區 (啟發式學習)
    col_header, col_btn = st.columns([4, 1])
    with col_header: 
        st.subheader("💡 隨機探索 (Random Inspiration)")
    with col_btn:
        if st.button("🔄 換一批", use_container_width=True):
            if 'home_sample' in st.session_state: 
                del st.session_state.home_sample
            st.rerun()
    
    if not df.empty:
        # 確保隨機抽取不重複
        if 'home_sample' not in st.session_state:
            st.session_state.home_sample = df.sample(min(3, len(df)))
        
        sample = st.session_state.home_sample
        cols = st.columns(3)
        for i, (index, row) in enumerate(sample.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    
                    # 預覽內容：顯示本質意義 (meaning) 而非 roots，避免 LaTeX 截斷跑版
                    preview_text = fix_content(row['meaning'])
                    if len(preview_text) > 40:
                        preview_text = preview_text[:40] + "..."
                    st.markdown(f"**本質：** {preview_text}")
                    
                    st.write("") # 增加間距
                    
                    # 功能按鈕
                    b1, b2 = st.columns([1, 1])
                    with b1: 
                        speak(row['word'], f"home_{i}")
                    with b2: 
                        if st.button("查看詳情", key=f"h_det_{i}_{row['word']}", use_container_width=True):
                            st.session_state.curr_w = row.to_dict()
                            st.session_state.app_mode = "Etymon Decoder (單字解碼)" # 確保在正確模式
                            # 這裡可以跳轉到學習頁或直接彈出
                            st.toast(f"已選取 {row['word']}")
    else:
        st.info("目前資料庫尚無資料，請前往「解碼實驗室」新增第一個概念。")

    st.write("---")
    st.caption("👈 提示：點擊左側選單進入「學習與搜尋」查看完整清單")


def page_etymon_learn(df):
    """
    學習與搜尋頁面：支援隨機探索與精確查找
    """
    st.title("📖 知識庫探索")
    if df.empty:
        st.warning("目前書架是空的，請先去實驗室解碼一些內容吧！")
        return

    tab_card, tab_list = st.tabs(["🎲 隨機探索 (Explore)", "🔍 搜尋與列表 (Search)"])
    
    # --- Tab 1: 隨機探索 ---
    with tab_card:
        # 分類篩選
        cats = ["全部"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("篩選學習領域", cats, key="learn_cat_select")
        
        f_df = df if sel_cat == "全部" else df[df['category'] == sel_cat]
        
        if 'curr_w' not in st.session_state: 
            st.session_state.curr_w = None
        
        # 隨機按鈕
        if st.button("🎲 抽下一個概念 (Next)", use_container_width=True, type="primary"):
            if not f_df.empty:
                st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
                st.rerun()
        
        # 初始顯示
        if st.session_state.curr_w is None and not f_df.empty:
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
            
        if st.session_state.curr_w:
            # 呼叫優化後的百科卡片
            show_encyclopedia_card(st.session_state.curr_w)

    # --- Tab 2: 搜尋與列表 ---
    with tab_list:
        col_search, col_mode = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("🔍 關鍵字搜尋", placeholder="輸入名稱、定義或領域關鍵字...")
        with col_mode:
            search_mode = st.radio("模式", ["包含", "精確"], horizontal=True)

        if search_query:
            query_clean = search_query.strip().lower()
            if search_mode == "精確":
                mask = df['word'].str.strip().str.lower() == query_clean
            else:
                # 全欄位關鍵字檢索 (針對 word, definition, category, meaning)
                mask = (
                    df['word'].str.contains(query_clean, case=False, na=False) |
                    df['definition'].str.contains(query_clean, case=False, na=False) |
                    df['category'].str.contains(query_clean, case=False, na=False) |
                    df['meaning'].str.contains(query_clean, case=False, na=False)
                )
            
            display_df = df[mask]
            
            if not display_df.empty:
                st.success(f"💡 找到 {len(display_df)} 筆相符結果：")
                for index, row in display_df.iterrows():
                    with st.container(border=True):
                        show_encyclopedia_card(row)
            else:
                st.error(f"❌ 找不到與「{search_query}」相關的內容。")
                # 模糊建議
                fuzzy_mask = df['word'].str.contains(query_clean[:2], case=False, na=False)
                suggestions = df[fuzzy_mask]['word'].tolist()
                if suggestions:
                    st.info(f"您是不是在找：{', '.join(suggestions[:5])}？")
        else:
            # 預設顯示精簡列表
            st.write("### 📚 完整清單預覽")
            # 僅顯示最關鍵的 4 個欄位供快速瀏覽
            st.dataframe(
                df[['word', 'category', 'meaning', 'definition']], 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "word": "主題名稱",
                    "category": "領域",
                    "meaning": "本質意義",
                    "definition": "直覺定義"
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
            model = genai.GenerativeModel('gemini-1.5-flash')
            
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
                    💖 支援我們持續開發：PayPal / 綠界贊助 (ECPay) / Buy Me a Coffee
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
    """
    Handout Pro 頁面邏輯 (專業版)：
    提供圖片處理、AI 結構化排版、即時 Markdown 編輯與高品質 PDF 下載。
    """
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
            st.info("💡 提示：您可以直接在右側編輯器中貼上內容進行排版。AI 自動排版功能目前僅開放給管理員。")

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
    主程式入口：負責導航、權限驗證與全域樣式注入。
    """
    # 1. 注入優化後的自定義 CSS (含 PayPal 樣式)
    inject_custom_css()
    
    # 2. 初始化核心 Session State
    modes = ["Etymon Decoder (單字解碼)", "Handout Pro (講義排版)"]
    
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = modes[0]
        
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False

    # ==========================================
    # 3. 側邊欄 (Sidebar) 佈局
    # ==========================================
    with st.sidebar:
        st.title("🏫 AI 專業教育工作站")
        
        # --- 💖 支持本站營運 (PayPal / ECPay / BMC) ---
        st.markdown("### 💖 支持本站營運")
        st.markdown(f"""
            <div class="sponsor-container">
                <a href="https://www.paypal.com/ncp/payment/8HTS3P48X3YM2" target="_blank" class="sponsor-btn btn-paypal">
                    <span style="font-weight:bold; font-style: italic;">P</span> PayPal 贊助
                </a>
                <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" class="sponsor-btn btn-ecpay">
                    💳 綠界贊助 (台灣)
                </a>
                <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" class="sponsor-btn btn-bmc">
                    <img src="https://cdn.buymeacoffee.com/buttons/bmc-new-btn-logo.svg" class="btn-icon">
                    Buy Me a Coffee
                </a>
            </div>
        """, unsafe_allow_html=True)
        st.caption("講義下載完全免費。您的支持將用於支付 AI 算力與伺服器維護費用，感謝支持！")
        
        st.markdown("---")

        # --- 🔐 管理員權限驗證 ---
        with st.sidebar.expander("🔐 管理員登入"):
            admin_pwd_input = st.text_input("輸入管理密碼", type="password", key="admin_pwd_input_sidebar")
            
            # 驗證邏輯
            if admin_pwd_input:
                if admin_pwd_input == st.secrets.get("ADMIN_PASSWORD", "0000"):
                    st.session_state.is_admin = True
                    st.success("🔓 管理員模式：已解鎖進階功能")
                else:
                    st.session_state.is_admin = False
                    st.error("❌ 密碼錯誤")
            else:
                # 若未輸入密碼，預設為非管理員
                st.session_state.is_admin = False

        st.markdown("---")

        # --- 🧭 模組導航控制 ---
        try:
            current_mode_index = modes.index(st.session_state.app_mode)
        except ValueError:
            current_mode_index = 0

        selected_mode = st.sidebar.selectbox(
            "切換工具模組", 
            modes, 
            index=current_mode_index,
            help="選擇您要使用的 AI 工具"
        )
        
        # 更新模式
        st.session_state.app_mode = selected_mode

    # ==========================================
    # 4. 路由邏輯 (Routing)
    # ==========================================
    
    if st.session_state.app_mode == "Etymon Decoder (單字解碼)":
        # 載入優化後的 12 欄位資料庫
        df = load_db()
        
        # 子選單設定
        menu = ["首頁", "學習與搜尋"]
        if st.session_state.is_admin:
            menu.append("🔬 解碼實驗室")
            
        page = st.sidebar.radio("Etymon 功能選單", menu)
        
        # 頁面跳轉
        if page == "首頁":
            page_etymon_home(df)
        elif page == "學習與搜尋":
            page_etymon_learn(df)
        elif page == "🔬 解碼實驗室":
            if st.session_state.is_admin:
                page_etymon_lab()
            else:
                st.error("⛔ 權限不足：此功能僅限管理員使用。")
            
    elif st.session_state.app_mode == "Handout Pro (講義排版)":
        # 執行講義排版模組
        run_handout_app()

    # --- 側邊欄頁尾資訊 ---
    st.sidebar.markdown("---")
    auth_status = "🔴 管理員模式" if st.session_state.is_admin else "🟢 公開服務模式"
    st.sidebar.caption(f"系統版本: v4.3 Pro Integrated")
    st.sidebar.caption(f"當前狀態: {auth_status}")

if __name__ == "__main__":
    main()
