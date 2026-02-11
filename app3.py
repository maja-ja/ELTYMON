# ==========================================
# Etymon Decoder Mobile - LaTeX Pro Version
# ==========================================
import streamlit as st
import pandas as pd
import base64
import time
import re
import markdown
from io import BytesIO
from gtts import gTTS
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心工具函式
# ==========================================

def fix_content(text):
    """處理文本中的換行與 LaTeX 轉義，保留原始反斜線"""
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    # 僅處理換行符號，不處理反斜線，以免破壞 LaTeX 語法
    return str(text).replace('\\n', '\n').strip('"').strip("'")

def speak(text, key_suffix=""):
    """語音朗讀：過濾 LaTeX 符號避免發音怪異"""
    # 移除 $...$ 內部的內容，避免唸出數學公式
    clean_text = re.sub(r"\$.*?\$", "", str(text))
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", clean_text).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        components.html(f"""
        <style>
            .speak-btn {{ 
                background: #F0F7FF; border: 1px solid #B3E5FC; border-radius: 12px; 
                padding: 10px; cursor: pointer; width: 100%; font-weight: 600; 
                color: #0277BD; transition: 0.2s;
            }}
            @media (prefers-color-scheme: dark) {{
                .speak-btn {{ background: #161B22; border-color: #30363d; color: #f0f6fc; }}
            }}
        </style>
        <button class="speak-btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
        <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        """, height=50)
    except: pass

@st.cache_data(ttl=3600) 
def load_db():
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe']
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        df = conn.read(spreadsheet=url, ttl=0)
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無")[COL_NAMES].reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

# ==========================================
# 2. LaTeX 講義生成引擎 (含 MathJax 渲染)
# ==========================================

def generate_printable_html(title, text_content, **kwargs):
    """
    生成包含 MathJax 支援的 A4 HTML。
    確保在執行 html2pdf 前，LaTeX 公式已完成渲染。
    """
    # 將 Markdown 轉為 HTML，保留 LaTeX 原始標籤供 MathJax 解析
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    
    auto_download_js = "window.onload = function() { setTimeout(renderAndSave, 1000); };" if kwargs.get("auto_download") else ""

    return f"""
    <html><head>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <!-- 引入 html2pdf.js -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <!-- 引入 MathJax 3.0 -->
        <script>
            window.MathJax = {{
                tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$']] }},
                svg: {{ fontCache: 'global' }}
            }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
            #paper {{ background: white; width: 210mm; min-height: 297mm; padding: 20mm 25mm; box-sizing: border-box; margin: 0 auto; }}
            h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            h3 {{ color: #283593; margin-top: 25px; border-left: 5px solid #1a237e; padding-left: 10px; }}
            p, li {{ font-size: 16px; line-height: 1.8; color: #333; }}
            code {{ background: #f0f0f0; padding: 2px 5px; border-radius: 4px; }}
        </style>
    </head><body>
        <div id="paper">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:12px; color:#aaa; margin-bottom:20px;">AI 數位學習講義系列</div>
            <div>{html_body}</div>
        </div>
        <script>
            function renderAndSave() {{
                const element = document.getElementById('paper');
                // 等待 MathJax 渲染完畢
                MathJax.typesetPromise().then(() => {{
                    html2pdf().set({{
                        margin: 0,
                        filename: '{title}.pdf',
                        image: {{ type: 'jpeg', quality: 1 }},
                        html2canvas: {{ scale: 2, useCORS: true }},
                        jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                    }}).from(element).save();
                }});
            }}
            {auto_download_js}
        </script>
    </body></html>"""

# ==========================================
# 3. 手機版 UI 配置 (CSS)
# ==========================================

def inject_mobile_ui():
    st.markdown("""
        <style>
            .block-container { max-width: 480px !important; padding: 2rem 1rem !important; }
            [data-testid="stSidebar"], header { display: none; }
            .stRadio > div { background: #eee; border-radius: 20px; padding: 5px; }
            @media (prefers-color-scheme: dark) { .stRadio > div { background: #262730; } }
            
            .word-card {
                background: var(--background-secondary); border-radius: 20px; padding: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 20px;
                border: 1px solid rgba(128,128,128,0.2);
            }
            .latex-box {
                background: rgba(128,128,128,0.05); padding: 15px; border-radius: 12px;
                margin: 10px 0; border-left: 4px solid #1976D2;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. 頁面邏輯
# ==========================================

def home_page(df):
    st.markdown("<h2 style='text-align:center;'>🔍 知識百科</h2>", unsafe_allow_html=True)
    
    # 搜尋與隨機
    col_search, col_rand = st.columns([4, 1])
    with col_search:
        query = st.text_input("輸入關鍵字 (如: 熵, Entropy)", label_visibility="collapsed")
    with col_rand:
        if st.button("🎲"):
            st.session_state.selected_word = df.sample(1).iloc[0].to_dict()
            st.rerun()

    # 決定顯示內容
    target = None
    if query:
        res = df[df['word'].str.contains(query, case=False) | df['definition'].str.contains(query)]
        if not res.empty: target = res.iloc[0].to_dict()
    elif "selected_word" in st.session_state:
        target = st.session_state.selected_word
    elif not df.empty:
        target = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target

    if target:
        # 使用 Streamlit 原生 Markdown 渲染 LaTeX
        with st.container():
            st.markdown(f"### {target['word']} `/{target['phonetic']}/`")
            st.caption(f"領域: {target['category']} | 字根: {target['roots']}")
            
            st.markdown("#### 📖 定義")
            st.markdown(fix_content(target['definition']))
            
            with st.expander("💡 查看詳解與 LaTeX 實例", expanded=True):
                st.markdown(fix_content(target['example']))
        
        c1, c2 = st.columns(2)
        with c1: speak(target['word'], "home")
        with c2:
            if st.button("📄 製作講義", type="primary"):
                st.session_state.handout_editor_content = (
                    f"## 專題內容：{target['word']}\n\n"
                    f"### 🧬 核心概念\n{fix_content(target['definition'])}\n\n"
                    f"### 🧪 應用實例\n{fix_content(target['example'])}\n\n"
                    f"### 📝 補充筆記\n(請在此輸入您的補充...)"
                )
                st.session_state.mobile_nav = "📄 講義"
                st.rerun()

def handout_page():
    st.markdown("<h2 style='text-align:center;'>📄 講義編輯器</h2>", unsafe_allow_html=True)
    
    if "handout_editor_content" not in st.session_state:
        st.session_state.handout_editor_content = "請先從探索頁面選擇內容。"

    # 編輯區
    content = st.text_area("編輯講義內容 (支援 Markdown & LaTeX)", 
                           value=st.session_state.handout_editor_content, 
                           height=300)
    st.session_state.handout_editor_content = content

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 下載 PDF", type="primary", use_container_width=True):
            st.session_state.trigger_download = True
            st.rerun()
    with col2:
        st.button("🔄 重置內容", on_click=lambda: st.session_state.pop("handout_editor_content", None), use_container_width=True)

    # 預覽與下載處理
    is_downloading = st.session_state.get("trigger_download", False)
    final_html = generate_printable_html("學習講義", content, auto_download=is_downloading)
    
    if is_downloading:
        st.session_state.trigger_download = False
        st.toast("正在生成 PDF，請稍候...", icon="⏳")

    st.markdown("---")
    st.caption("實時預覽 (含 LaTeX 渲染):")
    components.html(final_html, height=600, scrolling=True)

# ==========================================
# 5. 主程式進入點
# ==========================================

def main():
    st.set_page_config(page_title="Etymon Decoder", page_icon="🧪", layout="centered")
    inject_mobile_ui()

    # 導覽列
    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索"
    
    nav = st.radio("選單", ["🔍 探索", "📄 講義", "💖 支持"], 
                   index=["🔍 探索", "📄 講義", "💖 支持"].index(st.session_state.mobile_nav),
                   horizontal=True, label_visibility="collapsed")
    st.session_state.mobile_nav = nav
    st.markdown("---")

    df = load_db()

    if nav == "🔍 探索":
        home_page(df)
    elif nav == "📄 講義":
        handout_page()
    elif nav == "💖 支持":
        st.markdown("<h3 style='text-align:center;'>☕ 支持開發者</h3>", unsafe_allow_html=True)
        st.info("您的贊助將用於支付 Google Cloud 算力與資料庫成本。")
        st.markdown("""
        <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="text-decoration:none;">
            <div style="background:#00A650; color:white; padding:15px; border-radius:15px; text-align:center; font-weight:bold; margin-bottom:10px;">💳 綠界快速贊助</div>
        </a>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
