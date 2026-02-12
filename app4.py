import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
from io import BytesIO
from gtts import gTTS
import streamlit.components.v1 as components
import markdown
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 0. 核心配置與 CSS (手機版優化)
# ==========================================
st.set_page_config(page_title="Etymon Mobile", page_icon="📱", layout="centered")

def inject_mobile_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=Inter:wght@400;600&display=swap');
            
            :root {
                --main-bg: #F8F9FA; 
                --card-bg: #FFFFFF; 
                --text-color: #212529; 
                --subtle-text: #6c757d;
                --accent-color: #2196F3;
                --accent-light: #E3F2FD;
                --success-color: #4CAF50;
                --warning-color: #FFC107;
                --danger-color: #FF5252;
                --radius-lg: 20px;
                --radius-md: 12px;
                --shadow: 0 4px 20px rgba(0,0,0,0.05);
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --main-bg: #121212; 
                    --card-bg: #1E1E1E; 
                    --text-color: #E0E0E0; 
                    --subtle-text: #A0A0A0;
                    --accent-color: #64B5F6;
                    --accent-light: #1A237E;
                    --shadow: 0 4px 20px rgba(0,0,0,0.3);
                }
            }

            /* 全局設定 */
            .stApp { background-color: var(--main-bg); }
            .block-container { max-width: 500px !important; padding: 1rem 1rem 4rem 1rem !important; }
            [data-testid="stSidebar"], header { display: none; } /* 隱藏側邊欄與 Header */

            /* 卡片樣式 */
            .word-card {
                background: var(--card-bg);
                border-radius: var(--radius-lg);
                padding: 24px;
                box-shadow: var(--shadow);
                margin-bottom: 20px;
                border: 1px solid rgba(128, 128, 128, 0.1);
            }

            .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; }
            .word-title { font-size: 2rem; font-weight: 800; color: var(--accent-color); margin: 0; line-height: 1.1; font-family: 'Inter', sans-serif; }
            .phonetic { font-size: 0.9rem; color: var(--subtle-text); font-family: monospace; }
            
            .badge {
                display: inline-block; padding: 4px 10px; border-radius: 20px;
                font-size: 0.75rem; font-weight: 600; margin-right: 5px;
            }
            .badge-cat { background: var(--accent-light); color: var(--accent-color); }
            .badge-root { background: rgba(255, 193, 7, 0.2); color: #FF9800; }

            /* 內容區塊 */
            .section-title { font-size: 0.85rem; font-weight: 700; color: var(--subtle-text); margin-top: 15px; text-transform: uppercase; letter-spacing: 1px; }
            .content-text { font-size: 1rem; line-height: 1.6; color: var(--text-color); margin-top: 5px; }
            
            .vibe-box {
                background: linear-gradient(135deg, rgba(33, 150, 243, 0.1) 0%, rgba(33, 203, 243, 0.1) 100%);
                border-left: 4px solid var(--accent-color);
                padding: 12px 16px;
                border-radius: var(--radius-md);
                margin-top: 15px;
                font-size: 0.95rem;
                color: var(--text-color);
            }

            /* 按鈕與互動 */
            .action-row { display: flex; gap: 10px; margin-top: 20px; }
            .stButton > button {
                border-radius: var(--radius-md) !important;
                height: 48px !important;
                font-weight: 600 !important;
                border: none !important;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
                transition: transform 0.1s !important;
            }
            .stButton > button:active { transform: scale(0.97); }
            
            /* 贊助區塊 */
            .sponsor-btn {
                display: block; width: 100%; text-align: center;
                padding: 12px; border-radius: var(--radius-md);
                text-decoration: none; font-weight: bold; margin-bottom: 10px;
                transition: opacity 0.2s;
            }
            .sponsor-btn:hover { opacity: 0.9; }
            .btn-ecpay { background: #00A650; color: white !important; }
            .btn-bmc { background: #FFDD00; color: black !important; }

        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 後端邏輯工具
# ==========================================

def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet")

def fix_content(text):
    if text is None or str(text).strip() in ["無", "nan", ""]: return ""
    return str(text).replace('\\n', '  \n').replace('\n', '  \n').strip('"').strip("'")

@st.cache_data(ttl=600)
def load_db():
    # 完整欄位定義，確保與原資料庫兼容
    COL_NAMES = ['category', 'roots', 'meaning', 'word', 'breakdown', 'definition', 'phonetic', 'example', 'translation', 'native_vibe']
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=get_spreadsheet_url(), ttl=0)
        # 補齊缺失欄位
        for col in COL_NAMES:
            if col not in df.columns: df[col] = "無"
        return df.dropna(subset=['word']).fillna("無").reset_index(drop=True)
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return pd.DataFrame(columns=COL_NAMES)

def submit_report(row_data):
    """一鍵回報功能"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0" # 請確認此 URL 是否正確或替換
        
        # 準備資料
        report_row = row_data.copy()
        report_row['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        report_row['type'] = 'mobile_feedback'
        
        try: existing = conn.read(spreadsheet=url, ttl=0)
        except: existing = pd.DataFrame()
        
        updated = pd.concat([existing, pd.DataFrame([report_row])], ignore_index=True)
        conn.update(spreadsheet=url, data=updated)
        st.toast(f"✅ 已回報「{row_data.get('word')}」的問題，感謝貢獻！", icon="🙏")
    except Exception as e:
        st.toast(f"❌ 回報失敗: {e}")

def speak(text, key_suffix=""):
    """HTML Audio 播放器"""
    english_only = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        unique_id = f"audio_{int(time.time()*1000)}_{key_suffix}"
        
        # 隱藏式播放器，透過按鈕觸發
        components.html(f"""
            <script>
                function playAudio() {{
                    var audio = document.getElementById('{unique_id}');
                    audio.play();
                }}
            </script>
            <audio id="{unique_id}" src="data:audio/mp3;base64,{audio_base64}"></audio>
            <button onclick="playAudio()" style="
                background:none; border:none; cursor:pointer; 
                width:100%; height:100%; display:block;">
            </button>
        """, height=0, width=0) # 實際 UI 在 Streamlit button 處理
        return audio_base64 # 回傳以備不時之需
    except: return None

def generate_printable_html(title, text_content, auto_download=False):
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 1000); };" if auto_download else ""
    return f"""
    <html><head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            body {{ font-family: 'Noto Sans TC', sans-serif; background: #525659; margin: 0; padding: 20px; display: flex; justify-content: center; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; padding: 20mm; box-shadow: 0 0 10px rgba(0,0,0,0.5); }}
            h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            h2 {{ color: #0277BD; margin-top: 20px; border-left: 5px solid #0277BD; padding-left: 10px; }}
            p, li {{ line-height: 1.8; color: #333; }}
            code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 4px; color: #d32f2f; }}
        </style>
    </head><body>
        <div id="printable-area">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:12px; color:#999;">Generated by Etymon Mobile</div>
            {html_body}
            <div style="margin-top:50px; text-align:center; font-size:12px; color:#ccc; border-top:1px solid #eee; padding-top:10px;">
                免費講義資源 - 僅供教育用途
            </div>
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                html2pdf().set({{ margin: 0, filename: '{title}.pdf', image: {{ type: 'jpeg', quality: 0.98 }}, html2canvas: {{ scale: 2 }}, jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }} }}).from(element).save();
            }}
            {auto_js}
        </script>
    </body></html>
    """

# ==========================================
# 2. 介面頁面組件
# ==========================================

def render_word_card(row):
    """渲染單張精美的單字卡"""
    w = row['word']
    phonetic = fix_content(row['phonetic'])
    roots = fix_content(row['roots'])
    definition = fix_content(row['definition'])
    breakdown = fix_content(row['breakdown'])
    vibe = fix_content(row['native_vibe'])
    
    # 1. 卡片主體
    st.markdown(f"""
        <div class="word-card">
            <div class="card-header">
                <div>
                    <h1 class="word-title">{w}</h1>
                    <div class="phonetic">/{phonetic}/</div>
                </div>
                <div>
                    <span class="badge badge-cat">{row['category']}</span>
                </div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <span class="badge badge-root">🧬 字根: {roots}</span>
            </div>
            
            <div class="content-text">
                <b>💡 定義：</b>{definition}
            </div>

            <div class="vibe-box">
                <div style="font-weight:bold; margin-bottom:5px;">🌊 專家視角</div>
                {vibe if vibe != "無" else "暫無專家補充"}
            </div>
            
            <div style="margin-top: 15px;">
                <div class="section-title">邏輯拆解</div>
                <div class="content-text" style="font-family: monospace; color: var(--accent-color);">{breakdown}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 2. 功能按鈕區 (Grid Layout)
    c1, c2, c3 = st.columns([1, 1, 2])
    
    with c1:
        # TTS 發音 (需要一個隱藏的組件來觸發)
        if st.button("🔊 發音", key=f"btn_speak_{w}"):
            speak(w, f"m_{w}") # 這裡其實只是觸發 audio 生成，實際播放需要上面的 html 配合，或簡化為 toast 提示
            st.toast(f"正在播放：{w}")
            # 注意：Streamlit 的按鈕刷新機制可能會打斷音頻，手機版建議用 st.audio 如果不介意醜一點，或用上面的 component 方案
            
    with c2:
        if st.button("🚩 回報", key=f"btn_rep_{w}"):
            submit_report(row.to_dict())

    with c3:
        if st.button("📄 轉講義", type="primary", key=f"btn_jump_{w}", use_container_width=True):
            # 準備講義內容
            draft = (
                f"## 📖 專題講義：{w}\n\n"
                f"### 🧬 核心邏輯\n{breakdown}\n\n"
                f"### 🎯 核心定義\n{definition}\n\n"
                f"### 💡 核心原理\n{roots}\n\n"
                f"**專家心法**：\n> {vibe}\n\n"
                f"### 📝 應用筆記\n(請在此處補充課堂筆記...)"
            )
            st.session_state.manual_input_content = draft
            st.session_state.mobile_nav = "📄 講義預覽"
            st.rerun()

def page_explore(df):
    """探索頁面"""
    st.markdown("### 🔍 探索知識")
    
    # 搜尋與篩選
    col_cat, col_rand = st.columns([2, 1])
    with col_cat:
        cats = ["全部領域"] + sorted(df['category'].unique().tolist())
        sel_cat = st.selectbox("分類", cats, label_visibility="collapsed")
    with col_rand:
        if st.button("🎲 抽卡", type="primary", use_container_width=True):
            pool = df if sel_cat == "全部領域" else df[df['category'] == sel_cat]
            if not pool.empty:
                st.session_state.selected_word = pool.sample(1).iloc[0].to_dict()
            st.rerun()

    search_q = st.text_input("搜尋單字...", placeholder="輸入單字 (例如: entropy)")

    # 決定要顯示哪個單字
    target_row = None
    
    if search_q:
        # 搜尋邏輯
        mask = df['word'].str.lower() == search_q.strip().lower()
        if mask.any(): target_row = df[mask].iloc[0].to_dict()
        else:
            # 模糊搜尋
            fuzzy = df[df['word'].str.contains(search_q, case=False)]
            if not fuzzy.empty: target_row = fuzzy.iloc[0].to_dict()
            else: st.warning("找不到該單字")
    
    elif "selected_word" in st.session_state:
        target_row = st.session_state.selected_word
    
    elif not df.empty:
        # 預設隨機顯示一個
        target_row = df.sample(1).iloc[0].to_dict()
        st.session_state.selected_word = target_row

    # 渲染卡片
    if target_row:
        render_word_card(target_row)

def page_handout():
    """講義預覽與下載頁面"""
    st.markdown("### 📄 講義排版")
    
    content = st.text_area(
        "編輯講義內容 (支援 Markdown)", 
        value=st.session_state.get("manual_input_content", "請先從「探索」頁面選擇單字..."), 
        height=250
    )
    st.session_state.manual_input_content = content
    
    # 提取標題
    title = "AI 講義"
    if content:
        for line in content.split('\n'):
            if "講義" in line or "# " in line:
                title = line.replace('#', '').strip()
                break

    # 下載按鈕
    if st.button("📥 下載 PDF", type="primary", use_container_width=True):
        st.session_state.trigger_download = True
        st.rerun()
    
    # 預覽區域
    st.caption("👇 A4 預覽")
    html = generate_printable_html(
        title=title,
        text_content=content,
        auto_download=st.session_state.get("trigger_download", False)
    )
    if st.session_state.get("trigger_download"): 
        st.session_state.trigger_download = False
        
    components.html(html, height=450, scrolling=True)

def page_sponsor():
    """贊助頁面"""
    st.markdown("### 💖 支持開發")
    st.markdown("""
        <div class="word-card" style="text-align:center;">
            <div style="font-size: 3rem;">🎁</div>
            <p style="color:var(--text-color); margin: 15px 0;">
                這是一個免費的教育工具。<br>
                如果它對您的學習有幫助，<br>
                歡迎贊助一杯咖啡，支持伺服器與 AI 算力成本！
            </p>
            <hr style="opacity:0.2; margin: 20px 0;">
            <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" class="sponsor-btn btn-ecpay">
                💳 綠界贊助 (ECPay)
            </a>
            <a href="https://www.buymeacoffee.com/YOUR_ID" target="_blank" class="sponsor-btn btn-bmc">
                ☕ Buy Me a Coffee
            </a>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 主程式入口
# ==========================================
def main():
    inject_mobile_css()
    
    # 初始化 Session State
    if 'mobile_nav' not in st.session_state: st.session_state.mobile_nav = "🔍 探索"
    
    # 資料庫載入
    df = load_db()

    # 底部導航列 (模擬 Mobile Tab Bar)
    # 使用 radio 配合 horizontal=True 並隱藏 label
    tabs = ["🔍 探索", "📄 講義預覽", "💖 支持"]
    selected = st.radio(
        "Nav", tabs, 
        index=tabs.index(st.session_state.mobile_nav), 
        horizontal=True, 
        label_visibility="collapsed"
    )
    
    # 導航狀態更新
    if selected != st.session_state.mobile_nav:
        st.session_state.mobile_nav = selected
        st.rerun()

    st.markdown("---") # 分隔線

    # 路由
    if st.session_state.mobile_nav == "🔍 探索":
        page_explore(df)
    elif st.session_state.mobile_nav == "📄 講義預覽":
        page_handout()
    elif st.session_state.mobile_nav == "💖 支持":
        page_sponsor()

if __name__ == "__main__":
    main()
