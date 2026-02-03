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
# 1. 核心配置與 25-44 歲專業感視覺
# ==========================================
st.set_page_config(page_title="Etymon Decoder v3.0 | 專業版", page_icon="🧩", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            /* 專業藍調背景與字體 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
            html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
            
            .breakdown-wrapper {
                background: linear-gradient(135deg, #0D47A1 0%, #1976D2 100%);
                padding: 30px; border-radius: 20px; color: white !important; 
                margin: 25px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .breakdown-wrapper h4 { color: #BBDEFB !important; letter-spacing: 2px; }
            .hero-word { 
                font-size: 4rem; font-weight: 900; color: #0D47A1; 
                margin-bottom: 0px; letter-spacing: -2px;
            }
            .vibe-box { 
                background-color: #F5F9FF; padding: 25px; border-radius: 15px; 
                border-left: 8px solid #0D47A1; color: #37474F; 
                font-style: italic; font-size: 1.1rem;
            }
            .stButton>button {
                border-radius: 12px; padding: 10px 25px; font-weight: 700;
                transition: all 0.3s ease;
            }
            .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 高效能資料庫處理 (不卡頓關鍵)
# ==========================================
DB_FILE = 'master_db.json'
COL_NAMES = [
    'category', 'roots', 'meaning', 'word', 'breakdown', 
    'definition', 'phonetic', 'example', 'translation', 'native_vibe',
    'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
    'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag'
]

@st.cache_data(ttl=600) # 每10分鐘快取一次，30萬流量才扛得住
def load_db():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=COL_NAMES)
    try:
        # 讀取本地 JSON，這是目前最快的做法
        df = pd.read_json(DB_FILE, orient='records')
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.fillna("無")
    except:
        return pd.DataFrame(columns=COL_NAMES)

def save_db(df):
    df.to_json(DB_FILE, orient='records', force_ascii=False, indent=4)
    st.cache_data.clear() # 更新後清除快取

# ==========================================
# 3. 20 欄位 AI 專家指令 (核心靈魂)
# ==========================================
def ai_decode(input_text, category):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    
    # 這裡鎖定你的 20 欄位與專家人格
    prompt = f"""
    任務：將單字「{input_text}」轉化為 Etymon Decoder 專業 JSON。
    身份：你是精通醫學、資工與語言學的「聯覺專家」。
    
    欄位要求：
    1. roots: 必須使用 LaTeX 格式，例如 $ad- + nihil$.
    2. meaning: 鎖定專業痛點。
    3. definition: 給 25-44 歲精英看的簡潔定義。
    4. translation: 必須包含一個 🍎 生活比喻。
    5. native_vibe: 提供一個該領域的專家心法或🌊場景感。
    
    輸出格式：嚴格 JSON，欄位包含：{', '.join(COL_NAMES)}。
    注意：不要輸出任何解釋文字，只要純 JSON 代碼。
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-pro') # 商業版建議用 Pro
        res = model.generate_content(prompt)
        return res.text if res else None
    except: return None

# ==========================================
# 4. 專業級 UI 組件
# ==========================================
def show_card(row):
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    st.markdown(f"**{row['phonetic']}** | `{row['category']}`")
    
    # 音訊播放 (Web Speech API 預備位)
    if st.button(f"🔊 播放音訊 ({row['word']})"):
        tts = gTTS(text=row['word'], lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp)
    
    st.markdown(f"""
    <div class='breakdown-wrapper'>
        <h4>🧬 語源邏輯拆解 (Etymology Breakdown)</h4>
        {row['breakdown'].replace('\\n', '<br>')}
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎯 精準定義")
        st.info(row['definition'])
        st.markdown("### 📝 實戰場景")
        st.write(row['example'])
    with col2:
        st.markdown("### 🧪 核心公式")
        st.latex(row['roots'].replace('$', ''))
        st.markdown("### 🔍 專家意義")
        st.success(row['meaning'])

    if row['native_vibe'] != "無":
        st.markdown(f"<div class='vibe-box'>🌊 專家心法：{row['native_vibe']}</div>", unsafe_allow_html=True)
    
    with st.expander("🚀 高階解析 (Social, Emotional, Memory Hook)"):
        st.write(f"**🍎 生活比喻：** {row['translation']}")
        st.write(f"**💡 記憶金句：** {row['memory_hook']}")
        st.write(f"**⚠️ 使用禁忌：** {row['usage_warning']}")

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    df = load_db()
    
    st.sidebar.title("🧬 Kadowsella v3.0")
    st.sidebar.write(f"📊 30萬人驗證的知識引擎")
    
    # 上帝模式權限 (未來可改為登入制)
    is_admin = st.sidebar.toggle("解碼實驗室 (上帝模式)", value=False)
    
    menu = ["🔍 單字搜尋", "📖 7000單學習庫"]
    if is_admin: menu.append("🔬 AI 批量洗資料")
    
    choice = st.sidebar.radio("導覽選單", menu)

    if choice == "🔍 單字搜尋":
        st.title("🧩 語源邏輯解碼器")
        query = st.text_input("輸入你想拆解的單字 (例如: annihilate, heart, algorithm)...").strip()
        if query:
            result = df[df['word'].str.lower() == query.lower()]
            if not result.empty:
                show_card(result.iloc[0])
            else:
                st.warning("資料庫尚未收錄此單字，請切換至實驗室由 AI 進行解碼。")

    elif choice == "📖 7000單學習庫":
        st.title("📚 高中 7000 單 | 專業升級版")
        level = st.select_slider("選擇難度分級", options=["Level 1", "Level 2", "Level 3", "Level 4", "Level 5", "Level 6"])
        filtered_df = df[df['category'].str.contains(level, na=False)]
        
        if not filtered_df.empty:
            idx = st.slider("瀏覽單字", 0, len(filtered_df)-1, 0)
            show_card(filtered_df.iloc[idx])
        else:
            st.info(f"正在等待 AI 洗滌 {level} 的資料...")

    elif choice == "🔬 AI 批量洗資料":
        st.title("🔬 AI 知識生產線")
        st.write("這是在補習期間，讓 Google 幫你打工的地方。")
        raw_input = st.text_area("貼入單字列表 (以換行分隔)")
        category = st.selectbox("這批單字的領域", ["醫學字根", "AI資工", "高中7000單-Level1", "高階寫作"])
        
        if st.button("開始批次洗資料 (Run Batch)", type="primary"):
            words = [w.strip() for w in raw_input.split('\n') if w.strip()]
            progress = st.progress(0)
            for i, word in enumerate(words):
                with st.spinner(f"正在加工: {word}..."):
                    res_raw = ai_decode(word, category)
                    if res_raw:
                        try:
                            # 強化 JSON 提取邏輯
                            match = re.search(r'\{.*\}', res_raw, re.DOTALL)
                            item = json.loads(match.group(0).replace("'", '"'))
                            df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
                            save_db(df)
                        except:
                            st.error(f"單字 {word} 解析失敗")
                progress.progress((i + 1) / len(words))
            st.success(f"成功完成 {len(words)} 筆資料洗滌！")

if __name__ == "__main__":
    main()