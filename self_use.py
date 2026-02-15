import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
from io import BytesIO
from PIL import Image, ImageOps
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown

# ==========================================
# 1. 核心配置與視覺美化
# ==========================================
st.set_page_config(page_title="個人AI工作站", page_icon="🚀", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1A237E; }
            .vibe-box { background-color: #F0F7FF; padding: 20px; border-radius: 12px; border-left: 6px solid #2196F3; margin: 15px 0; }
            .breakdown-wrapper { background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%); padding: 25px 30px; border-radius: 15px; color: white !important; }
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #90CAF9 !important; }
                .vibe-box { background-color: #1E262E !important; border-left: 6px solid #64B5F6 !important; }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 共用工具與核心函式
# ==========================================
def get_gemini_keys():
    keys = st.secrets.get("GEMINI_FREE_KEYS", [])
    if isinstance(keys, str): keys = [keys]
    random.shuffle(keys)
    if not keys: st.error("尚未設定 Gemini API Keys！")
    return keys

def fix_content(text):
    if text is None or str(text).strip().lower() in ["無", "nan", ""]: return ""
    text = str(text).replace('\\\\', '\\').replace('\\n', '\n').replace('\n', '  \n')
    return text.strip('"\' ')

def speak(text, key_suffix=""):
    english_only = re.sub(r"[^a-zA-Z0-9\s'-]", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        components.html(f'<button onclick="document.getElementById(\'{unique_id}\').play()">🔊 聽發音</button><audio id="{unique_id}" src="data:audio/mp3;base64,{audio_base64}"></audio>', height=40)
    except Exception as e: print(f"TTS Error: {e}")

@st.cache_data(ttl=300)
def load_etymon_db():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        for col in ['word', 'definition', 'category', 'roots']:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無").reset_index(drop=True)
    except Exception as e:
        st.error(f"資料庫載入失敗: {e}")
        return pd.DataFrame()

# ==========================================
# 3. 知識百科 (Etymon) 模組
# ==========================================
def ai_decode_term(input_text, category):
    keys = get_gemini_keys()
    if not keys: return None
    SYSTEM_PROMPT = f"""Role: Polymath Decoder. Task: Analyze input and structure it into a high-quality JSON. Domain: "{category}". Rules: Pure JSON output only. Use "\\\\LaTeX" for LaTeX commands. Use "\\n" for newlines. Fields: category, word, roots, meaning, breakdown, definition, phonetic, example, translation, native_vibe, synonym_nuance, usage_warning, memory_hook."""
    last_error = "Unknown error"
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(f"{SYSTEM_PROMPT}\n\nDecode: '{input_text}'")
            clean_json = re.sub(r'^```json\s*|\s*```$', '', response.text.strip(), flags=re.M)
            json.loads(clean_json)
            return clean_json
        except Exception as e:
            last_error = str(e)
            continue
    st.error(f"All API Keys failed. Last error: {last_error}")
    return None

def display_etymon_card(row):
    r_word, r_phonetic, r_breakdown, r_def, r_meaning, r_hook, r_vibe, r_ex = (
        str(row.get('word', 'N/A')), fix_content(row.get('phonetic', '')), fix_content(row.get('breakdown', '')),
        fix_content(row.get('definition', '')), str(row.get('meaning', '')), fix_content(row.get('memory_hook', '')),
        fix_content(row.get('native_vibe', '')), fix_content(row.get('example', ''))
    )
    r_roots = f"$${fix_content(row.get('roots', '')).replace('$', '').strip()}$$" if row.get('roots') else "（無）"

    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    if r_phonetic != "無": st.caption(f"/{r_phonetic}/")
    st.markdown(f"<div class='breakdown-wrapper'><h4>🧬 邏輯拆解</h4>{r_breakdown}</div>", unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🎯 定義與解釋"); st.write(r_def)
        if r_ex and r_ex != "無": st.info(f"💡 **應用實例：**\n{r_ex}")
    with c2:
        st.markdown("##### 💡 核心原理"); st.markdown(r_roots)
        st.write(f"**🔍 本質意義：** {r_meaning}"); st.write(f"**🪝 記憶鉤子：** {r_hook}")

    if r_vibe and r_vibe != "無":
        st.markdown(f"<div class='vibe-box'><h4>🌊 專家視角</h4>{r_vibe}</div>", unsafe_allow_html=True)

    b1, b2 = st.columns(2)
    with b1: speak(r_word, f"card_{r_word}")
    with b2:
        if st.button("📄 生成講義", key=f"gen_{r_word}", use_container_width=True, type="primary"):
            handout_draft = (
                f"# {r_word}\n\n"
                f"## 核心定義\n{r_def}\n\n"
                f"## 邏輯拆解\n{r_breakdown}\n\n"
                f"## 核心原理\n{r_roots}\n\n"
                f"### 本質意義\n{r_meaning}\n\n"
                f"### 應用實例\n{r_ex}\n\n"
                f"### 專家視角\n{r_vibe}"
            )
            st.session_state.handout_draft = handout_draft
            st.session_state.app_mode = "🎓 AI 講義排版大師"
            st.rerun()
    st.divider()

def run_etymon_app(df):
    st.title("📚 知識百科")
    tab_learn, tab_create = st.tabs(["🔍 查詢與學習", "🔬 新增知識"])

    with tab_learn:
        search_query = st.text_input("搜尋知識庫...", placeholder="輸入關鍵字...")
        if search_query:
            mask = df.apply(lambda row: row.astype(str).str.lower().str.contains(search_query.strip().lower()).any(), axis=1)
            results = df[mask]
            st.write(f"找到 {len(results)} 筆結果：")
            for _, row in results.iterrows():
                display_etymon_card(row.to_dict())
        else:
            if st.button("🎲 隨機探索", use_container_width=True):
                st.session_state.random_card = df.sample(1).iloc[0].to_dict() if not df.empty else None
            if 'random_card' in st.session_state and st.session_state.random_card:
                display_etymon_card(st.session_state.random_card)

    with tab_create:
        with st.form("create_form"):
            new_term = st.text_input("輸入新主題：", placeholder="例如: 貝氏定理...")
            categories = sorted(df['category'].unique().tolist()) + ["自定義"]
            selected_cat = st.selectbox("選定領域", categories)
            final_cat = st.text_input("自定義領域名稱：") if selected_cat == "自定義" else selected_cat
            force_refresh = st.checkbox("🔄 強制刷新 (覆蓋舊資料)")
            if st.form_submit_button("🚀 啟動 AI 解碼", use_container_width=True):
                if new_term and final_cat:
                    with st.spinner(f"正在解構「{new_term}」..."):
                        json_res = ai_decode_term(new_term, final_cat)
                        if json_res:
                            new_data = json.loads(json_res)
                            conn = st.connection("gsheets", type=GSheetsConnection)
                            current_df = conn.read(ttl=0)
                            if not force_refresh and (current_df['word'].astype(str).str.lower() == new_term.lower()).any():
                                st.warning(f"「{new_term}」已存在。")
                            else:
                                current_df = current_df[current_df['word'].astype(str).str.lower() != new_term.lower()]
                                updated_df = pd.concat([current_df, pd.DataFrame([new_data])], ignore_index=True)
                                conn.update(data=updated_df)
                                st.success("新增成功！")
                                st.cache_data.clear()

# ==========================================
# 4. 講義生成 (Handout) 模組
# ==========================================
def handout_ai_generate(image, manual_input, instruction):
    keys = get_gemini_keys()
    if not keys: return "❌ API Key 未設定"
    prompt = "You are a professional handout layout expert. Create a well-structured Markdown handout from the provided materials. Rules: Use `$` for inline math, `$$` for block math, and `#`/`##` for titles. Be professional and instructive. Output content directly."
    parts = [prompt, f"Materials:\n{manual_input}", f"Instructions: {instruction}"]
    if image: parts.append(image)
    try:
        genai.configure(api_key=keys[0])
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(parts).text
    except Exception as e: return f"AI Error: {e}"

def generate_printable_html(title, text, img_b64, auto_download=False):
    html_body = markdown.markdown(text, extensions=['fenced_code', 'tables'])
    auto_js = "setTimeout(() => downloadPDF(), 500);" if auto_download else ""
    return f"""<html><head>
        <script>window.MathJax={{tex:{{inlineMath:[['$','$']],displayMath:[['$$','$$']]}},chtml:{{scale:1.1}}}};</script>
        <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>@page{{size:A4;margin:0}} body{{background:#555;display:flex;justify-content:center}} #p{{background:white;width:210mm;min-height:297mm;margin:20px 0;padding:20mm;box-sizing:border-box}} h1{{text-align:center}}</style>
    </head><body><div id="p"><h1>{title}</h1>{f'<img src="data:image/jpeg;base64,{img_b64}" style="width:80%;display:block;margin:auto;">' if img_b64 else ""}<div>{html_body}</div></div>
    <script>function downloadPDF(){{html2pdf().set({{filename:'{title}.pdf',jsPDF:{{format:'a4'}},html2canvas:{{scale:2}}}}).from(document.getElementById('p')).save()}} {auto_js}</script>
    </body></html>"""

def run_handout_app():
    st.title("🎓 AI 講義排版大師")

    # 檢查是否有來自 Etymon 的草稿
    if "handout_draft" in st.session_state and st.session_state.handout_draft:
        st.session_state.preview_editor = st.session_state.handout_draft
        del st.session_state.handout_draft # 使用後即刪除

    # 初始化
    if "preview_editor" not in st.session_state: st.session_state.preview_editor = ""
    if "handout_title" not in st.session_state: st.session_state.handout_title = "AI 專題講義"

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    with col_ctrl:
        st.subheader("1. 素材與控制")
        uploaded_file = st.file_uploader("上傳圖片 (可選)", type=["jpg", "png", "jpeg"])
        image = Image.open(uploaded_file) if uploaded_file else None
        if image: st.image(image, use_container_width=True)
        manual_input = st.text_area("或貼上文字素材", height=200)
        instruction = st.text_input("額外指令", placeholder="例如：整理成三大重點...")
        if st.button("🚀 啟動 AI 生成", type="primary", use_container_width=True):
            with st.spinner("🤖 AI 正在撰寫講義..."):
                generated_res = handout_ai_generate(image, manual_input, instruction)
                st.session_state.preview_editor = generated_res
                first_line = generated_res.split('\n')[0].replace('#', '').strip()
                if first_line: st.session_state.handout_title = first_line

    with col_prev:
        st.subheader("2. 預覽與輸出")
        st.session_state.handout_title = st.text_input("講義標題", st.session_state.handout_title)
        edited_content = st.text_area("內容編輯器", st.session_state.preview_editor, height=500, key="preview_editor")
        if st.button("📥 下載 PDF", use_container_width=True):
            img_b64 = base64.b64encode(uploaded_file.getvalue()).decode() if uploaded_file else ""
            html = generate_printable_html(st.session_state.handout_title, edited_content, img_b64, auto_download=True)
            components.html(html, height=0)

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    st.sidebar.title("🚀 個人AI工作站")
    
    # 使用 st.session_state 來控制 radio 的選擇，以便程式可以更改它
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = "📚 知識百科"

    selected_mode = st.sidebar.radio(
        "選擇功能模組",
        ("📚 知識百科", "🎓 AI 講義排版大師"),
        key='app_mode'
    )
    
    st.sidebar.divider()
    st.sidebar.caption("v6.0 Personal Edition")

    if selected_mode == "📚 知識百科":
        etymon_df = load_etymon_db()
        if not etymon_df.empty:
            run_etymon_app(etymon_df)
    elif selected_mode == "🎓 AI 講義排版大師":
        run_handout_app()

if __name__ == "__main__":
    main()
