import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import os
from io import BytesIO
from gtts import gTTS
import google.generativeai as genai

# ==========================================
# 1. 核心配置與 CSS
# ==========================================
st.set_page_config(page_title="Etymon Decoder v3.0", page_icon="🧩", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            .breakdown-wrapper {
                background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
                padding: 25px; border-radius: 15px; color: white !important; margin: 20px 0;
            }
            .breakdown-wrapper p, .breakdown-wrapper li { color: white !important; font-weight: 700; }
            .hero-word { font-size: 3rem; font-weight: 800; color: #1A237E; }
            .vibe-box { 
                background-color: #F0F7FF; padding: 20px; border-radius: 12px; 
                border-left: 6px solid #2196F3; color: #2C3E50; margin: 15px 0;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 資料處理 (master_db.json)
# ==========================================
DB_FILE = 'master_db.json'
COL_NAMES = [
    'category', 'roots', 'meaning', 'word', 'breakdown', 
    'definition', 'phonetic', 'example', 'translation', 'native_vibe',
    'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
    'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag'
]

def load_db():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=COL_NAMES)
    try:
        df = pd.read_json(DB_FILE, orient='records')
        # 補齊缺失欄位
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.fillna("無")
    except Exception as e:
        st.error(f"讀取資料庫失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

def save_db(df):
    try:
        df.to_json(DB_FILE, orient='records', force_ascii=False, indent=4)
    except Exception as e:
        st.error(f"儲存資料庫失敗: {e}")

def fix_content(text):
    if text is None or str(text) in ["無", "nan", ""]: return ""
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
        html_code = f"""<button style="padding:5px 10px; border-radius:8px; cursor:pointer;" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
        <audio id="{unique_id}"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>"""
        st.components.v1.html(html_code, height=45)
    except: pass

# ==========================================
# 3. AI 解碼核心
# ==========================================
def ai_decode(input_text, category):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    
    prompt = f"""
    Task: 解構「{input_text}」為高品質百科 JSON。
    身份：你是「{category}」專家。
    欄位對照：category, word, roots(LaTeX), meaning(痛點), breakdown(流程), definition(ELI5), phonetic(背景/發音), example(場景), translation(🍎生活比喻), native_vibe(🌊專家心法), synonym_nuance, visual_prompt, social_status, emotional_tone, street_usage, collocation, etymon_story, usage_warning, memory_hook, audio_tag.
    規範：輸出純 JSON，不含 ```json，引號用單引號或中文引號，換行用 \\\\n。
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(prompt)
        return res.text if res else None
    except: return None

# ==========================================
# 4. 介面組件
# ==========================================
def show_card(row):
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    st.caption(f"📍 {row['category']} | {row['phonetic']}")
    speak(row['word'], "main")
    
    st.markdown(f"<div class='breakdown-wrapper'><h4>🧬 邏輯拆解</h4>{fix_content(row['breakdown'])}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"### 🎯 定義\n{row['definition']}\n\n**📝 應用：**\n{row['example']}")
    with c2:
        st.success(f"### 💡 原理\n{str(row['roots']).replace('$', '$$')}\n\n**🔍 意義：**\n{row['meaning']}")

    if row['native_vibe'] != "無":
        st.markdown(f"<div class='vibe-box'>{row['native_vibe']}</div>", unsafe_allow_html=True)

# ==========================================
# 5. 各分頁邏輯
# ==========================================
def page_home(df):
    st.title("🚀 Etymon Decoder")
    st.metric("📚 總單字量", len(df))
    st.write("---")
    if not df.empty:
        if st.button("🔄 換一批推薦"): st.rerun()
        sample = df.sample(min(3, len(df)))
        cols = st.columns(3)
        for i, (idx, row) in enumerate(sample.iterrows()):
            with cols[i]:
                st.subheader(row['word'])
                st.write(row['definition'])
                speak(row['word'], f"h_{i}")

def page_learn(df):
    st.title("📖 學習中心")
    search = st.text_input("🔍 搜尋單字或分類...")
    if search:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    
    if not df.empty:
        if 'idx' not in st.session_state: st.session_state.idx = 0
        if st.button("🎲 隨機抽一個"):
            st.session_state.idx = df.sample(1).index[0]
        
        target = df.loc[st.session_state.idx] if st.session_state.idx in df.index else df.iloc[0]
        show_card(target)

def page_lab(df):
    st.title("🔬 解碼實驗室")
    word = st.text_input("輸入解碼主題")
    cat = st.selectbox("領域", ["英語辭源", "數學邏輯", "物理科學", "程式開發", "雜類"])
    
    if st.button("啟動 AI 解碼", type="primary"):
        with st.spinner("AI 思考中..."):
            raw_res = ai_decode(word, cat)
            if raw_res:
                try:
                    match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                    res_json = json.loads(match.group(0), strict=False)
                    new_df = pd.concat([df, pd.DataFrame([res_json])], ignore_index=True)
                    save_db(new_df)
                    st.success("解碼完成並存入 master_db.json！")
                    show_card(res_json)
                except Exception as e: st.error(f"解析失敗: {e}")

# ==========================================
# 6. 主入口
# ==========================================
def main():
    inject_custom_css()
    df = load_db()
    
    st.sidebar.title("Kadowsella")
    is_admin = st.sidebar.checkbox("上帝模式 (解碼)")
    
    menu = ["首頁", "學習中心"]
    if is_admin: menu.append("🔬 解碼實驗室")
    
    choice = st.sidebar.radio("選單", menu)
    
    if choice == "首頁": page_home(df)
    elif choice == "學習中心": page_learn(df)
    elif choice == "🔬 解碼實驗室": page_lab(df)

if __name__ == "__main__":
    main()