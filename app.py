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
        
        # --- [新增] 英語濾網 ---
        # 只保留 A-Z, a-z, 0-9, 空格,連字號(-), 撇號(')
        # 這樣 "Quantum Mechanics (量子力學)" 變成 "Quantum Mechanics"
        # 而 "黑洞" 變成 "" (空字串)，就不會發出怪聲
        english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", "", str(text)).strip()
        
        # 如果濾完沒東西（代表全是中文），就直接跳出，不播放
        if not english_only:
            return
            
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time())}_{key_suffix}"
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
def ai_decode_and_save(input_text, fixed_category):
    """
    進化版解碼函式：
    1. 接收使用者選定的固定領域 (fixed_category)。
    2. 注入強制指令，鎖定 AI 的專業視角。
    3. 執行 JSON 提取與安全過濾。
    """
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
    
    try:
        base_prompt = st.secrets["SYSTEM_PROMPT"]
    except KeyError:
        st.error("❌ 密碼箱中找不到 SYSTEM_PROMPT")
        return None
    
    # --- 關鍵修正：注入領域鎖定指令 ---
    lock_instruction = f"""
    【領域鎖定指令】：
    1. 你目前的身份是「{fixed_category}」專家。
    2. JSON 中的 'category' 欄位必須精確填寫為：「{fixed_category}」。
    3. 請務必從「{fixed_category}」的專業知識體系出發，提供深度的解構內容。
    """
    
    final_prompt = f"{base_prompt}\n\n{lock_instruction}\n\n解碼目標：「{input_text}」"
    
    try:
        response = model.generate_content(final_prompt)
        raw_text = response.text
        
        # 提取 JSON 部分
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return match.group(0)
        return raw_text
            
    except Exception as e:
        st.error(f"AI 生成出錯: {e}")
        return None
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
    
    # 1. 定義固定領域清單
    FIXED_CATEGORIES = [
        "英語辭源", "語言邏輯", "物理科學", "生物醫學", "天文地質", "數學邏輯", 
        "歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "考古發現",
        "商業商戰", "金融投資", "程式開發", "人工智慧", "產品設計", "數位行銷",
        "藝術美學", "影視文學", "料理食觀", "運動健身", "流行文化", "雜類", "自定義"
    ]
    
    col_input, col_cat = st.columns([2, 1])
    
    with col_input:
        new_word = st.text_input("輸入解碼主題：", placeholder="例如: 'Entropy'...")
        
    with col_cat:
        selected_category = st.selectbox("選定領域標籤", FIXED_CATEGORIES)
        
    # 處理自定義領域邏輯
    if selected_category == "自定義":
        custom_cat = st.text_input("請輸入自定義領域名稱：")
        final_category = custom_cat if custom_cat else "未分類"
    else:
        final_category = selected_category

    force_refresh = st.checkbox("🔄 強制刷新 (覆蓋舊資料)")
    
    if st.button("啟動三位一體解碼", type="primary"):
        if not new_word:
            st.warning("請先輸入內容。")
            return

        # --- 步驟 1: 檢查資料庫 ---
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        existing_data = conn.read(spreadsheet=url, ttl=0)
        
        is_exist = False
        if not existing_data.empty:
            match_mask = existing_data['word'].astype(str).str.lower() == new_word.lower()
            is_exist = match_mask.any()

        if is_exist and not force_refresh:
            st.warning(f"⚠️ 「{new_word}」已在書架上！")
            existing_row = existing_data[match_mask].iloc[0].to_dict()
            st.markdown("---")
            show_encyclopedia_card(existing_row)
            return

        # --- 步驟 2: AI 生成 (關鍵修正：傳入 final_category) ---
        with st.spinner(f'正在以【{final_category}】專業視角解碼「{new_word}」...'):
            try:
                # 這裡呼叫我們優化過的函式
                raw_res = ai_decode_and_save(new_word, final_category)
                
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if not match:
                    st.error("AI 輸出解析失敗。")
                    return
                
                res_data = json.loads(match.group(0))

                # --- 步驟 3: 資料覆寫與存檔 ---
                if is_exist and force_refresh:
                    existing_data = existing_data[~match_mask]
                    st.toast(f"🗑️ 已替換舊版數據", icon="🔄")

                new_row = pd.DataFrame([res_data])
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                conn.update(spreadsheet=url, data=updated_df)
                
                st.success(f"🎉 「{new_word}」解碼成功！")
                st.balloons()
                st.markdown("---")
                show_encyclopedia_card(res_data)

            except Exception as e:
                st.error(f"解碼過程出錯: {e}")
def page_home(df):
    st.markdown("<h1 style='text-align: center;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.write("---")
    
    # 1. 數據儀表板
    c1, c2, c3 = st.columns(3)
    c1.metric("📚 總單字量", len(df))
    c2.metric("🏷️ 分類主題", df['category'].nunique() if not df.empty else 0)
    c3.metric("🧩 獨特字根", df['roots'].nunique() if not df.empty else 0)
    
    st.write("---")

    # 2. [新增] 隨機推薦展示區
    st.subheader("💡 今日隨機推薦")
    
    if not df.empty:
        # 如果資料庫少於 3 筆，就全秀；否則隨機抽 3 筆
        sample_count = min(3, len(df))
        #每次重新整理頁面都會變動
        sample = df.sample(sample_count) 
        
        # 使用 3 個欄位並排顯示，看起來更像卡片
        cols = st.columns(3)
        for i, (index, row) in enumerate(sample.iterrows()):
            with cols[i % 3]: # 確保在 3 欄內循環
                with st.container(border=True): # 加個邊框更有質感
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    st.write(f"**定義：** {row['definition']}")
                    st.write(f"**核心：** {row['roots']}")
                    # 這裡可以加一個小按鈕，點了朗讀該單字
                    if st.button("🔊", key=f"home_spk_{row['word']}"):
                        speak(row['word'], "home")
    else:
        st.info("👈 資料庫目前是空的，請從左側進入「解碼實驗室」新增第一筆知識！")

    st.write("---")
    st.info("👈 點擊左側選單進入「學習與搜尋」查看完整資料庫。")

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
    
    # --- [贊助區塊] 雙刀流 ---
    st.sidebar.markdown("""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 12px; border: 1px solid #e9ecef; margin-bottom: 25px;">
            <p style="text-align: center; margin-bottom: 12px; font-weight: bold; color: #444;">💖 支持開發者</p>
            <a href="https://www.buymeacoffee.com/kadowsella" target="_blank" style="text-decoration: none;">
                <div style="background-color: #FFDD00; color: #000; padding: 8px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 8px; font-size: 0.9rem;">
                    ☕ Buy Me a Coffee
                </div>
            </a>
            <a href="https://p.ecpay.com.tw/kadowsella20" target="_blank" style="text-decoration: none;">
                <div style="background: linear-gradient(90deg, #28C76F 0%, #81FBB8 100%); color: white; padding: 8px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 0.9rem;">
                    贊助一碗米糕！
                </div>
            </a>
        </div>
    """, unsafe_allow_html=True)
    
    # --- [管理員登入] ---
    is_admin = False
    with st.sidebar.expander("🔐 管理員登入", expanded=False):
        input_pass = st.text_input("輸入密碼", type="password")
        if input_pass == st.secrets.get("ADMIN_PASSWORD", "0000"):
            is_admin = True
            st.success("🔓 上帝模式啟動")

    # --- [選單邏輯] ---
    if is_admin:
        menu_options = ["首頁", "學習與搜尋", "測驗模式", "🔬 解碼實驗室"]
        if st.sidebar.button("🔄 強制同步雲端", help="清除 App 快取"):
            st.cache_data.clear()
            st.rerun()
    else:
        menu_options = ["首頁", "學習與搜尋", "測驗模式"]
    
    page = st.sidebar.radio("功能選單", menu_options)
    st.sidebar.markdown("---")
    
    df = load_db()
    
    if page == "首頁":
        page_home(df)
    elif page == "學習與搜尋":
        page_learn_search(df)
    elif page == "測驗模式":
        page_quiz(df)
    elif page == "🔬 解碼實驗室":
        if is_admin:
            page_ai_lab()
        else:
            st.error("⛔ 請先登入")

    status = "🔴 管理員" if is_admin else "🟢 訪客"
    st.sidebar.caption(f"v3.0 Ultimate | {status}")

if __name__ == "__main__":
    main()
