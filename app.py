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
# 1. 核心配置 (必須放在最前面)
# ==========================================
st.set_page_config(page_title="AI 教育工作站 (Etymon + Handout)", page_icon="🏫", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Noto+Sans+TC:wght@500;700&display=swap');
            
            /* --- 全域樣式 --- */
            .stMainContainer { transition: background-color 0.3s ease; }

            /* --- Etymon Decoder 樣式 --- */
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
            
            /* --- Handout Pro 樣式 --- */
            .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
            .info-card { background-color: #f0f9ff; border-left: 5px solid #0ea5e9; padding: 15px; border-radius: 8px; margin-bottom: 20px; }

            /* --- 贊助按鈕樣式 --- */
            .sponsor-container { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
            .btn-ecpay {
                background-color: #00A650; color: white !important; text-decoration: none;
                padding: 10px 15px; border-radius: 8px; font-weight: bold; text-align: center;
                display: flex; align-items: center; justify-content: center; gap: 8px; border: none; transition: 0.3s;
            }
            .btn-ecpay:hover { background-color: #008540; transform: translateY(-2px); }
            .btn-bmc {
                background-color: #FFDD00; color: black !important; text-decoration: none;
                padding: 10px 15px; border-radius: 8px; font-weight: bold; text-align: center;
                display: flex; align-items: center; justify-content: center; gap: 8px; border: none; transition: 0.3s;
            }
            .btn-bmc:hover { background-color: #ffea00; transform: translateY(-2px); }
            .btn-icon { width: 20px; height: 20px; }

            /* --- 深色模式適應 --- */
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #90CAF9 !important; }
                .vibe-box { background-color: #1E262E !important; color: #E3F2FD !important; border-left: 6px solid #64B5F6 !important; }
                .stMarkdown p, .stMarkdown li { color: #E0E0E0 !important; }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 用戶系統與工具函式
# ==========================================
def hash_password(password): 
    import hashlib
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_user_db():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        cols = ['username', 'password', 'role', 'membership', 'ai_usage', 'is_online', 'last_seen']
        for col in cols:
            if col not in df.columns: df[col] = "free" if col=="membership" else (0 if col=="ai_usage" else "無")
        return df.fillna("無")
    except: return pd.DataFrame(columns=['username', 'password', 'role', 'membership', 'ai_usage', 'is_online', 'last_seen'])

def save_user_to_db(new_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        new_data['created_at'] = time.strftime("%Y-%m-%d")
        updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(worksheet="users", data=updated_df)
        return True
    except: return False

def update_user_status(username, column, value):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        df.loc[df['username'] == username, column] = value
        conn.update(worksheet="users", data=df)
    except: pass

def get_gemini_keys():
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
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    text = str(text)
    text = text.replace('\\n', '  \n').replace('\n', '  \n')
    if '\\\\' in text: text = text.replace('\\\\', '\\')
    text = text.strip('"').strip("'")
    return text

def speak(text, key_suffix=""):
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
    except: pass

def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets["gsheets"]["spreadsheet"]

@st.cache_data(ttl=360) 
def load_db(source_type="Google Sheets"):
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe', 'synonym_nuance', 'visual_prompt', 'social_status', 'emotional_tone', 'street_usage', 'collocation', 'etymon_story', 'usage_warning', 'memory_hook', 'audio_tag', 'term']
    df = pd.DataFrame(columns=COL_NAMES)
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        df = conn.read(spreadsheet=url, ttl=0)
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
    except Exception as e: st.error(f"回報失敗: {e}")

# ==========================================
# 3. Etymon 模組: AI 解碼核心
# ==========================================
def ai_decode_and_save(input_text, fixed_category):
    keys = get_gemini_keys()
    if not keys:
        st.error("❌ 找不到 GEMINI_FREE_KEYS")
        return None

    SYSTEM_PROMPT = f"""
    Role: 全領域知識解構專家. Task: 將輸入解構為 JSON.
    Category: {fixed_category}.
    Fields: category, word, roots(LaTeX), meaning, breakdown(steps), definition(ELI5), phonetic, example, translation, native_vibe, synonym_nuance, visual_prompt, social_status, emotional_tone, street_usage, collocation, etymon_story, usage_warning, memory_hook, audio_tag.
    Output: Pure JSON only. No Markdown. Use double quotes for keys/values.
    """
    final_prompt = f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」"

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(final_prompt)
            if response and response.text: return response.text
        except: continue
    st.error("❌ AI 服務暫時無法使用")
    return None

def show_encyclopedia_card(row):
    r_word = str(row.get('word', '未命名'))
    r_roots = fix_content(row.get('roots', "")).replace('$', '$$')
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_ex = fix_content(row.get('example', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))

    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    if row.get('phonetic') != "無": st.caption(f"/{fix_content(row.get('phonetic'))}/")
    
    st.markdown(f"<div class='breakdown-wrapper'><h4>🧬 邏輯拆解</h4>{r_breakdown}</div>", unsafe_allow_html=True)
    st.write("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("### 🎯 定義與解釋")
        st.write(r_def)
        st.caption(f"📝 {r_ex}")
    with c2:
        st.success("### 💡 核心原理")
        st.write(r_roots)
        st.write(f"**🔍 本質：** {row.get('meaning')}")

    if r_vibe and r_vibe != "無":
        st.markdown(f"<div class='vibe-box'><h4>🌊 專家視角</h4>{r_vibe}</div>", unsafe_allow_html=True)

    st.write("---")
    op1, op2, op3 = st.columns([1, 1, 1.5])
    with op1: speak(r_word, f"card_{r_word}")
    with op2: 
        if st.button("🚩 有誤回報", key=f"rep_{r_word}"): submit_report(row.to_dict())
            
    with op3:
        # 【免費跳轉按鈕】
        if st.button("📄 生成講義 (預覽)", key=f"jump_ho_{r_word}", type="primary", use_container_width=True):
            inherited_draft = (
                f"## 專題講義：{r_word}\n\n"
                f"### 🧬 邏輯拆解\n{r_breakdown}\n\n"
                f"### 🎯 核心定義\n{r_def}\n\n"
                f"### 💡 核心原理\n{r_roots}\n\n"
                f"**本質意義**：{row.get('meaning')}\n\n"
                f"**應用實例**：{r_ex}\n\n"
                f"**專家心法**：{r_vibe}"
            )
            st.session_state.manual_input_content = inherited_draft
            st.session_state.generated_text = inherited_draft
            st.session_state.app_mode = "Handout Pro (講義排版)"
            st.rerun()

# ==========================================
# 4. Etymon 頁面
# ==========================================
def page_etymon_lab():
    st.title("🔬 解碼實驗室")
    col_in, col_cat = st.columns([2, 1])
    with col_in: new_word = st.text_input("輸入主題", placeholder="例如: '熵增定律'...")
    with col_cat: cat = st.selectbox("領域", ["物理科學", "商業商戰", "心理學", "自定義"])
    
    if st.button("啟動解碼", type="primary"):
        with st.spinner("解碼中..."):
            res = ai_decode_and_save(new_word, cat)
            if res:
                try:
                    match = re.search(r'\{.*\}', res, re.DOTALL)
                    data = json.loads(match.group(0))
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    url = get_spreadsheet_url()
                    old_df = conn.read(spreadsheet=url, ttl=0)
                    new_df = pd.concat([old_df, pd.DataFrame([data])], ignore_index=True)
                    conn.update(spreadsheet=url, data=new_df)
                    st.success("✅ 解碼並存檔成功！")
                    show_encyclopedia_card(data)
                except Exception as e: st.error(f"解析失敗: {e}")

def page_etymon_home(df):
    st.markdown("<h1 style='text-align: center;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("📚 總單字量", len(df))
    c2.metric("🏷️ 分類", df['category'].nunique() if not df.empty else 0)
    c3.metric("🧩 字根", df['roots'].nunique() if not df.empty else 0)
    st.write("---")
    
    if st.button("🔄 換一批推薦", use_container_width=True):
        if 'home_sample' in st.session_state: del st.session_state.home_sample
        st.rerun()
        
    if not df.empty:
        if 'home_sample' not in st.session_state:
            st.session_state.home_sample = df.sample(min(3, len(df)))
        cols = st.columns(3)
        for i, (idx, row) in enumerate(st.session_state.home_sample.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### {row['word']}")
                    st.caption(f"🏷️ {row['category']}")
                    st.markdown(f"**定義：** {fix_content(row['definition'])[:50]}...")
                    b1, b2 = st.columns(2)
                    with b1: speak(row['word'], f"h_{i}")
                    with b2: 
                        if st.button("🚩 有誤", key=f"h_rep_{i}"): submit_report(row.to_dict())

def page_etymon_learn(df):
    st.title("📖 學習與搜尋")
    tab1, tab2 = st.tabs(["🎲 隨機", "🔍 搜尋"])
    with tab1:
        if st.button("🎲 下一個", type="primary"):
            st.session_state.curr_w = df.sample(1).iloc[0].to_dict()
            st.rerun()
        if 'curr_w' in st.session_state and st.session_state.curr_w:
            show_encyclopedia_card(st.session_state.curr_w)
    with tab2:
        q = st.text_input("搜尋...")
        if q:
            res = df[df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            for _, row in res.iterrows():
                with st.container(border=True): show_encyclopedia_card(row)

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
        st.write(f"**提示:** {st.session_state.q['roots']}")
        if st.button("揭曉答案"):
            st.session_state.show_ans = True
            st.rerun()
        if st.session_state.show_ans:
            st.success(f"💡 答案：**{st.session_state.q['word']}**")
            speak(st.session_state.q['word'], "quiz")

# ==========================================
# 5. Handout Pro 模組
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
    keys = get_gemini_keys()
    if not keys: return "❌ 錯誤：API Key 未設定"
    prompt = "你是一位專業教師。請撰寫講義。【格式】使用 $...$ 或 $$...$$ 撰寫 LaTeX。【排版】請直接開始內容，不要有前言。"
    parts = [prompt]
    if manual_input: parts.append(f"【補充】：{manual_input}")
    if instruction: parts.append(f"【要求】：{instruction}")
    if image: parts.append(image)
    
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(parts)
            return response.text
        except: continue
    return "AI 異常"

def generate_printable_html(title, text_content, img_b64, img_width_percent):
    text_content = text_content.strip()
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>').replace('\\\\', '\\')
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.8; padding: 0; margin: 0; background: #2c2c2c; display: flex; flex-direction: column; align-items: center; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; margin: 20px 0; padding: 20mm 25mm; box-sizing: border-box; position: relative; }}
            .content {{ font-size: 16px; text-align: justify; }}
            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            #btn-container {{ text-align: center; padding: 15px; width: 100%; position: sticky; top: 0; background: #1a1a1a; z-index: 9999; }}
            .download-btn {{ background: #0284c7; color: white; border: none; padding: 12px 50px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }}
            .sponsor-text {{ color: #cbd5e1; font-size: 12px; margin-top: 8px; }}
            @media print {{ #btn-container {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 下載 A4 講義 (PDF)</button>
            <div class="sponsor-text">💖 講義生成完全免費，若覺得好用歡迎隨喜贊助支持！</div>
        </div>
        <div id="printable-area">
            <h1>{title}</h1><div style="text-align:right; font-size:12px; color:#666;">日期：{date_str}</div>
            {img_section}<div class="content">{html_body}</div>
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{
                    margin: 0, filename: '{title}.pdf', image: {{ type: 'jpeg', quality: 1.0 }},
                    html2canvas: {{ scale: 3, useCORS: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                html2pdf().set(opt).from(element).save();
            }}
        </script>
    </body>
    </html>
    """

def run_handout_app():
    st.header("🎓 AI 講義排版大師 Pro")
    is_admin = st.session_state.get("is_admin", False)
    
    if "manual_input_content" not in st.session_state: st.session_state.manual_input_content = ""
    if "generated_text" not in st.session_state: st.session_state.generated_text = ""
    if "rotate_angle" not in st.session_state: st.session_state.rotate_angle = 0

    if "專題講義" in st.session_state.manual_input_content:
        st.toast("📝 已導入單字草稿", icon="✨")

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    with col_ctrl:
        st.subheader("1. 素材與生成")
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
                if st.button("🔄 旋轉"): 
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with c2: img_width = st.slider("寬度", 10, 100, 80)
            st.image(image, use_container_width=True)

        st.divider()
        st.text_area("講義素材內容", key="manual_input_content", height=300)
        
        if is_admin:
            ai_instr = st.text_input("額外 AI 指令")
            st.info("🔓 管理員模式：可調用 AI 算力。")
            if st.button("🚀 啟動 AI 專業生成", type="primary", use_container_width=True):
                if not st.session_state.manual_input_content and not uploaded_file:
                    st.warning("⚠️ 請提供素材")
                else:
                    with st.spinner("🤖 AI 排版中..."):
                        image_obj = Image.open(uploaded_file) if uploaded_file else None
                        res = handout_ai_generate(image_obj, st.session_state.manual_input_content, ai_instr)
                        st.session_state.generated_text = res
                        st.success("✅ 生成成功！")
                        st.rerun()
        else:
            st.warning("🔒 **AI 生成功能僅限管理員使用**")
            st.caption("訪客可手動編輯、上傳圖片並免費下載 PDF。")

    with col_prev:
        st.subheader("2. A4 預覽與修訂")
        preview_source = st.session_state.generated_text if st.session_state.generated_text else st.session_state.manual_input_content
        if not preview_source: preview_source = "### 預覽區\n請在左側輸入內容，或從單字解碼跳轉。"
        
        edited_content = st.text_area("📝 講義內容編輯", value=preview_source, height=450, key="preview_editor")
        default_title = "AI 專題講義"
        if edited_content:
            line = edited_content.split('\n')[0].replace('#', '').strip()
            if line: default_title = line
        handout_title = st.text_input("講義標題", value=default_title)
        
        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)
        components.html(final_html, height=1000, scrolling=True)

def render_login_ui():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = "訪客"
        st.session_state.role = "guest"

    if not st.session_state.logged_in:
        with st.sidebar.expander("👤 管理員 / 會員登入 (選用)", expanded=False):
            with st.form("sidebar_login"):
                u = st.text_input("帳號")
                p = st.text_input("密碼", type="password")
                if st.form_submit_button("登入"):
                    users = load_user_db()
                    hashed = hash_password(p)
                    user = users[(users['username'] == u) & (users['password'] == hashed)]
                    if not user.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.session_state.role = str(user.iloc[0]['role']).lower()
                        st.session_state.is_admin = (st.session_state.role == 'admin')
                        st.rerun()
                    else: st.error("登入失敗")
    else:
        st.sidebar.caption(f"👤 {st.session_state.username} ({st.session_state.role})")
        if st.sidebar.button("登出", key="logout_mini"):
            st.session_state.logged_in = False
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.session_state.is_admin = False
            st.rerun()

# ==========================================
# 6. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    modes = ["Etymon Decoder (單字解碼)", "Handout Pro (講義排版)"]
    
    if 'app_mode' not in st.session_state: st.session_state.app_mode = modes[0]
    if 'is_admin' not in st.session_state: st.session_state.is_admin = False

    with st.sidebar:
        render_login_ui()
        st.sidebar.title("🏫 AI 教育工作站")
        st.markdown("### 💖 隨喜贊助")
        st.markdown(f"""
            <div class="sponsor-container">
                <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" class="btn-ecpay">💳 綠界贊助</a>
                <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" class="btn-bmc">☕ BMC</a>
            </div>
        """, unsafe_allow_html=True)
        st.caption("本站完全免費。您的贊助將用於支持 AI 算力支出，感謝！")
        st.markdown("---")

        try: idx = modes.index(st.session_state.app_mode)
        except: idx = 0
        selected_mode = st.selectbox("切換工具", modes, index=idx)
        st.session_state.app_mode = selected_mode
        
        st.markdown("---")
        with st.expander("🔐 管理員登入"):
            pwd = st.text_input("管理密碼", type="password")
            if pwd == st.secrets.get("ADMIN_PASSWORD", "0000"):
                st.session_state.is_admin = True
                st.success("上帝模式")
            else:
                st.session_state.is_admin = False
                if pwd: st.error("密碼錯誤")

    if st.session_state.app_mode == "Etymon Decoder (單字解碼)":
        df = load_db()
        menu = ["首頁", "學習與搜尋", "測驗模式"]
        if st.session_state.is_admin: menu.append("🔬 解碼實驗室")
        page = st.sidebar.radio("選單", menu)
        
        if page == "首頁": page_etymon_home(df)
        elif page == "學習與搜尋": page_etymon_learn(df)
        elif page == "測驗模式": page_etymon_quiz(df)
        elif page == "🔬 解碼實驗室": page_etymon_lab()
            
    elif st.session_state.app_mode == "Handout Pro (講義排版)":
        run_handout_app()

if __name__ == "__main__":
    main()
