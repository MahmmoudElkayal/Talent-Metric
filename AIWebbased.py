"""
Talent Metric — AI-Driven Career Development Platform
Flask Backend Server with Multi-Provider AI Support
"""

import os
import io
import re
import uuid
import json
import hashlib
import urllib.request
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, jsonify, send_file,
    send_from_directory, session, make_response
)

try:
    import requests as http_requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from huggingface_hub import InferenceClient
    HAS_HF = True
except ImportError:
    HAS_HF = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import cm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET", "talent_metric_secret_key_2026")

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "admin_settings.json")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

DEFAULT_SETTINGS = {
    "active_provider": "openrouter",
    "fallback_order": ["openrouter", "openai", "huggingface", "ollama", "lmstudio"],
    "providers": {
        "openrouter": {
            "enabled": True,
            "api_key": "",
            "base_url": "https://openrouter.ai/api/v1",
            "models": {
                "default": "openai/gpt-4o-mini",
                "skills": "openai/gpt-4o-mini",
                "chat_interview": "openai/gpt-4o-mini",
                "video_interview": "openai/gpt-4o-mini",
                "resume": "openai/gpt-4o-mini",
                "career": "openai/gpt-4o-mini"
            }
        },
        "openai": {
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "models": {
                "default": "gpt-4o-mini",
                "skills": "gpt-4o-mini",
                "chat_interview": "gpt-4o-mini",
                "video_interview": "gpt-4o-mini",
                "resume": "gpt-4o-mini",
                "career": "gpt-4o-mini"
            }
        },
        "huggingface": {
            "enabled": False,
            "api_key": "",
            "model": "mistralai/Mistral-7B-Instruct-v0.3"
        },
        "ollama": {
            "enabled": True,
            "base_url": "http://localhost:11434",
            "model": "llama3"
        },
        "lmstudio": {
            "enabled": True,
            "base_url": "http://localhost:1234",
            "model": "local-model"
        }
    },
    "site": {
        "app_name": "Talent Metric",
        "default_target_role": "\u0645\u0637\u0648\u0631 \u0628\u0631\u0645\u062c\u064a\u0627\u062a",
        "interview_fields": [
            "\u062a\u0643\u0646\u0648\u0644\u0648\u062c\u064a\u0627 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a",
            "\u0627\u0644\u0647\u0646\u062f\u0633\u0629", "\u0627\u0644\u062a\u0633\u0648\u064a\u0642",
            "\u0627\u0644\u0645\u0627\u0644\u064a\u0629", "\u0627\u0644\u0645\u0648\u0627\u0631\u062f \u0627\u0644\u0628\u0634\u0631\u064a\u0629",
            "\u0627\u0644\u062a\u0635\u0645\u064a\u0645", "\u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a",
            "\u0627\u0644\u0625\u062f\u0627\u0631\u0629", "\u0623\u062e\u0631\u0649"
        ],
        "max_activity_items": 20
    }
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(saved)
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# AIClient — Multi-Provider AI Abstraction
# ---------------------------------------------------------------------------
class AIClient:
    def __init__(self, settings):
        self.settings = settings

    def get_model_for_feature(self, provider_name, feature="default"):
        # Routing override takes highest priority
        if getattr(self, '_model_override', None):
            return self._model_override
        prov = self.settings.get("providers", {}).get(provider_name, {})
        if provider_name == "huggingface":
            return prov.get("model", DEFAULT_SETTINGS["providers"]["huggingface"]["model"])
        models = prov.get("models", {})
        return models.get(feature, models.get("default", "gpt-4o-mini"))

    def chat(self, messages, feature="default", max_tokens=1024,
             override_provider=None, override_model=None):
        """Route to the correct provider. Respects routing_overrides set in admin."""
        routing = self.settings.get("routing_overrides", {})
        feat_override = routing.get(feature, {})

        # Determine provider: explicit override > routing table > active provider
        active = override_provider or feat_override.get("provider") or self.settings.get("active_provider", "openrouter")
        fallback = self.settings.get("fallback_order", [])

        # Determine model override from routing table
        self._model_override = override_model or feat_override.get("model")

        tried = []
        for prov_name in [active] + [p for p in fallback if p != active]:
            if prov_name in tried:
                continue
            tried.append(prov_name)
            cfg = self.settings.get("providers", {}).get(prov_name)
            if not cfg or not cfg.get("enabled"):
                continue

            try:
                result = self._call_provider(prov_name, cfg, messages, feature, max_tokens)
                if result:
                    self._model_override = None
                    return result
            except Exception as e:
                print(f"[{prov_name}] Error: {e}")
        self._model_override = None
        return None

    def _call_provider(self, name, cfg, messages, feature, max_tokens):
        if name in ("openrouter", "openai"):
            return self._call_openai_compat(name, cfg, messages, feature, max_tokens)
        elif name == "huggingface":
            return self._call_huggingface(cfg, messages, max_tokens)
        elif name in ("ollama", "lmstudio"):
            return self._call_local(name, cfg, messages, feature, max_tokens)
        return None

    def _call_openai_compat(self, name, cfg, messages, feature, max_tokens):
        api_key = cfg.get("api_key", "")
        # Both OpenAI and OpenRouter require an API key
        if not api_key:
            return None
        if not HAS_REQUESTS:
            return None
        model = self.get_model_for_feature(name, feature)
        base = cfg.get("base_url", "").rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        if name == "openrouter":
            headers["HTTP-Referer"] = "http://localhost:5000"
            headers["X-Title"] = "Talent Metric"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        resp = http_requests.post(
            f"{base}/chat/completions",
            headers=headers, json=payload, timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_huggingface(self, cfg, messages, max_tokens):
        api_key = cfg.get("api_key") or os.environ.get("HF_API_KEY")
        if not api_key:
            return None
        if not HAS_HF:
            return None
        client = InferenceClient(
            model=cfg.get("model", "mistralai/Mistral-7B-Instruct-v0.3"),
            token=api_key
        )
        resp = client.chat_completion(
            messages=messages, max_tokens=max_tokens, temperature=0.7
        )
        return resp.choices[0].message.content

    def _call_local(self, name, cfg, messages, feature, max_tokens):
        """
        Support both Ollama-native API and OpenAI-compatible endpoints.
        - Ollama: tries /api/chat (native) first, then /v1/chat/completions
        - LM Studio: uses /v1/chat/completions (OpenAI-compat)
        """
        if not HAS_REQUESTS:
            return None
        model = self.get_model_for_feature(name, feature)
        if not model:
            print(f"[{name}] No model configured. Set default model in Admin panel.")
            return None
        base = cfg.get("base_url", "").rstrip("/")
        if not base:
            print(f"[{name}] No base_url configured.")
            return None

        if name == "ollama":
            # Try Ollama's native /api/chat endpoint first
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": max_tokens}
                }
                resp = http_requests.post(
                    f"{base}/api/chat",
                    json=payload, timeout=120
                )
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
            except Exception as e:
                print(f"[ollama] native /api/chat failed: {e}, trying /v1/chat/completions")

        # OpenAI-compat fallback (LM Studio + Ollama /v1)
        try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "stream": False
            }
            resp = http_requests.post(
                f"{base}/v1/chat/completions",
                json=payload, timeout=120
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[{name}] Connection failed: {e}")
            return None

    def test_connection(self, provider_name):
        cfg = self.settings.get("providers", {}).get(provider_name)
        if not cfg:
            return {"ok": False, "error": "Provider not configured"}
        test_msg = [{"role": "user", "content": "Say 'ok' if you can hear me."}]
        try:
            result = self._call_provider(provider_name, cfg, test_msg, "default", 50)
            if result:
                return {"ok": True, "response": result[:200]}
            return {"ok": False, "error": "No response"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


settings_cache = load_settings()
ai_client = AIClient(settings_cache)

admin_tokens = {}


def get_settings():
    global settings_cache
    return settings_cache


def reload_settings():
    global settings_cache, ai_client
    settings_cache = load_settings()
    ai_client = AIClient(settings_cache)


def extract_json(text):
    if not text:
        return None
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# In-Memory Data Stores
# ---------------------------------------------------------------------------
users_db = {}
user_sessions = {}
interview_sessions = {}
user_activity = {}
user_stats = {}


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


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token not in admin_tokens:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def add_activity(email, act_type, title):
    max_items = get_settings().get("site", {}).get("max_activity_items", 20)
    user_activity.setdefault(email, []).insert(0, {
        "type": act_type, "title": title,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    if len(user_activity[email]) > max_items:
        user_activity[email] = user_activity[email][:max_items]


def ensure_stats(email):
    if email not in user_stats:
        user_stats[email] = {"assessments": 0, "interviews": 0, "resumes": 0, "careers": 0}


def ai_chat(messages, feature="default", max_tokens=1024):
    return ai_client.chat(messages, feature=feature, max_tokens=max_tokens)


# ═══════════════════════════════════════════════════════════════════════════
# Page Routes
# ═══════════════════════════════════════════════════════════════════════════
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

@app.route("/admin")
def admin_page():
    return send_from_directory(".", "admin.html")

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
# ADMIN API
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    password = data.get("password", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Wrong password"}), 401
    token = str(uuid.uuid4())
    admin_tokens[token] = True
    return jsonify({"token": token})


@app.route("/api/admin/settings", methods=["GET", "PUT"])
@admin_required
def admin_settings():
    if request.method == "GET":
        return jsonify(get_settings())
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    save_settings(data)
    reload_settings()
    return jsonify({"ok": True, "message": "Settings saved"})


@app.route("/api/admin/test", methods=["POST"])
@admin_required
def admin_test():
    data = request.get_json()
    provider = data.get("provider", "")
    return jsonify(ai_client.test_connection(provider))


@app.route("/api/admin/local-status", methods=["GET"])
@admin_required
def admin_local_status():
    status = {}
    for name in ("ollama", "lmstudio"):
        cfg = get_settings().get("providers", {}).get(name, {})
        base = cfg.get("base_url", "")
        reachable = False
        try:
            if HAS_REQUESTS:
                resp = http_requests.get(f"{base}/api/tags", timeout=3)
                reachable = resp.ok
        except Exception:
            pass
        status[name] = {"reachable": reachable, "base_url": base, "model": cfg.get("model", "")}
    return jsonify(status)


@app.route("/api/admin/health")
def admin_health():
    return jsonify({
        "status": "ok",
        "admin_password_set": bool(os.environ.get("ADMIN_PASSWORD")),
        "has_requests": HAS_REQUESTS,
        "has_huggingface": HAS_HF,
        "has_reportlab": HAS_REPORTLAB,
        "active_provider": get_settings().get("active_provider", "none")
    })


@app.route("/api/admin/local-models", methods=["GET"])
@admin_required
def admin_local_models():
    """Fetch installed models from Ollama and LM Studio."""
    result = {"ollama": [], "lmstudio": []}
    if not HAS_REQUESTS:
        return jsonify(result)

    # --- Ollama ---
    try:
        cfg = get_settings().get("providers", {}).get("ollama", {})
        base = cfg.get("base_url", "http://localhost:11434").rstrip("/")
        resp = http_requests.get(f"{base}/api/tags", timeout=5)
        if resp.ok:
            data = resp.json()
            result["ollama"] = [
                {"name": m["name"], "size": m.get("size", 0)}
                for m in data.get("models", [])
            ]
    except Exception as e:
        print(f"[ollama] model fetch error: {e}")

    # --- LM Studio ---
    try:
        cfg = get_settings().get("providers", {}).get("lmstudio", {})
        base = cfg.get("base_url", "http://localhost:1234").rstrip("/")
        resp = http_requests.get(f"{base}/v1/models", timeout=5)
        if resp.ok:
            data = resp.json()
            result["lmstudio"] = [
                {"name": m.get("id", m.get("name", "unknown"))}
                for m in data.get("data", [])
            ]
    except Exception as e:
        print(f"[lmstudio] model fetch error: {e}")

    return jsonify(result)


@app.route("/api/site/config", methods=["GET"])
def site_config():
    return jsonify(get_settings().get("site", {}))

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
    target_role = data.get("target_role") or get_settings()["site"]["default_target_role"]

    if not skills:
        return jsonify({"error": "يرجى إدخال المهارات"}), 400

    skills_text = ", ".join(skills)
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

    ai_response = ai_chat(messages, feature="skills")
    result = extract_json(ai_response)

    if not result:
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
    role = data.get("role") or get_settings()["site"]["default_target_role"]
    field = data.get("field") or "تكنولوجيا المعلومات"
    mode = data.get("mode", "chat")  # 'chat' or 'video'
    feature = "video_interview" if mode == "video" else "chat_interview"

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

    ai_response = ai_chat(messages, feature=feature)

    if ai_response:
        result = extract_json(ai_response)
        question = result.get("question", ai_response) if result else ai_response
    else:
        question = f"مرحباً بك في مقابلة وظيفة {role}. أخبرني عن نفسك وخبراتك المهنية في مجال {field}."

    messages.append({"role": "assistant", "content": question})
    interview_sessions[session_id] = {
        "messages": messages,
        "role": role, "field": field,
        "mode": mode, "feature": feature,
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

    ai_response = ai_chat(sess["messages"], feature=sess.get("feature", "chat_interview"))

    if ai_response:
        result = extract_json(ai_response)
        if not result:
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
    ai_response = ai_chat(sess["messages"], feature=sess.get("feature", "chat_interview"))

    result = extract_json(ai_response)

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

    ai_response = ai_chat(messages, feature="resume")
    enhancements = extract_json(ai_response)

    if not enhancements:
        enhancements = {
            "professional_summary": "محترف ذو خبرة في مجال عمله، يتمتع بمهارات قوية في التواصل وحل المشكلات.",
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

    y = h - 2 * cm
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, y, data.get("name", ""))
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, y, data.get("email", "") + " | " + data.get("phone", ""))
    y -= 1.5 * cm

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

    skills_text = ", ".join(skills) if skills else "غير محدد"

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

    ai_response = ai_chat(messages, feature="career")
    result = extract_json(ai_response)

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
    print("=" * 55)
    print("  Talent Metric Server Starting...")
    print(f"  Admin Password: {'[OK] Set via ADMIN_PASSWORD env' if os.environ.get('ADMIN_PASSWORD') else '[--] Using default (admin123)'}")
    print(f"  Settings file: {SETTINGS_FILE}")
    print(f"  PDF Export: {'[OK] Available' if HAS_REPORTLAB else '[--] Install reportlab'}")
    print(f"  URL: http://localhost:5000")
    print("  Admin: http://localhost:5000/admin")
    print("=" * 55)
    app.run(debug=True, port=5000)
