import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image, ImageOps
import base64
from io import BytesIO
import streamlit.components.v1 as components
import time
import markdown

# ==========================================
# 1. 核心設定
# ==========================================
st.set_page_config(page_title="AI 名師講義編輯器 Pro", layout="wide", page_icon="🎓")

# 介面美化 CSS
st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
        .stSlider { padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心工具函式 (完整定義)
# ==========================================

def fix_image_orientation(image):
    """修正手機拍照方向標籤 (解決倒過來的問題)"""
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass
    return image

def get_image_base64(image):
    """將圖片轉為 Base64 供 HTML 渲染"""
    if image is None: return ""
    buffered = BytesIO()
    # 確保轉成 RGB 模式避免 JPEG 儲存錯誤
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode()

def ai_generate_content(image, manual_input, instruction):
    """呼叫 AI API 並強制 LaTeX 格式"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ 錯誤：API Key 未設定"
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = """
    你是一位專業的高中物理/數學名師。請撰寫講義內容。
    【重要：LaTeX 公式規範】：
    1. 行內公式使用 $...$ (例如 $E=mc^2$)。
    2. 獨立區塊公式使用 $$...$$。
    3. 必須使用標準 LaTeX 指令 (如 \\frac, \\lambda, \\propto, \\approx)。
    4. 內容需包含：核心觀念、物理/數學推導、參考答案。
    """
    parts = [prompt]
    if manual_input: parts.append(f"【補充/手打內容】：{manual_input}")
    if instruction: parts.append(f"【特別指令】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正結合圖片與物理邏輯進行解析..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"AI 服務暫時無法使用：{str(e)}"

# ==========================================
# 3. 專業級 PDF/HTML 模板 (修復 LaTeX 顯示)
# ==========================================
def generate_printable_html(title, text_content, img_b64, img_width_percent):
    # 預處理：修正 markdown 可能造成的轉義問題，並確保 LaTeX 反斜線正確
    processed_content = text_content.replace('\\\\', '\\')
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        
        <!-- MathJax 3 配置：解決 $ 定界符不顯示的問題 -->
        <script>
        window.MathJax = {{
          tex: {{
            inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
            processEscapes: true
          }},
          options: {{
            skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
          }}
        }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.7; padding: 20px; background: #f0f0f0; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; margin: 0 auto; padding: 20mm; box-sizing: border-box; box-shadow: 0 0 10px rgba(0,0,0,0.2); }}
            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; font-size: 28px; }}
            .meta {{ text-align: right; color: #555; font-size: 12px; margin-bottom: 20px; border-bottom: 1px solid #eee; }}
            .img-wrapper {{ text-align: center; margin: 25px 0; }}
            img {{ border: 1px solid #000; padding: 2px; }}
            .content {{ font-size: 16px; text-align: justify; }}
            h2, h3 {{ color: #1a237e; border-left: 5px solid #1a237e; padding-left: 10px; margin-top: 25px; }}
            
            #btn-container {{ text-align: center; padding: 20px; }}
            .download-btn {{ background: #1a237e; color: white; border: none; padding: 15px 40px; border-radius: 30px; font-size: 18px; font-weight: bold; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 生成 PDF (含數學公式)</button>
        </div>

        <div id="printable-area">
            <h1>{title}</h1>
            <div class="meta">日期：{date_str} | AI 自動備課系統</div>
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
                    html2canvas: {{ scale: 3, useCORS: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                
                // 確保 MathJax 渲染完畢後再生成
                MathJax.typesetPromise().then(() => {{
                    setTimeout(() => {{
                        html2pdf().set(opt).from(element).save();
                    }}, 800);
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
        uploaded_file = st.file_uploader("上傳題目圖片 (支援手機拍照)", type=["jpg", "png", "jpeg"])
        
        image = None
        img_width = 80
        
        if uploaded_file:
            img_obj = Image.open(uploaded_file)
            # 呼叫轉正函式
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
        st.subheader("2. 補充與指令")
        manual_input = st.text_area("手打輸入補充內容", height=100)
        ai_instr = st.text_input("給 AI 的特別指令")

        if st.button("🚀 呼叫 AI 生成內容", type="primary"):
            if not image and not manual_input:
                st.warning("請提供素材！")
            else:
                result = ai_generate_content(image, manual_input, ai_instr)
                st.session_state.generated_text = result
                st.rerun()

    with col_prev:
        st.subheader("3. 預覽與編輯")
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else "### 這裡是預覽區\n請先在左側完成生成。"
        
        edited_content = st.text_area("📝 直接微調講義內容", value=content_to_show, height=300)
        handout_title = st.text_input("講義標題", value="精選試題解析")

        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)

        components.html(final_html, height=850, scrolling=True)

if __name__ == "__main__":
    main()
