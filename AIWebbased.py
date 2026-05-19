"""
ASK_tech — AI-Driven Career Development Platform
Flask Backend Server with Hugging Face Inference API Integration
"""

import os
import io
import uuid
import json
import hashlib
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, jsonify, send_file,
    send_from_directory, session, make_response
)

# ---------------------------------------------------------------------------
# Hugging Face Inference Client (optional – gracefully degrades)
# ---------------------------------------------------------------------------
try:
    from huggingface_hub import InferenceClient
    HF_TOKEN = os.environ.get("HF_API_KEY")
    if HF_TOKEN:
        hf_client = InferenceClient(
            model="mistralai/Mistral-7B-Instruct-v0.3", token=HF_TOKEN
        )
    else:
        hf_client = None
except ImportError:
    hf_client = None

# ---------------------------------------------------------------------------
# PDF generation (optional)
# ---------------------------------------------------------------------------
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import cm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET", "ask_tech_secret_key_2026")

# ---------------------------------------------------------------------------
# In-Memory Data Stores
# ---------------------------------------------------------------------------
users_db = {}            # email -> {name, email, password_hash, created_at}
user_sessions = {}       # token -> email
interview_sessions = {}  # session_id -> {messages: [], role, field, scores: []}
user_activity = {}       # email -> [{type, title, date}]
user_stats = {}          # email -> {assessments, interviews, resumes, careers}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_current_user():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    email = user_sessions.get(token)
    if email and email in users_db:
        return users_db[email]
    return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "يجب تسجيل الدخول أولاً"}), 401
        return f(user, *args, **kwargs)
    return decorated

def add_activity(email, act_type, title):
    user_activity.setdefault(email, []).insert(0, {
        "type": act_type, "title": title,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    if len(user_activity[email]) > 20:
        user_activity[email] = user_activity[email][:20]

def ensure_stats(email):
    if email not in user_stats:
        user_stats[email] = {
            "assessments": 0, "interviews": 0,
            "resumes": 0, "careers": 0
        }

# ---------------------------------------------------------------------------
# AI Helper – call Hugging Face or return placeholder
# ---------------------------------------------------------------------------
def ai_chat(messages, max_tokens=1024):
    """Send messages to HF Inference API. Falls back to placeholder text."""
    if hf_client:
        try:
            resp = hf_client.chat_completion(
                messages=messages, max_tokens=max_tokens, temperature=0.7
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[HF API Error] {e}")
    # Fallback placeholder (works without API key)
    return None

# ---------------------------------------------------------------------------
# Page Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(".", "MainPage.html")

@app.route("/login")
def login_page():
    return send_from_directory(".", "login.html")

@app.route("/dashboard")
def dashboard_page():
    return send_from_directory(".", "dashboard.html")

@app.route("/skills")
def skills_page():
    return send_from_directory(".", "skills.html")

@app.route("/interview")
def interview_page():
    return send_from_directory(".", "interview.html")

@app.route("/resume")
def resume_page():
    return send_from_directory(".", "resume.html")

@app.route("/career")
def career_page():
    return send_from_directory(".", "career.html")

# Serve static files (CSS / JS)
@app.route("/AIStyle.css")
def serve_css():
    return send_from_directory(".", "AIStyle.css")

@app.route("/AIScript.js")
def serve_js():
    return send_from_directory(".", "AIScript.js")

# ═══════════════════════════════════════════════════════════════════════════
# AUTH API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "جميع الحقول مطلوبة"}), 400
    if email in users_db:
        return jsonify({"error": "البريد الإلكتروني مسجل بالفعل"}), 409

    users_db[email] = {
        "name": name, "email": email,
        "password_hash": hash_password(password),
        "created_at": datetime.now().isoformat()
    }
    ensure_stats(email)
    token = str(uuid.uuid4())
    user_sessions[token] = email
    add_activity(email, "auth", "تسجيل حساب جديد")
    return jsonify({"token": token, "user": {"name": name, "email": email}}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = users_db.get(email)
    if not user or user["password_hash"] != hash_password(password):
        return jsonify({"error": "بيانات الدخول غير صحيحة"}), 401

    token = str(uuid.uuid4())
    user_sessions[token] = email
    add_activity(email, "auth", "تسجيل دخول")
    return jsonify({"token": token, "user": {"name": user["name"], "email": email}})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user_sessions.pop(token, None)
    return jsonify({"message": "تم تسجيل الخروج"})

@app.route("/api/auth/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "غير مسجل"}), 401
    return jsonify({"name": user["name"], "email": user["email"]})

# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/dashboard/stats")
@login_required
def dashboard_stats(user):
    email = user["email"]
    ensure_stats(email)
    return jsonify({
        "stats": user_stats[email],
        "activities": user_activity.get(email, [])[:10],
        "user_name": user["name"]
    })

# ═══════════════════════════════════════════════════════════════════════════
# SKILLS ASSESSMENT API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/skills/assess", methods=["POST"])
@login_required
def assess_skills(user):
    data = request.get_json()
    skills = data.get("skills", [])
    target_role = data.get("target_role", "مطور برمجيات")

    if not skills:
        return jsonify({"error": "يرجى إدخال المهارات"}), 400

    skills_text = "، ".join(skills)
    messages = [
        {"role": "system", "content": (
            "أنت خبير موارد بشرية ومستشار مهني محترف. قم بتحليل مهارات المستخدم "
            "وتحديد الفجوات مقارنة بمتطلبات الوظيفة المستهدفة. "
            "أجب بصيغة JSON تحتوي على: "
            '{"analysis": "تحليل عام", "strengths": ["نقطة قوة 1"], '
            '"gaps": [{"skill": "مهارة", "importance": "عالية/متوسطة/منخفضة", '
            '"recommendation": "توصية"}], "score": 75, '
            '"roadmap": ["خطوة 1", "خطوة 2"]}'
        )},
        {"role": "user", "content": (
            f"مهاراتي الحالية: {skills_text}\n"
            f"الوظيفة المستهدفة: {target_role}\n"
            "قم بتحليل مهاراتي وتحديد الفجوات وتقديم خارطة طريق."
        )}
    ]

    ai_response = ai_chat(messages)

    if ai_response:
        try:
            # Try to extract JSON from the response
            json_start = ai_response.find("{")
            json_end = ai_response.rfind("}") + 1
            if json_start >= 0:
                result = json.loads(ai_response[json_start:json_end])
            else:
                result = {"analysis": ai_response, "strengths": skills[:3],
                          "gaps": [], "score": 70, "roadmap": []}
        except json.JSONDecodeError:
            result = {"analysis": ai_response, "strengths": skills[:3],
                      "gaps": [], "score": 70, "roadmap": []}
    else:
        # Placeholder response
        result = {
            "analysis": f"تحليل مهاراتك لوظيفة {target_role}: لديك أساس جيد في {skills_text}. تحتاج لتطوير بعض المهارات الإضافية.",
            "strengths": skills[:3],
            "gaps": [
                {"skill": "إدارة المشاريع", "importance": "عالية", "recommendation": "احصل على شهادة PMP أو Scrum Master"},
                {"skill": "التواصل المهني", "importance": "متوسطة", "recommendation": "شارك في ورش عمل التواصل"},
                {"skill": "التحليل البياني", "importance": "عالية", "recommendation": "تعلم أدوات مثل Power BI أو Tableau"}
            ],
            "score": 65,
            "roadmap": [
                "الشهر 1-2: تعلم أساسيات إدارة المشاريع",
                "الشهر 3-4: الحصول على شهادة مهنية",
                "الشهر 5-6: بناء مشاريع تطبيقية"
            ]
        }

    email = user["email"]
    ensure_stats(email)
    user_stats[email]["assessments"] += 1
    add_activity(email, "skills", f"تقييم مهارات لوظيفة {target_role}")
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════
# MOCK INTERVIEW API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/interview/start", methods=["POST"])
@login_required
def interview_start(user):
    data = request.get_json()
    role = data.get("role", "مطور برمجيات")
    field = data.get("field", "تكنولوجيا المعلومات")

    session_id = str(uuid.uuid4())
    system_prompt = (
        f"أنت مُحاوِر مهني محترف تجري مقابلة عمل لوظيفة {role} في مجال {field}. "
        "اطرح سؤالاً واحداً في كل مرة باللغة العربية. "
        "بعد إجابة المرشح، قدم تقييماً موجزاً ثم اطرح السؤال التالي. "
        'أجب بصيغة JSON: {"question": "السؤال", "feedback": "التقييم أو فارغ للسؤال الأول", "score": 0}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "ابدأ المقابلة بالسؤال الأول."}
    ]

    ai_response = ai_chat(messages)

    if ai_response:
        try:
            json_start = ai_response.find("{")
            json_end = ai_response.rfind("}") + 1
            result = json.loads(ai_response[json_start:json_end])
            question = result.get("question", ai_response)
        except (json.JSONDecodeError, ValueError):
            question = ai_response
    else:
        question = f"مرحباً بك في مقابلة وظيفة {role}. أخبرني عن نفسك وخبراتك المهنية في مجال {field}."

    messages.append({"role": "assistant", "content": question})
    interview_sessions[session_id] = {
        "messages": messages,
        "role": role, "field": field,
        "scores": [], "question_count": 1,
        "email": user["email"]
    }

    return jsonify({"session_id": session_id, "question": question})

@app.route("/api/interview/respond", methods=["POST"])
@login_required
def interview_respond(user):
    data = request.get_json()
    session_id = data.get("session_id")
    answer = data.get("answer", "")

    sess = interview_sessions.get(session_id)
    if not sess:
        return jsonify({"error": "جلسة المقابلة غير موجودة"}), 404

    sess["messages"].append({"role": "user", "content": answer})
    sess["question_count"] += 1

    eval_prompt = (
        "قيّم الإجابة السابقة ثم اطرح السؤال التالي. "
        'أجب بصيغة JSON: {"feedback": "تقييم الإجابة", "score": 7, "question": "السؤال التالي"}'
    )
    sess["messages"].append({"role": "user", "content": eval_prompt})

    ai_response = ai_chat(sess["messages"])

    if ai_response:
        try:
            json_start = ai_response.find("{")
            json_end = ai_response.rfind("}") + 1
            result = json.loads(ai_response[json_start:json_end])
        except (json.JSONDecodeError, ValueError):
            result = {"feedback": ai_response, "score": 7, "question": "ما هي أهدافك المهنية المستقبلية؟"}
    else:
        placeholders = [
            "كيف تتعامل مع ضغوط العمل والمواعيد النهائية الضيقة؟",
            "أعطني مثالاً على مشكلة واجهتها في العمل وكيف حللتها.",
            "ما هي أهم إنجازاتك المهنية؟",
            "كيف تعمل ضمن فريق وما هو أسلوبك في التواصل؟",
            "أين ترى نفسك بعد خمس سنوات؟"
        ]
        q_idx = min(sess["question_count"] - 1, len(placeholders) - 1)
        result = {
            "feedback": "إجابة جيدة! أظهرت فهماً واضحاً للموضوع. يمكنك تحسين إجابتك بإضافة أمثلة عملية.",
            "score": 7,
            "question": placeholders[q_idx]
        }

    # Remove the eval prompt and add assistant response
    sess["messages"].pop()
    sess["messages"].append({"role": "assistant", "content": json.dumps(result, ensure_ascii=False)})
    sess["scores"].append(result.get("score", 7))

    return jsonify(result)

@app.route("/api/interview/end", methods=["POST"])
@login_required
def interview_end(user):
    data = request.get_json()
    session_id = data.get("session_id")
    sess = interview_sessions.get(session_id)

    if not sess:
        return jsonify({"error": "جلسة المقابلة غير موجودة"}), 404

    scores = sess["scores"]
    avg_score = round(sum(scores) / max(len(scores), 1), 1)

    summary_prompt = (
        "قدم ملخصاً نهائياً لأداء المرشح في المقابلة. "
        'أجب بصيغة JSON: {"summary": "ملخص الأداء", "overall_score": 7.5, '
        '"strengths": ["نقطة قوة"], "improvements": ["نقطة تحسين"], '
        '"tips": ["نصيحة 1", "نصيحة 2"]}'
    )
    sess["messages"].append({"role": "user", "content": summary_prompt})
    ai_response = ai_chat(sess["messages"])

    if ai_response:
        try:
            json_start = ai_response.find("{")
            json_end = ai_response.rfind("}") + 1
            result = json.loads(ai_response[json_start:json_end])
        except (json.JSONDecodeError, ValueError):
            result = None
    else:
        result = None

    if not result:
        result = {
            "summary": f"أداء جيد في مقابلة {sess['role']}. أظهرت معرفة جيدة بالمجال مع بعض النقاط التي تحتاج تطوير.",
            "overall_score": avg_score,
            "strengths": ["التواصل الواضح", "المعرفة التقنية", "الثقة بالنفس"],
            "improvements": ["إضافة أمثلة عملية أكثر", "التركيز على النتائج القابلة للقياس"],
            "tips": [
                "استخدم أسلوب STAR للإجابة على الأسئلة السلوكية",
                "حضّر أمثلة محددة من تجاربك السابقة",
                "تدرب على الإجابة بإيجاز مع الحفاظ على الشمولية"
            ]
        }

    email = user["email"]
    ensure_stats(email)
    user_stats[email]["interviews"] += 1
    add_activity(email, "interview", f"مقابلة تجريبية - {sess['role']}")
    interview_sessions.pop(session_id, None)
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════
# RESUME API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/resume/generate", methods=["POST"])
@login_required
def resume_generate(user):
    data = request.get_json()

    messages = [
        {"role": "system", "content": (
            "أنت خبير كتابة سير ذاتية محترف. حسّن المحتوى المقدم واكتب ملخصاً مهنياً. "
            'أجب بصيغة JSON: {"professional_summary": "الملخص المهني", '
            '"enhanced_experiences": [{"title": "المسمى", "description": "وصف محسن"}], '
            '"skill_categories": [{"category": "فئة", "skills": ["مهارة"]}]}'
        )},
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)}
    ]

    ai_response = ai_chat(messages)

    if ai_response:
        try:
            json_start = ai_response.find("{")
            json_end = ai_response.rfind("}") + 1
            enhancements = json.loads(ai_response[json_start:json_end])
        except (json.JSONDecodeError, ValueError):
            enhancements = {"professional_summary": ai_response}
    else:
        enhancements = {
            "professional_summary": f"محترف ذو خبرة في مجال عمله، يتمتع بمهارات قوية في التواصل وحل المشكلات.",
            "enhanced_experiences": [],
            "skill_categories": []
        }

    email = user["email"]
    ensure_stats(email)
    user_stats[email]["resumes"] += 1
    add_activity(email, "resume", "إنشاء سيرة ذاتية")
    return jsonify({"resume_data": data, "enhancements": enhancements})

@app.route("/api/resume/export-pdf", methods=["POST"])
@login_required
def resume_export_pdf(user):
    data = request.get_json()

    if not HAS_REPORTLAB:
        return jsonify({"error": "مكتبة PDF غير متوفرة"}), 500

    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    # Simple PDF generation (RTL text is limited in reportlab)
    y = h - 2 * cm
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, y, data.get("name", ""))
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, y, data.get("email", "") + " | " + data.get("phone", ""))
    y -= 1.5 * cm

    # Sections
    sections = [
        ("Professional Summary", data.get("summary", "")),
        ("Experience", data.get("experience", "")),
        ("Education", data.get("education", "")),
        ("Skills", data.get("skills", ""))
    ]

    for title, content in sections:
        if not content:
            continue
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, y, title)
        y -= 0.7 * cm
        c.setFont("Helvetica", 11)
        for line in str(content).split("\n"):
            if y < 2 * cm:
                c.showPage()
                y = h - 2 * cm
            c.drawString(2 * cm, y, line[:80])
            y -= 0.5 * cm
        y -= 0.5 * cm

    c.save()
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf",
                     as_attachment=True, download_name="resume.pdf")

# ═══════════════════════════════════════════════════════════════════════════
# CAREER RECOMMENDATIONS API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/career/recommend", methods=["POST"])
@login_required
def career_recommend(user):
    data = request.get_json()
    skills = data.get("skills", [])
    interests = data.get("interests", "")
    experience = data.get("experience_years", 0)

    skills_text = "، ".join(skills) if skills else "غير محدد"

    messages = [
        {"role": "system", "content": (
            "أنت مستشار مهني خبير. بناءً على مهارات المستخدم واهتماماته، "
            "اقترح مسارات مهنية مناسبة. "
            'أجب بصيغة JSON: {"paths": [{"title": "المسمى الوظيفي", '
            '"match_percentage": 85, "description": "وصف", '
            '"required_skills": ["مهارة"], "salary_range": "النطاق", '
            '"growth_outlook": "التوقعات"}], '
            '"general_advice": "نصيحة عامة"}'
        )},
        {"role": "user", "content": (
            f"مهاراتي: {skills_text}\n"
            f"اهتماماتي: {interests}\n"
            f"سنوات الخبرة: {experience}\n"
            "اقترح لي مسارات مهنية مناسبة."
        )}
    ]

    ai_response = ai_chat(messages)

    if ai_response:
        try:
            json_start = ai_response.find("{")
            json_end = ai_response.rfind("}") + 1
            result = json.loads(ai_response[json_start:json_end])
        except (json.JSONDecodeError, ValueError):
            result = None
    else:
        result = None

    if not result:
        result = {
            "paths": [
                {
                    "title": "مهندس برمجيات",
                    "match_percentage": 88,
                    "description": "تطوير وصيانة التطبيقات والأنظمة البرمجية",
                    "required_skills": ["Python", "JavaScript", "SQL", "Git"],
                    "salary_range": "8,000 - 25,000 ر.س",
                    "growth_outlook": "نمو مرتفع - 22% خلال 5 سنوات"
                },
                {
                    "title": "محلل بيانات",
                    "match_percentage": 75,
                    "description": "تحليل البيانات واستخراج الرؤى لدعم القرارات",
                    "required_skills": ["Python", "SQL", "Power BI", "Excel"],
                    "salary_range": "7,000 - 20,000 ر.س",
                    "growth_outlook": "نمو مرتفع جداً - 35% خلال 5 سنوات"
                },
                {
                    "title": "مدير مشاريع تقنية",
                    "match_percentage": 68,
                    "description": "إدارة فرق التطوير والمشاريع التقنية",
                    "required_skills": ["Scrum", "Agile", "JIRA", "Communication"],
                    "salary_range": "12,000 - 30,000 ر.س",
                    "growth_outlook": "نمو متوسط - 15% خلال 5 سنوات"
                }
            ],
            "general_advice": "بناءً على مهاراتك، لديك فرص ممتازة في مجال التكنولوجيا. ركز على تطوير مهاراتك العملية وبناء مشاريع شخصية."
        }

    email = user["email"]
    ensure_stats(email)
    user_stats[email]["careers"] += 1
    add_activity(email, "career", "استكشاف مسارات مهنية")
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════
# Run Server
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  ASK_tech Server Starting...")
    print(f"  HF API: {'[OK] Connected' if hf_client else '[--] No API key (using placeholders)'}")
    print(f"  PDF Export: {'[OK] Available' if HAS_REPORTLAB else '[--] Install reportlab'}")
    print("  URL: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
