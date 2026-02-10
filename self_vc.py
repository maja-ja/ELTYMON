
import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
import google.generativeai as genai

st.set_page_config(layout="wide", page_title="Have vs Want Editor")

# --- 硬核防呆：檢查 API Key ---
# 這裡會自動從 Streamlit Cloud 的 Secrets 抓密碼
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    api_ready = True
else:
    st.error("⚠️ 尚未設定 API Key！請在 Streamlit Cloud 的 Secrets 設定 'GEMINI_API_KEY'。")
    api_ready = False

st.title("🎯 Have vs Want：代碼煉成陣")

# --- 定義節點 (你的工作流) ---
nodes = [
    StreamlitFlowNode("have", (50, 150), 
        {'content': '【HAVE】\n原始輸入 (Raw)'}, 
        'input', 'right', 
        style={'background': '#ffcccc', 'border': '2px solid red', 'color': 'black', 'width': '180px'}),
    
    StreamlitFlowNode("transform", (350, 150), 
        {'content': '⚡ AI 轉換層\n(Processing)'}, 
        'default', 'right', target_position='left',
        style={'background': '#333', 'border': '2px solid #00ff00', 'color': 'white', 'width': '180px'}),

    StreamlitFlowNode("want", (650, 150), 
        {'content': '【WANT】\n預期產出 (Result)'}, 
        'output', 'left', target_position='left',
        style={'background': '#ccffcc', 'border': '2px solid green', 'color': 'black', 'width': '180px'})
]

edges = [
    StreamlitFlowEdge("e1", "have", "transform", animated=True),
    StreamlitFlowEdge("e2", "transform", "want", animated=True)
]

# --- 佈局邏輯 ---
col_ui, col_edit = st.columns([3, 1])

with col_ui:
    st.caption("視覺化流程圖")
    streamlit_flow("main_flow", nodes, edges, height=500, fit_view=True)

with col_edit:
    st.markdown("### 🎛️ 控制台")
    
    # 這裡模擬節點內的資料流
    have_text = st.text_area("1. 我有什麼 (Have)", height=150, placeholder="貼上你的爛代碼...")
    prompt_text = st.text_area("2. 轉換指令 (Transform)", value="重構這段代碼，使其符合 PEP8 並加上註解。", height=100)
    
    if st.button("🚀 執行轉換", disabled=not api_ready):
        if not have_text:
            st.warning("左邊沒東西啊！")
        else:
            with st.spinner("AI 正在煉成中..."):
                try:
                    # 呼叫 Gemini 1.5 Flash (速度快、省錢)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(f"【輸入代碼】\n{have_text}\n\n【需求】\n{prompt_text}")
                    st.session_state['result'] = response.text
                    st.success("轉換完成！")
                except Exception as e:
                    st.error(f"爆掉了：{e}")

# 顯示結果區域
if 'result' in st.session_state:
    st.markdown("### 3. 我得到的 (Want)")
    st.code(st.session_state['result'])
