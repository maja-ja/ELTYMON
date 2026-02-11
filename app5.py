import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
import os
from io import BytesIO
from PIL import Image, ImageOps
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown
# ==========================================
# 0. 用戶系統核心工具 (移植自 Kadowsella)
# ==========================================
def hash_password(password): 
    import hashlib
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_user_db():
    """讀取用戶資料表"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        # 確保必要欄位存在
        cols = ['username', 'password', 'role', 'membership', 'ai_usage', 'is_online', 'last_seen']
        for col in cols:
            if col not in df.columns: 
                df[col] = "free" if col=="membership" else (0 if col=="ai_usage" else "無")
        return df.fillna("無")
    except: 
        return pd.DataFrame(columns=['username', 'password', 'role', 'membership', 'ai_usage', 'is_online', 'last_seen'])

def save_user_to_db(new_data):
    """註冊新用戶"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        new_data['created_at'] = time.strftime("%Y-%m-%d")
        updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(worksheet="users", data=updated_df)
        return True
    except: return False

def update_user_status(username, column, value):
    """更新用戶特定狀態 (如在線時間、餘額)"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        df.loc[df['username'] == username, column] = value
        conn.update(worksheet="users", data=df)
    except: pass
# ==========================================
# 2. 登入頁面 UI (移植自 Kadowsella)
# ==========================================
def login_page():
    st.markdown("""
        <style>
            .login-header { text-align: center; padding: 20px; }
            .stTabs [data-baseweb="tab-list"] { justify-content: center; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='login-header'><h1>🏫 AI 教育工作站</h1><p>Etymon Decoder + Handout Pro 整合版</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2 = st.tabs(["🔑 帳號登入", "📝 新生註冊"])
        
        with tab1:
            with st.form("login_form"):
                u = st.text_input("帳號")
                p = st.text_input("密碼", type="password")
                submit = st.form_submit_button("進入戰情室", use_container_width=True)
                if submit:
                    users = load_user_db()
                    hashed_p = hash_password(p)
                    user = users[(users['username'] == u) & (users['password'] == hashed_p)]
                    if not user.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.session_state.role = user.iloc[0]['role']
                        st.session_state.user_balance = 100 # 模擬初始餘額
                        update_user_status(u, "is_online", "TRUE")
                        st.rerun()
                    else:
                        st.error("❌ 帳號或密碼錯誤")
        
        with tab2:
            with st.form("register_form"):
                nu = st.text_input("設定帳號")
                np = st.text_input("設定密碼", type="password")
                code = st.text_input("邀請碼 (選填)", type="password")
                reg_submit = st.form_submit_button("完成註冊", use_container_width=True)
                if reg_submit:
                    if not nu or not np:
                        st.warning("請填寫帳號密碼")
                    else:
                        is_admin = (code == st.secrets.get("ADMIN_PASSWORD", "0000"))
                        user_data = {
                            "username": nu, 
                            "password": hash_password(np), 
                            "role": "admin" if is_admin else "student",
                            "membership": "pro" if is_admin else "free",
                            "ai_usage": 0, "is_online": "FALSE"
                        }
                        if save_user_to_db(user_data):
                            st.success("✅ 註冊成功！請切換至登入分頁。")
                        else:
                            st.error("註冊失敗，請聯繫管理員")

        st.markdown("---")
        st.write("🚀 **想先看看內容？**")
        if st.button("🚪 以訪客身分試用", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.session_state.user_balance = 20 # 訪客給較少餘額
            st.rerun()
# ==========================================
# 1. 核心配置與視覺美化 (CSS)
# ==========================================
st.set_page_config(page_title="AI 教育工作站 (Etymon + Handout)", page_icon="🏫", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Noto+Sans+TC:wght@500;700&display=swap');
            
            /* --- 全域樣式 --- */
            .stMainContainer { transition: background-color 0.3s ease; }

            /* --- Etymon Decoder 樣式 (v3.0 保留) --- */
            .hero-word { 
                font-size: 2.8rem; font-weight: 800; color: #1A237E; margin-bottom: 5px;
            }
            .vibe-box { 
                background-color: #F0F7FF; padding: 20px; border-radius: 12px; 
                border-left: 6px solid #2196F3; color: #2C3E50 !important; margin: 15px 0;
            }
            .breakdown-wrapper {
                background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
                padding: 25px 30px; border-radius: 15px; color: white !important;
            }
            
            /* --- Handout Pro 樣式 (Code 1 新增) --- */
            .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
            .info-card { background-color: #f0f9ff; border-left: 5px solid #0ea5e9; padding: 15px; border-radius: 8px; margin-bottom: 20px; }

            /* --- 贊助按鈕樣式 --- */
            .sponsor-box { padding: 10px; text-align: center; margin-bottom: 10px; }
            .sponsor-title { font-weight: bold; color: #555; }

            /* --- 深色模式適應 --- */
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #90CAF9 !important; }
                .vibe-box { background-color: #1E262E !important; color: #E3F2FD !important; border-left: 6px solid #64B5F6 !important; }
                .stMarkdown p, .stMarkdown li { color: #E0E0E0 !important; }
                .sponsor-title { color: #ccc; }
            }
                        /* 贊助按鈕容器 */
            .sponsor-container {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin-bottom: 20px;
            }

            /* 綠界按鈕樣式 */
            .btn-ecpay {
                background-color: #00A650;
                color: white !important;
                text-decoration: none;
                padding: 10px 15px;
                border-radius: 8px;
                font-weight: bold;
                text-align: center;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                border: none;
                transition: 0.3s;
            }
            .btn-ecpay:hover { background-color: #008540; transform: translateY(-2px); }

            /* Buy Me a Coffee 按鈕樣式 */
            .btn-bmc {
                background-color: #FFDD00;
                color: black !important;
                text-decoration: none;
                padding: 10px 15px;
                border-radius: 8px;
                font-weight: bold;
                text-align: center;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                border: none;
                transition: 0.3s;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .btn-bmc:hover { background-color: #ffea00; transform: translateY(-2px); }
            
            .btn-icon { width: 20px; height: 20px; }
        </style>
    """, unsafe_allow_html=True)
# ==========================================
# 2. 共用工具函式
# ==========================================

def get_gemini_keys():
    """獲取並隨機打亂 API Keys (支援單一字串或列表)"""
    keys = st.secrets.get("GEMINI_FREE_KEYS")
    if not keys:
        single_key = st.secrets.get("GEMINI_API_KEY")
        if single_key: keys = [single_key]
        else: return []
    if isinstance(keys, str): keys = [keys]
    shuffled_keys = keys.copy()
    random.shuffle(shuffled_keys)
    return shuffled_keys

def fix_content(text):
    """全域字串清洗 (v3.0 邏輯)"""
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    text = str(text)
    text = text.replace('\\n', '  \n').replace('\n', '  \n')
    if '\\\\' in text: text = text.replace('\\\\', '\\')
    text = text.strip('"').strip("'")
    return text

def speak(text, key_suffix=""):
    """TTS 發音生成 (v3.0 HTML 按鈕版)"""
    if not text: return
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    english_only = " ".join(english_only.split()).strip()
    if not english_only: return

    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        
        html_code = f"""
        <html>
        <style>
            .btn {{ background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 5px 10px; cursor: pointer; display: flex; align-items: center; gap: 5px; font-family: sans-serif; font-size: 14px; color: #333; transition: 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .btn:hover {{ background: #f8f9fa; border-color: #ccc; }}
            .btn:active {{ background: #eef; transform: scale(0.98); }}
        </style>
        <body>
            <button class="btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
            <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        </body>
        </html>
        """
        components.html(html_code, height=40)
    except Exception:
        pass

def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets["gsheets"]["spreadsheet"]

def log_user_intent(label):
    """紀錄用戶意願 (Metrics)"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        try: m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
        except: m_df = pd.DataFrame(columns=['label', 'count'])
        
        if label in m_df['label'].values:
            m_df.loc[m_df['label'] == label, 'count'] = m_df.loc[m_df['label'] == label, 'count'].astype(int) + 1
        else:
            new_record = pd.DataFrame([{'label': label, 'count': 1}])
            m_df = pd.concat([m_df, new_record], ignore_index=True)
        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)
    except: pass

@st.cache_data(ttl=360) 
def load_db(source_type="Google Sheets"):
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe', 'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage', 'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag', 'term']
    df = pd.DataFrame(columns=COL_NAMES)
    try:
        if source_type == "Google Sheets":
            conn = st.connection("gsheets", type=GSheetsConnection)
            url = get_spreadsheet_url()
            df = conn.read(spreadsheet=url, ttl=0)
        elif source_type == "Local JSON":
            if os.path.exists("master_db.json"):
                with open("master_db.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data: df = pd.DataFrame(data)
        for col in COL_NAMES:
            if col not in df.columns: df[col] = 0 if col == 'term' else "無"
        return df.dropna(subset=['word']).fillna("無")[COL_NAMES].reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

def submit_report(row_data):
    try:
        FEEDBACK_URL = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
        conn = st.connection("gsheets", type=GSheetsConnection)
        report_row = row_data.copy()
        report_row['term'] = 1
        try: existing = conn.read(spreadsheet=FEEDBACK_URL, ttl=0)
        except: existing = pd.DataFrame()
        updated = pd.concat([existing, pd.DataFrame([report_row])], ignore_index=True)
        conn.update(spreadsheet=FEEDBACK_URL, data=updated)
        st.toast(f"✅ 已回報「{row_data.get('word')}」", icon="🛠️")
        return True
    except Exception as e:
        st.error(f"回報失敗: {e}")
        return False

# ==========================================
# 3. Etymon 模組: AI 解碼核心 (詳細版)
# ==========================================

def ai_decode_and_save(input_text, fixed_category):
    """
    核心解碼函式 (多 Key 輪詢版)：
    保留 v3.0 的詳細 Prompt 與欄位定義。
    """
    keys = get_gemini_keys()
    if not keys:
        st.error("❌ 找不到 GEMINI_FREE_KEYS")
        return None

    # 保留 v3.0 的詳細 Prompt
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
    7. phonetic: 關鍵年代、發明人名、或該領域的專門術語。標註正確發音與背景。
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
    1. 必須輸出純 JSON 格式，不含任何 Markdown 標記。
    2. 所有的鍵名 (Keys) 與字串值 (Values) 必須使用雙引號 (") 包裹。
    3. LaTeX 公式請使用單個反斜線格式，但在 JSON 內需雙重轉義。
    4. 換行統一使用 \\\\n。
    """
    final_prompt = f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」"

    last_error = None
    for key in keys:
        try:
            genai.configure(api_key=key)
            # 使用較新的模型
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(final_prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            last_error = e
            print(f"⚠️ Etymon Key failed: {e}")
            continue
    
    st.error(f"❌ 所有 Key 皆失敗: {last_error}")
    return None
def show_encyclopedia_card(row):
    # 1. 變數定義與清洗
    r_word = str(row.get('word', '未命名主題'))
    r_roots = fix_content(row.get('roots', "")).replace('$', '$$')
    r_phonetic = fix_content(row.get('phonetic', "")) 
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_meaning = str(row.get('meaning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_trans = str(row.get('translation', ""))
    r_ex = fix_content(row.get('example', ""))

    # 2. 標題與發音區
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    if r_phonetic and r_phonetic != "無":
        st.caption(f"/{r_phonetic}/")

    # 3. 邏輯拆解區 (視覺化漸層外框)
    st.markdown(f"""
        <div class='breakdown-wrapper'>
            <h4 style='color: white; margin-top: 0;'>🧬 邏輯拆解</h4>
            <div style='color: white; font-weight: 700;'>{r_breakdown}</div>
        </div>
    """, unsafe_allow_html=True)

    st.write("---")
    
    # 4. 核心內容區 (定義與原理)
    c1, c2 = st.columns(2)
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

    # 5. 專家視角 (內行心法)
    if r_vibe and r_vibe != "無":
        st.markdown(f"""
            <div class='vibe-box'>
                <h4 style='margin-top:0;'>🌊 專家視角 / 內行心法</h4>
                {r_vibe}
            </div>
        """, unsafe_allow_html=True)

    # 6. 深度百科
    with st.expander("🔍 深度百科 (辨析、起源、邊界條件)"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：** \n{fix_content(row.get('synonym_nuance', '無'))}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：** \n{fix_content(row.get('usage_warning', '無'))}")

    st.write("---")

    # 7. 功能操作區 (發音、回報、跳轉講義)
    op1, op2, op3 = st.columns([1, 1, 1.5])
    
    with op1:
        speak(r_word, f"card_{r_word}")
        
    with op2:
        if st.button("🚩 有誤回報", key=f"rep_{r_word}", use_container_width=True):
            submit_report(row.to_dict() if hasattr(row, 'to_dict') else row)
            
    with op3:
        # 關鍵功能：繼承資訊並同步填入「素材框」與「預覽區」
        if st.button("📄 生成講義 (10元)", key=f"gen_ho_{r_word}", type="primary", use_container_width=True):
            # A. 封裝完整單字物件資料
            st.session_state.inherited_word_data = row.to_dict() if hasattr(row, 'to_dict') else row
            
            # B. 格式化內容 (Markdown 格式)
            inherited_text = (
                f"## 專題講義：{r_word}\n\n"
                f"### 🧬 邏輯拆解\n{r_breakdown}\n\n"
                f"### 🎯 核心定義\n{r_def}\n\n"
                f"### 💡 核心原理\n{r_roots}\n\n"
                f"**本質意義**：{r_meaning}\n\n"
                f"**應用實例**：{r_ex}\n\n"
                f"**專家心法**：{r_vibe}"
            )
            
            # C. 雙向同步：同時設定左側素材與右側預覽 (解決跳轉後預覽區空白的問題)
            st.session_state.manual_input_content = inherited_text  # 填入左側素材框
            st.session_state.generated_text = inherited_text       # 填入右側預覽區
            
            # D. 切換導航模式並重整頁面
            st.session_state.app_mode = "Handout Pro (講義排版)"
            st.rerun()
# ==========================================
# 4. Etymon 模組: 頁面邏輯
# ==========================================

def page_etymon_lab():
    st.title("🔬 解碼實驗室")
    
    # 保留 v3.0 完整的分類列表
    FIXED_CATEGORIES = [
        "英語辭源", "語言邏輯", "物理科學", "生物醫學", "天文地質", "數學邏輯", 
        "歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "考古發現",
        "商業商戰", "金融投資", "程式開發", "人工智慧", "產品設計", "數位行銷",
        "藝術美學", "影視文學", "料理食觀", "運動健身", "流行文化", "雜類", "自定義"
    ]
    
    col_input, col_cat = st.columns([2, 1])
    with col_input:
        new_word = st.text_input("輸入解碼主題：", placeholder="例如: '熵增定律'...")
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
                    st.code(raw_res)
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

def page_etymon_home(df):
    st.markdown("<h1 style='text-align: center;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.write("---")
    
    # 1. 數據儀表板
    c1, c2, c3 = st.columns(3)
    c1.metric("📚 總單字量", len(df))
    c2.metric("🏷️ 分類主題", df['category'].nunique() if not df.empty else 0)
    c3.metric("🧩 獨特字根", df['roots'].nunique() if not df.empty else 0)
    
    st.write("---")

    # 2. 隨機推薦區
    col_header, col_btn = st.columns([4, 1])
    with col_header: st.subheader("💡 今日隨機推薦")
    with col_btn:
        if st.button("🔄 換一批", use_container_width=True):
            if 'home_sample' in st.session_state: del st.session_state.home_sample
            st.rerun()
    
    if not df.empty:
        if 'home_sample' not in st.session_state:
            st.session_state.home_sample = df.sample(min(3, len(df)))
        
        sample = st.session_state.home_sample
        cols = st.columns(3)
        for i, (index, row) in enumerate(sample.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    st.markdown(f"**定義：** {fix_content(row['definition'])[:50]}...")
                    st.markdown(f"**核心：** {fix_content(row['roots'])[:50]}...")
                    
                    b1, b2 = st.columns(2)
                    with b1: speak(row['word'], f"home_{i}")
                    with b2: 
                        if st.button("🚩 有誤", key=f"h_rep_{i}_{row['word']}"): submit_report(row.to_dict())

    st.write("---")
    st.info("👈 點擊左側選單進入「學習與搜尋」查看完整資料庫。")
def run_handout_app():
    st.header("🎓 AI 講義排版大師 Pro")
    
    # 1. 檢查繼承狀態與初始化 Session State
    inherited_data = st.session_state.get("inherited_word_data")
    if inherited_data:
        st.success(f"🧬 已成功繼承單字「{inherited_data.get('word')}」的深度解碼資訊")
    
    # 確保必要的狀態 Key 存在
    if "manual_input_content" not in st.session_state:
        st.session_state.manual_input_content = ""
    if "generated_text" not in st.session_state:
        st.session_state.generated_text = ""
    if "user_balance" not in st.session_state:
        st.session_state.user_balance = 100

    # 2. 頁面佈局
    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    
    with col_ctrl:
        st.subheader("1. 素材與設定")
        
        # --- 圖片處理區 ---
        uploaded_file = st.file_uploader("上傳題目圖片 (可選)", type=["jpg", "png", "jpeg"])
        image = None
        img_width = 80
        if uploaded_file:
            img_obj = Image.open(uploaded_file)
            image = fix_image_orientation(img_obj)
            if st.session_state.get('rotate_angle', 0) != 0:
                image = image.rotate(-st.session_state.rotate_angle, expand=True)
            
            c1, c2 = st.columns([1, 2])
            with c1: 
                if st.button("🔄 旋轉 90°"): 
                    st.session_state.rotate_angle = (st.session_state.get('rotate_angle', 0) + 90) % 360
                    st.rerun()
            with c2: img_width = st.slider("圖片顯示寬度 (%)", 10, 100, 80)
            st.image(image, use_container_width=True)

        st.divider()
        
        # --- 文字輸入區 (左側素材) ---
        # 使用 key 綁定，確保跳轉過來的文字自動填入
        st.text_area(
            "講義素材內容 (AI 將根據此內容生成)", 
            key="manual_input_content", 
            height=300,
            help="您可以修改繼承過來的文字，或手動輸入新素材。"
        )
        
        ai_instr = st.text_input("額外 AI 指令", placeholder="例如：增加三個隨堂練習題、標註重點...")
        
        # --- 3. 支付確認與生成按鈕 ---
        current_balance = st.session_state.user_balance
        st.markdown(f"""
            <div style='background: #fff7ed; padding: 15px; border-radius: 8px; border: 1px solid #fdba74;'>
                <p style='margin:0; color: #9a3412;'><b>💰 生成費用：10 元 / 次</b></p>
                <p style='margin:0; font-size: 0.9rem; color: #c2410c;'>當前帳戶餘額：{current_balance} 元</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("") 
        
        if st.button("🚀 確認支付並開始生成", type="primary", use_container_width=True):
            if current_balance < 10:
                st.error("❌ 餘額不足，請點擊左上角贊助支持以獲得點數。")
            elif not st.session_state.manual_input_content and not uploaded_file:
                st.warning("⚠️ 請提供文字素材或上傳圖片內容。")
            else:
                with st.spinner("💸 正在扣款並調用 AI 進行深度排版..."):
                    # A. 執行扣款
                    st.session_state.user_balance -= 10
                    
                    # B. 調用 AI 生成 (傳入左側 manual_input_content)
                    final_prompt = st.session_state.manual_input_content
                    if inherited_data:
                        final_prompt = f"請根據以下解碼後的單字精華資訊，製作一份具備教學邏輯的專業講義：\n\n{final_prompt}"
                    
                    generated_res = handout_ai_generate(image, final_prompt, ai_instr)
                    
                    # C. 更新右側預覽內容
                    st.session_state.generated_text = generated_res
                    
                    # D. 清除繼承標記，但保留輸入框文字
                    if "inherited_word_data" in st.session_state:
                        del st.session_state.inherited_word_data
                    
                    st.success("✅ 支付成功！專業講義已生成。")
                    st.rerun()

    with col_prev:
        st.subheader("2. A4 預覽與修訂")
        st.markdown('<div class="info-card"><b>📏 提示：</b>下方為即時預覽區。您可以直接修改文字，完成後點擊下載 PDF。</div>', unsafe_allow_html=True)
        
        # --- 內容修訂區 (右側預覽) ---
        # 關鍵修正：value 綁定 st.session_state.generated_text
        # 這樣跳轉過來時，初步草稿會立刻顯示在這裡
        edited_content = st.text_area(
            "📝 講義內容編輯", 
            value=st.session_state.generated_text, 
            height=450,
            key="preview_editor" # 使用 key 確保編輯器狀態獨立
        )
        
        # 標題設定
        default_title = "AI 專題講義"
        if inherited_data: 
            default_title = f"{inherited_data.get('word')} 專題講義"
        elif st.session_state.generated_text:
            # 嘗試從內容中抓取標題 (簡單邏輯)
            first_line = st.session_state.generated_text.split('\n')[0].replace('#', '').strip()
            if first_line: default_title = first_line
            
        handout_title = st.text_input("講義標題", value=default_title)
        
        # 準備圖片 Base64
        img_b64 = get_image_base64(image) if image else ""
        
        # 4. 生成最終列印用 HTML
        # 使用 edited_content (用戶手動修改後的內容) 進行渲染
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)
        
        # 渲染 HTML 預覽組件
        components.html(final_html, height=1000, scrolling=True)
def page_etymon_learn(df):
    st.title("📖 學習與搜尋")
    if df.empty:
        st.warning("目前書架是空的。")
        return

    tab_card, tab_list = st.tabs(["🎲 隨機探索", "🔍 搜尋與列表"])
    
    # --- Tab 1: 隨機探索 ---
    with tab_card:
        cats = ["全部"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("選擇學習分類", cats, key="learn_cat_select")
        f_df = df if sel_cat == "全部" else df[df['category'] == sel_cat]
        
        if 'curr_w' not in st.session_state: st.session_state.curr_w = None
        
        if st.button("🎲 隨機探索下一字 (Next Word)", use_container_width=True, type="primary"):
            if not f_df.empty:
                st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
                st.rerun()
        
        if st.session_state.curr_w is None and not f_df.empty:
            st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
            
        if st.session_state.curr_w:
            show_encyclopedia_card(st.session_state.curr_w)

    # --- Tab 2: 搜尋與列表 ---
    with tab_list:
        col_search, col_mode = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("🔍 搜尋內容...", placeholder="輸入單字名稱...")
        with col_mode:
            search_mode = st.radio("搜尋模式", ["精確匹配", "關鍵字包含"], horizontal=True)

        if search_query:
            query_clean = search_query.strip().lower()
            if search_mode == "精確匹配":
                mask = df['word'].str.strip().str.lower() == query_clean
            else:
                mask = df.astype(str).apply(lambda x: x.str.contains(query_clean, case=False)).any(axis=1)
            
            display_df = df[mask]
            
            if not display_df.empty:
                st.info(f"💡 找到 {len(display_df)} 筆結果：")
                for index, row in display_df.iterrows():
                    with st.container(border=True): show_encyclopedia_card(row)
            else:
                st.warning(f"❌ 找不到與「{search_query}」匹配的內容。")
                if search_mode == "精確匹配":
                    fuzzy_mask = df['word'].str.contains(query_clean, case=False)
                    suggestions = df[fuzzy_mask]['word'].tolist()
                    if suggestions: st.caption(f"你是不是在找：{', '.join(suggestions[:5])}？")
        else:
            st.caption("請在上方輸入框輸入單字。")
            st.dataframe(df[['word', 'definition', 'category']], use_container_width=True, hide_index=True)

def page_etymon_quiz(df):
    st.title("🧠 字根記憶挑戰")
    if df.empty: return
    
    cat = st.selectbox("選擇測驗範圍", df['category'].unique())
    pool = df[df['category'] == cat]
    
    if 'q' not in st.session_state: st.session_state.q = None
    if 'show_ans' not in st.session_state: st.session_state.show_ans = False

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
            speak(st.session_state.q['word'], "quiz")
            st.write(f"結構拆解：`{st.session_state.q['breakdown']}`")
# ==========================================
# 5. Handout Pro 模組: 講義排版
# ==========================================

def fix_image_orientation(image):
    try: image = ImageOps.exif_transpose(image)
    except: pass
    return image

def get_image_base64(image):
    if image is None: return ""
    buffered = BytesIO()
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode()

def handout_ai_generate(image, manual_input, instruction):
    """Handout 的 AI 核心 (含輪詢機制)"""
    keys = get_gemini_keys()
    if not keys: return "❌ 錯誤：API Key 未設定"

    prompt = "你是一位專業教師。請撰寫講義。【格式】使用 $...$ 或 $$...$$ 撰寫 LaTeX。【排版】請直接開始內容，不要有前言。"
    parts = [prompt]
    if manual_input: parts.append(f"【補充】：{manual_input}")
    if instruction: parts.append(f"【要求】：{instruction}")
    if image: parts.append(image)

    last_error = None
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(parts)
            return response.text
        except Exception as e:
            last_error = e
            print(f"⚠️ Handout Key failed: {e}")
            continue
    
    return f"AI 異常 (所有 Key 皆失敗): {str(last_error)}"

def generate_printable_html(title, text_content, img_b64, img_width_percent):
    """
    生成 A4 列印用 HTML。
    注意：f-string 中的 CSS 和 JS 大括號必須使用 {{ }} 進行轉義。
    """
    text_content = text_content.strip()
    text_content = re.sub(r'^(\[換頁\]|\s|\n)+', '', text_content)
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>').replace('\\\\', '\\')
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script>
        window.MathJax = {{ tex: {{ inlineMath: [['$', '$']], displayMath: [['$$', '$$']], processEscapes: true }}, svg: {{ fontCache: 'global' }} }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.8; padding: 0; margin: 0; background: #2c2c2c; display: flex; flex-direction: column; align-items: center; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; margin: 20px 0; padding: 20mm 25mm; box-sizing: border-box; position: relative; background-image: linear-gradient(to bottom, #e0f2fe 20mm, transparent 20mm), linear-gradient(to bottom, transparent 277mm, #fee2e2 277mm); background-size: 100% 297mm; }}
            .content {{ font-size: 16px; text-align: justify; position: relative; z-index: 2; }}
            .content h2 {{ page-break-before: always; break-before: always; color: #1a237e; border-left: 5px solid #1a237e; padding-left: 10px; margin-top: 30px; }}
            .content h2:first-child {{ page-break-before: avoid !important; margin-top: 0 !important; }}
            .manual-page-break {{ page-break-before: always; height: 1px; }}
            .content p, .content li, .img-wrapper, mjx-container, table {{ page-break-inside: avoid; break-inside: avoid; margin-bottom: 15px; }}
            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; margin-top: 0; }}
            .img-wrapper {{ text-align: center; margin: 15px 0; }}
            #btn-container {{ text-align: center; padding: 15px; width: 100%; position: sticky; top: 0; background: #1a1a1a; z-index: 9999; }}
            .download-btn {{ background: #0284c7; color: white; border: none; padding: 12px 60px; border-radius: 4px; font-size: 16px; font-weight: bold; cursor: pointer; }}
            @media print {{ body {{ background: white !important; }} #printable-area {{ margin: 0 !important; box-shadow: none !important; background-image: none !important; }} #btn-container {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div id="btn-container"><button class="download-btn" onclick="downloadPDF()">📥 下載 A4 講義</button></div>
        <div id="printable-area">
            <h1>{title}</h1><div style="text-align:right; font-size:12px; color:#666;">日期：{date_str}</div>
            {img_section}<div class="content">{html_body}</div>
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{ margin: 0, filename: '{title}.pdf', image: {{ type: 'jpeg', quality: 1.0 }}, html2canvas: {{ scale: 3, useCORS: true, logging: false, scrollY: 0 }}, jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}, pagebreak: {{ mode: ['avoid-all', 'css', 'legacy'] }} }};
                MathJax.typesetPromise().then(() => {{ setTimeout(() => {{ html2pdf().set(opt).from(element).save(); }}, 1200); }});
            }}
        </script>
    </body>
    </html>
    """

def run_handout_app():
    st.header("🎓 AI 講義排版大師 Pro")
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    with col_ctrl:
        st.subheader("1. 素材與設定")
        uploaded_file = st.file_uploader("上傳題目圖片", type=["jpg", "png", "jpeg"])
        image = None
        img_width = 80
        if uploaded_file:
            img_obj = Image.open(uploaded_file)
            image = fix_image_orientation(img_obj)
            if st.session_state.rotate_angle != 0:
                image = image.rotate(-st.session_state.rotate_angle, expand=True)
            c1, c2 = st.columns([1, 2])
            with c1: 
                if st.button("🔄 旋轉 90°"): 
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with c2: img_width = st.slider("圖片寬度 (%)", 10, 100, 80)
            st.image(image, use_container_width=True)

        st.divider()
        manual_input = st.text_area("補充文字", height=150)
        ai_instr = st.text_input("AI 指令")
        if st.button("🚀 生成內容", type="primary"):
            if not image and not manual_input: st.warning("⚠️ 請提供素材！")
            else:
                with st.spinner("🤖 AI 排版運算中 (多 Key 輪詢)..."):
                    res = handout_ai_generate(image, manual_input, ai_instr)
                    st.session_state.generated_text = res
                    st.rerun()

    with col_prev:
        st.subheader("2. A4 預覽")
        st.markdown('<div class="info-card"><b>📏 說明：</b>藍色為起點，紅色為終點。輸入 [換頁] 可強制分頁。</div>', unsafe_allow_html=True)
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else "### 預覽區\n請在左側上傳圖片或輸入文字以生成講義。"
        edited_content = st.text_area("📝 內容修訂", value=content_to_show, height=300)
        handout_title = st.text_input("講義標題", value="精選解析")
        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)
        components.html(final_html, height=1000, scrolling=True)

# ==========================================
# 6. 主程式入口與導航
# ==========================================
def main():
    inject_custom_css()
    
    # 初始化登入狀態
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # 判斷是否已登入
    if not st.session_state.logged_in:
        login_page()
        return

    # --- 以下為登入後的內容 ---
    
    # 側邊欄用戶資訊
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state.username}")
        role_label = "🔴 管理員" if st.session_state.role == "admin" else "🟢 學生"
        if st.session_state.role == "guest": role_label = "⚪ 訪客"
        st.caption(role_label)
        
        # 登出按鈕
        if st.button("🚪 登出系統"):
            if st.session_state.username != "訪客":
                update_user_status(st.session_state.username, "is_online", "FALSE")
            st.session_state.logged_in = False
            st.rerun()
        
        st.markdown("---")
        # 贊助按鈕區 (原本的區塊)
        st.markdown('<div class="sponsor-box"><span class="sponsor-title">💖 支持開發者</span></div>', unsafe_allow_html=True)
        # ... (ECPay, BMC 按鈕代碼) ...
        
        # 餘額顯示
        st.markdown(f"""
            <div style='background: #fff3e0; padding: 12px; border-radius: 10px; border: 1px solid #ffb74d; text-align: center; margin-bottom: 20px;'>
                <span style='color: #e65100; font-weight: bold;'>💰 帳戶餘額：{st.session_state.user_balance} 元</span>
            </div>
        """, unsafe_allow_html=True)

    # 模式選擇
    app_mode = st.sidebar.selectbox("選擇功能模組", ["Etymon Decoder (單字解碼)", "Handout Pro (講義排版)"])
    
    # 路由邏輯
    if app_mode == "Etymon Decoder (單字解碼)":
        menu = ["首頁", "學習與搜尋", "測驗模式"]
        # 只有管理員可以看到實驗室
        if st.session_state.role == "admin":
            menu.append("🔬 解碼實驗室")
        
        page = st.sidebar.radio("Etymon 選單", menu)
        df = load_db() # 這是原本讀取單字庫的函式
        
        if page == "首頁": page_etymon_home(df)
        elif page == "學習與搜尋": page_etymon_learn(df)
        elif page == "測驗模式": page_etymon_quiz(df)
        elif page == "🔬 解碼實驗室": page_etymon_lab()
        
    elif app_mode == "Handout Pro (講義排版)":
        run_handout_app()

if __name__ == "__main__":
    main()
