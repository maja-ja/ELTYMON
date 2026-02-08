import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image, ImageOps
import base64
from io import BytesIO
import streamlit.components.v1 as components
import time
import markdown
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 設定與 CSS
# ==========================================
st.set_page_config(page_title="AI 講義排版大師", layout="wide", page_icon="📄")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
        /* 讓預覽區有陰影，像一張紙 */
        .preview-box { border: 1px solid #ddd; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 工具函式
# ==========================================

def fix_image_orientation(image):
    """修正手機照片方向"""
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass
    return image

def get_image_base64(image):
    """轉檔給 HTML/PDF 使用"""
    if image is None: return ""
    buffered = BytesIO()
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def compress_image_for_db(image):
    """壓縮存入資料庫用"""
    if image is None: return ""
    img_copy = image.copy()
    img_copy.thumbnail((600, 600))
    buffered = BytesIO()
    if img_copy.mode in ("RGBA", "P"): img_copy = img_copy.convert("RGB")
    img_copy.save(buffered, format="JPEG", quality=60)
    return base64.b64encode(buffered.getvalue()).decode()

def save_to_google_sheets(title, content, image):
    """寫入資料庫"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="history", ttl=0)
        img_b64 = compress_image_for_db(image)
        new_row = pd.DataFrame([{
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "title": title,
            "content": content,
            "image_b64": img_b64
        }])
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(worksheet="history", data=updated_df)
        return True
    except Exception as e:
        st.error(f"❌ 資料庫寫入失敗: {str(e)}")
        return False

def ai_generate_content(image, manual_input, instruction):
    """呼叫 Gemini API"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ 錯誤：未設定 API Key。"
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = """
    你是一位專業的高中/大學教師。請根據使用者提供的資訊（圖片或文字）撰寫教學講義。
    【格式要求】：
    1. 使用 Markdown 語法。
    2. 數學公式請務必使用 LaTeX 格式，並用 $ 包夾（例如 $E=mc^2$）。
    3. 內容需包含：核心觀念、解析/推導過程、參考答案。
    """
    
    parts = [prompt]
    if manual_input: parts.append(f"【補充文字】：{manual_input}")
    if instruction: parts.append(f"【指令】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正在閱讀圖片與文字..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"生成失敗：{str(e)}"

# ==========================================
# 3. HTML 生成器 (核心預覽邏輯)
# ==========================================
def generate_html(title, text_content, img_b64, img_width):
    """
    動態生成 HTML，用於預覽和 PDF 下載
    """
    # 將 Markdown 轉為 HTML
    html_body = markdown.markdown(text_content, extensions=['fenced_code', 'tables'])
    
    # 圖片 HTML (如果有圖片)
    img_tag = ""
    if img_b64:
        img_tag = f"""
        <div class="img-container">
            <img src="data:image/jpeg;base64,{img_b64}" style="width: {img_width}%;">
        </div>
        """
    
    date_str = time.strftime("%Y-%m-%d")

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <style>
            body {{ 
                font-family: 'Noto Sans TC', sans-serif; 
                padding: 40px; 
                line-height: 1.8; 
                color: #333; 
                background-color: white; /* 預覽時背景白 */
            }}
            h1 {{ color: #4f46e5; text-align: center; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; margin-bottom: 5px; }}
            .meta {{ text-align: center; color: #666; font-size: 12px; margin-bottom: 30px; }}
            .img-container {{ text-align: center; margin: 20px 0; }}
            img {{ border: 1px solid #ddd; border-radius: 5px; padding: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            ul, ol {{ padding-left: 20px; }}
            p {{ margin-bottom: 15px; }}
            code {{ background: #f1f5f9; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
            blockquote {{ border-left: 4px solid #ccc; margin-left: 0; padding-left: 15px; color: #555; }}
        </style>
    </head>
    <body>
        <div id="element-to-print">
            <h1>{title}</h1>
            <div class="meta">生成日期：{date_str}</div>
            {img_tag}
            <div class="content">{html_body}</div>
        </div>
        
        <script>
            function generatePDF() {{
                const element = document.getElementById('element-to-print');
                const opt = {{
                    margin: 10,
                    filename: '{title}.pdf',
                    image: {{ type: 'jpeg', quality: 0.98 }},
                    html2canvas: {{ scale: 2, useCORS: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                // 延遲 800ms 確保 MathJax 數學公式渲染完畢
                setTimeout(() => {{
                    html2pdf().set(opt).from(element).save();
                }}, 800);
            }}
        </script>
        
        <!-- 下載按鈕 (僅在 PDF 模式顯示，Streamlit 預覽不需點擊) -->
        <div style="text-align: center; margin-top: 30px; display: none;" id="dl-btn-container">
             <button onclick="generatePDF()">下載 PDF</button>
        </div>
    </body>
    </html>
    """

# ==========================================
# 4. 主程式邏輯
# ==========================================

def main():
    st.title("📄 AI 講義排版大師")
    st.caption("流程：調整圖片/文字 (省流量) ➝ 滿意後再呼叫 AI ➝ 下載成品")

    # --- 初始化 Session State ---
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""
    if 'last_file_name' not in st.session_state: st.session_state.last_file_name = ""

    # 預設範例文字 (當還沒呼叫 AI 時顯示)
    SAMPLE_TEXT = """
### 📌 範例標題 (預覽模式)

這是一個 **範例文字區塊**，用來讓您預覽圖片與文字的排版效果。
當您按下左側的「呼叫 AI」按鈕後，這裡的內容將會被 AI 的解析取代。

- 您可以調整圖片大小。
- 您可以旋轉圖片方向。
- **數學公式範例**： $E = mc^2$ 或 $\\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$

請確認左側圖片設定滿意後，再進行生成。
    """

    col_left, col_right = st.columns([1, 1], gap="medium")

    # ================= 左側：設定與 AI 控制 =================
    with col_left:
        st.subheader("1. 圖片與設定")
        
        # 1. 上傳
        uploaded_file = st.file_uploader("上傳題目圖片", type=["jpg", "png", "jpeg"])
        
        image = None
        if uploaded_file:
            # 重置邏輯：如果是新圖，角度歸零
            if uploaded_file.name != st.session_state.last_file_name:
                st.session_state.rotate_angle = 0
                st.session_state.last_file_name = uploaded_file.name
                
            # 處理圖片
            original = Image.open(uploaded_file)
            image = fix_image_orientation(original)
            
            # 應用旋轉
            if st.session_state.rotate_angle != 0:
                image = image.rotate(-st.session_state.rotate_angle, expand=True)

            # --- 控制面板 ---
            col_c1, col_c2 = st.columns([1, 2])
            with col_c1:
                if st.button("🔄 轉 90°"):
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with col_c2:
                # 圖片大小滑桿
                img_width = st.slider("圖片寬度 (%)", 10, 100, 80, step=5)
            
            st.image(image, caption=f"目前預覽 (寬度 {img_width}%)", use_container_width=True)
            
        else:
            img_width = 80 # 預設值

        st.divider()

        # 2. 文字輸入
        st.markdown("##### ✍️ 給 AI 的提示")
        manual_text = st.text_area("補充條件 (選填)", height=100, placeholder="例如：請把數字 10 改成 20...")
        instruction = st.text_input("指令 (選填)", placeholder="例如：請做成克漏字...")

        # 3. 生成按鈕
        st.markdown("---")
        if st.button("🚀 呼叫 AI 生成解析 (扣除額度)", type="primary"):
            if not image and not manual_text:
                st.warning("請先上傳圖片或輸入文字！")
            else:
                result = ai_generate_content(image, manual_text, instruction)
                st.session_state['generated_text'] = result
                st.rerun() # 重新整理以更新右側內容

    # ================= 右側：即時預覽與輸出 =================
    with col_right:
        st.subheader("2. 即時預覽與編輯")
        
        # 決定要顯示什麼文字 (AI 生成的 OR 範例文字)
        current_content = st.session_state['generated_text'] if st.session_state['generated_text'] else SAMPLE_TEXT
        
        # 讓老師可以編輯 (無論是範例還是 AI 結果)
        final_text = st.text_area(
            "📝 內容編輯區 (所見即所得)", 
            value=current_content, 
            height=300,
            key="editor" # 使用 key 綁定
        )

        pdf_title = st.text_input("講義標題", value="精選試題解析")

        # --- 生成 HTML 預覽 ---
        img_b64 = get_image_base64(image) if image else ""
        
        # 產生完整的 HTML 字串
        full_html = generate_html(pdf_title, final_text, img_b64, img_width)
        
        # 顯示預覽視窗 (模擬 A4 紙張)
        st.markdown("##### 📄 A4 預覽結果 (請捲動查看)")
        components.html(full_html, height=600, scrolling=True)

        st.divider()
        
        # --- 下載區 ---
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            # 下載按鈕：利用 HTML 注入 JS 按鈕
            # 我們這裡生成一個只有按鈕的小 HTML，按下後會觸發上面的 PDF 下載函數
            download_btn_html = f"""
            <html>
            <body>
                <script>
                    // 這裡的邏輯是：Streamlit Components 是 iframe，無法直接呼叫另一個 component 的函數。
                    // 所以我們最簡單的方法是重新渲染一次完整的 HTML，但這次只顯示按鈕。
                    // 但為了體驗，我們建議直接使用上面的預覽視窗做 PDF 下載，或者提供一個專門的下載按鈕。
                </script>
                <div style="text-align: center;">
                    <button onclick="parent.document.getElementsByTagName('iframe')[0].contentWindow.generatePDF()" 
                    style="
                        background: linear-gradient(to right, #4f46e5, #6366f1); 
                        color: white; border: none; padding: 12px 25px; 
                        border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%;">
                        📥 下載 PDF
                    </button>
                    <div style="font-size:12px; color:#666; margin-top:5px;">(點擊後請稍等彈出視窗)</div>
                </div>
            </body>
            </html>
            """
            # 這裡我們做一個取巧：
            # 直接在剛剛的大預覽視窗底下，再放一個小的 HTML component 專門用來觸發下載
            # 注意：跨 iframe 呼叫比較困難，所以我們直接再渲染一次「專門下載用」的隱藏 HTML
            
            # 【修正方案】：為了保證下載成功，我們在下方渲染一個包含「下載按鈕」與「完整內容」的 HTML
            # 但把內容隱藏起來，只顯示按鈕。
            
            download_html_hidden = full_html.replace('display: none;" id="dl-btn-container"', 'display: block;" id="dl-btn-container"')
            download_html_hidden = download_html_hidden.replace('<div id="element-to-print">', '<div id="element-to-print" style="display:none">') # 隱藏內容，只留按鈕邏輯
            
            # 使用更直觀的方式：直接渲染一個帶有下載功能的按鈕區塊
            # 由於 components 隔離，我們必須把內容包進去
            st.components.v1.html(f"""
                {full_html}
                <style>
                    /* 覆蓋樣式：隱藏內容，只顯示按鈕 */
                    #element-to-print {{ display: none; }}
                    #dl-btn-container {{ display: block !important; margin-top: 0; }}
                    button {{ 
                        background: #4f46e5; color: white; border: none; 
                        padding: 15px 30px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%;
                    }}
                    button:hover {{ background: #4338ca; }}
                </style>
            """, height=60)

        with col_d2:
            if st.button("💾 存入資料庫"):
                if save_to_google_sheets(pdf_title, final_text, image):
                    st.success("✅ 存檔成功！")

if __name__ == "__main__":
    main()
