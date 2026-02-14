import streamlit as st
import pandas as pd
import random
import time
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# ==========================================
# 0. 基礎設定與 CSS 美化
# ==========================================
st.set_page_config(page_title="單字大亂鬥", page_icon="🤪", layout="wide")

def inject_game_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@500;900&display=swap');
            
            /* 1. 全域背景與文字 (白底黑字) */
            [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #ffffff !important; }
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
                background: #fff; border: 3px solid #000; border-radius: 20px; padding: 15px; margin: 15px auto;
                position: relative; box-shadow: 5px 5px 0px #000; font-weight: 900; color: #000 !important;
                max-width: 500px; text-align: center;
            }
            .taunt-bubble:after {
                content: ''; position: absolute; bottom: -23px; left: 50%; transform: translateX(-50%);
                border-width: 20px 20px 0; border-style: solid; border-color: #000 transparent; display: block; width: 0;
            }

            /* 3. 單字泡泡 */
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
                background-color: #f1f2f6; border-radius: 20px; padding: 20px; margin: 20px auto;
                border: 3px dashed #333; text-align: center; max-width: 800px;
            }
            div.stButton > button {
                background-color: #ffffff; color: #000000 !important; border-radius: 15px; font-weight: 900; 
                border: 2px solid #000; box-shadow: 4px 4px 0 #000; transition: 0.1s;
            }
            div.stButton > button:hover { background-color: #fffa65; border-color: #000; }
            div.stButton > button:active { box-shadow: 0 0 0 #000; transform: translate(4px, 4px); }

            /* 🚀 5. Toast 純白高對比 */
            div[data-baseweb="toast"] {
                background-color: #000000 !important; border: 2px solid #ffffff !important;
                box-shadow: 0px 0px 15px rgba(0,0,0,0.5) !important; border-radius: 12px !important;
            }
            div[data-baseweb="toast"] * { color: #ffffff !important; font-weight: 900 !important; fill: #ffffff !important; }

            @keyframes float {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-15px); }
                100% { transform: translateY(0px); }
            }

            /* 📱 6. 手機版優化 */
            @media (max-width: 768px) {
                .game-title { font-size: 2.5rem; }
                [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"]:nth-of-type(2),
                [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"]:nth-of-type(3) { display: none !important; }
                [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"]:nth-of-type(1) {
                    width: 100% !important; flex: 1 1 100% !important; display: flex; justify-content: center;
                }
            }
            
            .centered-image-box { display: flex; flex-direction: column; justify-content: center; align-items: center; margin: 20px 0; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 核心邏輯 (資料/評分)
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
        return pd.DataFrame([{"word": "Serendipity", "definition": "意外發現的美好", "roots": "serendip-", "breakdown": "童話故事來的"}])

def submit_rating(word, rating, icon):
    st.toast(f"✅ [{icon}] {word} >> {rating}")
    time.sleep(0.5)
    if 'current_bubbles' in st.session_state: del st.session_state.current_bubbles
    st.session_state.selected_bubble_idx = None
    st.rerun()

# ==========================================
# 2. 靈魂拷問贊助模組 (核心邏輯更新)
# ==========================================
def render_sarcastic_sponsor_module():
    st.write("---")
    st.markdown("<h3 style='text-align:center;'>💸 錢包破洞區</h3>", unsafe_allow_html=True)
    
    # 檢查後台設定是否有 LINK
    sponsor_url = st.secrets.get("SPONSOR_URL", "") # 或是檢查特定的 Key
    is_bank_open = True if sponsor_url else False

    if 'taunt_level' not in st.session_state: st.session_state.taunt_level = 0
    
    _, sponsor_col, _ = st.columns([1, 2, 1])
    
    with sponsor_col:
        if st.session_state.taunt_level == 0:
            if st.button("💰 我想贊助 (真的沒事找事做)", use_container_width=True):
                st.session_state.taunt_level = 1
                st.rerun()
        
        elif st.session_state.taunt_level == 1:
            st.markdown("<div class='taunt-bubble'>🤨 蛤？你認真？<br>我是個免費仔寫的程式欸。<br>你確定按的不是「檢舉」？</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("對啦！", use_container_width=True): st.session_state.taunt_level = 2; st.rerun()
            if c2.button("按錯了", use_container_width=True): st.session_state.taunt_level = 0; st.rerun()
            
        elif st.session_state.taunt_level == 2:
            st.markdown("<div class='taunt-bubble'>🥤 不是...<br>這錢拿去買杯珍奶不好嗎？<br>一定要給我？</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("閉嘴收錢", use_container_width=True): st.session_state.taunt_level = 3; st.rerun()
            if c2.button("去買珍奶", use_container_width=True): st.session_state.taunt_level = 0; st.rerun()
            
        elif st.session_state.taunt_level == 3:
            if is_bank_open:
                # 情況 A：後台有設定連結
                st.markdown("<div class='taunt-bubble'>🙄 好啦好啦...連結丟這裡...<br>隨便你啦。</div>", unsafe_allow_html=True)
                st.markdown(f"""
                    <a href="{sponsor_url}" target="_blank" style="display:block; text-align:center; background:#00A650; color:white; padding:15px; border-radius:10px; margin-bottom:10px; font-weight:bold; text-decoration:none; border: 2px solid #000;">💳 綠界贊助 (ECPay)</a>
                    <a href="https://www.buymeacoffee.com/" target="_blank" style="display:block; text-align:center; background:#FFDD00; color:black; padding:15px; border-radius:10px; font-weight:bold; text-decoration:none; border: 2px solid #000;">☕ 請我喝咖啡 (BMC)</a>
                """, unsafe_allow_html=True)
            else:
                # 情況 B：後台沒有設定連結 (哈哈銀行)
                st.markdown("<div class='taunt-bubble'>🙄 蛤？你想給錢？<br><br>可惜「哈哈銀行」今天沒開門欸。<br>錢自己留著買椰果吧。</div>", unsafe_allow_html=True)
            
            if st.button("重置嘲諷流程", use_container_width=True):
                st.session_state.taunt_level = 0
                st.rerun()

# ==========================================
# 3. 核心遊戲區域
# ==========================================
def render_game_area(df):
    if 'current_bubbles' not in st.session_state: st.session_state.current_bubbles = df.sample(min(3, len(df))).to_dict('records')
    if 'selected_bubble_idx' not in st.session_state: st.session_state.selected_bubble_idx = None

    _, c_top, _ = st.columns([1, 2, 1])
    if c_top.button("🔄 這些太醜了，換一批！", use_container_width=True):
        if 'current_bubbles' in st.session_state: del st.session_state.current_bubbles
        st.session_state.selected_bubble_idx = None
        st.rerun()
    
    st.write("---")
    cols = st.columns(3)
    bubbles = st.session_state.current_bubbles
    for i, bubble in enumerate(bubbles):
        with cols[i]:
            st.markdown(f"""<div class="bubble-wrapper"><div class="word-bubble delay-{i+1}"><div class="bubble-word">{bubble['word']}</div><div class="bubble-hint">{str(bubble['roots'])[:8]}...</div></div></div>""", unsafe_allow_html=True)
            if st.button(f"👆 戳 {bubble['word']}", key=f"p_{i}", use_container_width=True): st.session_state.selected_bubble_idx = i

    if st.session_state.selected_bubble_idx is not None:
        idx = st.session_state.selected_bubble_idx
        if idx < len(bubbles):
            target = bubbles[idx]
            st.markdown(f"""<div class="rating-container"><h2>{target['word']}</h2><p style="font-size:1.2rem; font-weight:bold;">{target['definition']}</p><p>拆解：{target['breakdown']}</p><hr style="border-top: 2px dashed #000;"><h3>👇 評價一下？ (點完自動下一題)</h3></div>""", unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns(5)
            opts = [("😍 夯", "🧺"), ("🙂 還行", "🧺"), ("😐 普通", "❓"), ("😒 醜", "🗑️"), ("🤮 爛", "🗑️")]
            for j, (label, icon) in enumerate(opts):
                if getattr(eval(f"c{j+1}"), "button")(label, use_container_width=True): submit_rating(target['word'], label, icon)

# ==========================================
# 4. 底部區域
# ==========================================
def render_bottom_section():
    html_code = """
    <!DOCTYPE html><html><head><link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Noto+Sans+TC:wght@400;900&display=swap" rel="stylesheet"><style>
    body { background: transparent; margin: 0; padding: 0; font-family: 'Fredoka', 'Noto Sans TC', sans-serif; overflow: hidden; }
    .bottom-container { display: flex; justify-content: space-around; align-items: flex-end; padding-top: 50px; height: 180px; border-top: 4px solid #000; }
    .zone-item { text-align: center; cursor: pointer; position: relative; width: 30%; transition: transform 0.1s; user-select: none; }
    .zone-item:active { transform: scale(0.95); }
    .zone-icon { font-size: 4rem; margin-bottom: 5px; display: block; }
    .zone-label { font-size: 1.2rem; font-weight: 900; color: #000 !important; margin: 0; }
    .zone-hint { font-size: 0.8rem; color: #555 !important; margin: 0; font-weight: bold; }
    @media (max-width: 600px) { .zone-icon { font-size: 2.5rem; } .zone-label { font-size: 0.9rem; } .zone-hint { font-size: 0.6rem; } .bottom-container { padding-top: 20px; height: 140px; } }
    .float-text { position: absolute; top: 0; left: 50%; transform: translateX(-50%); color: #FF4757; font-weight: 900; font-size: 1.2rem; white-space: nowrap; pointer-events: none; animation: floatUp 1.5s ease-out forwards; text-shadow: 2px 2px 0px #fff; z-index: 999; }
    @keyframes floatUp { 0% { top: -10px; opacity: 1; transform: translateX(-50%) scale(1); } 100% { top: -80px; opacity: 0; transform: translateX(-50%) scale(1.2); } }
    </style></head><body><div class="bottom-container">
    <div class="zone-item" onclick="createFloat(this, '這裡沒有吃的')"><div class="zone-icon">🧺</div><p class="zone-label">真香籃</p><p class="zone-hint">(夯貨)</p></div>
    <div class="zone-item" onclick="createFloat(this, '？？？？？')"><div class="zone-icon">❓</div><p class="zone-label">黑人問號</p><p class="zone-hint">(拖不動)</p></div>
    <div class="zone-item" onclick="createFloat(this, '莎莎莎莎莎')"><div class="zone-icon">🗑️</div><p class="zone-label">垃圾桶</p><p class="zone-hint">(爛貨)</p></div>
    </div><script>function createFloat(el, text) { const f = document.createElement('span'); f.innerText = text; f.className = 'float-text'; el.appendChild(f); setTimeout(() => f.remove(), 1500); }</script></body></html>
    """
    components.html(html_code, height=250, scrolling=False)
    st.markdown("<div class='centered-image-box'><img src='https://media.giphy.com/media/l2JHVUriDGEtWOx0c/giphy.gif' style='width:300px; border:3px solid #000; border-radius:15px; box-shadow:8px 8px 0px #eee;'><p style='margin-top:10px; color:#888 !important; font-size:0.8rem; font-weight:bold;'>看著你的靈魂...</p></div>", unsafe_allow_html=True)
    render_sarcastic_sponsor_module()
    st.markdown("<p style='text-align:center; color:#ccc !important; font-size:0.7rem;'>v5.8 Haha Bank Edition</p>", unsafe_allow_html=True)

# ==========================================
# 5. 主程式入口
# ==========================================
def main():
    inject_game_css()
    st.markdown("<div class='game-title'>🤪 單字大亂鬥</div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#000 !important; font-weight:900;'>別再背單字了，來決定單字的生死吧！</p>", unsafe_allow_html=True)
    df = load_bubbles()
    if not df.empty:
        render_game_area(df)
        render_bottom_section()
    else:
        st.error("資料庫連線失敗")

if __name__ == "__main__":
    main()
