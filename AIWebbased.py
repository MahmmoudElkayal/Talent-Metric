"""
Talent Metric — AI-Driven Career Development Platform
Flask Backend v2.0
  - SQLite persistence (talent_metric.db)
  - PBKDF2 / bcrypt password hashing
  - 24h user tokens, 2h admin tokens
  - In-process rate limiting
  - Streaming SSE interview endpoint
  - Video frame (base64 JPEG) injected into vision models
  - Interview history saved to DB
  - Language toggle (ar / en) per request
  - Admin password change from UI
  - OpenRouter live model fetch
  - Dynamic skills list
  - Deep-merge settings
  - All security / bug fixes
"""

import os, io, json, hashlib, secrets, sqlite3, time, threading
from datetime import datetime, timedelta
from contextlib import contextmanager
from functools import wraps
from collections import defaultdict

from flask import (
    Flask, request, jsonify, send_file,
    send_from_directory, Response, stream_with_context
)

# ── Optional dependencies ──────────────────────────────────────────────────────
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

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_RESHAPE = True
except ImportError:
    HAS_ARABIC_RESHAPE = False

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET", "talent_metric_secret_key_2026")

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_FILE      = os.path.join(BASE_DIR, "talent_metric.db")
SETTINGS_FILE = os.path.join(BASE_DIR, "admin_settings.json")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEBUG_MODE   = os.environ.get("DEBUG", "0") == "1"

# ── Settings ───────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "active_provider": "openrouter",
    "fallback_order": ["openrouter", "openai", "huggingface", "ollama", "lmstudio"],
    "routing_overrides": {},
    "providers": {
        "openrouter": {
            "enabled": True, "api_key": "",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "openai/gpt-4o-mini"
        },
        "openai": {
            "enabled": False, "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini"
        },
        "huggingface": {
            "enabled": False, "api_key": "",
            "model": "mistralai/Mistral-7B-Instruct-v0.3"
        },
        "ollama": {
            "enabled": True, "base_url": "http://localhost:11434", "model": "llama3"
        },
        "lmstudio": {
            "enabled": True, "base_url": "http://localhost:1234", "model": "local-model"
        }
    },
    "site": {
        "app_name": "Talent Metric",
        "default_target_role": "مطور برمجيات",
        "language": "ar",
        "interview_fields": [
            "تكنولوجيا المعلومات", "الهندسة", "التسويق",
            "المالية", "الموارد البشرية", "التصميم",
            "المبيعات", "الإدارة", "أخرى"
        ],
        "skills_list": [
            "Python", "JavaScript", "HTML/CSS", "React", "Node.js",
            "SQL", "Java", "C#", "تحليل البيانات",
            "Machine Learning", "Power BI", "Excel متقدم", "Deep Learning",
            "التواصل", "القيادة", "إدارة الوقت", "العمل الجماعي",
            "حل المشكلات", "التفكير النقدي",
            "Git", "Docker", "AWS", "Agile/Scrum", "Linux", "Figma"
        ],
        "max_activity_items": 20
    }
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base without losing nested defaults."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return deep_merge(DEFAULT_SETTINGS, saved)
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Database ───────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                email       TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                email       TEXT NOT NULL,
                expires_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admin_tokens (
                token       TEXT PRIMARY KEY,
                expires_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_stats (
                email       TEXT PRIMARY KEY,
                assessments INTEGER DEFAULT 0,
                interviews  INTEGER DEFAULT 0,
                resumes     INTEGER DEFAULT 0,
                careers     INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                type        TEXT,
                title       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS interview_sessions (
                session_id     TEXT PRIMARY KEY,
                email          TEXT,
                role           TEXT,
                field          TEXT,
                mode           TEXT,
                feature        TEXT,
                lang           TEXT DEFAULT 'ar',
                messages       TEXT DEFAULT '[]',
                scores         TEXT DEFAULT '[]',
                question_count INTEGER DEFAULT 0,
                started_at     TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS interview_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL,
                role          TEXT,
                field         TEXT,
                mode          TEXT,
                overall_score REAL,
                summary       TEXT,
                strengths     TEXT DEFAULT '[]',
                improvements  TEXT DEFAULT '[]',
                tips          TEXT DEFAULT '[]',
                created_at    TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_email  ON sessions(email);
            CREATE INDEX IF NOT EXISTS idx_sessions_exp    ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_activity_email  ON activity_log(email);
            CREATE INDEX IF NOT EXISTS idx_history_email   ON interview_history(email);
        """)


# ── Password hashing ───────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash with PBKDF2-SHA256 (310k rounds). Falls back gracefully."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    except ImportError:
        pass
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000)
    return f"pbkdf2:{salt}:{h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify against bcrypt, pbkdf2, or legacy sha256."""
    try:
        import bcrypt
        if stored_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except ImportError:
        pass
    if stored_hash.startswith("pbkdf2:"):
        parts = stored_hash.split(":", 2)
        if len(parts) == 3:
            _, salt, h = parts
            expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000)
            return secrets.compare_digest(expected.hex(), h)
    # Legacy SHA-256
    return secrets.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored_hash)


# ── Rate limiting ──────────────────────────────────────────────────────────────
_rate_data: dict = defaultdict(list)
_rate_lock = threading.Lock()

def check_rate_limit(key: str, max_calls: int = 15, window: int = 60) -> bool:
    now = time.time()
    with _rate_lock:
        calls = [t for t in _rate_data[key] if now - t < window]
        if len(calls) >= max_calls:
            _rate_data[key] = calls
            return False
        calls.append(now)
        _rate_data[key] = calls
        return True


def rate_limited(max_calls=15, window=60):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            if not check_rate_limit(f"ai:{ip}", max_calls, window):
                return jsonify({"error": "تجاوزت الحد المسموح به. حاول مرة أخرى بعد دقيقة."}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── DB helpers ─────────────────────────────────────────────────────────────────
SESSION_TTL_HOURS  = 24
ADMIN_TTL_HOURS    = 2


def create_user_token(email: str) -> str:
    token = secrets.token_urlsafe(40)
    exp = (datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
    with get_db() as conn:
        # Clean expired tokens first
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
        conn.execute("INSERT INTO sessions (token, email, expires_at) VALUES (?,?,?)",
                     (token, email, exp))
    return token


def get_user_by_token(token: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON s.email=u.email "
            "WHERE s.token=? AND s.expires_at > datetime('now')", (token,)
        ).fetchone()
    return dict(row) if row else None


def create_admin_token() -> str:
    token = secrets.token_urlsafe(40)
    exp = (datetime.utcnow() + timedelta(hours=ADMIN_TTL_HOURS)).isoformat()
    with get_db() as conn:
        conn.execute("DELETE FROM admin_tokens WHERE expires_at < datetime('now')")
        conn.execute("INSERT INTO admin_tokens (token, expires_at) VALUES (?,?)", (token, exp))
    return token


def verify_admin_token(token: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM admin_tokens WHERE token=? AND expires_at > datetime('now')", (token,)
        ).fetchone()
    return row is not None


def ensure_stats(email: str):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_stats (email) VALUES (?)", (email,)
        )


def add_activity(email: str, kind: str, title: str):
    settings = load_settings()
    max_items = settings.get("site", {}).get("max_activity_items", 20)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO activity_log (email, type, title) VALUES (?,?,?)",
            (email, kind, title)
        )
        # Trim old entries
        conn.execute(
            """DELETE FROM activity_log WHERE id IN (
               SELECT id FROM activity_log WHERE email=?
               ORDER BY id DESC LIMIT -1 OFFSET ?)""",
            (email, max_items)
        )


def bump_stat(email: str, column: str):
    ensure_stats(email)
    with get_db() as conn:
        conn.execute(f"UPDATE user_stats SET {column}={column}+1 WHERE email=?", (email,))


# ── Auth decorators ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "غير مصرح"}), 401
        user = get_user_by_token(auth[7:])
        if not user:
            return jsonify({"error": "انتهت الجلسة، يرجى تسجيل الدخول"}), 401
        return f(user, *args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not verify_admin_token(token):
            return jsonify({"error": "صلاحية مسؤول مطلوبة"}), 401
        return f(*args, **kwargs)
    return wrapper


# ── Language helpers ───────────────────────────────────────────────────────────
LANG_INSTRUCTION = {
    "ar": "يجب أن تكتب ردك كاملاً باللغة العربية الفصحى.",
    "en": "You must write your entire response in English only."
}

def get_lang(data: dict = None) -> str:
    """Extract language preference from request body, defaulting to site setting."""
    if data and "lang" in data:
        return data["lang"] if data["lang"] in ("ar", "en") else "ar"
    try:
        settings = load_settings()
        return settings.get("site", {}).get("language", "ar")
    except Exception:
        return "ar"


# ── AI Client ──────────────────────────────────────────────────────────────────
class AIClient:
    def __init__(self, settings: dict):
        self.settings = settings

    def _get_provider_cfg(self, provider_name: str) -> dict:
        return dict(self.settings.get("providers", {}).get(provider_name, {}))

    def _get_model(self, provider_name: str, feature: str = "default") -> str:
        # Routing override
        overrides = self.settings.get("routing_overrides", {})
        feat_override = overrides.get(feature, {})
        if feat_override.get("provider") == provider_name and feat_override.get("model"):
            return feat_override["model"]
        cfg = self._get_provider_cfg(provider_name)
        return cfg.get("model", "gpt-4o-mini")

    # ── OpenAI-compatible call ────────────────────────────────────────────────
    def _call_openai_compat(self, cfg: dict, messages: list,
                             model: str, max_tokens: int,
                             extra_headers: dict = None) -> str | None:
        api_key  = cfg.get("api_key", "")
        base_url = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
        headers  = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        payload = {
            "model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": 0.7
        }
        if HAS_REQUESTS:
            resp = http_requests.post(
                f"{base_url}/chat/completions",
                headers=headers, json=payload, timeout=90
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        import urllib.request as urlreq
        req = urlreq.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=headers, method="POST"
        )
        with urlreq.urlopen(req, timeout=90) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]

    def _stream_openai_compat(self, cfg: dict, messages: list,
                               model: str, max_tokens: int,
                               extra_headers: dict = None):
        """Yield text chunks from an OpenAI-compat streaming endpoint."""
        if not HAS_REQUESTS:
            # Non-streaming fallback
            yield self._call_openai_compat(cfg, messages, model, max_tokens, extra_headers) or ""
            return
        api_key  = cfg.get("api_key", "")
        base_url = cfg.get("base_url", "").rstrip("/")
        headers  = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if extra_headers:
            headers.update(extra_headers)
        payload = {
            "model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": 0.7, "stream": True
        }
        with http_requests.post(
            f"{base_url}/chat/completions",
            headers=headers, json=payload, stream=True, timeout=90
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        chunk = delta.get("content", "")
                        if chunk:
                            yield chunk
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

    def _call_ollama(self, cfg: dict, messages: list, model: str, max_tokens: int) -> str | None:
        base_url = cfg.get("base_url", "http://localhost:11434").rstrip("/")
        if HAS_REQUESTS:
            try:
                resp = http_requests.post(
                    f"{base_url}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                    timeout=120
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"]
            except Exception:
                pass
            # Fallback to OpenAI-compat
            return self._call_openai_compat(
                {**cfg, "api_key": "ollama"},
                messages, model, max_tokens
            )
        return None

    def _stream_ollama(self, cfg: dict, messages: list, model: str, max_tokens: int):
        """Yield chunks from Ollama streaming."""
        if not HAS_REQUESTS:
            yield self._call_ollama(cfg, messages, model, max_tokens) or ""
            return
        base_url = cfg.get("base_url", "http://localhost:11434").rstrip("/")
        try:
            with http_requests.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
                stream=True, timeout=120
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            pass
        except Exception:
            # Fallback to OpenAI-compat stream
            yield from self._stream_openai_compat(
                {**cfg, "api_key": "ollama"},
                messages, model, max_tokens
            )

    def _call_huggingface(self, cfg: dict, messages: list, model: str, max_tokens: int) -> str | None:
        if not HAS_HF:
            return None
        api_key = cfg.get("api_key", "")
        client  = InferenceClient(api_key=api_key)
        resp    = client.chat_completion(
            model=model, messages=messages, max_tokens=max_tokens
        )
        return resp.choices[0].message.content

    def _call_provider(self, provider_name: str, cfg: dict,
                        messages: list, feature: str, max_tokens: int) -> str | None:
        model = self._get_model(provider_name, feature)
        try:
            if provider_name == "openrouter":
                return self._call_openai_compat(cfg, messages, model, max_tokens, {
                    "HTTP-Referer": "https://talentmetric.app",
                    "X-Title": "Talent Metric"
                })
            elif provider_name == "openai":
                return self._call_openai_compat(cfg, messages, model, max_tokens)
            elif provider_name == "huggingface":
                return self._call_huggingface(cfg, messages, model, max_tokens)
            elif provider_name == "ollama":
                return self._call_ollama(cfg, messages, model, max_tokens)
            elif provider_name == "lmstudio":
                return self._call_openai_compat(cfg, messages, model, max_tokens)
        except Exception as e:
            print(f"[{provider_name}] Error: {e}")
            return None

    def _stream_provider(self, provider_name: str, cfg: dict,
                          messages: list, feature: str, max_tokens: int):
        model = self._get_model(provider_name, feature)
        try:
            if provider_name == "openrouter":
                yield from self._stream_openai_compat(cfg, messages, model, max_tokens, {
                    "HTTP-Referer": "https://talentmetric.app",
                    "X-Title": "Talent Metric"
                })
            elif provider_name == "openai":
                yield from self._stream_openai_compat(cfg, messages, model, max_tokens)
            elif provider_name == "ollama":
                yield from self._stream_ollama(cfg, messages, model, max_tokens)
            elif provider_name == "lmstudio":
                yield from self._stream_openai_compat(cfg, messages, model, max_tokens)
            elif provider_name == "huggingface":
                # HF doesn't support streaming easily; yield full response as single chunk
                result = self._call_huggingface(cfg, messages, model, max_tokens)
                if result:
                    yield result
        except Exception as e:
            print(f"[{provider_name}] Stream error: {e}")

    def _get_active_chain(self, feature: str = "default"):
        overrides  = self.settings.get("routing_overrides", {})
        feat_prov  = overrides.get(feature, {}).get("provider", "")
        providers  = self.settings.get("providers", {})
        if feat_prov and providers.get(feat_prov, {}).get("enabled"):
            yield feat_prov
        active = self.settings.get("active_provider", "openrouter")
        if active != feat_prov and providers.get(active, {}).get("enabled"):
            yield active
        for p in self.settings.get("fallback_order", []):
            if p not in (feat_prov, active) and providers.get(p, {}).get("enabled"):
                yield p

    def chat(self, messages: list, feature: str = "default", max_tokens: int = 1024) -> str | None:
        for provider_name in self._get_active_chain(feature):
            cfg    = self._get_provider_cfg(provider_name)
            result = self._call_provider(provider_name, cfg, messages, feature, max_tokens)
            if result:
                return result
        return None

    def stream(self, messages: list, feature: str = "default", max_tokens: int = 1024):
        """Yield text chunks, falling back to next provider on error."""
        for provider_name in self._get_active_chain(feature):
            cfg = self._get_provider_cfg(provider_name)
            chunks = []
            try:
                for chunk in self._stream_provider(provider_name, cfg, messages, feature, max_tokens):
                    chunks.append(chunk)
                    yield chunk
                if chunks:
                    return  # success
            except Exception as e:
                print(f"[{provider_name}] Stream failed: {e}")

    def test_connection(self, provider_name: str, live_overrides: dict = None):
        cfg = dict(self.settings.get("providers", {}).get(provider_name, {}))
        if live_overrides:
            cfg.update(live_overrides)
        if not cfg:
            return {"ok": False, "error": "Provider not configured"}
        test_msg = [{"role": "user", "content": "Say 'ok' if you can hear me."}]
        try:
            model  = cfg.get("model", "gpt-4o-mini")
            result = self._call_provider(provider_name, cfg, test_msg, "default", 50)
            if result:
                return {"ok": True, "response": result[:200]}
            return {"ok": False, "error": "No response — check API key and model name"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── JSON extractor ─────────────────────────────────────────────────────────────
def extract_json(text: str):
    if not text:
        return None
    # Try code fences first
    for fence in ["```json", "```"]:
        if fence in text:
            parts = text.split(fence)
            for i in range(1, len(parts), 2):
                try:
                    return json.loads(parts[i].strip().rstrip("`"))
                except json.JSONDecodeError:
                    pass
    # Try raw JSON
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


# ── Global AI client (lazy-init on each request) ───────────────────────────────
def get_ai_client() -> AIClient:
    return AIClient(load_settings())


# ═══════════════════════════════════════════════════════════════════════════════
# Page routes
# ═══════════════════════════════════════════════════════════════════════════════
PAGES = {
    "/": "MainPage.html", "/login": "login.html", "/dashboard": "dashboard.html",
    "/skills": "skills.html", "/interview": "interview.html", "/resume": "resume.html",
    "/career": "career.html", "/admin": "admin.html", "/history": "history.html",
    "/profile": "profile.html",
}
for _route, _file in PAGES.items():
    app.add_url_rule(
        _route, _route.lstrip("/") or "index",
        lambda f=_file: send_from_directory(BASE_DIR, f)
    )

@app.route("/AIStyle.css")
def serve_css():
    return send_from_directory(BASE_DIR, "AIStyle.css")

@app.route("/AIScript.js")
def serve_js():
    return send_from_directory(BASE_DIR, "AIScript.js")


# ═══════════════════════════════════════════════════════════════════════════════
# Auth API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data     = request.json or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or not password:
        return jsonify({"error": "جميع الحقول مطلوبة"}), 400
    if len(password) < 6:
        return jsonify({"error": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}), 400
    with get_db() as conn:
        existing = conn.execute("SELECT email FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "البريد الإلكتروني مستخدم بالفعل"}), 409
        conn.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?,?,?)",
            (email, name, hash_password(password))
        )
    token = create_user_token(email)
    return jsonify({"token": token, "user": {"email": email, "name": name}}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data     = request.json or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    admin_mode = data.get("admin_mode", False)

    if admin_mode:
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "كلمة مرور المسؤول غير صحيحة"}), 401
        token = create_admin_token()
        return jsonify({"token": token, "admin": True})

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "البريد أو كلمة المرور غير صحيحة"}), 401
    token = create_user_token(email)
    return jsonify({"token": token, "user": {"email": email, "name": user["name"]}})


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout(user):
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
@login_required
def api_me(user):
    return jsonify({"email": user["email"], "name": user["name"]})


@app.route("/api/auth/profile", methods=["PUT"])
@login_required
def api_update_profile(user):
    data         = request.json or {}
    new_name     = (data.get("name") or "").strip()
    new_email    = (data.get("email") or "").strip().lower()
    new_password = data.get("new_password") or ""
    cur_password = data.get("current_password") or ""

    email = user["email"]

    if new_password:
        if not verify_password(cur_password, user["password_hash"]):
            return jsonify({"error": "كلمة المرور الحالية غير صحيحة"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل"}), 400
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET password_hash=? WHERE email=?",
                (hash_password(new_password), email)
            )

    if new_name and new_name != user["name"]:
        with get_db() as conn:
            conn.execute("UPDATE users SET name=? WHERE email=?", (new_name, email))

    with get_db() as conn:
        updated = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return jsonify({"ok": True, "user": {"email": email, "name": updated["name"]}})


# ═══════════════════════════════════════════════════════════════════════════════
# Admin API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "كلمة مرور غير صحيحة"}), 401
    token = create_admin_token()
    return jsonify({"token": token, "expires_in_hours": ADMIN_TTL_HOURS})


@app.route("/api/admin/change-password", methods=["PUT"])
@admin_required
def api_admin_change_password():
    global ADMIN_PASSWORD
    data = request.json or {}
    cur  = data.get("current_password", "")
    new  = data.get("new_password", "")
    if cur != ADMIN_PASSWORD:
        return jsonify({"error": "كلمة المرور الحالية غير صحيحة"}), 400
    if len(new) < 6:
        return jsonify({"error": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}), 400
    # Persist as env override hint — store in settings
    settings = load_settings()
    settings.setdefault("admin", {})["password"] = new
    save_settings(settings)
    ADMIN_PASSWORD = new
    return jsonify({"ok": True})


@app.route("/api/admin/settings", methods=["GET"])
@admin_required
def api_admin_get_settings():
    return jsonify(load_settings())


@app.route("/api/admin/settings", methods=["PUT"])
@admin_required
def api_admin_save_settings():
    data = request.json or {}
    # Remove admin password from settings if stored there previously
    current = load_settings()
    merged  = deep_merge(current, data)
    save_settings(merged)
    return jsonify({"ok": True})


@app.route("/api/admin/test", methods=["POST"])
@admin_required
def api_admin_test():
    data          = request.json or {}
    provider_name = data.get("provider", "openrouter")
    live_overrides = {}
    if "api_key"  in data: live_overrides["api_key"]  = data["api_key"]
    if "base_url" in data: live_overrides["base_url"] = data["base_url"]
    if "model"    in data: live_overrides["model"]    = data["model"]
    result = get_ai_client().test_connection(provider_name, live_overrides or None)
    return jsonify(result)


@app.route("/api/admin/local-status", methods=["GET"])
@admin_required
def api_admin_local_status():
    if not HAS_REQUESTS:
        return jsonify({"ollama": False, "lmstudio": False})
    settings = load_settings()
    def probe(url):
        try:
            http_requests.get(url, timeout=3)
            return True
        except Exception:
            return False
    ollama_url   = settings["providers"]["ollama"].get("base_url", "http://localhost:11434")
    lmstudio_url = settings["providers"]["lmstudio"].get("base_url", "http://localhost:1234")
    return jsonify({
        "ollama":   probe(f"{ollama_url}/api/tags"),
        "lmstudio": probe(f"{lmstudio_url}/v1/models")
    })


@app.route("/api/admin/local-models", methods=["GET"])
@admin_required
def api_admin_local_models():
    if not HAS_REQUESTS:
        return jsonify({"ollama": [], "lmstudio": []})
    settings     = load_settings()
    ollama_url   = settings["providers"]["ollama"].get("base_url", "http://localhost:11434")
    lmstudio_url = settings["providers"]["lmstudio"].get("base_url", "http://localhost:1234")

    ollama_models, lmstudio_models = [], []
    try:
        r = http_requests.get(f"{ollama_url}/api/tags", timeout=5)
        ollama_models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    try:
        r = http_requests.get(f"{lmstudio_url}/v1/models", timeout=5)
        lmstudio_models = [m["id"] for m in r.json().get("data", [])]
    except Exception:
        pass
    return jsonify({"ollama": ollama_models, "lmstudio": lmstudio_models})


@app.route("/api/admin/openrouter-models", methods=["GET"])
@admin_required
def api_admin_openrouter_models():
    """Fetch live model list from OpenRouter API."""
    if not HAS_REQUESTS:
        return jsonify({"error": "requests library not installed"}), 503
    settings = load_settings()
    api_key  = settings["providers"]["openrouter"].get("api_key", "")
    try:
        resp = http_requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=15
        )
        resp.raise_for_status()
        models_raw = resp.json().get("data", [])
        models = []
        for m in models_raw:
            arch = m.get("architecture", {})
            modalities = arch.get("input_modalities", arch.get("modalities", []))
            models.append({
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "vision": "image" in modalities,
                "context": m.get("context_length", 0),
            })
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/admin/health", methods=["GET"])
@admin_required
def api_admin_health():
    return jsonify({
        "has_requests":    HAS_REQUESTS,
        "has_huggingface": HAS_HF,
        "has_reportlab":   HAS_REPORTLAB,
        "has_arabic_pdf":  HAS_ARABIC_RESHAPE,
        "active_provider": load_settings().get("active_provider"),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Site config (public)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/site/config", methods=["GET"])
def api_site_config():
    site = load_settings().get("site", {})
    return jsonify(site)


@app.route("/api/site/skills", methods=["GET"])
def api_site_skills():
    skills = load_settings().get("site", {}).get("skills_list", [])
    return jsonify({"skills": skills})


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/dashboard/stats", methods=["GET"])
@login_required
def api_dashboard_stats(user):
    email = user["email"]
    ensure_stats(email)
    with get_db() as conn:
        stats = conn.execute(
            "SELECT * FROM user_stats WHERE email=?", (email,)
        ).fetchone()
        activity = conn.execute(
            "SELECT type, title, created_at FROM activity_log WHERE email=? ORDER BY id DESC LIMIT 10",
            (email,)
        ).fetchall()
    return jsonify({
        "user": {"name": user["name"], "email": email},
        "stats": {
            "assessments": stats["assessments"] if stats else 0,
            "interviews":  stats["interviews"]  if stats else 0,
            "resumes":     stats["resumes"]     if stats else 0,
            "careers":     stats["careers"]     if stats else 0,
        },
        "activity": [
            {"type": a["type"], "title": a["title"], "created_at": a["created_at"]}
            for a in activity
        ]
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Skills API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/skills/assess", methods=["POST"])
@login_required
@rate_limited(max_calls=10)
def api_skills_assess(user):
    data        = request.json or {}
    skills      = data.get("skills", [])[:30]          # cap at 30
    target_role = (data.get("target_role") or "").strip()[:100]
    lang        = get_lang(data)

    if not skills:
        return jsonify({"error": "يرجى تحديد مهاراتك أولاً"}), 400

    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])
    system_prompt = f"""أنت خبير تطوير مسيرة مهنية. {lang_instruction}
حلل مهارات المستخدم بالنسبة للوظيفة المستهدفة.
أرجع JSON فقط بهذا الشكل (لا تضف نصاً خارجه):
{{
  "score": <0-100>,
  "analysis": "<تحليل شامل>",
  "strengths": ["<ميزة>", ...],
  "gaps": ["<فجوة>", ...],
  "roadmap": ["<خطوة>", ...]
}}"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": f"الوظيفة: {target_role or 'غير محددة'}\nالمهارات: {', '.join(skills)}"}
    ]
    ai_response = get_ai_client().chat(messages, feature="skills", max_tokens=1200)
    result = extract_json(ai_response) or {
        "score": 65, "analysis": "لم نتمكن من تحليل مهاراتك في الوقت الحالي.",
        "strengths": skills[:3], "gaps": [], "roadmap": []
    }

    email = user["email"]
    bump_stat(email, "assessments")
    add_activity(email, "skills", f"تقييم مهارات: {target_role or 'عام'}")
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Interview API
# ═══════════════════════════════════════════════════════════════════════════════

# Interview streaming prompt format
INTERVIEW_STREAM_SYSTEM = {
    "ar": (
        "أنت مدرب مقابلات احترافي. بعد كل إجابة من المرشح:\n"
        "1. قيّم الإجابة بإيجاز (2-3 جمل)\n"
        "2. اطرح السؤال التالي للمقابلة\n\n"
        "اكتب ردك بهذا التنسيق الحرفي:\n"
        "[التقييم]: نصك هنا\n"
        "[النقاط]: X\n"
        "[السؤال]: سؤالك هنا"
    ),
    "en": (
        "You are a professional interview coach. After each answer:\n"
        "1. Evaluate the answer briefly (2-3 sentences)\n"
        "2. Ask the next interview question\n\n"
        "Write your response in EXACTLY this format:\n"
        "[FEEDBACK]: Your evaluation here\n"
        "[SCORE]: X\n"
        "[QUESTION]: Your next question here"
    )
}

MAX_INTERVIEW_QUESTIONS = 7


def parse_stream_response(text: str, lang: str) -> dict:
    """Parse the structured streaming response into components."""
    if lang == "en":
        fb_tag = "[FEEDBACK]:"
        sc_tag = "[SCORE]:"
        qu_tag = "[QUESTION]:"
    else:
        fb_tag = "[التقييم]:"
        sc_tag = "[النقاط]:"
        qu_tag = "[السؤال]:"

    feedback = question = ""
    score = 7.0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(fb_tag):
            feedback = line[len(fb_tag):].strip()
        elif line.startswith(sc_tag):
            try:
                score = float(line[len(sc_tag):].strip().split()[0])
            except (ValueError, IndexError):
                score = 7.0
        elif line.startswith(qu_tag):
            question = line[len(qu_tag):].strip()
    return {"feedback": feedback, "score": score, "question": question}


@app.route("/api/interview/start", methods=["POST"])
@login_required
def api_interview_start(user):
    data    = request.json or {}
    role    = (data.get("role") or "").strip()[:100]
    field   = (data.get("field") or "").strip()[:100]
    mode    = data.get("mode", "chat")
    feature = "video_interview" if mode == "video" else "chat_interview"
    lang    = get_lang(data)

    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])
    system_prompt = (
        f"أنت مدرب مقابلات محترف لدور '{role}' في مجال '{field}'. {lang_instruction}\n"
        "ابدأ بسؤال مقابلة واحد واضح وذو صلة."
    ) if lang == "ar" else (
        f"You are a professional interview coach for the role of '{role}' in the field of '{field}'. {lang_instruction}\n"
        "Start with one clear, relevant interview question."
    )

    messages = [{"role": "system", "content": system_prompt}]
    first_q  = get_ai_client().chat(messages, feature=feature, max_tokens=300)
    if not first_q:
        first_q = "أخبرني عن نفسك ومسيرتك المهنية." if lang == "ar" else "Tell me about yourself and your professional background."

    messages.append({"role": "assistant", "content": first_q})
    session_id = secrets.token_urlsafe(20)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO interview_sessions (session_id,email,role,field,mode,feature,lang,messages,scores,question_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (session_id, user["email"], role, field, mode, feature, lang,
             json.dumps(messages), json.dumps([]), 1)
        )
    return jsonify({"session_id": session_id, "question": first_q, "question_count": 1})


@app.route("/api/interview/respond", methods=["POST"])
@login_required
@rate_limited(max_calls=60)
def api_interview_respond(user):
    data       = request.json or {}
    session_id = data.get("session_id", "")
    answer     = (data.get("answer") or "").strip()
    frame_b64  = data.get("frame_b64")          # optional camera JPEG

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE session_id=? AND email=?",
            (session_id, user["email"])
        ).fetchone()
    if not row:
        return jsonify({"error": "جلسة غير موجودة"}), 404

    messages       = json.loads(row["messages"])
    scores         = json.loads(row["scores"])
    question_count = row["question_count"]
    lang           = row["lang"] or "ar"
    feature        = row["feature"] or "chat_interview"

    # Build user message (add camera frame if vision mode)
    if frame_b64 and feature == "video_interview":
        user_content = [
            {"type": "text",      "text": answer},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}", "detail": "low"}}
        ]
    else:
        user_content = answer

    messages.append({"role": "user", "content": user_content})

    # Streaming system message
    stream_sys = INTERVIEW_STREAM_SYSTEM.get(lang, INTERVIEW_STREAM_SYSTEM["ar"])
    messages_with_sys = [{"role": "system", "content": stream_sys}] + messages[1:]

    # Non-streaming call for structured parse
    ai_response = get_ai_client().chat(messages_with_sys, feature=feature, max_tokens=500)
    if not ai_response:
        ai_response = (
            "[التقييم]: لم أتمكن من تقييم إجابتك.\n[النقاط]: 6\n[السؤال]: حدثني عن تحدٍّ واجهته."
            if lang == "ar" else
            "[FEEDBACK]: Unable to evaluate your answer.\n[SCORE]: 6\n[QUESTION]: Tell me about a challenge you faced."
        )

    parsed = parse_stream_response(ai_response, lang)
    scores.append(parsed["score"])
    messages.append({"role": "assistant", "content": ai_response})
    question_count += 1

    with get_db() as conn:
        conn.execute(
            "UPDATE interview_sessions SET messages=?, scores=?, question_count=? WHERE session_id=?",
            (json.dumps(messages), json.dumps(scores), question_count, session_id)
        )

    done = question_count >= MAX_INTERVIEW_QUESTIONS
    return jsonify({
        "feedback":       parsed["feedback"],
        "score":          parsed["score"],
        "next_question":  parsed["question"] if not done else None,
        "question_count": question_count,
        "done":           done
    })


@app.route("/api/interview/respond/stream", methods=["POST"])
@login_required
@rate_limited(max_calls=60)
def api_interview_respond_stream(user):
    """SSE streaming version of /respond. Yields tokens then a final JSON event."""
    data       = request.json or {}
    session_id = data.get("session_id", "")
    answer     = (data.get("answer") or "").strip()
    frame_b64  = data.get("frame_b64")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE session_id=? AND email=?",
            (session_id, user["email"])
        ).fetchone()
    if not row:
        def err_gen():
            yield f"data: {json.dumps({'error': 'جلسة غير موجودة'})}\n\n"
        return Response(stream_with_context(err_gen()), content_type="text/event-stream")

    messages       = json.loads(row["messages"])
    scores         = json.loads(row["scores"])
    question_count = row["question_count"]
    lang           = row["lang"] or "ar"
    feature        = row["feature"] or "chat_interview"

    if frame_b64 and feature == "video_interview":
        user_content = [
            {"type": "text",      "text": answer},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}", "detail": "low"}}
        ]
    else:
        user_content = answer

    messages.append({"role": "user", "content": user_content})
    stream_sys = INTERVIEW_STREAM_SYSTEM.get(lang, INTERVIEW_STREAM_SYSTEM["ar"])
    messages_with_sys = [{"role": "system", "content": stream_sys}] + messages[1:]

    ai_client = get_ai_client()

    def generate():
        full_text = []
        try:
            for chunk in ai_client.stream(messages_with_sys, feature=feature, max_tokens=500):
                full_text.append(chunk)
                yield f"data: {json.dumps({'token': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        complete = "".join(full_text)
        parsed   = parse_stream_response(complete, lang)
        new_scores = scores + [parsed["score"]]
        new_messages = messages + [{"role": "assistant", "content": complete}]
        new_qcount = question_count + 1

        with get_db() as conn:
            conn.execute(
                "UPDATE interview_sessions SET messages=?, scores=?, question_count=? WHERE session_id=?",
                (json.dumps(new_messages), json.dumps(new_scores), new_qcount, session_id)
            )

        done = new_qcount >= MAX_INTERVIEW_QUESTIONS
        yield f"data: {json.dumps({'done': True, 'score': parsed['score'], 'feedback': parsed['feedback'], 'next_question': parsed['question'] if not done else None, 'question_count': new_qcount, 'interview_done': done})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/api/interview/end", methods=["POST"])
@login_required
def api_interview_end(user):
    data       = request.json or {}
    session_id = data.get("session_id", "")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE session_id=? AND email=?",
            (session_id, user["email"])
        ).fetchone()
    if not row:
        return jsonify({"error": "جلسة غير موجودة"}), 404

    messages = json.loads(row["messages"])
    scores   = json.loads(row["scores"])
    lang     = row["lang"] or "ar"
    role     = row["role"] or ""
    field    = row["field"] or ""
    mode     = row["mode"] or "chat"

    overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])

    summary_prompt = (
        f"قدّم ملخصاً نهائياً لأداء المرشح. {lang_instruction}\n"
        "أرجع JSON فقط:\n"
        '{"summary":"<ملخص>","strengths":["..."],"improvements":["..."],"tips":["..."]}'
    ) if lang == "ar" else (
        f"Provide a final performance summary for the candidate. {lang_instruction}\n"
        "Return JSON only:\n"
        '{"summary":"<summary>","strengths":["..."],"improvements":["..."],"tips":["..."]}'
    )

    summary_messages = messages + [{"role": "user", "content": summary_prompt}]
    ai_response = get_ai_client().chat(summary_messages, feature="chat_interview", max_tokens=800)
    result = extract_json(ai_response) or {
        "summary": "أداء جيد في المقابلة." if lang == "ar" else "Good interview performance.",
        "strengths": [], "improvements": [], "tips": []
    }
    result["overall_score"] = overall_score

    # Save to history
    with get_db() as conn:
        conn.execute(
            "INSERT INTO interview_history (email,role,field,mode,overall_score,summary,strengths,improvements,tips) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                user["email"], role, field, mode, overall_score,
                result.get("summary", ""),
                json.dumps(result.get("strengths", [])),
                json.dumps(result.get("improvements", [])),
                json.dumps(result.get("tips", []))
            )
        )
        conn.execute("DELETE FROM interview_sessions WHERE session_id=?", (session_id,))

    email = user["email"]
    bump_stat(email, "interviews")
    add_activity(email, "interview", f"مقابلة: {role or 'عام'} — {overall_score}/10")
    return jsonify(result)


@app.route("/api/interview/history", methods=["GET"])
@login_required
def api_interview_history(user):
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 10
    offset   = (page - 1) * per_page
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM interview_history WHERE email=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user["email"], per_page, offset)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM interview_history WHERE email=?", (user["email"],)
        ).fetchone()[0]
    items = []
    for r in rows:
        items.append({
            "id":            r["id"],
            "role":          r["role"],
            "field":         r["field"],
            "mode":          r["mode"],
            "overall_score": r["overall_score"],
            "summary":       r["summary"],
            "strengths":     json.loads(r["strengths"]  or "[]"),
            "improvements":  json.loads(r["improvements"] or "[]"),
            "tips":          json.loads(r["tips"] or "[]"),
            "created_at":    r["created_at"],
        })
    return jsonify({"items": items, "total": total, "page": page, "per_page": per_page})


@app.route("/api/interview/history/<int:history_id>", methods=["GET"])
@login_required
def api_interview_history_item(user, history_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interview_history WHERE id=? AND email=?",
            (history_id, user["email"])
        ).fetchone()
    if not row:
        return jsonify({"error": "لم يُعثر على السجل"}), 404
    return jsonify({
        "id":            row["id"],
        "role":          row["role"],
        "field":         row["field"],
        "mode":          row["mode"],
        "overall_score": row["overall_score"],
        "summary":       row["summary"],
        "strengths":     json.loads(row["strengths"]    or "[]"),
        "improvements":  json.loads(row["improvements"] or "[]"),
        "tips":          json.loads(row["tips"]         or "[]"),
        "created_at":    row["created_at"],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Resume API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/resume/generate", methods=["POST"])
@login_required
@rate_limited(max_calls=5)
def api_resume_generate(user):
    data = request.json or {}
    lang = get_lang(data)
    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])

    system_prompt = (
        f"أنت خبير كتابة سير ذاتية احترافية. {lang_instruction}\n"
        "حسّن السيرة الذاتية المقدمة وأعد هيكلتها.\n"
        "أرجع JSON فقط:\n"
        '{"summary":"<ملخص مهني>","experience":[{"title":"","company":"","period":"","bullets":["..."]}],'
        '"skills":["..."],"improvements":["..."]}'
    ) if lang == "ar" else (
        f"You are a professional resume writing expert. {lang_instruction}\n"
        "Improve and restructure the provided resume.\n"
        "Return JSON only:\n"
        '{"summary":"<professional summary>","experience":[{"title":"","company":"","period":"","bullets":["..."]}],'
        '"skills":["..."],"improvements":["..."]}'
    )

    user_msg = f"السيرة الذاتية:\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_msg}
    ]
    ai_response = get_ai_client().chat(messages, feature="resume", max_tokens=1500)
    result = extract_json(ai_response) or {
        "summary": data.get("summary", ""),
        "experience": data.get("experience", []),
        "skills": data.get("skills", []),
        "improvements": ["تعذّر تحسين السيرة تلقائياً."]
    }

    email = user["email"]
    bump_stat(email, "resumes")
    add_activity(email, "resume", "تحسين سيرة ذاتية")
    return jsonify(result)


def _render_arabic(text: str) -> str:
    """Reshape + bidi-order Arabic text for correct PDF rendering."""
    if HAS_ARABIC_RESHAPE:
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            pass
    return str(text)


@app.route("/api/resume/export-pdf", methods=["POST"])
@login_required
def api_resume_export_pdf(user):
    if not HAS_REPORTLAB:
        return jsonify({"error": "مكتبة PDF غير متوفرة. pip install reportlab"}), 503

    data = request.json or {}

    # Try to load Arabic font (Amiri) if available
    arabic_font = "Helvetica"
    font_path = os.path.join(BASE_DIR, "fonts", "Amiri-Regular.ttf")
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("Amiri", font_path))
            arabic_font = "Amiri"
        except Exception:
            pass

    buf = io.BytesIO()
    c   = pdf_canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # Header
    c.setFillColorRGB(0.1, 0.1, 0.25)
    c.rect(0, H - 80, W, 80, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 22)
    name = _render_arabic(data.get("name", user["name"]))
    c.drawCentredString(W / 2, H - 45, name)
    c.setFont("Helvetica", 11)
    contact_parts = [data.get("email", user["email"])]
    if data.get("phone"):  contact_parts.append(data["phone"])
    if data.get("location"): contact_parts.append(data["location"])
    c.drawCentredString(W / 2, H - 65, "  |  ".join(contact_parts))

    y = H - 110
    margin = 2 * cm

    def section_header(title, ypos):
        c.setFillColorRGB(0.15, 0.35, 0.7)
        c.rect(margin, ypos - 4, W - 2 * margin, 18, fill=True, stroke=False)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin + 5, ypos, _render_arabic(title))
        c.setFillColorRGB(0, 0, 0)
        return ypos - 24

    def wrap_text(text, width_pts, font_name="Helvetica", size=10):
        words = str(text).split()
        lines, current = [], ""
        c.setFont(font_name, size)
        for w in words:
            test = (current + " " + w).strip()
            if c.stringWidth(test, font_name, size) < width_pts:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def draw_text(text, xpos, ypos, font_name="Helvetica", size=10, max_width=None):
        c.setFont(font_name, size)
        rendered = _render_arabic(text)
        if max_width:
            lines = wrap_text(rendered, max_width, font_name, size)
            for line in lines:
                c.drawString(xpos, ypos, line)
                ypos -= size + 3
            return ypos
        c.drawString(xpos, ypos, rendered)
        return ypos - (size + 4)

    # Professional Summary
    if data.get("summary"):
        y = section_header("الملخص المهني / Professional Summary", y)
        c.setFont("Helvetica", 10)
        for line in wrap_text(data["summary"], W - 2 * margin - 10):
            c.drawString(margin + 5, y, _render_arabic(line))
            y -= 14
        y -= 6

    # Experience
    if data.get("experience"):
        y = section_header("الخبرة العملية / Work Experience", y)
        for exp in data["experience"]:
            c.setFont("Helvetica-Bold", 11)
            c.setFillColorRGB(0.1, 0.1, 0.3)
            y = draw_text(f"{exp.get('title','')} — {exp.get('company','')}", margin + 5, y, "Helvetica-Bold", 11)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            y = draw_text(exp.get("period", ""), margin + 5, y, "Helvetica", 9)
            c.setFillColorRGB(0, 0, 0)
            for bullet in exp.get("bullets", []):
                y = draw_text(f"  • {bullet}", margin + 10, y, "Helvetica", 10, W - 2 * margin - 20)
            y -= 6
            if y < 80:
                c.showPage(); y = H - 60

    # Skills
    if data.get("skills"):
        y = section_header("المهارات / Skills", y)
        skills_str = "  •  ".join(data["skills"])
        for line in wrap_text(skills_str, W - 2 * margin - 10):
            y = draw_text(line, margin + 5, y)
        y -= 6

    c.save()
    buf.seek(0)
    safe_name = user["name"].replace(" ", "_")
    return send_file(
        buf, as_attachment=True,
        download_name=f"resume_{safe_name}.pdf",
        mimetype="application/pdf"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Career API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/career/recommend", methods=["POST"])
@login_required
@rate_limited(max_calls=10)
def api_career_recommend(user):
    data   = request.json or {}
    lang   = get_lang(data)
    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])

    system_prompt = (
        f"أنت مستشار مسيرة مهنية خبير. {lang_instruction}\n"
        "بناءً على المهارات والخلفية المقدمة، اقترح 3 مسارات مهنية.\n"
        "أرجع JSON فقط:\n"
        '{"paths":[{"title":"","match_percentage":0,"description":"","required_skills":["..."],"salary_range":"","growth_outlook":""}],"general_advice":""}'
    ) if lang == "ar" else (
        f"You are an expert career counselor. {lang_instruction}\n"
        "Based on the provided skills and background, suggest 3 career paths.\n"
        "Return JSON only:\n"
        '{"paths":[{"title":"","match_percentage":0,"description":"","required_skills":["..."],"salary_range":"","growth_outlook":""}],"general_advice":""}'
    )

    user_content = json.dumps({
        k: v for k, v in data.items() if k != "lang"
    }, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content}
    ]
    ai_response = get_ai_client().chat(messages, feature="career", max_tokens=1200)
    result = extract_json(ai_response) or {
        "paths": [
            {"title": "مهندس برمجيات", "match_percentage": 88,
             "description": "تطوير وصيانة التطبيقات",
             "required_skills": ["Python", "JavaScript", "SQL"],
             "salary_range": "8,000–25,000 ر.س", "growth_outlook": "نمو مرتفع"}
        ],
        "general_advice": "ركز على تطوير مهاراتك العملية."
    }

    email = user["email"]
    bump_stat(email, "careers")
    add_activity(email, "career", "استكشاف مسارات مهنية")
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Bootstrap & Run
# ═══════════════════════════════════════════════════════════════════════════════
init_db()

# Reload admin password from settings if previously changed via UI
_settings_cache = load_settings()
if _settings_cache.get("admin", {}).get("password"):
    ADMIN_PASSWORD = _settings_cache["admin"]["password"]

if __name__ == "__main__":
    print("=" * 60)
    print("  Talent Metric v2.0")
    print(f"  DB:       {DB_FILE}")
    print(f"  Settings: {SETTINGS_FILE}")
    print(f"  PDF:      {'✓ reportlab' if HAS_REPORTLAB else '✗ pip install reportlab'}")
    print(f"  Arabic PDF: {'✓ arabic_reshaper + bidi' if HAS_ARABIC_RESHAPE else '✗ pip install arabic-reshaper python-bidi'}")
    print(f"  Admin pw: {'✓ env ADMIN_PASSWORD set' if os.environ.get('ADMIN_PASSWORD') else '⚠ using default admin123'}")
    print(f"  URL:      http://localhost:5000")
    print(f"  Admin:    http://localhost:5000/admin")
    print("=" * 60)
    app.run(debug=DEBUG_MODE, port=5000)
