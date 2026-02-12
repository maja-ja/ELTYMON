import streamlit as st
import pandas as pd
import base64
import time
import re
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
                .speak-btn {{ background: #eef7ff; border: 1px solid #d0e8ff; border-radius: 12px; padding: 10px; cursor: pointer; width: 100%; font-weight: 600; color: #1c6aae; }}
                @media (prefers-color-scheme: dark) {{ .speak-btn {{ background: #161B22; border-color: #30363d; color: #f0f6fc; }} }}
            </style>
            <button class="speak-btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
            <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        </body></html>""", height=50)
    except: pass

def submit_error_report(data_row):
    """根據使用者提供的完整欄位結構回報錯誤"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_url = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit#gid=0"
        
        # 定義欄位清單 (與您提供的一致)
        columns = [
            'category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 
            'example', 'translation', 'native_vibe', 'synonym_nuance', 'visual_prompt', 
            'social_status', 'emotional_tone', 'street_usage', 'collocation', 'etymon_story', 
            'usage_warning', 'memory_hook', 'audio_tag', 'term'
        ]
        
        # 讀取現有資料
        try: r_df = conn.read(spreadsheet=sheet_url, worksheet="feedback", ttl=0)
        except: r_df = pd.DataFrame(columns=columns + ['report_time', 'report_status'])
        
        # 準備新資料列
        new_row = {col: data_row.get(col, "無") for col in columns}
        new_row['report_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
        new_row['report_status'] = '待處理'
        
        updated_df = pd.concat([r_df, pd.DataFrame([new_row])], ignore_index=True)
        conn.update(spreadsheet=sheet_url, worksheet="feedback", data=updated_df)
        return True
    except Exception as e:
        print(f"Report Error: {e}")
        return False

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
        <meta charset="UTF-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            body {{ background-color: #525659; display: flex; justify-content: center; padding: 20px; margin: 0; }}
            #area {{ background-color: white !important; color: black !important; width: 210mm; min-height: 297mm; padding: 20mm; box-shadow: 0 0 10px rgba(0,0,0,0.5); font-family: sans-serif; line-height: 1.6; }}
            h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; color: black; }}
        </style>
    </head><body>
        <div id="area"><h1>{title}</h1>{html_body}</div>
        <script>function downloadPDF(){{const e=document.getElementById('area');html2pdf().from(e).save('{title}.pdf');}}{auto_js}</script>
    </body></html>"""

# ==========================================
# 2. UI 樣式 (解決卡住問題)
# ==========================================

def inject_ui():
    st.markdown("""
        <style>
            /* 隱藏頂部所有 Streamlit 標籤與按鈕 */
            header, footer, .stAppDeployButton, #MainMenu { visibility: hidden !important; height: 0 !important; display: none !important; }
            
            /* 調整容器以防被頂部卡住 */
            .block-container { 
                max-width: 480px !important; 
                padding: 2.5rem 1rem 5rem 1rem !important; 
            }

            :root {
                --main-bg: #f8f9fa; --card-bg: white; --text-color: #212529;
                --subtle-text: #6c757d; --border-color: #dee2e6;
                --h1-color: #343a40; --accent-color: #e6f0ff; --accent-text: #0059b3;
            }
            @media (prefers-color-scheme: dark) {
                :root {
                    --main-bg: #0E1117; --card-bg: #161B22; --text-color: #e3e3e3;
                    --subtle-text: #a0a0a0; --border-color: #30363d;
                    --h1-color: #f0f6fc; --accent-color: #1c2a3a; --accent-text: #79c0ff;
                }
            }
            html, body, .main { background-color: var(--main-bg) !important; }

            .word-card { 
                background: var(--card-bg); border-radius: 16px; padding: 20px;
                border: 1px solid var(--border-color); margin-bottom: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }
            .roots-tag { background: var(--accent-color); color: var(--accent-text); padding: 5px 12px; border-radius: 10px; font-size: 0.85rem; font-weight: 500; }
            .sponsor-banner { 
                background: linear-gradient(90deg, #ffc107, #ff9800); color: #212529 !important; 
                padding: 12px; border-radius: 12px; text-align: center; display: block; 
                text-decoration: none; margin-bottom: 20px; font-weight: bold;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 頁面邏輯
# ==========================================

def home_page(df):
    st.markdown("<h2 style='text-align:center;'>🔍 探索知識</h2>", unsafe_allow_html=True)
    st.markdown("""<a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" class="sponsor-banner">💖 贊助支持開發成本</a>""", unsafe_allow_html=True)
    
    sel_cat = st.selectbox("領域", ["🌍 全部領域"] + sorted(df['category'].unique().tolist()), label_visibility="collapsed")
    
    c_s, c_r, c_report = st.columns([4, 1, 2])
    with c_s:
        query = st.text_input("搜尋...", placeholder="例如: genocide", label_visibility="collapsed")
    with c_r:
        if st.button("🎲"):
            pool = df if sel_cat == "🌍 全部領域" else df[df['category'] == sel_cat]
            if not pool.empty:
                st.session_state.selected_word = pool.sample(1).iloc[0].to_dict()
                st.rerun()
    with c_report:
        if st.button("⚠️ 報錯"):
            current_data = st.session_state.get('selected_word', {})
            if submit_error_report(current_data): st.toast(f"已回報 {current_data.get('word')}！")

    # 單字顯示邏輯
    target = None
    if query:
        match = df[df['word'].str.lower() == query.strip().lower()]
        if not match.empty: 
            target = match.iloc[0].to_dict()
            st.session_state.selected_word = target
    elif "selected_word" in st.session_state: target = st.session_state.selected_word
    elif not df.empty: target = df.sample(1).iloc[0].to_dict()
    
    if target:
        w = target['word']
        st.session_state.selected_word = target
        st.markdown(f"""
        <div class="word-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <span class="roots-tag">🧬 {target['roots']}</span>
                <span style="font-size:0.75rem; color:var(--subtle-text);">{target['category']}</span>
            </div>
            <h1 style="font-size:2.5rem; margin-top:10px;">{w}</h1>
            <p style="color:var(--subtle-text); margin-top:-15px;">/{target['phonetic']}/</p>
            <div style="font-size:1.1rem; line-height:1.7;">{fix_content(target['definition'])}</div>
            <div style="background:var(--main-bg); padding:15px; border-radius:12px; margin-top:15px;">
                <b style="color:var(--accent-text);">💡 實例:</b><br>
                <div style="margin-top:5px;">{fix_content(target['example'])}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1: speak(w, f"spk_{w}")
        with b2:
            if st.button("📄 生成講義", type="primary"):
                st.session_state.manual_input_content = f"## {w}\n\n{target['definition']}\n\n### 實例\n{target['example']}"
                st.session_state.mobile_nav = "📄 製作講義"
                st.rerun()

def handout_page():
    st.markdown("<h2 style='text-align:center;'>📄 製作講義</h2>", unsafe_allow_html=True)
    content = st.text_area("編輯內容", value=st.session_state.get("manual_input_content", ""), height=300)
    st.session_state.manual_input_content = content
    if st.button("📥 下載 PDF", type="primary", use_container_width=True):
        st.session_state.trigger_pdf = True
    
    final_html = generate_printable_html("學習講義", content, st.session_state.get("trigger_pdf", False))
    st.session_state.trigger_pdf = False
    components.html(final_html, height=450, scrolling=True)
def sponsor_page():
    st.markdown("<h2 style='text-align:center;'>💖 支持我們</h2>", unsafe_allow_html=True)
    st.markdown("""
    <div class="word-card" style="text-align:center;">
        <p style="font-size:1.1rem; line-height:1.7;">如果您覺得這個工具有幫助，您的任何支持都將是我們持續開發與維護的最大動力！</p>
        <p style="color:var(--subtle-text); font-size:0.9rem;">您的贊助將用於支付伺服器與 API 的費用。</p>
        <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="text-decoration:none;">
            <div style="background:#00A650; color:white; padding:15px; border-radius:12px; font-weight:bold; margin: 20px 0 10px 0;">💳 綠界 ECPay (推薦)</div>
        </a>
        <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="text-decoration:none;">
            <div style="background:#FFDD00; color:black; padding:15px; border-radius:12px; font-weight:bold;">☕ Buy Me a Coffee</div>
        </a>
    </div>
    """, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Etymon", page_icon="💡")
    inject_ui()
    
    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索知識"

    nav_options = ["🔍 探索知識", "📄 製作講義", "💖 支持"]
    current_index = nav_options.index(st.session_state.mobile_nav) if st.session_state.mobile_nav in nav_options else 0

    st.write("") # Spacer
    selected_nav = st.radio("導覽", options=nav_options, index=current_index, horizontal=True, label_visibility="collapsed")

    if selected_nav != st.session_state.mobile_nav:
        st.session_state.mobile_nav = selected_nav
        st.rerun()

    df = load_db()
    if df.empty: return

    if st.session_state.mobile_nav == "🔍 探索知識":
        home_page(df)
    elif st.session_state.mobile_nav == "📄 製作講義":
        handout_page()
    elif st.session_state.mobile_nav == "💖 支持":
        sponsor_page()

if __name__ == "__main__":
    main()
