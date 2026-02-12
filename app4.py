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
# 0. 核心配置與 CSS
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
                --shadow: 0 8px 30px rgba(0,0,0,0.5);
                --radius-lg: 20px;
            }

            .stApp { background-color: var(--main-bg); }
            .block-container { max-width: 500px !important; padding: 1rem 1rem 6rem 1rem !important; }
            [data-testid="stSidebar"], header { display: none; } 

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
            .word-title { font-family: 'Inter', sans-serif; font-size: 2.2rem; font-weight: 800; color: #FFFFFF; margin: 0; line-height: 1.1; }
            .phonetic { font-family: monospace; font-size: 0.95rem; color: var(--subtle-text); margin-top: 5px; }
            
            .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
            .badge-cat { background: #0D47A1; color: #BBDEFB; }
            .badge-root { background: #37474F; color: #FFD54F; margin-right: 8px; }

            .section-label { font-size: 0.8rem; font-weight: 700; color: var(--subtle-text); text-transform: uppercase; margin-top: 20px; margin-bottom: 8px; }
            .content-text { font-size: 1.05rem; line-height: 1.6; color: #EEEEEE; }
            
            .vibe-box {
                background: rgba(33, 150, 243, 0.15);
                border-left: 3px solid var(--accent-color);
                padding: 15px; border-radius: 8px; margin-top: 20px; font-size: 0.95rem;
            }

            .stButton > button { border-radius: 12px !important; height: 50px !important; font-weight: 600 !important; border: none !important; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 功能工具
# ==========================================

def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet")

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    return str(text).replace('\\n', '<br>').replace('\n', '<br>').strip('"').strip("'")

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
    """修正：傳入的是 dict，不再 call to_dict()"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
        
        # 直接使用傳入的 dict 資料
        report_row = dict(row_data) 
        report_row['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try: existing = conn.read(spreadsheet=url, ttl=0)
        except: existing = pd.DataFrame()
        
        updated = pd.concat([existing, pd.DataFrame([report_row])], ignore_index=True)
        conn.update(spreadsheet=url, data=updated)
        st.toast(f"✅ 已回報問題！", icon="🙏")
    except Exception as e:
        st.error(f"回報失敗: {e}")

def speak_v2(text):
    """修正：發音邏輯優化"""
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        
        # 建立一個會自動播放的 HTML 元件
        audio_html = f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            </audio>
        """
        components.html(audio_html, height=0, width=0)
    except Exception as e:
        st.error(f"音訊生成失敗: {e}")

# ==========================================
# 2. 介面組件
# ==========================================

def render_word_card(row):
    """ row 現在預期就是一個字典 (dict) """
    w = row['word']
    phonetic = fix_content(row['phonetic'])
    roots = fix_content(row['roots'])
    definition = fix_content(row['definition'])
    breakdown = fix_content(row['breakdown'])
    vibe = fix_content(row['native_vibe'])
    
    # HTML 卡片 (靠左對齊防縮排錯誤)
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
    <div class="content-text"><b>💡 定義：</b>{definition}</div>
    <div class="vibe-box">
        <div style="font-weight:bold; margin-bottom:8px; opacity:0.8;">🌊 專家視角</div>
        {vibe if vibe != "無" else "暫無專家補充"}
    </div>
    <div class="section-label">邏輯拆解</div>
    <div class="content-text" style="font-family: monospace; color: #64B5F6;">{breakdown}</div>
</div>
"""
    st.markdown(html_content, unsafe_allow_html=True)

    # 功能列
    c1, c2, c3 = st.columns([1, 1, 2])
    
    with c1:
        if st.button("🔊 發音", key=f"v_{w}", use_container_width=True):
            speak_v2(w) # 觸發發音
            
    with c2:
        # 重要修正：不再呼叫 row.to_dict()，因為 row 已經是字典
        if st.button("🚩 回報", key=f"r_{w}", use_container_width=True):
            submit_report(row)

    with c3:
        if st.button("📄 轉講義", type="primary", key=f"j_{w}", use_container_width=True):
            draft = f"# 📖 {w}\n\n### 🧬 核心邏輯\n{breakdown.replace('<br>', '  \n')}\n\n### 🎯 核心定義\n{definition.replace('<br>', '  \n')}"
            st.session_state.manual_input_content = draft
            st.session_state.mobile_nav = "📄 講義"
            st.rerun()

# ==========================================
# 3. 頁面路由
# ==========================================

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
                # 這裡已經把 Series 轉成 dict 存入 Session 了
                st.session_state.selected_word = pool.sample(1).iloc[0].to_dict()
            st.rerun()

    search_q = st.text_input("搜尋單字...", placeholder="例如: entropy")

    target_row = None
    if search_q:
        mask = df['word'].str.lower() == search_q.strip().lower()
        if mask.any(): target_row = df[mask].iloc[0].to_dict()
        else:
            fuzzy = df[df['word'].str.contains(search_q, case=False)]
            if not fuzzy.empty: target_row = fuzzy.iloc[0].to_dict()
    
    if not target_row and "selected_word" in st.session_state:
        target_row = st.session_state.selected_word
    
    if not target_row and not df.empty:
        target_row = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target_row

    if target_row:
        render_word_card(target_row)

# (講義與贊助頁面保持簡潔版)
def page_handout():
    st.markdown("### 📄 講義製作")
    content = st.text_area("內容", value=st.session_state.get("manual_input_content", "請先選擇單字"), height=300)
    st.session_state.manual_input_content = content
    st.info("💡 手機端請直接複製內容至筆記 App 使用。")

def page_sponsor():
    st.markdown("### 💖 支持開發")
    st.markdown('<div class="word-card" style="text-align:center;">歡迎贊助支持 AI 算力支出！</div>', unsafe_allow_html=True)

def main():
    inject_mobile_css()
    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索"
    
    df = load_db()

    # 導航
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🔍 探索", use_container_width=True): st.session_state.mobile_nav = "🔍 探索"; st.rerun()
    with c2: 
        if st.button("📄 講義", use_container_width=True): st.session_state.mobile_nav = "📄 講義"; st.rerun()
    with c3: 
        if st.button("💖 支持", use_container_width=True): st.session_state.mobile_nav = "💖 支持"; st.rerun()

    st.markdown("---")

    if st.session_state.mobile_nav == "🔍 探索":
        page_explore(df)
    elif st.session_state.mobile_nav == "📄 講義":
        page_handout()
    elif st.session_state.mobile_nav == "💖 支持":
        page_sponsor()

if __name__ == "__main__":
    main()
