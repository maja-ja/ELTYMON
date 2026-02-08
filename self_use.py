import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image, ImageOps # 新增 ImageOps 用於自動轉正
import base64
from io import BytesIO
import streamlit.components.v1 as components
import time
import markdown
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 設定與 CSS
# ==========================================
st.set_page_config(page_title="AI 講義生成器 Pro", layout="wide", page_icon="🎓")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
        .rotate-btn { margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 工具函式
# ==========================================

def fix_image_orientation(image):
    """
    自動修正手機照片的 EXIF 方向資訊
    """
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass # 如果沒有 EXIF 資訊就不處理
    return image

def compress_image_for_db(image):
    """壓縮圖片以存入 Google Sheets"""
    if image is None: return ""
    img_copy = image.copy()
    img_copy.thumbnail((600, 600))
    buffered = BytesIO()
    # 轉為 RGB 避免 PNG 透明度造成 JPEG 存檔錯誤
    if img_copy.mode in ("RGBA", "P"): img_copy = img_copy.convert("RGB")
    img_copy.save(buffered, format="JPEG", quality=60)
    return base64.b64encode(buffered.getvalue()).decode()

def get_image_base64(image):
    """轉檔給 PDF 使用"""
    if image is None: return ""
    buffered = BytesIO()
    # 轉為 RGB
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.save(buffered, format="JPEG")
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
    """呼叫 Gemini"""
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
# 3. 主程式邏輯
# ==========================================

def main():
    st.title("🎓 AI 混合輸入講義生成器")

    # 初始化 session state 用來記錄旋轉角度
    if 'rotate_angle' not in st.session_state:
        st.session_state.rotate_angle = 0
    if 'last_uploaded_file' not in st.session_state:
        st.session_state.last_uploaded_file = None

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("1. 輸入素材")
        
        uploaded_file = st.file_uploader("上傳題目或圖表", type=["jpg", "png", "jpeg"])
        
        image = None
        if uploaded_file:
            # 檢測是否換了新圖片，如果是，重置旋轉角度
            if uploaded_file.name != st.session_state.last_uploaded_file:
                st.session_state.rotate_angle = 0
                st.session_state.last_uploaded_file = uploaded_file.name

            # 1. 讀取並自動修正 EXIF 方向
            original_image = Image.open(uploaded_file)
            image = fix_image_orientation(original_image)

            # 2. 應用手動旋轉
            if st.session_state.rotate_angle != 0:
                image = image.rotate(-st.session_state.rotate_angle, expand=True)

            # 3. 顯示旋轉按鈕
            col_rot1, col_rot2 = st.columns([1, 2])
            with col_rot1:
                if st.button("🔄 旋轉圖片 90°"):
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun() # 重新整理頁面以顯示旋轉後的圖
            
            # 4. 顯示圖片
            st.image(image, caption=f"預覽圖片 (已旋轉 {st.session_state.rotate_angle}°)", use_container_width=True)

        st.divider()

        st.markdown("##### ✍️ 手動輸入 (選填)")
        manual_text = st.text_area("補充條件或題目文字", height=100, placeholder="例如：請把數字 5 改成 10...")
        instruction = st.text_input("🤖 AI 指令", placeholder="例如：請做成克漏字...")

        if st.button("🚀 開始生成講義", type="primary"):
            if not image and not manual_text:
                st.warning("請提供圖片或文字！")
            else:
                result = ai_generate_content(image, manual_text, instruction)
                st.session_state['generated_text'] = result

    with col_right:
        st.subheader("2. 編輯與輸出")
        
        if 'generated_text' in st.session_state:
            final_text = st.text_area("內容修訂", value=st.session_state['generated_text'], height=600)
            pdf_title = st.text_input("講義標題", value="課程講義")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("💾 存入資料庫"):
                    if save_to_google_sheets(pdf_title, final_text, image):
                        st.success("✅ 存檔成功！")
            with col_b2:
                st.info("👇 預覽與下載在下方")

            st.divider()

            # PDF 生成
            img_html = ""
            if image:
                img_b64 = get_image_base64(image)
                img_html = f'<div class="img-container"><img src="data:image/jpeg;base64,{img_b64}"></div>'
            
            date_str = time.strftime("%Y-%m-%d")
            html_content = markdown.markdown(final_text, extensions=['fenced_code', 'tables'])

            pdf_html = f"""
            <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
                <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
                <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                <style>
                    body {{ font-family: 'Noto Sans TC', sans-serif; padding: 30px; line-height: 1.6; color: #333; }}
                    h1 {{ color: #4f46e5; text-align: center; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }}
                    .meta {{ text-align: center; color: #666; font-size: 12px; margin-bottom: 20px; }}
                    .img-container {{ text-align: center; margin: 20px 0; }}
                    img {{ max-width: 80%; border: 1px solid #ddd; border-radius: 5px; padding: 5px; }}
                    ul, ol {{ padding-left: 20px; }}
                    code {{ background: #f1f5f9; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
                </style>
            </head>
            <body>
                <div id="element-to-print">
                    <h1>{pdf_title}</h1>
                    <div class="meta">生成日期：{date_str}</div>
                    {img_html}
                    <div class="content">{html_content}</div>
                </div>
                <script>
                    function generatePDF() {{
                        const element = document.getElementById('element-to-print');
                        const opt = {{
                            margin: 15, filename: '{pdf_title}.pdf',
                            image: {{ type: 'jpeg', quality: 0.98 }},
                            html2canvas: {{ scale: 2, useCORS: true }},
                            jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                        }};
                        setTimeout(() => {{ html2pdf().set(opt).from(element).save(); }}, 800);
                    }}
                </script>
                <div style="text-align: center; margin-top: 15px;">
                    <button onclick="generatePDF()" style="background: #4f46e5; color: white; border: none; padding: 12px 25px; border-radius: 8px; cursor: pointer; font-weight: bold;">
                        📥 下載 PDF
                    </button>
                </div>
            </body>
            </html>
            """
            components.html(pdf_html, height=120)

if __name__ == "__main__":
    main()
