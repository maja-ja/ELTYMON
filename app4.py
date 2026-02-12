import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
from io import BytesIO
from gtts import gTTS
import streamlit.components.v1 as components
import markdown
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 0. 核心配置與 CSS (手機版優化)
# ==========================================
st.set_page_config(page_title="Etymon Mobile", page_icon="📱", layout="centered")

def inject_mobile_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=Inter:wght@400;800&display=swap');
            
            :root {
                --main-bg: #121212; 
                --card-bg: #1E1E1E; 
                --text-color: #E0E0E0; 
                --subtle-text: #A0A0A0;
                --accent-color: #64B5F6;
                --accent-light: rgba(33, 150, 243, 0.15);
                --shadow: 0 8px 30px rgba(0,0,0,0.5);
                --radius-lg: 20px;
                --radius-md: 12px;
            }

            /* 強制覆蓋 Streamlit 預設樣式 */
            .stApp { background-color: var(--main-bg); }
            .block-container { max-width: 500px !important; padding: 1rem 1rem 6rem 1rem !important; }
            [data-testid="stSidebar"], header { display: none; } 

            /* 卡片樣式 */
            .word-card {
                background-color: var(--card-bg);
                border-radius: var(--radius-lg);
                padding: 24px;
                box-shadow: var(--shadow);
                border: 1px solid #333;
                margin-bottom: 20px;
                color: var(--text-color);
            }

            .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
            .word-title { 
                font-family: 'Inter', sans-serif; 
                font-size: 2.2rem; 
                font-weight: 800; 
                color: #FFFFFF; 
                margin: 0; 
                line-height: 1.1; 
                letter-spacing: -0.5px;
            }
            .phonetic { font-family: monospace; font-size: 0.95rem; color: var(--subtle-text); margin-top: 5px; }
            
            .badge {
                display: inline-block; padding: 4px 12px; border-radius: 20px;
                font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px;
            }
            .badge-cat { background: #0D47A1; color: #BBDEFB; }
            .badge-root { background: #37474F; color: #FFD54F; margin-right: 8px; }

            /* 內容區塊 */
            .section-label { 
                font-size: 0.8rem; font-weight: 700; color: var(--subtle-text); 
                text-transform: uppercase; margin-top: 20px; margin-bottom: 8px;
            }
            .content-text { font-size: 1.05rem; line-height: 1.6; color: #EEEEEE; }
            
            .vibe-box {
                background: var(--accent-light);
                border-left: 3px solid var(--accent-color);
                padding: 15px;
                border-radius: 8px;
                margin-top: 20px;
                font-size: 0.95rem;
                color: #E3F2FD;
            }

            /* 按鈕優化 */
            .stButton > button {
                border-radius: 12px !important;
                height: 50px !important;
                font-weight: 600 !important;
                border: none !important;
                transition: transform 0.1s !important;
            }
            .stButton > button:active { transform: scale(0.96); }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 後端邏輯工具
# ==========================================

def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet")

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    # 這裡將換行符號轉為 HTML 的 <br> 確保排版正確
    text = str(text).replace('\\n', '<br>').replace('\n', '<br>')
    return text.strip('"').strip("'")

@st.cache_data(ttl=600)
def load_db():
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe']
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=get_spreadsheet_url(), ttl=0)
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無").reset_index(drop=True)
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

def submit_report(row_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
        report_row = row_data.copy()
        report_row['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        report_row['type'] = 'mobile_feedback'
        try: existing = conn.read(spreadsheet=url, ttl=0)
        except: existing = pd.DataFrame()
        updated = pd.concat([existing, pd.DataFrame([report_row])], ignore_index=True)
        conn.update(spreadsheet=url, data=updated)
        st.toast(f"✅ 已回報問題，感謝！", icon="🙏")
    except Exception as e:
        st.toast(f"❌ 回報失敗: {e}")

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
            <audio id="{unique_id}" autoplay src="data:audio/mp3;base64,{audio_base64}"></audio>
        """, height=0, width=0)
    except: pass

def generate_printable_html(title, text_content, auto_download=False):
    # 將 <br> 轉回 \n 以便 Markdown 解析，或者直接保留 HTML
    text_content = text_content.replace('<br>', '\n')
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 1000); };" if auto_download else ""
    return f"""
    <html><head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            body {{ font-family: 'Noto Sans TC', sans-serif; background: #525659; margin: 0; padding: 20px; display: flex; justify-content: center; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; padding: 20mm; box-shadow: 0 0 10px rgba(0,0,0,0.5); }}
            h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            p, li {{ line-height: 1.8; color: #333; }}
        </style>
    </head><body>
        <div id="printable-area">
            <h1>{title}</h1>
            {html_body}
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                html2pdf().set({{ margin: 0, filename: '{title}.pdf', image: {{ type: 'jpeg', quality: 0.98 }}, html2canvas: {{ scale: 2 }}, jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }} }}).from(element).save();
            }}
            {auto_js}
        </script>
    </body></html>
    """

# ==========================================
# 2. 介面頁面組件 (修復重點)
# ==========================================

def render_word_card(row):
    """
    【修復說明】：
    HTML 字串內的每一行都必須「靠左對齊」，不能有縮排。
    縮排在 Markdown 中會被解釋為「程式碼區塊」，導致顯示出 HTML 原始碼。
    """
    w = row['word']
    phonetic = fix_content(row['phonetic'])
    roots = fix_content(row['roots'])
    definition = fix_content(row['definition'])
    breakdown = fix_content(row['breakdown'])
    vibe = fix_content(row['native_vibe'])
    
    # 這裡的 HTML 字串全部靠左，解決顯示原始碼的問題
    html_content = f"""
<div class="word-card">
    <div class="card-header">
        <div>
            <h1 class="word-title">{w}</h1>
            <div class="phonetic">/{phonetic}/</div>
        </div>
        <span class="badge badge-cat">{row['category']}</span>
    </div>
    
    <div style="margin-bottom: 20px;">
        <span class="badge badge-root">🧬 字根: {roots}</span>
    </div>
    
    <div class="content-text">
        <b>💡 定義：</b>{definition}
    </div>

    <div class="vibe-box">
        <div style="font-weight:bold; margin-bottom:8px; opacity:0.8;">🌊 專家視角</div>
        {vibe if vibe != "無" else "暫無專家補充"}
    </div>
    
    <div class="section-label">邏輯拆解</div>
    <div class="content-text" style="font-family: monospace; color: #64B5F6;">
        {breakdown}
    </div>
</div>
"""
    st.markdown(html_content, unsafe_allow_html=True)

    # 按鈕區
    c1, c2, c3 = st.columns([1, 1, 2], gap="small")
    
    with c1:
        if st.button("🔊 發音", key=f"btn_speak_{w}", use_container_width=True):
            speak(w, f"m_{w}")
            
    with c2:
        if st.button("🚩 回報", key=f"btn_rep_{w}", use_container_width=True):
            submit_report(row.to_dict())

    with c3:
        if st.button("📄 轉講義", type="primary", key=f"btn_jump_{w}", use_container_width=True):
            draft = (
                f"# 📖 {w}\n\n"
                f"### 🧬 核心邏輯\n{breakdown.replace('<br>', '  \n')}\n\n"
                f"### 🎯 核心定義\n{definition.replace('<br>', '  \n')}\n\n"
                f"### 💡 核心原理\n{roots}\n\n"
                f"**專家心法**：\n> {vibe}\n\n"
            )
            st.session_state.manual_input_content = draft
            st.session_state.mobile_nav = "📄 講義預覽"
            st.rerun()

def page_explore(df):
    st.markdown("### 🔍 探索知識")
    
    col_cat, col_rand = st.columns([2, 1])
    with col_cat:
        cats = ["全部領域"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("分類", cats, label_visibility="collapsed")
    with col_rand:
        if st.button("🎲 抽卡", type="primary", use_container_width=True):
            pool = df if sel_cat == "全部領域" else df[df['category'] == sel_cat]
            if not pool.empty:
                st.session_state.selected_word = pool.sample(1).iloc[0].to_dict()
            st.rerun()

    search_q = st.text_input("搜尋單字...", placeholder="輸入單字 (例如: entropy)")

    target_row = None
    if search_q:
        mask = df['word'].str.lower() == search_q.strip().lower()
        if mask.any(): target_row = df[mask].iloc[0].to_dict()
        else:
            fuzzy = df[df['word'].str.contains(search_q, case=False)]
            if not fuzzy.empty: target_row = fuzzy.iloc[0].to_dict()
            else: st.warning("找不到該單字")
    elif "selected_word" in st.session_state:
        target_row = st.session_state.selected_word
    elif not df.empty:
        target_row = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target_row

    if target_row:
        render_word_card(target_row)

def page_handout():
    st.markdown("### 📄 講義排版")
    content = st.text_area(
        "編輯內容", 
        value=st.session_state.get("manual_input_content", "請先選擇單字..."), 
        height=300
    )
    st.session_state.manual_input_content = content
    
    title = "AI 講義"
    if content:
        for line in content.split('\n'):
            if "# " in line:
                title = line.replace('#', '').strip()
                break

    if st.button("📥 下載 PDF", type="primary", use_container_width=True):
        st.session_state.trigger_download = True
        st.rerun()
    
    st.caption("👇 A4 預覽")
    html = generate_printable_html(
        title=title,
        text_content=content,
        auto_download=st.session_state.get("trigger_download", False)
    )
    if st.session_state.get("trigger_download"): 
        st.session_state.trigger_download = False
    components.html(html, height=450, scrolling=True)

def page_sponsor():
    st.markdown("### 💖 支持開發")
    st.markdown("""
        <div class="word-card" style="text-align:center;">
            <div style="font-size: 3rem;">🎁</div>
            <p style="color:#E0E0E0; margin: 15px 0;">
                這是一個免費的教育工具。<br>歡迎贊助支持伺服器與 AI 算力成本！
            </p>
            <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="
                display:block; background:#00A650; color:white; padding:12px; 
                border-radius:12px; text-decoration:none; font-weight:bold; margin-bottom:10px;">
                💳 綠界贊助 (ECPay)
            </a>
            <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="
                display:block; background:#FFDD00; color:black; padding:12px; 
                border-radius:12px; text-decoration:none; font-weight:bold;">
                ☕ Buy Me a Coffee
            </a>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 主程式入口
# ==========================================
def main():
    inject_mobile_css()
    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索"
    
    df = load_db()

    # 底部導航
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 探索", use_container_width=True): st.session_state.mobile_nav = "🔍 探索"; st.rerun()
    with col2:
        if st.button("📄 講義", use_container_width=True): st.session_state.mobile_nav = "📄 講義預覽"; st.rerun()
    with col3:
        if st.button("💖 支持", use_container_width=True): st.session_state.mobile_nav = "💖 支持"; st.rerun()

    st.markdown("---")

    if st.session_state.mobile_nav == "🔍 探索":
        page_explore(df)
    elif st.session_state.mobile_nav == "📄 講義預覽":
        page_handout()
    elif st.session_state.mobile_nav == "💖 支持":
        page_sponsor()

if __name__ == "__main__":
    main()
