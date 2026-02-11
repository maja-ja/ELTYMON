# ==========================================
# Etymon Decoder - LaTeX & Mobile Pro Version
# ==========================================
import streamlit as st
import pandas as pd
import base64
import time
import re
import markdown
import json
from io import BytesIO
from gtts import gTTS
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心工具函式
# ==========================================

def fix_content(text):
    """處理文本，保留 LaTeX 所需的反斜線與換行"""
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    # 僅處理資料庫中可能的轉義換行，保留 LaTeX 語法
    return str(text).replace('\\n', '\n').strip('"').strip("'")

def speak(text, key_suffix=""):
    """語音朗讀：過濾 LaTeX 標籤以免發音錯誤"""
    # 移除 $...$ 之間的數學公式，只唸文字
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
                color: #0277BD; transition: 0.2s; font-family: sans-serif;
            }}
            .speak-btn:active {{ transform: scale(0.98); }}
            @media (prefers-color-scheme: dark) {{
                .speak-btn {{ background: #161B22; border-color: #30363d; color: #f0f6fc; }}
            }}
        </style>
        <button class="speak-btn" onclick="document.getElementById('{unique_id}').play()">🔊 聽發音</button>
        <audio id="{unique_id}" style="display:none" src="data:audio/mp3;base64,{audio_base64}"></audio>
        """, height=52)
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
# 2. LaTeX 講義生成引擎 (MathJax + html2pdf)
# ==========================================

def generate_printable_html(title, text_content, **kwargs):
    """
    生成支援 LaTeX 的 A4 PDF。
    利用 MathJax 3.0 渲染公式，並在渲染完成後才觸發 html2pdf。
    """
    # 轉換 Markdown 為 HTML (保留 LaTeX 標記)
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    
    auto_download_js = "window.onload = function() { setTimeout(renderAndSave, 1500); };" if kwargs.get("auto_download") else ""

    return f"""
    <html><head>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <script>
            window.MathJax = {{
                tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$']] }},
                svg: {{ fontCache: 'global' }}
            }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; margin: 0; padding: 0; background: #eee; }}
            #paper {{ background: white; width: 210mm; min-height: 297mm; padding: 20mm 25mm; box-sizing: border-box; margin: 0 auto; }}
            h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            h3 {{ color: #283593; margin-top: 25px; border-left: 5px solid #1a237e; padding-left: 10px; }}
            p, li {{ font-size: 16px; line-height: 1.8; color: #333; }}
            .mjx-chtml {{ font-size: 110% !important; }}
        </style>
    </head><body>
        <div id="paper">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:12px; color:#aaa; margin-bottom:20px;">AI Education Workstation</div>
            <div>{html_body}</div>
        </div>
        <script>
            function renderAndSave() {{
                const element = document.getElementById('paper');
                // 關鍵：等待 MathJax 排版完畢
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
# 3. 手機版介面樣式
# ==========================================

def inject_mobile_ui():
    st.markdown("""
        <style>
            .main { background: var(--background-primary); }
            .block-container { max-width: 480px !important; padding: 1.5rem 1rem 5rem 1rem !important; }
            [data-testid="stSidebar"], header { display: none; }
            
            /* 導覽列按鈕優化 */
            .stRadio > div { background: #f0f2f6; border-radius: 15px; padding: 4px; gap: 5px; }
            @media (prefers-color-scheme: dark) { .stRadio > div { background: #262730; } }
            
            .word-card {
                background: var(--background-secondary); border-radius: 20px; padding: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid rgba(128,128,128,0.1);
                margin-bottom: 20px;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. 頁面組件
# ==========================================

def home_page(df):
    st.markdown("<h2 style='text-align:center;'>🔍 知識探索</h2>", unsafe_allow_html=True)
    
    col_search, col_rand = st.columns([4, 1])
    with col_search:
        query = st.text_input("輸入關鍵字...", placeholder="例如：熵 或 Entropy", label_visibility="collapsed")
    with col_rand:
        if st.button("🎲"):
            st.session_state.selected_word = df.sample(1).iloc[0].to_dict()
            st.rerun()

    target = None
    if query:
        res = df[df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
        if not res.empty: target = res.iloc[0].to_dict()
        else: st.warning("未找到匹配項目")
    elif "selected_word" in st.session_state:
        target = st.session_state.selected_word
    elif not df.empty:
        target = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target

    if target:
        w = target['word']
        st.markdown(f"""
        <div class="word-card">
            <h1 style="margin:0; color:#1976D2;">{w}</h1>
            <p style="color:gray; font-size:0.9rem; margin-bottom:15px;">/{target['phonetic']}/ · {target['category']}</p>
            <span style="background:#E3F2FD; color:#1976D2; padding:4px 10px; border-radius:10px; font-size:0.8rem; font-weight:bold;">🧬 {target['roots']}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 使用原生 Markdown 渲染 LaTeX 預覽
        st.markdown("#### 📖 定義")
        st.markdown(fix_content(target['definition']))
        
        with st.expander("💡 深入解析與 LaTeX 實例", expanded=True):
            st.markdown(fix_content(target['example']))
        
        c1, c2 = st.columns(2)
        with c1: speak(w, "home")
        with c2:
            if st.button("📄 生成講義", type="primary", use_container_width=True):
                # 準備繼承到講義頁面的文字
                st.session_state.handout_editor_content = (
                    f"## 講義主題：{w}\n\n"
                    f"### 🧬 核心邏輯\n{fix_content(target['breakdown'])}\n\n"
                    f"### 🎯 專業定義\n{fix_content(target['definition'])}\n\n"
                    f"### 🧪 應用實例 (含公式)\n{fix_content(target['example'])}\n\n"
                    f"---\n### 📝 個人筆記\n在此輸入您的補充內容..."
                )
                st.session_state.mobile_nav = "📄 講義"
                st.rerun()

def handout_page():
    st.markdown("<h2 style='text-align:center;'>📄 講義製作</h2>", unsafe_allow_html=True)
    
    if "handout_editor_content" not in st.session_state:
        st.session_state.handout_editor_content = "請先從探索頁面選擇一個單字。"

    content = st.text_area("編輯內容 (支援 Markdown & LaTeX)", 
                           value=st.session_state.handout_editor_content, 
                           height=350)
    st.session_state.handout_editor_content = content

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 下載 PDF", type="primary", use_container_width=True):
            st.session_state.trigger_download = True
            st.rerun()
    with col2:
        if st.button("🔄 重置", use_container_width=True):
            st.session_state.pop("handout_editor_content", None)
            st.rerun()

    is_downloading = st.session_state.get("trigger_download", False)
    final_html = generate_printable_html("學術講義", content, auto_download=is_downloading)
    
    if is_downloading:
        st.session_state.trigger_download = False
        st.toast("正在渲染 LaTeX 並生成 PDF...", icon="⏳")

    st.markdown("---")
    st.caption("A4 講義實時預覽:")
    components.html(final_html, height=500, scrolling=True)

# ==========================================
# 5. 主程式入口
# ==========================================

def main():
    st.set_page_config(page_title="Etymon Decoder", page_icon="🧪", layout="centered")
    inject_mobile_ui()

    # --- 修正後的導覽邏輯 (防止 ValueError) ---
    nav_options = ["🔍 探索", "📄 講義", "💖 支持"]
    
    # 檢查 session 中的值是否還有效
    if 'mobile_nav' not in st.session_state or st.session_state.mobile_nav not in nav_options:
        st.session_state.mobile_nav = nav_options[0]

    # 安全地獲取當前索引
    try:
        current_idx = nav_options.index(st.session_state.mobile_nav)
    except ValueError:
        current_idx = 0

    nav = st.radio("選單", nav_options, index=current_idx, horizontal=True, label_visibility="collapsed")
    
    if nav != st.session_state.mobile_nav:
        st.session_state.mobile_nav = nav
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    df = load_db()
    if df.empty:
        st.error("無法載入資料，請檢查 Google Sheets 設定。")
        return

    # 路由分發
    if st.session_state.mobile_nav == "🔍 探索":
        home_page(df)
    elif st.session_state.mobile_nav == "📄 講義":
        handout_page()
    elif st.session_state.mobile_nav == "💖 支持":
        st.markdown("<div class='word-card' style='text-align:center;'>", unsafe_allow_html=True)
        st.markdown("### 💖 支持開發者")
        st.write("您的支持是維持資料庫與算力運行電力來源！")
        st.markdown("""
            <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="text-decoration:none;">
                <div style="background:#00A650; color:white; padding:15px; border-radius:15px; font-weight:bold; margin-top:15px;">💳 綠界小額贊助</div>
            </a>
            <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" style="text-decoration:none;">
                <div style="background:#FFDD00; color:black; padding:15px; border-radius:15px; font-weight:bold; margin-top:10px;">☕ 請我喝杯咖啡</div>
            </a>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
