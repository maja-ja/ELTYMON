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
# 1. 核心配置與視覺美化 (CSS)
# ==========================================
st.set_page_config(page_title="AI 教育工作站", page_icon="🏫", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@500;700&display=swap');
            /* ... (此處省略部分重複的 CSS 樣式以節省空間) ... */
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1A237E; }
            .vibe-box { background-color: #F0F7FF; padding: 20px; border-radius: 12px; border-left: 6px solid #2196F3; margin: 15px 0; }
            .breakdown-wrapper { background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%); padding: 25px 30px; border-radius: 15px; color: white !important; }
            .sponsor-container { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
            .btn-ecpay { background-color: #00A650; color: white !important; text-decoration: none; padding: 10px 15px; border-radius: 8px; font-weight: bold; text-align: center; }
            .btn-bmc { background-color: #FFDD00; color: black !important; text-decoration: none; padding: 10px 15px; border-radius: 8px; font-weight: bold; text-align: center; display: flex; align-items: center; justify-content: center; gap: 8px; }
            .btn-icon { width: 20px; height: 20px; }
            @media (prefers-color-scheme: dark) {
                .hero-word { color: #90CAF9 !important; }
                .vibe-box { background-color: #1E262E !important; border-left: 6px solid #64B5F6 !important; }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 共用工具與核心函式 (邏輯保留)
# ==========================================

def get_gemini_keys():
    """獲取並隨機打亂 API Keys"""
    keys = st.secrets.get("GEMINI_FREE_KEYS", [])
    if isinstance(keys, str): keys = [keys]
    random.shuffle(keys)
    return keys

def fix_content(text):
    """處理 JSON 字串與 Markdown 換行"""
    if text is None or str(text).strip().lower() in ["無", "nan", ""]: return ""
    text = str(text).replace('\\\\', '\\').replace('\\n', '\n').replace('\n', '  \n')
    return text.strip('"\' ')

def speak(text, key_suffix=""):
    """TTS 發音生成"""
    english_only = re.sub(r"[^a-zA-Z0-9\s'-]", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        components.html(f'<button onclick="document.getElementById(\'{unique_id}\').play()">🔊 聽發音</button><audio id="{unique_id}" src="data:audio/mp3;base64,{audio_base64}"></audio>', height=40)
    except Exception as e:
        print(f"TTS Error: {e}")

def get_spreadsheet_url():
    """安全地獲取 Google Sheets URL"""
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except KeyError: return st.secrets.get("gsheets", {}).get("spreadsheet")

@st.cache_data(ttl=300)
def load_etymon_db():
    """從 Google Sheets 載入知識百科資料庫"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        # 確保核心欄位存在
        for col in ['word', 'definition', 'category', 'roots']:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無").reset_index(drop=True)
    except Exception as e:
        st.error(f"資料庫載入失敗: {e}")
        return pd.DataFrame(columns=['word', 'definition', 'category', 'roots'])

# ==========================================
# 3. Etymon 知識百科模組
# ==========================================

def ai_decode_term(input_text, category):
    """AI 核心解碼函式 (保留過去的穩定 Prompt)"""
    keys = get_gemini_keys()
    if not keys:
        st.error("找不到 Gemini API Keys，請檢查 Streamlit Secrets 設定。")
        return None

    SYSTEM_PROMPT = f"""
    Role: 全領域知識解構專家. Task: 深度分析輸入內容，並將其解構為高品質的 JSON。
    【領域鎖定】：你目前的身份是「{category}」專家。
    ## 輸出規範 (Strict JSON Rules):
    1. **必須輸出純 JSON 格式**，嚴禁包含任何 Markdown 標記（如 ```json）。
    2. **LaTeX 雙重轉義**: 所有 LaTeX 指令必須使用「雙反斜線」(例如: "\\\\frac")。
    3. **換行處理**: JSON 內部換行請統一使用 "\\\\n"。
    ## 欄位定義:
    - category: "{category}"
    - word: 核心概念名稱
    - roots: 底層邏輯/關鍵公式 (使用 LaTeX)
    - meaning: 核心本質意義
    - breakdown: 結構拆解 (用 \\\\n 分隔)
    - definition: 給五歲小孩的解釋 (ELI5)
    - phonetic: 發音或背景
    - example: 實際應用場景
    - translation: 「🍎 生活比喻：」開頭
    - native_vibe: 「🌊 專家心法：」開頭
    - synonym_nuance: 相似概念辨析
    - usage_warning: 邊界條件
    - memory_hook: 記憶金句
    """
    last_error = "未知錯誤"
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」")
            clean_json = re.sub(r'^```json\s*|\s*```$', '', response.text.strip(), flags=re.M)
            json.loads(clean_json) # 驗證 JSON 格式
            return clean_json
        except Exception as e:
            last_error = str(e)
            continue
    st.error(f"所有 API Key 皆嘗試失敗。最後錯誤: {last_error}")
    return None

def display_etymon_card(row):
    """顯示單張知識卡片 (保留過去的穩定 UI)"""
    r_word = str(row.get('word', 'N/A'))
    r_phonetic = fix_content(row.get('phonetic', ''))
    r_breakdown = fix_content(row.get('breakdown', ''))
    r_def = fix_content(row.get('definition', ''))
    r_meaning = str(row.get('meaning', ''))
    r_hook = fix_content(row.get('memory_hook', ''))
    r_vibe = fix_content(row.get('native_vibe', ''))
    r_ex = fix_content(row.get('example', ''))
    
    raw_roots = fix_content(row.get('roots', ''))
    clean_roots = raw_roots.replace('$', '').strip()
    r_roots = f"$${clean_roots}$$" if clean_roots else "（無公式或原理）"

    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    if r_phonetic != "無": st.caption(f"/{r_phonetic}/")

    st.markdown(f"<div class='breakdown-wrapper'><h4>🧬 邏輯拆解</h4>{r_breakdown}</div>", unsafe_allow_html=True)
    st.write("")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🎯 定義與解釋")
        st.write(r_def)
        if r_ex and r_ex != "無": st.info(f"💡 **應用實例：**\n{r_ex}")
    with c2:
        st.markdown("### 💡 核心原理")
        st.markdown(r_roots)
        st.write(f"**🔍 本質意義：** {r_meaning}")
        st.write(f"**🪝 記憶鉤子：** {r_hook}")

    if r_vibe and r_vibe != "無":
        st.markdown(f"<div class='vibe-box'><h4>🌊 專家視角</h4>{r_vibe}</div>", unsafe_allow_html=True)
    
    with st.expander("🔍 深度百科 (辨析、邊界條件)"):
        st.markdown(f"**⚖️ 相似對比：** \n{fix_content(row.get('synonym_nuance', '無'))}")
        st.markdown(f"**⚠️ 使用注意：** \n{fix_content(row.get('usage_warning', '無'))}")
    
    speak(r_word, f"card_{r_word}")
    st.divider()

def run_etymon_app(df):
    """Etymon 知識百科主應用程式"""
    st.title("📚 Etymon 知識百科全書")
    st.info("您可以在此查詢已建立的知識卡，或透過 AI 新增知識到共享資料庫中。")
    
    tab_learn, tab_create = st.tabs(["🔍 查詢與學習", "🔬 新增知識卡"])

    with tab_learn:
        st.subheader("隨機探索或精確搜尋")
        
        # 搜尋功能
        search_query = st.text_input("搜尋知識庫...", placeholder="輸入關鍵字，例如 '熵' 或 '光合作用'")
        if search_query:
            query_clean = search_query.strip().lower()
            mask = df.apply(lambda row: row.astype(str).str.lower().str.contains(query_clean).any(), axis=1)
            results = df[mask]
            st.write(f"找到 {len(results)} 筆相關結果：")
            for _, row in results.iterrows():
                with st.container(border=True):
                    display_etymon_card(row.to_dict())
        else:
            # 隨機探索
            if st.button("🎲 隨機來一張知識卡", use_container_width=True, type="primary"):
                if not df.empty:
                    st.session_state.random_card = df.sample(1).iloc.to_dict()
            
            if 'random_card' in st.session_state and st.session_state.random_card:
                with st.container(border=True):
                    display_etymon_card(st.session_state.random_card)

    with tab_create:
        st.subheader("透過 AI 新增知識")
        with st.form("create_form"):
            new_term = st.text_input("輸入想解構的新主題：", placeholder="例如: '貝氏定理'、'馬基維利主義'...")
            
            categories = sorted(df['category'].unique().tolist())
            if "自定義" not in categories: categories.append("自定義")
            selected_category = st.selectbox("選定領域標籤", categories)
            
            final_category = st.text_input("若選自定義，請輸入領域名稱：") if selected_category == "自定義" else selected_category
            
            force_refresh = st.checkbox("🔄 強制刷新 (若主題已存在，用新資料覆蓋)")
            
            submitted = st.form_submit_button("🚀 啟動 AI 解碼", use_container_width=True)

            if submitted and new_term and final_category:
                is_exist = not df.empty and (df['word'].astype(str).str.lower() == new_term.lower()).any()
                
                if is_exist and not force_refresh:
                    st.warning(f"「{new_term}」已存在知識庫中。如需更新請勾選「強制刷新」。")
                    display_etymon_card(df[df['word'].astype(str).str.lower() == new_term.lower()].iloc.to_dict())
                else:
                    with st.spinner(f"正在以【{final_category}】視角解構「{new_term}」..."):
                        json_res = ai_decode_term(new_term, final_category)
                        if json_res:
                            try:
                                new_data = json.loads(json_res)
                                conn = st.connection("gsheets", type=GSheetsConnection)
                                current_df = conn.read(ttl=0)
                                
                                if is_exist and force_refresh:
                                    current_df = current_df[current_df['word'].astype(str).str.lower() != new_term.lower()]
                                
                                updated_df = pd.concat([current_df, pd.DataFrame([new_data])], ignore_index=True)
                                conn.update(data=updated_df)
                                
                                st.success(f"🎉 「{new_term}」解碼完成並已存入雲端！")
                                st.balloons()
                                st.cache_data.clear() # 清除快取以便下次載入最新資料
                                display_etymon_card(new_data)
                            except Exception as e:
                                st.error(f"寫入資料庫失敗: {e}")
                                st.code(json_res)

# ==========================================
# 4. Handout AI 講義生成模組
# ==========================================

def handout_ai_generate(image, manual_input, instruction):
    """Handout AI 核心 (保留過去的穩定 Prompt)"""
    keys = get_gemini_keys()
    if not keys: return "❌ 錯誤：API Key 未設定"
    prompt = """
    你是一位專業的講義排版專家。請根據輸入素材撰寫一份結構清晰、排版完美的 Markdown 講義。
    【⚠️ 絕對排版紅線】:
    1. **行內公式**: 必須用 `$` 包裹, 如 `$E=mc^2$`。
    2. **區塊公式**: 必須用 `$$` 包裹並獨立成行。
    3. **標題**: 僅使用 Markdown 的 `#`, `##`, `###`。
    【內容要求】：語氣專業且教學導向，直接輸出內容，不要有「好的，這是您的講義」等廢話。
    """
    parts = [prompt, f"【講義素材】：\n{manual_input}", f"【額外排版要求】：{instruction}"]
    if image: parts.append(image)

    last_error = "未知錯誤"
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(parts)
            return response.text
        except Exception as e:
            last_error = str(e)
            continue
    return f"AI 異常: {last_error}"

def generate_printable_html(title, text_content, img_b64, img_width_percent, auto_download=False):
    """生成可列印的 HTML (保留過去的穩定渲染邏輯)"""
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    auto_js = "setTimeout(downloadPDF, 500);" if auto_download else ""
    return f"""
    <html><head>
        <script>
            window.MathJax = {{ tex: {{ inlineMath: [['$', '$']], displayMath: [['$$', '$$']] }}, chtml: {{ scale: 1.1 }} }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            @page {{ size: A4; margin: 0; }} body {{ background: #555; display: flex; justify-content: center; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; margin: 20px 0; padding: 20mm; box-sizing: border-box; box-shadow: 0 0 10px rgba(0,0,0,0.5); }}
            h1 {{ text-align: center; }} .content {{ font-size: 16px; line-height: 1.8; }}
        </style>
    </head><body>
        <div id="printable-area">
            <h1>{title}</h1>
            {f'<img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%; display:block; margin:auto;">' if img_b64 else ""}
            <div class="content">{html_body}</div>
        </div>
        <script>
            function downloadPDF() {{
                const el = document.getElementById('printable-area');
                html2pdf().set({{ filename: '{title}.pdf', jsPDF: {{ format: 'a4' }}, html2canvas: {{ scale: 2 }} }}).from(el).save();
            }}
            {auto_js}
        </script>
    </body></html>"""

def run_handout_app():
    """Handout AI 講義生成主應用程式"""
    st.title("🎓 AI 講義排版大師")
    st.info("上傳圖片或貼上文字素材，AI 將為您自動生成結構化、排版優美的 Markdown 講義，並可直接下載為 PDF。")

    # 初始化 session state
    for key, default_val in [("preview_editor", ""), ("handout_title", "AI 專題講義"), ("trigger_download", False)]:
        if key not in st.session_state: st.session_state[key] = default_val

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")

    with col_ctrl:
        st.subheader("1. 素材與控制")
        uploaded_file = st.file_uploader("上傳圖片 (可選)", type=["jpg", "png", "jpeg"])
        image = Image.open(uploaded_file) if uploaded_file else None
        if image: st.image(image, "上傳的圖片", use_container_width=True)

        manual_input = st.text_area("或貼上文字素材", height=200, placeholder="將您的筆記、題目、文章貼在這裡...")
        instruction = st.text_input("額外指令 (可選)", placeholder="例如：請將內容整理成三大重點，並附上練習題。")
        
        if st.button("🚀 啟動 AI 生成講義", type="primary", use_container_width=True):
            if not manual_input and not image:
                st.warning("請至少提供文字素材或上傳一張圖片。")
            else:
                with st.spinner("🤖 AI 正在撰寫與排版講義..."):
                    generated_res = handout_ai_generate(image, manual_input, instruction)
                    st.session_state.preview_editor = generated_res
                    # 自動抓取第一行當標題
                    first_line = generated_res.split('\n').replace('#', '').strip()
                    if first_line: st.session_state.handout_title = first_line

    with col_prev:
        st.subheader("2. 預覽、修訂與下載")
        
        st.session_state.handout_title = st.text_input("講義標題", value=st.session_state.handout_title)
        
        edited_content = st.text_area("內容編輯器 (可在此手動修改)", value=st.session_state.preview_editor, height=500)
        
        if st.button("📥 下載講義 PDF", use_container_width=True):
            st.session_state.trigger_download = True
        
        img_b64 = base64.b64encode(uploaded_file.getvalue()).decode() if uploaded_file else ""
        
        if edited_content:
            final_html = generate_printable_html(
                title=st.session_state.handout_title,
                text_content=edited_content,
                img_b64=img_b64,
                img_width_percent=80,
                auto_download=st.session_state.trigger_download
            )
            components.html(final_html, height=800, scrolling=True)

        if st.session_state.trigger_download:
            st.session_state.trigger_download = False

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_custom_css()

    st.sidebar.title("🏫 AI 教育工作站")
    st.sidebar.markdown("一個整合了知識學習與內容創作的 AI 工具。")

    app_mode = st.sidebar.radio(
        "選擇功能模組",
        ("📚 Etymon 知識百科", "🎓 AI 講義生成")
    )
    
    st.sidebar.divider()
    st.sidebar.markdown("### 💖 隨喜贊助")
    st.sidebar.markdown("""
        本站所有功能皆免費使用。若您覺得有幫助，您的支持是我們持續開發與維護 AI 算力的最大動力！
        <div class="sponsor-container">
            <a href="#" target="_blank" class="btn-ecpay">💳 綠界 ECPay</a>
            <a href="#" target="_blank" class="btn-bmc">
                <img src="https://cdn.buymeacoffee.com/buttons/bmc-new-btn-logo.svg" class="btn-icon">
                Buy Me a Coffee
            </a>
        </div>
    """, unsafe_allow_html=True)
    st.sidebar.divider()
    st.sidebar.caption("v5.0 Streamlined | Public Access")

    if app_mode == "📚 Etymon 知識百科":
        etymon_df = load_etymon_db()
        run_etymon_app(etymon_df)
    elif app_mode == "🎓 AI 講義生成":
        run_handout_app()

if __name__ == "__main__":
    main()
