# -------------------------------------------------------------------------
# Math Twin Generator - Public Full Version (Ad-Supported)
# -------------------------------------------------------------------------

import streamlit as st
# [Fix] Removed unused import that causes ModuleNotFoundError
# import google.generativeai as genai 
from PIL import Image
import fitz  # PyMuPDF
from fpdf import FPDF
import io
import os
import json
import re
import base64
import textwrap
import time
from datetime import datetime
import requests
import urllib3
import matplotlib
import tempfile
import zipfile
import csv

# [Fix] Matplotlib GUI backend conflict prevention
matplotlib.use('Agg') 
import matplotlib.pyplot as plt 
import matplotlib.font_manager as fm
import numpy as np 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# SSL Warning Suppression
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================================
# 1. Initialization & Configuration
# =========================================================================

st.set_page_config(
    page_title="Math Twin Generator",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 기본 설정 및 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILENAME = "NanumGothic.ttf"
FONT_PATH = os.path.join(BASE_DIR, FONT_FILENAME)
REF_DIR_NAME = "references"
REF_DIR_PATH = os.path.join(BASE_DIR, REF_DIR_NAME)

# 폰트 다운로드 및 설정
@st.cache_resource
def setup_fonts():
    font_ready = False
    if not os.path.exists(FONT_PATH):
        try:
            url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                with open(FONT_PATH, "wb") as f: f.write(res.content)
        except: pass

    if os.path.exists(FONT_PATH):
        try:
            fm.fontManager.addfont(FONT_PATH)
            font_prop = fm.FontProperties(fname=FONT_PATH)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['mathtext.fontset'] = 'cm' 
            plt.rcParams['axes.unicode_minus'] = False
            font_ready = True
        except: pass
    
    if not font_ready:
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.unicode_minus'] = False
    
    return font_ready

setup_fonts()

# Session State Init (로그인 관련 변수 제거)
default_session = {
    'curriculum_text': "", 'base_ref_text': "", 'generated_data': None,
    'img_rotation': 0, 'processed_file_id': None, 'valid_model_name': None,
    'generated_figure': None, 'raw_response': "", 'history': [],
    'selected_indices': [], 'api_key': "", 'last_used_model': "",
    'preferred_model_mode': "Auto", 'style_img': None,
    'user_answer': "", 'show_grading': False,
    'theme_primary': "#e4c1b2", 'theme_bg': "#242329", 'theme_text': "#ded5d2",
    'bg_image_file': None,
    'grade': "Middle 1", 'difficulty': "Maintain", 'prob_type': "Any", 'creativity': 0.4,
    'subject': None
}
for k, v in default_session.items():
    if k not in st.session_state: st.session_state[k] = v

# =========================================================================
# 2. Ad & Marketing Components (광고 영역)
# =========================================================================

def display_sidebar_ads():
    """사이드바 광고 배너 영역"""
    st.sidebar.markdown("---")
    st.sidebar.header("📚 추천 학습 자료")
    
    # [광고 1] 쿠팡/YES24 파트너스 링크 예시
    ad_html = """
    <div style="text-align: center; margin-bottom: 15px; background-color: #2F2E35; padding: 10px; border-radius: 10px; border: 1px solid #403e41;">
        <p style="color: #e4c1b2; font-size: 0.9em; margin-bottom: 5px;">🔥 선생님 필수템</p>
        <a href="https://www.coupang.com/" target="_blank" style="text-decoration: none;">
            <div style="background-color: #eee; color: #333; padding: 15px; border-radius: 5px; font-weight: bold; font-size: 0.9em;">
                쿠팡 수학 교구 모음전<br>
                <span style="font-size: 0.8em; color: #666;">(클릭하여 보기)</span>
            </div>
        </a>
    </div>
    """
    st.sidebar.markdown(ad_html, unsafe_allow_html=True)
    st.sidebar.info("💡 **Tip:** 문제를 만드느라 힘드셨죠? [여기서 커피 한 잔 하세요!](https://www.starbucks.co.kr)")

# =========================================================================
# 3. Utilities & Logic (원본 기능 100% 복구)
# =========================================================================

def load_reference_materials():
    if not os.path.exists(REF_DIR_PATH):
        try: os.makedirs(REF_DIR_PATH)
        except: pass
        return "", 0
    combined_text = ""
    file_count = 0
    try:
        files = os.listdir(REF_DIR_PATH)
        for filename in files:
            file_path = os.path.join(REF_DIR_PATH, filename)
            if filename.lower().endswith('.pdf'):
                try:
                    with fitz.open(file_path) as doc:
                        max_p = min(doc.page_count, 50)
                        for i in range(max_p): combined_text += doc.load_page(i).get_text() + "\n"
                    file_count += 1
                except: pass
            elif filename.lower().endswith('.txt'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f: combined_text += f.read() + "\n"
                    file_count += 1
                except: pass
    except: pass
    return combined_text, file_count

def check_files():
    if not os.path.exists(FONT_PATH):
        pass
    if not st.session_state['base_ref_text']:
        text, count = load_reference_materials()
        if count > 0:
            st.session_state['base_ref_text'] = text
            st.toast(f"📚 Loaded {count} reference files!", icon="🟣")
    return True

def extract_text_safe(uploaded_file):
    text_content = ""
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                max_pages = min(doc.page_count, 30)
                for page_num in range(max_pages):
                    page = doc.load_page(page_num)
                    text_content += page.get_text()
                if doc.page_count > 30: text_content += "\n...(omitted)..."
        elif uploaded_file.type == "text/plain":
            text_content = file_bytes.decode("utf-8", errors='ignore')
        return text_content, None
    except Exception as e:
        return "", str(e)

def pdf_to_image(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            if doc.page_count < 1: return None
            page = doc.load_page(0)
            zoom = 2; mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            return img
    except: return None

def normalize_latex_text(text):
    if text is None: return ""
    text = str(text)
    
    # cases 환경 단순화
    text = re.sub(r'\\begin\{cases\}', r'\{', text)
    text = re.sub(r'\\end\{cases\}', r'\}', text)
    
    math_placeholders = []
    def protect(match):
        math_placeholders.append(match.group(0))
        return f"__MATH_PROTECTED_{len(math_placeholders)-1}__"
    
    text = re.sub(r'\$\$.*?\$\$', protect, text, flags=re.DOTALL)
    text = re.sub(r'\$.*?\$', protect, text, flags=re.DOTALL)

    # Remove complex commands to prevent breakage
    commands = [
        r'\\ge', r'\\le', r'\\neq', r'\\ne', r'\\approx', r'\\pm', 
        r'\\times', r'\\div', r'\\cdot', r'\\infty', 
        r'\\alpha', r'\\beta', r'\\gamma', r'\\theta', r'\\pi', r'\\to',
    ]
    cmd_pattern = '|'.join(commands)
    def wrap_cmd(match): return f"${match.group(0)}$"
    text = re.sub(f"({cmd_pattern})", wrap_cmd, text)

    text = re.sub(r'therefore(?=[a-zA-Z])', r'\\therefore ', text)
    replacements = {
        r';lim\b': r'\\lim', r';to\b': r'\\to', r';frac\b': r'\\frac',
        r'\btherefore\b': r'\\therefore', r'\bbecause\b': r'\\because',
        r'\bquad\b': r'\\quad', r'\bqquad\b': r'\\qquad',
        r'\bcdots\b': r'\\cdots', r'\bvdots\b': r'\\vdots',
        r'\bddots\b': r'\\ddots', r'\btext\b': r'\\text',
        r'\bgeq\b': r'$\\ge$', r'\bleq\b': r'$\\le$',
        r'\bge\b': r'$\\ge$', r'\ble\b': r'$\\le$'
    }
    for p, r in replacements.items(): text = re.sub(p, r, text)
    text = re.sub(r'\\text\((.*?)\)', r'\\text{\1}', text)

    def restore(match): return math_placeholders[int(match.group(1))]
    for _ in range(3):
        if "__MATH_PROTECTED_" not in text: break
        text = re.sub(r'__MATH_PROTECTED_(\d+)__', restore, text)
    
    text = text.replace('$$', '$')
    text = re.sub(r'\$\s*\$', '', text) 
    return text

def clean_python_code(code):
    if not code: return ""
    code = re.sub(r'\\\s*\n', ' ', code)
    code = code.replace('plt.show()', '# plt.show() removed')
    return code

def validate_python_code(code):
    dangerous = ['import os', 'import sys', 'import subprocess', 'open(', 'exec(', 'eval(', '__import__', 'globals', 'locals', 'urllib', 'requests', 'socket']
    for kw in dangerous:
        if kw in code: return False, f"Security Risk: {kw}"
    return True, "Safe"

def split_long_latex(text, limit=75):
    if not text: return ""
    if not isinstance(text, str): text = str(text)
    
    def replacer(match):
        content = match.group(0) # $...$
        inner = content[1:-1].strip()
        if r'\begin{' in inner: return content
        if len(inner) < limit: return content
            
        if " = " in inner:
            parts = inner.split(" = ")
            new_inner = f"{parts[0]}"
            for part in parts[1:]: new_inner += f" $\n\n$ = {part}"
            return f"${new_inner}$"
        elif "=" in inner:
            parts = inner.split("=")
            new_inner = f"{parts[0]}"
            for part in parts[1:]: new_inner += f" $\n\n$ = {part}"
            return f"${new_inner}$"
        
        for op in [" + ", " - "]:
            if op in inner:
                parts = inner.split(op)
                new_inner = f"{parts[0]}"
                for part in parts[1:]: new_inner += f" $\n\n$ {op.strip()} {part}"
                return f"${new_inner}$"
        return content
    return re.sub(r'\$.*?\$', replacer, text, flags=re.DOTALL)

def get_base64_of_bin_file(bin_file):
    data = bin_file.read()
    return base64.b64encode(data).decode()

def parse_gemini_json_response(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        cleaned_text = match.group(0) if match else re.sub(r"```(json)?", "", text).replace("```", "").strip()
        data = json.loads(cleaned_text)
        required_keys = ["problem", "hint", "answer", "solution", "concept", "achievement_standard", "drawing_code"]
        for key in required_keys:
            if key not in data: 
                data[key] = ""
            else:
                val = data[key]
                if isinstance(val, (list, tuple)):
                    val = "\n\n".join(map(str, val))
                elif isinstance(val, dict):
                    val = str(val)
                elif val is None:
                    val = ""
                else:
                    val = str(val)
                data[key] = val

                if key == "drawing_code":
                    data[key] = clean_python_code(data[key])
                else:
                    data[key] = data[key].replace('\\[', '$$').replace('\\]', '$$')
                    data[key] = data[key].replace('\\(', '$').replace('\\)', '$')
                    data[key] = normalize_latex_text(data[key])
                    if key in ['solution', 'problem']:
                        data[key] = split_long_latex(data[key], limit=75)
        return data
    except json.JSONDecodeError:
        try: cleaned_text = cleaned_text.replace('\\', '\\\\')
        except: pass
        extracted_data = {k: "" for k in ["problem", "hint", "answer", "solution", "concept", "achievement_standard", "drawing_code"]}
        patterns = {
            "concept": r'"concept"\s*:\s*"(.*?)"', "achievement_standard": r'"achievement_standard"\s*:\s*"(.*?)"',
            "problem": r'"problem"\s*:\s*"(.*?)"', "hint": r'"hint"\s*:\s*"(.*?)"', 
            "answer": r'"answer"\s*:\s*"(.*?)"', "solution": r'"solution"\s*:\s*"(.*?)"', "drawing_code": r'"drawing_code"\s*:\s*"(.*?)"'
        }
        for k, p in patterns.items():
            found = re.search(p, text, re.DOTALL)
            if found:
                content = found.group(1).replace('\\"', '"').replace('\\n', '\n')
                if k == "drawing_code":
                    extracted_data[k] = clean_python_code(content)
                else:
                    content = content.replace('\\[', '$$').replace('\\]', '$$').replace('\\(', '$').replace('\\)', '$')
                    extracted_data[k] = normalize_latex_text(content)
        if len(extracted_data["problem"]) > 10: return extracted_data
        return {"problem": text, "concept": "Parsing Error", "achievement_standard": "", "hint": "", "answer": "", "solution": "", "drawing_code": ""}

# =========================================================================
# 4. PDF Generator (원본 풀버전)
# =========================================================================

class PDFGenerator:
    @staticmethod
    def render_text_to_image(text, width_inch=8.0):
        try:
            if not text or not text.strip(): return None
            plt.clf(); plt.close('all')
            prop = fm.FontProperties(fname=FONT_PATH, size=14) if os.path.exists(FONT_PATH) else None
            
            text = normalize_latex_text(text)
            text = text.replace('$$', '$')
            text = re.sub(r'([가-힣])(\$)(?=[^.,:;?!])', r'\1 \2', text)
            text = re.sub(r'(\$)([가-힣])', r'\1 \2', text)
            
            math_matches = []
            def protect(m): math_matches.append(m.group(0)); return f"__M_{len(math_matches)-1}__"
            protected_text = re.sub(r'\$.*?\$', protect, text, flags=re.DOTALL)
            
            wrapped_lines = []
            for line in protected_text.split('\n'):
                if not line.strip(): 
                    wrapped_lines.append("")
                    continue
                lines = textwrap.wrap(line, width=50, break_long_words=False, break_on_hyphens=False)
                wrapped_lines.extend(lines)
            
            final_lines = []
            for line in wrapped_lines:
                restored = re.sub(r'__M_(\d+)__', lambda m: math_matches[int(m.group(1))], line)
                final_lines.append(restored)
            
            wrapped_text = '\n'.join(final_lines)
            height = max(1.0, len(final_lines) * 0.7) + 0.5
            
            fig = plt.figure(figsize=(width_inch, height))
            fig.patch.set_facecolor('white')
            try:
                plt.text(0.01, 0.98, wrapped_text, fontproperties=prop, va='top', ha='left')
                plt.axis('off')
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight', dpi=600, pad_inches=0.1)
                buf.seek(0)
                plt.close()
                return buf
            except:
                plt.clf(); plt.close()
                return None
        except: return None

    class ExamPDF(FPDF):
        def header(self):
            if os.path.exists(FONT_PATH):
                self.add_font('NanumGothic', '', FONT_PATH)
                self.set_font('NanumGothic', '', 10)
            else: self.set_font('helvetica', '', 10)
            self.cell(0, 10, 'Math Twin Generator - Public Edition', align='L')
            self.ln(5); self.line(10, 20, 200, 20); self.ln(10)

        def footer(self):
            self.set_y(-15)
            if os.path.exists(FONT_PATH): self.set_font('NanumGothic', '', 8)
            else: self.set_font('helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    @staticmethod
    def _add_image_to_pdf(pdf_obj, image_data, x=None, w=0):
        if not image_data: return
        data_bytes = None
        if isinstance(image_data, io.BytesIO): data_bytes = image_data.getvalue()
        elif isinstance(image_data, Image.Image):
            buf = io.BytesIO(); image_data.save(buf, format="PNG"); data_bytes = buf.getvalue()
        if not data_bytes: return
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(data_bytes); tmp_path = tmp.name
            if x is not None: pdf_obj.image(tmp_path, x=x, w=w)
            else: pdf_obj.image(tmp_path, w=w)
        except: pass
        finally:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except: pass

    @staticmethod
    def _generate_figure_from_code(code):
        if not code or "plt" not in code: return None
        try:
            code = clean_python_code(code)
            plt.clf(); plt.close('all'); fig = plt.figure()
            local_vars = {'plt': plt, 'np': np}
            exec(code, local_vars)
            buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); buf.seek(0)
            plt.close('all')
            return buf
        except: return None

    @staticmethod
    def create_single_pdf(data, title, figure_image, export_mode="Integrated"):
        pdf = PDFGenerator.ExamPDF()
        pdf.add_page()
        if os.path.exists(FONT_PATH): pdf.add_font('NanumGothic', '', FONT_PATH); pdf.set_font('NanumGothic', '', 12)
        
        # 1. Problem Section
        if export_mode in ["Integrated", "Problem Only"]:
            meta = ""
            if data.get('achievement_standard'): meta += f"[{data.get('achievement_standard')}] "
            if data.get('concept'): meta += f"[{data.get('concept')}]"
            
            if meta:
                pdf.set_font_size(10); pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 6, meta); pdf.ln(5); pdf.set_text_color(0, 0, 0)
            
            pdf.set_font_size(14); pdf.cell(0, 10, title, ln=True); pdf.ln(5)
            
            prob_txt = data.get('problem', '').replace('\n', '\n\n')
            prob_img = PDFGenerator.render_text_to_image(prob_txt)
            if prob_img: PDFGenerator._add_image_to_pdf(pdf, prob_img, w=180); pdf.ln(5)
            else: pdf.multi_cell(0, 8, prob_txt.replace('$', ''))

            if figure_image:
                PDFGenerator._add_image_to_pdf(pdf, figure_image, x=55, w=100); pdf.ln(5)
        
        # 2. Solution Section
        if export_mode in ["Integrated", "Solution Only"]:
            if export_mode == "Integrated": pdf.add_page()
            
            pdf.set_font_size(14); pdf.cell(0, 10, "Answer & Solution", ln=True, align='C'); pdf.ln(10)
            
            ans_img = PDFGenerator.render_text_to_image(f"[Answer]\n{data.get('answer', '')}")
            if ans_img: PDFGenerator._add_image_to_pdf(pdf, ans_img, w=180); pdf.ln(5)
            
            if data.get('hint'):
                hint_img = PDFGenerator.render_text_to_image(f"[Hint]\n{data.get('hint', '')}")
                if hint_img: PDFGenerator._add_image_to_pdf(pdf, hint_img, w=180); pdf.ln(5)

            sol_txt = f"[Solution]\n{data.get('solution', '')}".replace('\n', '\n\n')
            chunk_img = PDFGenerator.render_text_to_image(sol_txt)
            if chunk_img:
                 PDFGenerator._add_image_to_pdf(pdf, chunk_img, w=180)
            else:
                 pdf.multi_cell(0, 8, sol_txt.replace('$', ''))
                
        out = pdf.output(dest='S')
        if isinstance(out, str):
            return out.encode('latin-1')
        return bytes(out)
    
    @staticmethod
    def create_workbook_pdf(history_items, title="My Math Workbook", export_mode="Integrated"):
        pdf = PDFGenerator.ExamPDF()
        if os.path.exists(FONT_PATH): pdf.add_font('NanumGothic', '', FONT_PATH); pdf.set_font('NanumGothic', '', 12)
        import tempfile

        # 1. Cover
        pdf.add_page()
        pdf.set_font_size(24); pdf.cell(0, 60, "", ln=True)
        pdf.cell(0, 20, title, ln=True, align='C')
        pdf.set_font_size(16)
        pdf.cell(0, 15, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
        pdf.cell(0, 15, f"Total: {len(history_items)} Questions", ln=True, align='C')
        pdf.cell(0, 10, f"Mode: {export_mode}", ln=True, align='C')
        
        # 2. Problems
        if export_mode in ["Integrated", "Problem Only"]:
            pdf.add_page()
            pdf.set_font_size(18); pdf.cell(0, 15, "PART 1. Problems", ln=True, align='C'); pdf.ln(10)
            for idx, item in enumerate(history_items):
                data = item['data']
                pdf.set_font_size(10); pdf.set_text_color(100)
                grade_info = item.get('grade', '')
                diff_info = item.get('difficulty', '')
                meta = f"Q{idx+1}. {grade_info} ({diff_info}) "
                if data.get('achievement_standard'): meta += f"[{data.get('achievement_standard')}]"
                elif data.get('concept'): meta += f"[{data.get('concept')}]"
                pdf.multi_cell(0, 6, meta); pdf.set_text_color(0)
                
                prob_txt = data.get('problem', '').replace('\n', '\n\n')
                prob_img = PDFGenerator.render_text_to_image(prob_txt)
                if prob_img: PDFGenerator._add_image_to_pdf(pdf, prob_img, w=175); pdf.ln(5)
                else: pdf.set_font_size(12); pdf.multi_cell(0, 8, prob_txt.replace('$', ''))
                
                d_code = data.get('drawing_code', '')
                if d_code:
                    fig_data = PDFGenerator._generate_figure_from_code(d_code)
                    if fig_data:
                        PDFGenerator._add_image_to_pdf(pdf, fig_data, x=55, w=100)
                        pdf.ln(5)
                pdf.ln(15) 

        # 3. Solutions
        if export_mode in ["Integrated", "Solution Only"]:
            pdf.add_page()
            pdf.set_font_size(18); pdf.cell(0, 15, "PART 2. Solutions", ln=True, align='C'); pdf.ln(10)
            for idx, item in enumerate(history_items):
                data = item['data']
                pdf.set_font_size(12); pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 10, f"Q{idx+1} Solution", ln=True)
                
                sol_txt = f"[Answer] {data.get('answer', '')}\n\n[Solution]\n{data.get('solution', '')}".replace('\n', '\n\n')
                chunk_img = PDFGenerator.render_text_to_image(sol_txt)
                if chunk_img: PDFGenerator._add_image_to_pdf(pdf, chunk_img, w=175); pdf.ln(10)
                else: pdf.multi_cell(0, 8, chunk_img.replace('$', '')); pdf.ln(10)

        # 4. Quick Answers
        if export_mode == "Integrated":
            pdf.add_page()
            pdf.set_font_size(18); pdf.cell(0, 15, "PART 3. Quick Answers", ln=True, align='C'); pdf.ln(10)
            pdf.set_font_size(11)
            col_width = 190 / 2
            for i in range(0, len(history_items), 2):
                item1 = history_items[i]
                ans1 = item1['data'].get('answer', '').replace('$', '').strip()
                ans1_short = (ans1[:30] + '..') if len(ans1) > 30 else ans1
                text1 = f"Q{i+1}: {ans1_short}"
                text2 = ""
                if i + 1 < len(history_items):
                    item2 = history_items[i+1]
                    ans2 = item2['data'].get('answer', '').replace('$', '').strip()
                    ans2_short = (ans2[:30] + '..') if len(ans2) > 30 else ans2
                    text2 = f"Q{i+2}: {ans2_short}"
                y_start = pdf.get_y()
                pdf.cell(col_width, 10, text1, border=1)
                pdf.cell(col_width, 10, text2, border=1, ln=True)
        
        return pdf.output(dest='S').encode('latin-1')

    @staticmethod
    def create_history_zip(history_items):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for idx, item in enumerate(history_items):
                data = item.get('data')
                if not data: continue
                title = f"Problem_{idx+1}_{item.get('grade', '').replace(' ', '_')}"
                
                fig_img = None
                if data.get('drawing_code'):
                    fig_img = PDFGenerator._generate_figure_from_code(data['drawing_code'])
                
                try:
                    pdf_bytes = PDFGenerator.create_single_pdf(data, title, fig_img, "Integrated")
                    zip_file.writestr(f"{title}.pdf", pdf_bytes)
                except Exception as e:
                    print(f"Error zipping item {idx}: {e}")
                    
        return zip_buffer.getvalue()

    @staticmethod
    def convert_history_to_csv(history):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Grade', 'Difficulty', 'Concept', 'Problem', 'Answer', 'Solution'])
        for item in history:
            data = item.get('data', {})
            writer.writerow([
                item.get('time', ''), item.get('grade', ''), item.get('difficulty', ''),
                data.get('concept', ''), data.get('problem', ''), data.get('answer', ''), data.get('solution', '')
            ])
        return output.getvalue().encode('utf-8-sig')

# =========================================================================
# 5. API Client & Logic (원본 기능 100% 복구)
# =========================================================================

class GeminiClient:
    @staticmethod
    def get_working_model(api_key):
        key = str(api_key).strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        priorities = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-001', 'gemini-2.0-flash-exp', 'gemini-1.5-pro']
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=Retry(connect=3, backoff_factor=0.5))
        session.mount('https://', adapter)
        try:
            res = session.get(url, timeout=5, verify=False)
            if res.status_code == 200:
                avail = [m['name'].replace('models/', '') for m in res.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
                avail = [m for m in avail if 'gemma' not in m.lower()] 
                return [m for m in priorities if m in avail] + [m for m in avail if m not in priorities]
        except: pass
        return priorities 

    @staticmethod
    def test_api_connection(api_key):
        candidates = GeminiClient.get_working_model(api_key)
        for m in candidates:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
                res = requests.post(url, headers={'Content-Type': 'application/json'}, json={"contents": [{"parts": [{"text": "Hi"}]}]}, timeout=5, verify=False)
                if res.status_code == 200:
                    st.session_state['valid_model_name'] = m
                    return True, f"Connection Successful! ({m})"
            except: pass
        return False, "No usable model found."

    @staticmethod
    def call_api(api_key, payload, active_model_name=None, retry=0):
        pref_mode = st.session_state.get('preferred_model_mode', 'Auto')
        if pref_mode != 'Auto': m = pref_mode
        else:
            m = active_model_name
            if not m:
                cached_m = st.session_state.get('valid_model_name')
                m = cached_m if cached_m else 'gemini-1.5-flash'
                st.session_state['valid_model_name'] = m
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
        try:
            res = session.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=300, verify=False)
            if res.status_code == 200:
                try: return res.json()['candidates'][0]['content']['parts'][0]['text'], m
                except: return "⚠️ Format Error", m
            elif res.status_code == 429:
                if retry < 3:
                    time.sleep(10); return GeminiClient.call_api(api_key, payload, m, retry+1)
                return "⚠️ Quota Exceeded", m
            elif res.status_code == 404:
                st.session_state['valid_model_name'] = None 
                if retry < 2: return GeminiClient.call_api(api_key, payload, None, retry+1)
                return "⚠️ Model Not Found", m
            return f"Error {res.status_code}: {res.text}", m
        except Exception as e:
            if retry < 2:
                time.sleep(5); return GeminiClient.call_api(api_key, payload, active_model_name, retry+1)
            return f"Network Error: {str(e)}", m

def generate_draft(api_key, image, difficulty, grade, curr_text, instruction, style_img, temperature, p_type, subject=None):
    opt_img = image.copy(); opt_img.thumbnail((800, 800))
    if opt_img.mode != 'RGB': opt_img = opt_img.convert('RGB')
    buf = io.BytesIO(); opt_img.save(buf, format="JPEG"); img_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    
    diff_map = {"Maintain": "유지", "Easier": "쉽게", "Harder": "어렵게"}
    diff_kr = diff_map.get(difficulty, "유지")
    
    grade_map = {
        "Elementary 3": "초등학교 3학년", "Elementary 4": "초등학교 4학년", "Elementary 5": "초등학교 5학년", "Elementary 6": "초등학교 6학년",
        "Middle 1": "중학교 1학년", "Middle 2": "중학교 2학년", "Middle 3": "중학교 3학년",
        "High 1": "고등학교 1학년", "High 2": "고등학교 2학년", "High 3": "고등학교 3학년",
        "University Math": "대학수학"
    }
    grade_kr = grade_map.get(grade, "중학교 1학년")
    
    subject_map = {
        "Number Theory": "정수론", "Linear Algebra": "선형대수학", "Statistics": "통계학",
        "Differential Geometry": "미분기하학", "Analysis": "해석학", "Abstract Algebra": "현대대수학",
        "Complex Analysis": "복소해석학", "Topology": "위상수학", "Discrete Mathematics": "이산수학"
    }
    
    subject_prompt = ""
    abstract_subjects = ["Abstract Algebra", "Topology", "Number Theory", "Discrete Mathematics"]
    drawing_constraint = "6. **그림 생성:** 기하학/함수 그래프 등 시각자료가 문제 풀이에 필수적인 경우에만 Python matplotlib 코드를 생성하십시오."
    
    if grade == "University Math" and subject:
        subject_kr = subject_map.get(subject, subject)
        grade_kr = f"대학수학({subject_kr})"
        subject_prompt = f"전공 분야: {subject_kr}. 해당 전공의 전문 용어와 개념을 사용하여 문제를 출제하십시오."
        
        if subject in abstract_subjects:
            drawing_constraint = "6. **그림 생성 금지:** 이 분야(추상수학)는 시각화가 불필요하거나 오류 가능성이 높으므로, drawing_code는 반드시 비워두십시오."
        elif subject in ["Calculus", "Differential Geometry"]:
             drawing_constraint = "6. **그림 생성 필수 권장:** 이 분야(미적분/기하)는 시각적 이해가 중요하므로, matplotlib 코드를 적극적으로 생성하여 그래프나 도형을 제공하십시오."

    if temperature < 0.3: mode_desc = "Change numbers/symbols only (Maintain Structure)"
    elif temperature < 0.7: mode_desc = "Change context but maintain core concept"
    else: mode_desc = "Creative application of same concept"

    type_inst = ""
    if p_type == "Multiple Choice": type_inst = "Make this a multiple choice question with 5 options (①~⑤)."
    elif p_type == "Essay": type_inst = "Make this a narrative/essay type question requiring logical explanation."

    parts = [{"text": f"""
    당신은 대한민국 수학 교육 전문가입니다. 입력된 이미지의 문제를 분석하여, 동일한 수학적 개념을 묻는 '{grade_kr}' 수준(난이도:{diff_kr})의 새로운 '쌍둥이 문제'를 만드십시오.
    
    [필수 지침]
    1. **언어:** 문제, 풀이, 해설 등 모든 텍스트는 **반드시 한국어(Korean)**로 작성하십시오.
    2. **용어 제한(중요):** 대한민국 초/중/고등학교 교육과정 내의 표준 용어만 사용하십시오.
        - 금지: '상한(Upper limit)', '하한(Lower limit)' 용어 사용 금지.
        - 대체: 정적분의 구간은 '위끝', '아래끝'으로 표현하십시오. 해석학적 의미의 상한(Supremum) 개념은 고교 과정에서 다루지 않으므로 사용하지 마십시오.
        - 대학수학일 경우에만 해당 전공 용어를 사용하십시오.
    3. **변형 모드:** {mode_desc}
    4. **문제 유형:** {p_type}. {type_inst}
    5. **제약 사항:** {grade_kr} 교육과정 범위를 준수하십시오. {curr_text[:10000]}
    6. **추가 요청:** {instruction}
    {subject_prompt}
    {drawing_constraint}
    7. **절대 금지:** 생성된 그림에 정답, 해설, 힌트 텍스트를 넣지 마십시오. 오직 문제의 초기 상태만 시각화하십시오.
    8. **코드 규칙:** Python 코드 작성 시 줄바꿈 문자(\\)를 절대 사용하지 마십시오.
    """}, {"inline_data": {"mime_type": "image/jpeg", "data": img_str}}]
    
    if style_img:
        s_buf = io.BytesIO(); style_img.save(s_buf, format="JPEG"); s_str = base64.b64encode(s_buf.getvalue()).decode("utf-8")
        parts.append({"text": "Style Reference:"}); parts.append({"inline_data": {"mime_type": "image/jpeg", "data": s_str}})

    payload = {"contents": [{"parts": parts}], "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}], "generationConfig": {"temperature": temperature}}
    return GeminiClient.call_api(api_key, payload)

def refine_final(api_key, draft, style_img, grade, subject=None):
    grade_map = {
        "Elementary 3": "초등학교 3학년", "Elementary 4": "초등학교 4학년", "Elementary 5": "초등학교 5학년", "Elementary 6": "초등학교 6학년",
        "Middle 1": "중학교 1학년", "Middle 2": "중학교 2학년", "Middle 3": "중학교 3학년",
        "High 1": "고등학교 1학년", "High 2": "고등학교 2학년", "High 3": "고등학교 3학년",
        "University Math": "대학수학"
    }
    grade_kr = grade_map.get(grade, "중학교 1학년")
    
    subject_map = {
        "Number Theory": "정수론", "Linear Algebra": "선형대수학", "Statistics": "통계학",
        "Differential Geometry": "미분기하학", "Analysis": "해석학", "Abstract Algebra": "현대대수학",
        "Complex Analysis": "복소해석학", "Topology": "위상수학", "Discrete Mathematics": "이산수학"
    }
    if grade == "University Math" and subject:
        subject_kr = subject_map.get(subject, subject)
        grade_kr = f"대학수학({subject_kr})"
        validation_prompt = f"""
        [대학수학 정밀 검증]
        - 전공 분야: {subject_kr}
        - 생성된 문제가 해당 전공의 공리 및 정리와 모순되지 않는지 엄밀히 증명하십시오.
        - 수식 전개 과정에서 논리적 비약이 없는지 확인하십시오.
        - 답이 유일하게 결정되는지, 혹은 해가 없는 경우(불능)나 무수히 많은 경우(부정)는 아닌지 확인하십시오.
        """
    else:
        validation_prompt = """
        [오류 점검 및 수정 (Self-Correction)]
        - 생성된 문제를 직접 처음부터 끝까지 풀어보고, 정답이 정확한지 검증하십시오.
        - 문제 조건이 불충분하거나 모순이 있는지 확인하십시오.
        - 계산 과정에 오류가 있다면 수정하십시오.
        """

    prompt = f"""
    당신은 대한민국 수학 문제 검토 위원장입니다. 아래 초안(Draft)을 면밀히 검토하고, 오류가 있다면 수정한 뒤 최종본을 JSON 포맷으로 작성하십시오.
    
    [검토 및 수정 지침]
    1. **언어:** 모든 내용은 **한국어(Korean)**로 작성되어야 합니다.
    2. **풀이 검증:** 논리적 비약이나 계산 오류가 없어야 합니다. 풀이는 '1단계', '2단계' 또는 'Step 1', 'Step 2'와 같이 단계별로 명확히 서술하십시오.
    3. **줄바꿈:** 풀이 과정에서 수식과 수식 사이, 문장과 문장 사이에는 줄바꿈(`\\n\\n`)을 충분히 사용하여 가독성을 높이십시오.
    4. **용어 점검:** {grade_kr} 수준에 맞는 용어를 사용하십시오. 특히 '상한', '하한' 등의 용어가 있다면 '위끝', '아래끝' 또는 적절한 교육과정 내 용어로 수정하십시오.
    5. **수식 포맷:** 수식은 반드시 LaTeX 포맷인 $ ... $ 를 사용하십시오. (\\begin{{cases}} 사용 금지)
    6. **그림 코드:** matplotlib 사용 시 plt.show()를 포함하지 마십시오. 코드 줄바꿈에 백슬래시(\\)를 사용하지 마십시오.
    7. **그림 검증:** 그림에 정답이나 풀이 과정이 포함되어 있다면 제거하고, 문제의 초기 상태만 그리도록 코드를 수정하십시오.
    8. **성취기준:** 해당 문제가 속한 대한민국 교육과정 성취기준 코드(예: [10수학01-01])를 분석하여 작성하십시오. (대학수학은 관련 전공 주제 명시)
    
    {validation_prompt}
    
    [입력된 초안]
    {draft}
    
    [최종 출력 JSON 포맷]
    {{ "concept": "핵심 개념", "problem": "수정된 문제 내용", "hint": "힌트", "answer": "검증된 정답", "solution": "검증된 상세 풀이 (줄바꿈 필수)", "drawing_code": "Python 코드", "achievement_standard": "성취기준" }}
    """
    parts = [{"text": prompt}]
    if style_img:
        s_buf = io.BytesIO(); style_img.save(s_buf, format="JPEG"); s_str = base64.b64encode(s_buf.getvalue()).decode("utf-8")
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": s_str}})

    payload = {"contents": [{"parts": parts}], "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}], "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}}
    return GeminiClient.call_api(api_key, payload)

# =========================================================================
# 6. UI Dialogs (필요한 기능만 유지)
# =========================================================================

@st.dialog("📝 Options")
def dialog_options():
    st.caption("Customize problem generation")
    g = st.selectbox("Grade", ["Middle 1", "Middle 2", "Middle 3", "High 1", "High 2", "High 3", "University Math"], index=0, key="opt_grade")
    if g != st.session_state['grade']: st.session_state['grade'] = g
    if st.session_state['grade'] == "University Math":
        s = st.selectbox("Subject", ["Calculus", "Linear Algebra", "Statistics", "Topology", "Number Theory"], key="opt_subj")
        st.session_state['subject'] = s
    st.session_state['difficulty'] = st.radio("Diff", ["Maintain", "Easier", "Harder"], key="opt_diff")
    st.session_state['prob_type'] = st.radio("Type", ["Any", "Multiple Choice", "Essay"], key="opt_type")
    st.divider()
    if st.button("Save & Close", type="primary", use_container_width=True): st.rerun()

@st.dialog("📖 User Guide")
def dialog_guide():
    st.markdown("""
    ### How to Use
    1. **🔑 API**: Enter Google Gemini API Key.
    2. **📝 Options**: Set grade & difficulty.
    3. **📸 Upload**: Drag & drop problem image.
    4. **✨ Generate**: Click button!
    """)

@st.dialog("📚 Materials")
def dialog_materials():
    st.caption("Upload reference materials (PDF/TXT)")
    curr_len = len(st.session_state.get('curriculum_text', ''))
    st.progress(min(curr_len / 30000, 1.0))
    st.caption(f"Loaded: {curr_len} chars")
    uploaded_refs = st.file_uploader("Upload Files", type=['pdf', 'txt'], accept_multiple_files=True, key="mat_upload")
    if uploaded_refs:
        for u_file in uploaded_refs:
            txt, err = extract_text_safe(u_file)
            if not err: st.session_state['curriculum_text'] += "\n" + txt
        st.success("Materials Added!")

@st.dialog("🖼️ Style Reference")
def dialog_style():
    st.caption("Upload an image to mimic its visual style")
    s_file = st.file_uploader("Reference Image", type=['png', 'jpg'], key="style_upload")
    if s_file:
        try: 
            st.session_state['style_img'] = pdf_to_image(s_file) if s_file.type == "application/pdf" else Image.open(s_file)
            st.success("Style Applied!")
            st.image(st.session_state['style_img'], caption="Current Style", use_container_width=True)
        except: st.error("Failed to load image")

@st.dialog("🎨 Theme Settings")
def dialog_theme():
    st.caption("Customize colors")
    c1, c2, c3 = st.columns(3)
    p = c1.color_picker("Primary", st.session_state['theme_primary'], key="cp_p")
    b = c2.color_picker("Background", st.session_state['theme_bg'], key="cp_b")
    t = c3.color_picker("Text", st.session_state['theme_text'], key="cp_t")
    bg_img = st.file_uploader("Background Image", type=['png', 'jpg', 'jpeg'], key="bg_upload")
    if bg_img: st.session_state['bg_image_file'] = bg_img
    if st.button("Apply Theme", key="btn_apply_theme"):
        st.session_state['theme_primary'] = p
        st.session_state['theme_bg'] = b
        st.session_state['theme_text'] = t
        st.rerun()

@st.dialog("🗑️ Data Management")
def dialog_data():
    st.warning("This action cannot be undone.")
    if st.button("Clear All History", type="primary", key="btn_clear_hist"):
        st.session_state['history'] = []
        st.rerun()

# =========================================================================
# 7. Main Application Logic
# =========================================================================

def apply_custom_css():
    """사용자 설정 테마 및 배경 이미지 적용 (원본 그대로)"""
    primary = st.session_state.get('theme_primary', "#e4c1b2")
    bg = st.session_state.get('theme_bg', "#242329")
    text_color = st.session_state.get('theme_text', "#ded5d2")
    sidebar_bg = "#1A1C24"

    bg_style = f"background-color: {bg};"
    if st.session_state.get('bg_image_file'):
        try:
            st.session_state['bg_image_file'].seek(0)
            bin_str = get_base64_of_bin_file(st.session_state['bg_image_file'])
            bg_style = f"""
                background-image: url("data:image/png;base64,{bin_str}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            """
        except:
            bg_style = f"background-color: {bg};"

    st.markdown(f"""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css');

        .stApp {{
            {bg_style}
            color: {text_color};
            font-family: 'Pretendard', sans-serif;
        }}
        .stApp::before {{
            content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(18, 18, 18, 0.4);
            pointer-events: none; z-index: -1;
        }}
        /* Header Banner */
        .logo-container {{
            display: flex; align-items: center; justify-content: center;
            padding: 30px 0; margin-bottom: 30px;
            background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 100%);
            border-bottom: 1px solid rgba(228, 193, 178, 0.1);
        }}
        .logo-icon {{
            font-size: 3.5rem; margin-right: 15px;
            filter: drop-shadow(0 0 15px {primary}44);
            animation: float 4s ease-in-out infinite;
        }}
        .logo-text {{
            font-size: 3rem; font-weight: 800;
            color: {primary};
            letter-spacing: -1px;
            text-shadow: 0 0 30px {primary}33;
        }}
        @keyframes float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-6px); }} }}

        /* Sidebar Styling */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg};
            border-right: 1px solid #403e41;
            padding-top: 10px;
        }}
        
        /* Result Card */
        .result-card {{
            background-color: #2F2E35;
            border: 1px solid #403e41;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            padding: 20px;
            margin-bottom: 20px;
        }}
        .result-header {{
            font-weight: bold;
            color: {primary};
            margin-bottom: 15px;
            font-size: 1.1em;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 10px;
        }}
        </style>
    """, unsafe_allow_html=True)

def main_app_interface():
    st.markdown("""
        <div class="logo-container">
            <span class="logo-icon">📐</span>
            <div class="logo-text">Math Twin Generator</div>
        </div>
    """, unsafe_allow_html=True)

    # API Key Handling (Secrets -> Input)
    api_key = st.session_state.get('api_key')
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    
    with st.sidebar:
        if st.button("📖 Guide", use_container_width=True): dialog_guide()
        
        # API Key Input if not in Secrets
        if not api_key:
            new_key = st.text_input("🔑 API Key", type="password")
            if new_key: st.session_state['api_key'] = new_key; api_key = new_key
            if st.button("Check Connection"):
                 ok, msg = GeminiClient.test_api_connection(api_key)
                 if ok: st.success(msg)
                 else: st.error(msg)
        else:
            st.success("✅ API Key Loaded")

        if st.button("📝 Options", use_container_width=True): dialog_options()
        if st.button("📚 Materials", use_container_width=True): dialog_materials()
        if st.button("🖼️ Style", use_container_width=True): dialog_style()
        if st.button("🎨 Theme", use_container_width=True): dialog_theme()
        if st.button("🗑️ Data", use_container_width=True): dialog_data()
        
        st.divider()
        st.markdown(f"""
        <div class="status-box">
            <div class="status-item"><span class="status-label">Grade</span><span class="status-value">{st.session_state.get('grade')}</span></div>
            <div class="status-item"><span class="status-label">Diff</span><span class="status-value">{st.session_state.get('difficulty')}</span></div>
            <div class="status-item"><span class="status-label">Type</span><span class="status-value">{st.session_state.get('prob_type')}</span></div>
            {f'<div class="status-item"><span class="status-label">Subject</span><span class="status-value">{st.session_state.get("subject")}</span></div>' if st.session_state.get('grade') == 'University Math' else ''}
        </div>
        """, unsafe_allow_html=True)
        
        # [광고 영역]
        display_sidebar_ads()

    c1, c2 = st.columns([1, 1.2])
    with c1:
        with st.container():
            st.markdown('<div class="result-card"><div class="result-header">📸 Original</div><div class="result-body">', unsafe_allow_html=True)
            q_file = st.file_uploader("Upload", type=['png','jpg','jpeg','pdf'], key="uploader")
            if q_file:
                img = pdf_to_image(q_file) if q_file.type == 'application/pdf' else Image.open(q_file)
                st.image(img, use_container_width=True)
                
                if st.button("✨ Generate", type="primary", disabled=not api_key, use_container_width=True):
                    with st.status("Generating..."):
                        d_res, _ = generate_draft(api_key, img, st.session_state['difficulty'], st.session_state['grade'], st.session_state['curriculum_text'], "", st.session_state['style_img'], st.session_state['creativity'], st.session_state['prob_type'], st.session_state['subject'])
                        f_res, _ = refine_final(api_key, d_res, st.session_state['style_img'], st.session_state['grade'], st.session_state['subject'])
                    
                        st.session_state['generated_data'] = parse_gemini_json_response(f_res)
                        
                        # Save to History
                        if st.session_state['generated_data'].get('problem'):
                             history_item = {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": st.session_state['generated_data'], "grade": st.session_state['grade'], "difficulty": st.session_state['difficulty']}
                             st.session_state['history'].insert(0, history_item)
                             
                        st.rerun()
                if not api_key: st.error("API Key Required")
            st.markdown('</div></div>', unsafe_allow_html=True)

    with c2:
        tab_curr, tab_hist = st.tabs(["✨ Result", "📜 History"])
        
        with tab_curr:
            if st.session_state.get('generated_data'):
                data = st.session_state.get('generated_data')
                with st.container():
                    st.markdown('<div class="result-card"><div class="result-header">Result</div>', unsafe_allow_html=True)
                    with st.container(border=True):
                        st.markdown(f"**Q.** {normalize_latex_text(data.get('problem'))}")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                d_code = data.get('drawing_code')
                if d_code and "plt" in d_code:
                    try:
                        code = clean_python_code(d_code)
                        plt.clf(); plt.close('all'); fig = plt.figure()
                        exec(code, {'plt': plt, 'np': np})
                        st.pyplot(fig)
                        st.session_state['generated_figure'] = fig 
                    except: pass
                
                with st.expander("Answer & Solution"):
                    st.markdown(f"**Ans:** {data.get('answer')}")
                    st.divider()
                    sol = str(data.get('solution')).replace('\\n', '\n').replace('\n', '\n\n')
                    st.markdown(f"**Solution:**\n\n{normalize_latex_text(sol)}")
                
                st.divider()
                
                c_tit, c_mode = st.columns([2, 1])
                title = c_tit.text_input("File Name", value=f"{st.session_state['grade']} Math Twin Problem")
                export_mode = c_mode.selectbox("Export Mode", ["Integrated", "Problem Only", "Solution Only"], label_visibility="collapsed")
                
                # Figure handling for PDF
                fig_img = None
                if st.session_state.get('generated_figure'):
                     buf = io.BytesIO()
                     st.session_state['generated_figure'].savefig(buf, format='png', bbox_inches='tight')
                     buf.seek(0)
                     fig_img = Image.open(buf)

                pdf_bytes = PDFGenerator.create_single_pdf(data, title, fig_img, export_mode)
                
                if pdf_bytes:
                     st.download_button("📥 Download PDF", data=bytes(pdf_bytes), file_name=f"{title}.pdf", mime="application/pdf", use_container_width=True)
                
                # [결과 하단 광고]
                st.success("팁: 이 문제가 마음에 드셨나요? 더 많은 자료는 아래 링크를 확인해보세요!")
                st.markdown("""
                <a href="https://www.yes24.com" target="_blank">
                    <div style="background-color: #f0f2f6; padding: 15px; border-radius: 8px; text-align: center; color: #333;">
                        📚 <b>추천 문제집 보러가기 (YES24)</b>
                    </div>
                </a>
                """, unsafe_allow_html=True)
            else:
                st.info("Upload and generate to see results.")

        with tab_hist:
            if st.session_state['history']:
                c_h_txt, c_h_btn1, c_h_btn2 = st.columns([3, 1, 1])
                c_h_txt.write("Recent History")
                if c_h_btn1.button("📦 ZIP Download", use_container_width=True):
                    zip_data = PDFGenerator.create_history_zip(st.session_state['history'])
                    st.download_button("Download ZIP", data=zip_data, file_name="math_problems.zip", mime="application/zip")
                if c_h_btn2.button("📊 CSV Download", use_container_width=True):
                    csv_data = PDFGenerator.convert_history_to_csv(st.session_state['history'])
                    st.download_button("Download CSV", data=csv_data, file_name="history.csv", mime="text/csv")

                if 'selected_indices' not in st.session_state: st.session_state['selected_indices'] = []
                if st.checkbox("Select All", key='chk_all'):
                     st.session_state['selected_indices'] = list(range(len(st.session_state['history'])))
                else:
                     if len(st.session_state['selected_indices']) == len(st.session_state['history']):
                         st.session_state['selected_indices'] = []

                selected_items = []
                for i, item in enumerate(st.session_state['history']):
                    is_sel = i in st.session_state['selected_indices']
                    col_chk, col_content = st.columns([0.05, 0.95])
                    with col_chk:
                        chk = st.checkbox("Select", value=is_sel, key=f"chk_{i}", label_visibility="collapsed")
                    if chk:
                        if i not in st.session_state['selected_indices']: st.session_state['selected_indices'].append(i)
                        selected_items.append(item)
                    else:
                        if i in st.session_state['selected_indices']: st.session_state['selected_indices'].remove(i)

                    with col_content:
                        grade_label = f"**[{item.get('grade', '?')}/{item.get('difficulty', '?')}]**"
                        prob_preview = normalize_latex_text(item['data'].get('problem', ''))
                        st.markdown(f"{grade_label} {prob_preview}")
                        with st.expander("View Details"):
                            st.markdown(normalize_latex_text(item['data'].get('problem')))
                            st.divider()
                            st.write(f"**Answer:** {item['data'].get('answer')}")
                            if st.button("Delete", key=f"del_{i}"):
                                st.session_state['history'].pop(i)
                                st.rerun()
                    st.divider()

                if selected_items:
                    st.divider()
                    c_w_tit, c_w_mode = st.columns([3, 1])
                    wb_title = c_w_tit.text_input("Workbook Title", value="My Math Workbook")
                    wb_mode = c_w_mode.selectbox("Workbook Mode", ["Integrated", "Problem Only", "Solution Only"])
                    if st.button(f"📚 Create Workbook ({len(selected_items)} problems)"):
                        with st.spinner("Creating Workbook..."):
                            wb_bytes = PDFGenerator.create_workbook_pdf(selected_items, wb_title, wb_mode)
                            if wb_bytes:
                                st.download_button("📥 Download Workbook", data=bytes(wb_bytes), file_name="workbook.pdf", mime="application/pdf", use_container_width=True)
            else:
                st.info("No history yet.")

def main():
    apply_custom_css()
    main_app_interface()

if __name__ == "__main__":
    main()
