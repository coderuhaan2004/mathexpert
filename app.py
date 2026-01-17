"""
Pixel Art Math Quiz Application
Interactive educational quiz app with database integration and LLM answer checking
"""

import streamlit as st
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import random
from PIL import Image
import io
import base64
import os
from dotenv import load_dotenv
from google import genai
import statistics
import sqlite3

# Page configuration
st.set_page_config(
    page_title="Math Quiz Master",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for pixel art theme
def load_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
    
    * {
        font-family: 'Press Start 2P', cursive !important;
    }
    
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main {
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    
    h1, h2, h3 {
        color: #4a148c;
        text-shadow: 3px 3px 0px #ffeb3b;
        letter-spacing: 2px;
    }
    
    .stButton > button {
        background: linear-gradient(45deg, #ff6b6b, #ff8e53);
        color: white;
        border: 4px solid #000;
        border-radius: 10px;
        padding: 20px 40px;
        font-size: 18px;
        font-weight: bold;
        box-shadow: 5px 5px 0px #000;
        transition: all 0.1s;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    .stButton > button:hover {
        transform: translate(2px, 2px);
        box-shadow: 3px 3px 0px #000;
    }
    
    .question-card {
        background: linear-gradient(135deg, #ffeaa7, #fdcb6e);
        border: 5px solid #000;
        border-radius: 15px;
        padding: 25px;
        margin: 20px 0;
        box-shadow: 8px 8px 0px #000;
    }
    
    .score-badge {
        background: linear-gradient(45deg, #f093fb, #f5576c);
        color: white;
        border: 4px solid #000;
        border-radius: 50%;
        width: 100px;
        height: 100px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        box-shadow: 5px 5px 0px #000;
    }
    
    .navigation-panel {
        background: #fff;
        border: 4px solid #000;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .metric-card {
        background: white;
        border: 3px solid #000;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 4px 4px 0px #000;
    }
    </style>
    """, unsafe_allow_html=True)


def extract_answer_from_json(answer_json_str: str, answer_type: str) -> Optional[str]:
    """Extract answer from JSON string format"""
    try:
        if not answer_json_str:
            return None
        
        answer_data = json.loads(answer_json_str)
        
        if isinstance(answer_data, dict):
            if 'answer' in answer_data:
                return str(answer_data['answer'])
            elif 'value' in answer_data:
                return str(answer_data['value'])
            elif answer_type in ['integer', 'float']:
                for key in ['number', 'numerical_value', 'result']:
                    if key in answer_data:
                        return str(answer_data[key])
        elif isinstance(answer_data, list) and answer_data:
            return str(answer_data[0])
        
        return str(answer_data)
    except:
        return answer_json_str


def get_questions_from_db(topic: str, num_questions: int) -> List[Dict[str, Any]]:
    """Fetch questions from SQLite databases"""
    questions = []
    
    topic_mapping = {
        "Algebra": ("olympiad.db", ["Algebra"]),
        "Calculus": ("calculus.db", None),
        "Geometry": ("olympiad.db", ["Geometry"]),
        "Number Theory": ("olympiad.db", ["Number Theory"]),
        "Combinatorics": ("olympiad.db", ["Combinatorics"]),
        "Miscellaneous": ("olympiad.db", None)
    }
    
    db_file, subfields = topic_mapping.get(topic, ("olympiad.db", None))
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        if db_file == "olympiad.db":
            if subfields and len(subfields) == 1:
                query = """
                    SELECT id, subfield, problem, final_answer_json, answer_type, unit, solution
                    FROM problems 
                    WHERE subfield = ? AND split = 'train'
                    ORDER BY RANDOM() 
                    LIMIT ?
                """
                cursor.execute(query, (subfields[0], num_questions * 2))
            else:
                query = """
                    SELECT id, subfield, problem, final_answer_json, answer_type, unit, solution
                    FROM problems 
                    WHERE split = 'train'
                    ORDER BY RANDOM() 
                    LIMIT ?
                """
                cursor.execute(query, (num_questions * 2,))
            
            rows = cursor.fetchall()
            
            for row in rows:
                problem_id, subfield, problem, answer_json, answer_type, unit, solution = row
                
                correct_answer = extract_answer_from_json(answer_json, answer_type)
                
                if not correct_answer:
                    continue
                
                difficulty = "medium"
                if solution:
                    sol_len = len(solution)
                    if sol_len < 200:
                        difficulty = "easy"
                    elif sol_len > 500:
                        difficulty = "hard"
                
                question_obj = {
                    "question_id": f"OLY_{problem_id}",
                    "question_type": "numerical",
                    "difficulty": difficulty,
                    "concept_tags": [f"{subfield.upper().replace(' ', '_')}"],
                    "question_text": problem,
                    "options": None,
                    "correct_answer": correct_answer,
                    "answer_type": answer_type,
                    "unit": unit or "",
                    "solution": solution
                }
                
                questions.append(question_obj)
        
        else:  # calculus.db
            query = """
                SELECT id, problem, expected_answer, problem_type, problem_source
                FROM problems 
                WHERE used_in_kaggle = 1
                ORDER BY RANDOM() 
                LIMIT ?
            """
            cursor.execute(query, (num_questions * 2,))
            rows = cursor.fetchall()
            
            for row in rows:
                problem_id, problem, expected_answer, problem_type, problem_source = row
                
                if not expected_answer:
                    continue
                
                difficulty = "medium"
                if problem_source and ("easy" in problem_source.lower()):
                    difficulty = "easy"
                elif problem_source and ("hard" in problem_source.lower() or "amc" in problem_source.lower()):
                    difficulty = "hard"
                
                question_obj = {
                    "question_id": f"CALC_{problem_id}",
                    "question_type": "numerical",
                    "difficulty": difficulty,
                    "concept_tags": ["CALCULUS", problem_type.upper().replace(" ", "_") if problem_type else "GENERAL"],
                    "question_text": problem,
                    "options": None,
                    "correct_answer": expected_answer,
                    "answer_type": "expression",
                    "unit": "",
                    "solution": None
                }
                
                questions.append(question_obj)
        
        conn.close()
        
        random.shuffle(questions)
        return questions[:num_questions]
    
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return []
    except Exception as e:
        st.error(f"Error fetching questions: {e}")
        return []


def check_answer_with_llm(student_answer: str, correct_answer: str, question_text: str, answer_type: str) -> bool:
    """Use LLM to check if student answer matches correct answer"""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return str(student_answer).strip().lower() == str(correct_answer).strip().lower()
    
    prompt = f"""You are a mathematical answer checker. Determine if the student's answer is mathematically equivalent to the correct answer.

Question: {question_text}

Expected Answer: {correct_answer}
Student Answer: {student_answer}
Answer Type: {answer_type}

Consider:
- Mathematical equivalence (e.g., 1/2 = 0.5 = 50%)
- Simplified vs unsimplified forms (e.g., 2/4 = 1/2)
- Different notations (e.g., pi vs π, sqrt(2) vs √2)
- Rounding tolerance for numerical answers (±0.01)
- Algebraic equivalence (e.g., x+1 vs 1+x)

Respond with ONLY one word: "CORRECT" or "INCORRECT"
"""
    
    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        
        result = response.text.strip().upper()
        return "CORRECT" in result
    
    except Exception as e:
        st.warning(f"LLM check failed, using string comparison: {e}")
        return str(student_answer).strip().lower() == str(correct_answer).strip().lower()


def process_student_work(question: Dict, responses: Dict, uploaded_files: Dict) -> Dict[str, Any]:
    """Process student's handwritten work using OCR"""
    q_id = question['question_id']
    response = responses.get(q_id, {})
    
    typed_work = response.get('typed_work', '')
    handwritten_ocr = ""
    combined_work = typed_work
    
    if q_id in uploaded_files:
        try:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            
            if api_key:
                image_data = uploaded_files[q_id]['data']
                image_bytes = base64.b64decode(image_data)
                
                temp_path = f"temp_{q_id}.jpg"
                with open(temp_path, 'wb') as f:
                    f.write(image_bytes)
                
                client = genai.Client(api_key=api_key)
                
                uploaded_image = client.files.upload(path=temp_path)
                
                response_ocr = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=[
                        "Extract all mathematical work, equations, and text from this handwritten solution. Preserve mathematical notation.",
                        uploaded_image
                    ]
                )
                
                handwritten_ocr = response_ocr.text.strip()
                
                os.remove(temp_path)
                
                if typed_work and handwritten_ocr:
                    combined_work = f"**Typed Work:**\n{typed_work}\n\n**Handwritten Work (OCR):**\n{handwritten_ocr}"
                elif handwritten_ocr:
                    combined_work = handwritten_ocr
        
        except Exception as e:
            st.warning(f"OCR processing failed: {e}")
    
    return {
        'handwritten_work_ocr': handwritten_ocr,
        'combined_work': combined_work
    }


def initialize_session_state():
    """Initialize session state variables"""
    defaults = {
        'page': 'home',
        'selected_topic': None,
        'num_questions': 10,
        'questions': [],
        'current_question_idx': 0,
        'responses': {},
        'start_time': None,
        'question_start_times': {},
        'first_attempt_times': {},
        'option_changes': {}
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_home_page():
    """Render the topic selection page"""
    st.markdown("<h1 style='text-align: center; font-size: 48px;'>🎮 MATH QUIZ MASTER 🎮</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #666;'>SELECT YOUR BATTLEFIELD</h3>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    topics = [
        ("📐 Algebra", "Algebra"),
        ("🔢 Combinatorics", "Combinatorics"),
        ("∫ Calculus", "Calculus"),
        ("🎲 Number Theory", "Number Theory"),
        ("📊 Geometry", "Geometry"),
        ("🎯 Miscellaneous", "Miscellaneous")
    ]
    
    col1, col2 = st.columns(2)
    
    for idx, (display_name, topic_name) in enumerate(topics):
        col = col1 if idx % 2 == 0 else col2
        
        with col:
            if st.button(display_name, key=f"topic_{topic_name}", use_container_width=True):
                st.session_state.selected_topic = topic_name
                st.rerun()
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>NUMBER OF QUESTIONS</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        num_questions = st.select_slider(
            "Select number of questions:",
            options=[5, 10, 15, 20, 25, 30],
            value=st.session_state.num_questions,
            label_visibility="collapsed"
        )
        st.session_state.num_questions = num_questions
    
    if st.session_state.selected_topic:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("🚀 START QUIZ 🚀", use_container_width=True):
                with st.spinner("Loading questions from database..."):
                    st.session_state.questions = get_questions_from_db(
                        st.session_state.selected_topic,
                        st.session_state.num_questions
                    )
                
                if not st.session_state.questions:
                    st.error("Failed to load questions. Please check database files.")
                    return
                
                st.session_state.start_time = time.time()
                st.session_state.current_question_idx = 0
                st.session_state.responses = {}
                st.session_state.question_start_times = {}
                st.session_state.first_attempt_times = {}
                st.session_state.option_changes = {}
                st.session_state.page = 'quiz'
                st.rerun()
        
        st.markdown(f"<p style='text-align: center; font-size: 18px; color: #666;'>Ready to tackle {num_questions} {st.session_state.selected_topic} questions!</p>", unsafe_allow_html=True)


def render_question_navigation():
    """Render question navigation panel"""
    st.markdown("<div class='navigation-panel'>", unsafe_allow_html=True)
    st.markdown("**Question Navigator**")
    
    cols = st.columns(10)
    
    for i, question in enumerate(st.session_state.questions):
        col_idx = i % 10
        
        with cols[col_idx]:
            is_attempted = question['question_id'] in st.session_state.responses
            is_current = i == st.session_state.current_question_idx
            
            if st.button(
                str(i + 1),
                key=f"nav_{i}",
                use_container_width=True,
                disabled=is_current
            ):
                st.session_state.current_question_idx = i
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)


def render_quiz_page():
    """Render the quiz page"""
    if not st.session_state.questions:
        st.error("No questions loaded!")
        if st.button("← Back to Home"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        st.markdown(f"**Topic:** {st.session_state.selected_topic}")
    
    with col2:
        progress = (st.session_state.current_question_idx + 1) / len(st.session_state.questions)
        st.progress(progress)
        st.markdown(f"<p style='text-align: center;'>Question {st.session_state.current_question_idx + 1} / {len(st.session_state.questions)}</p>", unsafe_allow_html=True)
    
    with col3:
        attempted = len(st.session_state.responses)
        st.markdown(f"**Attempted:** {attempted} / {len(st.session_state.questions)}")
    
    render_question_navigation()
    
    current_question = st.session_state.questions[st.session_state.current_question_idx]
    q_id = current_question['question_id']
    
    if q_id not in st.session_state.question_start_times:
        st.session_state.question_start_times[q_id] = time.time()
    
    st.markdown("<div class='question-card'>", unsafe_allow_html=True)
    
    st.markdown(f"### Question {st.session_state.current_question_idx + 1}")
    st.markdown(f"**Difficulty:** {current_question['difficulty'].upper()}")
    st.markdown(f"**Type:** {current_question['question_type'].upper()}")
    
    question_text = current_question['question_text']
    st.markdown(f"<p style='font-size: 16px; margin-top: 20px; line-height: 1.6;'>{question_text}</p>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    prev_response = st.session_state.responses.get(q_id, {})
    
    st.markdown("### Your Answer")
    
    numerical_answer = st.text_input(
        "Enter your answer:",
        value=prev_response.get('final_answer', ''),
        key=f"numerical_{q_id}",
        help=f"Answer type: {current_question.get('answer_type', 'numerical')}"
    )
    
    if numerical_answer and numerical_answer != prev_response.get('final_answer', ''):
        if q_id not in st.session_state.first_attempt_times:
            st.session_state.first_attempt_times[q_id] = time.time() - st.session_state.question_start_times[q_id]
        
        if q_id not in st.session_state.option_changes:
            st.session_state.option_changes[q_id] = 0
        else:
            st.session_state.option_changes[q_id] += 1
        
        st.session_state.responses[q_id] = {
            'final_answer': numerical_answer,
            'changed_answer': st.session_state.option_changes[q_id] > 0,
            'timestamp': time.time()
        }
    
    st.markdown("---")
    st.markdown("### Submit Your Work (Optional)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Upload Handwritten Solution**")
        uploaded_file = st.file_uploader(
            "Upload image (JPG/PNG)",
            type=['jpg', 'jpeg', 'png'],
            key=f"upload_{q_id}"
        )
        
        if uploaded_file:
            if 'uploaded_files' not in st.session_state:
                st.session_state.uploaded_files = {}
            
            image_bytes = uploaded_file.read()
            image_b64 = base64.b64encode(image_bytes).decode()
            st.session_state.uploaded_files[q_id] = {
                'filename': uploaded_file.name,
                'data': image_b64
            }
            
            st.success(f"✓ Uploaded: {uploaded_file.name}")
            st.image(Image.open(io.BytesIO(image_bytes)), width=300)
    
    with col2:
        st.markdown("**Type Your Logic/Work**")
        typed_work = st.text_area(
            "Explain your approach:",
            value=prev_response.get('typed_work', ''),
            height=200,
            key=f"work_{q_id}"
        )
        
        if typed_work:
            if q_id in st.session_state.responses:
                st.session_state.responses[q_id]['typed_work'] = typed_work
            else:
                st.session_state.responses[q_id] = {'typed_work': typed_work}
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.session_state.current_question_idx > 0:
            if st.button("← Previous", use_container_width=True):
                st.session_state.current_question_idx -= 1
                st.rerun()
    
    with col2:
        if st.button("🔖 Mark & Review", use_container_width=True):
            if 'marked_for_review' not in st.session_state:
                st.session_state.marked_for_review = set()
            
            if q_id in st.session_state.marked_for_review:
                st.session_state.marked_for_review.remove(q_id)
            else:
                st.session_state.marked_for_review.add(q_id)
            st.rerun()
    
    with col3:
        if st.session_state.current_question_idx < len(st.session_state.questions) - 1:
            if st.button("Next →", use_container_width=True):
                st.session_state.current_question_idx += 1
                st.rerun()
        else:
            if st.button("🏁 Finish Quiz", use_container_width=True, type="primary"):
                st.session_state.page = 'submit'
                st.rerun()


def generate_performance_report() -> Dict[str, Any]:
    """Generate Stage 1 performance report with LLM answer checking"""
    now = datetime.now(timezone.utc)
    
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    
    questions_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_questions = len(st.session_state.questions)
    
    for idx, question in enumerate(st.session_state.questions):
        q_id = question['question_id']
        response = st.session_state.responses.get(q_id, {})
        
        progress_bar.progress((idx + 1) / total_questions)
        status_text.text(f"Checking answer {idx + 1}/{total_questions}...")
        
        uploaded_files = st.session_state.get('uploaded_files', {})
        work_data = process_student_work(question, st.session_state.responses, uploaded_files)
        
        final_answer = response.get('final_answer', None)
        
        if final_answer:
            is_correct = check_answer_with_llm(
                student_answer=final_answer,
                correct_answer=question['correct_answer'],
                question_text=question['question_text'],
                answer_type=question.get('answer_type', 'numerical')
            )
            
            if is_correct:
                correct_count += 1
            else:
                incorrect_count += 1
        else:
            unattempted_count += 1
            is_correct = False
        
        q_start = st.session_state.question_start_times.get(q_id, st.session_state.start_time)
        time_spent = int(time.time() - q_start) if q_id in st.session_state.question_start_times else 0
        
        first_attempt_latency = int(st.session_state.first_attempt_times.get(q_id, 0))
        num_changes = st.session_state.option_changes.get(q_id, 0)
        
        revision_outcome = "none"
        if num_changes > 0:
            revision_outcome = "improved" if is_correct else "worsened"
        
        uploaded = q_id in uploaded_files
        typed_work = response.get('typed_work', '')
        
        question_data = {
            "question_id": q_id,
            "question_type": question['question_type'],
            "difficulty": question['difficulty'],
            "concept_tags": question['concept_tags'],
            "submission": {
                "final_answer": str(final_answer) if final_answer else "",
                "correct_answer": str(question['correct_answer']),
                "is_correct": is_correct,
                "changed_answer": response.get('changed_answer', False)
            },
            "kpis": {
                "time_spent_sec": time_spent,
                "first_attempt_latency_sec": first_attempt_latency,
                "num_option_changes": num_changes,
                "revision_outcome": revision_outcome
            },
            "optional_work": {
                "handwritten_uploaded": uploaded,
                "typed_work_provided": bool(typed_work),
                "typed_work_text": typed_work,
                "handwritten_work_ocr": work_data['handwritten_work_ocr'],
                "combined_work_text": work_data['combined_work']
            }
        }
        
        questions_data.append(question_data)
    
    progress_bar.empty()
    status_text.empty()
    
    report = {
        "schema_version": "stage1.v1",
        "report_meta": {
            "report_id": f"rep_{now.strftime('%Y_%m_%d_%H%M%S')}",
            "generated_at_iso": now.isoformat(),
            "exam_target": "JEE",
            "subject": "Math",
            "assessment_id": f"quiz_{st.session_state.selected_topic.lower().replace(' ', '_')}_v1",
            "num_questions": len(st.session_state.questions),
            "time_limit_sec": 3600
        },
        "score_summary": {
            "raw_score": correct_count,
            "max_score": len(st.session_state.questions),
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unattempted_count": unattempted_count
        },
        "questions": questions_data
    }
    
    return report


def generate_stage2_report(stage1_report: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Stage 2 report with aggregated metrics"""
    now = datetime.now(timezone.utc)
    
    questions = stage1_report['questions']
    
    time_spent_list = [q['kpis']['time_spent_sec'] for q in questions if q['kpis']['time_spent_sec'] > 0]
    first_attempt_list = [q['kpis']['first_attempt_latency_sec'] for q in questions if q['kpis']['first_attempt_latency_sec'] > 0]
    option_changes_list = [q['kpis']['num_option_changes'] for q in questions]
    
    changed_answers = sum(1 for q in questions if q['submission']['changed_answer'])
    total_attempted = sum(1 for q in questions if q['submission']['final_answer'])
    
    revision_outcomes = [q['kpis']['revision_outcome'] for q in questions]
    improved_count = sum(1 for r in revision_outcomes if r == 'improved')
    worsened_count = sum(1 for r in revision_outcomes if r == 'worsened')
    no_change_count = sum(1 for r in revision_outcomes if r == 'none')
    
    total_revisions = improved_count + worsened_count + no_change_count
    
    easy_questions = [q for q in questions if q['difficulty'] == 'easy']
    easy_time_threshold = 120
    overthinking_count = sum(1 for q in easy_questions if q['kpis']['time_spent_sec'] > easy_time_threshold)
    overthinking_index = overthinking_count / len(easy_questions) if easy_questions else 0
    
    impulsive_threshold = 20
    impulsive_count = sum(1 for q in questions if 0 < q['kpis']['first_attempt_latency_sec'] < impulsive_threshold)
    impulsivity_index = impulsive_count / total_attempted if total_attempted > 0 else 0
    
    concept_data = {}
    
    for question in questions:
        for concept_tag in question['concept_tags']:
            if concept_tag not in concept_data:
                concept_data[concept_tag] = {
                    'questions': [],
                    'attempted': 0,
                    'correct': 0,
                    'time_spent': [],
                    'first_attempt': [],
                    'option_changes': [],
                    'changed_answers': 0,
                    'work_evidence': []
                }
            
            concept_data[concept_tag]['questions'].append(question)
            
            if question['submission']['final_answer']:
                concept_data[concept_tag]['attempted'] += 1
                
                if question['submission']['is_correct']:
                    concept_data[concept_tag]['correct'] += 1
                
                if question['kpis']['time_spent_sec'] > 0:
                    concept_data[concept_tag]['time_spent'].append(question['kpis']['time_spent_sec'])
                
                if question['kpis']['first_attempt_latency_sec'] > 0:
                    concept_data[concept_tag]['first_attempt'].append(question['kpis']['first_attempt_latency_sec'])
                
                concept_data[concept_tag]['option_changes'].append(question['kpis']['num_option_changes'])
                
                if question['submission']['changed_answer']:
                    concept_data[concept_tag]['changed_answers'] += 1
                
                if question['optional_work']['typed_work_provided'] or question['optional_work']['handwritten_uploaded']:
                    concept_data[concept_tag]['work_evidence'].append(question['question_id'])
    
    concepts_list = []
    
    for concept_id, data in concept_data.items():
        if data['attempted'] == 0:
            continue
        
        accuracy = data['correct'] / data['attempted']
        
        work_quality = 5
        if len(data['work_evidence']) >= data['attempted'] * 0.8:
            work_quality = 8 if accuracy > 0.7 else 6
        elif len(data['work_evidence']) >= data['attempted'] * 0.5:
            work_quality = 6 if accuracy > 0.5 else 4
        else:
            work_quality = 3
        
        accuracy_score = accuracy
        
        avg_time = statistics.mean(data['time_spent']) if data['time_spent'] else 0
        time_score = max(0, 1 - (avg_time / 300))
        
        avg_first_attempt = statistics.mean(data['first_attempt']) if data['first_attempt'] else 0
        impulsivity_score = 1 if avg_first_attempt > impulsive_threshold else 0.5
        
        work_score = work_quality / 10
        
        concept_confidence = (
            0.4 * accuracy_score +
            0.2 * time_score +
            0.2 * impulsivity_score +
            0.2 * work_score
        )
        
        concept_obj = {
            "concept_id": concept_id,
            "attempted": data['attempted'],
            "correct": data['correct'],
            "accuracy": round(accuracy, 2),
            "kpis": {
                "avg_time_spent_sec": round(statistics.mean(data['time_spent']), 1) if data['time_spent'] else 0,
                "median_time_spent_sec": round(statistics.median(data['time_spent']), 1) if data['time_spent'] else 0,
                "avg_first_attempt_latency_sec": round(statistics.mean(data['first_attempt']), 1) if data['first_attempt'] else 0,
                "median_first_attempt_latency_sec": round(statistics.median(data['first_attempt']), 1) if data['first_attempt'] else 0,
                "changed_answer_rate": round(data['changed_answers'] / data['attempted'], 2),
                "avg_num_option_changes": round(statistics.mean(data['option_changes']), 2) if data['option_changes'] else 0
            },
            "work_quality_rating": {
                "scale": "1-10",
                "value": work_quality,
                "evidence_count": len(data['work_evidence']),
                "evidence_question_ids": data['work_evidence'][:5],
                "source": "rule_based"
            },
            "concept_confidence": {
                "value": round(concept_confidence, 2),
                "method": "kpi_weighted",
                "inputs_used": [
                    "accuracy",
                    "avg_time_spent_sec",
                    "impulsivity_proxy",
                    "revision_outcome_proxy",
                    "work_quality_rating"
                ]
            }
        }
        
        concepts_list.append(concept_obj)
    
    stage2_report = {
        "schema_version": "stage2.v1",
        "report_meta": {
            "report_id": stage1_report['report_meta']['report_id'] + "_stage2",
            "source_stage1_report_id": stage1_report['report_meta']['report_id'],
            "generated_at_iso": now.isoformat()
        },
        "kpis_summary": {
            "time_spent_sec": {
                "avg": round(statistics.mean(time_spent_list), 1) if time_spent_list else 0,
                "median": round(statistics.median(time_spent_list), 1) if time_spent_list else 0
            },
            "first_attempt_latency_sec": {
                "avg": round(statistics.mean(first_attempt_list), 1) if first_attempt_list else 0,
                "median": round(statistics.median(first_attempt_list), 1) if first_attempt_list else 0
            },
            "num_option_changes": {
                "avg": round(statistics.mean(option_changes_list), 2) if option_changes_list else 0,
                "median": round(statistics.median(option_changes_list), 1) if option_changes_list else 0
            },
            "changed_answer_rate": round(changed_answers / total_attempted, 2) if total_attempted > 0 else 0,
            "revision_effect": {
                "improved_rate": round(improved_count / total_revisions, 2) if total_revisions > 0 else 0,
                "worsened_rate": round(worsened_count / total_revisions, 2) if total_revisions > 0 else 0,
                "no_change_rate": round(no_change_count / total_revisions, 2) if total_revisions > 0 else 0
            },
            "overthinking_index": {
                "value": round(overthinking_index, 2),
                "easy_time_threshold_sec": easy_time_threshold
            },
            "impulsivity_index": {
                "value": round(impulsivity_index, 2),
                "impulsive_threshold_sec": impulsive_threshold
            }
        },
        "concepts": concepts_list
    }
    
    return stage2_report


def generate_stage3_report_with_llm(stage2_report: Dict[str, Any], stage1_report: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Stage 3 report using Gemini LLM with student work analysis"""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.error("GEMINI_API_KEY not found in .env file")
        return None
    
    work_summary = []
    
    for question in stage1_report['questions']:
        q_id = question['question_id']
        combined_work = question['optional_work'].get('combined_work_text', '')
        
        if combined_work:
            work_summary.append({
                'question_id': q_id,
                'concept_tags': question['concept_tags'],
                'is_correct': question['submission']['is_correct'],
                'student_work': combined_work,
                'correct_answer': question['submission']['correct_answer'],
                'student_answer': question['submission']['final_answer']
            })
    
    work_context = ""
    if work_summary:
        work_context = "\n\n**STUDENT WORK ANALYSIS:**\n"
        work_context += "The student provided written explanations/solutions for some questions. Analyze their work to identify:\n"
        work_context += "- Conceptual misunderstandings\n"
        work_context += "- Procedural errors\n"
        work_context += "- Missing knowledge\n"
        work_context += "- Areas of confusion\n\n"
        
        for idx, work_item in enumerate(work_summary, 1):
            work_context += f"**Question {work_item['question_id']}** (Concepts: {', '.join(work_item['concept_tags'])})\n"
            work_context += f"Correct: {'Yes' if work_item['is_correct'] else 'No'} | Student Answer: {work_item['student_answer']} | Correct Answer: {work_item['correct_answer']}\n"
            work_context += f"Student's Work:\n```\n{work_item['student_work'][:500]}\n```\n\n"
    
    prompt = f"""You are an expert educational analyst specializing in JEE mathematics preparation. 

You have been provided with:
1. A detailed performance analysis (Stage 2 report) of a student's quiz attempt
2. The student's written explanations and work for questions they attempted

Your task is to generate a Stage 3 report that:
1. Identifies priority concepts the student needs to work on (based on low accuracy, low confidence, poor work quality)
2. **ANALYZE THE STUDENT'S WORK** to understand their thinking process, identify specific errors, and misconceptions
3. For each priority concept, explain WHY it's important using the signals from the data AND insights from their work
4. Specify concrete improvement aspects (procedural_fluency, conceptual_understanding, visual_intuition, etc.)
5. Create a recommended learning sequence (teach → guided_practice → mixed_practice)
6. Generate video requests with precise scripts for Manim explainer videos that address the SPECIFIC errors you found in their work

**Stage 2 Report:**
```json
{json.dumps(stage2_report, indent=2)}
```
{work_context}

**Instructions:**
- Focus on concepts with accuracy < 0.6 OR concept_confidence < 0.5
- Prioritize "high" for concepts with accuracy < 0.4 or where student work shows fundamental misconceptions
- Prioritize "medium" for concepts with accuracy 0.4-0.6
- When student work is available, USE IT to identify SPECIFIC errors and create targeted video content
- For each priority concept, create 2-3 improvement aspects based on observed errors
- Create a realistic learning sequence with time estimates
- For video requests, be VERY specific about what should be shown visually - reference the student's actual errors
- Use the exact schema provided below

**Output Format:**
Generate a valid JSON object matching this exact schema:

{{
  "schema_version": "stage3.v1",
  "report_meta": {{
    "report_id": "{stage2_report['report_meta']['source_stage1_report_id']}_stage3",
    "source_stage2_report_id": "{stage2_report['report_meta']['report_id']}",
    "generated_at_iso": "{datetime.now(timezone.utc).isoformat()}",
    "producer": "llm"
  }},
  "priority_concepts": [
    {{
      "concept_id": "CONCEPT_TAG",
      "priority": "high|medium|low",
      "why_this_concept": {{
        "signals": {{
          "accuracy": 0.0,
          "concept_confidence": 0.0,
          "work_quality_rating": 0
        }},
        "observed_errors": ["Specific error from student work", "Another error pattern"]
      }},
      "improve_aspects": [
        {{
          "aspect_tag": "procedural_fluency|conceptual_understanding|visual_intuition|problem_identification",
          "goal_statement": "Clear, actionable goal addressing specific student errors"
        }}
      ],
      "recommended_sequence": [
        {{
          "step_type": "teach|guided_practice|mixed_practice|test",
          "title": "Descriptive title",
          "estimated_minutes": 0
        }}
      ]
    }}
  ],
  "video_requests": [
    {{
      "video_id": "VID_CONCEPTTAG_01",
      "concept_id": "CONCEPT_TAG",
      "video_type": "manim_explainer",
      "duration_sec_target": 360,
      "visual_strategy": "number_line|graph|geometric|algebraic|symbolic",
      "addresses_student_error": "Specific error observed in student's work",
      "precise_script_requirements": {{
        "must_include": ["Step 1 addressing student's error", "Step 2", "Step 3"],
        "examples": [
          {{"original": "equation", "transform": "solution", "student_mistake": "what they did wrong"}}
        ],
        "common_traps_to_address": ["Trap 1 from student work", "Trap 2"]
      }},
      "assets": {{
        "template_id": "TEMPLATE.TYPE.NAME",
        "manim_parameters": {{
          "show_animation": true,
          "highlight_key_step": true,
          "pace": "fast_jee|medium|slow_beginner"
        }}
      }}
    }}
  ]
}}

**Important:**
- Respond with ONLY valid JSON, no markdown formatting, no explanations
- Do not include ```json or ``` markers
- Ensure all JSON is properly formatted and escaped
- Include at least 1-3 priority concepts
- Create at least 1 video request per priority concept
- USE STUDENT WORK INSIGHTS to make recommendations highly specific and personalized
"""
    
    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        
        response_text = response.text.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()
        
        stage3_report = json.loads(response_text)
        
        return stage3_report
        
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse LLM response as JSON: {e}")
        st.code(response_text[:500])
        return None
        
    except Exception as e:
        st.error(f"Error generating Stage 3 report: {e}")
        return None


def render_submit_page():
    """Render the submission confirmation page"""
    st.markdown("<h1 style='text-align: center;'>📊 QUIZ SUMMARY 📊</h1>", unsafe_allow_html=True)
    
    attempted = len(st.session_state.responses)
    unattempted = len(st.session_state.questions) - attempted
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Total Questions", len(st.session_state.questions))
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Attempted", attempted)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col3:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Unattempted", unattempted)
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if unattempted > 0:
        st.warning(f"⚠️ You have {unattempted} unattempted questions!")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← Back to Quiz", use_container_width=True):
            st.session_state.page = 'quiz'
            st.rerun()
    
    with col3:
        if st.button("✅ SUBMIT QUIZ", use_container_width=True, type="primary"):
            with st.spinner("Analyzing your performance..."):
                stage1_report = generate_performance_report()
                
                stage2_report = generate_stage2_report(stage1_report)
                
                stage3_report = generate_stage3_report_with_llm(stage2_report, stage1_report)
            
            if stage3_report:
                reports_dir = Path("quiz_reports")
                reports_dir.mkdir(exist_ok=True)
                
                report_file = reports_dir / f"performance_report_{stage3_report['report_meta']['report_id']}.json"
                
                with open(report_file, 'w') as f:
                    json.dump(stage3_report, f, indent=2)
                
                st.session_state.stage1_report = stage1_report
                st.session_state.stage2_report = stage2_report
                st.session_state.final_report = stage3_report
                st.session_state.report_file = str(report_file)
                st.session_state.page = 'results'
                st.rerun()
            else:
                st.error("Failed to generate performance report. Please try again.")


def render_results_page():
    """Render the results page with Stage 3 report"""
    stage3_report = st.session_state.final_report
    stage2_report = st.session_state.stage2_report
    stage1_report = st.session_state.stage1_report
    
    st.markdown("<h1 style='text-align: center;'>🎉 PERFORMANCE ANALYSIS 🎉</h1>", unsafe_allow_html=True)
    
    score_summary = stage1_report['score_summary']
    percentage = (score_summary['correct_count'] / score_summary['max_score']) * 100
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown(f"""
        <div style='text-align: center; padding: 40px;'>
            <div class='score-badge' style='margin: 0 auto;'>
                {percentage:.0f}%
            </div>
            <h2 style='margin-top: 20px;'>Your Score</h2>
            <h3>{score_summary['correct_count']} / {score_summary['max_score']}</h3>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📊 Performance Metrics")
    
    kpis = stage2_report['kpis_summary']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Avg Time/Question", f"{kpis['time_spent_sec']['avg']:.1f}s")
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("First Attempt", f"{kpis['first_attempt_latency_sec']['avg']:.1f}s")
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col3:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Overthinking Index", f"{kpis['overthinking_index']['value']:.2f}")
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col4:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Impulsivity Index", f"{kpis['impulsivity_index']['value']:.2f}")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🎯 Priority Learning Areas")
    
    if stage3_report.get('priority_concepts'):
        for idx, concept in enumerate(stage3_report['priority_concepts'], 1):
            priority_color = {
                'high': '#ff6b6b',
                'medium': '#ffa500',
                'low': '#4ecdc4'
            }.get(concept['priority'], '#gray')
            
            with st.expander(f"🔴 {concept['concept_id']} - {concept['priority'].upper()} Priority", expanded=(idx==1)):
                st.markdown("**Why focus on this?**")
                signals = concept['why_this_concept']['signals']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Accuracy", f"{signals['accuracy']*100:.0f}%")
                with col2:
                    st.metric("Confidence", f"{signals['concept_confidence']*100:.0f}%")
                with col3:
                    st.metric("Work Quality", f"{signals['work_quality_rating']}/10")
                
                if concept['why_this_concept'].get('observed_errors'):
                    st.markdown("<br>**Observed Errors in Your Work:**", unsafe_allow_html=True)
                    for error in concept['why_this_concept']['observed_errors']:
                        st.error(f"❌ {error}")
                
                st.markdown("<br>**What to improve:**", unsafe_allow_html=True)
                for aspect in concept['improve_aspects']:
                    st.markdown(f"- **{aspect['aspect_tag'].replace('_', ' ').title()}**: {aspect['goal_statement']}")
                
                st.markdown("<br>**Recommended Learning Path:**", unsafe_allow_html=True)
                total_time = sum(step['estimated_minutes'] for step in concept['recommended_sequence'])
                
                for step in concept['recommended_sequence']:
                    st.markdown(f"""
                    <div style='background: #f0f0f0; border-left: 4px solid {priority_color}; padding: 10px; margin: 5px 0; border-radius: 5px;'>
                        <strong>{step['step_type'].replace('_', ' ').title()}</strong>: {step['title']}<br>
                        <small>⏱️ {step['estimated_minutes']} minutes</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.info(f"📚 Total estimated time: {total_time} minutes")
    else:
        st.success("✅ Great job! No critical concepts need immediate attention.")
    
    if stage3_report.get('video_requests'):
        st.markdown("---")
        st.markdown("### 🎬 Recommended Learning Videos")
        
        for video in stage3_report['video_requests']:
            with st.expander(f"📺 {video['video_id']} - {video['concept_id']}"):
                st.markdown(f"**Type**: {video['video_type']}")
                st.markdown(f"**Duration**: {video['duration_sec_target']//60} minutes")
                st.markdown(f"**Visual Strategy**: {video['visual_strategy']}")
                
                if video.get('addresses_student_error'):
                    st.warning(f"🎯 **Addresses your error:** {video['addresses_student_error']}")
                
                st.markdown("**Must Include:**")
                for item in video['precise_script_requirements']['must_include']:
                    st.markdown(f"- {item}")
                
                if video['precise_script_requirements'].get('examples'):
                    st.markdown("**Examples:**")
                    for ex in video['precise_script_requirements']['examples']:
                        error_note = f" (Your mistake: {ex.get('student_mistake', 'N/A')})" if ex.get('student_mistake') else ""
                        st.code(f"{ex.get('original', '')} → {ex.get('transform', '')}{error_note}")
                
                if video['precise_script_requirements'].get('common_traps_to_address'):
                    st.markdown("**Common Mistakes to Address:**")
                    for trap in video['precise_script_requirements']['common_traps_to_address']:
                        st.warning(f"⚠️ {trap}")
    
    st.markdown("---")
    st.markdown("### 📄 Download Reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success(f"✓ Report saved to: `{st.session_state.report_file}`")
    
    with col2:
        report_json = json.dumps(stage3_report, indent=2)
        st.download_button(
            label="⬇️ Download Performance Report",
            data=report_json,
            file_name=f"performance_report_{stage3_report['report_meta']['report_id']}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with st.expander("View Detailed Reports"):
        tab1, tab2, tab3 = st.tabs(["Stage 1: Raw Data", "Stage 2: Analytics", "Stage 3: Recommendations"])
        
        with tab1:
            st.json(stage1_report)
        
        with tab2:
            st.json(stage2_report)
        
        with tab3:
            st.json(stage3_report)
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("🏠 Back to Home", use_container_width=True, type="primary"):
            st.session_state.page = 'home'
            st.session_state.questions = []
            st.session_state.responses = {}
            st.session_state.current_question_idx = 0
            st.session_state.selected_topic = None
            st.rerun()


def main():
    """Main application entry point"""
    load_custom_css()
    
    initialize_session_state()
    
    if st.session_state.page == 'home':
        render_home_page()
    elif st.session_state.page == 'quiz':
        render_quiz_page()
    elif st.session_state.page == 'submit':
        render_submit_page()
    elif st.session_state.page == 'results':
        render_results_page()


if __name__ == "__main__":
    main()