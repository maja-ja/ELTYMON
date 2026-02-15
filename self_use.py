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
st.set_page_config(page_title="個人 AI 教育工作站", page_icon="🚀", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@500;700&display=swap');
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1A237E; margin-bottom: 5px; }
            .vibe-box { background-color: #F0F7FF; padding: 20px; border-radius: 12px; border-left: 6px solid #2196F3; color: #2C3E50 !important; margin: 15px 0; }
            .breakdown-wrapper { background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%); padding: 25px 30px; border-radius: 15px; color: white !important; }
            .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 共用工具函式
# ==========================================
def get_gemini_keys():
    keys = st.secrets.get("GEMINI_FREE_KEYS")
    if not keys: keys = [st.secrets.get("GEMINI_API_KEY")]
    if isinstance(keys, str): keys = [keys]
    shuffled = keys.copy()
    random.shuffle(shuffled)
    return shuffled

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    text = str(text).replace('\\\\', '\\').replace('\\n', '\n').replace('\n', '  \n')
    return text.strip('"').strip("'").strip()

def speak(text, key_suffix=""):
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        uid = f"audio_{int(time.time()*1000)}_{key_suffix}"
        components.html(f'<button onclick="document.getElementById(\'{uid}\').play()">🔊 聽發音</button><audio id="{uid}" src="data:audio/mp3;base64,{audio_base64}"></audio>', height=40)
    except: pass

@st.cache_data(ttl=360) 
def load_db():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        return df.dropna(subset=['word']).fillna("無").reset_index(drop=True)
    except:
        return pd.DataFrame()

# ==========================================
# 3. Etymon AI 解碼邏輯 (不直接儲存)
# ==========================================
def ai_decode_only(input_text, category):
    keys = get_gemini_keys()
    if not keys: return None
    PROMPT = f"""Role: Polymath Decoder. Task: Analyze the concept and return a structure JSON. Domain: {category}.
    Rules: Pure JSON output. LaTeX must use double backslash (e.g. \\\\frac).
    Fields: category, word, roots, meaning, breakdown, definition, phonetic, example, translation, native_vibe, synonym_nuance, usage_warning, memory_hook."""
    
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(f"{PROMPT}\n\nTarget: {input_text}")
            clean_json = re.sub(r'^```json\s*|\s*```$', '', res.text.strip(), flags=re.MULTILINE)
            return json.loads(clean_json)
        except: continue
    return None

def show_encyclopedia_card(row):
    r_word = row.get('word', '未命名')
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='breakdown-wrapper'><h4>🧬 邏輯拆解</h4>{fix_content(row.get('breakdown',''))}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🎯 定義")
        st.write(fix_content(row.get('definition','')))
    with c2:
        st.markdown("### 💡 核心原理")
        st.markdown(f"$${fix_content(row.get('roots','')).replace('$','')}$$")
        st.write(f"**🔍 本質：** {row.get('meaning','')}")

    if row.get('native_vibe') != "無":
        st.markdown(f"<div class='vibe-box'><h4>🌊 專家心法</h4>{fix_content(row.get('native_vibe',''))}</div>", unsafe_allow_html=True)
    
    speak(r_word, f"card_{r_word}")

# ==========================================
# 4. 頁面函式
# ==========================================

def page_learn(df):
    st.title("📖 知識庫搜尋")
    search_query = st.text_input("🔍 模糊搜尋 (輸入多個關鍵字以空格分開，例如：物理 能量)", placeholder="例如：熵 物理")
    
    if search_query:
        # --- 核心優化：模糊搜尋邏輯 ---
        keywords = search_query.lower().split()
        mask = df.astype(str).apply(lambda x: all(k in x.str.lower().to_string() for k in keywords), axis=1)
        res = df[mask]
        
        if not res.empty:
            st.info(f"找到 {len(res)} 筆結果")
            for _, row in res.iterrows():
                with st.container(border=True): show_encyclopedia_card(row)
        else:
            st.warning("查無結果")
    else:
        st.dataframe(df[['word', 'category', 'definition']], use_container_width=True)
def page_lab(df):
    st.title("🔬 解碼實驗室 (先編輯，後儲存)")
    st.info("輸入主題後，系統會自動預查資料庫。若已存在，您可以選擇跳過或重新解碼。")

    col1, col2 = st.columns([2, 1])
    with col1: 
        target = st.text_input("輸入解碼主題", placeholder="例如：熵、貝氏定理...", key="lab_target")
    with col2: 
        cat = st.selectbox("預設分類", ["物理科學", "英語辭源", "程式開發", "人工智慧", "自定義"])

    # --- 核心優化：回覆預查功能 ---
    has_existing = False
    if target.strip():
        # 進行精確匹配預查 (不分大小寫)
        existing_match = df[df['word'].str.lower() == target.lower().strip()]
        
        if not existing_match.empty:
            has_existing = True
            st.warning(f"⚠️ 預查發現：書架上已有「{target}」的解碼資料。")
            with st.expander("查看現有內容", expanded=False):
                show_encyclopedia_card(existing_match.iloc[0])
            
            re_decode_confirm = st.checkbox("我確認要「重新解碼」並覆蓋舊資料", value=False)
            if not re_decode_confirm:
                st.info("💡 若內容無誤，您可以直接切換到「講義排版」使用。")
        else:
            st.success(f"🔍 預查確認：這是全新的主題，準備啟動 AI 解碼。")

    # --- 啟動解碼按鈕邏輯 ---
    # 若已有資料且未勾選重新解碼，則禁用按鈕或不執行
    can_decode = True
    if has_existing and not locals().get('re_decode_confirm', False):
        can_decode = False

    if st.button("🚀 啟動 AI 解碼", type="primary", disabled=not target.strip() or (has_existing and not can_decode)):
        with st.spinner(f"正在透過 AI 深入解析「{target}」..."):
            draft = ai_decode_only(target, cat)
            if draft: 
                st.session_state.temp_draft = draft
                st.toast("AI 草稿生成完畢！")
            else: 
                st.error("AI 沒回應，可能是 API Key 額度問題或網路異常。")

    # --- 編輯與儲存區 (保持不變) ---
    if "temp_draft" in st.session_state:
        st.divider()
        st.subheader("📝 AI 草稿編輯區")
        st.caption("您可以修改下方內容，確認完美後再點擊儲存。")
        
        d = st.session_state.temp_draft
        
        col_edit1, col_edit2 = st.columns(2)
        with col_edit1:
            e_word = st.text_input("主題名稱 (Word)", d.get('word'))
            e_phonetic = st.text_input("發音背景 (Phonetic)", d.get('phonetic'))
            e_roots = st.text_input("核心原理 (LaTeX 格式)", d.get('roots'))
        with col_edit2:
            e_cat = st.text_input("最終分類 (Category)", d.get('category'))
            e_meaning = st.text_input("本質意義 (Meaning)", d.get('meaning'))
            e_hook = st.text_input("記憶鉤子 (Memory Hook)", d.get('memory_hook'))

        e_breakdown = st.text_area("邏輯拆解 (使用 \\n 換行)", d.get('breakdown'), height=150)
        e_def = st.text_area("詳細定義 (Definition)", d.get('definition'), height=150)
        e_vibe = st.text_area("專家心法 (Native Vibe)", d.get('native_vibe'), height=150)

        if st.button("✅ 確認無誤，存入雲端書架", use_container_width=True):
            # 構建最終存檔資料
            new_row = d.copy()
            new_row.update({
                "word": e_word, "category": e_cat, "roots": e_roots, 
                "breakdown": e_breakdown, "definition": e_def, 
                "native_vibe": e_vibe, "meaning": e_meaning,
                "phonetic": e_phonetic, "memory_hook": e_hook
            })
            
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                # 再次讀取最新資料以確保寫入位置正確
                latest_df = conn.read(ttl=0)
                # 執行覆蓋邏輯：移除舊的，加上新的
                updated_df = pd.concat([latest_df[latest_df['word'] != e_word], pd.DataFrame([new_row])], ignore_index=True)
                
                conn.update(data=updated_df)
                st.success(f"🎉 儲存成功！「{e_word}」已更新至雲端書架。")
                st.balloons()
                
                # 清理狀態並強制刷新
                if "temp_draft" in st.session_state: del st.session_state.temp_draft
                st.cache_data.clear()
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"儲存到 Google Sheets 時發生錯誤: {e}")

# ==========================================
# 5. Handout 講義排版模組
# ==========================================
def run_handout_app():
    st.title("🎓 AI 講義排版大師 Pro")
    
    # 初始化
    if "preview_editor" not in st.session_state: st.session_state.preview_editor = ""
    if "final_handout_title" not in st.session_state: st.session_state.final_handout_title = "新講義"

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    
    with col_ctrl:
        uploaded_file = st.file_uploader("上傳素材圖片", type=["jpg", "png", "jpeg"])
        manual_input = st.text_area("素材內容", value=st.session_state.get("manual_input_content", ""), height=200)
        
        if st.button("🚀 AI 專業排版", type="primary", use_container_width=True):
            with st.spinner("排版中..."):
                res = handout_ai_generate(Image.open(uploaded_file) if uploaded_file else None, manual_input, "請使用標準 Markdown 排版")
                st.session_state.preview_editor = res
                st.rerun()

    with col_prev:
        edited_content = st.text_area("📝 內容修訂", key="preview_editor", height=500)
        title = st.text_input("講義標題", key="final_handout_title")
        
        if st.button("📥 下載 PDF", use_container_width=True):
            html = generate_printable_html(title, edited_content, "", 80, True)
            components.html(html, height=0)
        
        # 預覽 HTML
        html_preview = generate_printable_html(title, edited_content, "", 80, False)
        components.html(html_preview, height=800, scrolling=True)

def get_image_base64(image):
    if image is None: return ""
    buffered = BytesIO()
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode()

def handout_ai_generate(image, manual_input, instruction):
    """
    Handout AI 核心 (安全排版版)：
    強制區分行內 ($) 與區塊 ($$) 公式，杜絕排版崩壞。
    """
    keys = get_gemini_keys()
    if not keys: return "❌ 錯誤：API Key 未設定"

    # --- 🛡️ 安全排版核心指令 ---
    prompt = """
    你是一位專業的講義排版專家。請根據輸入素材撰寫一份結構清晰、排版完美的講義。
    
    【⚠️ 絕對排版紅線 (必須遵守)】：
    1. **行內公式 (Inline Math)**：
       - 當變數或短公式出現在文字行中間時，**必須**使用單個錢字號 `$ ... $`。
       - 範例：正確為「設電阻為 $R$ 歐姆」，**嚴禁**寫成「設電阻為 $$R$$ 歐姆」(這會導致換行跑版)。
    
    2. **區塊公式 (Block Math)**：
       - 只有長公式或重點推導才使用雙錢字號 `$$ ... $$` 並獨立成行。
       - 範例：
         $$ V = I \times R $$
    
    3. **標題結構**：
       - 僅使用 Markdown 標題 (`#`, `##`, `###`)。
       - **嚴禁**使用 LaTeX 標題指令 (如 `\section`, `\textbf`)。
    
    4. **列表安全**：
       - 在列表 (List) 項目中，盡量避免放入複雜的區塊公式 `$$`，這容易導致 PDF 生成錯誤。若必須放，請確保換行縮排正確。

    【內容要求】：
    - 語氣專業且教學導向。
    - 直接輸出內容，不要有「好的，這是您的講義」等廢話。
    """
    
    parts = [prompt]
    if manual_input: parts.append(f"【講義素材】：\n{manual_input}")
    if instruction: parts.append(f"【額外排版要求】：{instruction}")
    if image: parts.append(image)

    last_error = None
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(parts)
            return response.text
        except Exception as e:
            last_error = e
            continue
    
    return f"AI 異常: {str(last_error)}"
def generate_printable_html(title, text_content, img_b64, img_width_percent, auto_download=False):
    """
    排版修復版：
    1. 改用 tex-chtml (CommonHTML) 引擎，解決 SVG 導致的文字錯位與換行問題。
    2. 增加 CSS 強制修正行內公式的垂直對齊。
    """
    text_content = text_content.strip()
    # 處理換頁符號
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>')
    
    # 將 Markdown 轉為 HTML
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables'])
    
    date_str = time.strftime("%Y-%m-%d")
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 500); };" if auto_download else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Roboto+Mono:wght@400&display=swap" rel="stylesheet">
        
        <!-- 1. MathJax 配置：改用 CHTML (CommonHTML) -->
        <script>
            window.MathJax = {{
                tex: {{ 
                    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                    processEscapes: true
                }},
                chtml: {{ 
                    scale: 1.1,  /* 稍微放大公式 */
                    matchFontHeight: true 
                }},
                options: {{
                    ignoreHtmlClass: 'tex2jax_ignore',
                    processHtmlClass: 'tex2jax_process'
                }}
            }};
        </script>
        <!-- 2. 載入 CHTML 版本的 MathJax -->
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ 
                font-family: 'Noto Sans TC', sans-serif; 
                line-height: 1.8; 
                padding: 0; margin: 0; 
                background: #555; 
                display: flex; flex-direction: column; align-items: center; 
            }}
            #printable-area {{ 
                background: white; 
                width: 210mm; min-height: 297mm; 
                margin: 20px 0; padding: 20mm 25mm; 
                box-sizing: border-box; position: relative; 
                box-shadow: 0 0 10px rgba(0,0,0,0.5); 
            }}
            
            /* --- 關鍵 CSS 修復 --- */
            .content {{ font-size: 16px; text-align: justify; color: #333; }}
            
            /* 修正行內公式的垂直對齊，避免文字忽高忽低 */
            mjx-container[jax="CHTML"][display="false"] {{
                margin: 0 2px !important;
                vertical-align: middle !important;
                display: inline-block !important;
            }}
            
            /* 確保區塊公式有適當間距 */
            mjx-container[jax="CHTML"][display="true"] {{
                margin: 1em 0 !important;
                display: block !important;
                text-align: center !important;
            }}

            /* 標題樣式優化 */
            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; margin-top: 0; }}
            h2 {{ color: #0d47a1; border-left: 5px solid #2196f3; padding-left: 10px; margin-top: 30px; margin-bottom: 15px; }}
            h3 {{ color: #1565c0; font-weight: bold; margin-top: 25px; margin-bottom: 10px; }}
            
            p {{ margin-bottom: 15px; }}
            ul, ol {{ margin-bottom: 15px; padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            
            .sponsor-text-footer {{ color: #666; font-size: 12px; text-align: center; margin-top: 40px; border-top: 1px solid #eee; padding-top: 10px; }}
            .manual-page-break {{ page-break-before: always; height: 1px; display: block; }}
        </style>
    </head>
    <body>
        <div id="printable-area">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:12px; color:#666; margin-bottom: 20px;">日期：{date_str}</div>
            {img_section}
            <div class="content">{html_body}</div>
            <div class="sponsor-text-footer">💖 講義完全免費，您的支持是我們持續開發的動力。</div>
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{
                    margin: 0, 
                    filename: '{title}.pdf', 
                    image: {{ type: 'jpeg', quality: 1.0 }},
                    html2canvas: {{ scale: 2, useCORS: true, letterRendering: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                // 增加延遲確保 MathJax 渲染完畢再下載
                setTimeout(() => {{
                    html2pdf().set(opt).from(element).save();
                }}, 1000);
            }}
            {auto_js}
        </script>
    </body>
    </html>
    """

# ==========================================
# 6. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    df = load_db()
    
    with st.sidebar:
        st.title("🚀 個人戰情室")
        mode = st.radio("功能切換", ["📚 知識庫搜尋", "🔬 解碼實驗室", "🎓 講義排版大師"])
    
    if mode == "📚 知識庫搜尋": page_learn(df)
    elif mode == "🔬 解碼實驗室": page_lab(df)
    elif mode == "🎓 講義排版大師": run_handout_app()

def generate_printable_html(title, text_content, img_b64, img_width_percent, auto_download=False):
    # 此處保留您最穩定的 HTML/MathJax 渲染邏輯
    html_body = markdown.markdown(text_content.replace('[換頁]', '<div style="page-break-before: always;"></div>'), extensions=['fenced_code', 'tables'])
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 1000); };" if auto_download else ""
    return f"""
    <html><head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
    <style>body {{ font-family: sans-serif; padding: 20px; }} #p {{ background: white; width: 210mm; margin: auto; padding: 20mm; }}</style>
    </head><body><div id="p"><h1>{title}</h1>{html_body}</div>
    <script>function downloadPDF() {{ html2pdf().from(document.getElementById('p')).save('{title}.pdf'); }} {auto_js}</script>
    </body></html>
    """

def handout_ai_generate(image, manual_input, instruction):
    keys = get_gemini_keys()
    parts = [f"You are a layout expert. Content: {manual_input}. {instruction}"]
    if image: parts.append(image)
    try:
        genai.configure(api_key=keys[0])
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(parts).text
    except: return "AI 錯誤"

if __name__ == "__main__":
    main()
