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
# 1. 核心介面配置
# ==========================================
st.set_page_config(page_title="AI 講義分頁大師", layout="wide", page_icon="📄")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', 'Courier New', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
        .hint-card { background-color: #eef2ff; border-left: 5px solid #4f46e5; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        .hint-text { color: #4f46e5; font-size: 0.85rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心工具函式
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
    你是一位專業的高中教師。請撰寫講義。
    使用 $...$ 或 $$...$$ 撰寫 LaTeX。
    建議使用 ## 作為大題標題，這會觸發自動分頁。
    """
    parts = [prompt]
    if manual_input: parts.append(f"【補充內容】：{manual_input}")
    if instruction: parts.append(f"【指令】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正在進行深度解析與排版..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"AI 異常：{str(e)}"

# ==========================================
# 3. 虛擬 A4 分頁預覽模板 (核心邏輯)
# ==========================================
def generate_printable_html(title, text_content, img_b64, img_width_percent):
    # 處理標籤與 LaTeX
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>')
    processed_content = processed_content.replace('\\\\', '\\')
    
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <script>
        window.MathJax = {{
          tex: {{ inlineMath: [['$', '$']], displayMath: [['$$', '$$']], processEscapes: true }},
          svg: {{ fontCache: 'global' }}
        }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        
        <style>
            @page {{ size: A4; margin: 0; }}
            
            body {{ 
                font-family: 'Noto Sans TC', sans-serif; 
                line-height: 1.8; 
                padding: 0; margin: 0;
                background: #525659; /* 模擬 PDF 閱讀器的深色背景 */
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            
            #printable-area {{ 
                background: white; 
                width: 210mm; 
                min-height: 297mm;
                margin: 20px 0; 
                padding: 25mm; 
                box-sizing: border-box; 
                position: relative;
                
                /* 【核心】虛擬分頁線導引 - 每 297mm 畫一條紅線 */
                background-image: linear-gradient(to bottom, 
                    transparent 0%, 
                    transparent calc(297mm - 1px), 
                    #ff4d4d calc(297mm - 1px), 
                    #ff4d4d 297mm, 
                    transparent 297mm
                );
                background-size: 100% 297mm;
            }}

            /* 預覽模式下的分頁標籤 */
            #printable-area::after {{
                content: "--- 以上為第一頁 ---";
                position: absolute;
                top: 293mm;
                left: 50%;
                transform: translateX(-50%);
                color: #ff4d4d;
                font-size: 10px;
                font-weight: bold;
                pointer-events: none;
            }}

            /* 標題自動分頁 */
            .content h2 {{
                page-break-before: always;
                color: #1a237e;
                border-bottom: 2px solid #e8eaf6;
                margin-top: 30px;
            }}
            .content h2:first-child {{ page-break-before: avoid !important; margin-top: 0; }}

            .manual-page-break {{ page-break-before: always; height: 1px; }}

            /* 智慧避讓 */
            .content p, .content li, .img-wrapper, mjx-container, table {{
                page-break-inside: avoid;
                break-inside: avoid;
            }}

            .img-wrapper {{ text-align: center; margin: 30px 0; }}
            mjx-container {{ margin: 5px 2px !important; vertical-align: middle !important; display: inline-block !important; }}
            
            #btn-container {{ 
                text-align: center; padding: 15px; width: 100%;
                position: sticky; top: 0; background: #323639; z-index: 1000;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            }}
            .download-btn {{ 
                background: #4f46e5; color: white; border: none; padding: 12px 50px; 
                border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; 
            }}

            /* 【重要】下載 PDF 時隱藏輔助線 */
            @media print {{
                body {{ background: white !important; }}
                #printable-area {{ 
                    margin: 0 !important; 
                    box-shadow: none !important; 
                    background-image: none !important; /* 移除紅線 */
                }}
                #printable-area::after {{ display: none; }}
                #btn-container {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 下載正式 PDF (不含導引線)</button>
        </div>

        <div id="printable-area">
            <h1 style="text-align:center; color:#1a237e;">{title}</h1>
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
                    html2canvas: {{ scale: 3, useCORS: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }},
                    pagebreak: {{ mode: ['avoid-all', 'css', 'legacy'] }}
                }};
                
                MathJax.typesetPromise().then(() => {{
                    setTimeout(() => {{
                        html2pdf().set(opt).from(element).save();
                    }}, 1200);
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
    st.title("🎓 AI 講義分頁大師 Pro")
    
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")

    with col_ctrl:
        st.subheader("1. 內容設定")
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
            
            st.image(image, use_container_width=True)

        st.divider()
        manual_input = st.text_area("補充文字 (會與圖片整合)", height=100)
        ai_instr = st.text_input("AI 指令", placeholder="例如：請將解析做成表格...")

        if st.button("🚀 呼叫 AI 生成內容", type="primary"):
            if not image and not manual_input:
                st.warning("請提供素材！")
            else:
                result = ai_generate_content(image, manual_input, ai_instr)
                st.session_state.generated_text = result
                st.rerun()

    with col_prev:
        st.subheader("2. A4 虛擬分頁預覽")
        
        with st.container():
            st.markdown("""
                <div class="hint-card">
                    <p class="hint-text">🚩 預覽中出現的<b>紅色橫線</b>代表 A4 斷頁處。</p>
                    <p class="hint-text">🚩 若文字壓線，請使用 <b>[換頁]</b> 標籤或 <b>## 標題</b> 手動調整。</p>
                </div>
            """, unsafe_allow_html=True)
        
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else "### 這裡是預覽區\n請先在上傳區操作內容。"
        
        edited_content = st.text_area("📝 編輯內容 (直接在此修改內容或調整分頁)", value=content_to_show, height=300)
        handout_title = st.text_input("講義標題", value="精選試題解析")

        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)

        # 這裡高度設高一點，讓老師可以看到整張 A4 甚至兩張的範疇
        components.html(final_html, height=1000, scrolling=True)

if __name__ == "__main__":
    main()
