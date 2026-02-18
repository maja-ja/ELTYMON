import streamlit as st
from graphviz import Digraph

# 設定頁面寬度為寬廣模式
st.set_page_config(layout="wide")

def generate_flow_chart(current_node, history):
    """
    current_node: 目前停留的節點 ID
    history: 所有走過的節點 ID 列表
    """
    dot = Digraph()
    dot.attr(rankdir='TB', bgcolor='transparent')
    
    # 定義節點 (ID, 顯示標籤)
    nodes = {
        "start": "開始決策",
        "money": "家裡有礦？",
        "talent": "天賦異稟？",
        "dream": "大膽追夢",
        "office": "穩定公職",
        "tech": "電資醫牙",
        "gap": "重考/轉行"
    }

    # 定義連線 (起點, 終點, 條件標籤)
    edges = [
        ("start", "money", ""),
        ("money", "dream", "有"),
        ("money", "talent", "無"),
        ("talent", "tech", "有"),
        ("talent", "office", "無"),
        ("office", "gap", "不甘心"),
    ]

    # 繪製節點
    for node_id, label in nodes.items():
        # 如果是目前節點或歷史路徑，使用亮藍色，否則使用淡灰色
        is_active = node_id in history
        color = "#1E90FF" if is_active else "#D3D3D3"
        font_color = "#FFFFFF" if is_active else "#A9A9A9"
        border_color = "#1E90FF" if is_active else "#D3D3D3"
        
        dot.node(node_id, label, 
                 color=border_color, 
                 style="filled" if is_active else "outline", 
                 fillcolor=color if is_active else "white",
                 fontcolor=font_color, 
                 shape="rect", 
                 style_attr="rounded,filled")

    # 繪製連線
    for src, dst, label in edges:
        # 連線要亮起的條件：起點與終點都在歷史紀錄中
        is_path_active = src in history and dst in history
        path_color = "#1E90FF" if is_path_active else "#E0E0E0"
        path_width = "2.5" if is_path_active else "1.0"
        
        dot.edge(src, dst, label=label, 
                 color=path_color, 
                 penwidth=path_width, 
                 fontcolor=path_color)

    return dot

# --- 初始化狀態 ---
if 'history' not in st.session_state:
    st.session_state.history = ["start"]
if 'current' not in st.session_state:
    st.session_state.current = "start"

# --- UI 佈局 ---
st.title("🚀 自我輔助決策系統 v2.0")
st.markdown("---")

# 建立左右兩欄，比例可以調整，這裡設為 1:1 或自定義
left_col, right_col = st.columns([1, 1])

# --- 左側：互動問題區 ---
with left_col:
    st.subheader("📝 決策問題")
    curr = st.session_state.current

    if curr == "start":
        st.info("點擊下方按鈕開始你的現實面評估。")
        if st.button("準備好了，開始吧！"):
            st.session_state.current = "money"
            st.session_state.history.append("money")
            st.rerun()

    elif curr == "money":
        st.write("### 核心問題：家裡有礦嗎？")
        st.write("這裡指的礦是：失敗了有人墊背、不必背房貸、家產夠你燒三年。")
        col_a, col_b = st.columns(2)
        if col_a.button("我有礦 (投胎高手)"):
            st.session_state.current = "dream"
            st.session_state.history.append("dream")
            st.rerun()
        if col_b.button("我沒礦 (白手起家)"):
            st.session_state.current = "talent"
            st.session_state.history.append("talent")
            st.rerun()

    elif curr == "talent":
        st.write("### 現實問題：你真的有天賦嗎？")
        st.write("在該領域，你是否能在不眠不休的情況下依然贏過 90% 的人？")
        if st.button("是的，我是天選之人"):
            st.session_state.current = "tech"
            st.session_state.history.append("tech")
            st.rerun()
        if st.button("我只是比較努力的凡人"):
            st.session_state.current = "office"
            st.session_state.history.append("office")
            st.rerun()

    elif curr in ["dream", "tech", "office"]:
        st.success(f"🎉 決策完成！建議路徑：{curr}")
        if st.button("重新評估"):
            st.session_state.history = ["start"]
            st.session_state.current = "start"
            st.rerun()

# --- 右側：動態路線圖 ---
with right_col:
    st.subheader("🗺️ 即時決策路徑")
    chart = generate_flow_chart(st.session_state.current, st.session_state.history)
    st.graphviz_chart(chart, use_container_width=True)

# 側邊欄重置
st.sidebar.button("重置所有進度", on_click=lambda: st.session_state.clear())
