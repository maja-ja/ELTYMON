# ==========================================
# 0. 基礎套件導入
# ==========================================
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
    """修復內容，確保 LaTeX 和 HTML 能被正確解析"""
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    # 處理雙反斜線與換行，確保 Markdown 語法正確
    return str(text).replace('\\n', '\n').replace('\n', '  \n').strip('"').strip("'")

def submit_error_report(word):
    """將錯誤單字回報至指定的 Google Sheets 工作表: feedback"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # 完整的試算表 URL
        sheet_url = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit#gid=0"
        
        # 嘗試讀取 'feedback' 工作表
        try:
            r_df = conn.read(spreadsheet=sheet_url, worksheet="feedback", ttl=0)
        except:
            # 如果 feedback 工作表不存在，則建立新的欄位架構
            r_df = pd.DataFrame(columns=['word', 'timestamp', 'status'])
        
        # 新增一筆紀錄
        new_report = pd.DataFrame([{
            'word': word, 
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'status': '待處理'
        }])
        
        updated_df = pd.concat([r_df, new_report], ignore_index=True)
        
        # 寫回 Google Sheets (這需要權限，請確認你的 Secrets 有效)
        conn.update(spreadsheet=sheet_url, worksheet="feedback", data=updated_df)
        return True
    except Exception as e:
        # 如果是權限問題或分頁不存在，會在終端機顯示錯誤，前端顯示失敗
        print(f"Update Error: {e}")
        return False

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

# ==========================================
# 2. UI 佈局優化
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
            .block-container { max-width: 480px !important; padding: 2rem 1.2rem !important; }
            .word-card {
                background: var(--card-bg); border-radius: 20px; padding: 20px;
                box-shadow: 0 10px 30px var(--shadow-color); border: 1px solid var(--border-color);
                margin-bottom: 10px;
            }
            .roots-tag {
                background: var(--accent-bg); color: var(--accent-text-color); 
                padding: 4px 10px; border-radius: 10px; font-size: 0.8rem; font-weight: bold;
            }
            .report-btn { color: #ff4b4b; font-size: 0.8rem; cursor: pointer; text-decoration: none; float: right; }
        </style>
    """, unsafe_allow_html=True)
def mobile_home_page(df):
    st.markdown("<h2 style='text-align:center;'>🔍 探索知識</h2>", unsafe_allow_html=True)
    
    # 領域選擇與搜尋 (代碼簡略，請保留原本的邏輯)
    all_cats = ["🌍 全部領域"] + sorted(df['category'].unique().tolist())
    selected_cat = st.selectbox("選擇學習領域", all_cats, label_visibility="collapsed")

    col_search, col_rand = st.columns([4, 1])
    with col_search:
        query = st.text_input("搜尋...", placeholder="例如: 熵", label_visibility="collapsed")
    with col_rand:
        if st.button("🎲"): 
            sample_pool = df if selected_cat == "🌍 全部領域" else df[df['category'] == selected_cat]
            if not sample_pool.empty:
                st.session_state.selected_word = sample_pool.sample(1).iloc[0].to_dict()
                st.rerun()

    # 單字顯示邏輯
    target_row = None
    if query:
        match = df[df['word'].str.lower() == query.strip().lower()]
        if not match.empty: target_row = match.iloc[0].to_dict()
    elif "selected_word" in st.session_state:
        target_row = st.session_state.selected_word

    if target_row:
        w = target_row['word']
        
        # 1. 頂部標籤與資訊區
        st.markdown(f"""
        <div class="word-card" style="margin-bottom:0px; padding-bottom:5px; border-bottom:none; border-radius:20px 20px 0 0;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <span class="roots-tag">🧬 {fix_content(target_row['roots'])}</span>
                <span style="font-size:0.75rem; color:var(--subtle-text-color);">{target_row['category']}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        # 2. 標題與回報按鈕區 (使用 Columns 模擬右上角按鈕)
        card_col1, card_col2 = st.columns([6, 1])
        with card_col1:
            st.markdown(f"<h1 style='margin:0 0 0 25px; color:var(--h1-color);'>{w}</h1>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0 0 0 25px; color:var(--subtle-text-color);'>/{fix_content(target_row['phonetic'])}/</p>", unsafe_allow_html=True)
        with card_col2:
            # 這是報錯按鈕
            if st.button("⚠️", key="report_btn", help="回報單字內容錯誤"):
                if submit_error_report(w):
                    st.toast(f"已回報 {w} 至 feedback 表格！", icon="✅")
                else:
                    st.error("回報失敗，請確認試算表中有 feedback 分頁與寫入權限。")

        # 3. 核心內容區 (分開使用 st.markdown 以支援 LaTeX 和 HTML)
        st.markdown('<div class="word-card" style="margin-top:-20px; border-top:none; border-radius:0 0 20px 20px; padding-top:0;">', unsafe_allow_html=True)
        
        # 定義 (支援 LaTeX)
        st.markdown(fix_content(target_row['definition']), unsafe_allow_html=True)
        
        # 實例 (支援 LaTeX)
        st.markdown(f"""
            <div style="background:var(--main-bg); padding:15px; border-radius:12px; margin-top:15px;">
                <b style="color:var(--accent-text-color);">💡 實例:</b>
        """, unsafe_allow_html=True)
        st.markdown(fix_content(target_row['example']), unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        
        # 按鈕區 (聽發音、生成講義)
        c1, c2 = st.columns(2)
        with c1: speak(w, f"m_speak_{w}")
        with c2:
            if st.button("📄 生成講義", type="primary"):
                st.session_state.manual_input_content = f"## {w}\n\n{fix_content(target_row['definition'])}\n\n### 實例\n{fix_content(target_row['example'])}"
                st.session_state.mobile_nav = "📄 製作講義"
                st.rerun()

def main():
    st.set_page_config(page_title="Etymon Mobile", page_icon="📱")
    inject_dual_theme_ui()

    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索知識"

    # 簡易導覽
    cols = st.columns(3)
    navs = ["🔍 探索知識", "📄 製作講義", "💖 支持"]
    for i, n in enumerate(navs):
        if cols[i].button(n, use_container_width=True, type="primary" if st.session_state.mobile_nav == n else "secondary"):
            st.session_state.mobile_nav = n
            st.rerun()

    df = load_db()
    if df.empty: return
        
    if st.session_state.mobile_nav == "🔍 探索知識": mobile_home_page(df)
    # 其他頁面邏輯保持類似...

if __name__ == "__main__":
    main()
