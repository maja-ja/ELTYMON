import streamlit as st
import pandas as pd
import base64, re
from io import BytesIO
from gtts import gTTS
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置：醫學系衝刺風格 UI
# ==========================================
st.set_page_config(page_title="Kadowsella | Study Mode", page_icon="📖", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            /* 適合長時間閱讀的灰藍配色 */
            .hero-word { font-size: 3rem; font-weight: 800; color: #1E293B; margin-bottom: 2px; }
            .vibe-box { 
                background-color: #F1F5F9; padding: 20px; border-radius: 12px; 
                border-left: 8px solid #475569; color: #334155; margin: 15px 0;
            }
            .breakdown-wrapper {
                background: #F8FAFC; padding: 20px; border-radius: 12px;
                border: 1px solid #E2E8F0; color: #1E293B; line-height: 1.6;
            }
            /* 隱藏所有不必要的開發者元素 */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .stButton>button { width: 100%; border-radius: 8px; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心讀取與清洗功能
# ==========================================

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    # 處理資料庫中的列表格式與換行 
    text = str(text).replace('\\n', '  \n').replace('\n', '  \n')
    if '\\\\' in text: text = text.replace('\\\\', '\\')
    return text.strip('"').strip("'")

def speak(text, key_suffix=""):
    # 針對英語單字提供發音支援 
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    if not english_only.strip(): return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{key_suffix}"
        html_code = f"""
            <button onclick="document.getElementById('{unique_id}').play()" style="cursor:pointer; border-radius:8px; border:1px solid #CBD5E1; background:white; padding:6px 12px; font-size:14px;">🔊 Listen</button>
            <audio id="{unique_id}"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>
        """
        st.components.v1.html(html_code, height=45)
    except: pass

@st.cache_data(ttl=600) 
def load_db():
    # 連接至你的 MyDB 的副本 
    conn = st.connection("gsheets", type=GSheetsConnection)
    url = "https://docs.google.com/spreadsheets/d/1jTsd9IWQEMG6jfYmYnAJ9AO0NUIz8pp9iOku0Diyybo/edit"
    df = conn.read(spreadsheet=url, ttl=0)
    return df.fillna("無")

# ==========================================
# 3. 沈浸式卡片 UI
# ==========================================

def show_card(row):
    # 標題與音標
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    if row['phonetic'] != "無":
        st.caption(f"/{row['phonetic']}/")
    
    # 邏輯拆解：展示資料庫中的 breakdown 欄位 
    st.markdown(f"<div class='breakdown-wrapper'><b>🧬 邏輯拆解：</b><br>{fix_content(row['breakdown'])}</div>", unsafe_allow_html=True)
    
    # 核心資訊欄位
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**🎯 定義與解釋**\n\n{fix_content(row['definition'])}")
    with col2:
        st.success(f"**💡 核心原理**\n\n{fix_content(row['roots'])}")
        st.warning(f"**🪝 記憶鉤子**\n\n{fix_content(row['memory_hook'])}")
    
    # 專家視角：展示 native_vibe 欄位 
    if row['native_vibe'] != "無":
        st.markdown(f"<div class='vibe-box'><b>🌊 專家心法：</b><br>{row['native_vibe']}</div>", unsafe_allow_html=True)
    
    speak(row['word'], f"read_{row['word']}")

# ==========================================
# 4. 主程式：移除所有寫入入口
# ==========================================

def main():
    inject_custom_css()
    
    try:
        df = load_db()
    except:
        st.error("無法連接資料庫，請檢查 secrets 設定。")
        return
    
    st.sidebar.title("🧬 Study Mode")
    st.sidebar.info("目標：台大醫學系衝刺")
    
    mode = st.sidebar.radio("導覽", ["🎲 隨機探索", "🔍 全庫搜尋"])
    
    if mode == "🎲 隨機探索":
        st.title("💡 今日高效複習")
        if st.button("換一個知識點", type="primary"):
            st.rerun()
        
        if not df.empty:
            random_row = df.sample(1).iloc[0]
            show_card(random_row)
            
    else:
        st.title("🔍 知識庫檢索")
        search_query = st.text_input("輸入關鍵字 (如：元認知、量子、ASD)...")
        
        if search_query:
            # 搜尋 word、definition 或 category 
            mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
            results = df[mask]
            
            st.write(f"找到 {len(results)} 筆結果：")
            for _, row in results.iterrows():
                with st.expander(f"📘 {row['word']} ({row['category']})"):
                    show_card(row)
        else:
            # 預設展示簡表
            st.dataframe(df[['word', 'category', 'definition']], use_container_width=True)

if __name__ == "__main__":
    main()
