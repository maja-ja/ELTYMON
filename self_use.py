
import streamlit as st
import pandas as pd
import base64
import time
import json
import re
from io import BytesIO
from PIL import Image
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# ==========================================
# 1. 核心配置與 CSS 美化 (教師專業版)
# ==========================================
st.set_page_config(
    page_title="LectureGen Pro | 智慧講義生成系統",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
            
            :root {
                --primary: #4f46e5;
                --bg-light: #f8fafc;
                --card-bg: #ffffff;
                --text-dark: #1e293b;
            }

            .stApp { background-color: var(--bg-light); font-family: 'Noto Sans TC', sans-serif; }
            
            /* 卡片樣式 */
            .concept-card {
                background: var(--card-bg);
                padding: 20px;
                border-radius: 12px;
                border-left: 5px solid var(--primary);
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                margin-bottom: 15px;
            }
            
            /* 標題樣式 */
            .section-header {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--primary);
                margin-bottom: 20px;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 10px;
            }

            /* PDF 預覽區 */
            .pdf-preview-box {
                border: 1px solid #cbd5e1;
                padding: 40px;
                background: white;
                min-height: 600px;
                box-shadow: inset 0 0 20px rgba(0,0,0,0.05);
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 工具函式：資料庫、圖片處理、AI
# ==========================================

@st.cache_data(ttl=60)
def load_data(sheet_name):
    """讀取 Google Sheets 資料"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df.fillna("")
    except Exception as e:
        st.error(f"資料庫連線錯誤: {e}")
        return pd.DataFrame()

def save_data(df, sheet_name):
    """寫入 Google Sheets"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(worksheet=sheet_name, data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

def image_to_base64(uploaded_file):
    """將上傳的圖片轉為 Base64 字串 (用於顯示與 AI 分析)"""
    if uploaded_file is None:
        return None
    try:
        bytes_data = uploaded_file.getvalue()
        return base64.b64encode(bytes_data).decode()
    except Exception as e:
        st.error(f"圖片處理失敗: {e}")
        return None

def ai_generate_explanation(image_parts, point, notes, concepts):
    """呼叫 Gemini Pro Vision 生成講解"""
    api_key = st.secrets["GEMINI"]["API_KEY"]
    if not api_key:
        return "❌ 未設定 API Key"
    
    genai.configure(api_key=api_key)
    
    # 判斷是否有圖
    model_name = "gemini-1.5-flash" # 使用支援圖片的 Flash 模型
    model = genai.GenerativeModel(model_name)
    
    prompt = f"""
    角色：你是一位資深的高中補習班名師。
    任務：根據提供的題目資訊，撰寫一段精闢的「題目詳解」。
    
    輸入資訊：
    1. 核心考點：{point}
    2. 學生常錯/注意點：{notes}
    3. 使用觀念：{concepts}
    
    輸出要求：
    1. 語氣專業、循序漸進，適合放入講義中。
    2. 使用 Markdown 格式。
    3. 若有數學公式，請使用 LaTeX 格式 (例如 $x^2$)。
    4. 分為「解題思路」與「詳細步驟」兩部分。
    """
    
    inputs = [prompt]
    if image_parts:
        inputs.append(image_parts) # image_parts 應該是 PIL Image 物件或特定的 dict 格式

    try:
        with st.spinner("🤖 AI 正在撰寫詳解..."):
            response = model.generate_content(inputs)
            return response.text
    except Exception as e:
        return f"AI 生成失敗: {e}"

# ==========================================
# 3. 頁面邏輯
# ==========================================

def page_input_processor():
    """頁面 1: 題目登錄與 AI 生成"""
    st.markdown('<div class="section-header">📝 題目登錄與 AI 解析</div>', unsafe_allow_html=True)
    
    col_img, col_text = st.columns([1, 1])
    
    with col_img:
        uploaded_file = st.file_uploader("上傳題目圖片", type=['png', 'jpg', 'jpeg'])
        img_display = None
        if uploaded_file:
            st.image(uploaded_file, caption="題目預覽", use_container_width=True)
            # 準備給 AI 的圖片格式
            img_bytes = uploaded_file.getvalue()
            img_display = {"mime_type": uploaded_file.type, "data": img_bytes}
            
            # 暫存圖片 Base64 供後續存檔 (注意：存入 Sheets 可能會因太長而失敗，建議存圖片連結，這裡示範存 Session)
            b64_str = base64.b64encode(img_bytes).decode()
            st.session_state['current_img_b64'] = b64_str

    with col_text:
        exam_point = st.text_input("🎯 核心考點", placeholder="例如：牛頓第二運動定律、三角函數和差角")
        notes = st.text_area("⚠️ 注意點 / 陷阱", placeholder="例如：注意單位換算、正負號方向")
        concepts = st.text_input("📚 關聯觀念 (用於索引)", placeholder="例如：力學, 向量")
        
        if st.button("✨ 讓 AI 生成詳解", type="primary", use_container_width=True):
            if not uploaded_file and not exam_point:
                st.warning("請至少上傳圖片或輸入考點")
            else:
                # 呼叫 AI (這裡需要將 bytes 轉為 PIL Image 傳給某些版本的 SDK，或直接傳 dict)
                # 修正：Gemini Python SDK 接受 PIL Image
                pil_image = Image.open(uploaded_file) if uploaded_file else None
                result = ai_generate_explanation(pil_image, exam_point, notes, concepts)
                st.session_state['generated_expl'] = result

    # 顯示與編輯生成結果
    if 'generated_expl' in st.session_state:
        st.divider()
        st.subheader("🤖 AI 生成結果 (可手動修訂)")
        final_expl = st.text_area("詳解內容", value=st.session_state['generated_expl'], height=300)
        
        col_save, _ = st.columns([1, 4])
        with col_save:
            if st.button("💾 存入題庫", use_container_width=True):
                # 讀取現有資料
                df_q = load_data("questions")
                
                new_row = {
                    "id": int(time.time()),
                    # 注意：實際專案建議將圖片上傳至圖床，存 URL。這裡簡化，不存 Base64 進 Sheets 避免爆掉，僅存 metadata
                    "image_name": uploaded_file.name if uploaded_file else "no_image", 
                    "exam_point": exam_point,
                    "notes": notes,
                    "concepts": concepts,
                    "explanation": final_expl,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M")
                }
                
                updated_df = pd.concat([df_q, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(updated_df, "questions"):
                    st.success("✅ 題目已存入資料庫！")
                    # 如果需要，這裡可以把圖片存在本地或 Session 供 PDF 生成使用
                    if 'temp_question_bank' not in st.session_state:
                        st.session_state.temp_question_bank = []
                    # 將包含 Base64 的完整資料存在 Session 以便稍後生成 PDF
                    new_row['image_b64'] = st.session_state.get('current_img_b64', "")
                    st.session_state.temp_question_bank.append(new_row)

def page_concept_library():
    """頁面 2: 觀念庫檢索與維護"""
    st.markdown('<div class="section-header">🗂️ 觀念卡資料庫</div>', unsafe_allow_html=True)

    # 1. 檢索區
    search_q = st.text_input("🔍 搜尋觀念...", placeholder="輸入關鍵字，如：動量、虛擬語氣...")
    
    df_c = load_data("concepts")
    if df_c.empty:
        st.info("觀念庫目前為空，請直接在下方新增資料。")
        # 初始化 DataFrame 結構
        df_c = pd.DataFrame(columns=["topic", "intro", "deep_dive", "related_qs", "years"])

    # 過濾邏輯
    if search_q:
        filtered_df = df_c[df_c.apply(lambda row: search_q.lower() in row.astype(str).str.lower().values.sum(), axis=1)]
    else:
        filtered_df = df_c

    # 2. 顯示卡片
    for idx, row in filtered_df.iterrows():
        with st.expander(f"📌 {row['topic']} (歷年考題: {row['years']})"):
            st.markdown(f"""
            **📖 基本介紹：**  
            {row['intro']}
            
            **💡 深度講解：**  
            {row['deep_dive']}
            
            **🔗 可能搭配考題：**  
            {row['related_qs']}
            """)

    # 3. 編輯模式 (Data Editor)
    st.divider()
    st.subheader("🛠️ 維護觀念資料")
    edited_df = st.data_editor(df_c, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 更新觀念庫"):
        if save_data(edited_df, "concepts"):
            st.success("資料庫已更新！")

def page_pdf_generator():
    """頁面 3: 講義合成與 PDF 輸出"""
    st.markdown('<div class="section-header">📄 客製化講義生成</div>', unsafe_allow_html=True)

    col_select, col_preview = st.columns([1, 1])
    
    with col_select:
        st.subheader("1. 選擇內容")
        
        # 來源 A: 本次 Session 新增的題目 (含圖片 Base64)
        session_qs = st.session_state.get('temp_question_bank', [])
        selected_session_qs = []
        if session_qs:
            st.markdown("**🔹 本次新增的題目**")
            for q in session_qs:
                if st.checkbox(f"題目：{q['exam_point']} ({q['timestamp']})", key=f"sq_{q['id']}"):
                    selected_session_qs.append(q)
        
        # 來源 B: 觀念庫
        df_c = load_data("concepts")
        selected_concepts = []
        if not df_c.empty:
            st.markdown("**🔹 選擇要放入的觀念**")
            # 使用 Multiselect 比較乾淨
            concept_topics = df_c['topic'].tolist()
            picked_topics = st.multiselect("搜尋並加入觀念", concept_topics)
            selected_concepts = df_c[df_c['topic'].isin(picked_topics)].to_dict('records')

    with col_preview:
        st.subheader("2. 講義預覽")
        
        # 組合 HTML
        html_content = ""
        
        # Part 1: 觀念區
        if selected_concepts:
            html_content += "<div class='section'><h2>第一部分：核心觀念重點</h2>"
            for c in selected_concepts:
                html_content += f"""
                <div class='concept-box'>
                    <h3>📌 {c['topic']}</h3>
                    <p><b>年份紀錄：</b>{c['years']}</p>
                    <div class='content'>{c['intro']}</div>
                    <div class='deep-dive'><b>名師講解：</b><br>{c['deep_dive']}</div>
                </div>
                <hr>
                """
            html_content += "</div>"

        # Part 2: 題目區
        if selected_session_qs:
            html_content += "<div class='section'><h2>第二部分：精選試題解析</h2>"
            for q in selected_session_qs:
                img_tag = ""
                if q.get('image_b64'):
                    img_tag = f'<img src="data:image/jpeg;base64,{q["image_b64"]}" style="max-width:100%; border:1px solid #ddd; margin: 10px 0;">'
                
                # 處理 Markdown 轉 HTML (簡單處理，實際可用 markdown 庫)
                expl_html = q['explanation'].replace('\n', '<br>')
                
                html_content += f"""
                <div class='question-box'>
                    <div class='meta'><b>考點：</b>{q['exam_point']} | <b>關聯：</b>{q['concepts']}</div>
                    {img_tag}
                    <div class='alert'>⚠️ <b>注意：</b>{q['notes']}</div>
                    <div class='explanation'>
                        <h4>📝 解析</h4>
                        {expl_html}
                    </div>
                </div>
                <br><br>
                """
            html_content += "</div>"
            
        if not html_content:
            st.info("👈 請從左側選擇要加入的內容")
        else:
            # 渲染預覽
            st.components.v1.html(f"""
                <style>
                    body {{ font-family: 'Helvetica', sans-serif; padding: 20px; color: #333; }}
                    h2 {{ color: #4f46e5; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
                    h3 {{ color: #1e293b; margin-top: 0; }}
                    .concept-box {{ background: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                    .alert {{ background: #fff7ed; color: #c2410c; padding: 10px; border-radius: 5px; margin: 10px 0; font-weight: bold; }}
                    .explanation {{ background: #fff; padding: 15px; border-left: 4px solid #4f46e5; }}
                </style>
                {html_content}
            """, height=600, scrolling=True)

            # 3. PDF 下載按鈕 (使用 html2pdf.js)
            # 構建完整的 HTML 包含 JS
            pdf_template = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Noto Sans TC', sans-serif; padding: 40px; }}
                    .section {{ margin-bottom: 30px; page-break-inside: avoid; }}
                    h1 {{ text-align: center; color: #4f46e5; }}
                    h2 {{ border-bottom: 2px solid #4f46e5; padding-bottom: 5px; margin-top: 30px; }}
                    .concept-box, .question-box {{ margin-bottom: 20px; }}
                    img {{ max-width: 80%; display: block; margin: 10px auto; }}
                </style>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
            </head>
            <body>
                <div id="content_to_print">
                    <h1>LectureGen 專屬講義</h1>
                    <p style="text-align:center; color:#666;">生成日期：{time.strftime("%Y-%m-%d")}</p>
                    {html_content}
                </div>
                <script>
                    function downloadPDF() {{
                        const element = document.getElementById('content_to_print');
                        const opt = {{
                            margin: 10,
                            filename: 'LectureGen_Handout.pdf',
                            image: {{ type: 'jpeg', quality: 0.98 }},
                            html2canvas: {{ scale: 2, useCORS: true }},
                            jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                        }};
                        html2pdf().set(opt).from(element).save();
                    }}
                </script>
                <div style="text-align: center; margin-top: 20px;">
                    <button onclick="downloadPDF()" style="
                        background: #4f46e5; color: white; border: none; 
                        padding: 12px 25px; border-radius: 8px; font-size: 16px; 
                        cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        📥 下載 PDF 講義
                    </button>
                </div>
            </body>
            </html>
            """
            components.html(pdf_template, height=100)

# ==========================================
# 4. 主程式入口
# ==========================================
def main():
    inject_custom_css()
    
    with st.sidebar:
        st.title("🎓 LectureGen Pro")
        st.caption("教師專用備課系統 v2.0")
        
        menu = st.radio("功能導航", ["📝 題目登錄", "🗂️ 觀念庫", "📄 講義生成"], label_visibility="collapsed")
        
        st.divider()
        st.subheader("⚙️ 設定")
        api_status = "✅ 已連結" if "GEMINI" in st.secrets else "❌ 未設定"
        db_status = "✅ 已連結" if "connections" in st.secrets else "❌ 未設定"
        st.caption(f"API: {api_status}")
        st.caption(f"Database: {db_status}")
        
        if st.button("清除暫存資料"):
            st.session_state.clear()
            st.rerun()

    if menu == "📝 題目登錄":
        page_input_processor()
    elif menu == "🗂️ 觀念庫":
        page_concept_library()
    elif menu == "📄 講義生成":
        page_pdf_generator()

if __name__ == "__main__":
    main()
