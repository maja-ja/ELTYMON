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
    html, body, [class*="css"] {
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
# 2. 認證與 API 設定區塊 (多金鑰管理)
# ==========================================
# [API 設定指引]
# 取得所有的免費金鑰列表 (請在 .streamlit/secrets.toml 中設定)
try:
    GEMINI_FREE_KEYS = st.secrets.get("GEMINI_FREE_KEYS",[])
except:
    GEMINI_FREE_KEYS =[]

if not GEMINI_FREE_KEYS:
    st.warning("⚠️ 尚未設定 Gemini API 金鑰，請在 .streamlit/secrets.toml 中設定 `GEMINI_FREE_KEYS` 陣列。")

# [Google Sheets 設定指引]
# 需準備 credentials.json 放入專案目錄
def get_gspread_client():
    try:
        gc = gspread.service_account(filename="credentials.json") 
        # 請替換為您的 Google Sheet 網址或名稱
        sh = gc.open_by_url("YOUR_GOOGLE_SHEET_URL_HERE")
        return sh.sheet1
    except Exception as e:
        return None

worksheet = get_gspread_client()


# ==========================================
# 3. 狀態管理 (Session State)
# ==========================================
if 'ai_generated_content' not in st.session_state:
    st.session_state.ai_generated_content = ""
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'mock_db' not in st.session_state:
    st.session_state.mock_db = pd.DataFrame(columns=["日期戳記", "講義標題", "原始圖片網址", "AI整理內容"])
if 'api_key_index' not in st.session_state:
    # 記憶當前正常使用的 API 金鑰索引
    st.session_state.api_key_index = 0


# ==========================================
# 4. 核心功能函數
# ==========================================
def process_image_with_gemini(image_file):
    """呼叫 Gemini API，並在遇到限制時自動切換備用金鑰"""
    if not GEMINI_FREE_KEYS:
        raise Exception("未設定任何 Gemini API 金鑰，請檢查 secrets.toml")

    img = Image.open(image_file)
    
    # [給 Gemini 的講義結構化提示詞]
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
    
    # 輪詢嘗試所有的金鑰
    for offset in range(total_keys):
        current_index = (start_index + offset) % total_keys
        current_key = GEMINI_FREE_KEYS[current_index]
        
        try:
            # 配置當前的 API Key
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 發送請求
            response = model.generate_content([prompt, img])
            
            # 若成功，將當前成功的索引存回 session_state，下次優先使用這把
            if current_index != start_index:
                st.toast(f"✅ 成功切換至金鑰 {current_index + 1}", icon="🔑")
            st.session_state.api_key_index = current_index
            return response.text
            
        except Exception as e:
            error_msg = str(e)
            # 在介面右下角提示切換狀態
            st.toast(f"⚠️ 金鑰 {current_index + 1} 達到限制或失效，嘗試下一把...", icon="🔄")
            
            # 如果是最後一把金鑰也失敗了，就把錯誤拋出
            if offset == total_keys - 1:
                raise Exception(f"所有 {total_keys} 把 API 金鑰皆已達到限制或發生異常。最後錯誤：{error_msg}")

def save_to_collection(title, content):
    """將資料存入 Google Sheets (若無設定則寫入暫存 DB)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    img_url = "尚未綁定圖床 URL" 
    new_record =[timestamp, title, img_url, content]
    
    if worksheet:
        worksheet.append_row(new_record)
    else:
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
    options = ["➕ 新增講義 (拍照/上傳)"]
    if not df_history.empty:
        history_list = df_history.apply(lambda row: f"{row['講義標題']} ({row['日期戳記']})", axis=1).tolist()
        # 反轉列表讓最新的在最上面
        options.extend(history_list[::-1])
    
    # iPad 友善的大型選擇列
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
        
        current_img = camera_img if camera_img else upload_img
        
        # 檢查是否更換了圖片，若更換則清空上次生成的內容
        if current_img != st.session_state.current_image:
            st.session_state.current_image = current_img
            st.session_state.ai_generated_content = ""

        # 確認按鈕
        if current_img:
            if st.button("🚀 開始 AI 邏輯排版", type="primary"):
                with st.spinner("Gemini 正在為您智慧排版中... (若金鑰達上限將自動切換)"):
                    try:
                        result = process_image_with_gemini(current_img)
                        st.session_state.ai_generated_content = result
                    except Exception as e:
                        st.error(f"AI 生成失敗。錯誤訊息: {e}")
        
        st.write("---")
        
        # 即時生成顯示區 & 存檔確認
        if st.session_state.ai_generated_content:
            st.markdown("### 💡 AI 結構化整理結果")
            
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
                
                # 存檔後清除當前狀態
                st.session_state.ai_generated_content = ""
                st.session_state.current_image = None
                
else:
    # 歷史講義閱讀模式
    st.button("📖 閱讀模式 (歷史館藏)")
    
    # 解析選單中選擇的講義 (去掉最後括號內的日期時間)
    selected_title = selected_option.rsplit(" (", 1)[0]
    
    history_row = df_history[df_history['講義標題'] == selected_title]
    
    if not history_row.empty:
        content = history_row.iloc[0]['AI整理內容']
        date_stamp = history_row.iloc[0]['日期戳記']
        
        st.markdown(f"<h1>{selected_title}</h1>", unsafe_allow_html=True)
        st.caption(f"🗓️ 歸檔時間：{date_stamp}")
        st.write("---")
        
        st.markdown(content)
