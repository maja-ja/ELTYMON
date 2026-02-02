import streamlit as st
import pandas as pd
import base64
import time
import random
from io import BytesIO
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import json

# ==========================================
# 1. 核心配置與視覺美化 (CSS)
# ==========================================
st.set_page_config(page_title="Etymon Decoder v2.5", page_icon="🧩", layout="wide")
def inject_custom_css():
    st.markdown("""
        <style>
            /* 1. 核心字體：採用現代無襯線字體，確保英中混排完美 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Noto+Sans+TC:wght@500;700&display=swap');

            .breakdown-container {
                /* 使用 Inter 處理英文，Noto Sans TC 處理中文 */
                font-family: 'Inter', 'Noto Sans TC', sans-serif; 
                font-size: 1.8rem !important; 
                font-weight: 700;
                letter-spacing: 1px;
                
                /* 漸層科技感背景 */
                background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
                color: #FFFFFF;
                
                /* 形狀與間距 */
                padding: 12px 30px;
                border-radius: 15px; /* 微圓角矩形，比膠囊型更具現代感 */
                display: inline-block;
                margin: 20px 0;
                
                /* 外陰影，讓它「浮」起來 */
                box-shadow: 0 4px 15px rgba(30, 136, 229, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            /* 針對內部的括號與加號做細微調整 */
            .breakdown-container span.operator {
                color: #BBDEFB; /* 讓 + 號顏色稍淡一點，突出主體 */
                margin: 0 8px;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 工具函式 (音訊與 20 欄讀取)
# ==========================================

def speak(text, key_suffix=""):
    try:
        if not text: return
        tts = gTTS(text=text, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time())}_{key_suffix}"
        st.components.v1.html(f'<audio id="{unique_id}" autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio><script>document.getElementById("{unique_id}").play();</script>', height=0)
    except Exception as e: st.error(f"語音錯誤: {e}")

@st.cache_data(ttl=30)
def load_db():
    COL_NAMES = [
        'category', 'roots', 'meaning', 'word', 'breakdown', 
        'definition', 'phonetic', 'example', 'translation', 'native_vibe',
        'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
        'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag'
    ]
    # 使用您的試算表 ID
    # 約第 68 行
    SHEET_ID = '1qyHWIWq3albA8czV_ZZ4ofXjP02D3rz2R9YVC4E4Fz4' # 你的 MyDB ID
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&range=A:T'
    try:
        df = pd.read_csv(url)
        # 強制對齊 20 欄，若欄位不足則補齊
        for i, col in enumerate(COL_NAMES):
            if i >= len(df.columns): df[col] = ""
        df.columns = COL_NAMES
        return df.dropna(subset=['word']).fillna("").reset_index(drop=True)
    except Exception as e:
        st.error(f"資料庫連線失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

# ==========================================
# 3. 百科級顯示組件 (融合正式版邏輯)
# ==========================================
def ai_decode_and_save(word):
    # 從 secrets 讀取 API Key
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 【安全熔斷指令】與 20 欄位定義
    prompt = f"""
    Role: Kadowsella 語言架構師 & 安全審核官。
    Task: 解構單字「{word}」。
    
    ## 輸出格式: 嚴格 JSON，包含以下 20 個欄位（繁體中文）：
    category, roots, meaning, word, breakdown, definition, phonetic, example, 
    translation, native_vibe, synonym_nuance, visual_prompt, social_status, 
    emotional_tone, street_usage, collocation, etymon_story, usage_warning, 
    memory_hook, audio_tag
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- 頁面邏輯：AI 解碼實驗室 ---
def page_ai_lab():
    st.title("🔬 Kadowsella 解碼實驗室")
    st.write("輸入新知識，AI 將自動填寫 20 欄位並存入你的 **MyDB** 書架。")
    
    new_word = st.text_input("輸入想解碼的單字或知識點：", placeholder="例如: 'metabolism'...")
    
    if st.button("啟動三位一體解碼", type="primary"):
        if not new_word:
            st.warning("請先輸入單字。")
            return

        with st.spinner(f'正在為「{new_word}」進行深度解碼...'):
            try:
                # 1. 呼叫 AI (第一、二個人)
                raw_res = ai_decode_and_save(new_word)
                # 清理 Markdown 標籤
                clean_json = raw_res.replace('```json', '').replace('```', '').strip()
                res_data = json.loads(clean_json)


                # 2. 寫入書架 (第三個人)
                conn = st.connection("gsheets", type=GSheetsConnection)
                
                # 讀取現有資料並 Append 新的一列
                # 注意：這裡需要你的 Service Account 具備寫入權限
                existing_data = conn.read(spreadsheet=st.secrets["gsheets"]["spreadsheet"])
                new_row = pd.DataFrame([res_data])
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                conn.update(spreadsheet=st.secrets["gsheets"]["spreadsheet"], data=updated_df)
                
                st.success(f"🎉 解碼完成！「{new_word}」已永久存入你的 MyDB 書架。")
                st.balloons()
                
                # 預覽剛剛生成的卡片
                st.markdown("---")
                show_encyclopedia_card(res_data)

            except Exception as e:
                st.error(f"解碼過程出錯: {e}")
def show_encyclopedia_card(row):
    """美化顯示單一單字的百科卡片"""
    # --- 頂部：單字 Hero 區 ---
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-phonetic'>/{row['phonetic']}/</div>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("🔊 朗讀", key=f"spk_{row['word']}", use_container_width=True):
            speak(row['word'], row['word'])
    with col_b:
        styled_breakdown = row['breakdown'].replace("+", "<span class='operator'>+</span>")
        st.markdown(f"<div class='breakdown-container'>{styled_breakdown}</div>", unsafe_allow_html=True)

    # --- 中間：定義與字根 ---
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**🎯 定義：**\n{row['definition']}")
        st.write(f"**📝 例句：**\n{row['example']}")
        st.caption(f"（{row['translation']}）")
    with c2:
        st.success(f"**💡 字根：** {row['roots']}\n\n**意義：** {row['meaning']}")
        st.markdown(f"**🪝 記憶鉤子：**\n{row['memory_hook']}")

    # --- 關鍵：語感驚喜包 (正式版特色) ---
    if row['native_vibe']:
        # 檢查當前單字是否已解鎖 (使用 session_state 紀錄單字)
        unlocked_key = f"unlocked_{row['word']}"
        if not st.session_state.get(unlocked_key, False):
            if st.button("🎁 拆開語感驚喜包 (Unlock Native Vibe)", use_container_width=True, type="secondary"):
                st.session_state[unlocked_key] = True
                st.balloons()
                st.rerun()
        else:
            st.markdown(f"""
                <div class='vibe-box'>
                    <h4 style='color:#1E88E5; margin-top:0;'>🌊 母語人士語感 (Native Vibe)</h4>
                    <p style='font-style: italic; font-size: 1.1rem;'>{row['native_vibe']}</p>
                </div>
            """, unsafe_allow_html=True)

    # --- 底部：深度百科擴充 ---
    with st.expander("📚 查看深度百科 (文化、社會、街頭實戰)"):
        t1, t2, t3 = st.tabs(["🏛️ 字源文化", "👔 社會地位", "😎 街頭實戰"])
        with t1:
            st.write(f"**📜 字源故事：** {row['etymon_story']}")
            st.write(f"**⚖️ 同義詞辨析：** {row['synonym_nuance']}")
        with t2:
            st.write(f"**🎨 視覺提示：** {row['visual_prompt']}")
            st.write(f"**👔 社會感：** {row['social_status']} | **🌡️ 情緒值：** {row['emotional_tone']}")
        with t3:
            st.write(f"**🏙️ 街頭用法：** {row['street_usage']}")
            st.write(f"**🔗 常用搭配：** {row['collocation']}")
            if row['usage_warning']:
                st.error(f"⚠️ 使用警告：{row['usage_warning']}")

# ==========================================
# 4. 頁面邏輯 (融合 Tabs 模式)
# ==========================================

def page_home(df):
    st.markdown("<h1 style='text-align: center;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.write("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("📚 總單字量", len(df))
    c2.metric("🏷️ 分類主題", df['category'].nunique())
    c3.metric("🧩 獨特字根", df['roots'].nunique())
    st.write("---")
    st.info("👈 請從左側選單進入「學習與搜尋」開啟您的語感之旅。")

def page_learn_search(df):
    st.title("📖 學習與搜尋")
    tab_card, tab_list = st.tabs(["🎲 隨機探索", "🔍 資料庫列表"])
    
    with tab_card:
        # 1. 篩選
        cats = ["全部"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("選擇學習分類", cats)
        f_df = df if sel_cat == "全部" else df[df['category'] == sel_cat]

        # 2. 隨機邏輯
        if st.button("下一個單字 (Next Word) ➔", use_container_width=True, type="primary"):
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
            st.rerun()

        if 'curr_w' not in st.session_state and not f_df.empty:
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()

        if 'curr_w' in st.session_state:
            show_encyclopedia_card(st.session_state.curr_w)

    with tab_list:
        search = st.text_input("🔍 搜尋單字、字根或中文定義...", placeholder="例如: 'bio' 或 '生命'...")
        if search:
            mask = df.apply(lambda r: search.lower() in str(r.values).lower(), axis=1)
            display_df = df[mask]
        else:
            display_df = df.head(50)
            
        st.write(f"顯示 {len(display_df)} 筆結果")
        st.dataframe(display_df[['word', 'definition', 'roots', 'category', 'native_vibe']], use_container_width=True)

def page_quiz(df):
    st.title("🧠 字根記憶挑戰")
    cat = st.selectbox("選擇測驗範圍", df['category'].unique())
    pool = df[df['category'] == cat]
    
    if st.button("🎲 抽一題", use_container_width=True):
        st.session_state.q = pool.sample(1).iloc[0].to_dict()
        st.session_state.show_ans = False

    if 'q' in st.session_state:
        st.markdown(f"### ❓ 請問這對應哪個單字？")
        st.info(st.session_state.q['definition'])
        st.write(f"**提示 (字根):** {st.session_state.q['roots']} ({st.session_state.q['meaning']})")
        
        if st.button("揭曉答案"):
            st.session_state.show_ans = True
        
        if st.session_state.show_ans:
            st.success(f"💡 答案是：**{st.session_state.q['word']}**")
            speak(st.session_state.q['word'], "quiz")
            st.write(f"結構拆解：`{st.session_state.q['breakdown']}`")

# ==========================================
# 5. 主程式
def main():
    inject_custom_css()
    
    # 手機端優化：隱藏側邊欄位後，讓內容更集中
    st.sidebar.title("Kadowsella Protocol")
    page = st.sidebar.radio(
        "功能選單", 
        ["首頁", "學習與搜尋", "測驗模式", "🔬 AI 解碼實驗室"]
    )
    st.sidebar.markdown("---")
    
    # 載入資料庫
    df = load_db()

    if page == "首頁":
        page_home(df)
    elif page == "學習與搜尋":
        if df.empty:
            st.warning("資料庫目前是空的，請先使用解碼實驗室新增單字。")
        else:
            page_learn_search(df)
    elif page == "測驗模式":
        if df.empty:
            st.warning("資料庫沒有單字可以進行測驗。")
        else:
            page_quiz(df)
    elif page == "🔬 AI 解碼實驗室":
        page_ai_lab()

    # 頁尾標記
    st.sidebar.caption("v2.5 自用書架版 | 不限地點隨身解碼")

if __name__ == "__main__":
    main()
