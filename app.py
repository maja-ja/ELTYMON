import streamlit as st
import pandas as pd
import random
import time
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# ==========================================
# 0. 基礎設定與 CSS 美化 (V5.5 修正版)
# ==========================================
st.set_page_config(page_title="單字大亂鬥", page_icon="🤪", layout="wide")

def inject_game_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@500;900&display=swap');
            
            /* 1. 全域背景與文字 (白底黑字) */
            [data-testid="stAppViewContainer"], [data-testid="stHeader"] { 
                background-color: #ffffff !important; 
            }
            [data-testid="stSidebar"] { 
                background-color: #f8f9fa !important; 
                border-right: 2px solid #000 !important; 
            }
            .stMarkdown, p, h1, h2, h3, div, span, label { 
                color: #000000 !important; 
                font-family: 'Fredoka', 'Noto Sans TC', sans-serif !important; 
            }
            header, footer, .stDeployButton { display: none; }

            /* 2. 標題與對話框 */
            .game-title {
                text-align: center; font-size: 3.5rem; font-weight: 900; 
                color: #FF4757 !important; text-shadow: 4px 4px 0px #2F3542; 
                margin-bottom: 5px; animation: float 3s ease-in-out infinite;
            }
            .taunt-bubble {
                background: #fff; border: 3px solid #000; border-radius: 20px; padding: 15px; margin: 15px 0;
                position: relative; box-shadow: 5px 5px 0px #000; font-weight: 900; color: #000 !important;
            }
            .taunt-bubble:after {
                content: ''; position: absolute; bottom: -23px; left: 20px;
                border-width: 20px 20px 0; border-style: solid; border-color: #000 transparent; display: block; width: 0;
            }
            .taunt-bubble:before {
                content: ''; position: absolute; bottom: -16px; left: 23px;
                border-width: 17px 17px 0; border-style: solid; border-color: #fff transparent; display: block; width: 0; z-index: 1;
            }

            /* 3. 單字泡泡 (反底色：彩底白字) */
            .bubble-wrapper { display: flex; justify-content: center; align-items: center; padding: 10px; }
            .word-bubble {
                width: 200px; height: 200px;
                background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%);
                border-radius: 50%; display: flex; flex-direction: column; justify-content: center; align-items: center;
                text-align: center; border: 4px solid #fff; box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                position: relative; animation: float 4s ease-in-out infinite;
                color: #ffffff !important; text-shadow: 2px 2px 0px rgba(0,0,0,0.8);
            }
            .word-bubble div { color: #ffffff !important; }
            .delay-1 { animation-delay: 0s; background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%); }
            .delay-2 { animation-delay: 1s; background: linear-gradient(135deg, #4834d4 0%, #686de0 100%); }
            .delay-3 { animation-delay: 2s; background: linear-gradient(135deg, #6ab04c 0%, #badc58 100%); }
            .bubble-word { font-size: 1.8rem; font-weight: 900; }
            .bubble-hint { font-size: 0.9rem; font-weight: 600; opacity: 0.9; margin-top: 5px; }

            /* 4. 評分區與按鈕 */
            .rating-container {
                background-color: #f1f2f6; border-radius: 20px; padding: 20px; margin-top: 20px;
                border: 3px dashed #333; text-align: center;
            }
            div.stButton > button {
                background-color: #ffffff; color: #000000 !important; border-radius: 15px; font-weight: 900; 
                border: 2px solid #000; box-shadow: 4px 4px 0 #000; transition: 0.1s;
            }
            div.stButton > button:hover { background-color: #fffa65; border-color: #000; }
            div.stButton > button:active { box-shadow: 0 0 0 #000; transform: translate(4px, 4px); }

            /* =========================================
               🚀 5. Toast 純白化 (強制修正)
               ========================================= */
            div[data-baseweb="toast"] {
                background-color: #000000 !important; /* 黑底 */
                border: 2px solid #ffffff !important; /* 白框 */
                box-shadow: 0px 0px 15px rgba(0,0,0,0.5) !important;
                border-radius: 12px !important;
                padding: 12px !important;
                display: flex !important;
                align-items: center !important;
            }
            /* 強制文字與圖示純白 */
            div[data-baseweb="toast"] * {
                color: #ffffff !important; 
                font-weight: 900 !important;
                font-size: 1.1rem !important;
                fill: #ffffff !important; /* SVG圖示顏色 */
            }

            @keyframes float {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-15px); }
                100% { transform: translateY(0px); }
            }

            /* =========================================
               📱 6. 手機版優化
               ========================================= */
            @media (max-width: 768px) {
                .game-title { font-size: 2.5rem; }
                
                /* 隱藏第2、3顆泡泡 */
                [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"]:nth-of-type(2),
                [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"]:nth-of-type(3) {
                    display: none !important;
                }
                /* 讓第1顆泡泡滿版置中 */
                [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"]:nth-of-type(1) {
                    width: 100% !important; flex: 1 1 100% !important; display: flex; justify-content: center;
                }
                .rating-container { padding: 10px; }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 資料庫讀取
# ==========================================
def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet", "")

@st.cache_data(ttl=60) 
def load_bubbles():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        df = conn.read(spreadsheet=url, ttl=0)
        cols = ['word', 'definition', 'roots', 'breakdown']
        for col in cols:
            if col not in df.columns: df[col] = "???"
        return df.fillna("???")
    except:
        return pd.DataFrame([
            {"word": "Serendipity", "definition": "意外發現的美好", "roots": "serendip-", "breakdown": "童話故事來的"},
            {"word": "Petrichor", "definition": "雨後泥土的味道", "roots": "petro-", "breakdown": "石頭的血"},
            {"word": "Lagom", "definition": "不多不少剛剛好", "roots": "Swedish", "breakdown": "瑞典哲學"},
            {"word": "Schadenfreude", "definition": "幸災樂禍", "roots": "German", "breakdown": "別人的痛苦是我的快樂"}
        ])

def submit_rating(word, rating, icon):
    """
    提交評分並強制刷新單字
    """
    # 修正：不使用 icon 參數，直接將圖示與文字放在字串中
    # 修正：使用 >> 代替 ➔ 避免字型編碼問題
    msg = f"✅  [{icon}] {word} >> {rating}"
    
    st.toast(msg)
    
    time.sleep(0.5)
    
    # 清除舊泡泡，強制換一批
    if 'current_bubbles' in st.session_state:
        del st.session_state.current_bubbles
    st.session_state.selected_bubble_idx = None
    st.rerun()

# ==========================================
# 2. 嘲諷贊助 (Sidebar - 置底)
# ==========================================
def render_sarcastic_sponsor():
    if 'taunt_level' not in st.session_state: st.session_state.taunt_level = 0
    st.sidebar.markdown("### 💸 錢包破洞區")
    ph = st.sidebar.container()

    if st.session_state.taunt_level == 0:
        if ph.button("💰 我想贊助", type="primary", use_container_width=True):
            st.session_state.taunt_level = 1
            st.rerun()
    elif st.session_state.taunt_level == 1:
        ph.markdown("<div class='taunt-bubble'>🤨 蛤？你認真？<br>我是個免費仔寫的程式欸。<br>你確定按的不是「檢舉」？</div>", unsafe_allow_html=True)
        c1, c2 = ph.columns(2)
        if c1.button("對啦！", use_container_width=True): st.session_state.taunt_level = 2; st.rerun()
        if c2.button("按錯了", use_container_width=True): st.session_state.taunt_level = 0; st.rerun()
    elif st.session_state.taunt_level == 2:
        ph.markdown("<div class='taunt-bubble'>🥤 不是...<br>這錢拿去買杯珍奶不好嗎？<br>加個椰果它不香嗎？</div>", unsafe_allow_html=True)
        c1, c2 = ph.columns(2)
        if c1.button("閉嘴收錢", use_container_width=True): st.session_state.taunt_level = 3; st.rerun()
        if c2.button("去買珍奶", use_container_width=True): st.session_state.taunt_level = 0; st.rerun()
    elif st.session_state.taunt_level == 3:
        ph.markdown("<div class='taunt-bubble'>🙄 好啦好啦...<br>既然你那麼堅持...<br>連結丟這裡，隨便你啦。</div>", unsafe_allow_html=True)
        ph.markdown("""
            <a href="https://p.ecpay.com.tw/" target="_blank" style="display:block; text-align:center; background:#00A650; color:white; padding:10px; border-radius:10px; margin-bottom:10px; font-weight:bold; text-decoration:none;">💳 綠界 (勉強收下)</a>
            <a href="https://www.buymeacoffee.com/" target="_blank" style="display:block; text-align:center; background:#FFDD00; color:black; padding:10px; border-radius:10px; font-weight:bold; text-decoration:none;">☕ Buy Me a Coffee</a>
        """, unsafe_allow_html=True)
        if ph.button("重置嘲諷", use_container_width=True): st.session_state.taunt_level = 0; st.rerun()

# ==========================================
# 3. 核心功能：泡泡與評分
# ==========================================
def render_game_area(df):
    if 'current_bubbles' not in st.session_state:
        st.session_state.current_bubbles = df.sample(min(3, len(df))).to_dict('records')
    
    if 'selected_bubble_idx' not in st.session_state:
        st.session_state.selected_bubble_idx = None

    # --- 頂部換一批按鈕 (手機版置頂) ---
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            # 此按鈕在手機上會自動置頂且滿版
            if st.button("🔄 這些太醜了，換一批！", use_container_width=True):
                if 'current_bubbles' in st.session_state:
                    del st.session_state.current_bubbles
                st.session_state.selected_bubble_idx = None
                st.rerun()
    
    st.write("---")

    # --- 泡泡顯示區 ---
    cols = st.columns(3)
    bubbles = st.session_state.current_bubbles
    
    for i, bubble in enumerate(bubbles):
        with cols[i]:
            delay_class = f"delay-{i+1}"
            st.markdown(f"""
                <div class="bubble-wrapper">
                    <div class="word-bubble {delay_class}">
                        <div class="bubble-word">{bubble['word']}</div>
                        <div class="bubble-hint">{str(bubble['roots'])[:8]}...</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            if st.button(f"👆 戳 {bubble['word']}", key=f"btn_poke_{i}", use_container_width=True):
                st.session_state.selected_bubble_idx = i

    st.write("") 

    # --- 評分互動區 ---
    if st.session_state.selected_bubble_idx is not None:
        idx = st.session_state.selected_bubble_idx
        if idx < len(bubbles):
            target = bubbles[idx]
            with st.container():
                st.markdown(f"""
                <div class="rating-container">
                    <h2 style="margin:0; color:#000;">{target['word']}</h2>
                    <p style="color:#000; font-size:1.2rem; font-weight:bold;">{target['definition']}</p>
                    <p style="color:#333; font-size:0.9rem;">拆解：{target['breakdown']}</p>
                    <hr style="border-top: 2px dashed #000;">
                    <h3 style="color:#000;">👇 評價一下？</h3>
                </div>
                """, unsafe_allow_html=True)

                c1, c2, c3, c4, c5 = st.columns(5)
                with c1: 
                    if st.button("😍 夯", use_container_width=True): submit_rating(target['word'], "夯", "🧺")
                with c2: 
                    if st.button("🙂 還行", use_container_width=True): submit_rating(target['word'], "還行", "🧺")
                with c3: 
                    if st.button("😐 普通", use_container_width=True): submit_rating(target['word'], "普通", "❓")
                with c4: 
                    if st.button("😒 醜", use_container_width=True): submit_rating(target['word'], "醜", "🗑️")
                with c5: 
                    if st.button("🤮 爛", use_container_width=True): submit_rating(target['word'], "爛", "🗑️")

# ==========================================
# 4. 底部視覺區域 (HTML/JS 動畫版)
# ==========================================
def render_bottom_zone():
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@400;900&display=swap" rel="stylesheet">
        <style>
            body { background: transparent; margin: 0; padding: 0; font-family: 'Fredoka', 'Noto Sans TC', sans-serif; overflow: hidden; }
            .bottom-container {
                display: flex; justify-content: space-around; align-items: flex-end;
                padding-top: 50px; height: 180px; border-top: 4px solid #000;
            }
            .zone-item {
                text-align: center; cursor: pointer; position: relative; width: 30%;
                transition: transform 0.1s; user-select: none;
            }
            .zone-item:active { transform: scale(0.95); }
            .zone-icon { font-size: 4rem; margin-bottom: 5px; display: block; }
            .zone-label { font-size: 1.2rem; font-weight: 900; color: #000 !important; margin: 0; }
            .zone-hint { font-size: 0.8rem; color: #555 !important; margin: 0; font-weight: bold; }
            
            @media (max-width: 600px) {
                .zone-icon { font-size: 2.5rem; }
                .zone-label { font-size: 0.9rem; }
                .zone-hint { font-size: 0.6rem; }
                .bottom-container { padding-top: 20px; height: 140px; }
            }

            .float-text {
                position: absolute; top: 0; left: 50%; transform: translateX(-50%);
                color: #FF4757; font-weight: 900; font-size: 1.2rem; white-space: nowrap;
                pointer-events: none; animation: floatUp 1.5s ease-out forwards;
                text-shadow: 2px 2px 0px #fff; z-index: 999;
            }
            @keyframes floatUp {
                0% { top: -10px; opacity: 1; transform: translateX(-50%) scale(1); }
                100% { top: -80px; opacity: 0; transform: translateX(-50%) scale(1.2); }
            }
        </style>
    </head>
    <body>
        <div class="bottom-container">
            <div class="zone-item" onclick="createFloat(this, '這裡沒有吃的')">
                <div class="zone-icon">🧺</div><p class="zone-label">真香籃</p><p class="zone-hint">(夯貨)</p>
            </div>
            <div class="zone-item" onclick="createFloat(this, '？？？？？')">
                <div class="zone-icon">❓</div><p class="zone-label">黑人問號</p><p class="zone-hint">(拖不動)</p>
            </div>
            <div class="zone-item" onclick="createFloat(this, '莎莎莎莎莎')">
                <div class="zone-icon">🗑️</div><p class="zone-label">垃圾桶</p><p class="zone-hint">(爛貨)</p>
            </div>
        </div>
        <script>
            function createFloat(el, text) {
                const f = document.createElement('span');
                f.innerText = text; f.className = 'float-text';
                el.appendChild(f);
                setTimeout(() => f.remove(), 1500);
            }
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=250, scrolling=False)

# ==========================================
# 5. 主程式
# ==========================================
def main():
    inject_game_css()
    st.markdown("<div class='game-title'>🤪 單字大亂鬥</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; color:#000 !important; margin-bottom:30px; font-weight:900;'>別再背單字了，來決定單字的生死吧！</div>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.image("https://media.giphy.com/media/l2JHVUriDGEtWOx0c/giphy.gif", caption="...你在看我嗎？")
        # 間距推擠
        st.markdown("<div style='height: 45vh;'></div>", unsafe_allow_html=True)
        st.sidebar.markdown("---")
        render_sarcastic_sponsor()
        st.sidebar.caption("v5.5 White Toast Fix")

    df = load_bubbles()
    if not df.empty:
        render_game_area(df)
        render_bottom_zone()
    else:
        st.error("資料庫連線失敗")

if __name__ == "__main__":
    main()
