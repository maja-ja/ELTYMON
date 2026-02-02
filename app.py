import streamlit as st
import pandas as pd
import base64
import time
import json
import re  # 新增：用於精準提取 JSON
from io import BytesIO
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置與視覺美化 (CSS)
# ==========================================
st.set_page_config(page_title="Etymon Decoder v2.5", page_icon="🧩", layout="wide")
def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Noto+Sans+TC:wght@500;700&display=swap');
            
            /* 1. 拆解區塊樣式 */
            .breakdown-container {
                font-family: 'Inter', 'Noto Sans TC', sans-serif; 
                font-size: 1.8rem !important; 
                font-weight: 700;
                letter-spacing: 1px;
                background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
                color: #FFFFFF;
                padding: 12px 30px;
                border-radius: 15px;
                display: inline-block;
                margin: 20px 0;
                box-shadow: 0 4px 15px rgba(30, 136, 229, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .breakdown-container span.operator {
                color: #BBDEFB;
                margin: 0 8px;
            }

            /* 2. 手機響應式調整 */
            @media (max-width: 600px) {
                .breakdown-container {
                    font-size: 1.2rem !important;
                    display: block;
                    text-align: center;
                }
            }

            /* 3. 單字與音標 */
            .hero-word { font-size: 2.5rem; font-weight: 800; color: #333; }
            /* 如果在深色模式下，單字標題也要確保看得到 */
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #FFF; }
            }
            .hero-phonetic { font-size: 1.2rem; color: #888; font-family: monospace; margin-bottom: 10px; }

            /* 4. [修正點] 語感區塊：強制深色文字 */
            .vibe-box { 
                background-color: #E3F2FD; 
                padding: 15px; 
                border-radius: 10px; 
                border-left: 5px solid #2196F3; 
                
                /* 這裡強制指定文字顏色為深灰，避免被深色模式反白 */
                color: #333333 !important; 
            }
            /* 確保 box 裡面的標題也是深藍色 */
            .vibe-box h4 {
                color: #1565C0 !important;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 工具函式
# ==========================================

def speak(text, key_suffix=""):
    try:
        if not text: return
        tts = gTTS(text=text, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time())}_{key_suffix}"
        # 隱藏播放器，自動播放
        st.components.v1.html(f'<audio id="{unique_id}" autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio><script>document.getElementById("{unique_id}").play();</script>', height=0)
    except Exception as e: st.error(f"語音錯誤: {e}")

def get_spreadsheet_url():
    """安全地獲取試算表網址，相容兩種 secrets 格式"""
    try:
        # 優先嘗試 connections 結構
        return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except:
        try:
            # 備用：直接結構
            return st.secrets["gsheets"]["spreadsheet"]
        except:
            st.error("找不到 spreadsheet 設定，請檢查 secrets.toml")
            return ""

@st.cache_data(ttl=60)
def load_db():
    COL_NAMES = [
        'category', 'roots', 'meaning', 'word', 'breakdown', 
        'definition', 'phonetic', 'example', 'translation', 'native_vibe',
        'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
        'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag'
    ]
    
    # 使用 GSheetsConnection 讀取 (比 pd.read_csv 更穩定且能利用快取)
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        df = conn.read(spreadsheet=url, ttl=60) # 加入 TTL 避免頻繁讀取
        
        # 強制對齊 20 欄
        for col in COL_NAMES:
            if col not in df.columns:
                df[col] = ""
        
        # 只保留這 20 個欄位並去除非單字行
        df = df[COL_NAMES].dropna(subset=['word']).fillna("").reset_index(drop=True)
        return df
    except Exception as e:
        # Fallback: 如果連線失敗，回傳空表以免 App 崩潰
        st.error(f"資料庫連線失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

# ==========================================
# 3. AI 解碼核心 (自用解鎖版)
# ==========================================
def ai_decode_and_save(input_text):
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # 設定無限制的安全過濾
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=safety_settings)
    
    prompt = f"""
    Role: 全領域知識解構專家 (Polymath Decoder).
    Task: 分析輸入內容「{input_text}」，判斷其領域（語言學習、歷史、科學、商業、程式碼等），並將其解構為結構化知識。

    ## 處理邏輯 (Field Mapping Strategy):
    請將知識映射到以下 20 個固定欄位中 (欄位名稱雖然是英文單字相關，但請靈活借代)：
    
    1. **category**: 知識分類 (如: 物理學、商業模型、Python語法)。
    2. **word**: 核心概念名稱 (Title)。
    3. **roots**: 核心原理 / 關鍵公式 / 底層邏輯 (The "Root" cause)。
    4. **meaning**: 該概念的核心價值或解決了什麼問題。
    5. **breakdown**: 結構拆解 / 步驟流程 / 程式碼片段。
    6. **definition**: 給初學者的「一句話解釋」 (ELI5)。
    7. **phonetic**: (若非單字) 請填入關鍵人名或關鍵時間點。
    8. **example**: 實際應用案例 / 場景。
    9. **translation**: 類比說明 (用生活例子比喻)。
    10. **native_vibe**: 專家視角 / 內行人的心法 (Insider Insight)。
    11. **synonym_nuance**: 易混淆概念比較 / 相似理論辨析。
    12. **visual_prompt**: 視覺化想像畫面 (幫助記憶的圖景)。
    13. **social_status**: 重要性評級 / 在該領域的地位。
    14. **emotional_tone**: 學習該知識的情緒基調 (如: 嚴肅、反直覺、優雅)。
    15. **street_usage**: (若非單字) 請填入「常見誤區」或「坑」。
    16. **collocation**: 相關聯的知識點 / 延伸閱讀關鍵字。
    17. **etymon_story**: 起源故事 / 發明背景 / 歷史脈絡。
    18. **usage_warning**: 使用注意 / 限制條件 / 邊界情況。
    19. **memory_hook**: 金句記憶法 / 口訣。
    20. **audio_tag**: (留空或填入 hashtags)。

    ## 輸出規範：
    1. 必須是嚴格的 JSON 格式。
    2. 內容以繁體中文為主。
    3. 不論輸入是什麼，都必須填滿上述 20 個欄位，沒有的請填 "無"。
    """
    
    response = model.generate_content(prompt)
    return response.text

def show_encyclopedia_card(row):
    """美化顯示單一單字的百科卡片"""
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-phonetic'>/{row['phonetic']}/</div>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("🔊 朗讀", key=f"spk_{row['word']}_{int(time.time())}", use_container_width=True):
            speak(row['word'], "card")
    with col_b:
        styled_breakdown = str(row['breakdown']).replace("+", "<span class='operator'>+</span>")
        st.markdown(f"<div class='breakdown-container'>{styled_breakdown}</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**🎯 定義：**\n{row['definition']}")
        st.write(f"**📝 例句：**\n{row['example']}")
        st.caption(f"（{row['translation']}）")
    with c2:
        st.success(f"**💡 字根：** {row['roots']}\n\n**意義：** {row['meaning']}")
        st.markdown(f"**🪝 記憶鉤子：**\n{row['memory_hook']}")

    # 語感部分
    if row['native_vibe']:
        st.markdown(f"""
            <div class='vibe-box'>
                <h4 style='color:#1E88E5; margin-top:0;'>🌊 母語人士語感 (Native Vibe)</h4>
                <p style='font-size: 1.1rem;'>{row['native_vibe']}</p>
            </div>
        """, unsafe_allow_html=True)

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
# 4. 頁面邏輯
# ==========================================
def page_ai_lab():
    st.title("🔬 Kadowsella 解碼實驗室")
    st.write("輸入新知識，AI 將自動填寫 20 欄位並存入你的 **MyDB** 書架。")
    
    col_input, col_check = st.columns([3, 1])
    with col_input:
        new_word = st.text_input("輸入想解碼的單字或知識點：", placeholder="例如: 'Entropy' 或 '量子力學'...")
    with col_check:
        # 新增：強制刷新開關
        st.write("") # 排版用
        st.write("") 
        force_refresh = st.checkbox("🔄 強制刷新\n(覆蓋舊資料)", value=False)
    
    if st.button("啟動三位一體解碼", type="primary"):
        if not new_word:
            st.warning("請先輸入內容。")
            return

        # --- 步驟 1: 先檢查資料庫是否已有此字 ---
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        existing_data = conn.read(spreadsheet=url, ttl=0)
        
        # 檢查單字是否存在 (不分大小寫比較安全)
        # 注意：這裡假設 'word' 欄位是索引鍵
        is_exist = False
        if not existing_data.empty:
            # 轉小寫比對，避免 Apple 和 apple 重複
            match_mask = existing_data['word'].astype(str).str.lower() == new_word.lower()
            is_exist = match_mask.any()

        if is_exist and not force_refresh:
            st.warning(f"⚠️ 「{new_word}」已經在書架上了！若要重新解碼，請勾選右側的『強制刷新』。")
            # 顯示現有卡片給使用者看
            existing_row = existing_data[match_mask].iloc[0].to_dict()
            st.markdown("---")
            st.info("👇 這是目前的庫存版本：")
            show_encyclopedia_card(existing_row)
            return

        # --- 步驟 2: AI 生成 ---
        with st.spinner(f'正在為「{new_word}」進行深度解碼...'):
            try:
                # 呼叫 AI
                raw_res = ai_decode_and_save(new_word)
                
                # 正則解析
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if not match:
                    st.error("AI 輸出格式錯誤，無法解析 JSON。")
                    st.code(raw_res)
                    return
                
                clean_json = match.group(0)
                res_data = json.loads(clean_json)

                # --- 步驟 3: 資料覆寫邏輯 ---
                if is_exist and force_refresh:
                    # 刪除舊資料：保留 "不等於" 該單字的行
                    existing_data = existing_data[~match_mask]
                    st.toast(f"🗑️ 已移除舊版「{new_word}」，正在寫入新版...", icon="Rg")

                # 合併新資料
                new_row = pd.DataFrame([res_data])
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                # 寫回 Google Sheets
                conn.update(spreadsheet=url, data=updated_df)
                
                st.success(f"🎉 更新完成！「{new_word}」已刷新並存入書架。")
                st.balloons()
                
                st.markdown("---")
                show_encyclopedia_card(res_data)

            except Exception as e:
                st.error(f"解碼過程出錯: {e}")
def page_home(df):
    st.markdown("<h1 style='text-align: center;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.write("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("📚 總單字量", len(df))
    c2.metric("🏷️ 分類主題", df['category'].nunique() if not df.empty else 0)
    c3.metric("🧩 獨特字根", df['roots'].nunique() if not df.empty else 0)
    st.info("👈 請從左側選單進入「解碼實驗室」擴充你的知識庫。")

def page_learn_search(df):
    st.title("📖 學習與搜尋")
    if df.empty:
        st.warning("目前書架是空的。")
        return

    tab_card, tab_list = st.tabs(["🎲 隨機探索", "🔍 資料庫列表"])
    
    with tab_card:
        cats = ["全部"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("選擇學習分類", cats)
        f_df = df if sel_cat == "全部" else df[df['category'] == sel_cat]

        if st.button("下一個單字 (Next Word) ➔", use_container_width=True, type="primary"):
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
            st.rerun()

        if 'curr_w' not in st.session_state and not f_df.empty:
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()

        if 'curr_w' in st.session_state:
            show_encyclopedia_card(st.session_state.curr_w)

    with tab_list:
        search = st.text_input("🔍 搜尋書架內容...")
        if search:
            mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
            display_df = df[mask]
        else:
            display_df = df.head(50)
        st.dataframe(display_df[['word', 'definition', 'roots', 'category', 'native_vibe']], use_container_width=True)

def page_quiz(df):
    st.title("🧠 字根記憶挑戰")
    if df.empty: return
    
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
# 5. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    
    st.sidebar.title("Kadowsella")
    page = st.sidebar.radio("功能選單", ["首頁", "學習與搜尋", "測驗模式", "🔬 AI 解碼實驗室"])
    st.sidebar.markdown("---")
    
    # 載入書架
    df = load_db()
    
    if page == "首頁":
        page_home(df)
    elif page == "學習與搜尋":
        page_learn_search(df)
    elif page == "測驗模式":
        page_quiz(df)
    elif page == "🔬 AI 解碼實驗室":
        page_ai_lab()
        
    st.sidebar.caption("v2.5 Pro 自用版")

if __name__ == "__main__":
    main()
