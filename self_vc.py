import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, InvalidArgument, PermissionDenied, GoogleAPIError

st.set_page_config(layout="wide", page_title="Have vs Want Editor")

# --- 硬核防呆：檢查 API Key ---
# 這裡會自動從 Streamlit Cloud 的 Secrets 抓密碼
api_ready = False
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    api_ready = True
    # 快取 Gemini 模型實例
    if "gemini_model" not in st.session_state:
        try:
            st.session_state.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            st.success("Gemini 模型已準備就緒！")
        except Exception as e:
            st.error(f"初始化 Gemini 模型失敗：{e}")
            api_ready = False
else:
    st.error("⚠️ 尚未設定 API Key！請在 Streamlit Cloud 的 Secrets 設定 'GEMINI_API_KEY'。")
    api_ready = False

st.title("🎯 Have vs Want：代碼煉成陣")

# --- 初始化 session_state 變數 ---
if 'have_text' not in st.session_state:
    st.session_state['have_text'] = ""
if 'prompt_text' not in st.session_state:
    st.session_state['prompt_text'] = "重構這段代碼，使其符合 PEP8 並加上註解。"
if 'result' not in st.session_state:
    st.session_state['result'] = ""

# --- 定義節點和邊的函數 (動態更新) ---
def get_flow_elements(current_have_text, current_result):
    nodes = [
        StreamlitFlowNode("have", (50, 150),
            {'content': f'【HAVE】\n原始輸入:\n{current_have_text[:100]}...' if len(current_have_text) > 100 else f'【HAVE】\n原始輸入:\n{current_have_text}'},
            'input', 'right',
            style={'background': '#ffcccc', 'border': '2px solid red', 'color': 'black', 'width': '180px', 'height': '120px'}),

        StreamlitFlowNode("transform", (350, 150),
            {'content': '⚡ AI 轉換層\n(Processing)'},
            'default', 'right', target_position='left',
            style={'background': '#333', 'border': '2px solid #00ff00', 'color': 'white', 'width': '180px', 'height': '120px'}),

        StreamlitFlowNode("want", (650, 150),
            {'content': f'【WANT】\n預期產出:\n{current_result[:100]}...' if len(current_result) > 100 else f'【WANT】\n預期產出:\n{current_result}'},
            'output', 'left', target_position='left',
            style={'background': '#ccffcc', 'border': '2px solid green', 'color': 'black', 'width': '180px', 'height': '120px'})
    ]

    edges = [
        StreamlitFlowEdge("e1", "have", "transform", animated=True),
        StreamlitFlowEdge("e2", "transform", "want", animated=True)
    ]
    return nodes, edges

# --- 佈局邏輯 ---
col_ui, col_edit = st.columns([3, 1])

with col_ui:
    st.caption("視覺化流程圖 (節點內容會隨輸入/輸出更新)")
    # 動態獲取節點和邊
    current_nodes, current_edges = get_flow_elements(st.session_state['have_text'], st.session_state['result'])
    streamlit_flow("main_flow", current_nodes, current_edges, height=500, fit_view=True)

with col_edit:
    st.markdown("### 🎛️ 控制台")

    # 這裡模擬節點內的資料流
    st.session_state['have_text'] = st.text_area(
        "1. 我有什麼 (Have)",
        value=st.session_state['have_text'],
        height=150,
        placeholder="貼上你的爛代碼...",
        key="have_input" # 添加 key 以確保狀態正確
    )
    st.session_state['prompt_text'] = st.text_area(
        "2. 轉換指令 (Transform)",
        value=st.session_state['prompt_text'],
        height=100,
        key="prompt_input" # 添加 key 以確保狀態正確
    )

    if st.button("🚀 執行轉換", disabled=not api_ready):
        if not st.session_state['have_text']:
            st.warning("左邊沒東西啊！請在 '我有什麼 (Have)' 欄位輸入內容。")
        else:
            with st.spinner("AI 正在煉成中..."):
                try:
                    # 使用快取的 Gemini 模型實例
                    model = st.session_state.gemini_model
                    response = model.generate_content(
                        f"【輸入代碼】\n{st.session_state['have_text']}\n\n【需求】\n{st.session_state['prompt_text']}"
                    )
                    st.session_state['result'] = response.text
                    st.success("轉換完成！")
                    # 重新運行以更新流程圖
                    st.rerun()
                except ResourceExhausted:
                    st.error("爆掉了：API 請求頻率過高或超出配額。請稍後再試。")
                except InvalidArgument as e:
                    st.error(f"爆掉了：API 請求參數無效。錯誤訊息：{e}")
                except PermissionDenied:
                    st.error("爆掉了：API 權限不足。請檢查您的 API Key 是否正確且有權限。")
                except GoogleAPIError as e:
                    st.error(f"爆掉了：Google API 服務錯誤。錯誤訊息：{e}")
                except Exception as e:
                    st.error(f"爆掉了：發生未知錯誤：{e}")

# 顯示結果區域
st.markdown("### 3. 我得到的 (Want)")
if st.session_state['result']:
    st.code(st.session_state['result'], language="python") # 假設輸出是 Python 代碼
else:
    st.info("點擊 '🚀 執行轉換' 以查看 AI 產出的結果。")
