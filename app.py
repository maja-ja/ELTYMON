import streamlit as st
import pandas as pd
import base64
import time
import json
import random
import os
from io import BytesIO
from gtts import gTTS
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# ==========================================
# 0. 基礎設定與 CSS 美化 (大幅度修改為遊戲風)
# ==========================================
st.set_page_config(page_title="單字大亂鬥", page_icon="🤪", layout="wide")

def inject_game_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@400;700&display=swap');
            
            /* 全域字體與背景 */
            .stApp {
                background-color: #fdfbf7;
                font-family: 'Fredoka', 'Noto Sans TC', sans-serif;
            }

            /* 隱藏預設元素 */
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            footer {visibility: hidden;}

            /* 標題樣式 */
            .game-title {
                text-align: center;
                font-size: 3rem;
                font-weight: 900;
                color: #FF6B6B;
                text-shadow: 2px 2px 0px #Feca57;
                margin-bottom: 10px;
                animation: float 3s ease-in-out infinite;
            }

            /* 嘲諷對話框 */
            .taunt-bubble {
                background: #fff;
                border: 3px solid #000;
                border-radius: 20px;
                padding: 15px;
                margin: 10px 0;
                position: relative;
                box-shadow: 5px 5px 0px rgba(0,0,0,0.2);
                font-weight: bold;
                color: #333;
            }
            .taunt-bubble:after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 50%;
                width: 0;
                height: 0;
                border: 10px solid transparent;
                border-top-color: #000;
                border-bottom: 0;
                margin-left: -10px;
                margin-bottom: -10px;
            }

            /* 單字泡泡 (核心元件) */
            .word-bubble-container {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 200px;
            }
            .word-bubble {
                width: 180px;
                height: 180px;
                background: linear-gradient(135deg, #74ebd5 0%, #9face6 100%);
                border-radius: 50%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                box-shadow: 0 10px 20px rgba(0,0,0,0.15);
                transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                border: 5px solid white;
                cursor: pointer;
                color: white;
                padding: 10px;
            }
            .word-bubble:hover {
                transform: scale(1.1) rotate(5deg);
            }
            .bubble-word { font-size: 1.5rem; font-weight: 800; text-shadow: 1px 1px 2px rgba(0,0,0,0.2); }
            .bubble-hint { font-size: 0.8rem; opacity: 0.9; margin-top: 5px; }

            /* 底部籃子與垃圾桶區域 */
            .bottom-zone {
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                padding: 20px 50px;
                margin-top: 50px;
                border-top: 2px dashed #ccc;
            }
            .zone-icon {
                font-size: 3rem;
                text-align: center;
                opacity: 0.6;
            }
            .zone-label {
                font-size: 1rem;
                font-weight: bold;
                color: #888;
            }

            /* 評分按鈕樣式優化 */
            .stButton>button {
                border-radius: 12px;
                border: 2px solid #eee;
                font-weight: bold;
            }
            
            /* 動畫 Keyframes */
            @keyframes float {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
                100% { transform: translateY(0px); }
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 資料庫讀取 (簡化版)
# ==========================================
def get_spreadsheet_url():
    try: return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except: return st.secrets["gsheets"]["spreadsheet"]

@st.cache_data(ttl=60) 
def load_bubbles():
    """只讀取需要的欄位，不管複雜結構"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        df = conn.read(spreadsheet=url, ttl=0)
        # 確保有基本欄位
        required = ['word', 'definition', 'roots', 'breakdown']
        for col in required:
            if col not in df.columns: df[col] = "???"
        return df
    except:
        return pd.DataFrame([
            {"word": "Error", "definition": "資料庫連線失敗", "roots": "Bug", "breakdown": "請檢查網路"}
        ])

def submit_rating(word, rating):
    """將評分回傳到 metrics 表或是 feedback 表 (模擬)"""
    try:
        # 這裡簡化處理，僅顯示 toast
        msgs = {
            "夯（超讚）": "🎉 識貨喔！這個單字我也覺得很頂！",
            "太好了（還行）": "👌 OK，收進籃子裡。",
            "一般般（普通）": "😐 真是個平平無奇的單字呢。",
            "這啥啊（不太行）": "🤨 確實，這單字長得有點醜。",
            "回家吃自己（超爛）": "🗑️ 噁心！丟進垃圾桶！"
        }
        st.toast(msgs.get(rating, "收到評價"), icon="✅")
        # 實際應用可在此寫入 Google Sheets
    except:
        pass

# ==========================================
# 2. 核心功能：嘲諷贊助系統
# ==========================================
def render_sarcastic_sponsor():
    if 'taunt_level' not in st.session_state:
        st.session_state.taunt_level = 0

    st.sidebar.markdown("### 💸 錢包破洞區")
    
    if st.session_state.taunt_level == 0:
        if st.sidebar.button("💰 我想贊助", type="primary", use_container_width=True):
            st.session_state.taunt_level = 1
            st.rerun()

    elif st.session_state.taunt_level == 1:
        st.sidebar.markdown("""
            <div class='taunt-bubble'>
                🤨 蛤？你認真？<br>我是個免費仔寫的程式欸。<br>你確定按的不是「檢舉」？
            </div>
        """, unsafe_allow_html=True)
        if st.sidebar.button("對啦我要付錢！", use_container_width=True):
            st.session_state.taunt_level = 2
            st.rerun()
        if st.sidebar.button("也是，算了", use_container_width=True):
            st.session_state.taunt_level = 0
            st.rerun()

    elif st.session_state.taunt_level == 2:
        st.sidebar.markdown("""
            <div class='taunt-bubble'>
                🥤 不是...<br>這錢拿去買杯珍奶不好嗎？<br>加個椰果它不香嗎？
            </div>
        """, unsafe_allow_html=True)
        col_yes, col_no = st.sidebar.columns(2)
        with col_yes:
            if st.button("閉嘴收錢!", use_container_width=True):
                st.session_state.taunt_level = 3
                st.rerun()
        with col_no:
            if st.button("去買珍奶", use_container_width=True):
                st.session_state.taunt_level = 0
                st.rerun()

    elif st.session_state.taunt_level == 3:
        st.sidebar.markdown("""
            <div class='taunt-bubble'>
                🙄 好啦好啦...<br>既然你那麼堅持...<br>連結丟這裡，隨便你啦。
            </div>
        """, unsafe_allow_html=True)
        st.sidebar.markdown("""
            <a href="https://p.ecpay.com.tw/YOUR_LINK" target="_blank" style="display:block; text-align:center; background:#00A650; color:white; padding:10px; border-radius:10px; text-decoration:none; margin-bottom:10px;">
                💳 綠界 (勉強收下)
            </a>
            <a href="https://www.buymeacoffee.com/" target="_blank" style="display:block; text-align:center; background:#FFDD00; color:black; padding:10px; border-radius:10px; text-decoration:none;">
                ☕ 請我喝咖啡 (甚至不是珍奶)
            </a>
        """, unsafe_allow_html=True)
        if st.sidebar.button("重置嘲諷", use_container_width=True):
            st.session_state.taunt_level = 0
            st.rerun()

# ==========================================
# 3. 核心功能：單字泡泡邏輯
# ==========================================
def render_bubbles(df):
    if df.empty:
        st.error("單字庫是空的，怎麼玩？")
        return

    # 初始化隨機單字 (避免每次點擊按鈕都重洗，存入 session)
    if 'current_bubbles' not in st.session_state:
        # 隨機選 3 個 (如果不夠 3 個就全選)
        sample_size = min(3, len(df))
        st.session_state.current_bubbles = df.sample(sample_size).to_dict('records')
    
    if 'selected_bubble_idx' not in st.session_state:
        st.session_state.selected_bubble_idx = None

    # 上方換一批按鈕
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🔄 這些太爛了，換一批！", use_container_width=True):
            sample_size = min(3, len(df))
            st.session_state.current_bubbles = df.sample(sample_size).to_dict('records')
            st.session_state.selected_bubble_idx = None
            st.rerun()

    st.write("---")

    # 顯示泡泡 (使用 Columns 佈局)
    cols = st.columns(3)
    bubbles = st.session_state.current_bubbles
    
    for i, bubble in enumerate(bubbles):
        with cols[i]:
            # 這是視覺上的泡泡，實際上是一個容器 + 按鈕
            st.markdown(f"""
                <div class="word-bubble-container">
                    <div class="word-bubble">
                        <div class="bubble-word">{bubble['word']}</div>
                        <div class="bubble-hint">{bubble['roots'][:10]}...</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 透明按鈕覆蓋或是下方按鈕
            if st.button(f"👆 戳一下 {bubble['word']}", key=f"btn_{i}", use_container_width=True):
                st.session_state.selected_bubble_idx = i

    st.write("") # Spacer

    # 如果有選中泡泡，顯示詳細資訊與評分板
    if st.session_state.selected_bubble_idx is not None:
        idx = st.session_state.selected_bubble_idx
        target = bubbles[idx]
        
        with st.container(border=True):
            st.markdown(f"<h2 style='text-align:center; color:#2c3e50;'>{target['word']}</h2>", unsafe_allow_html=True)
            
            d1, d2 = st.columns(2)
            with d1:
                st.info(f"**意思：** {target['definition']}")
            with d2:
                st.warning(f"**拆解：** {target['breakdown']}")
            
            st.markdown("### 👉 給這個單字打個分數吧：")
            
            # 5個評分按鈕
            b1, b2, b3, b4, b5 = st.columns(5)
            
            # 定義評分選項
            options = ["夯（超讚）", "太好了（還行）", "一般般（普通）", "這啥啊（不太行）", "回家吃自己（超爛）"]
            
            if b1.button(options[0], use_container_width=True): submit_rating(target['word'], options[0])
            if b2.button(options[1], use_container_width=True): submit_rating(target['word'], options[1])
            if b3.button(options[2], use_container_width=True): submit_rating(target['word'], options[2])
            if b4.button(options[3], use_container_width=True): submit_rating(target['word'], options[3])
            if b5.button(options[4], use_container_width=True): submit_rating(target['word'], options[4])

# ==========================================
# 4. 底部視覺區域 (籃子/問號/垃圾桶)
# ==========================================
def render_bottom_zone():
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        st.markdown("""
            <div style="text-align:center; opacity:0.5;">
                <div style="font-size:4rem;">🧺</div>
                <div style="font-weight:bold;">真香籃</div>
                <div style="font-size:0.8rem;">(覺得夯的都在這)</div>
            </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
            <div style="text-align:center; opacity:0.5;">
                <div style="font-size:4rem;">❓</div>
                <div style="font-weight:bold;">黑人問號</div>
                <div style="font-size:0.8rem;">(拖不動，點上面的按鈕啦)</div>
            </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
            <div style="text-align:center; opacity:0.5;">
                <div style="font-size:4rem;">🗑️</div>
                <div style="font-weight:bold;">垃圾桶</div>
                <div style="font-size:0.8rem;">(爛單字下去)</div>
            </div>
        """, unsafe_allow_html=True)

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_game_css()
    
    # 標題區
    st.markdown("<div class='game-title'>🤪 單字大亂鬥</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; color:#666; margin-bottom:30px;'>別再背單字了，來決定單字的生死吧！</div>", unsafe_allow_html=True)
    
    # 載入資料
    df = load_bubbles()
    
    # 側邊欄：只有嘲諷贊助
    with st.sidebar:
        st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjEx.../giphy.gif", caption="看什麼看？") # 示意圖
        render_sarcastic_sponsor()
        st.sidebar.markdown("---")
        st.sidebar.caption("v5.0 Chaos Mode | 這裡沒有硬知識")

    # 主畫面區塊
    render_bubbles(df)
    
    # 底部裝飾
    render_bottom_zone()

if __name__ == "__main__":
    main()
