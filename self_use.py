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
# 1. 介面與視覺風格設定
# ==========================================
st.set_page_config(page_title="AI 名師講義編輯器 Pro", layout="wide", page_icon="🎓")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; font-family: 'Consolas', monospace; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3.2em; }
        .info-card { background-color: #f0f4ff; border-left: 5px solid #1a237e; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
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
    【格式要求】使用 $...$ 或 $$...$$ 撰寫 LaTeX。
    【自動換頁】請適度分段。系統會自動偵測頁面邊界，確保內容（如公式、圖片）不會被切斷。
    """
    parts = [prompt]
    if manual_input: parts.append(f"【補充/指令】：{manual_input}")
    if instruction: parts.append(f"【特別要求】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正在智能排版並計算分頁空間..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"AI 異常：{str(e)}"

# ==========================================
# 3. 智慧分頁 HTML/CSS 模板
# ==========================================
def generate_printable_html(title, text_content, img_b64, img_width_percent):
    # 處理手動換頁
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>')
    # 修正 LaTeX 轉義問題
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
                background: #323639; /* 模擬 PDF 閱讀器背景 */
                display: flex; flex-direction: column; align-items: center;
            }}
            
            #printable-area {{ 
                background: white; 
                width: 210mm; 
                min-height: 297mm;
                margin: 20px 0; 
                padding: 25mm; 
                box-sizing: border-box; 
                position: relative;
                box-shadow: 0 0 15px rgba(0,0,0,0.5);

                /* 【虛擬導引紅線】每隔 297mm 自動出現，導引老師查看分頁 */
                background-image: linear-gradient(to bottom, 
                    transparent 296.5mm, 
                    rgba(255, 0, 0, 0.5) 296.5mm, 
                    rgba(255, 0, 0, 0.5) 297mm, 
                    transparent 297mm
                );
                background-size: 100% 297mm;
            }}

            /* 【智慧分頁核心：規避切割】 */
            .content p, .content li, .img-wrapper, mjx-container, blockquote, table {{
                page-break-inside: avoid; /* 強制：不要在元素中間斷開 */
                break-inside: avoid;
                margin-bottom: 15px;
            }}

            h2, h3 {{ 
                page-break-after: avoid; /* 強制：標題必須跟著下方內容 */
                break-after: avoid;
                color: #1a237e; 
                border-left: 5px solid #1a237e; 
                padding-left: 10px; 
                margin-top: 30px; 
            }}
            
            h2 {{ page-break-before: auto; }} /* 二級標題可自動換頁 */

            .manual-page-break {{ page-break-before: always; height: 1px; }}

            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; margin-top: 0; }}
            .img-wrapper {{ text-align: center; margin: 25px 0; }}
            mjx-container {{ margin: 8px 0 !important; vertical-align: middle !important; display: inline-block !important; width: auto !important; }}
            
            .content {{ font-size: 16px; text-align: justify; }}

            /* 按鈕列樣式 */
            #btn-container {{ 
                text-align: center; padding: 15px; width: 100%;
                position: sticky; top: 0; background: #202124; z-index: 9999;
                box-shadow: 0 2px 10px rgba(0,0,0,0.5);
            }}
            .download-btn {{ 
                background: #1a73e8; color: white; border: none; padding: 12px 60px; 
                border-radius: 4px; font-size: 16px; font-weight: bold; cursor: pointer; 
                transition: background 0.2s;
            }}
            .download-btn:hover {{ background: #1765cc; }}

            /* 下載 PDF 時隱藏紅線與 UI */
            @media print {{
                body {{ background: white !important; }}
                #printable-area {{ 
                    margin: 0 !important; box-shadow: none !important; 
                    background-image: none !important; /* 移除預覽紅線 */
                }}
                #btn-container {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 下載 A4 智慧分頁講義</button>
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
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }},
                    pagebreak: {{ mode: ['avoid-all', 'css', 'legacy'] }} // 開啟最強分頁模式
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
    st.title("🎓 AI 名師講義編輯器 Pro")
    
    # Session States
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""

    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")

    with col_ctrl:
        st.subheader("1. 內容素材")
        uploaded_file = st.file_uploader("上傳題目/截圖 (AI 會自動辨識)", type=["jpg", "png", "jpeg"])
        
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
                img_width = st.slider("圖片在 A4 紙上的寬度 (%)", 10, 100, 80)
            
            st.image(image, use_container_width=True)

        st.divider()
        manual_input = st.text_area("補充文字 (在此手打題目或要求)", height=150)
        ai_instr = st.text_input("AI 指令 (例如：請將解析轉為條列式)")

        if st.button("🚀 呼叫 AI 生成講義內容", type="primary"):
            if not image and not manual_input:
                st.warning("⚠️ 請先提供圖片或輸入文字！")
            else:
                result = ai_generate_content(image, manual_input, ai_instr)
                st.session_state.generated_text = result
                st.rerun()

    with col_prev:
        st.subheader("2. 智慧分頁預覽區")
        
        st.markdown("""
            <div class="info-card">
                <b>💡 智慧分頁說明：</b><br>
                1. 預覽中的<b>紅線</b>為 A4 斷頁參考位置。<br>
                2. 系統會自動規避將公式或圖片切斷，若內容壓線，它會自動跳至下一頁。<br>
                3. 若需強制換頁，請在編輯區輸入 <b>[換頁]</b>。
            </div>
        """, unsafe_allow_html=True)
        
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else "### 這裡是 A4 預覽區\n完成左側設定後，AI 解析將會出現在此。"
        
        edited_content = st.text_area("📝 內容修訂 (支援 Markdown / LaTeX)", value=content_to_show, height=300)
        handout_title = st.text_input("講義標題", value="精選解析")

        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)

        # 高度設為 1000px 方便滾動查看
        components.html(final_html, height=1000, scrolling=True)

if __name__ == "__main__":
    main()
