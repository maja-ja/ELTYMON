import streamlit as st

# 1. 注入自定義 CSS (包含手機端優化)
def inject_custom_css():
    st.markdown("""
    <style>
    /* 匯入字體 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Noto+Sans+TC:wght@500;700&display=swap');

    /* 基礎背景與字體設置 */
    .stApp {
        background-color: #0E1117;
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
    }

    /* 英雄詞：響應式字體大小 */
    .hero-word {
        font-size: clamp(2rem, 8vw, 3.5rem);
        font-weight: 800;
        color: #90CAF9;
        text-align: center;
        margin: 20px 0 10px 0;
        text-shadow: 0px 4px 10px rgba(144, 202, 249, 0.2);
    }

    /* 邏輯拆解區：漸變背景 */
    .breakdown-wrapper {
        background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
        padding: 25px;
        border-radius: 15px;
        color: white !important;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    /* 定義區：深藍塊 */
    .def-box {
        background-color: #1A237E;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #2196F3;
        color: #E3F2FD;
        height: 100%;
        margin-bottom: 15px;
    }

    /* 核心原理區：深綠塊 */
    .core-box {
        background-color: #1B5E20;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #4CAF50;
        color: #E8F5E9;
        height: 100%;
        margin-bottom: 15px;
    }

    /* 響應式修正：強制手機端列垂直堆疊並撐滿 */
    @media (max-width: 768px) {
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        .stHorizontal {
            flex-direction: column !important;
        }
    }

    /* 按鈕美化 */
    .stButton button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        font-weight: bold !important;
        transition: transform 0.2s;
    }
    .stButton button:hover {
        transform: scale(1.02);
        background-color: #B71C1C !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. 頁面內容渲染邏輯
def render_app():
    inject_custom_css()

    # 側邊欄示例
    with st.sidebar:
        st.title("🧩 Etymon Decoder")
        st.radio("導航菜單", ["🏠 首頁", "📖 學習與搜尋", "🧠 腦根挑戰", "🔬 解碼實驗室"])
        st.divider()
        st.button("☕ Buy Me a Coffee", use_container_width=True)

    # 主介面標題
    st.markdown('<p style="text-align:center; color:#888;">📖 學習與搜尋 > 🎲 隨機探索</p>', unsafe_allow_html=True)

    # 隨機探索按鈕
    _, col_btn_mid, _ = st.columns([1, 2, 1])
    with col_btn_mid:
        if st.button("🎲 隨機探索下一個 (Next)", use_container_width=True):
            st.toast("正在探索新單詞...")

    # 核心展示區
    st.markdown('<h1 class="hero-word">evict</h1>', unsafe_allow_html=True)

    # 邏輯拆解
    st.markdown("""
    <div class="breakdown-wrapper">
        <h3 style="margin:0; font-size:1.1rem; opacity:0.9;">🧩 邏輯拆解</h3>
        <p style="font-size:1.5rem; font-weight:bold; margin:10px 0;">e- (向外) + vict (征服/證明)</p>
        <p style="opacity:0.8;">詞源：來自拉丁語 evincere，意為通過法律手段徹底戰勝並驅逐。</p>
    </div>
    """, unsafe_allow_html=True)

    # 定義與原理 (雙列佈局)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="def-box">
            <h4 style="margin-top:0; color:#90CAF9;">📘 定義與解釋</h4>
            <p><b>v. 依法驅逐；趕出</b></p>
            <hr style="opacity:0.2;">
            <p style="font-size:0.9rem;">通常指通過法律程序將房客或佔據者從房產中移除。</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="core-box">
            <h4 style="margin-top:0; color:#A5D6A7;">🟢 核心原理</h4>
            <p><b>「法律上的勝訴」</b></p>
            <hr style="opacity:0.2;">
            <p style="font-size:0.9rem;">vict 詞根代表力量。evict 不僅是趕走，而是通過「證明自己有理」來正當驅逐。</p>
        </div>
        """, unsafe_allow_html=True)

    # 底部頁腳
    st.divider()
    st.caption("© 2026 Etymon Decoder | 基於邏輯的單詞解碼工具")

# 3. 主程序入口
if __name__ == "__main__":
    st.set_page_config(
        page_title="Etymon Decoder",
        page_icon="🧩",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    render_app()