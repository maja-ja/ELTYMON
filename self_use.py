import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image, ImageOps
import base64
from io import BytesIO
import streamlit.components.v1 as components
import time
import markdown
import re # 用於處理轉義問題

# ... (fix_image_orientation, get_image_base64 保持不變)

def ai_generate_content(image, manual_input, instruction):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ 錯誤：API Key 未設定"
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # 改進 Prompt：要求 AI 使用標準 LaTeX 語法，且不要對特殊字元過度轉義
    prompt = """
    你是一位專業的高中物理/數學教師。請撰寫講義內容。
    【LaTeX 規範】：
    - 行內公式使用 $...$ (例如 $E=mc^2$)。
    - 獨立區塊公式使用 $$...$$。
    - 確保反斜線 \\ 指令正確 (例如 \\frac, \\lambda, \\propto)。
    - 不要使用任何會干擾渲染的 Markdown 轉義符。
    """
    parts = [prompt]
    if manual_input: parts.append(f"【補充/手打內容】：{manual_input}")
    if instruction: parts.append(f"【特別指令】：{instruction}")
    if image: parts.append(image)

    try:
        with st.spinner("🤖 AI 正進行物理邏輯解析與數學排版..."):
            response = model.generate_content(parts)
            return response.text
    except Exception as e:
        return f"AI 服務異常：{str(e)}"

# ==========================================
# 修正後的 PDF/HTML 模板
# ==========================================
def generate_printable_html(title, text_content, img_b64, img_width_percent):
    # 預先處理 text_content，防止 markdown 套件破壞 LaTeX 反斜線
    # 這是最關鍵的一步：將雙反斜線轉為單反斜線，確保送入 HTML 是正確的 LaTeX
    processed_content = text_content.replace('\\\\', '\\')
    
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables'])
    date_str = time.strftime("%Y-%m-%d")
    
    img_section = f'<div class="img-wrapper"><img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;"></div>' if img_b64 else ""

    return f"""
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        
        <!-- 【核心修復】MathJax 3 配置：允許 $ 作為行內定界符 -->
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
            body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.8; padding: 20px; background: #f0f0f0; }}
            #printable-area {{ background: white; width: 210mm; min-height: 297mm; margin: 0 auto; padding: 20mm; box-sizing: border-box; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #1a237e; text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
            .meta {{ text-align: right; color: #666; font-size: 12px; margin-bottom: 20px; }}
            .img-wrapper {{ text-align: center; margin: 25px 0; }}
            img {{ border: 1px solid #ddd; }}
            .content {{ font-size: 16px; text-align: justify; }}
            
            /* 下載按鈕 */
            #btn-container {{ text-align: center; padding: 20px; }}
            .download-btn {{ background: #1a237e; color: white; border: none; padding: 12px 30px; border-radius: 25px; font-weight: bold; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div id="btn-container">
            <button class="download-btn" onclick="downloadPDF()">📥 生成 PDF (含數學公式)</button>
        </div>

        <div id="printable-area">
            <h1>{title}</h1>
            <div class="meta">日期：{date_str}</div>
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
                
                // 【核心修復】確保 MathJax 渲染完成後再下載
                MathJax.typesetPromise().then(() => {{
                    setTimeout(() => {{
                        html2pdf().set(opt).from(element).save();
                    }}, 500);
                }});
            }}
        </script>
    </body>
    </html>
    """
def main():
    st.title("🎓 AI 名師講義編輯器 (列印優化版)")
    
    # 初始化 Session State
    if 'rotate_angle' not in st.session_state: st.session_state.rotate_angle = 0
    if 'generated_text' not in st.session_state: st.session_state.generated_text = ""

    # 範例文字 (供尚未呼叫 AI 時預覽)
    EXAMPLE_CONTENT = """
### 💡 這裡將會顯示 AI 生成的解析

這是預覽模式。請先在左側完成以下動作：
1. **上傳圖片** 並調整到正確的方向與大小。
2. 在下方輸入 **手打補充資訊** (選填)。
3. 按下 **「🚀 呼叫 AI 生成內容」**。

**[列印優化說明]**：
- 本系統自動支援 **LaTeX 數學公式** 渲染，如：$f(x) = \int_a^b g(t) dt$
- 下載後的 PDF 將自動符合 **A4 紙張格式**。
"""

    col_ctrl, col_prev = st.columns([1, 1.2], gap="large")

    # --- 左側：控制區 ---
    with col_ctrl:
        st.subheader("1. 素材準備")
        uploaded_file = st.file_uploader("上傳題目圖片 (支援手機拍照)", type=["jpg", "png", "jpeg"])
        
        image = None
        img_width = 80 # 預設寬度
        
        if uploaded_file:
            # 讀取與修正
            img_obj = Image.open(uploaded_file)
            image = fix_image_orientation(img_obj)
            
            # 手動旋轉邏輯
            if st.session_state.rotate_angle != 0:
                image = image.rotate(-st.session_state.rotate_angle, expand=True)

            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("🔄 旋轉 90°"):
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with c2:
                img_width = st.slider("圖片在 A4 紙上的寬度 (%)", 10, 100, 80)
            
            st.image(image, caption="當前圖片設定", use_container_width=True)

        st.divider()
        st.subheader("2. 文字補充與指令")
        manual_input = st.text_area("手打輸入 (補強圖片看不清的地方)", height=100, placeholder="例如：這題的重力加速度請以 10 計算...")
        ai_instr = st.text_input("給 AI 的特別要求", placeholder="例如：請針對解題步驟進行詳細說明")

        if st.button("🚀 呼叫 AI 生成內容", type="primary"):
            if not image and not manual_input:
                st.warning("請至少提供圖片或手打文字！")
            else:
                result = ai_generate_content(image, manual_input, ai_instr)
                st.session_state.generated_text = result
                st.rerun()

    # --- 右側：預覽與 PDF 下載 ---
    with col_prev:
        st.subheader("3. 講義預覽與列印")
        
        # 取得當前內容
        content_to_show = st.session_state.generated_text if st.session_state.generated_text else EXAMPLE_CONTENT
        
        # 讓老師進行最後微調
        edited_content = st.text_area("📝 直接修改講義內容", value=content_to_show, height=250)
        
        handout_title = st.text_input("講義標題", value="精選試題解析")

        # 生成最終 HTML
        img_b64 = get_image_base64(image) if image else ""
        final_html = generate_printable_html(handout_title, edited_content, img_b64, img_width)

        # 渲染 A4 預覽視窗
        st.info("💡 下方視窗模擬 A4 紙張大小，滿意後請點擊視窗內的「生成 PDF」按鈕。")
        components.html(final_html, height=850, scrolling=True)

if __name__ == "__main__":
    main()
# ... (main 函數邏輯保持不變)
