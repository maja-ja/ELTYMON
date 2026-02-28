import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from datetime import datetime
from PIL import Image
import io

# ==========================================
# 1. 頁面與全域設定 (針對 iPad 13" 優化)
# ==========================================
st.set_page_config(
    page_title="智慧講義館藏系統",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 針對 iPad 大螢幕觸控優化的 CSS
st.markdown("""
<style>
    /* 調整全局字體與行距，提升閱讀舒適度 */
    html, body,[class*="css"] {
        font-size: 18px !important;
        line-height: 1.8 !important;
    }
    
    /* 放大 Markdown 標題，建立清晰層次 */
    h1 { font-size: 2.5rem !important; color: #1E3A8A; font-weight: 700 !important; }
    h2 { font-size: 2rem !important; color: #2563EB; font-weight: 600 !important; border-bottom: 2px solid #E5E7EB; padding-bottom: 0.5rem; }
    h3 { font-size: 1.5rem !important; color: #3B82F6; }
    
    /* 放大按鈕，增加手指觸控熱區 (Touch Target) */
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
    .stButton > button:hover {
        border-color: #3B82F6;
        color: #3B82F6;
    }
    .stButton > button:active {
        background-color: #EFF6FF;
    }

    /* 確保相機與上傳區塊視覺連貫 */
    .stCameraInput, .stFileUploader {
        padding: 10px;
        background-color: #F8FAFC;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. 認證與 API 設定區塊 (請填入您的金鑰)
# ==========================================
# [API 設定指引]
# 1. 將您的 Gemini API Key 放入 Streamlit Secrets 或直接替換下方字串
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)

# 2. Google Sheets API 設定 (需準備 service_account.json)
# 由於 gspread 需要認證，此處寫好標準邏輯，若無設定檔案則預設為展示模式
def get_gspread_client():
    try:
        # 請確保工作目錄下有 Google Cloud 服務帳號的 credentials.json
        gc = gspread.service_account(filename="credentials.json") 
        # 請替換為您的 Google Sheet 網址或名稱
        sh = gc.open_by_url("YOUR_GOOGLE_SHEET_URL_HERE")
        worksheet = sh.sheet1
        return worksheet
    except Exception as e:
        return None

worksheet = get_gspread_client()


# ==========================================
# 3. 狀態管理 (Session State)
# ==========================================
# 初始化應用程式需要記住的變數，防止畫面重整時資料遺失
if 'ai_generated_content' not in st.session_state:
    st.session_state.ai_generated_content = ""
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'mock_db' not in st.session_state:
    # 作為尚未接上 Google Sheets 時的暫存資料庫
    st.session_state.mock_db = pd.DataFrame(columns=["日期戳記", "講義標題", "原始圖片網址", "AI整理內容"])


# ==========================================
# 4. 核心功能函數
# ==========================================
def process_image_with_gemini(image_file):
    """呼叫 Gemini API 解析圖片並產生結構化 Markdown"""
    img = Image.open(image_file)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    #[給 Gemini 的講義結構化提示詞]
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
    
    response = model.generate_content([prompt, img])
    return response.text

def save_to_collection(title, content):
    """將資料存入 Google Sheets (或暫存 DB)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 圖片網址需將圖片上傳至雲端硬碟/Imgur後獲取，此處以預設文字代替
    img_url = "尚未綁定圖床 URL" 
    
    new_record =[timestamp, title, img_url, content]
    
    if worksheet:
        worksheet.append_row(new_record)
    else:
        # Fallback 寫入暫存 DB (Session State)
        new_df = pd.DataFrame([new_record], columns=st.session_state.mock_db.columns)
        st.session_state.mock_db = pd.concat([st.session_state.mock_db, new_df], ignore_index=True)


# ==========================================
# 5. UI 佈局：側邊欄 (Sidebar) - 館藏區
# ==========================================
with st.sidebar:
    st.title("📚 我的智慧館藏")
    st.write("---")
    
    # 讀取歷史資料
    if worksheet:
        try:
            records = worksheet.get_all_records()
            df_history = pd.DataFrame(records)
        except:
            df_history = pd.DataFrame(columns=["日期戳記", "講義標題", "AI整理內容"])
    else:
        df_history = st.session_state.mock_db

    # 建立選單：第一項固定為新增功能
    options =["➕ 新增講義 (拍照/上傳)"]
    if not df_history.empty:
        # 將標題與日期結合成選單顯示字串
        history_list = df_history.apply(lambda row: f"{row['講義標題']} ({row['日期戳記']})", axis=1).tolist()
        options.extend(history_list)
    
    # iPad 友善的大型選擇列 (selectbox 在 iPad 上點擊體驗佳)
    selected_option = st.selectbox("選擇操作或瀏覽歷史講義：", options)


# ==========================================
# 6. UI 佈局：主畫面 (Main) - 閱讀與操作區
# ==========================================
if selected_option == "➕ 新增講義 (拍照/上傳)":
    
    st.header("✨ 新增智慧講義")
    
    #[核心 UI 要求] - 操作模組與生成模組一體化
    with st.container():
        st.write("請使用 iPad 鏡頭拍照或上傳講義圖片：")
        
        col1, col2 = st.columns(2)
        with col1:
            camera_img = st.camera_input("📷 拍照")
        with col2:
            upload_img = st.file_uploader("📂 或上傳照片", type=['jpg', 'jpeg', 'png'])
        
        # 決定當前使用的圖片來源
        current_img = camera_img if camera_img else upload_img
        
        # 檢查是否更換了圖片，若更換則清空上次生成的內容
        if current_img != st.session_state.current_image:
            st.session_state.current_image = current_img
            st.session_state.ai_generated_content = ""

        # 確認按鈕
        if current_img:
            if st.button("🚀 開始 AI 邏輯排版", type="primary"):
                with st.spinner("Gemini 正在為您智慧排版中..."):
                    try:
                        result = process_image_with_gemini(current_img)
                        st.session_state.ai_generated_content = result
                    except Exception as e:
                        st.error(f"AI 生成失敗，請檢查 API 金鑰設定。錯誤訊息: {e}")
        
        st.write("---")
        
        # 即時生成顯示區 & 存檔確認
        if st.session_state.ai_generated_content:
            st.markdown("### 💡 AI 結構化整理結果")
            
            # 建立一個容器來顯示 Markdown，給予視覺上的區隔
            with st.container():
                st.markdown(st.session_state.ai_generated_content)
            
            st.write("---")
            st.write("確認內容無誤後，請設定標題並存檔：")
            
            # 自動命名機制
            default_title = f"{datetime.now().strftime('%Y-%m-%d %H:%M')} 講義"
            doc_title = st.text_input("講義標題", value=default_title)
            
            if st.button("💾 確認存檔至館藏"):
                save_to_collection(doc_title, st.session_state.ai_generated_content)
                st.success(f"✅ 《{doc_title}》已成功存入您的智慧館藏！")
                
                # 存檔後清除當前狀態，準備下一次上傳
                st.session_state.ai_generated_content = ""
                st.session_state.current_image = None
                
else:
    # 歷史講義閱讀模式
    st.button("📖 閱讀模式 (歷史館藏)")
    
    # 解析選單中選擇的講義
    selected_title = selected_option.rsplit(" (", 1)[0]
    
    # 從歷史資料庫尋找內容
    history_row = df_history[df_history['講義標題'] == selected_title]
    
    if not history_row.empty:
        content = history_row.iloc[0]['AI整理內容']
        date_stamp = history_row.iloc[0]['日期戳記']
        
        # 顯示標題與時間戳記
        st.markdown(f"<h1>{selected_title}</h1>", unsafe_allow_html=True)
        st.caption(f"🗓️ 歸檔時間：{date_stamp}")
        st.write("---")
        
        # 顯示排版過的 Markdown 講義內容
        st.markdown(content)
