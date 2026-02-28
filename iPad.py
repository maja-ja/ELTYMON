import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from datetime import datetime
from PIL import Image

st.set_page_config(
    page_title="智慧講義館藏系統",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-size: 18px !important;
        line-height: 1.8 !important;
    }
    h1 { font-size: 2.5rem !important; color: #1E3A8A; font-weight: 700 !important; }
    h2 { font-size: 2rem !important; color: #2563EB; font-weight: 600 !important; border-bottom: 2px solid #E5E7EB; padding-bottom: 0.5rem; }
    h3 { font-size: 1.5rem !important; color: #3B82F6; }
    .stButton > button {
        width: 100%;
        min-height: 60px;
        font-size: 1.2rem !important;
        font-weight: bold;
        border-radius: 12px;
        background-color: #F8FAFC;
        border: 2px solid #E2E8F0;
        transition: all 0.3s ease;
    }
    .stButton > button:hover { border-color: #3B82F6; color: #3B82F6; }
    .stButton > button:active { background-color: #EFF6FF; }
    .stCameraInput, .stFileUploader {
        padding: 10px;
        background-color: #F8FAFC;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    div[data-testid="stExpander"] {
        background-color: #F8FAFC;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
    }
    div[data-testid="stExpander"] summary {
        font-size: 1.3rem !important;
        font-weight: bold;
        color: #1E3A8A;
    }
</style>
""", unsafe_allow_html=True)

try:
    GEMINI_FREE_KEYS = st.secrets.get("GEMINI_FREE_KEYS",[])
except:
    GEMINI_FREE_KEYS =[]

def get_gspread_client():
    gc = gspread.service_account(filename="credentials.json") 
    sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1fyGma34kn3t7uvBArurnQmSiH3UFwGsYFb-Ygv3_rD0/edit?gid=0#gid=0")
    return sh.sheet1

worksheet = get_gspread_client()

if 'ai_generated_content' not in st.session_state:
    st.session_state.ai_generated_content = ""
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'api_key_index' not in st.session_state:
    st.session_state.api_key_index = 0

def process_image_with_gemini(image_file):
    img = Image.open(image_file)
    prompt = """
    你是一個專業的教育筆記整理助手。請分析這張講義/筆記圖片的內容，並使用結構化的 Markdown 格式輸出。
    請遵循以下排版規則以利在 iPad 螢幕上閱讀：
    # 📝 核心主旨：(用一句話總結這份講義的重點)
    ## 📌 重點摘要
    (使用列點式整理最重要的 3~5 個核心概念)
    ## 📖 詳細內容
    (根據講義的邏輯架構，使用 ### 子標題與條列、粗體來排版詳細內容)
    ## 💡 關鍵字與名詞解釋
    (萃取講義中的專有名詞，並以「**關鍵字**：解釋」的方式列出)
    """
    total_keys = len(GEMINI_FREE_KEYS)
    start_index = st.session_state.api_key_index
    
    for offset in range(total_keys):
        current_index = (start_index + offset) % total_keys
        current_key = GEMINI_FREE_KEYS[current_index]
        try:
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([prompt, img])
            if current_index != start_index:
                st.toast(f"✅ 成功切換至金鑰 {current_index + 1}", icon="🔑")
            st.session_state.api_key_index = current_index
            return response.text
        except Exception as e:
            st.toast(f"⚠️ 金鑰 {current_index + 1} 達到限制，嘗試下一把...", icon="🔄")
            if offset == total_keys - 1:
                raise Exception(f"所有 API 金鑰皆已達到限制。最後錯誤：{str(e)}")

def save_to_collection(title, content):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    img_url = "尚未綁定圖床 URL" 
    new_record = [timestamp, title, img_url, content]
    worksheet.append_row(new_record)


with st.sidebar:
    st.title("📚 館藏導覽")
    st.write("---")
    app_mode = st.radio("請選擇操作模式：", ["✨ 新增講義", "📂 我的館藏"])


if app_mode == "✨ 新增講義":
    st.header("✨ 新增智慧講義")
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            camera_img = st.camera_input("📷 拍照")
        with col2:
            upload_img = st.file_uploader("📂 或上傳照片", type=['jpg', 'jpeg', 'png'])
        
        current_img = camera_img if camera_img else upload_img
        if current_img != st.session_state.current_image:
            st.session_state.current_image = current_img
            st.session_state.ai_generated_content = ""

        if current_img:
            if st.button("🚀 開始 AI 邏輯排版", type="primary"):
                with st.spinner("Gemini 正在為您智慧排版中..."):
                    try:
                        result = process_image_with_gemini(current_img)
                        st.session_state.ai_generated_content = result
                    except Exception as e:
                        st.error(f"AI 生成失敗。錯誤訊息: {e}")
        
        st.write("---")
        if st.session_state.ai_generated_content:
            st.markdown("### 💡 AI 結構化整理結果")
            with st.container():
                st.markdown(st.session_state.ai_generated_content)
            
            st.write("---")
            default_title = f"{datetime.now().strftime('%Y-%m-%d %H:%M')} 講義"
            doc_title = st.text_input("講義標題", value=default_title)
            
            if st.button("💾 確認存檔至館藏"):
                save_to_collection(doc_title, st.session_state.ai_generated_content)
                st.success(f"✅ 《{doc_title}》已成功存檔！")
                st.session_state.ai_generated_content = ""
                st.session_state.current_image = None

elif app_mode == "📂 我的館藏":
    st.header("📂 我的智慧館藏")
    st.write("---")
    
    with st.spinner("載入館藏資料中..."):
        records = worksheet.get_all_records()
        df_history = pd.DataFrame(records)
    
    if df_history.empty:
        st.info("目前館藏尚無資料，請前往「新增講義」建立您的第一份筆記！")
    else:
        # 清理並轉換日期格式，確保可分組
        df_history = df_history[df_history['日期戳記'].astype(bool)] # 過濾空行
        df_history['日期'] = pd.to_datetime(df_history['日期戳記']).dt.date
        df_history = df_history.sort_values(by='日期戳記', ascending=False)
        
        # 標記是否為第一個展開項 (預設將最新日期的資料展開)
        is_first = True
        
        # 以「日期」分組呈現
        for date, group in df_history.groupby('日期', sort=False):
            with st.expander(f"🗓️ {date} (共 {len(group)} 份)", expanded=is_first):
                for index, row in group.iterrows():
                    st.markdown(f"### 📄 {row['講義標題']}")
                    st.caption(f"🕒 歸檔時間：{row['日期戳記']}")
                    st.markdown(row['AI整理內容'])
                    st.divider()
            
            is_first = False
