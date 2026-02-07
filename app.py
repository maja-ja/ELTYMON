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
            
            /* 1. 基礎卡片樣式：在深色模式下增加陰影與邊框對比 */
            .stMainContainer {
                transition: background-color 0.3s ease;
            }

            /* 2. 標題 Hero Word：動態適應主題色 */
            .hero-word { 
                font-size: 2.8rem; 
                font-weight: 800; 
                color: #1A237E; /* 淺色模式：深藍 */
                margin-bottom: 5px;
            }
            
            /* 3. 專家視角 Vibe Box：適應深色背景 */
            .vibe-box { 
                background-color: #F0F7FF; 
                padding: 20px; 
                border-radius: 12px; 
                border-left: 6px solid #2196F3; 
                color: #2C3E50 !important; 
                margin: 15px 0;
            }

            /* --- 深色模式自動適應樣式覆蓋 --- */
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #90CAF9 !important; } /* 深色模式：粉藍 */
                
                .vibe-box {
                    background-color: #1E262E !important; /* 深色模式：深灰藍 */
                    color: #E3F2FD !important; /* 文字轉亮色 */
                    border-left: 6px solid #64B5F6 !important;
                }
                
                /* 強制修正深色模式下的表格/清單文字顏色 */
                .stMarkdown p, .stMarkdown li {
                    color: #E0E0E0 !important;
                }
            }

            /* 4. 邏輯拆解區 (漸層外框保持高對比) */
            .breakdown-wrapper {
                background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
                padding: 25px 30px;
                border-radius: 15px;
                color: white !important;
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
def track_intent(label):
    """紀錄用戶意願 (點擊次數) 到 Google Sheets 的 metrics 分頁"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        # 讀取 metrics 分頁 (建議你在 Sheet 裡先建好這一頁，欄位為 feature_name, count)
        try:
            m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
        except:
            # 如果沒這一頁，建立初始資料
            m_df = pd.DataFrame(columns=['feature_name', 'count'])
        
        if label in m_df['feature_name'].values:
            m_df.loc[m_df['feature_name'] == label, 'count'] += 1
        else:
            new_row = pd.DataFrame([{'feature_name': label, 'count': 1}])
            m_df = pd.concat([m_df, new_row], ignore_index=True)
        
        # 寫回雲端 (注意：這會更新整頁)
        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)
    except Exception as e:
        # 靜默處理，不干擾用戶
        pass
@st.cache_data(ttl=360) 
def load_db(source_type="Google Sheets"):
    # 定義標準 21 個欄位名稱
    COL_NAMES = [
        'category', 'roots', 'meaning', 'word', 'breakdown', 
        'definition', 'phonetic', 'example', 'translation', 'native_vibe',
        'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage',
        'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag',
        'term'  # <-- 補上第 21 個欄位
    ]
    
    df = pd.DataFrame(columns=COL_NAMES)

    try:
        if source_type == "Google Sheets":
            conn = st.connection("gsheets", type=GSheetsConnection)
            url = get_spreadsheet_url()
            df = conn.read(spreadsheet=url, ttl=0)
        
        elif source_type == "Local JSON":
            json_file = "master_db.json"
            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data: df = pd.DataFrame(data)
        
        # 1. 自動補齊缺失欄位
        for col in COL_NAMES:
            if col not in df.columns:
                df[col] = 0 if col == 'term' else "無"
        
        # 2. 清洗與排序
        df = df.dropna(subset=['word']).fillna("無")
        return df[COL_NAMES].reset_index(drop=True)
        
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)
def submit_report(row_data):
    """
    將單字資料一鍵寫入反饋試算表，並標記 term=1 (待修理)
    """
    try:
        # 1. 指定你的回饋表單 URL
        FEEDBACK_URL = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
        
        # 2. 建立連線 (確保 secrets.toml 已配置 GSheets 權限)
        conn_fb = st.connection("gsheets", type=GSheetsConnection)
        
        # 3. 處理資料：複製該列並強制設定 term=1
        # row_data 如果是從 page_home 傳進來的 row.to_dict()
        report_row = row_data.copy()
        report_row['term'] = 1  # 標記為待修理
        
        # 4. 讀取現有資料進行合併 (Append 邏輯)
        # ttl=0 確保每次按按鈕都是讀取最新狀態，避免寫入衝突
        existing_fb = conn_fb.read(spreadsheet=FEEDBACK_URL, ttl=0)
        
        # 5. 轉換為 DataFrame 並確保欄位順序正確
        report_df = pd.DataFrame([report_row])
        
        # 6. 合併新舊資料
        updated_fb = pd.concat([existing_fb, report_df], ignore_index=True)
        
        # 7. 寫回 Google Sheets
        conn_fb.update(spreadsheet=FEEDBACK_URL, data=updated_fb)
        
        # 8. 顯示輕量化提示 (Toast) 
        # 這不會像 st.success 佔用頁面空間，也不會強制阻斷使用者操作
        st.toast(f"✅ 已成功將「{row_data.get('word', '該單字')}」記錄至待修清單", icon="🛠️")
        
        return True
        
    except Exception as e:
        st.error(f"❌ 回報寫入失敗: {e}")
        return False
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
    # 變數定義與清洗
    r_word = str(row.get('word', '未命名主題'))
    r_roots = fix_content(row.get('roots', "")).replace('$', '$$')
    r_phonetic = fix_content(row.get('phonetic', "")) 
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_meaning = str(row.get('meaning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_trans = str(row.get('translation', ""))

    # 1. 標題區 (會隨系統主題變色)
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    
    if r_phonetic and r_phonetic != "無":
        st.caption(f"/{r_phonetic}/")

    # 2. 邏輯拆解 (深色底漸層)
    st.markdown(f"""
        <div class='breakdown-wrapper'>
            <h4 style='color: white; margin-top: 0;'>🧬 邏輯拆解</h4>
            <div style='color: white; font-weight: 700;'>{r_breakdown}</div>
        </div>
    """, unsafe_allow_html=True)

    st.write("---")
    
    # 3. 核心內容區 (st.info/success 會自動處理深淺色)
    c1, c2 = st.columns(2)
    r_ex = fix_content(row.get('example', ""))
    
    with c1:
        st.info("### 🎯 定義與解釋")
        st.write(r_def) 
        st.caption(f"📝 {r_ex}")
        if r_trans and r_trans != "無":
            st.caption(f"（{r_trans}）")
        
    with c2:
        st.success("### 💡 核心原理")
        st.write(r_roots)
        st.write(f"**🔍 本質意義：** {r_meaning}")
        st.write(f"**🪝 記憶鉤子：** {r_hook}")

    # 4. 專家視角 (配合 CSS 變數自動變色)
    if r_vibe:
        st.markdown(f"""
            <div class='vibe-box'>
                <h4 style='margin-top:0;'>🌊 專家視角 / 內行心法</h4>
                {r_vibe}
            </div>
        """, unsafe_allow_html=True)

    # 5. 深度百科
    with st.expander("🔍 深度百科 (辨析、起源、邊界條件)"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：** \n{fix_content(row.get('synonym_nuance', '無'))}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：** \n{fix_content(row.get('usage_warning', '無'))}")

    # --- [關鍵修正：變數名稱統一為 rep_col] ---
    st.write("---")
    rep_col1, rep_col2 = st.columns([3, 1])
    
    with rep_col1:
        st.caption("發現解析有誤？點擊按鈕一鍵送入修復清單。")
        
    with rep_col2:
        # 使用唯一 key 以免在隨機探索時發生元件 ID 衝突
        if st.button("🚩 有誤", key=f"rep_card_{r_word}", use_container_width=True):
            submit_report(row.to_dict() if hasattr(row, 'to_dict') else row)
# 4. 頁面邏輯
# ==========================================

def page_ai_lab():
    st.title("🔬 Kadowsella 解碼實驗室")
    
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
                # 1. 提取 JSON
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if not match:
                    st.error("解析失敗：找不到 JSON 結構。")
                    return
                
                json_str = match.group(0)

                # 2. 解析 JSON
                try:
                    res_data = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    fixed_json = json_str.replace('\n', '\\n').replace('\r', '\\r')
                    res_data = json.loads(fixed_json, strict=False)

                # 3. 寫回資料庫
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
def log_user_intent(label):
    """將用戶點擊意願寫入 Google Sheets 的 metrics 分頁"""
    try:
        # 1. 建立連線
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        
        # 2. 嘗試讀取名為 'metrics' 的工作表
        try:
            # ttl=0 確保我們拿到的是最即時的計數
            m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
        except Exception:
            # 如果找不到 metrics 工作表，就建立一個初始的 DataFrame
            m_df = pd.DataFrame(columns=['label', 'count'])
        
        # 3. 更新計數邏輯
        if label in m_df['label'].values:
            # 如果這個標籤（如 click_coffee）已存在，次數 +1
            m_df.loc[m_df['label'] == label, 'count'] = m_df.loc[m_df['label'] == label, 'count'].astype(int) + 1
        else:
            # 如果是第一次點擊，新增一行紀錄
            new_record = pd.DataFrame([{'label': label, 'count': 1}])
            m_df = pd.concat([m_df, new_record], ignore_index=True)
        
        # 4. 寫回雲端 (覆蓋 metrics 分頁)
        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)
        
    except Exception as e:
        # 為了不干擾用戶體驗，後台紀錄失敗時我們靜默處理
        # 測試時可以把下面這行註解拿掉來除錯
        # st.write(f"DEBUG: Metrics Error - {e}")
        pass
def page_home(df):
    st.markdown("<h1 style='text-align: center;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.write("---")
    
    # 1. 數據儀表板 (Dashboard)
    c1, c2, c3 = st.columns(3)
    c1.metric("📚 總單字量", len(df))
    c2.metric("🏷️ 分類主題", df['category'].nunique() if not df.empty else 0)
    c3.metric("🧩 獨特字根", df['roots'].nunique() if not df.empty else 0)
    
    st.write("---")

    # 2. 隨機推薦區標頭
    col_header, col_btn = st.columns([4, 1])
    with col_header:
        st.subheader("💡 今日隨機推薦")
    with col_btn:
        # 當點擊「換一批」時，清除 Session State 讓它重新抽樣
        if st.button("🔄 換一批", use_container_width=True):
            if 'home_sample' in st.session_state:
                del st.session_state.home_sample
            st.rerun()
    
    # --- 關鍵修正：鎖定隨機抽樣的結果 ---
    if not df.empty:
        # 如果 Session State 裡還沒有抽樣結果，則進行抽樣並鎖定
        if 'home_sample' not in st.session_state:
            sample_count = min(3, len(df))
            st.session_state.home_sample = df.sample(sample_count)
        
        # 從 Session State 讀取單字，確保按下「🚩 有誤」刷新後單字不變
        sample = st.session_state.home_sample
        
        cols = st.columns(3)
        for i, (index, row) in enumerate(sample.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    # 標題與分類
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    
                    # 內容清洗
                    cleaned_def = fix_content(row['definition'])
                    cleaned_roots = fix_content(row['roots'])
                    
                    st.markdown(f"**定義：** {cleaned_def}")
                    st.markdown(f"**核心：** {cleaned_roots}")

                    # --- [功能按鈕佈局] ---
                    btn_col_a, btn_col_b = st.columns([1, 1])
                    
                    with btn_col_a:
                        speak(row['word'], key_suffix=f"home_{i}")
                    
                    with btn_col_b:
                        # 點擊「🚩 有誤」會觸發 submit_report 寫入 feedback 試算表
                        # 加入 term=1 的邏輯已封裝在 submit_report 內
                        if st.button("🚩 有誤", key=f"rep_home_{i}_{row['word']}", use_container_width=True):
                            # 呼叫回報函式
                            submit_report(row.to_dict())

    st.write("---")
    st.info("👈 點擊左側選單進入「學習與搜尋」查看完整資料庫。")
def page_learn_search(df):
    st.title("📖 學習與搜尋")
    if df.empty:
        st.warning("目前書架是空的。")
        return

    tab_card, tab_list = st.tabs(["🎲 隨機探索", "🔍 搜尋與列表"])
    
    # --- Tab 1: 隨機探索 (保持原樣) ---
    with tab_card:
        cats = ["全部"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("選擇學習分類", cats, key="learn_cat_select")
        f_df = df if sel_cat == "全部" else df[df['category'] == sel_cat]

        if 'curr_w' not in st.session_state:
            st.session_state.curr_w = None

        if st.button("🎲 隨機探索下一字 (Next Word)", use_container_width=True, type="primary"):
            if not f_df.empty:
                st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
                st.rerun()

        if st.session_state.curr_w is None and not f_df.empty:
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()

        if st.session_state.curr_w:
            show_encyclopedia_card(st.session_state.curr_w)

    # --- Tab 2: 搜尋與列表 (這是我們要修改的地方) ---
    with tab_list:
        search = st.text_input("🔍 搜尋書架內容...", placeholder="輸入關鍵字（單字、定義或字根）...")
        
        if search:
            # 執行搜尋過濾
            mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
            display_df = df[mask]
            
            if not display_df.empty:
                st.info(f"💡 找到 {len(display_df)} 筆相關資料：")
                
                # 遍歷搜尋結果，呼叫你寫好的字卡函式
                for index, row in display_df.iterrows():
                    # 使用 st.container(border=True) 讓多張字卡排隊時有明顯邊界
                    with st.container(border=True):
                        show_encyclopedia_card(row)
                    st.write(" ") # 增加一些垂直間距
            else:
                st.warning("查無資料，請嘗試其他關鍵字。")
        else:
            # 當使用者還沒輸入搜尋內容時，顯示簡要表格方便快速瀏覽
            st.caption("請在上方輸入框輸入關鍵字以查看詳細字卡，或參考下方目錄：")
            st.dataframe(
                df[['word', 'definition', 'category', 'roots']], 
                use_container_width=True, 
                hide_index=True
            )
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
    
    # --- [贊助區塊：視覺複刻與意願追蹤] ---
    with st.sidebar:
        # 渲染外框與標題
        st.markdown('<div class="sponsor-box"><span class="sponsor-title">💖 支持開發者</span></div>', unsafe_allow_html=True)
        
        # 咖啡按鈕 (由 CSS 著色)
        if st.button("☕ Buy Me a Coffee", key="btn_coffee"):
            if 'log_user_intent' in globals():
                log_user_intent("click_coffee")
            st.info("### 🚧 帳號系統準備中，將開放贊助，感謝您的支持！")
            st.balloons()

        # 米糕按鈕 (由 CSS 著色)
        if st.button("贊助一碗米糕！", key="btn_rice"):
            if 'log_user_intent' in globals():
                log_user_intent("click_ricecake")
            st.success("### 🏗️ 帳號系統準備中，將開放贊助，感謝您的支持！")
            
        st.markdown("---")
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
