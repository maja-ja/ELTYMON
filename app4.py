import streamlit as st
import pandas as pd
import base64
import time
import re
import os
from io import BytesIO
from gtts import gTTS
import streamlit.components.v1 as components
import markdown
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心工具函式
# ==========================================

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    return str(text).replace('\\n', '\n').replace('\n', '  \n').strip('"').strip("'")

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
                .speak-btn {{ background: #F0F7FF; border: 1px solid #B3E5FC; border-radius: 12px; padding: 10px; cursor: pointer; width: 100%; font-weight: 600; color: #0277BD; }}
                @media (prefers-color-scheme: dark) {{ .speak-btn {{ background: #161B22; border-color: #30363d; color: #f0f6fc; }} }}
            </style>
            <button class="speak-btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
            <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        </body></html>""", height=50)
    except: pass

def submit_error_report(word):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_url = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit#gid=0"
        try: r_df = conn.read(spreadsheet=sheet_url, worksheet="feedback", ttl=0)
        except: r_df = pd.DataFrame(columns=['word', 'timestamp', 'status'])
        new_report = pd.DataFrame([{'word': word, 'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"), 'status': '待處理'}])
        updated_df = pd.concat([r_df, new_report], ignore_index=True)
        conn.update(spreadsheet=sheet_url, worksheet="feedback", data=updated_df)
        return True
    except: return False

@st.cache_data(ttl=3600) 
def load_db():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        df = conn.read(spreadsheet=url, ttl=0)
        return df.fillna("無")
    except: return pd.DataFrame()

def generate_printable_html(title, text_content, auto_download=False):
    html_body = markdown.markdown(text_content)
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 500); };" if auto_download else ""
    return f"""
    <html><head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>body {{ font-family: sans-serif; padding: 20px; }} #area {{ background: white; padding: 20px; }}</style>
    </head><body>
        <div id="area"><h1>{title}</h1>{html_body}</div>
        <script>function downloadPDF(){{const e=document.getElementById('area');html2pdf().from(e).save('{title}.pdf');}}{auto_js}</script>
    </body></html>"""

# ==========================================
# 2. UI 樣式
# ==========================================

def inject_ui():
    st.markdown("""
        <style>
            .block-container { max-width: 480px !important; padding: 1.5rem 1rem !important; }
            .word-card { 
                background: var(--card-bg, white); border-radius: 20px; padding: 20px;
                border: 1px solid #eee; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 15px;
            }
            .roots-tag { background: #E3F2FD; color: #1976D2; padding: 4px 10px; border-radius: 10px; font-size: 0.8rem; font-weight: bold; }
            .sponsor-banner { background: linear-gradient(90deg, #FFDD00, #FBB03B); color: black !important; padding: 12px; border-radius: 15px; text-align: center; display: block; text-decoration: none; margin-bottom: 15px; font-weight: bold; }
            @media (prefers-color-scheme: dark) {
                :root { --card-bg: #161B22; }
                .word-card { border-color: #30363d; }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 頁面邏輯
# ==========================================

def home_page(df):
    # 標題區
    st.markdown("<h2 style='text-align:center;'>🔍 探索知識</h2>", unsafe_allow_html=True)
    st.markdown("""<a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" class="sponsor-banner">💖 贊助支持開發成本</a>""", unsafe_allow_html=True)

    # 1. 調整整體下移 (透過空出的 margin)
    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

    # 2. 領域選擇
    all_cats = ["🌍 全部領域"] + sorted(df['category'].unique().tolist())
    sel_cat = st.selectbox("領域", all_cats, label_visibility="collapsed")

    # 3. 搜尋、骰子與報錯區塊 (整合在同一排)
    # 比例調整：搜尋框(5)、骰子(1.2)、報錯按鈕(2.8)
    c_search, c_rand, c_report = st.columns([5, 1.2, 2.8])
    
    with c_search:
        query = st.text_input("搜尋單字...", placeholder="例如: entropy", label_visibility="collapsed")
    
    with c_rand:
        if st.button("🎲", help="隨機單字"):
            pool = df if sel_cat == "🌍 全部領域" else df[df['category'] == sel_cat]
            if not pool.empty:
                st.session_state.selected_word = pool.sample(1).iloc[0].to_dict()
                st.rerun()
                
    with c_report:
        # 這裡放置報錯按鈕，加上注記文字
        if st.button("⚠️ 錯誤回報", key="top_report_btn"):
            # 取得當前畫面上顯示的單字
            current_w = st.session_state.get('selected_word', {}).get('word', 'Unknown')
            if submit_error_report(current_w):
                st.toast(f"已記錄 {current_w} 的內容錯誤", icon="✅")
            else:
                st.error("回報失敗，請確認網路或分頁設定")

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    # --- 單字顯示邏輯 ---
    target = None
    if query:
        match = df[df['word'].str.lower() == query.strip().lower()]
        if not match.empty: 
            target = match.iloc[0].to_dict()
            st.session_state.selected_word = target # 搜尋時也同步更新選取狀態
    elif "selected_word" in st.session_state: 
        target = st.session_state.selected_word
    elif not df.empty: 
        target = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target

    # --- 渲染卡片 ---
    if target:
        w = target['word']
        
        # 卡片頂部標籤
        st.markdown(f"""
        <div class="word-card" style="margin-bottom:-1px; border-bottom:none; border-radius:20px 20px 0 0;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="roots-tag">🧬 {target['roots']}</span>
                <span style="font-size:0.75rem; color:gray;">{target['category']}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        # 單字標題區 (移除原本卡片內的 ⚠️ 按鈕，避免重複)
        st.markdown(f"""
        <div class="word-card" style="margin-top:-1px; border-top:none; border-bottom:none; border-radius:0; padding-top:0; padding-bottom:5px;">
            <h1 style="margin:0; font-size:2.2rem; color:var(--h1-color);">{w}</h1>
            <p style="color:gray; margin-top:5px;">/{target['phonetic']}/</p>
        </div>""", unsafe_allow_html=True)

        # 核心內容區 (LaTeX 渲染)
        st.markdown('<div class="word-card" style="margin-top:-1px; border-top:none; border-radius:0 0 20px 20px; padding-top:0;">', unsafe_allow_html=True)
        st.markdown(fix_content(target['definition']), unsafe_allow_html=True)
        
        # 實例區塊
        st.markdown(f"""
            <div style="background:rgba(0,0,0,0.03); padding:15px; border-radius:12px; margin-top:20px;">
                <b style="color:#1976D2;">💡 實例:</b><br>
        """, unsafe_allow_html=True)
        st.markdown(fix_content(target['example']), unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)

        # 底部功能按鈕
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: speak(w, f"m_speak_{w}")
        with c2:
            if st.button("📄 生成講義", type="primary", use_container_width=True):
                st.session_state.manual_input_content = f"## {w}\n\n{target['definition']}\n\n### 實例\n{target['example']}"
                st.session_state.mobile_nav = "📄 製作講義"
                st.rerun()

        # 咖啡贊助按鈕
        st.markdown(f"""<a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="text-decoration:none;">
            <div style="border: 2px dashed #FFDD00; padding:15px; border-radius:15px; text-align:center; margin-top:20px; color:inherit; font-weight:bold;">☕ 內容有幫助嗎？請作者喝杯咖啡吧！</div>
        </a>""", unsafe_allow_html=True)
def handout_page():
    st.markdown("<h2 style='text-align:center;'>📄 製作講義</h2>", unsafe_allow_html=True)
    content = st.text_area("編輯內容", value=st.session_state.get("manual_input_content", ""), height=300)
    st.session_state.manual_input_content = content
    
    if st.button("📥 下載 PDF 講義", type="primary", use_container_width=True):
        st.session_state.trigger_pdf = True

    final_html = generate_printable_html("學習講義", content, st.session_state.get("trigger_pdf", False))
    st.session_state.trigger_pdf = False
    components.html(final_html, height=400, scrolling=True)

def main():
    st.set_page_config(page_title="Etymon", page_icon="📱")
    inject_ui()
    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索知識"
    
    # 導覽列
    nav = st.radio("導覽", ["🔍 探索知識", "📄 製作講義", "💖 支持"], horizontal=True, label_visibility="collapsed")
    st.session_state.mobile_nav = nav
    
    df = load_db()
    if df.empty: return

    if nav == "🔍 探索知識": home_page(df)
    elif nav == "📄 製作講義": handout_page()
    elif nav == "💖 支持": st.markdown("<h2 style='text-align:center;'>💖 感謝支持</h2><p>這裡是贊助頁面...</p>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
