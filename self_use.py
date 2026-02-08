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
# 1. 介面設定
# ==========================================
st.set_page_config(page_title="AI 講義排版大師 Pro", layout="wide", page_icon="🎓")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3.2em; }
        .info-card { background-color: #f0f9ff; border-left: 5px solid #0ea5e9; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
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
    你是一位專業教師。請撰寫講義。
    【格式】使用 $...$ 或 $$...$$ 撰寫 LaTeX。
    【排版】請直接開始內容，不要有前言或空白行。
    """
    parts = [prompt]
    if manual_input: parts.append(f"【補充/指令】：{manual_input}")
    if instruction: parts.append(f"【特別要求】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正在精確計算排版空間..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"AI 異常：{str(e)}"

# ==========================================
# 3. 嚴格 A4 容器模板 (固定高度起點與終點)
# ==========================================
def generate_printable_html(title, text_content, img_b64, img_width_percent):
    # 清理開頭贅字與換行
    text_content = text_content.strip()
    text_content = re.sub(r'^(\[換頁\]|\s|\n)+', '', text_content)
    
    # 處理換頁與 LaTeX
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
                background: #2c2c2c;
                display: flex; flex-direction: column; align-items: center;
            }}
            
            #printable-area {{ 
                background: white; 
                width: 210mm; 
                min-height: 297mm;
                margin: 20px 0; 
                /* 【核心設定】固定高度起點與終點 */
                padding: 20mm 25mm; /* 上下固定 20mm 邊距 */
                box-sizing: border-box; 
                position: relative;

                /* 【視覺導引】藍色為起點，紅色為終點 */
                background-image: 
                    linear-gradient(to bottom, #e0f2fe 20mm, transparent 20mm), /* 頂部固定高度標示 */
                    linear-gradient(to bottom, transparent 277mm, #fee2e2 277mm); /* 底部固定低度標示 */
                background-size: 100% 297mm;
            }}

            /* 內容容器 */
            .content {{ 
                font-size: 16px; 
                text-align: justify; 
                position: relative;
                z-index: 2;
            }}

            /* 標題分頁邏輯 */
            .content h2 {{
                page-break-before: always;
                break-before: always;
                color: #1a237e; 
                border-left: 5px solid #1a237e; 
                padding-left: 10px; 
                margin-top: 30px; 
            }}
            
            /* 確保第一頁從固定高度開始，不換頁 */
            .content h2:first-child {{
                page-break-before: avoid !important;
                margin-top: 0 !important;
            }}

            .manual-page-break {{ page-break-before: always; height: 1px; }}

            /* 智慧避讓：確保物件不跨越固定低度 */
            .content p, .content li, .img-wrapper, mjx-container, table {{
                page-break-inside: avoid;
                break-inside: avoid;
                margin-bottom: 15px;
            }}

            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; margin-top: 0; }}
            .img-wrapper {{ text-align: center; margin: 15px 0; }}
            mjx-container {{ margin: 8px 0 !important; vertical-align: middle !important; display: inline-block !important; }}

            #btn-container {{ 
                text-align: center; padding: 15px; width: 100%;
                position: sticky; top: 0; background: #1a1a1a; z-index: 9999;
            }}
            .download-btn {{ 
                background: #0284c7; color: white; border: none; padding: 12px 60px; 
                border-radius: 4px; font-size: 16px; font-weight: bold; cursor: pointer; 
            }}

            @media print {{
                body {{ background: white !important; }}
                #printable-area {{ 
                    margin: 0 !important; box-shadow: none !important; 
                    background-image: none !important; /* 下載時移除導引色塊 */
                }}
                #btn-container {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 下載 A4 講義 (固定邊距校正版)</button>
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
                    html2canvas: {{ 
                        scale: 3, 
                        useCORS: true, 
                        logging: false,
                        scrollY: 0 
                    }},
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
# 4. 主程式入口
# ==========================================

def main():
    st.title("🎓 AI 講義排版大師 Pro")
    
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")

    with col_ctrl:
        st.subheader("1. 素材與設定")
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
        manual_input = st.text_area("補充文字", height=150)
        ai_instr = st.text_input("AI 指令")

        if st.button("🚀 呼叫 AI 生成內容", type="primary"):
            if not image and not manual_input:
                st.warning("⚠️ 請提供素材！")
            else:
                result = ai_generate_content(image, manual_input, ai_instr)
                st.session_state.generated_text = result
                st.rerun()

    with col_prev:
        st.subheader("2. 嚴格 A4 預覽")
        
        st.markdown("""
            <div class="info-card">
                <b>📏 固定高度說明：</b><br>
                1. 頂部<b>藍色區塊</b>為固定起點 (20mm)。<br>
                2. 底部<b>紅色區塊</b>為固定終點 (277mm)。<br>
                3. 內容會自動在此區間內排版，下載時色塊會自動消失。
            </div>
        """, unsafe_allow_html=True)
        
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else "### 預覽區"
        edited_content = st.text_area("📝 內容修訂", value=content_to_show, height=300)
        handout_title = st.text_input("講義標題", value="精選解析")

        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)

        components.html(final_html, height=1000, scrolling=True)

if __name__ == "__main__":
    main()
