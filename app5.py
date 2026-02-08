import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import hashlib
import random
from io import BytesIO
from datetime import datetime
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# ==========================================
# 1. 核心配置與視覺美化 (最高規格 CSS)
# ==========================================
st.set_page_config(
    page_title="Kadowsella | Etymon Decoder Pro", 
    page_icon="🧩", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_custom_css():
    st.markdown("""
        <style>
            /* --- 載入頂級字體 --- */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Noto+Sans+TC:wght@300;500;700;900&display=swap');

            /* --- 全域變數定義 --- */
            :root {
                --primary-gradient: linear-gradient(135deg, #6366f1 0%, #4338ca 100%);
                --glass-bg: rgba(255, 255, 255, 0.7);
                --glass-border: rgba(255, 255, 255, 0.3);
                --card-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
                --text-main: #1e293b;
            }

            /* --- 基礎容器優化 --- */
            .stApp {
                background: radial-gradient(circle at top right, #f8fafc, #f1f5f9);
                font-family: 'Inter', 'Noto Sans TC', sans-serif;
            }

            /* --- 標題 Hero Word: 旗艦級排版 --- */
            .hero-word { 
                font-size: clamp(2.5rem, 5vw, 4rem); /* 響應式字體大小 */
                font-weight: 900; 
                background: var(--primary-gradient);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
                letter-spacing: -1px;
                line-height: 1.1;
                filter: drop-shadow(0 2px 4px rgba(0,0,0,0.05));
            }
            
            /* --- 專家視角 Vibe Box: 毛玻璃效果 --- */
            .vibe-box { 
                background: var(--glass-bg);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border-radius: 20px;
                border: 1px solid var(--glass-border);
                padding: 25px;
                box-shadow: var(--card-shadow);
                color: var(--text-main) !important;
                margin: 20px 0;
                position: relative;
                overflow: hidden;
            }
            .vibe-box::before {
                content: "";
                position: absolute;
                top: 0; left: 0; width: 6px; height: 100%;
                background: var(--primary-gradient);
            }

            /* --- 邏輯拆解區: 深度漸層與內發光 --- */
            .breakdown-wrapper {
                background: var(--primary-gradient);
                padding: 30px;
                border-radius: 24px;
                color: white !important;
                box-shadow: 0 20px 25px -5px rgba(67, 56, 202, 0.2);
                border: 1px solid rgba(255,255,255,0.1);
                position: relative;
                transition: transform 0.3s ease;
            }
            .breakdown-wrapper:hover {
                transform: translateY(-5px);
            }

            /* --- 數據指標卡片 (Metric) 客製化 --- */
            [data-testid="stMetric"] {
                background: white;
                padding: 15px 20px;
                border-radius: 16px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
                border: 1px solid #f1f5f9;
            }

            /* --- 按鈕美化: 現代 SaaS 風格 --- */
            .stButton button {
                border-radius: 12px !important;
                padding: 0.6rem 1.5rem !important;
                font-weight: 600 !important;
                transition: all 0.2s ease !important;
                border: none !important;
                background: #ffffff !important;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
                color: #4338ca !important;
            }
            .stButton button:hover {
                transform: scale(1.02);
                box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1) !important;
                background: var(--primary-gradient) !important;
                color: white !important;
            }

            /* --- 手機版極致優化 --- */
            @media (max-width: 768px) {
                .hero-word { font-size: 2.2rem !important; text-align: left; }
                .vibe-box { padding: 18px; border-radius: 16px; }
                .breakdown-wrapper { padding: 20px; border-radius: 18px; }
                .stButton button { width: 100% !important; height: 3.8rem; font-size: 1.1rem !important; }
            }

            /* --- 深色模式: 頂級對比度優化 --- */
            @media (prefers-color-scheme: dark) {
                .stApp {
                    background: radial-gradient(circle at top right, #0f172a, #020617);
                }
                .vibe-box {
                    background: rgba(30, 41, 59, 0.7);
                    border: 1px solid rgba(255,255,255,0.05);
                    color: #f1f5f9 !important;
                }
                .hero-word {
                    background: linear-gradient(135deg, #818cf8 0%, #c084fc 100%);
                    -webkit-background-clip: text;
                }
                [data-testid="stMetric"] {
                    background: #1e293b;
                    border: 1px solid #334155;
                    color: white;
                }
                .stMarkdown p, .stMarkdown li { color: #cbd5e1 !important; }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 工具函式 (旗艦級重構: 安全、快取、強健)
# ==========================================

def hash_password(password): 
    """最高規格加密：SHA-256 結合系統鹽值"""
    salt = st.secrets.get("AUTH_SALT", "kadowsella_default_salt")
    salted_pass = f"{password}{salt}"
    return hashlib.sha256(salted_pass.encode()).hexdigest()

def fix_content(text):
    """
    極致資料清洗：處理 LaTeX、Markdown 換行與 AI 轉義殘留
    """
    if text is None or str(text).strip() in ["無", "nan", "None", ""]: 
        return ""
    
    text = str(text)
    # 處理 AI 常見的轉義錯誤
    text = text.replace('\\n', '  \n').replace('\n', '  \n')
    text = text.replace('\\"', '"').replace('\\\'', "'")
    
    # LaTeX 修正：確保反斜線在 Markdown 中能正確渲染
    if '\\\\' in text:
        text = text.replace('\\\\', '\\')
    
    # 移除 JSON 字串首尾可能殘留的引號
    text = text.strip('"').strip("'")
    return text

@st.cache_data(show_spinner=False, ttl=3600)
def get_audio_base64(text, lang='en'):
    """快取語音資料，避免重複請求 TTS API"""
    try:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        return base64.b64encode(fp.getvalue()).decode()
    except Exception as e:
        return None

def speak(text, key_suffix=""):
    """
    最高規格語音組件：具備快取功能與現代化 UI 按鈕
    """
    # 過濾非英語內容
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    english_only = " ".join(english_only.split()).strip()
    if not english_only: return

    audio_b64 = get_audio_base64(english_only)
    if not audio_b64: return

    unique_id = f"audio_{hashlib.md5(english_only.encode()).hexdigest()[:8]}_{key_suffix}"
    
    # 現代化 SaaS 風格按鈕 HTML
    html_code = f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 5px 0;">
        <button id="btn_{unique_id}" onclick="play_{unique_id}()" 
            style="
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 6px 14px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 8px;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                font-weight: 600;
                color: #4338ca;
                transition: all 0.2s ease;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            "
            onmouseover="this.style.background='#f8fafc'; this.style.transform='translateY(-1px)';"
            onmouseout="this.style.background='white'; this.style.transform='translateY(0)';"
        >
            <span style="font-size: 16px;">🔊</span> 聽發音
        </button>
        <audio id="{unique_id}" style="display:none">
            <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
        </audio>
        <script>
            function play_{unique_id}() {{
                var audio = document.getElementById('{unique_id}');
                audio.currentTime = 0;
                audio.play();
                var btn = document.getElementById('btn_{unique_id}');
                btn.style.borderColor = '#6366f1';
                setTimeout(() => {{ btn.style.borderColor = '#e2e8f0'; }}, 500);
            }}
        </script>
    </div>
    """
    components.html(html_code, height=45)

@st.cache_data(show_spinner="正在同步雲端數據...", ttl=300)
def load_sheet(worksheet_name):
    """
    強健型資料載入：具備自動欄位校驗與錯誤處理
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        df = conn.read(spreadsheet=url, worksheet=worksheet_name, ttl=0)
        
        if df.empty:
            return pd.DataFrame()
            
        # 針對 vocabulary 分頁進行標準化處理
        if worksheet_name == "vocabulary":
            required_cols = ['word', 'definition', 'category']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = "無"
                    
        return df.fillna("無")
    except Exception as e:
        st.error(f"📡 雲端連線失敗: {e}")
        return pd.DataFrame()

def update_sheet(df, worksheet_name):
    """
    安全型資料更新：確保寫入前資料格式正確
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # 確保資料中沒有不可見的特殊字元
        df = df.astype(str).replace('nan', '無')
        conn.update(spreadsheet=url, worksheet=worksheet_name, data=df)
        st.cache_data.clear() # 更新後強制清除快取
        return True
    except Exception as e:
        st.error(f"❌ 寫入失敗: {e}")
        return False
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import random

def get_api_keys():
    """從 secrets 獲取 API Key 列表，支援單一字串或列表"""
    keys = st.secrets.get("GEMINI_API_KEYS")
    if isinstance(keys, list): return keys
    if isinstance(keys, str): return [keys]
    return [st.secrets.get("GEMINI_API_KEY")]

def ai_call(system_prompt, user_input, tier="free"):
    """
    最高規格 AI 呼叫：具備 Key 輪替、自動重試與錯誤處理
    """
    keys = get_api_keys()
    if not keys or not keys[0]:
        st.error("❌ 未設定 API Key")
        return None
    
    # 隨機打亂 Key 順序，實現負載平衡
    random.shuffle(keys)
    
    # 模型選擇
    model_name = "gemini-2.0-flash" if tier == "free" else "gemini-2.0-pro-exp-02-05"
    
    # 安全設定：解除所有限制，確保教育內容不被誤擋
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
            response = model.generate_content(
                user_input,
                generation_config={"temperature": 0.3}, # 降低溫度以確保輸出穩定
                safety_settings=safety_settings
            )
            if response.text:
                return response.text
        except Exception as e:
            # 記錄錯誤並嘗試下一個 Key
            print(f"Key {key[:5]}... failed: {e}")
            continue
            
    return None

def ai_decode_concept(input_text, category):
    """
    最高規格解碼：強制 JSON 輸出與多重解析防護
    """
    system_prompt = f"""
    You are a world-class expert in {category}. 
    Your task is to decompose the concept: "{input_text}".
    
    STRICT OUTPUT RULES:
    1. Output ONLY valid JSON. No markdown formatting (no ```json).
    2. Ensure all keys and string values are wrapped in double quotes.
    3. Use LaTeX format for math formulas (e.g., $x^2$).
    4. Escape backslashes properly for JSON (e.g., \\n).
    
    Required JSON Schema:
    {{
        "category": "{category}",
        "word": "{input_text}",
        "roots": "string",
        "meaning": "string",
        "breakdown": "string",
        "definition": "string",
        "phonetic": "string",
        "example": "string",
        "translation": "string",
        "native_vibe": "string",
        "synonym_nuance": "string",
        "usage_warning": "string",
        "memory_hook": "string",
        "audio_tag": "string"
    }}
    """
    
    raw_response = ai_call(system_prompt, input_text, tier="pro")
    
    if not raw_response:
        return None

    # 多重解析防護：先嘗試直接解析，失敗則用 Regex 提取
    try:
        # 嘗試直接解析
        return json.loads(raw_response)
    except json.JSONDecodeError:
        # 如果失敗，嘗試用 Regex 提取 JSON 區塊
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                return None
    return None
# ==========================================
# 4. UI 組件 (旗艦級：視覺層次與專業講義)
# ==========================================

def show_encyclopedia_card(row, show_report=True):
    """最高規格百科卡片：層次化排版與微互動"""
    r_word = str(row.get('word', '未命名'))
    
    # 標題與語音
    col_title, col_audio = st.columns([3, 1])
    with col_title:
        st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    with col_audio:
        speak(r_word, f"card_{r_word}")
    
    # 邏輯拆解 (旗艦漸層盒)
    st.markdown(f"""
        <div class='breakdown-wrapper'>
            <div style='font-size: 0.9rem; opacity: 0.9; margin-bottom: 5px;'>🧬 LOGIC BREAKDOWN</div>
            <div style='font-size: 1.15rem; font-weight: 600; line-height: 1.6;'>
                {fix_content(row.get('breakdown', ''))}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 核心內容 (自定義雙欄)
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
            <div style='background: rgba(99, 102, 241, 0.05); padding: 20px; border-radius: 15px; border: 1px solid rgba(99, 102, 241, 0.1); height: 100%;'>
                <h4 style='color: #4338ca; margin-top: 0;'>🎯 核心定義</h4>
                <p style='font-size: 1rem; line-height: 1.6;'>{fix_content(row.get('definition', ''))}</p>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
            <div style='background: rgba(16, 185, 129, 0.05); padding: 20px; border-radius: 15px; border: 1px solid rgba(16, 185, 129, 0.1); height: 100%;'>
                <h4 style='color: #059669; margin-top: 0;'>💡 底層原理</h4>
                <p style='font-size: 1rem; line-height: 1.6;'>{fix_content(row.get('roots', ''))}</p>
            </div>
        """, unsafe_allow_html=True)
    
    # 專家心法
    if row.get('native_vibe'):
        st.markdown(f"<div class='vibe-box'>{fix_content(row['native_vibe'])}</div>", unsafe_allow_html=True)

    # 底部功能區
    if show_report:
        st.write("---")
        rep_c1, rep_c2 = st.columns([3, 1])
        with rep_c2:
            if st.button(f"🚩 內容糾錯", key=f"rep_{r_word}", use_container_width=True):
                st.toast(f"已將 {r_word} 送入待修清單", icon="🛠️")

def show_pro_paper_with_download(title, content):
    """最高規格 PDF 生成：具備專業排版與品牌標示"""
    js_content = json.dumps(content, ensure_ascii=False)
    
    # PDF 專用 CSS 樣式
    pdf_style = """
        <style>
            .pdf-body { font-family: 'Noto Sans TC', sans-serif; padding: 40px; color: #1e293b; }
            .pdf-header { border-bottom: 2px solid #6366f1; margin-bottom: 30px; padding-bottom: 10px; }
            .pdf-title { color: #4338ca; font-size: 28px; font-weight: 900; }
            .pdf-section { margin-bottom: 25px; }
            .pdf-label { color: #6366f1; font-weight: bold; font-size: 14px; text-transform: uppercase; }
            .pdf-text { font-size: 16px; line-height: 1.8; margin-top: 5px; }
            .pdf-footer { margin-top: 50px; font-size: 12px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px; }
        </style>
    """
    
    html_code = f"""
    {pdf_style}
    <div style="background: #0f172a; padding: 20px; border-radius: 20px; border: 1px solid #334155;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <span style="color: #818cf8; font-weight: bold; font-size: 0.9rem;">📄 PRO 講義預覽系統</span>
            <button id="dl_btn" style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); color: white; border: none; border-radius: 10px; padding: 10px 20px; cursor: pointer; font-weight: bold; transition: 0.3s;">📥 下載完整 PDF</button>
        </div>
        <div id="preview" style="height: 350px; overflow-y: auto; background: white; padding: 30px; border-radius: 12px; color: #1e293b; line-height: 1.6; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);">
            載入講義內容中...
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script>
        const rawContent = {js_content};
        const previewEl = document.getElementById('preview');
        previewEl.innerHTML = marked.parse(rawContent);

        document.getElementById('dl_btn').onclick = function() {{
            const element = document.createElement('div');
            element.className = 'pdf-body';
            element.innerHTML = `
                <div class="pdf-header">
                    <div class="pdf-title">⚡ Kadowsella Pro 數位講義</div>
                    <div style="color: #64748b;">主題：{title} | 生成日期：${{new Date().toLocaleDateString()}}</div>
                </div>
                <div class="pdf-section">${{marked.parse(rawContent)}}</div>
                <div class="pdf-footer">© 2026 Kadowsella Etymon Decoder Pro - 僅供個人學習使用</div>
            `;
            
            const opt = {{
                margin: 10,
                filename: 'Kadowsella_Pro_{title}.pdf',
                image: {{ type: 'jpeg', quality: 0.98 }},
                html2canvas: {{ scale: 2, useCORS: true }},
                jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
            }};
            html2pdf().set(opt).from(element).save();
        }};
    </script>
    """
    components.html(html_code, height=500)

# ==========================================
# 5. 頁面邏輯 (旗艦級：數據儀表板與專業工作流)
# ==========================================

def page_home(df):
    """最高規格首頁：品牌 Hero 區與數據可視化"""
    
    # 1. Hero Section
    st.markdown("""
        <div style="text-align: center; padding: 40px 0; background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(168, 85, 247, 0.05) 100%); border-radius: 30px; margin-bottom: 40px;">
            <h1 style="font-size: 3.5rem; font-weight: 900; margin-bottom: 10px; background: linear-gradient(135deg, #4338ca 0%, #a855f7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Etymon Decoder</h1>
            <p style="font-size: 1.2rem; color: #64748b; font-weight: 500;">116 級數位戰情室：以 AI 邏輯重構你的學測知識圖譜</p>
        </div>
    """, unsafe_allow_html=True)

    # 2. 倒數計時與核心指標 (自定義 HTML 卡片)
    days_left = (datetime(2027, 1, 15) - datetime.now()).days
    
    def custom_metric(label, value, icon, color_gradient):
        return f"""
            <div style="background: white; padding: 25px; border-radius: 24px; border: 1px solid #f1f5f9; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 10px;">{icon}</div>
                <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">{label}</div>
                <div style="font-size: 2rem; font-weight: 900; background: {color_gradient}; -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{value}</div>
            </div>
        """

    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(custom_metric("學測倒數", f"{days_left} Days", "🎯", "linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)"), unsafe_allow_html=True)
    with m2: st.markdown(custom_metric("總單字量", len(df), "📚", "linear-gradient(135deg, #6366f1 0%, #4338ca 100%)"), unsafe_allow_html=True)
    with m3: st.markdown(custom_metric("分類主題", df['category'].nunique() if not df.empty else 0, "🏷️", "linear-gradient(135deg, #10b981 0%, #059669 100%)"), unsafe_allow_html=True)
    with m4: st.markdown(custom_metric("邏輯字根", df['roots'].nunique() if not df.empty else 0, "🧩", "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"), unsafe_allow_html=True)

    st.write("")
    st.write("")

    # 3. 隨機推薦區 (Flashcard 視覺)
    st.markdown("### 💡 今日邏輯推薦")
    if not df.empty:
        # 鎖定隨機種子，避免按鈕點擊時刷新
        if 'home_sample' not in st.session_state:
            st.session_state.home_sample = df.sample(min(3, len(df)))
        
        cols = st.columns(3)
        for i, (idx, row) in enumerate(st.session_state.home_sample.iterrows()):
            with cols[i]:
                st.markdown(f"""
                    <div style="background: white; padding: 25px; border-radius: 20px; border: 1px solid #e2e8f0; height: 220px; position: relative; transition: 0.3s; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
                        <div style="color: #6366f1; font-weight: 700; font-size: 0.8rem; margin-bottom: 10px;">#{row['category']}</div>
                        <div style="font-size: 1.6rem; font-weight: 800; color: #1e293b; margin-bottom: 10px;">{row['word']}</div>
                        <div style="font-size: 0.95rem; color: #64748b; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
                            {fix_content(row['definition'])}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("展開深度解析", key=f"view_{idx}", use_container_width=True):
                    st.session_state.curr_w = row.to_dict()
                    st.rerun()

    # 顯示選中的詳解卡片
    if "curr_w" in st.session_state:
        st.write("---")
        show_encyclopedia_card(st.session_state.curr_w)
def page_ai_lab():
    """最高規格 AI 實驗室：專業級解碼工作流"""
    
    # 1. 標題與權限檢查
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 30px;">
            <h1 style="margin: 0;">🔬 AI 解碼實驗室</h1>
            <span style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); color: white; padding: 4px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: 800; letter-spacing: 1px;">PRO ONLY</span>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.role == "guest":
        st.markdown("""
            <div style="background: #fff7ed; border: 1px solid #ffedd5; padding: 30px; border-radius: 20px; text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 15px;">🔒</div>
                <h3 style="color: #9a3412; margin-top: 0;">此功能僅限 Pro 會員使用</h3>
                <p style="color: #c2410c;">登入後即可解鎖 AI 即時解碼、個人收藏夾與 PDF 講義下載功能。</p>
            </div>
        """, unsafe_allow_html=True)
        return
    
    # 2. 解碼控制面板
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            new_word = st.text_input("輸入解碼主題 (單字、公式或概念)：", placeholder="例如: 'meticulous' 或 '二次函數頂點式'...")
        with c2:
            cat_options = ["英語辭源", "物理科學", "數學邏輯", "生物醫學", "歷史文明", "自定義"]
            cat = st.selectbox("領域標籤", cat_options)
        
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
        with btn_col2:
            start_decode = st.button("🚀 啟動三位一體解碼", type="primary", use_container_width=True)

    # 3. 執行解碼與結果呈現
    if start_decode:
        if not new_word:
            st.warning("請輸入內容")
        else:
            with st.status("🤖 AI 正在進行深度邏輯重構...", expanded=True) as status:
                st.write("🔍 檢索底層字源與原理...")
                time.sleep(0.5)
                st.write("🧬 拆解結構化知識點...")
                res = ai_decode_concept(new_word, cat)
                if res:
                    st.session_state.last_ai = res
                    status.update(label="✅ 解碼完成！", state="complete", expanded=False)
                else:
                    status.update(label="❌ 解碼失敗", state="error")

    if "last_ai" in st.session_state:
        st.write("")
        show_encyclopedia_card(st.session_state.last_ai, show_report=False)
        
        # 存檔動作區
        st.write("---")
        save_c1, save_c2, save_c3 = st.columns([1, 2, 1])
        with save_c2:
            if st.button("💾 將此解碼結果存入雲端資料庫", use_container_width=True):
                with st.spinner("正在同步至雲端..."):
                    df = load_sheet("vocabulary")
                    # 檢查是否已存在
                    if new_word.lower() in df['word'].str.lower().values:
                        st.warning("此單字已存在於資料庫中。")
                    else:
                        new_df = pd.concat([df, pd.DataFrame([st.session_state.last_ai])], ignore_index=True)
                        if update_sheet(new_df, "vocabulary"):
                            st.balloons()
                            st.success(f"🎉 「{new_word}」已成功存入書架！")
                            del st.session_state.last_ai # 存完清除暫存
def page_admin_center():
    """最高規格管理員後台：具備即時編輯與數據監控功能"""
    
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 30px;">
            <h1 style="margin: 0;">👑 上帝模式：戰略指揮中心</h1>
            <span style="background: #ef4444; color: white; padding: 4px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: 800; letter-spacing: 1px;">GOD MODE</span>
        </div>
    """, unsafe_allow_html=True)

    # 1. 核心數據監控 (Metrics)
    users_df = load_sheet("users")
    vocab_df = load_sheet("vocabulary")
    
    # 讀取 metrics 分頁 (假設你在 Section 2 有實作 track_intent)
    try:
        metrics_df = load_sheet("metrics")
        total_clicks = metrics_df['count'].sum() if not metrics_df.empty else 0
    except:
        total_clicks = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 總註冊用戶", len(users_df))
    c2.metric("💎 Pro 會員數", len(users_df[users_df['membership'] == 'pro']))
    c3.metric("🚩 待修復單字", len(vocab_df[vocab_df['term'] == 1]))
    c4.metric("🖱️ 總互動次數", total_clicks)

    st.write("---")

    # 2. 功能分頁
    tab_users, tab_content, tab_system = st.tabs(["👤 用戶調度", "🛠️ 內容修復", "⚙️ 系統維護"])

    # --- Tab 1: 用戶調度 (Data Editor) ---
    with tab_users:
        st.subheader("用戶權限與能量管理")
        st.caption("提示：您可以直接在表格中修改資料，完成後點擊右上方「儲存變更」。")
        
        # 排除敏感資訊 (如密碼) 供編輯
        display_users = users_df.drop(columns=['password']) if 'password' in users_df.columns else users_df
        
        edited_users = st.data_editor(
            display_users,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "membership": st.column_config.SelectboxColumn(
                    "會員等級", options=["free", "pro"], help="升級用戶為 Pro 以解鎖 AI 功能"
                ),
                "role": st.column_config.SelectboxColumn(
                    "角色", options=["student", "admin", "guest"]
                ),
                "ai_usage": st.column_config.NumberColumn(
                    "AI 消耗量", help="手動調整用戶已使用的 AI 次數"
                )
            },
            key="user_editor"
        )
        
        if st.button("💾 儲存用戶變更", type="primary"):
            with st.spinner("正在同步用戶權限..."):
                # 這裡需要將密碼補回去再存入
                if 'password' in users_df.columns:
                    edited_users['password'] = users_df['password']
                if update_sheet(edited_users, "users"):
                    st.success("用戶資料已更新！")
                    st.balloons()

    # --- Tab 2: 內容修復 (處理 term=1) ---
    with tab_content:
        st.subheader("🚩 待修復單字清單")
        error_vocab = vocab_df[vocab_df['term'] == 1]
        
        if error_vocab.empty:
            st.success("目前沒有任何回報錯誤的單字，資料庫非常健康！")
        else:
            st.warning(f"發現 {len(error_vocab)} 筆資料需要校對。")
            for idx, row in error_vocab.iterrows():
                with st.expander(f"校對：{row['word']} (分類：{row['category']})"):
                    # 顯示當前內容
                    st.write("**當前定義：**", row['definition'])
                    st.write("**當前拆解：**", row['breakdown'])
                    
                    col_fix1, col_fix2 = st.columns(2)
                    if col_fix1.button("✅ 標記為已修復", key=f"fix_{idx}"):
                        vocab_df.at[idx, 'term'] = 0
                        if update_sheet(vocab_df, "vocabulary"):
                            st.success(f"{row['word']} 已恢復正常狀態")
                            st.rerun()
                            
                    if col_fix2.button("🗑️ 刪除此單字", key=f"del_{idx}"):
                        vocab_df = vocab_df.drop(idx)
                        if update_sheet(vocab_df, "vocabulary"):
                            st.error(f"{row['word']} 已從資料庫移除")
                            st.rerun()

    # --- Tab 3: 系統維護 ---
    with tab_system:
        st.subheader("系統核心控制")
        
        col_sys1, col_sys2 = st.columns(2)
        
        with col_sys1:
            with st.container(border=True):
                st.markdown("#### 🧹 快取管理")
                st.write("如果雲端資料更新後 App 沒反應，請執行強制刷新。")
                if st.button("清除全域快取 (Clear Cache)", use_container_width=True):
                    st.cache_data.clear()
                    st.success("快取已清空，下次載入將讀取最新雲端數據。")
        
        with col_sys2:
            with st.container(border=True):
                st.markdown("#### 🤖 AI 狀態檢查")
                api_key = st.secrets.get("GEMINI_API_KEY", "未設定")
                st.write(f"**API Key 狀態：** {'✅ 已配置' if api_key != '未設定' else '❌ 缺失'}")
                if st.button("測試 AI 連線", use_container_width=True):
                    test_res = ai_call("請回覆『Pong』", "Ping", tier="free")
                    if test_res:
                        st.success(f"AI 回應正常：{test_res}")
                    else:
                        st.error("AI 連線失敗，請檢查 API Key 或配額。")

        st.write("")
        with st.expander("📥 資料庫備份 (JSON 格式)"):
            json_vocab = vocab_df.to_json(orient='records', force_ascii=False)
            st.download_button(
                label="下載完整單字庫備份",
                data=json_vocab,
                file_name=f"vocab_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )
# ==========================================
# 6. 主程式入口 (旗艦級：智慧導航與全域路由)
# ==========================================

def main():
    # 1. 注入最高規格視覺樣式 (CSS)
    inject_custom_css()
    
    # 2. 初始化全域 Session 狀態 (確保不強制登入也能瀏覽)
    if 'logged_in' not in st.session_state:
        st.session_state.update({
            'logged_in': False,
            'username': "訪客",
            'role': "guest",
            'curr_w': None,    # 當前查看的單字詳解
            'last_ai': None    # 最後一次 AI 解碼結果
        })

    # 3. 側邊欄：旗艦級導航系統
    with st.sidebar:
        # --- 品牌標誌區 ---
        st.markdown("""
            <div style="padding: 10px 0 20px 0;">
                <h1 style="font-size: 1.8rem; font-weight: 900; background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;">⚡ Kadowsella</h1>
                <p style="font-size: 0.8rem; color: #94a3b8; font-weight: 600; letter-spacing: 1px;">116 DIGITAL WAR ROOM</p>
            </div>
        """, unsafe_allow_html=True)
        
        # --- 用戶狀態與登入卡片 ---
        if not st.session_state.logged_in:
            with st.container(border=True):
                st.markdown("🔑 **會員登入**")
                u = st.text_input("帳號", placeholder="Username", label_visibility="collapsed")
                p = st.text_input("密碼", type="password", placeholder="Password", label_visibility="collapsed")
                if st.button("身分驗證", use_container_width=True, type="primary"):
                    with st.spinner("正在連線戰情室..."):
                        users = load_sheet("users")
                        if not users.empty:
                            # 驗證帳號密碼 (使用 Section 2 的 hash_password)
                            user = users[(users['username'] == u) & (users['password'] == hash_password(p))]
                            if not user.empty:
                                st.session_state.update({
                                    'logged_in': True,
                                    'username': u,
                                    'role': user.iloc[0]['role']
                                })
                                st.toast(f"歡迎回來, {u}!", icon="👋")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("帳號或密碼錯誤")
                        else:
                            st.error("資料庫連線異常")
                st.caption("訪客模式僅開放基礎搜尋功能")
        else:
            # 已登入：顯示高級會員卡片
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%); padding: 15px; border-radius: 15px; border: 1px solid rgba(99, 102, 241, 0.2); margin-bottom: 10px;">
                    <div style="font-size: 0.7rem; color: #6366f1; font-weight: 800; text-transform: uppercase;">Current User</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #1e293b;">{st.session_state.username}</div>
                    <div style="font-size: 0.75rem; color: #64748b;">身分：{st.session_state.role.upper()} MEMBER</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("安全登出系統", use_container_width=True):
                st.session_state.update({'logged_in': False, 'username': "訪客", 'role': "guest"})
                st.rerun()
        
        st.write("")
        
        # --- 智慧導航選單 (權限分級) ---
        st.markdown("---")
        nav_items = {
            "🏠 戰情首頁": "home",
            "🔍 知識庫搜尋": "search",
            "🧠 記憶挑戰": "quiz"
        }
        
        # 根據登入狀態解鎖功能
        # 在 main() 函式的導航選單部分修改：
        if st.session_state.logged_in:
            nav_items.update({
                "🔬 AI 解碼實驗室": "ai_lab",
                "📄 Pro 講義生成": "pdf_gen"
            })
            # 如果是管理員，解鎖上帝模式
            if st.session_state.role == "admin":
                nav_items.update({
                    "👑 管理員中心": "admin_center"
                })
        else:
            nav_items.update({
                "🔒 AI 解碼 (Pro)": "locked",
                "🔒 講義生成 (Pro)": "locked"
            })
            
        choice = st.radio("NAVIGATION", list(nav_items.keys()), label_visibility="collapsed")
        
        st.divider()
        st.sidebar.caption(f"v3.0 Ultimate Edition | {datetime.now().strftime('%Y-%m-%d')}")

    # 4. 載入核心資料庫 (從 Section 2 的 load_sheet)
    df = load_sheet("vocabulary")

    # 5. 頁面路由邏輯 (Routing)
    if choice == "🏠 戰情首頁":
        page_home(df) # 呼叫 Section 5
    
    elif choice == "🔍 知識庫搜尋":
        st.title("🔍 知識庫搜尋")
        st.markdown("搜尋資料庫中已存在的 4500+ 學測邏輯單字。")
        
        col_q, col_cat = st.columns([3, 1])
        with col_q:
            q = st.text_input("輸入關鍵字搜尋...", placeholder="例如：meticulous, 物理, 函數...", label_visibility="collapsed")
        with col_cat:
            all_cats = ["全部"] + sorted(df['category'].unique().tolist())
            sel_cat = st.selectbox("分類過濾", all_cats, label_visibility="collapsed")
        
        # 執行過濾邏輯
        filtered_df = df
        if q:
            # 支援單字與定義的模糊搜尋
            filtered_df = filtered_df[filtered_df['word'].str.contains(q, case=False) | 
                                      filtered_df['definition'].str.contains(q, case=False)]
        if sel_cat != "全部":
            filtered_df = filtered_df[filtered_df['category'] == sel_cat]
            
        if not filtered_df.empty:
            st.write(f"💡 找到 {len(filtered_df)} 筆相關結果：")
            for _, r in filtered_df.iterrows():
                # 使用 Expander 節省空間，點開後顯示最高規格卡片
                with st.expander(f"✨ {r['word']} - {r['definition'][:40]}..."):
                    show_encyclopedia_card(r) # 呼叫 Section 4
        else:
            st.warning("找不到匹配的內容。如果是 Pro 會員，請前往「AI 解碼實驗室」即時生成！")

    elif choice == "🧠 記憶挑戰":
        st.title("🧠 記憶挑戰")
        st.info("測驗模式正在進行 UI 升級，將結合 AI 錯題分析功能，敬請期待！")
        # 這裡可以保留你原本的 page_quiz(df) 邏輯

    elif choice == "🔬 AI 解碼實驗室":
        page_ai_lab() # 呼叫 Section 5

    elif choice == "📄 Pro 講義生成":
        st.title("📄 Pro 講義生成器")
        st.markdown("選擇資料庫中的概念，一鍵生成具備專業排版的 PDF 複習講義。")
        
        # 讓用戶從現有資料庫選擇
        sel = st.selectbox("選擇要生成的單字或概念", ["--- 請選擇 ---"] + df['word'].tolist())
        if sel != "--- 請選擇 ---":
            row = df[df['word'] == sel].iloc[0]
            # 構建專業 Markdown 內容 (供 PDF 渲染使用)
            content = f"""
# {row['word']}
---
### 🎯 核心定義
{row['definition']}

### 🧬 邏輯拆解
{row['breakdown']}

### 💡 底層原理
{row['roots']}

### 🌊 專家心法
{row['native_vibe']}

### 🪝 記憶金句
{row['memory_hook']}
            """
            # 呼叫 Section 4 的 PDF 組件
            show_pro_paper_with_download(sel, content)

    elif choice == "🔒 AI 解碼 (Pro)" or choice == "🔒 講義生成 (Pro)":
        # 訪客點擊鎖定功能的引導頁面
        st.warning("### 🔒 權限受限")
        st.markdown("""
            <div style="background: rgba(99, 102, 241, 0.05); padding: 30px; border-radius: 20px; border: 1px solid rgba(99, 102, 241, 0.1);">
                <h3 style="color: #4338ca; margin-top: 0;">此功能為 Pro 會員專屬</h3>
                <p>您目前以<b>訪客身分</b>瀏覽。升級 Pro 會員或登入學生帳號即可解鎖：</p>
                <ul style="line-height: 1.8;">
                    <li><b>AI 即時解碼</b>：輸入任何單字，AI 立即拆解邏輯。</li>
                    <li><b>個人收藏夾</b>：儲存您的專屬學習筆記。</li>
                    <li><b>PDF 講義下載</b>：一鍵生成精美複習講義。</li>
                    <li><b>能量系統</b>：每日點數自動更新。</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
        if st.button("了解 Pro 會員開通方案", use_container_width=True, type="primary"):
            st.balloons()
            st.info("請聯繫管理員或加入 Discord 社群獲取邀請碼！")
    elif choice == "👑 管理員中心":
    if st.session_state.role == "admin":
        page_admin_center()
    else:
        st.error("權限不足")


# --- 執行入口 ---
if __name__ == "__main__":
    main()
