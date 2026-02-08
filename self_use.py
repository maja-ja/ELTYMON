import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image, ImageOps
import base64
from io import BytesIO
import streamlit.components.v1 as components
import time
import markdown
import re

# ==========================================
# 1. 核心設定
# ==========================================
st.set_page_config(page_title="AI 名師講義編輯器 Pro", layout="wide", page_icon="🎓")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 工具函式
# ==========================================

def fix_image_orientation(image):
    try: image = ImageOps.exif_transpose(image)
    except: pass
    return image

def get_image_base64(image):
    if image is None: return ""
    buffered = BytesIO()
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode()

def ai_generate_content(image, manual_input, instruction):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ 錯誤：API Key 未設定"
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = """
    你是一位專業的高中教師。請根據資訊撰寫講義。
    【重要：LaTeX 規範】
    - 使用 $...$ 包夾行內公式，$I \\propto \\frac{1}{\\lambda^4}$
    - 獨立公式使用 $$...$$
    - 確保數學符號使用標準 LaTeX 指令。
    """
    parts = [prompt]
    if manual_input: parts.append(f"【補充內容】：{manual_input}")
    if instruction: parts.append(f"【指令】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正在整理邏輯與數學排版..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"AI 異常：{str(e)}"

# ==========================================
# 3. 專業級 PDF/HTML 模板 (防重疊優化版)
# ==========================================
def generate_printable_html(title, text_content, img_b64, img_width_percent):
    # 預防性清理：修正反斜線與轉義問題
    clean_content = text_content.replace('\\\\', '\\')
    html_body = markdown.markdown(clean_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        
        <!-- 使用 SVG 模式，在 PDF 導出時最穩定 -->
        <script>
        window.MathJax = {{
          tex: {{
            inlineMath: [['$', '$']],
            displayMath: [['$$', '$$']],
            processEscapes: true
          }},
          svg: {{ fontCache: 'global' }}
        }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ 
                font-family: 'Noto Sans TC', sans-serif; 
                line-height: 1.8; /* 增加行高防止重疊 */
                padding: 20px; 
                background: #f4f4f9; 
            }}
            #printable-area {{ 
                background: white; width: 210mm; min-height: 297mm; 
                margin: 0 auto; padding: 25mm; box-sizing: border-box; 
            }}
            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            .img-wrapper {{ text-align: center; margin: 30px 0; }}
            
            /* 【關鍵修復】給予公式足夠的垂直空間 */
            mjx-container {{
                margin: 5px 2px !important;
                vertical-align: middle !important;
                display: inline-block !important;
            }}
            .content {{ font-size: 16px; text-align: justify; }}
            p {{ margin-bottom: 15px; word-break: break-word; }}
            
            #btn-container {{ text-align: center; padding: 20px; }}
            .download-btn {{ background: #1a237e; color: white; border: none; padding: 15px 40px; border-radius: 30px; font-size: 18px; font-weight: bold; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 生成 PDF (修復排版重疊)</button>
        </div>

        <div id="printable-area">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:12px; color:#666;">日期：{date_str}</div>
            {img_section}
            <div class="content">{html_body}</div>
        </div>
        
        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{
                    margin: 0,
                    filename: '{title}.pdf',
                    image: {{ type: 'jpeg', quality: 1.0 }},
                    html2canvas: {{ scale: 3, useCORS: true, logging: false }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                
                // 第一階段：呼叫 MathJax 渲染
                MathJax.typesetPromise().then(() => {{
                    // 第二階段：給予 1.5 秒緩衝讓瀏覽器完成 Reflow 排版
                    setTimeout(() => {{
                        html2pdf().set(opt).from(element).save();
                    }}, 1500);
                }});
            }}
        </script>
    </body>
    </html>
    """

# ==========================================
# 4. 主程式介面
# ==========================================

def main():
    st.title("🎓 AI 名師講義編輯器 Pro")
    
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""

    col_ctrl, col_prev = st.columns([1, 1.2], gap="large")

    with col_ctrl:
        st.subheader("1. 素材準備")
        uploaded_file = st.file_uploader("上傳題目圖片", type=["jpg", "png", "jpeg"])
        
        image = None
        img_width = 80
        
        if uploaded_file:
            img_obj = Image.open(uploaded_file)
            image = fix_image_orientation(img_obj)
            if st.session_state.rotate_angle != 0:
                image = image.rotate(-st.session_state.rotate_angle, expand=True)

            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("🔄 旋轉 90°"):
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with c2:
                img_width = st.slider("圖片寬度 (%)", 10, 100, 80)
            
            st.image(image, caption="預覽圖片", use_container_width=True)

        st.divider()
        manual_input = st.text_area("補充內容", height=100)
        ai_instr = st.text_input("給 AI 的特別指令")

        if st.button("🚀 呼叫 AI 生成內容", type="primary"):
            if not image and not manual_input:
                st.warning("請提供素材！")
            else:
                result = ai_generate_content(image, manual_input, ai_instr)
                st.session_state.generated_text = result
                st.rerun()

    with col_prev:
        st.subheader("2. 預覽與編輯")
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else "### 這裡是預覽區"
        edited_content = st.text_area("📝 微調講義內容", value=content_to_show, height=300)
        handout_title = st.text_input("講義標題", value="精選試題解析")

        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)

        components.html(final_html, height=850, scrolling=True)

if __name__ == "__main__":
    main()
