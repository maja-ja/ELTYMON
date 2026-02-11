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
# 1. 核心工具函式 (後端邏輯)
# ==========================================

def fix_content(text):
    """全域字串清洗"""
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    text = str(text)
    text = text.replace('\\n', '  \n').replace('\n', '  \n')
    if '\\\\' in text: text = text.replace('\\\\', '\\')
    text = text.strip('"').strip("'")
    return text

def speak(text, key_suffix=""):
    """TTS 發音生成 (HTML 按鈕版)"""
    if not text: return
    # 清理字串，只保留英文以利發音
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    english_only = " ".join(english_only.split()).strip()
    if not english_only: return

    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        
        # 使用更現代、簡潔的按鈕樣式
        html_code = f"""
        <html><body>
            <style>
                .speak-btn {{ 
                    background: #F0F7FF; border: 1px solid #B3E5FC; border-radius: 12px; 
                    padding: 10px; cursor: pointer; display: flex; align-items: center; 
                    justify-content: center; width: 100%; font-family: sans-serif; 
                    font-size: 14px; color: #0277BD; transition: 0.2s;
                }}
                .speak-btn:hover {{ background: #E1F5FE; }}
                .speak-btn:active {{ transform: scale(0.96); }}
            </style>
            <button class="speak-btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
            <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        </body></html>
        """
        components.html(html_code, height=50)
    except Exception:
        pass # 發生錯誤時靜默處理

def get_spreadsheet_url():
    """從 Streamlit Secrets 獲取 Google Sheet URL"""
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet")

def log_user_intent(label):
    """靜默紀錄用戶行為到 Google Sheet 的 'metrics' 分頁"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        try: 
            m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
            # 確保 count 欄位是數字
            m_df['count'] = pd.to_numeric(m_df['count'], errors='coerce').fillna(0).astype(int)
        except: 
            m_df = pd.DataFrame(columns=['label', 'count'])
        
        if label in m_df['label'].values:
            m_df.loc[m_df['label'] == label, 'count'] += 1
        else:
            new_record = pd.DataFrame([{'label': label, 'count': 1}])
            m_df = pd.concat([m_df, new_record], ignore_index=True)
            
        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)
    except:
        pass # 發生錯誤也不要打擾用戶

@st.cache_data(ttl=3600) 
def load_db():
    """從 Google Sheets 載入單字資料庫，並快取 1 小時"""
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe']
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        df = conn.read(spreadsheet=url, ttl=0) # 讀取時不快取，讓 cache_data 控制
        # 確保所有必要欄位都存在
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無")[COL_NAMES].reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

def generate_printable_html(title, text_content, img_b64, img_width_percent, auto_download=False):
    """生成用於講義預覽和下載的 HTML"""
    text_content = text_content.strip()
    # 將 Markdown 轉為 HTML
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    
    # 若 auto_download 為 True，則在頁面載入後自動觸發下載
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 500); };" if auto_download else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.8; background: #eee; display: flex; justify-content: center; }}
            #printable-area {{ 
                background: white; width: 210mm; min-height: 297mm; margin: 20px 0; 
                padding: 20mm 25mm; box-sizing: border-box; 
            }}
            .content {{ font-size: 16px; text-align: justify; }}
            h1, h2, h3 {{ color: #1a237e; }}
        </style>
    </head>
    <body>
        <div id="printable-area">
            <h1>{title}</h1><div style="text-align:right; font-size:12px; color:#666;">日期：{date_str}</div>
            <div class="content">{html_body}</div>
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{
                    margin: 0, filename: '{title}.pdf', image: {{ type: 'jpeg', quality: 1.0 }},
                    html2canvas: {{ scale: 3, useCORS: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                html2pdf().set(opt).from(element).save();
            }}
            {auto_js}
        </script>
    </body>
    </html>
    """

# ==========================================
# 2. 手機版 UI 介面與組件
# ==========================================

def inject_mobile_ui():
    """注入手機版專用的 CSS 樣式"""
    st.markdown("""
        <style>
            /* 強制手機版面與背景 */
            .main { background-color: #F8F9FA; }
            .block-container { max-width: 480px !important; padding: 1rem 1.2rem 5rem 1.2rem !important; }
            
            /* 隱藏桌面版元素 */
            [data-testid="stSidebar"] { display: none; }
            header { visibility: hidden; }
            
            /* 卡片設計 */
            .word-card {
                background: white; border-radius: 20px; padding: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.07); margin-bottom: 20px;
                border: 1px solid #f0f0f0;
            }
            .roots-tag {
                background: #E3F2FD; color: #1976D2; padding: 6px 14px;
                border-radius: 12px; font-size: 0.9rem; font-weight: bold;
                display: inline-block;
            }
            
            /* 按鈕與輸入框優化 */
            .stButton > button {
                border-radius: 15px !important; height: 55px !important;
                width: 100%; font-weight: 700 !important; font-size: 1rem !important;
                transition: transform 0.2s ease;
            }
            .stButton > button:active { transform: scale(0.95); }
            .stTextInput > div > div > input {
                border-radius: 15px !important; height: 55px !important;
                padding: 10px 15px !important;
            }
        </style>
    """, unsafe_allow_html=True)

def mobile_home_page(df):
    """手機版首頁：整合搜尋與隨機探索"""
    st.markdown("<h2 style='text-align:center;'>🔍 探索知識</h2>", unsafe_allow_html=True)
    
    col_search, col_rand = st.columns([4, 1])
    with col_search:
        query = st.text_input("搜尋單字或含意...", placeholder="例如: 熵", label_visibility="collapsed")
    with col_rand:
        if st.button("🎲", help="隨機抽一張卡片"): 
            st.session_state.selected_word = df.sample(1).iloc[0].to_dict()
            st.rerun()

    target_row = None
    if query:
        mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
        res = df[mask]
        if not res.empty:
            target_row = res.iloc[0].to_dict()
        else:
            st.info("找不到相關內容，試試其他關鍵字？")
    elif "selected_word" in st.session_state:
        target_row = st.session_state.selected_word
    elif not df.empty:
        target_row = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target_row

    if target_row:
        w = target_row['word']
        st.markdown(f"""
        <div class="word-card">
            <h1 style="margin-top:0; margin-bottom:5px; color:#1A237E;">{w}</h1>
            <p style="color:#666; margin-bottom:20px; font-size:0.9rem;">/{fix_content(target_row['phonetic'])}/</p>
            <span class="roots-tag">🧬 {fix_content(target_row['roots'])}</span>
            <p style="margin-top:20px; font-size:1.1rem; line-height:1.7;">{fix_content(target_row['definition'])}</p>
            <div style="background:#F5F5F5; padding:15px; border-radius:12px; font-size:0.95rem; color:#444; margin-top:15px;">
                💡 <b>應用:</b> {fix_content(target_row['example'])}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            speak(w, f"m_speak_{w}")
        with c2:
            if st.button("📄 生成講義", type="primary"):
                log_user_intent(f"jump_{w}")
                st.session_state.manual_input_content = (
                    f"## 專題講義：{w}\n\n"
                    f"### 🧬 核心邏輯\n{fix_content(target_row['breakdown'])}\n\n"
                    f"### 🎯 核心定義\n{fix_content(target_row['definition'])}\n\n"
                    f"### 💡 應用實例\n{fix_content(target_row['example'])}"
                )
                st.session_state.mobile_nav = "📄 製作講義"
                st.rerun()

def mobile_handout_page():
    """手機版講義製作與預覽頁面"""
    st.markdown("<h2 style='text-align:center;'>📄 講義預覽與下載</h2>", unsafe_allow_html=True)
    
    with st.expander("📝 編輯講義內容 (可選)"):
        content = st.text_area("講義內容", value=st.session_state.get("manual_input_content", ""), height=250, label_visibility="collapsed")
        st.session_state.manual_input_content = content
    
    st.markdown("---")
    if st.button("📥 下載 A4 講義 (PDF)", type="primary"):
        log_user_intent("pdf_download_mobile")
        st.session_state.trigger_download = True
        st.rerun()
    
    final_html = generate_printable_html(
        title="AI 學習講義", 
        text_content=st.session_state.get("manual_input_content", "請先從「探索知識」頁面選擇一個單字卡。"), 
        img_b64="", 
        img_width_percent=80,
        auto_download=st.session_state.get("trigger_download", False)
    )
    if st.session_state.get("trigger_download"):
        st.session_state.trigger_download = False
        
    st.caption("👇 PDF 預覽 (下載後為高清版本)")
    components.html(final_html, height=450, scrolling=True)

def mobile_sponsor_page():
    """手機版贊助頁面"""
    st.markdown("<h2 style='text-align:center;'>💖 支持我們</h2>", unsafe_allow_html=True)
    st.markdown("""
    <div class="word-card" style="text-align:center;">
        <p style="font-size:1.1rem; line-height:1.7;">如果這個免費工具對你有幫助，<br>歡迎贊助支持伺服器與開發成本！</p>
        <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="text-decoration:none;">
            <div style="background:#00A650; color:white; padding:15px; border-radius:15px; font-weight:bold; margin: 20px 0 10px 0;">💳 綠界贊助 (ECPay)</div>
        </a>
        <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="text-decoration:none;">
            <div style="background:#FFDD00; color:black; padding:15px; border-radius:15px; font-weight:bold;">☕ Buy Me a Coffee</div>
        </a>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 主程式入口 (Main App)
# ==========================================
def main():
    st.set_page_config(page_title="Etymon Mobile", page_icon="📱", layout="centered")
    inject_mobile_ui()

    if 'mobile_nav' not in st.session_state:
        st.session_state.mobile_nav = "🔍 探索知識"

    # 使用 st.radio 模擬底部導航列，更符合手機操作習慣
    nav_options = ["🔍 探索知識", "📄 製作講義", "💖 支持"]
    selected_nav = st.radio(
        "主選單", 
        options=nav_options, 
        index=nav_options.index(st.session_state.mobile_nav),
        horizontal=True, 
        label_visibility="collapsed"
    )
    if selected_nav != st.session_state.mobile_nav:
        st.session_state.mobile_nav = selected_nav
        st.rerun()

    st.markdown("<hr style='margin: 0.5rem 0 1.5rem 0; border-color: #eee;'>", unsafe_allow_html=True)

    # 頁面路由
    df = load_db()
    if df.empty:
        st.warning("資料庫連接中或目前無資料...")
        return
        
    if st.session_state.mobile_nav == "🔍 探索知識":
        mobile_home_page(df)
    elif st.session_state.mobile_nav == "📄 製作講義":
        mobile_handout_page()
    elif st.session_state.mobile_nav == "💖 支持":
        mobile_sponsor_page()

if __name__ == "__main__":
    main()
