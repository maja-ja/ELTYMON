import streamlit as st
import google.generativeai as genai
from PIL import Image
import base64
from io import BytesIO
import streamlit.components.v1 as components
import time

# ==========================================
# 設定與 CSS
# ==========================================
st.set_page_config(page_title="AI 圖片講義生成器", layout="centered", page_icon="📄")

st.markdown("""
    <style>
        .stTextArea textarea { font-size: 16px; line-height: 1.6; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 工具函式
# ==========================================

def get_image_base64(image):
    """將 PIL Image 轉為 Base64 字串，以便嵌入 HTML/PDF"""
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def ai_analyze_image(image, prompt_text):
    """呼叫 Gemini Vision 模型"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        return "❌ 錯誤：未設定 API Key，請檢查 secrets.toml。"
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # Flash 模型讀圖速度快且便宜

    full_prompt = [
        "你是一位專業的高中/大學教師。請針對這張圖片內容，撰寫一份詳細的教學講義。",
        "要求：",
        "1. 若圖片是題目，請給出解析與答案。",
        "2. 若圖片是圖表或筆記，請整理重點。",
        "3. 語氣要條理分明，適合學生閱讀。",
        "4. 請使用 Markdown 格式 (條列式、粗體)。",
        f"教師額外指令：{prompt_text}"
    ]
    
    try:
        with st.spinner("🤖 AI 正在觀察圖片並撰寫講義..."):
            response = model.generate_content([prompt_text, image])
            return response.text
    except Exception as e:
        return f"生成失敗：{str(e)}"

# ==========================================
# 主程式邏輯
# ==========================================

def main():
    st.title("📄 圖片轉講義生成器")
    st.caption("流程：上傳圖片 ➝ AI 自動撰寫 ➝ 老師修訂 ➝ 下載 PDF")

    # 1. 上傳區
    uploaded_file = st.file_uploader("請上傳圖片 (題目、板書、圖表)", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        # 顯示圖片
        image = Image.open(uploaded_file)
        st.image(image, caption="預覽圖片", use_container_width=True)
        
        # 2. AI 生成區
        st.divider()
        st.subheader("🤖 AI 解析設定")
        custom_prompt = st.text_input("給 AI 的指示 (選填)", placeholder="例如：請著重講解力學守恆的部分...")
        
        if st.button("🚀 開始生成文字敘述", type="primary"):
            explanation = ai_analyze_image(image, custom_prompt)
            st.session_state['generated_text'] = explanation

        # 3. 編輯區 (只有在生成過後才顯示)
        if 'generated_text' in st.session_state:
            st.divider()
            st.subheader("✏️ 內容修訂")
            
            # 讓老師修改 AI 寫的內容
            final_text = st.text_area(
                "講義內容 (支援 Markdown)", 
                value=st.session_state['generated_text'], 
                height=400
            )
            
            # 4. PDF 生成區
            st.divider()
            st.subheader("📥 匯出成品")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                title = st.text_input("講義標題", value="精選題型解析")
            with col2:
                # 準備資料給 HTML
                img_b64 = get_image_base64(image)
                date_str = time.strftime("%Y-%m-%d")
                
                # 處理換行轉 HTML
                html_text = final_text.replace('\n', '<br>').replace('**', '<b>').replace('**', '</b>')
                
                # 建立 PDF 的 HTML 模板 (包含中文字型設定)
                pdf_html = f"""
                <html>
                <head>
                    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
                    <style>
                        body {{ font-family: 'Noto Sans TC', sans-serif; padding: 40px; color: #333; }}
                        .header {{ text-align: center; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; margin-bottom: 30px; }}
                        h1 {{ color: #4f46e5; margin: 0; }}
                        .meta {{ color: #666; font-size: 12px; margin-top: 5px; }}
                        .img-container {{ text-align: center; margin-bottom: 30px; border: 1px solid #eee; padding: 10px; border-radius: 10px; }}
                        img {{ max-width: 90%; max-height: 400px; }}
                        .content {{ font-size: 14px; line-height: 1.8; text-align: justify; }}
                        b {{ color: #1e40af; }}
                    </style>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                </head>
                <body>
                    <div id="element-to-print">
                        <div class="header">
                            <h1>{title}</h1>
                            <div class="meta">生成日期：{date_str} | Generated by AI Teacher</div>
                        </div>
                        
                        <div class="img-container">
                            <img src="data:image/jpeg;base64,{img_b64}">
                        </div>
                        
                        <div class="content">
                            {html_text}
                        </div>
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
                            html2pdf().set(opt).from(element).save();
                        }}
                    </script>
                    
                    <div style="text-align: center; margin-top: 20px;">
                        <button onclick="generatePDF()" style="
                            background-color: #4f46e5; color: white; 
                            border: none; padding: 12px 24px; 
                            border-radius: 8px; font-size: 16px; 
                            cursor: pointer; font-weight: bold;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            ⬇️ 點擊下載 PDF
                        </button>
                    </div>
                </body>
                </html>
                """
                
            # 渲染下載按鈕
            components.html(pdf_html, height=100)

if __name__ == "__main__":
    main()
