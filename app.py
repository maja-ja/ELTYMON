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
            
            /* 1. 拆解區塊 (漸層外框) */
            .breakdown-wrapper {
                background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
                padding: 25px 30px;
                border-radius: 15px;
                box-shadow: 0 4px 15px rgba(30, 136, 229, 0.3);
                margin: 20px 0;
                color: white !important;
            }
            
            /* 2. LaTeX 引擎修正：徹底移除黑塊、文字變白 */
            .breakdown-wrapper .katex {
                color: #FFFFFF !important;
                background: transparent !important;
                font-size: 1.15em;
            }
            .breakdown-wrapper .katex-display {
                background: transparent !important;
                margin: 1em 0;
            }

            /* 3. 強制讓內容文字與列表變白、換行 */
            .breakdown-wrapper p, .breakdown-wrapper li, .breakdown-wrapper span {
                color: white !important;
                font-weight: 700 !important;
                line-height: 1.7;
                white-space: pre-wrap !important;
            }

            /* 4. 語感與標題樣式 */
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1A237E; }
            @media (prefers-color-scheme: dark) { .hero-word { color: #90CAF9; } }
            .vibe-box { 
                background-color: #F0F7FF; padding: 20px; border-radius: 12px; 
                border-left: 6px solid #2196F3; color: #2C3E50 !important; margin: 15px 0;
            }
        </style>
    """, unsafe_allow_html=True)
# ==========================================
# 2. 工具函式
# ==========================================
# 👇 放在程式最上面的工具區
def fix_content(text):
    """
    全域字串清洗 (解決 LaTeX 與 換行失效)：
    1. 處理空值與 nan。
    2. 先處理換行，再處理 LaTeX 轉義，避免衝突。
    3. 針對 Markdown 換行需求優化。
    """
    if text is None or str(text).strip() in ["無", "nan", ""]:
        return ""
    
    # 確保是字串類型
    text = str(text)
    
    # --- 關鍵修正 1：處理換行 ---
    # AI 有時輸出 \\n 有時輸出 \n。
    # 我們統一將其轉為 Markdown 的「兩格空白 + 換行」，這樣條列式才會漂亮。
    text = text.replace('\\n', '  \n').replace('\n', '  \n')
    
    # --- 關鍵修正 2：處理 LaTeX 反斜線 ---
    # 如果資料裡有 \\frac，代表被轉義過，我們要還原成 \frac 讓 st.markdown 認得
    # 但要注意不要把已經是單反斜線的又弄壞
    if '\\\\' in text:
        text = text.replace('\\\\', '\\')
    
    # --- 關鍵修正 3：清理 JSON 解析殘留的引號 ---
    # 有時 AI 會在字串前後留下多餘的引號，這會讓 UI 看起來很躁
    text = text.strip('"').strip("'")
    
    return text
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


@st.cache_data(ttl=3600) # 每 60 秒自動更新一次，兼顧速度與即時性
def load_db():
    # 定義我們需要的 20 個標準欄位名稱
    COL_NAMES = [
        'category', 'roots', 'meaning', 'word', 'breakdown', 
        'definition', 'phonetic', 'example', 'translation', 'native_vibe',
        'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
        'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag'
    ]
    
    try:
        # 連接 Google Sheets
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        
        # 讀取數據 (ttl=0 強制不使用 st.connection 內建快取，改用我們外層的 st.cache_data)
        df = conn.read(spreadsheet=url, ttl=0)
        
        # 1. 自動補齊缺失欄位：如果試算表沒這欄，自動填入 "無"
        for col in COL_NAMES:
            if col not in df.columns:
                df[col] = "無"
        
        # 2. 資料清洗：去除單字欄位為空的無效行，並填補 NaN
        df = df.dropna(subset=['word'])
        df = df.fillna("無")
        
        # 3. 欄位排序：確保 DataFrame 順序與我們定義的一致
        return df[COL_NAMES].reset_index(drop=True)
        
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        # 失敗時回傳一個空的 DataFrame，避免主程式當掉
        return pd.DataFrame(columns=COL_NAMES)
# ==========================================
# 3. AI 解碼核心 (自用解鎖版)
# ==========================================
def ai_decode_and_save(input_text, fixed_category):
    """
    核心解碼函式：將 Prompt 直接寫入程式碼，確保執行穩定。
    """
    # 從 secrets 讀取 API Key
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 找不到 GEMINI_API_KEY，請檢查 Streamlit Secrets 設定。")
        return None

    genai.configure(api_key=api_key)
    
    # 安全設定：解除過濾
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # 定義硬編碼 Prompt
    SYSTEM_PROMPT = f"""
    Role: 全領域知識解構專家 (Polymath Decoder).
    Task: 深度分析輸入內容，並將其解構為高品質、結構化的百科知識 JSON。
    
    【領域鎖定】：你目前的身份是「{fixed_category}」專家，請務必以此專業視角進行解構、評論與推導。

    ## 處理邏輯 (Field Mapping Strategy):
    1. category: 必須固定填寫為「{fixed_category}」。
    2. word: 核心概念名稱 (標題)。
    3. roots: 底層邏輯 / 核心原理 / 關鍵公式。使用 LaTeX 格式並用 $ 包圍。
    4. meaning: 該概念解決了什麼核心痛點或其存在的本質意義。
    5. breakdown: 結構拆解。步驟流程或組成要素，逐步條列並使用 \\n 換行。
    6. definition: 用五歲小孩都能聽懂的話 (ELI5) 解釋該概念。
    7. phonetic: 關鍵年代、發明人名、或該領域的專門術語。標註正確發音與背景。若是外語詞彙，請先提供國際音標 (IPA) 或通用音譯，再針對其中的「專有名詞人名」或「關鍵術語」提供「注音+拼音」對照。
    8. example: 兩個以上最具代表性的實際應用場景。
    9. translation: 生活類比。以「🍎 生活比喻：」開頭。
    10. native_vibe: 專家視角。以「🌊 專家心法：」開頭。
    11. synonym_nuance: 相似概念對比與辨析。
    12. visual_prompt: 視覺化圖景描述。
    13. social_status: 在該領域的重要性評級。
    14. emotional_tone: 學習此知識的心理感受。
    15. street_usage: 避坑指南。常見認知誤區。
    16. collocation: 關聯圖譜。三個延伸知識點。
    17. etymon_story: 歷史脈絡或發現瞬間。
    18. usage_warning: 邊界條件與失效場景。
    19. memory_hook: 記憶金句。
    20. audio_tag: 相關標籤 (以 # 開頭)。

    ## 輸出規範 (Strict JSON Rules):
    1. 必須輸出純 JSON 格式，不含任何 Markdown 標記 (如 ```json)。
    2. 必須遵循標準 JSON 格式，所有的鍵名 (Keys) 與字串值 (Values) 必須使用雙引號 (") 包裹。若內容中需要表示引號，請一律使用中文引號「」或單引號 '，嚴禁在字串內容中使用原始的雙引號。
    3. LaTeX 公式請使用單個反斜線格式，但在 JSON 內需雙重轉義。
    4. 換行統一使用 \\\\n。
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=safety_settings)
        final_prompt = f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」"
        
        response = model.generate_content(final_prompt)
        
        if response and response.text:
            return response.text
        return None
    except Exception as e:
        st.error(f"Gemini API 錯誤: {e}")
        return None
def show_encyclopedia_card(row):
    import time

    # 1. 變數取值與清洗 (使用新的清潔劑)
    r_word = str(row.get('word', '未命名主題'))
    r_phonetic = fix_content(row.get('phonetic', "")) 
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_roots = fix_content(row.get('roots', ""))
    r_meaning = str(row.get('meaning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_trans = str(row.get('translation', ""))

    # 2. 標題展示 (Hero Word)
    # 確保只有這一行在印標題
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    
    # 3. 標題下方的描述 (三明治大法：HTML開頭 -> Markdown內容 -> HTML結尾)
    if r_phonetic and r_phonetic != "無":
        # (A) 開啟一個灰白色的容器
        st.markdown("""
            <div style='color: #E0E0E0; font-size: 0.95rem; margin-bottom: 20px; line-height: 1.6; opacity: 0.9;'>
        """, unsafe_allow_html=True)
        
        # (B) 渲染內容 (Markdown 負責把 LaTeX 變漂亮)
        st.markdown(r_phonetic)
        
        # (C) 關閉容器
        st.markdown("</div>", unsafe_allow_html=True)

    # 4. 朗讀與拆解區
    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("🔊 朗讀", key=f"spk_{r_word}_{int(time.time())}", use_container_width=True):
            speak(r_word, "card")
            
    with col_b:
    # 方案 A：直接使用 st.markdown 並確保沒有被 <div> 包裹
    st.markdown(f"#### 🧬 邏輯拆解\n{r_breakdown}")
    # 5. 雙欄核心區
    st.write("---")
    c1, c2 = st.columns(2)
    r_ex = fix_content(row.get('example', ""))
    
    # 在 c1 欄位顯示區確保正確引用
    with c1:
        st.info("### 🎯 定義與解釋")
        st.markdown(r_def) 
        st.markdown(f"**📝 應用案例 / 推導步驟：** \n{r_ex}") # 確保 r_ex 已被定義
        if r_trans and r_trans != "無":
            st.caption(f"（{r_trans}）")
        
    with c2:
        st.success("### 💡 核心原理")
        st.markdown(r_roots)
        st.write(f"**🔍 本質意義：** {r_meaning}")
        st.markdown(f"**🪝 記憶鉤子：** \n{r_hook}")

    # 6. 專家視角 (同樣使用三明治大法)
    if r_vibe:
        st.markdown("""
            <div class='vibe-box'>
                <h4 style='margin-top:0; color:#1565C0;'>🌊 專家視角 / 內行心法</h4>
        """, unsafe_allow_html=True)
        st.markdown(r_vibe)
        st.markdown("</div>", unsafe_allow_html=True)

    # 7. 深度百科 (使用 Expander 收納)
    with st.expander("🔍 深度百科 (辨析、起源、邊界條件)"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：** \n{fix_content(row.get('synonym_nuance', '無'))}")
            st.markdown(f"**🏛️ 歷史脈絡：** \n{fix_content(row.get('etymon_story', '無'))}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：** \n{fix_content(row.get('usage_warning', '無'))}")
            st.markdown(f"**🏙️ 關聯圖譜：** \n{fix_content(row.get('collocation', '無'))}")
# ==========================================
# 4. 頁面邏輯
# ==========================================
def page_ai_lab():
    st.title("🔬 Kadowsella 解碼實驗室")
    
    # 24 個精選固定領域
    FIXED_CATEGORIES = [
        "英語辭源", "語言邏輯", "物理科學", "生物醫學", "天文地質", "數學邏輯", 
        "歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "考古發現",
        "商業商戰", "金融投資", "程式開發", "人工智慧", "產品設計", "數位行銷",
        "藝術美學", "影視文學", "料理食觀", "運動健身", "流行文化", "雜類", "自定義"
    ]
    
    col_input, col_cat = st.columns([2, 1])
    with col_input:
        new_word = st.text_input("輸入解碼主題：", placeholder="例如: '二次函數頂點式'...")
    with col_cat:
        selected_category = st.selectbox("選定領域標籤", FIXED_CATEGORIES)
        
    if selected_category == "自定義":
        custom_cat = st.text_input("請輸入自定義領域名稱：")
        final_category = custom_cat if custom_cat else "未分類"
    else:
        final_category = selected_category

    force_refresh = st.checkbox("🔄 強制刷新 (覆蓋舊資料)")
    
    if st.button("啟動解碼", type="primary"):
        if not new_word:
            st.warning("請先輸入內容。")
            return

        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        existing_data = conn.read(spreadsheet=url, ttl=0)
        
        is_exist = False
        if not existing_data.empty:
            match_mask = existing_data['word'].astype(str).str.lower() == new_word.lower()
            is_exist = match_mask.any()

        if is_exist and not force_refresh:
            st.warning(f"⚠️ 「{new_word}」已在書架上。")
            show_encyclopedia_card(existing_data[match_mask].iloc[0].to_dict())
            return

        with st.spinner(f'正在以【{final_category}】視角進行三位一體解碼...'):
            raw_res = ai_decode_and_save(new_word, final_category)
            
            if raw_res is None:
                st.error("AI 無回應。")
                return

            try:
                # 1. 提取 JSON 區塊
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if not match:
                    st.error("解析失敗：找不到 JSON 結構。")
                    return
                
                json_str = match.group(0)

                # 2. [關鍵防禦] 修復潛在的非法轉義字元
                # 使用 strict=False 允許解析器處理一些不合規的控制字元
                try:
                    res_data = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    # 如果 strict=False 還是失敗，進行暴力字串修復
                    fixed_json = json_str.replace('\n', '\\n').replace('\r', '\\r')
                    res_data = json.loads(fixed_json, strict=False)

                # 3. 更新 Google Sheets
                if is_exist and force_refresh:
                    existing_data = existing_data[~match_mask]
                
                new_row = pd.DataFrame([res_data])
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                conn.update(spreadsheet=url, data=updated_df)
                st.success(f"🎉 「{new_word}」解碼完成並已存入雲端！")
                st.balloons()
                show_encyclopedia_card(res_data)

            except Exception as e:
                st.error(f"⚠️ 處理失敗: {e}")
                with st.expander("查看原始數據回報錯誤"):
                    st.code(raw_res)
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
        sample_count = min(3, len(df))
        sample = df.sample(sample_count)
        
        cols = st.columns(3)
        for i, (index, row) in enumerate(sample.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    
                    # 👇 修正截圖 3：使用 fix_content 清洗 + st.markdown 渲染
                    cleaned_def = fix_content(row['definition'])
                    cleaned_roots = fix_content(row['roots'])
                    
                    # 使用 markdown 才能正確顯示 LaTeX 公式
                    st.markdown(f"**定義：** {cleaned_def}")
                    st.markdown(f"**核心：** {cleaned_roots}")

                    if st.button("🔊", key=f"home_spk_{row['word']}"):
                        speak(row['word'], "home")

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
