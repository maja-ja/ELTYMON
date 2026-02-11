# ==========================================
# 0. 基礎套件導入
# ==========================================
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
import streamlit.components.v1 as components
import markdown
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心工具函式
# ==========================================

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    return str(text).replace('\\n', '  \n').replace('\n', '  \n').strip('"').strip("'")

def speak(text, key_suffix=""):
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        components.html(f"""
        <html><body>
            <style>
                :root {{ --border-color: #B3E5FC; --accent-text-color: #0277BD; --speak-btn-bg: #F0F7FF; }}
                @media (prefers-color-scheme: dark) {{ :root {{ --border-color: #30363d; --accent-text-color: #f0f6fc; --speak-btn-bg: #161B22; }} }}
                .speak-btn {{ background: var(--speak-btn-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; width: 100%; font-family: sans-serif; font-size: 14px; font-weight: 600; color: var(--accent-text-color); transition: 0.2s; }}
                .speak-btn:active {{ transform: scale(0.96); }}
            </style>
            <button class="speak-btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
            <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        </body></html>""", height=50)
    except: pass

def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet")

def log_user_intent(label):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        try: 
            m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
            m_df['count'] = pd.to_numeric(m_df['count'], errors='coerce').fillna(0).astype(int)
        except: m_df = pd.DataFrame(columns=['label', 'count'])
        if label in m_df['label'].values: m_df.loc[m_df['label'] == label, 'count'] += 1
        else: m_df = pd.concat([m_df, pd.DataFrame([{'label': label, 'count': 1}])], ignore_index=True)
        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)
    except: pass

@st.cache_data(ttl=3600) 
def load_db():
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe']
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=get_spreadsheet_url(), ttl=0)
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無")[COL_NAMES].reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

def generate_printable_html(title, text_content, **kwargs):
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 500); };" if kwargs.get("auto_download") else ""
    return f"""
    <html><head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>@page {{ size: A4; margin: 0; }} body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.8; }} #printable-area {{ background: white; width: 210mm; min-height: 297mm; padding: 20mm 25mm; box-sizing: border-box; }} h1, h2, h3 {{ color: #1a237e; }}</style>
    </head><body>
        <div id="printable-area"><h1>{title}</h1><div>{html_body}</div></div>
        <script>function downloadPDF(){{const e=document.getElementById('printable-area');html2pdf().set({{margin:0,filename:'{title}.pdf',image:{{type:'jpeg',quality:1}},html2canvas:{{scale:3}},jsPDF:{{unit:'mm',format:'a4'}}}}).from(e).save();}}{auto_js}</script>
    </body></html>"""

# ==========================================
# 2. 手機版 UI (雙色主題與布局)
# ==========================================

def inject_dual_theme_ui():
    st.markdown("""
        <style>
            :root {
                --main-bg: #F8F9FA; --card-bg: white; --text-color: #212529; --subtle-text-color: #6c757d;
                --border-color: #f0f0f0; --shadow-color: rgba(0, 0, 0, 0.07);
                --accent-bg: #E3F2FD; --accent-text-color: #1976D2; --h1-color: #1A237E;
            }
            @media (prefers-color-scheme: dark) {
                :root {
                    --main-bg: #0E1117; --card-bg: #161B22; --text-color: #e3e3e3; --subtle-text-color: #a0a0a0;
                    --border-color: #30363d; --shadow-color: rgba(0, 0, 0, 0.2);
                    --accent-bg: #1f6feb; --accent-text-color: #f0f6fc; --h1-color: #90CAF9;
                }
            }
            .main { background-color: var(--main-bg) !important; }
            .block-container { max-width: 480px !important; padding: 2.5rem 1.2rem 6rem 1.2rem !important; }
            [data-testid="stSidebar"], header { display: none; }
            
            .word-card {
                background: var(--card-bg); border-radius: 20px; padding: 25px;
                box-shadow: 0 10px 30px var(--shadow-color); margin-bottom: 20px; border: 1px solid var(--border-color);
            }
            
            /* 🔥 修正：縮小淺藍色字根標籤的字體 */
            .roots-tag {
                background: var(--accent-bg); 
                color: var(--accent-text-color); 
                padding: 4px 10px;
                border-radius: 10px; 
                font-size: 0.8rem; /* 從 0.9rem 縮小到 0.8rem */
                font-weight: bold; 
                display: inline-block;
            }
            
            .stButton > button, .stTextInput > div > div > input, .stSelectbox > div > div > div {
                border-radius: 15px !important; height: 50px !important; transition: transform 0.2s ease;
            }
            .stButton > button:active { transform: scale(0.95); }
            
            .sponsor-banner {
                background: linear-gradient(90deg, #FFDD00, #FBB03B);
                color: #000 !important; padding: 12px; border-radius: 15px;
                text-align: center; font-weight: bold; font-size: 0.85rem;
                margin-bottom: 15px; cursor: pointer; display: block; text-decoration: none;
            }
        </style>
    """, unsafe_allow_html=True)

def mobile_home_page(df):
    """手機版首頁：融合領域篩選、精確搜尋與隨機探索"""
    
    # 1. 贊助印象 (頂部)
    st.markdown("""
        <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" class="sponsor-banner">
            💖 喜歡這個工具嗎？點此贊助支持開發成本！
        </a>
    """, unsafe_allow_html=True)

    # 2. 領域選擇
    all_cats = ["🌍 全部領域"] + sorted(df['category'].unique().tolist())
    selected_cat = st.selectbox("選擇學習領域", all_cats, label_visibility="collapsed")

    # 3. 搜尋與隨機抽
    col_search, col_rand = st.columns([4, 1])
    with col_search:
        query = st.text_input("輸入單字查詢...", placeholder="例如: 熵", label_visibility="collapsed")
    with col_rand:
        if st.button("🎲", help="從選定領域隨機抽取"): 
            sample_pool = df if selected_cat == "🌍 全部領域" else df[df['category'] == selected_cat]
            if not sample_pool.empty:
                st.session_state.selected_word = sample_pool.sample(1).iloc[0].to_dict()
                st.rerun()

    # 4. 搜尋與顯示邏輯
    target_row = None
    if query:
        exact_match = df[df['word'].str.lower() == query.strip().lower()]
        if not exact_match.empty:
            target_row = exact_match.iloc[0].to_dict()
        else:
            fuzzy_match = df[df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
            if not fuzzy_match.empty:
                target_row = fuzzy_match.iloc[0].to_dict()
            else:
                st.info("找不到該單字，點擊 🎲 試試隨機探索？")
    elif "selected_word" in st.session_state:
        target_row = st.session_state.selected_word
    else:
        if not df.empty:
            target_row = df.sample(1).iloc[0].to_dict()
            st.session_state.selected_word = target_row

    # 5. 渲染卡片
    if target_row:
        w = target_row['word']
        st.markdown(f"""
        <div class="word-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <h1 style="margin:0; color:var(--h1-color);">{w}</h1>
                    <p style="color:var(--subtle-text-color); margin:5px 0 15px 0; font-size:0.9rem;">/{fix_content(target_row['phonetic'])}/</p>
                </div>
                <span style="font-size:0.75rem; background:var(--main-bg); padding:4px 8px; border-radius:8px; color:var(--subtle-text-color);">
                    {target_row['category']}
                </span>
            </div>
            <span class="roots-tag">🧬 {fix_content(target_row['roots'])}</span>
            <p style="margin-top:20px; font-size:1.1rem; line-height:1.7; color:var(--text-color);">{fix_content(target_row['definition'])}</p>
            <div style="background:var(--main-bg); padding:15px; border-radius:12px; font-size:0.95rem; color:var(--text-color); margin-top:15px;">
                💡 <b>實例:</b> {fix_content(target_row['example'])}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            speak(w, f"m_speak_{w}")
        with c2:
            if st.button("📄 生成講義", type="primary"):
                log_user_intent(f"jump_{w}")
                st.session_state.manual_input_content = f"## 專題講義：{w}\n\n### 🧬 核心邏輯\n{fix_content(target_row['breakdown'])}\n\n### 🎯 核心定義\n{fix_content(target_row['definition'])}\n\n### 💡 應用實例\n{fix_content(target_row['example'])}"
                st.session_state.mobile_nav = "📄 製作講義"
                st.rerun()
        
        # 額外贊助提醒
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
            <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="text-decoration:none;">
                <div style="background:var(--card-bg); border: 2px dashed #FFDD00; color:var(--text-color); padding:15px; border-radius:15px; text-align:center; font-size:0.9rem; font-weight:bold;">
                    ☕ 內容對你有幫助嗎？請作者喝杯咖啡吧！
                </div>
            </a>
        """, unsafe_allow_html=True)

# ==========================================
# 3. 其他頁面與主程式
# ==========================================

def mobile_handout_page():
    st.markdown("<h2 style='text-align:center; color: var(--text-color);'>📄 講義預覽與下載</h2>", unsafe_allow_html=True)
    with st.expander("📝 編輯講義內容 (可選)"):
        st.session_state.manual_input_content = st.text_area("講義內容", value=st.session_state.get("manual_input_content", ""), height=250, label_visibility="collapsed")
    st.markdown("<hr style='border-color: var(--border-color);'>", unsafe_allow_html=True)
    if st.button("📥 下載 A4 講義 (PDF)", type="primary"):
        log_user_intent("pdf_download_mobile")
        st.session_state.trigger_download = True
        st.rerun()
    final_html = generate_printable_html("AI 學習講義", st.session_state.get("manual_input_content", "請先從「探索知識」頁面選擇一個單字卡。"), auto_download=st.session_state.get("trigger_download", False))
    if st.session_state.get("trigger_download"): st.session_state.trigger_download = False
    st.caption("👇 PDF 預覽 (下載後為高清版本)")
    components.html(final_html, height=450, scrolling=True)

def mobile_sponsor_page():
    st.markdown("<h2 style='text-align:center; color: var(--text-color);'>💖 支持我們</h2>", unsafe_allow_html=True)
    st.markdown("""
    <div class="word-card" style="text-align:center;">
        <p style="font-size:1.1rem; line-height:1.7; color:var(--text-color);">這是一個免費工具，您的贊助將支持算力支出。</p>
        <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="text-decoration:none;"><div style="background:#00A650; color:white; padding:15px; border-radius:15px; font-weight:bold; margin: 20px 0 10px 0;">💳 綠界贊助 (ECPay)</div></a>
        <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="text-decoration:none;"><div style="background:#FFDD00; color:black; padding:15px; border-radius:15px; font-weight:bold;">☕ Buy Me a Coffee</div></a>
    </div>
    """, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Etymon Mobile", page_icon="📱", layout="centered")
    inject_dual_theme_ui()

    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索知識"

    nav_options = ["🔍 探索知識", "📄 製作講義", "💖 支持"]
    selected_nav = st.radio("導覽", options=nav_options, index=nav_options.index(st.session_state.mobile_nav), horizontal=True, label_visibility="collapsed")
    if selected_nav != st.session_state.mobile_nav:
        st.session_state.mobile_nav = selected_nav
        st.rerun()

    st.markdown("<hr style='margin: 0.5rem 0 1.5rem 0; border-color: var(--border-color);'>", unsafe_allow_html=True)

    df = load_db()
    if df.empty: return
        
    if st.session_state.mobile_nav == "🔍 探索知識": mobile_home_page(df)
    elif st
