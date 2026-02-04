import streamlit as st
import pandas as pd
import base64, time, re
from io import BytesIO
from gtts import gTTS
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置：沈浸式讀書介面
# ==========================================
st.set_page_config(page_title="Kadowsella | Read Only", page_icon="📖", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            /* 適合長時間閱讀的配色 */
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1E293B; margin-bottom: 5px; }
            .vibe-box { 
                background-color: #F1F5F9; padding: 20px; border-radius: 12px; 
                border-left: 6px solid #64748B; color: #334155; margin: 15px 0;
            }
            .breakdown-wrapper {
                background: #F8FAFC; padding: 20px; border-radius: 12px;
                border: 1px solid #E2E8F0; color: #1E293B;
            }
            .stMetric { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心功能 (僅保留讀取與清洗)
# ==========================================

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    text = str(text).replace('\\n', '  \n').replace('\n', '  \n')
    if '\\\\' in text: text = text.replace('\\\\', '\\')
    return text.strip('"').strip("'")

def speak(text, key_suffix=""):
    # 保留語音，因為聽覺記憶對補習班複習很重要
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    if not english_only.strip(): return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{key_suffix}"
        html_code = f"""<button onclick="document.getElementById('{unique_id}').play()" style="cursor:pointer; border-radius:5px; border:1px solid #ddd; background:white; padding:4px 8px;">🔊 Listen</button>
                        <audio id="{unique_id}"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>"""
        st.components.v1.html(html_code, height=35)
    except: pass

@st.cache_data(ttl=600) # 快取 10 分鐘，節省流量
def load_db():
    conn = st.connection("gsheets", type=GSheetsConnection)
    url = st.secrets["gsheets"]["cram_url"] # 專讀補習班庫
    df = conn.read(spreadsheet=url, ttl=0)
    return df.fillna("無")

# ==========================================
# 3. 讀取頁面 UI (修剪掉所有回報按鈕)
# ==========================================

def show_card(row):
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    st.caption(f"🏷️ {row['category']} | /{row['phonetic']}/")
    
    with st.container():
        st.markdown(f"<div class='breakdown-wrapper'><b>🧬 邏輯拆解：</b><br>{fix_content(row['breakdown'])}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**🎯 定義：**\n{fix_content(row['definition'])}")
    with col2:
        st.success(f"**💡 核心：**\n{fix_content(row['roots'])}")
    
    if row['native_vibe'] != "無":
        st.markdown(f"<div class='vibe-box'><b>🌊 專家心法：</b><br>{row['native_vibe']}</div>", unsafe_allow_html=True)
    
    speak(row['word'], f"read_{row['word']}")

# ==========================================
# 4. 主程式
# ==========================================

def main():
    inject_custom_css()
    df = load_db()
    
    st.sidebar.title("📚 Med-Prep Mode")
    mode = st.sidebar.radio("切換功能", ["隨機複習", "全庫檢索"])
    
    if mode == "隨機複習":
        st.title("💡 High-Yield Review")
        if st.button("🎲 換一題", use_container_width=True):
            st.rerun()
        if not df.empty:
            show_card(df.sample(1).iloc[0])
            
    else:
        st.title("🔍 知識庫檢索")
        search = st.text_input("輸入關鍵字搜尋...")
        if search:
            results = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            for _, row in results.iterrows():
                with st.expander(f"{row['word']} - {row['category']}"):
                    show_card(row)
        else:
            st.dataframe(df[['word', 'category', 'definition']], use_container_width=True)

if __name__ == "__main__":
    main()
