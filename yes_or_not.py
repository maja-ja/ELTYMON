import streamlit as st
from graphviz import Digraph

# --- 1. 頁面設定與 CSS 優化 (保持緊湊) ---
st.set_page_config(layout="wide", page_title="理性決策輔助器")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 1.1rem !important; margin-top: 0rem !important; }
        p { font-size: 0.95rem; margin-bottom: 0.5rem; }
        .stButton button { width: 100%; border-radius: 6px; height: 3.2em; font-weight: bold; }
        /* 調整輸入框樣式 */
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

# --- 3. 繪圖邏輯 (極致緊湊版) ---
def generate_decision_map(history, topic):
    dot = Digraph()
    dot.attr(rankdir='TB', ranksep='0.25', nodesep='0.15', margin='0.05', bgcolor='transparent')
    
    node_attr = {
        'shape': 'box', 'style': 'rounded,filled', 'fontsize': '9', 
        'fontname': 'Sans-Serif', 'height': '0.35', 'width': '1.2'
    }
    
    # 修正點：這裡移除了 'penwidth'，因為後面會動態設定它
    edge_attr = {'fontsize': '7', 'fontcolor': '#666666', 'arrowsize': '0.5'}

    nodes = {
        "start": "決策起點",
        "risk": "風險承受\n(輸得起嗎?)",
        "value": "價值判斷\n(想要vs需要)",
        "time": "時間維度\n(長期效益?)",
        "regret": "遺憾最小化\n(不做會後悔?)",
        "stop_risk": "🛑 立刻停止\n(風險過高)",
        "stop_want": "🛑 冷靜期\n(只是慾望)",
        "do_it_now": "✅ 立即執行\n(剛需/急迫)",
        "do_it_plan": "📅 規劃執行\n(長期高回報)",
        "drop_it": "🗑️ 放棄\n(無效益)"
    }

    edges = [
        ("start", "risk", "開始分析"),
        ("risk", "stop_risk", "輸不起/會死"),
        ("risk", "value", "風險可控"),
        ("value", "do_it_now", "生存必需/急迫"),
        ("value", "time", "非急迫/改善型"),
        ("time", "stop_want", "短期爽/長期損"),
        ("time", "regret", "長期有益"),
        ("regret", "drop_it", "不做也沒差"),
        ("regret", "do_it_plan", "不做會後悔")
    ]

    for n_id, label in nodes.items():
        is_active = n_id in history
        if "stop" in n_id or "drop" in n_id:
            bg = "#E74C3C" if is_active else "#FADBD8"
        elif "do_it" in n_id:
            bg = "#27AE60" if is_active else "#D4EFDF"
        else:
            bg = "#3498DB" if is_active else "#EBF5FB"
            
        fc = "#FFFFFF" if is_active else "#566573"
        dot.node(n_id, label, fillcolor=bg, fontcolor=fc, color=bg, **node_attr)

    for src, dst, label in edges:
        is_path = src in history and dst in history
        ec = "#2C3E50" if is_path else "#D7DBDD"
        ew = "1.5" if is_path else "0.8"
        
        # 修正點：penwidth 只在這裡傳入一次，不會與 **edge_attr 衝突
        dot.edge(src, dst, label=label, color=ec, penwidth=ew, **edge_attr)

    return dot
# --- 4. 介面佈局 ---
left_col, right_col = st.columns([1.1, 1.9], gap="small")

with left_col:
    st.title("⚖️ 決策輔助器")
    
    # 步驟 0: 輸入主題
    if st.session_state.current_node == "start":
        st.info("請輸入你正在猶豫的事情：")
        topic_input = st.text_input("例如：買重機、離職創業、跟前任復合", value=st.session_state.topic)
        
        if st.button("開始分析流程 ➡️", type="primary"):
            if topic_input.strip():
                st.session_state.topic = topic_input
                st.session_state.current_node = "risk"
                st.session_state.history.append("risk")
                st.rerun()
            else:
                st.warning("請先輸入主題")

    # 步驟 1: 風險評估
    elif st.session_state.current_node == "risk":
        st.subheader("1. 致命風險檢查")
        st.write(f"關於「**{st.session_state.topic}**」，如果結果是**最壞的情況**（如錢全賠光、關係決裂、浪費一年），你的生活會崩潰嗎？")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("😱 會崩潰/無法承擔", type="secondary"):
                st.session_state.history.append("stop_risk")
                st.session_state.current_node = "stop_risk"
                st.rerun()
        with c2:
            if st.button("💪 有退路/可以承受", type="primary"):
                st.session_state.history.append("value")
                st.session_state.current_node = "value"
                st.rerun()

    # 步驟 2: 價值與急迫性
    elif st.session_state.current_node == "value":
        st.subheader("2. 需求本質")
        st.write(f"這件事對你的本質是什麼？是「生存必須」還是「為了快樂/成長」？")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔥 火燒眉毛/不做會死", type="primary"): # 導向立即執行
                st.session_state.history.append("do_it_now")
                st.session_state.current_node = "do_it_now"
                st.rerun()
        with c2:
            if st.button("✨ 改善生活/想要擁有", type="secondary"): # 導向長遠評估
                st.session_state.history.append("time")
                st.session_state.current_node = "time"
                st.rerun()

    # 步驟 3: 時間維度 (ROI)
    elif st.session_state.current_node == "time":
        st.subheader("3. 時間複利效應")
        st.write("想像 **3 年後** 回頭看這件事：")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📉 只有短期爽感", type="secondary"): # 例如衝動消費
                st.session_state.history.append("stop_want")
                st.session_state.current_node = "stop_want"
                st.rerun()
        with c2:
            if st.button("📈 具備長期價值", type="primary"): # 例如學習、投資
                st.session_state.history.append("regret")
                st.session_state.current_node = "regret"
                st.rerun()

    # 步驟 4: 遺憾最小化框架
    elif st.session_state.current_node == "regret":
        st.subheader("4. 遺憾最小化")
        st.write(f"如果你現在**放棄**不做「{st.session_state.topic}」，當你 80 歲回想起來，你會感到後悔嗎？")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🤔 其實沒差/會忘記", type="secondary"):
                st.session_state.history.append("drop_it")
                st.session_state.current_node = "drop_it"
                st.rerun()
        with c2:
            if st.button("😣 絕對會後悔", type="primary"):
                st.session_state.history.append("do_it_plan")
                st.session_state.current_node = "do_it_plan"
                st.rerun()

    # 結果頁面
    else:
        node = st.session_state.current_node
        res_title = {
            "stop_risk": "⛔ 禁止執行",
            "stop_want": "🧊 建議進入冷靜期",
            "do_it_now": "⚡ 必須立即行動",
            "do_it_plan": "🗓️ 這是個好決策，開始規劃",
            "drop_it": "👋 果斷放棄吧"
        }
        res_desc = {
            "stop_risk": "生存高於一切。當最壞情況無法承受時，潛在的回報再高都沒有意義。",
            "stop_want": "這看起來更像是「消費」而非「投資」。建議延遲決策，放入購物車一個月後再看。",
            "do_it_now": "這是剛需或急迫問題，猶豫的時間成本已經超過了執行成本。Do it now.",
            "do_it_plan": "這件事風險可控且具備長期價值，不做的遺憾成本太高。不需猶豫，只需擬定計畫。",
            "drop_it": "這件事對你的人生長河來說無足輕重。把注意力轉移到更高回報的事情上吧。"
        }
        
        st.success(f"### 結論：{res_title.get(node, '結束')}")
        st.write(res_desc.get(node, ""))
        
        if st.button("🔄 重新分析其他事件"):
            st.session_state.history = ["start"]
            st.session_state.current_node = "start"
            st.session_state.topic = ""
            st.rerun()

# --- 5. 右側圖表區 ---
with right_col:
    # 如果有輸入主題，圖表標題會跟著變
    chart_title = f"決策路徑：{st.session_state.topic}" if st.session_state.topic else "決策路徑預覽"
    st.caption(f"📍 {chart_title}")
    
    # 這裡傳入 topic 讓圖表節點文字能動態微調(選用)
    st.graphviz_chart(generate_decision_map(st.session_state.history, st.session_state.topic), use_container_width=True)
