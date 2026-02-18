import streamlit as st
from graphviz import Digraph

# --- 1. 頁面設定 ---
st.set_page_config(layout="wide", page_title="全方位決策過濾器")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 1.1rem !important; margin-top: 0rem !important; }
        p { font-size: 0.95rem; margin-bottom: 0.5rem; }
        .stButton button { width: 100%; border-radius: 6px; height: 3.2em; font-weight: bold; }
        .stTextInput > div > div > input { font-size: 1.1rem; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 狀態管理 ---
if 'history' not in st.session_state:
    st.session_state.history = ["start"]
if 'current_node' not in st.session_state:
    st.session_state.current_node = "start"
if 'topic' not in st.session_state:
    st.session_state.topic = ""

# --- 3. 繪圖邏輯 (升級版) ---
def generate_decision_map(history, topic):
    dot = Digraph()
    # 保持緊湊
    dot.attr(rankdir='TB', ranksep='0.22', nodesep='0.12', margin='0.05', bgcolor='transparent')
    
    node_attr = {
        'shape': 'box', 'style': 'rounded,filled', 'fontsize': '9', 
        'fontname': 'Sans-Serif', 'height': '0.35', 'width': '1.3'
    }
    # 移除重複的 penwidth
    edge_attr = {'fontsize': '7', 'fontcolor': '#666666', 'arrowsize': '0.5'}

    # 定義節點 (新增了 Alignment, Reversibility, Friction)
    nodes = {
        "start": "決策起點",
        "risk": "1.生存風險\n(輸得起嗎?)",
        "align": "2.願景一致\n(符合人設?)",
        "reverse": "3.可逆性\n(能反悔嗎?)",
        "friction": "4.能量阻力\n(心累嗎?)",
        "regret": "5.遺憾檢核\n(臨終後悔?)",
        
        # 負向結果
        "stop_risk": "🛑 禁止\n(致命風險)",
        "stop_align": "🗑️ 放棄\n(偏離目標)",
        "stop_friction": "💤 委外/延後\n(阻力過大)",
        "drop_it": "👋 放下\n(無遺憾)",
        
        # 正向結果
        "do_experiment": "🧪 低成本試錯\n(小規模嘗試)",
        "do_system": "⚙️ 建立系統\n(長期抗戰)",
        "do_it_now": "⚡ 立即執行\n(順流而下)",
        "do_heavy": "🏋️ 咬牙執行\n(痛苦但值得)"
    }

    # 定義路徑邏輯
    edges = [
        # Start -> Risk
        ("start", "risk", "開始"),
        ("risk", "stop_risk", "無法承擔"),
        ("risk", "align", "風險可控"),
        
        # Risk -> Alignment
        ("align", "stop_align", "不符合目標"),
        ("align", "reverse", "符合願景"),
        
        # Alignment -> Reversibility (Bezos Rule)
        ("reverse", "do_experiment", "可逆(雙向門)"),
        ("reverse", "friction", "不可逆(單向門)"),
        
        # Reversibility -> Friction (Energy)
        ("friction", "do_it_now", "順手/低阻力"),
        ("friction", "regret", "高阻力/困難"),
        
        # Friction -> Regret
        ("regret", "stop_friction", "不做也還好"),
        ("regret", "do_heavy", "不做會後悔")
    ]

    # 繪製節點
    for n_id, label in nodes.items():
        is_active = n_id in history
        
        # 顏色邏輯
        if "stop" in n_id or "drop" in n_id:
            bg = "#E74C3C" if is_active else "#FADBD8" # 紅
        elif "do_" in n_id:
            bg = "#27AE60" if is_active else "#D4EFDF" # 綠
        else:
            bg = "#3498DB" if is_active else "#EBF5FB" # 藍
            
        fc = "#FFFFFF" if is_active else "#566573"
        dot.node(n_id, label, fillcolor=bg, fontcolor=fc, color=bg, **node_attr)

    # 繪製邊線
    for src, dst, label in edges:
        is_path = src in history and dst in history
        ec = "#2C3E50" if is_path else "#D7DBDD"
        ew = "1.5" if is_path else "0.8"
        dot.edge(src, dst, label=label, color=ec, penwidth=ew, **edge_attr)

    return dot

# --- 4. 介面邏輯 ---
left_col, right_col = st.columns([1.1, 1.9], gap="small")

with left_col:
    st.title("⚖️ 高維度決策儀表板")
    
    # --- Step 0: 輸入 ---
    if st.session_state.current_node == "start":
        st.info("輸入讓你糾結的決策：")
        topic_input = st.text_input("例如：轉職軟體工程師、買特斯拉、分手", value=st.session_state.topic)
        if st.button("啟動多重過濾分析 ➡️", type="primary"):
            if topic_input.strip():
                st.session_state.topic = topic_input
                st.session_state.current_node = "risk"
                st.session_state.history.append("risk")
                st.rerun()
            else:
                st.warning("請輸入主題")

    # --- Step 1: 風險 (Risk) ---
    elif st.session_state.current_node == "risk":
        st.subheader("1. 生存邊界測試")
        st.write(f"如果做「{st.session_state.topic}」失敗了，最壞的情況你能接受嗎？（例如：破產、身敗名裂）")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💀 無法接受/會死", type="secondary"):
                st.session_state.history.append("stop_risk")
                st.session_state.current_node = "stop_risk"
                st.rerun()
        with c2:
            if st.button("🛡️ 有退路/可承受", type="primary"):
                st.session_state.history.append("align")
                st.session_state.current_node = "align"
                st.rerun()

    # --- Step 2: 一致性 (Alignment) ---
    elif st.session_state.current_node == "align":
        st.subheader("2. 人生目標校準")
        st.write(f"這件事與「你想要成為的人」或「你的長期目標」一致嗎？還是只是因為別人都在做？")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("😒 只是跟風/誘惑", type="secondary"):
                st.session_state.history.append("stop_align")
                st.session_state.current_node = "stop_align"
                st.rerun()
        with c2:
            if st.button("🎯 符合我的願景", type="primary"):
                st.session_state.history.append("reverse")
                st.session_state.current_node = "reverse"
                st.rerun()

    # --- Step 3: 可逆性 (Reversibility) ---
    elif st.session_state.current_node == "reverse":
        st.subheader("3. 雙向門 vs 單向門")
        st.write(f"如果做了覺得不合適，能夠輕易撤退或修正嗎？(時間/金錢成本低)")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🚪 難以回頭 (單向門)", type="secondary"):
                st.session_state.history.append("friction")
                st.session_state.current_node = "friction"
                st.rerun()
        with c2:
            if st.button("🔄 可以撤退 (雙向門)", type="primary"):
                st.session_state.history.append("do_experiment")
                st.session_state.current_node = "do_experiment"
                st.rerun()

    # --- Step 4: 摩擦力 (Friction) ---
    elif st.session_state.current_node == "friction":
        st.subheader("4. 執行能量阻力")
        st.write(f"這件事做起來，你是感到「興奮順流」還是「痛苦且需要極大意志力」？")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🌊 順流/興奮", type="primary"):
                st.session_state.history.append("do_it_now")
                st.session_state.current_node = "do_it_now"
                st.rerun()
        with c2:
            if st.button("🧗 痛苦/高門檻", type="secondary"):
                st.session_state.history.append("regret")
                st.session_state.current_node = "regret"
                st.rerun()

    # --- Step 5: 遺憾 (Regret) ---
    elif st.session_state.current_node == "regret":
        st.subheader("5. 終局遺憾模擬")
        st.write("這件事很痛苦且不可逆。但如果不做，你會在臨終前感到深深的遺憾嗎？")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💨 不做也沒差", type="secondary"):
                st.session_state.history.append("stop_friction")
                st.session_state.current_node = "stop_friction"
                st.rerun()
        with c2:
            if st.button("💔 絕對會後悔", type="primary"):
                st.session_state.history.append("do_heavy")
                st.session_state.current_node = "do_heavy"
                st.rerun()

    # --- 結果頁面 ---
    else:
        node = st.session_state.current_node
        res_map = {
            "stop_risk": ("⛔ 風險過高", "不要為了採蜂蜜而把手伸進熊嘴裡。先建立安全網再說。"),
            "stop_align": ("🗑️ 雜訊過濾", "這不是你要的人生。專注力很貴，不要浪費在不符合願景的事情上。"),
            "stop_friction": ("💤 戰略性放棄", "這件事既痛苦又非必要。或許可以花錢外包，或者直接刪除這個選項。"),
            "do_experiment": ("🧪 快速試錯 (MVP)", "既然失敗成本低，想再多都是浪費時間。先做再說，不行就撤。"),
            "do_it_now": ("⚡ 天選之選", "符合目標、風險可控且你充滿熱情。這是你的「甜蜜點」，立刻行動！"),
            "do_heavy": ("🏋️ 英雄之旅", "這是一條艱難的路，但這是你的天命。做好長期抗戰的準備，制定嚴格的紀律。")
        }
        
        title, desc = res_map.get(node, ("結束", ""))
        st.success(f"### 結論：{title}")
        st.write(desc)
        
        if st.button("🔄 分析下一個決策"):
            st.session_state.history = ["start"]
            st.session_state.current_node = "start"
            st.session_state.topic = ""
            st.rerun()

# --- 5. 右側圖表 ---
with right_col:
    chart_title = f"決策路徑：{st.session_state.topic}" if st.session_state.topic else "多維度過濾模型"
    st.caption(f"📍 {chart_title}")
    st.graphviz_chart(generate_decision_map(st.session_state.history, st.session_state.topic), use_container_width=True)
