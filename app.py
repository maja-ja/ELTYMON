import os
import streamlit as st
import pandas as pd
import base64
import time
import json
import re  # 用於精準提取 JSON 和文字清洗
from io import BytesIO
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置與視覺美化 (CSS)
# ==========================================
st.set_page_config(page_title="Etymon Decoder v3.0", page_icon="🧩", layout="wide")

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
    if '\\\\' in text:
        text = text.replace('\\\\', '\\')
    
    # --- 關鍵修正 3：清理 JSON 解析殘留的引號 ---
    text = text.strip('"').strip("'")
    
    return text

def speak(text, key_suffix=""):
    if not text: return
    
    # 1. 英語濾網
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    english_only = " ".join(english_only.split()).strip()
    if not english_only: return

    try:
        # 2. 用 Google 轉出高品質 MP3
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        
        # 3. 把 MP3 變成一串文字 (Base64)，直接塞進 HTML 裡
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"

        # 4. 建立一個獨立的 HTML 按鈕組件
        # 這裡面包含完整的 MP3 資料，不依賴外部連結，點擊瞬間直接播放
        html_code = f"""
        <html>
        <style>
            .btn {{
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 5px 10px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 5px;
                font-family: sans-serif;
                font-size: 14px;
                color: #333;
                transition: 0.2s;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .btn:hover {{
                background: #f8f9fa;
                border-color: #ccc;
            }}
            .btn:active {{
                background: #eef;
                transform: scale(0.98);
            }}
        </style>
        <body>
            <button class="btn" onclick="playAudio()">
                🔊 聽發音
            </button>
            
            <audio id="{unique_id}" style="display:none">
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            </audio>

            <script>
                function playAudio() {{
                    var audio = document.getElementById("{unique_id}");
                    audio.currentTime = 0; // 每次點擊都從頭播放
                    audio.play().catch(e => console.log(e));
                }}
            </script>
        </body>
        </html>
        """
        
        # 5. 渲染這個獨立組件 (設定高度避免留白太大)
        st.components.v1.html(html_code, height=40)
        
    except Exception as e:
        st.error(f"語音生成失敗: {e}")

def get_spreadsheet_url():
    """安全地獲取試算表網址，相容兩種 secrets 格式"""
    try:
        return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except:
        try:
            return st.secrets["gsheets"]["spreadsheet"]
        except:
            st.error("找不到 spreadsheet 設定，請檢查 secrets.toml")
            return ""

@st.cache_data(ttl=3600) # 改為 0，確保切換時不快取舊資料
def load_db(source_type="Google Sheets"):
    # 定義標準欄位
    COL_NAMES = [
        'category', 'roots', 'meaning', 'word', 'breakdown', 
        'definition', 'phonetic', 'example', 'translation', 'native_vibe',
        'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
        'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag'
    ]
    
    df = pd.DataFrame(columns=COL_NAMES)

    try:
        if source_type == "Google Sheets":
            # --- 模式 A: Google Sheets ---
            conn = st.connection("gsheets", type=GSheetsConnection)
            url = get_spreadsheet_url()
            df = conn.read(spreadsheet=url, ttl=0)
        
        elif source_type == "Local JSON":
            # --- 模式 B: Local JSON (master_db.json) ---
            json_file = "master_db.json"
            if os.path.exists(json_file):
                # 如果檔案存在，讀取並轉為 DataFrame
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:
                    df = pd.DataFrame(data)
            else:
                # 如果檔案不存在，建立一個空的並提示
                st.toast("⚠️ 尚未建立 master_db.json，將自動建立新檔。", icon="📂")
                df = pd.DataFrame(columns=COL_NAMES)

        # --- 通用資料清洗 (確保欄位齊全) ---
        # 1. 自動補齊缺失欄位
        for col in COL_NAMES:
            if col not in df.columns:
                df[col] = "無"
        
        # 2. 移除空值與字串轉換
        df = df.dropna(subset=['word'])
        df = df.fillna("無")
        
        # 3. 確保只回傳標準欄位
        return df[COL_NAMES].reset_index(drop=True)
        
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗 ({source_type}): {e}")
        return pd.DataFrame(columns=COL_NAMES)
# ==========================================
# 3. AI 解碼核心 (還原中文 Prompt)
# ==========================================
def ai_decode_and_save(input_text, fixed_category):
    """
    核心解碼函式：將 Prompt 直接寫入程式碼，確保執行穩定。
    """
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 找不到 GEMINI_API_KEY，請檢查 Streamlit Secrets 設定。")
        return None

    genai.configure(api_key=api_key)
    
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # 還原原本的中文 Prompt
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
    # 1. 變數取值與清洗
    r_word = str(row.get('word', '未命名主題'))
    r_roots = fix_content(row.get('roots', "")).replace('$', '$$')
    r_phonetic = fix_content(row.get('phonetic', "")) 
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_meaning = str(row.get('meaning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_trans = str(row.get('translation', ""))

    # 2. 標題展示 (Hero Word)
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    
    # 3. 標題下方的描述
    if r_phonetic and r_phonetic != "無":
        st.markdown(f"""
            <div style='color: #E0E0E0; font-size: 0.95rem; margin-bottom: 20px; line-height: 1.6; opacity: 0.9;'>
            {r_phonetic}
            </div>
        """, unsafe_allow_html=True)

    # 4. 朗讀與拆解區 (整合修正版 speak)
    col_a, col_b = st.columns([1, 4])
    with col_a:
        st.caption("🔊 點擊播放")
        # 這裡直接呼叫 speak，會在介面上顯示一個播放器
        speak(r_word, key_suffix="card_main")
            
    with col_b:
        st.markdown(f"#### 🧬 邏輯拆解\n{r_breakdown}")

    # 5. 雙欄核心區
    st.write("---")
    c1, c2 = st.columns(2)
    r_ex = fix_content(row.get('example', ""))
    
    with c1:
        st.info("### 🎯 定義與解釋")
        st.markdown(r_def) 
        st.markdown(f"**📝 應用案例 / 推導步驟：** \n{r_ex}")
        if r_trans and r_trans != "無":
            st.caption(f"（{r_trans}）")
        
    with c2:
        st.success("### 💡 核心原理")
        st.markdown(r_roots)
        st.write(f"**🔍 本質意義：** {r_meaning}")
        st.markdown(f"**🪝 記憶鉤子：** \n{r_hook}")

    # 6. 專家視角
    if r_vibe:
        st.markdown("""
            <div class='vibe-box'>
                <h4 style='margin-top:0; color:#1565C0;'>🌊 專家視角 / 內行心法</h4>
        """, unsafe_allow_html=True)
        st.markdown(r_vibe)
        st.markdown("</div>", unsafe_allow_html=True)

    # 7. 深度百科
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

def page_ai_lab(source_type):
    st.title(f"🔬 Kadowsella 解碼實驗室 ({source_type})")
    
    # 定義領域分類
    FIXED_CATEGORIES = [
        "英語辭源", "語言邏輯", "物理科學", "生物醫學", "天文地質", "數學邏輯", 
        "歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "考古發現",
        "商業商戰", "金融投資", "程式開發", "人工智慧", "產品設計", "數位行銷",
        "藝術美學", "影視文學", "料理食觀", "運動健身", "流行文化", "雜類", "自定義"
    ]
    
    # 輸入介面
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
    
    # 執行按鈕
    if st.button("啟動解碼", type="primary"):
        if not new_word:
            st.warning("請先輸入內容。")
            return

        # 1. 讀取當前資料庫 (根據傳入的來源類型)
        #    這一步很重要，確保我們是在比對正確的資料庫是否有重複
        existing_data = load_db(source_type)
        
        # 檢查是否已存在
        is_exist = False
        if not existing_data.empty:
            match_mask = existing_data['word'].astype(str).str.lower() == new_word.lower()
            is_exist = match_mask.any()

        # 若存在且不強制刷新，則直接顯示舊資料
        if is_exist and not force_refresh:
            st.warning(f"⚠️ 「{new_word}」已在 {source_type} 書架上。")
            show_encyclopedia_card(existing_data[match_mask].iloc[0].to_dict())
            return

        # 2. 呼叫 AI 進行解碼
        with st.spinner(f'正在以【{final_category}】視角進行三位一體解碼...'):
            raw_res = ai_decode_and_save(new_word, final_category)
            
            if raw_res is None:
                st.error("AI 無回應，請稍後再試。")
                return

            try:
                # 3. 解析 AI 回傳的 JSON
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if not match:
                    st.error("解析失敗：找不到 JSON 結構。")
                    return
                
                json_str = match.group(0)
                try:
                    res_data = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    # 嘗試修復常見的換行符號錯誤
                    fixed_json = json_str.replace('\n', '\\n').replace('\r', '\\r')
                    res_data = json.loads(fixed_json, strict=False)

                # 4. 準備存檔數據
                # 如果是更新模式，先移除舊的那一筆
                if is_exist and force_refresh:
                    existing_data = existing_data[match_mask]
                
                new_row = pd.DataFrame([res_data])
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                # --- [關鍵修改] 根據 source_type 決定存檔方式 ---
                if source_type == "Google Sheets":
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    url = get_spreadsheet_url()
                    conn.update(spreadsheet=url, data=updated_df)
                    st.success(f"🎉 已將「{new_word}」寫入 Google Sheets！")
                
                elif source_type == "Local JSON":
                    json_file = "master_db.json"
                    # 將 DataFrame 轉為 JSON 格式並寫入本地檔案
                    # orient='records' 會轉成 List of Dicts 格式，最適合 JSON 資料庫
                    updated_df.to_json(json_file, orient='records', force_ascii=False, indent=4)
                    st.success(f"🎉 已將「{new_word}」寫入本地 master_db.json！")
                
                # 5. 成功後的反饋
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

    # 2. [新增功能] 隨機推薦區 + 換一批按鈕
    col_header, col_btn = st.columns([4, 1])
    with col_header:
        st.subheader("💡 今日隨機推薦")
    with col_btn:
        # 👇 這裡就是你要的新增隨機按鈕
        if st.button("🔄 換一批", use_container_width=True):
            st.rerun() # 點擊後重新執行頁面，就會重新隨機抽樣
    
    if not df.empty:
        # 這裡的邏輯：每次頁面執行時 (包含點擊按鈕)，都會重新 sample
        sample_count = min(3, len(df))
        sample = df.sample(sample_count)
        
        cols = st.columns(3)
        for i, (index, row) in enumerate(sample.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    # 標題
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    
                    # 內容清洗與顯示
                    cleaned_def = fix_content(row['definition'])
                    cleaned_roots = fix_content(row['roots'])
                    
                    st.markdown(f"**定義：** {cleaned_def}")
                    st.markdown(f"**核心：** {cleaned_roots}")

                    # 發音按鈕 (使用 unique key 避免衝突)
                    speak(row['word'], key_suffix=f"home_{i}_{int(time.time())}")

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

        # --- [關鍵修正] Session State 鎖定邏輯 ---
        # 1. 初始化 State
        if 'curr_w' not in st.session_state:
            st.session_state.curr_w = None

        # 2. 只有按鈕點擊時才更新 State (換題)
        if st.button("🎲 隨機探索下一字 (Next Word)", use_container_width=True, type="primary"):
            if not f_df.empty:
                st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
                st.rerun() # 強制刷新以顯示新卡片
            else:
                st.warning("此分類目前沒有資料。")

        # 3. 初始載入 (如果原本是空的)
        if st.session_state.curr_w is None and not f_df.empty:
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()

        # 4. 顯示卡片 (speak 函式已內建在 show_encyclopedia_card 中)
        if st.session_state.curr_w:
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
    
    # 初始化測驗 State
    if 'q' not in st.session_state:
        st.session_state.q = None
    if 'show_ans' not in st.session_state:
        st.session_state.show_ans = False

    # 按鈕只更新題目
    if st.button("🎲 抽一題", use_container_width=True):
        st.session_state.q = pool.sample(1).iloc[0].to_dict()
        st.session_state.show_ans = False
        st.rerun()

    if st.session_state.q:
        st.markdown(f"### ❓ 請問這對應哪個單字？")
        st.info(st.session_state.q['definition'])
        st.write(f"**提示 (字根):** {st.session_state.q['roots']} ({st.session_state.q['meaning']})")
        
        if st.button("揭曉答案"):
            st.session_state.show_ans = True
            st.rerun()
        
        if st.session_state.show_ans:
            st.success(f"💡 答案是：**{st.session_state.q['word']}**")
            # 顯示原生播放器
            speak(st.session_state.q['word'], "quiz")
            st.write(f"結構拆解：`{st.session_state.q['breakdown']}`")

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    
    st.sidebar.title("Kadowsella")
    
    # --- [資料來源切換] (新增功能) ---
    st.sidebar.markdown("### 💾 資料庫設定")
    source_type = st.sidebar.selectbox(
        "選擇資料來源",
        ["Google Sheets", "Local JSON"],
        index=0, # 預設使用 Google Sheets
        help="切換讀取雲端試算表或本地 JSON 檔案"
    )
    
    if source_type == "Local JSON":
        st.sidebar.caption("📂 讀寫目標：master_db.json")
    else:
        st.sidebar.caption("☁️ 讀寫目標：Google Sheets")

    st.sidebar.markdown("---")

    # --- [贊助與其他區塊保持不變] ---
    # ... (保留原本的贊助區塊) ...

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
    
    # 關鍵修改：將 source_type 傳入 load_db
    df = load_db(source_type)
    
    if page == "首頁":
        page_home(df)
    elif page == "學習與搜尋":
        page_learn_search(df)
    elif page == "測驗模式":
        page_quiz(df)
    elif page == "🔬 解碼實驗室":
        if is_admin:
            # 關鍵修改：將 source_type 傳入，讓實驗室知道存到哪
            page_ai_lab(source_type)
        else:
            st.error("⛔ 請先登入")

    status = "🔴 管理員" if is_admin else "🟢 訪客"
    st.sidebar.caption(f"v3.1 Dual-DB | {status}")
if __name__ == "__main__":
    main()