import streamlit as st
import pandas as pd
import random
import time
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
# ==========================================
# 0. 基礎設定與強制白底 CSS
# ==========================================
st.set_page_config(page_title="單字大亂鬥", page_icon="🤪", layout="wide")

def inject_game_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@400;900&display=swap');
            
            /* --- 強制鎖定白色背景 (無論深色模式設定為何) --- */
            [data-testid="stAppViewContainer"] {
                background-color: #ffffff !important;
            }
            [data-testid="stHeader"] {
                background-color: #ffffff !important;
            }
            [data-testid="stSidebar"] {
                background-color: #f8f9fa !important;
                border-right: 1px dashed #ccc;
            }
            .stMarkdown, p, h1, h2, h3, div {
                color: #333 !important; /* 強制文字深色 */
                font-family: 'Fredoka', 'Noto Sans TC', sans-serif !important;
            }

            /* --- 隱藏預設元素 --- */
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            footer {visibility: hidden;}

            /* --- 標題樣式 --- */
            .game-title {
                text-align: center;
                font-size: 3.5rem;
                font-weight: 900;
                color: #FF6B6B !important;
                text-shadow: 3px 3px 0px #Feca57;
                margin-bottom: 5px;
                animation: float 3s ease-in-out infinite;
            }

            /* --- 嘲諷對話框 (漫畫風格) --- */
            .taunt-bubble {
                background: #fff;
                border: 3px solid #000;
                border-radius: 20px;
                padding: 15px;
                margin: 15px 0;
                position: relative;
                box-shadow: 5px 5px 0px rgba(0,0,0,0.8);
                font-weight: bold;
                color: #000 !important;
            }
            /* 對話框的小尾巴 */
            .taunt-bubble:after {
                content: '';
                position: absolute;
                bottom: -23px; /* 調整位置 */
                left: 20px;
                border-width: 20px 20px 0;
                border-style: solid;
                border-color: #000 transparent;
                display: block;
                width: 0;
            }
            .taunt-bubble:before {
                content: '';
                position: absolute;
                bottom: -16px; 
                left: 23px;
                border-width: 17px 17px 0;
                border-style: solid;
                border-color: #fff transparent;
                display: block;
                width: 0;
                z-index: 1;
            }

            /* --- 單字泡泡 (核心元件) --- */
            .bubble-wrapper {
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 10px;
            }
            .word-bubble {
                width: 200px;
                height: 200px;
                /* 鮮豔漸層 */
                background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 99%, #FECFEF 100%); 
                border-radius: 50%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                box-shadow: inset -10px -10px 20px rgba(0,0,0,0.1), 5px 10px 15px rgba(0,0,0,0.1);
                border: 4px solid #fff;
                color: #444 !important;
                position: relative;
                animation: float 4s ease-in-out infinite;
            }
            /* 讓每個泡泡動畫稍微錯開 */
            .delay-1 { animation-delay: 0s; background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%); }
            .delay-2 { animation-delay: 1s; background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%); }
            .delay-3 { animation-delay: 2s; background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%); }

            .bubble-word { font-size: 1.8rem; font-weight: 900; text-shadow: 2px 2px 0px rgba(255,255,255,0.5); }
            .bubble-hint { font-size: 0.9rem; font-weight: 600; opacity: 0.7; margin-top: 5px; }

            /* --- 評分按鈕區域 --- */
            .rating-container {
                background-color: #f0f0f0;
                border-radius: 20px;
                padding: 20px;
                margin-top: 20px;
                border: 3px dashed #ccc;
                text-align: center;
            }

            /* --- 底部籃子與垃圾桶區域 --- */
            .bottom-zone {
                display: flex;
                justify-content: space-around; /* 平均分配 */
                align-items: flex-end;
                padding-top: 30px;
                margin-top: 30px;
                border-top: 4px solid #eee;
            }
            .zone-item {
                text-align: center;
                opacity: 0.6;
                transition: 0.3s;
            }
            .zone-item:hover {
                opacity: 1;
                transform: scale(1.1);
            }
            .zone-icon { font-size: 4rem; margin-bottom: 5px; }
            .zone-label { font-size: 1.2rem; font-weight: 900; color: #888 !important; }

            /* --- 動畫定義 --- */
            @keyframes float {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-15px); }
                100% { transform: translateY(0px); }
            }
            
            /* 按鈕美化 */
            div.stButton > button {
                border-radius: 15px;
                font-weight: bold;
                border: 2px solid #ddd;
                box-shadow: 0 4px 0 #ddd;
                transition: 0.1s;
            }
            div.stButton > button:active {
                box-shadow: 0 0 0 #ddd;
                transform: translateY(4px);
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 資料庫讀取 (極簡版)
# ==========================================
def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets.get("gsheets", {}).get("spreadsheet", "")

@st.cache_data(ttl=60) 
def load_bubbles():
    """只抓取必要的欄位，如果失敗回傳假資料"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        df = conn.read(spreadsheet=url, ttl=0)
        # 填充缺失值
        cols = ['word', 'definition', 'roots', 'breakdown']
        for col in cols:
            if col not in df.columns: df[col] = "???"
        return df.fillna("???")
    except:
        # 離線或錯誤時的備用資料
        return pd.DataFrame([
            {"word": "Serendipity", "definition": "意外發現的美好", "roots": "serendip-", "breakdown": "童話故事來的"},
            {"word": "Petrichor", "definition": "雨後泥土的味道", "roots": "petro-", "breakdown": "石頭的血"},
            {"word": "Lagom", "definition": "不多不少剛剛好", "roots": "Swedish", "breakdown": "瑞典哲學"},
            {"word": "Schadenfreude", "definition": "幸災樂禍", "roots": "German", "breakdown": "別人的痛苦是我的快樂"}
        ])

def submit_rating(word, rating, icon):
    """處理評分邏輯 (顯示 Toast)"""
    st.toast(f"{icon} 已將「{word}」歸類為：{rating}", icon="🚀")
    # 清空選擇，讓使用者可以選下一個
    time.sleep(0.5)
    st.session_state.selected_bubble_idx = None
    st.rerun()

# ==========================================
# 2. 嘲諷贊助系統 (SideBar)
# ==========================================
def render_sarcastic_sponsor():
    if 'taunt_level' not in st.session_state:
        st.session_state.taunt_level = 0

    st.sidebar.markdown("### 💸 錢包破洞區")
    
    # 這裡用一個空的 container 來裝內容
    placeholder = st.sidebar.container()

    if st.session_state.taunt_level == 0:
        if placeholder.button("💰 我想贊助", type="primary", use_container_width=True):
            st.session_state.taunt_level = 1
            st.rerun()

    elif st.session_state.taunt_level == 1:
        placeholder.markdown("""
            <div class='taunt-bubble'>
                🤨 蛤？你認真？<br>我是個免費仔寫的程式欸。<br>你確定按的不是「檢舉」？
            </div>
        """, unsafe_allow_html=True)
        c1, c2 = placeholder.columns(2)
        if c1.button("對啦！", use_container_width=True):
            st.session_state.taunt_level = 2
            st.rerun()
        if c2.button("按錯了", use_container_width=True):
            st.session_state.taunt_level = 0
            st.rerun()

    elif st.session_state.taunt_level == 2:
        placeholder.markdown("""
            <div class='taunt-bubble'>
                🥤 不是...<br>這錢拿去買杯珍奶不好嗎？<br>加個椰果它不香嗎？<br>一定要給我？
            </div>
        """, unsafe_allow_html=True)
        c1, c2 = placeholder.columns(2)
        if c1.button("閉嘴收錢", use_container_width=True):
            st.session_state.taunt_level = 3
            st.rerun()
        if c2.button("去買珍奶", use_container_width=True):
            st.session_state.taunt_level = 0
            st.rerun()

    elif st.session_state.taunt_level == 3:
        placeholder.markdown("""
            <div class='taunt-bubble'>
                🙄 好啦好啦...<br>既然你那麼堅持...<br>連結丟這裡，隨便你啦。
            </div>
        """, unsafe_allow_html=True)
        placeholder.markdown("""
            <a href="https://p.ecpay.com.tw/" target="_blank" style="display:block; text-align:center; background:#00A650; color:white; padding:10px; border-radius:10px; text-decoration:none; margin-bottom:10px; font-weight:bold;">
                💳 綠界 (勉強收下)
            </a>
            <a href="https://www.buymeacoffee.com/" target="_blank" style="display:block; text-align:center; background:#FFDD00; color:black; padding:10px; border-radius:10px; text-decoration:none; font-weight:bold;">
                ☕ Buy Me a Coffee
            </a>
        """, unsafe_allow_html=True)
        if placeholder.button("重置嘲諷", use_container_width=True):
            st.session_state.taunt_level = 0
            st.rerun()

# ==========================================
# 3. 核心功能：泡泡與評分
# ==========================================
def render_game_area(df):
    # 初始化隨機單字 (避免每次互動都重洗)
    if 'current_bubbles' not in st.session_state:
        sample_size = min(3, len(df))
        st.session_state.current_bubbles = df.sample(sample_size).to_dict('records')
    
    if 'selected_bubble_idx' not in st.session_state:
        st.session_state.selected_bubble_idx = None

    # --- 頂部換一批 ---
    col_head_1, col_head_2, col_head_3 = st.columns([1, 2, 1])
    with col_head_2:
        if st.button("🔄 這些太醜了，換一批！", use_container_width=True):
            sample_size = min(3, len(df))
            st.session_state.current_bubbles = df.sample(sample_size).to_dict('records')
            st.session_state.selected_bubble_idx = None
            st.rerun()

    st.write("---")

    # --- 泡泡顯示區 ---
    cols = st.columns(3)
    bubbles = st.session_state.current_bubbles
    
    for i, bubble in enumerate(bubbles):
        with cols[i]:
            # 根據 index 給不同的顏色 class (delay-1, delay-2...)
            delay_class = f"delay-{i+1}"
            
            # 視覺泡泡 HTML
            st.markdown(f"""
                <div class="bubble-wrapper">
                    <div class="word-bubble {delay_class}">
                        <div class="bubble-word">{bubble['word']}</div>
                        <div class="bubble-hint">{str(bubble['roots'])[:8]}...</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 互動按鈕 (對應上方的泡泡)
            # 這裡使用全寬按鈕，看起來像是點擊泡泡下方
            if st.button(f"👆 戳 {bubble['word']}", key=f"btn_poke_{i}", use_container_width=True):
                st.session_state.selected_bubble_idx = i

    # --- 評分互動區 (如果選中) ---
    st.write("") # Spacer
    
    if st.session_state.selected_bubble_idx is not None:
        idx = st.session_state.selected_bubble_idx
        target = bubbles[idx]
        
        # 顯示詳細資料卡片
        with st.container():
            st.markdown(f"""
            <div class="rating-container">
                <h2 style="margin:0; color:#333;">{target['word']}</h2>
                <p style="color:#555; font-size:1.2rem;">{target['definition']}</p>
                <p style="color:#888; font-size:0.9rem;">拆解：{target['breakdown']}</p>
                <hr style="border-top: 2px dashed #ccc;">
                <h3 style="color:#333;">👇 這個單字要去哪裡？</h3>
            </div>
            """, unsafe_allow_html=True)

            # 評分按鈕：刻意排列對應底部的 籃子(左) / 問號(中) / 垃圾桶(右)
            c1, c2, c3, c4, c5 = st.columns(5)
            
            # 左邊對應籃子 (好)
            with c1:
                if st.button("😍 夯\n(超讚)", use_container_width=True): 
                    submit_rating(target['word'], "夯", "🧺")
            with c2:
                if st.button("🙂 還行\n(太好了)", use_container_width=True): 
                    submit_rating(target['word'], "還行", "🧺")
            
            # 中間對應問號 (普)
            with c3:
                if st.button("😐 普通\n(一般般)", use_container_width=True): 
                    submit_rating(target['word'], "普通", "❓")
            
            # 右邊對應垃圾桶 (爛)
            with c4:
                if st.button("😒 醜\n(這啥啊)", use_container_width=True): 
                    submit_rating(target['word'], "醜", "🗑️")
            with c5:
                if st.button("🤮 爛\n(回家吃自己)", use_container_width=True): 
                    submit_rating(target['word'], "爛", "🗑️")

# ==========================================
# 4. 底部視覺區域 (裝飾用)
# ==========================================
def render_bottom_zone():
    # 使用 HTML/JS 製作獨立的互動區塊
    # 這樣點擊時不會觸發 Streamlit 重新整理，動畫才會順暢
    
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@400;900&display=swap" rel="stylesheet">
        <style>
            body {
                background-color: transparent;
                margin: 0;
                padding: 0;
                font-family: 'Fredoka', 'Noto Sans TC', sans-serif;
                overflow: hidden; /* 防止捲軸出現 */
            }
            .bottom-container {
                display: flex;
                justify-content: space-around;
                align-items: flex-end;
                padding-top: 50px; /* 預留上方空間給飄浮文字 */
                height: 180px;
                border-top: 4px solid #eee;
                background-color: transparent;
            }
            .zone-item {
                text-align: center;
                cursor: pointer; /* 讓滑鼠變手手 */
                position: relative; /* 讓飄浮文字以此為基準 */
                width: 30%;
                transition: transform 0.1s;
                user-select: none; /* 防止選取文字 */
            }
            .zone-item:active {
                transform: scale(0.95);
            }
            .zone-icon {
                font-size: 4rem;
                margin-bottom: 5px;
                display: block;
            }
            .zone-label {
                font-size: 1.2rem;
                font-weight: 900;
                color: #888;
                margin: 0;
            }
            .zone-hint {
                font-size: 0.8rem;
                color: #aaa;
                margin: 0;
            }

            /* --- 飄浮文字動畫 --- */
            .float-text {
                position: absolute;
                top: 0;
                left: 50%;
                transform: translateX(-50%);
                color: #FF6B6B;
                font-weight: 900;
                font-size: 1.2rem;
                white-space: nowrap;
                pointer-events: none; /* 讓點擊穿透 */
                animation: floatUp 1.5s ease-out forwards;
                text-shadow: 2px 2px 0px #fff;
                z-index: 999;
            }

            @keyframes floatUp {
                0% {
                    top: -10px;
                    opacity: 1;
                    transform: translateX(-50%) scale(1);
                }
                50% {
                    opacity: 1;
                }
                100% {
                    top: -80px; /* 往上飄的距離 */
                    opacity: 0;
                    transform: translateX(-50%) scale(1.2);
                }
            }
        </style>
    </head>
    <body>
        <div class="bottom-container">
            <!-- 籃子 -->
            <div class="zone-item" onclick="createFloat(this, '這裡沒有吃的 🍔')">
                <div class="zone-icon">🧺</div>
                <p class="zone-label">真香籃</p>
                <p class="zone-hint">(覺得夯的都在這)</p>
            </div>

            <!-- 問號 -->
            <div class="zone-item" onclick="createFloat(this, '？？？？')">
                <div class="zone-icon">❓</div>
                <p class="zone-label">黑人問號</p>
                <p class="zone-hint">(拖不動，點按鈕啦)</p>
            </div>

            <!-- 垃圾桶 -->
            <div class="zone-item" onclick="createFloat(this, '你不會想進來吧？？ 😱')">
                <div class="zone-icon">🗑️</div>
                <p class="zone-label">垃圾桶</p>
                <p class="zone-hint">(爛單字下去)</p>
            </div>
        </div>

        <script>
            function createFloat(element, text) {
                // 1. 建立新的 span 元素
                const floatEl = document.createElement('span');
                floatEl.innerText = text;
                floatEl.className = 'float-text';
                
                // 2. 加到點擊的元素裡面
                element.appendChild(floatEl);

                // 3. 動畫結束後 (1.5秒) 自動移除該元素，防止記憶體堆積
                setTimeout(() => {
                    floatEl.remove();
                }, 1500);
            }
        </script>
    </body>
    </html>
    """
    # 渲染 HTML 組件，設定足夠的高度以免動畫被切掉
    components.html(html_code, height=250, scrolling=False)

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_game_css()
    
    # 標題
    st.markdown("<div class='game-title'>🤪 單字大亂鬥</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; color:#666; margin-bottom:30px; font-weight:bold;'>別再背單字了，來決定單字的生死吧！</div>", unsafe_allow_html=True)
    
    # 側邊欄嘲諷
    with st.sidebar:
        # 一個看著你的 GIF
        st.image("https://media.giphy.com/media/l2JHVUriDGEtWOx0c/giphy.gif", caption="...你在看我嗎？")
        render_sarcastic_sponsor()
        st.sidebar.markdown("---")
        st.sidebar.caption("v5.0 Chaos Mode | 這裡沒有硬知識")

    # 讀取資料並執行遊戲
    df = load_bubbles()
    if df.empty:
        st.error("資料庫讀取失敗，請稍後再試。")
    else:
        render_game_area(df)
        render_bottom_zone()

if __name__ == "__main__":
    main()
