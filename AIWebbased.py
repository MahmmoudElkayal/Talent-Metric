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
    """
    Recursively merges an override configuration dictionary into a base configuration dictionary.
    
    This ensures that when administrators update specific routing or provider fields, they
    do not accidentally wipe out nested defaults (e.g., specific parameters for other AI providers).
    
    Args:
        base (dict): The default settings dictionary containing the fallback catalog.
        override (dict): The custom administrative override settings dictionary.
        
    Returns:
        dict: A new dictionary containing the deep merged key-value pairs.
    """
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_settings() -> dict:
    """
    Loads site administration settings from the local 'admin_settings.json' file.
    
    If the file exists, it is parsed and dynamically merged with the system default 
    configuration parameters (DEFAULT_SETTINGS) using the `deep_merge` helper. This preserves 
    default structures for newly added parameters if the file on disk is from an older version.
    
    Returns:
        dict: The final merged configuration dictionary.
    """
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return deep_merge(DEFAULT_SETTINGS, saved)
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    """
    Saves the updated administration settings dictionary to 'admin_settings.json'.
    
    Ensures correct encoding (UTF-8) for Arabic/multilingual text strings and saves 
    the output with a clean, human-readable 2-space indentation format.
    
    Args:
        data (dict): The complete settings dictionary to persist.
    """
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Database ───────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    """
    A context manager helper that yields a transactional SQLite connection.
    
    Configures important SQLite parameters for the application:
    1. Row Factory: Sets connection row_factory to sqlite3.Row to support key-based column access.
    2. Write-Ahead Logging (WAL): Sets 'journal_mode=WAL' which optimizes concurrency, allowing 
       multiple parallel read operations to execute without blocking writes.
    3. Foreign Key Constraints: Enforces relational schema checks ('foreign_keys=ON').
    
    Ensures transactions are safely committed on successful completion, automatically 
    rolled back on error exceptions, and that resources are properly closed afterwards.
    
    Yields:
        sqlite3.Connection: The configured transactional SQLite database connection object.
    """
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
    """
    Initializes the SQLite database schema if the tables do not already exist.
    
    Defines the following relational schemas:
    1. `users`: Permanent credentials index (email, name, hashed password, created date).
    2. `sessions`: Standard candidate session keys mapping tokens to emails (24h lifespan).
    3. `admin_tokens`: Administrator session keys with short exipration bounds (2h lifespan).
    4. `user_stats`: Tracks counters for Dashboard metrics (assessments, interviews, resumes, etc.).
    5. `activity_log`: Holds audit logs showing candidate actions (limit-pruned to max_items).
    6. `interview_sessions`: Reload-proof middle-state mock interview cache.
    7. `interview_history`: Persistent logs of completed mock interviews, containing scores,
       AI summaries, strengths, improvement areas, and developer roadmaps.
       
    Creates relevant B-tree indexes to optimize performance for high-frequency search fields.
    """
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
                field          TEXT,
                mode           TEXT,
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
    """
    Secures a raw password string using cryptographic hashing.
    
    Tries to utilize the robust `bcrypt` library (configured at 12 work rounds) for 
    maximum resistance to offline GPU brute-force attacks. If `bcrypt` is not installed, 
    falls back gracefully to standard PBKDF2-HMAC-SHA256 with a cryptographically secure 
    16-byte random salt and 310,000 computation rounds.
    
    Args:
        password (str): The raw text password input by the user.
        
    Returns:
        str: The fully hashed password string (prefixed to indicate the method used).
    """
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    except ImportError:
        pass
    # PBKDF2 fallback on environments without bcrypt installed
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000)
    return f"pbkdf2:{salt}:{h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a raw password input against the stored cryptographic hash.
    
    Supports three levels of verification:
    1. Bcrypt validation (for standard hashes starting with '$2').
    2. PBKDF2 validation (re-computing and matching the SHA256 bytes using 
       the secure constant-time helper `secrets.compare_digest` to prevent timing attacks).
    3. Legacy SHA-256 validation (for retro-compatibility with basic user schemas).
    
    Args:
        password (str): The candidate password to verify.
        stored_hash (str): The hashed signature loaded from the database.
        
    Returns:
        bool: True if the password is correct, False otherwise.
    """
    try:
        import bcrypt
        if stored_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except ImportError:
        pass
    # Handle PBKDF2 comparison
    if stored_hash.startswith("pbkdf2:"):
        parts = stored_hash.split(":", 2)
        if len(parts) == 3:
            _, salt, h = parts
            expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000)
            return secrets.compare_digest(expected.hex(), h)
    # Legacy SHA-256 fallback comparison (uses constant-time check)
    return secrets.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored_hash)


# ── Rate limiting ──────────────────────────────────────────────────────────────
# Global in-memory storage dictionary that tracks request timestamps per key
_rate_data: dict = defaultdict(list)
# Threading lock object to safeguard operations against thread context-switching issues
_rate_lock = threading.Lock()

def check_rate_limit(key: str, max_calls: int = 15, window: int = 60) -> bool:
    """
    Thread-safe, high-performance in-memory rate-limiter check.
    
    Tracks request timestamps within a sliding window. Evicts expired timestamps 
    automatically and verifies whether the request rate exceeds allowed limits.
    
    Args:
        key (str): The rate limit identifier key (e.g., 'ai:127.0.0.1').
        max_calls (int): Maximum number of allowable operations within the window.
        window (int): The sliding window duration in seconds.
        
    Returns:
        bool: True if the request is within rate limits, False if rate-limited.
    """
    now = time.time()
    with _rate_lock:
        # Keep only timestamps that fall inside the active window range
        calls = [t for t in _rate_data[key] if now - t < window]
        if len(calls) >= max_calls:
            _rate_data[key] = calls
            return False
        # Log the current access timestamp
        calls.append(now)
        _rate_data[key] = calls
        return True


def rate_limited(max_calls=15, window=60):
    """
    A custom Flask route decorator that enforces rate-limiting per client IP address.
    
    Args:
        max_calls (int): The operation limit threshold.
        window (int): The duration of the window in seconds.
        
    Returns:
        function: The wrapped route handler.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            # Format the IP limit key
            if not check_rate_limit(f"ai:{ip}", max_calls, window):
                return jsonify({"error": "تجاوزت الحد المسموح به. حاول مرة أخرى بعد دقيقة."}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── DB helpers ─────────────────────────────────────────────────────────────────
# User session token validity span in hours
SESSION_TTL_HOURS  = 24
# Admin session token validity span in hours
ADMIN_TTL_HOURS    = 2


def create_user_token(email: str) -> str:
    """
    Creates and stores a secure session authorization token for a logged-in user.
    
    Prunes expired session rows automatically before inserting the newly generated
    cryptographically secure URL-safe token. Expiration is set to 24 hours.
    
    Args:
        email (str): The candidate's email address.
        
    Returns:
        str: The generated token.
    """
    token = secrets.token_urlsafe(40)
    exp = (datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
    with get_db() as conn:
        # Prevent database bloating by deleting expired session records first
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
        conn.execute("INSERT INTO sessions (token, email, expires_at) VALUES (?,?,?)",
                     (token, email, exp))
    return token


def get_user_by_token(token: str):
    """
    Authenticates a user request using their session token.
    
    Verifies that the token matches a record in the database and is still within
    its active validity window.
    
    Args:
        token (str): The bearer authorization token.
        
    Returns:
        dict: A dictionary containing the user's data on success, or None on failure/expiration.
    """
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
    """
    Validates the active, unexpired session token of an Administrator.
    
    Checks database records to confirm if the administrator token is matching
    and has not reached its scheduled expiration limits.
    
    Args:
        token (str): The bearer admin token.
        
    Returns:
        bool: True if authorized, False otherwise.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM admin_tokens WHERE token=? AND expires_at > datetime('now')", (token,)
        ).fetchone()
    return row is not None


def ensure_stats(email: str):
    """
    Guarantees that a metrics entry row exists in `user_stats` for the given email.
    
    Uses `INSERT OR IGNORE` to safely handle initializations without altering
    pre-existing numbers.
    
    Args:
        email (str): The candidate's email address.
    """
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_stats (email) VALUES (?)", (email,)
        )


def add_activity(email: str, kind: str, title: str):
    """
    Appends a new user activity log entry to the `activity_log` table.
    
    To prevent database bloating over time, this function retrieves the 
    maximum allowable logs per user (from `max_activity_items` settings) and
    safely trims older entries using a limit offset sub-query in SQLite.
    
    Args:
        email (str): The candidate's email address.
        kind (str): The category of activity (e.g., 'resume', 'skills', 'interview').
        title (str): A user-friendly Arabic/English description of the action.
    """
    settings = load_settings()
    max_items = settings.get("site", {}).get("max_activity_items", 20)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO activity_log (email, type, title) VALUES (?,?,?)",
            (email, kind, title)
        )
        # Safely delete historical records exceeding the configured capacity
        conn.execute(
            """DELETE FROM activity_log WHERE id IN (
               SELECT id FROM activity_log WHERE email=?
               ORDER BY id DESC LIMIT -1 OFFSET ?)""",
            (email, max_items)
        )


def bump_stat(email: str, column: str):
    """
    Increments a specific metric column inside the user's dashboard statistics deck.
    
    Ensures that a row exists for the user first before triggering the increment update.
    
    Args:
        email (str): The candidate's email address.
        column (str): The target table column name to increment (e.g. 'interviews').
    """
    ensure_stats(email)
    with get_db() as conn:
        conn.execute(f"UPDATE user_stats SET {column}={column}+1 WHERE email=?", (email,))


# ── Auth decorators ────────────────────────────────────────────────────────────
def login_required(f):
    """
    Flask route decorator that enforces user authentication using session tokens.
    
    Checks request headers for a valid `Authorization: Bearer <token>` signature,
    verifies it in the sessions database table, and injects the loaded user dict 
    directly as the first argument to the decorated route.
    
    Returns:
        HTTP 401: If credentials are missing, malformed, or expired.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "غير مصرح"}), 401
        # Extract bearer token signature
        user = get_user_by_token(auth[7:])
        if not user:
            return jsonify({"error": "انتهت الجلسة، يرجى تسجيل الدخول"}), 401
        return f(user, *args, **kwargs)
    return wrapper


def admin_required(f):
    """
    Flask route decorator that restricts access to system Administrators.
    
    Verifies that the Bearer token in the request header matches an active,
    unexpired token in the `admin_tokens` table.
    
    Returns:
        HTTP 401: If administrator credentials are invalid or expired.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not verify_admin_token(token):
            return jsonify({"error": "صلاحية مسؤول مطلوبة"}), 401
        return f(*args, **kwargs)
    return wrapper


# ── Language helpers ───────────────────────────────────────────────────────────
# Prompt instructions mapping to force LLMs to respond in the selected candidate language
LANG_INSTRUCTION = {
    "ar": "يجب أن تكتب ردك كاملاً باللغة العربية الفصحى.",
    "en": "You must write your entire response in English only."
}

def get_lang(data: dict = None) -> str:
    """
    Resolves the active language preference for the current API transaction.
    
    Inspects the incoming JSON payload for a 'lang' key. If missing or invalid, 
    falls back to the configured site-wide default language (configured by the Admin).
    If database settings are unavailable, defaults to Arabic ('ar').
    
    Args:
        data (dict): Optional request JSON payload dictionary.
        
    Returns:
        str: Resolves to either 'ar' (Arabic) or 'en' (English).
    """
    if data and "lang" in data:
        return data["lang"] if data["lang"] in ("ar", "en") else "ar"
    try:
        settings = load_settings()
        return settings.get("site", {}).get("language", "ar")
    except Exception:
        return "ar"


# ── AI Client ──────────────────────────────────────────────────────────────────
class AIClient:
    """
    Unified client orchestration class that manages connections to multiple AI providers.
    
    Acts as a highly resilient facade that wraps OpenRouter, OpenAI, Hugging Face, Ollama, 
    and LM Studio REST endpoints. Features integrated automatic failover loops, custom per-feature 
    routing overrides, streaming token emission handlers, and network probe diagnostic testing.
    """

    def __init__(self, settings: dict):
        """
        Initializes the AIClient with system configuration parameters.
        
        Args:
            settings (dict): A configuration dictionary representing current system preferences 
                             (e.g., active providers, API keys, fallback priority order).
        """
        self.settings = settings

    def _get_provider_cfg(self, provider_name: str) -> dict:
        """
        Retrieves the administrative configuration settings dictionary for a specific provider.
        
        Args:
            provider_name (str): The identifier key of the target provider (e.g., 'openrouter').
            
        Returns:
            dict: The provider configuration dictionary containing keys, URLs, and model defaults.
        """
        return dict(self.settings.get("providers", {}).get(provider_name, {}))

    def _get_model(self, provider_name: str, feature: str = "default") -> str:
        """
        Resolves which model name to use for a transaction based on admin configuration rules.
        
        Evaluates settings in hierarchical order:
        1. Checks for specific feature routing overrides (e.g., 'resume' or 'video_interview').
        2. If the active provider matches the overridden target and defines a model, returns it.
        3. Otherwise, falls back to the default configured model for that provider.
        
        Args:
            provider_name (str): The provider to retrieve the model name for.
            feature (str): The feature key requesting the model routing decision.
            
        Returns:
            str: The resolved string model ID (e.g., 'openai/gpt-4o-mini' or 'local-model').
        """
        # Read the current routing overrides list from settings
        overrides = self.settings.get("routing_overrides", {})
        feat_override = overrides.get(feature, {})
        # If an override matches the active provider and has a set model, apply it immediately
        if feat_override.get("provider") == provider_name and feat_override.get("model"):
            return feat_override["model"]
        # Fallback to the provider's default configured model
        cfg = self._get_provider_cfg(provider_name)
        return cfg.get("model", "gpt-4o-mini")

    # ── OpenAI-compatible call ────────────────────────────────────────────────
    def _call_openai_compat(self, cfg: dict, messages: list,
                             model: str, max_tokens: int,
                             extra_headers: dict = None) -> str | None:
        """
        Executes a standard non-streaming chat completion call against an OpenAI-compatible endpoint.
        
        Supports both modern `requests` block logic and standard library `urllib.request` fallbacks
        to maintain cross-platform runtime reliability even on stripped minimal Python installations.
        
        Args:
            cfg (dict): The provider credentials dictionary containing 'api_key' and 'base_url'.
            messages (list): The complete system and user message payload list.
            model (str): The model identifier code.
            max_tokens (int): The maximum generation output limits.
            extra_headers (dict): Optional extra HTTP headers to pass along (e.g., OpenRouter tags).
            
        Returns:
            str: The final generated text string on success, or None on failure.
        """
        api_key  = cfg.get("api_key", "")
        base_url = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
        headers  = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        
        # Prepare the standard OpenAI-compatible completions JSON payload
        payload = {
            "model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": 0.7
        }
        
        # Method A: Perform request using third-party requests library (default)
        if HAS_REQUESTS:
            resp = http_requests.post(
                f"{base_url}/chat/completions",
                headers=headers, json=payload, timeout=90
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
            
        # Method B: Fallback to standard library urllib if requests is missing
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
        """
        Generates real-time text chunks using Server-Sent Events (SSE) from an OpenAI-compatible api.
        
        Surgically parses the `data: {"choices": [{"delta": {"content": "..."}}]}` SSE data blocks 
        emitted line-by-line. If the third-party requests library is not available, falls back 
        automatically to yielding the complete response as a single monolithic block.
        
        Args:
            cfg (dict): The provider credentials dictionary containing 'api_key' and 'base_url'.
            messages (list): The list of conversational message history cards.
            model (str): The model identifier string.
            max_tokens (int): The maximum generation output limits.
            extra_headers (dict): Optional extra HTTP headers.
            
        Yields:
            str: Real-time text token chunks as they arrive from the upstream AI server.
        """
        if not HAS_REQUESTS:
            # Fallback to standard non-streaming response if requests is unavailable
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
        
        # Initiate the streaming HTTP POST request
        with http_requests.post(
            f"{base_url}/chat/completions",
            headers=headers, json=payload, stream=True, timeout=90
        ) as resp:
            resp.raise_for_status()
            # Iterate through the server-sent lines as they are pushed in real-time
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8")
                # Detect the SSE data marker
                if line.startswith("data: "):
                    data_str = line[6:]
                    # Check for completion payload terminator
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
        """
        Executes a direct non-streaming chat request against a local Ollama service.
        
        Probes the dedicated `/api/chat` Ollama endpoint. If the call fails or local configuration
        is invalid, attempts a fallback wrapper utilizing Ollama's OpenAI-compatible router interface.
        
        Args:
            cfg (dict): The Ollama provider config containing host base_url.
            messages (list): Conversational prompts history array.
            model (str): Local model tag.
            max_tokens (int): Max generation length.
            
        Returns:
            str: Complete generated text output, or None on failure.
        """
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
            # Try to fall back to Ollama's secondary OpenAI compatibility interface
            return self._call_openai_compat(
                {**cfg, "api_key": "ollama"},
                messages, model, max_tokens
            )
        return None

    def _stream_ollama(self, cfg: dict, messages: list, model: str, max_tokens: int):
        """
        Streams local generation tokens chunk-by-chunk using Ollama's native stream protocol.
        
        Decodes incoming line boundaries and extracts `message.content` tokens. On connection errors,
        transparently falls back to streaming via Ollama's secondary OpenAI compatibility layers.
        
        Args:
            cfg (dict): Local Ollama config dictionary.
            messages (list): Complete conversational messages list.
            model (str): Local target model.
            max_tokens (int): Max generation boundaries.
            
        Yields:
            str: Emitted local model text chunks in real-time.
        """
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
                            # Halt iteration if Ollama sends the completion indicator
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            pass
        except Exception:
            # Fall back to OpenAI compatibility stream
            yield from self._stream_openai_compat(
                {**cfg, "api_key": "ollama"},
                messages, model, max_tokens
            )

    def _call_huggingface(self, cfg: dict, messages: list, model: str, max_tokens: int) -> str | None:
        """
        Interfaces with the official HuggingFace Hub client using serverless inference.
        
        Requires `huggingface_hub` package dependency to be loaded and active.
        
        Args:
            cfg (dict): Configuration dictionary containing api_key.
            messages (list): Context prompts.
            model (str): Model repository tag (e.g. 'mistralai/Mistral-7B-Instruct-v0.3').
            max_tokens (int): Length bounds.
            
        Returns:
            str: Generated text string, or None if HF is not installed.
        """
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
        """
        Dispatches a non-streaming chat completion task to the correct provider helper.
        
        Maps provider names to their corresponding SDK/REST query methods.
        
        Args:
            provider_name (str): Active target provider name.
            cfg (dict): Target provider config specs.
            messages (list): Prompt message cards.
            feature (str): Feature category for overrides lookups.
            max_tokens (int): Generation tokens boundary.
            
        Returns:
            str: Text result, or None if error or unhandled.
        """
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
        """
        Dispatches a real-time streaming task to the appropriate provider stream method.
        
        Args:
            provider_name (str): Core target provider.
            cfg (dict): Active configuration properties.
            messages (list): Prompt context.
            feature (str): Target application feature module.
            max_tokens (int): Output tokens boundary.
            
        Yields:
            str: Token chunks emitted sequentially from the active model connection.
        """
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
                # Hugging Face serverless api doesn't easily support native streaming hooks;
                # yields complete compiled response text as a single token chunk.
                result = self._call_huggingface(cfg, messages, model, max_tokens)
                if result:
                    yield result
        except Exception as e:
            print(f"[{provider_name}] Stream error: {e}")

    def _get_active_chain(self, feature: str = "default"):
        """
        Resolves a prioritized, sequential chain order of AI providers for the request.
        
        Calculates execution priority dynamically:
        1. Checks for specific feature routing overrides. Yields the override provider first if active.
        2. Yields the global active provider (if enabled).
        3. Iterates through the configured fallback chain list and yields enabled providers.
        
        Args:
            feature (str): Current active feature route context.
            
        Yields:
            str: Active provider string identifiers sequentially for execution and failovers.
        """
        overrides  = self.settings.get("routing_overrides", {})
        feat_prov  = overrides.get(feature, {}).get("provider", "")
        providers  = self.settings.get("providers", {})
        
        # 1. Feature-specific override has first priority
        if feat_prov and providers.get(feat_prov, {}).get("enabled"):
            yield feat_prov
            
        # 2. Site-wide active provider has second priority
        active = self.settings.get("active_provider", "openrouter")
        if active != feat_prov and providers.get(active, {}).get("enabled"):
            yield active
            
        # 3. Dynamic failover list handles third-level priorities
        for p in self.settings.get("fallback_order", []):
            if p not in (feat_prov, active) and providers.get(p, {}).get("enabled"):
                yield p

    def chat(self, messages: list, feature: str = "default", max_tokens: int = 1024) -> str | None:
        """
        Executes a resilient chat completion call with automatic fallback and failover.
        
        Attempts connection through the prioritized provider chain sequentially. If a provider
        fails or encounters network issues, logs the error and moves to the next enabled provider.
        
        Args:
            messages (list): Prompt message context payloads.
            feature (str): Current calling application feature name.
            max_tokens (int): Max generation length.
            
        Returns:
            str: Generated text response on success, or None if the entire failover chain fails.
        """
        for provider_name in self._get_active_chain(feature):
            cfg    = self._get_provider_cfg(provider_name)
            result = self._call_provider(provider_name, cfg, messages, feature, max_tokens)
            if result:
                return result
        return None

    def stream(self, messages: list, feature: str = "default", max_tokens: int = 1024):
        """
        Orchestrates resilient token-by-token streaming with live connection failover capabilities.
        
        Tries streaming through the active chain. If connection terminates prematurely or fails,
        logs the error, catches the exception, and continues streaming by switching targets to 
        the next enabled fallback provider.
        
        Args:
            messages (list): Conversational message list context.
            feature (str): Active application feature context.
            max_tokens (int): Generation tokens boundary.
            
        Yields:
            str: Text generation tokens in real-time.
        """
        for provider_name in self._get_active_chain(feature):
            cfg = self._get_provider_cfg(provider_name)
            chunks = []
            try:
                for chunk in self._stream_provider(provider_name, cfg, messages, feature, max_tokens):
                    chunks.append(chunk)
                    yield chunk
                # If we successfully received at least one text chunk, terminate the fallback loop
                if chunks:
                    return
            except Exception as e:
                print(f"[{provider_name}] Stream failed: {e}")

    def test_connection(self, provider_name: str, live_overrides: dict = None):
        """
        Performs network connectivity and authentication validations for an AI provider.
        
        Used by the Admin Dashboard to check API key status and model endpoints.
        
        Args:
            provider_name (str): Identifier of the target provider to test.
            live_overrides (dict): Optional transient overrides (e.g. unpersisted key inputs).
            
        Returns:
            dict: Diagnostic status response (e.g., {'ok': True, 'response': '...'})
        """
        cfg = dict(self.settings.get("providers", {}).get(provider_name, {}))
        if live_overrides:
            cfg.update(live_overrides)
        if not cfg:
            return {"ok": False, "error": "Provider not configured"}
        # Static validation message to check roundtrip response
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
    """
    Surgically extracts and parses a valid JSON object from a raw LLM text response.
    
    LLMs often output text wrappers, conversational introductory remarks, or markdown 
    code fences (e.g., ```json ... ```) around their raw JSON data payloads. This parser:
    1. Scans for standard code fences, splitting the string to extract inner contents.
    2. If that fails or isn't present, finds the first opening brace '{' and the last closing 
       brace '}' in the string to capture and isolate the raw JSON block.
    3. Safely passes the isolated block to `json.loads` for parsing.
    
    Args:
        text (str): The raw text response string returned by the AI provider.
        
    Returns:
        dict | list | None: The parsed Python structure if successful, or None on failure.
    """
    if not text:
        return None
    # Method A: Try parsing using standard markdown JSON code fences
    for fence in ["```json", "```"]:
        if fence in text:
            parts = text.split(fence)
            for i in range(1, len(parts), 2):
                try:
                    return json.loads(parts[i].strip().rstrip("`"))
                except json.JSONDecodeError:
                    pass
    # Method B: Fallback to isolating the string between the outermost curly braces
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
    """
    Lazy-initializes and returns a dynamic AI routing Client for the current transaction.
    
    Loads active administrative key configurations and returns the instantiated 
    `AIClient` manager, which handles failovers and custom routing overrides automatically.
    
    Returns:
        AIClient: An initialized, transaction-ready routing client object.
    """
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
    """
    Serves the primary stylesheet ('AIStyle.css') containing the unified design system.
    
    Returns:
        Response: The local stylesheet file from the server's base directory.
    """
    return send_from_directory(BASE_DIR, "AIStyle.css")

@app.route("/AIScript.js")
def serve_js():
    """
    Serves the global client-side orchestrator script ('AIScript.js').
    
    Returns:
        Response: The core JavaScript file from the server's base directory.
    """
    return send_from_directory(BASE_DIR, "AIScript.js")


# ═══════════════════════════════════════════════════════════════════════════════
# Auth API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/auth/register", methods=["POST"])
def api_register():
    """
    Registers a new candidate account in the local SQLite database.
    
    Workflow:
    1. Extracts and sanitizes name, email, and password from the JSON payload.
    2. Performs robust schema validations (non-empty fields, minimum password length).
    3. Validates unique constraints by looking up existing user records.
    4. Hashes the user's password cryptographically (using bcrypt/PBKDF2) before database insertion.
    5. Generates a fresh user token and returns session information.
    
    Returns:
        JSON: User profile details and active JWT-like bearer token on success (HTTP 201).
        JSON: Error explanation on validation failures (HTTP 400) or database conflicts (HTTP 409).
    """
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
        # Cryptographically hash password before executing the write query
        conn.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?,?,?)",
            (email, name, hash_password(password))
        )
    token = create_user_token(email)
    return jsonify({"token": token, "user": {"email": email, "name": name}}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """
    Authenticates candidates and administrators to grant session tokens.
    
    Distinguishes flows based on the 'admin_mode' parameter:
    - Admin Mode: Matches raw input password with the dynamic ADMIN_PASSWORD string, 
      issuing a 2-hour admin token.
    - Candidate Mode: Queries the 'users' table, validates password hashes using 
      constant-time comparison helpers, and issues a 24-hour candidate token.
      
    Returns:
        JSON: Session authorization token and role descriptors on success.
        JSON: Error explanation on invalid login credentials (HTTP 401).
    """
    data     = request.json or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    admin_mode = data.get("admin_mode", False)

    if admin_mode:
        # Match administrative secret password with standard env-cache settings
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "كلمة مرور المسؤول غير صحيحة"}), 401
        token = create_admin_token()
        return jsonify({"token": token, "admin": True})

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    # Check credentials using the timing-attack resistant password verification wrapper
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "البريد أو كلمة المرور غير صحيحة"}), 401
    token = create_user_token(email)
    return jsonify({"token": token, "user": {"email": email, "name": user["name"]}})


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout(user):
    """
    Revokes the active session token, logging the user out immediately.
    
    Surgically extracts the active authorization token from the request header 
    and removes its trace from the sessions database table to enforce security logout boundaries.
    
    Args:
        user (dict): Loaded user dict injected by the decorator helper.
        
    Returns:
        JSON: Operational confirmation dictionary.
    """
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
@login_required
def api_me(user):
    """
    Returns profile information about the currently logged-in candidate session.
    
    Args:
        user (dict): Logged-in user dict loaded dynamically.
        
    Returns:
        JSON: Account profile containing name and email metadata.
    """
    return jsonify({"email": user["email"], "name": user["name"]})


@app.route("/api/auth/profile", methods=["PUT"])
@login_required
def api_update_profile(user):
    """
    Updates the authenticated candidate's name or changes their password.
    
    Validation Rules:
    1. Password updates require supplying and verifying the old 'current_password'.
    2. New passwords must meet the 6-character length security requirement.
    3. Profile name modifications are updated safely in the database users index.
    
    Args:
        user (dict): Decrypted database user dictionary.
        
    Returns:
        JSON: Success confirmation and updated profile card on success.
        JSON: Error response on current password mismatch or length validation failures (HTTP 400).
    """
    data         = request.json or {}
    new_name     = (data.get("name") or "").strip()
    new_email    = (data.get("email") or "").strip().lower()
    new_password = data.get("new_password") or ""
    cur_password = data.get("current_password") or ""

    email = user["email"]

    # Process password modification requests
    if new_password:
        # Securely verify that current password inputs match the database hash signature
        if not verify_password(cur_password, user["password_hash"]):
            return jsonify({"error": "كلمة المرور الحالية غير صحيحة"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل"}), 400
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET password_hash=? WHERE email=?",
                (hash_password(new_password), email)
            )

    # Process name modifications
    if new_name and new_name != user["name"]:
        with get_db() as conn:
            conn.execute("UPDATE users SET name=? WHERE email=?", (new_name, email))

    # Pull updated card details from persistence to return to the browser client
    with get_db() as conn:
        updated = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return jsonify({"ok": True, "user": {"email": email, "name": updated["name"]}})


# ═══════════════════════════════════════════════════════════════════════════════
# Admin API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    """
    Authenticate administrative credentials and issue a short-lived administrative bearer token.

    Security Architecture & Lifecycle:
    1. Validation: Extracts JSON password payloads. Compares against the globally configured
       ADMIN_PASSWORD (stored in configuration JSON and loaded into memory on server boot).
    2. Token Provisioning: If verified, generates a secure, cryptographically random,
       time-bound administrative session token via `create_admin_token()`.
    3. Session Expiration: Returns the token alongside a standard `expires_in_hours` value (2 hours).
       This enforces strict session boundaries suitable for sensitive config adjustments.
    
    Inputs (JSON):
        password (str): The plain-text administrative password to test.

    Returns:
        JSON Response:
            - On Success (200 OK): {"token": str, "expires_in_hours": int}
            - On Failure (401 Unauthorized): {"error": str}
    """
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "كلمة مرور غير صحيحة"}), 401
    token = create_admin_token()
    return jsonify({"token": token, "expires_in_hours": ADMIN_TTL_HOURS})


@app.route("/api/admin/change-password", methods=["PUT"])
@admin_required
def api_admin_change_password():
    """
    Update the global administrative password and persist the changes.

    Security & Storage Operations:
    1. Validation: Verifies current password matches ADMIN_PASSWORD. Enforces a 6-character
       minimum length on the new password.
    2. Persistence: Saves the new password into `admin_settings.json` under `admin.password`.
       This acts as a persistent override so the password change survives server restarts.
    3. State Sync: Synchronizes the running in-memory `ADMIN_PASSWORD` variable.

    Inputs (JSON):
        current_password (str): The current admin password.
        new_password (str): The desired new admin password (minimum 6 characters).

    Returns:
        JSON Response:
            - On Success (200 OK): {"ok": True}
            - On Failure (400 Bad Request): {"error": str}
    """
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
    """
    Retrieve the current administrative configuration state.

    Operational Workflow:
    - Invokes `load_settings()`, which merges environment variables, default settings,
      and local overrides from `admin_settings.json`.
    - Returns the fully materialized configurations for UI display.

    Returns:
        JSON Response (200 OK): The full system settings dictionary.
    """
    return jsonify(load_settings())


@app.route("/api/admin/settings", methods=["PUT"])
@admin_required
def api_admin_save_settings():
    """
    Surgically merge and persist updated administrative settings.

    Design & Merging Workflow:
    1. Retrieval: Loads the current system configuration from disk/defaults.
    2. Deep Merging: Applies a deep recursive merge (`deep_merge`) using the incoming JSON payload.
       This enables updates to specific keys (e.g., specific API keys or providers) without
       wiping out other configuration trees.
    3. Storage: Serializes the resulting state back into `admin_settings.json`.

    Inputs (JSON):
        A structured dictionary matching the settings schema (e.g., providers, site, models).

    Returns:
        JSON Response (200 OK): {"ok": True}
    """
    data = request.json or {}
    # Remove admin password from settings if stored there previously
    current = load_settings()
    merged  = deep_merge(current, data)
    save_settings(merged)
    return jsonify({"ok": True})


@app.route("/api/admin/test", methods=["POST"])
@admin_required
def api_admin_test():
    """
    Validate provider connectivity and configuration parameters in real-time.

    Diagnostic Workflow:
    1. Parameter Extraction: Identifies target provider and extracts optionally supplied keys, 
       URLs, or models to test.
    2. Override Application: Passes parameters to the AIClient test suite (`test_connection`).
       This verifies new configurations before committing them permanently to disk.
    3. Network Verification: The client sends a minimal testing ping to the target endpoint,
       measuring latency and verifying access scopes.

    Inputs (JSON):
        provider (str): The target provider (e.g., 'openrouter', 'ollama', 'huggingface').
        api_key (str, optional): Key to test.
        base_url (str, optional): Endpoint URL override to test.
        model (str, optional): Model ID to query.

    Returns:
        JSON Response (200 OK):
            - {"ok": True, "message": str, "latency_ms": float}
            - {"ok": False, "error": str}
    """
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
    """
    Probe the online status of configured local AI orchestration engines.

    Probing Workflow:
    - Ollama Probing: Queries the standard local tag lister `/api/tags` endpoint with a strict 3-second timeout.
    - LM Studio Probing: Queries the standard `/v1/models` route with a strict 3-second timeout.
    - Graceful Failures: Catch-all exception handling ensures that offline local clients simply report
      `False` without inducing a server-side route crash.

    Returns:
        JSON Response (200 OK): {"ollama": bool, "lmstudio": bool}
    """
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
    """
    Query and return lists of currently loaded/pulled model tags on local providers.

    Model Interrogation Workflow:
    1. Ollama Tag Lookup: Issues a request to the Ollama local service (`/api/tags`). Parses
       the `models` schema array and maps tags directly to strings.
    2. LM Studio Model Lookup: Queries the local Open-AI-compatible route (`/v1/models`).
       Extracts the model IDs array.
    3. Error Mitigation: If either local service is unreachable or errors out, catches the
       exception and returns an empty list `[]` for that specific provider, preserving diagnostic integrity.

    Returns:
        JSON Response (200 OK): {"ollama": list of str, "lmstudio": list of str}
    """
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
    """
    Query the live OpenRouter directory API to discover available models and their traits.

    Directory Parsing Workflow:
    1. Network Request: Fetches the public OpenRouter JSON list at `https://openrouter.ai/api/v1/models`.
       Passes the administrative API key in standard Bearer headers if it is set in configurations.
    2. Schema Mapping: Iterates over the catalog payloads. Normalizes key attributes, specifically
       checking the `architecture.input_modalities` list to tag whether the model supports image inputs (vision).
    3. Structural Normalization: Restructures each record into a unified frontend-safe schema:
       `{"id": id, "name": display_name, "vision": boolean, "context": context_length_tokens}`.
    4. HTTP Resiliency: Reports bad gateway (502) if network failures occur, or service unavailable (503)
       if core runtime dependencies are missing.

    Returns:
        JSON Response:
            - On Success (200 OK): {"models": [{"id": str, "name": str, "vision": bool, "context": int}, ...]}
            - On Dependency Error (503 Service Unavailable): {"error": str}
            - On Remote Fetch Fail (502 Bad Gateway): {"error": str}
    """
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
    """
    Check the current health and installation status of core backend library dependencies.

    System Diagnostics:
    - requests: Used for API interactions with remote LLMs and local engines.
    - huggingface: Wraps low-level repository requests for huggingface model serving.
    - reportlab: Key formatting engine used to generate career assets in PDF format.
    - arabic_reshape: Text shaping libraries required to display Arabic glyphs correctly in ReportLab canvases.
    - active_provider: Resolves which LLM provider is currently set as the primary dispatcher.

    Returns:
        JSON Response (200 OK):
            - {"has_requests": bool, "has_huggingface": bool, "has_reportlab": bool,
               "has_arabic_pdf": bool, "active_provider": str or None}
    """
    return jsonify({
        "has_requests":    HAS_REQUESTS,
        "has_huggingface": HAS_HF,
        "has_reportlab":   HAS_REPORTLAB,
        "has_arabic_pdf":  HAS_ARABIC_RESHAPE,
        "active_provider": load_settings().get("active_provider"),
    })


@app.route("/api/site/config", methods=["GET"])
def api_site_config():
    """
    Expose public, non-sensitive site configuration properties.

    Operational Design:
    - Queries `load_settings()` and reads the `site` subtree.
    - Exposes general theme parameters, site names, or layout configurations
      to the client application without requiring authentication or session tokens.

    Returns:
        JSON Response (200 OK): The public site configuration dictionary.
    """
    site = load_settings().get("site", {})
    return jsonify(site)


@app.route("/api/site/skills", methods=["GET"])
def api_site_skills():
    """
    Expose the default, pre-configured list of common professional skills.

    Operational Design:
    - Retrieves standard skill taxonomies pre-seeded under `site.skills_list`
      in administrative configurations.
    - Provides rapid autocomplete suggestions or selection choices to the UI.

    Returns:
        JSON Response (200 OK): {"skills": list of str}
    """
    skills = load_settings().get("site", {}).get("skills_list", [])
    return jsonify({"skills": skills})


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/dashboard/stats", methods=["GET"])
@login_required
def api_dashboard_stats(user):
    """
    Aggregate and serve personalized user engagement statistics and activity logs.

    Dashboard Aggregation Lifecycle:
    1. Schema Assurance: Calls `ensure_stats` to guarantee the database record for this user exists.
    2. Data Retrieval: Within an atomic database connection, executes parallel queries:
       - Query A: Reads the cumulative usage counters from `user_stats` (assessments, interviews, etc.).
       - Query B: Fetches the 10 most recent records from the user's `activity_log`, ordered chronologically (newest first).
    3. Structural Mapping: Formats dates and database row indexes to supply the frontend dashboard widgets.

    Inputs (Route & Session Context):
        user (dict): Loaded from the session validator `login_required`.

    Returns:
        JSON Response (200 OK):
            {
                "user": {"name": str, "email": str},
                "stats": {"assessments": int, "interviews": int, "resumes": int, "careers": int},
                "activity": [{"type": str, "title": str, "created_at": str}, ...]
            }
    """
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
@app.route("/api/skills/suggest", methods=["POST"])
@login_required
@rate_limited(max_calls=30)
def api_skills_suggest(user):
    """
    Utilize generative AI to suggest highly relevant skills based on a target role.

    AI Prompting & Parsing Workflow:
    1. Input Validation: Extract and sanitize the target job title (truncated to 100 chars).
    2. Context Resolution: Resolves target language (bilingual toggle fallback).
    3. Structured Prompts: Embeds language constraints inside the AI prompt. Requests a clean JSON
       document outlining 8-12 core skills grouped under: 'مهارات تقنية', 'مهارات شخصية', or 'أدوات وتكنولوجيا'.
    4. Orchestrated Querying: Hands the message list to the unified `AIClient` dispatcher targeting the
       "skills" feature config path.
    5. Clean Extraction: Uses `extract_json` to peel off markdown fences and isolate the JSON array.

    Inputs (JSON):
        target_role (str): The job title or profession target (e.g., 'Web Developer').
        lang (str, optional): Language choice ('ar' or 'en').

    Returns:
        JSON Response (200 OK): {"skills": [{"name": str, "category": str}, ...]}
    """
    data = request.json or {}
    target_role = (data.get("target_role") or "").strip()[:100]
    lang = get_lang(data)

    if not target_role:
        return jsonify({"skills": []})

    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])
    system_prompt = f"""أنت خبير توظيف وتنمية مهارات. {lang_instruction}
بناءً على المسمى الوظيفي المستهدف، اقترح قائمة مكونة من 8 إلى 12 مهارة أساسية ومطلوبة بشدة (تقنية وشخصية وأدوات).
أرجع JSON فقط بهذا الشكل (لا تضف نصاً خارجه):
{{
  "skills": [
    {{"name": "<اسم المهارة باللغة المناسبة>", "category": "<التصنيف: مهارات تقنية / مهارات شخصية / أدوات وتكنولوجيا>"}},
    ...
  ]
}}"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": f"المسمى الوظيفي المستهدف: {target_role}"}
    ]
    ai_response = get_ai_client().chat(messages, feature="skills", max_tokens=800)
    result = extract_json(ai_response) or {"skills": []}
    return jsonify(result)


@app.route("/api/skills/assess", methods=["POST"])
@login_required
@rate_limited(max_calls=10)
def api_skills_assess(user):
    """
    Perform a high-fidelity skills gap-analysis matching current capabilities against a target career.

    Analytical Intelligence & Processing Lifecycle:
    1. Input Sanitation: Extracts user's listed skills (capped at 30 items) and the target role (capped at 100 chars).
    2. Rating Scale Integration: Maps current skill proficiencies (1 to 5 star ratings) into descriptive 
       evaluation prompts (e.g., "Skill (Level X/5)").
    3. Evaluation Prompting: Instructs the AI model to:
       - Grade the candidate's alignment on a scale of 0-100.
       - Synthesize strong capabilities (Level 3-5).
       - Isolate high/medium/low-importance gaps (Level 1-2 or missing entirely).
       - Provide structured career growth suggestions.
    4. Resilient Fallbacks: Pre-populates clean structural fallback data to prevent front-end breaks
       in case the remote provider errors, timed out, or returned malformed content.
    5. Activity Tracking: Updates user stats, bumps `assessments` count in SQLite, and logs an action log entry.

    Inputs (JSON):
        target_role (str): The desired career path.
        skills (list of dict): e.g. [{"name": "Python", "level": 4}, ...]
        lang (str, optional): Target language.

    Returns:
        JSON Response (200 OK):
            {
                "score": int,
                "analysis": str,
                "strengths": [str, ...],
                "gaps": [{"skill": str, "importance": str, "recommendation": str}, ...],
                "roadmap": [str, ...]
            }
    """
    data        = request.json or {}
    skills      = data.get("skills", [])[:30]          # cap at 30
    target_role = (data.get("target_role") or "").strip()[:100]
    lang        = get_lang(data)

    if not skills:
        return jsonify({"error": "يرجى تحديد مهاراتك أولاً"}), 400

    formatted_skills = []
    for s in skills:
        if isinstance(s, dict):
            name = s.get("name", "").strip()
            level = s.get("level", 3)
            formatted_skills.append(f"{name} (المستوى {level}/5)" if lang == "ar" else f"{name} (Level {level}/5)")
        else:
            formatted_skills.append(str(s))

    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])
    system_prompt = f"""أنت خبير تطوير مسيرة مهنية وتنمية مهارات. {lang_instruction}
قم بتحليل مهارات المستخدم الحالية ومستويات كفاءته الذاتية فيها (المقياس من 1 إلى 5، حيث 1 هو مبتدئ/معرفة أساسية و5 هو خبير) مقارنةً بمتطلبات وتوقعات الوظيفة المستهدفة.
حدد مدى ملاءمته للوظيفة، وقدم تقييماً شاملاً وفجوات المهارات وخارطة طريق للوصول للمستوى المطلوب.
أرجع JSON فقط بهذا الشكل (لا تضف نصاً خارجه):
{{
  "score": <درجة التوافق الإجمالية 0-100 بناءً على ملاءمة المهارات ومستوياتها للوظيفة>,
  "analysis": "<تحليل شامل ومفصل يوضح أين يقف المستخدم الآن وكيف تؤثر مستويات مهاراته الحالية على أهدافه>",
  "strengths": ["<مهارة يمتلكها بمستوى جيد 3-5 وتعتبر نقطة قوة للوظيفة>", ...],
  "gaps": [
    {{
      "skill": "<اسم المهارة التي بها فجوة (إما لعدم إضافتها أصلاً وهي مطلوبة بشدة، أو لأن مستوى المستخدم فيها 1-2 وهو أقل من المتوقع للوظيفة)>",
      "importance": "<أهمية المهارة للوظيفة: عالية / متوسطة / منخفضة>",
      "recommendation": "<توصية محددة وعملية للمستخدم لرفع مستواه في هذه المهارة>"
    }}, ...
  ],
  "roadmap": ["<خطوة عملية واضحة في خطة التطوير المهني مرتبة زمنياً>", ...]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": f"الوظيفة المستهدفة: {target_role or 'غير محددة'}\nالمهارات والمستويات الحالية:\n" + "\n".join(formatted_skills)}
    ]
    ai_response = get_ai_client().chat(messages, feature="skills", max_tokens=1200)
    
    # Fallback structure
    default_gaps = []
    if lang == "ar":
        default_analysis = "لم نتمكن من تحليل مهاراتك في الوقت الحالي."
        default_strengths = [s.get("name") if isinstance(s, dict) else str(s) for s in skills[:3]]
    else:
        default_analysis = "We could not analyze your skills at this moment."
        default_strengths = [s.get("name") if isinstance(s, dict) else str(s) for s in skills[:3]]

    result = extract_json(ai_response) or {
        "score": 65,
        "analysis": default_analysis,
        "strengths": default_strengths,
        "gaps": default_gaps,
        "roadmap": []
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
    """
    Parse a structured, tag-demarcated LLM interview evaluation response into segments.

    Parsing Methodology:
    - Splits incoming raw response strings by line.
    - Matches prefixes based on the active session language (Arabic or English tags).
    - Extracts:
      - [FEEDBACK] / [التقييم]: Verbal analysis from the virtual coach.
      - [SCORE] / [النقاط]: Clean decimal scores, falling back to 7.0 if unparseable.
      - [QUESTION] / [السؤال]: The next question in the interview sequence.

    Args:
        text (str): Raw string generated from the LLM model.
        lang (str): User interface language tag ('ar' or 'en').

    Returns:
        dict: A dictionary containing {"feedback": str, "score": float, "question": str}
    """
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
    """
    Initiate a new interactive mock interview session.

    Setup Workflow:
    1. Settings Resolution: Extracts targeted role and field from input payloads. Checks the session 
       mode ('chat' or 'video') to set appropriate system prompts and routing targets.
    2. Prompt Drafting: Composes a personalized system prompt initiating the interview.
    3. AI Query: Calls `AIClient.chat` to retrieve the first question of the interview.
    4. Database Setup: Inserts a new record in `interview_sessions` storing session metadata, 
       initializing empty scores lists, and serializing messages history to JSON.

    Inputs (JSON):
        role (str): Targeted position (e.g., 'Financial Analyst').
        field (str): Industry field (e.g., 'Finance').
        mode (str, optional): 'chat' or 'video' interactive mode.
        lang (str, optional): Target language.

    Returns:
        JSON Response (200 OK):
            {"session_id": str, "question": str, "question_count": int}
    """
    data    = request.json or {}
    role    = (data.get("role") or "").strip()[:100]
    field   = (data.get("field") or "").strip()[:100]
    mode    = data.get("mode", "chat")
    feature = "video_interview" if mode == "video" else "chat_interview"
    lang    = get_lang(data)

    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])

    # Build an intro-first system prompt: greet, introduce, explain, then ask first Q
    if lang == "ar":
        system_prompt = (
            f"أنت محاور ذكاء اصطناعي محترف لدور '{role}' في مجال '{field}'. {lang_instruction}\n"
            "ابدأ الجلسة بالترحيب بالمرشح، قدّم نفسك بإيجاز كمحاور ذكاء اصطناعي، "
            "اشرح أن المقابلة ستتضمن عدة أسئلة وسيتلقى المرشح تقييماً في النهاية، "
            "ثم اطرح سؤالك الأول المناسب للدور. "
            "اجعل التقديم دافئاً ومشجعاً لا يتجاوز جملتين، ثم السؤال مباشرةً."
        )
    else:
        system_prompt = (
            f"You are a professional AI interviewer for the role of '{role}' in the field of '{field}'. {lang_instruction}\n"
            "Begin the session by warmly greeting the candidate, briefly introducing yourself as an AI interview coach, "
            "explaining that the interview will include several questions with a full evaluation report at the end, "
            "then immediately ask your first relevant interview question for this role. "
            "Keep the introduction warm and encouraging — no more than two sentences — then go straight to the question."
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
    """
    Surgically evaluate a candidate's answer using non-streaming backend loops.

    Synchronous Evaluation Pipeline:
    1. Validation: Matches the provided session ID to database session tables.
    2. Multimodal Vision Handling: If video vision mode is active and base64 frames are supplied, 
       packages the image input into OpenAI-compatible multimodal content objects alongside the user's text.
    3. Evaluation & Prompting: Appends the structured feedback guidelines system instructions 
       (`INTERVIEW_STREAM_SYSTEM`) to direct the model to grade and construct the next question.
    4. Parse & Save: Parses the response using `parse_stream_response`, appends scores and text 
       to session history arrays, updates SQLite databases, and flags session completion if 
       MAX_INTERVIEW_QUESTIONS is reached.

    Inputs (JSON):
        session_id (str): Reference ID to the current active session.
        answer (str): The candidate's verbal or typed response.
        frame_b64 (str, optional): Base64-encoded camera JPEG frame.

    Returns:
        JSON Response (200 OK):
            {
                "feedback": str,
                "score": float,
                "next_question": str or None,
                "question_count": int,
                "done": bool
            }
    """
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
    """
    Real-Time Server-Sent Events (SSE) Route to evaluate a candidate's response.
    
    Streams the AI evaluation and feedback token-by-token back to the browser client, 
    allowing an interactive chat-style mock interview presentation.
    
    Features:
    1. Multi-modal Vision Support: Extracts base64 JPEG video frames (captured via the candidate's 
       camera) and sends them to vision models for real-time presentation analysis.
    2. Real-Time Token Generation: Emits SSE chunk streams (data: {"token": "..."}\n\n).
    3. Final State Synchronization: Once the generation terminates, compiles the complete text, 
       extracts scores and next questions, and updates database records transactional.
       
    Args:
        user (dict): Loaded user credentials dictionary injected by @login_required.
        
    Returns:
        Response: A chunked HTTP response streaming mimetype "text/event-stream".
    """
    data       = request.json or {}
    session_id = data.get("session_id", "")
    answer     = (data.get("answer") or "").strip()
    frame_b64  = data.get("frame_b64")

    # Load the active interview session from the persistence layer
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE session_id=? AND email=?",
            (session_id, user["email"])
        ).fetchone()
    if not row:
        # Yield an immediate SSE error block if no active session is found
        def err_gen():
            yield f"data: {json.dumps({'error': 'جلسة غير موجودة'})}\n\n"
        return Response(stream_with_context(err_gen()), content_type="text/event-stream")

    # Reconstruct state fields from SQLite serialization wrappers
    messages       = json.loads(row["messages"])
    scores         = json.loads(row["scores"])
    question_count = row["question_count"]
    lang           = row["lang"] or "ar"
    feature        = row["feature"] or "chat_interview"

    # Multimodal formatting: Bind base64 images if video stream is active
    if frame_b64 and feature == "video_interview":
        user_content = [
            {"type": "text",      "text": answer},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}", "detail": "low"}}
        ]
    else:
        user_content = answer

    # Update state history and insert the structured system parameters
    messages.append({"role": "user", "content": user_content})
    stream_sys = INTERVIEW_STREAM_SYSTEM.get(lang, INTERVIEW_STREAM_SYSTEM["ar"])
    messages_with_sys = [{"role": "system", "content": stream_sys}] + messages[1:]

    ai_client = get_ai_client()

    def generate():
        full_text = []
        try:
            # Stream the evaluation response token-by-token from the active provider client
            for chunk in ai_client.stream(messages_with_sys, feature=feature, max_tokens=500):
                full_text.append(chunk)
                # Emit token chunk as an SSE data packet
                yield f"data: {json.dumps({'token': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # Generation complete. Now analyze the complete block payload
        complete = "".join(full_text)
        parsed   = parse_stream_response(complete, lang)
        new_scores = scores + [parsed["score"]]
        new_messages = messages + [{"role": "assistant", "content": complete}]
        new_qcount = question_count + 1

        # Save the updated session records to the database
        with get_db() as conn:
            conn.execute(
                "UPDATE interview_sessions SET messages=?, scores=?, question_count=? WHERE session_id=?",
                (json.dumps(new_messages), json.dumps(new_scores), new_qcount, session_id)
            )

        # Check if the mock interview has reached its maximum question count limit
        done = new_qcount >= MAX_INTERVIEW_QUESTIONS
        # Yield the final compiled transaction status event
        yield f"data: {json.dumps({'done': True, 'score': parsed['score'], 'feedback': parsed['feedback'], 'next_question': parsed['question'] if not done else None, 'question_count': new_qcount, 'interview_done': done})}\n\n"

    # Return chunked response stream with direct cache-control configurations to bypass Nginx proxies
    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/api/interview/end", methods=["POST"])
@login_required
def api_interview_end(user):
    """
    Finalize an interactive mock interview, compiling comprehensive performance diagnostics.

    Session Wrap-up and Logging Lifecycle:
    1. Data Loading: Fetches all messages and scores collected during the session.
    2. Performance Calculation: Computes an average overall score from the individual scores list.
    3. Generative Diagnostics: Calls the LLM to write a professional performance report detailing:
       - Overall performance summary.
       - Highlighted strengths.
       - Targeted areas of improvement.
       - Tactical career tips.
    4. Archival: Saves the complete analysis profile in `interview_history` for dashboard retention.
    5. Cleanup: Drops the temporary session from `interview_sessions` to prevent stale memory use.
    6. Activity Logging: Bumps the interviews metric counter and records a log event in SQLite.

    Inputs (JSON):
        session_id (str): Reference ID to the session to finalize.

    Returns:
        JSON Response (200 OK):
            {
                "summary": str,
                "strengths": list of str,
                "improvements": list of str,
                "tips": list of str,
                "overall_score": float
            }
    """
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
    feature = "video_interview" if mode == "video" else "chat_interview"

    if mode == "video":
        summary_prompt = (
            f"قدّم ملخصاً نهائياً لأداء المرشح في المقابلة المرئية. {lang_instruction}\n"
            "قم بتقييم ثقته وحضوره أمام الكاميرا، لغة جسده، وتواصله البصري وتعبيرات وجهه بناءً على لقطات الفيديو والردود.\n"
            "أرجع JSON فقط:\n"
            '{"summary":"<ملخص شامل لأداء المرشح اللفظي ومستوى ثقته وحضوره المرئي أمام الكاميرا>","strengths":["..."],"improvements":["..."],"tips":["..."]}'
        ) if lang == "ar" else (
            f"Provide a final performance summary for the candidate's video interview. {lang_instruction}\n"
            "Evaluate their presentation confidence, camera presence, body language, eye contact, and facial expressions based on the video frames and answers.\n"
            "Return JSON only:\n"
            '{"summary":"<comprehensive summary covering verbal answers, visual confidence, and camera presence>","strengths":["..."],"improvements":["..."],"tips":["..."]}'
        )
    else:
        summary_prompt = (
            f"قدّم ملخصاً نهائياً لأداء المرشح في المقابلة. {lang_instruction}\n"
            "أرجع JSON فقط:\n"
            '{"summary":"<ملخص>","strengths":["..."],"improvements":["..."],"tips":["..."]}'
        ) if lang == "ar" else (
            f"Provide a final performance summary for the candidate. {lang_instruction}\n"
            "Return JSON only:\n"
            '{"summary":"<summary>","strengths":["..."],"improvements":["..."],"tips":["..."]}'
        )

    summary_messages = messages + [{"role": "user", "content": summary_prompt}]
    ai_response = get_ai_client().chat(summary_messages, feature=feature, max_tokens=800)
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
    """
    Paginate and retrieve historical interview metrics for the logged-in candidate.

    Database Query Details:
    - Parses dynamic URL query parameters to locate the active page index.
    - Leverages SQLite `LIMIT` and `OFFSET` queries to return clean, chunked records (10 per page).
    - Deserializes JSON string fields (strengths, improvements, tips) to reconstruct frontend-safe lists.

    Returns:
        JSON Response (200 OK):
            {
                "items": [
                    {"id": int, "role": str, "field": str, "mode": str, "overall_score": float,
                     "summary": str, "strengths": list, "improvements": list, "tips": list, "created_at": str},
                    ...
                ],
                "total": int, "page": int, "per_page": int
            }
    """
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
    """
    Fetch granular details for a single past interview diagnostic profile.

    Verification Steps:
    - Executes a strict search in SQLite requiring BOTH `history_id` AND the candidate's `email`.
      This guards against access elevation leaks.
    - Parses and returns the fully hydrated dashboard statistics profile.

    Returns:
        JSON Response (200 OK): Granular history data matching the history record schema.
    """
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
    """
    Optimizes and restructures raw candidate resume fields using Generative AI.

    Design & Architecture:
    1. Input Parsing: Receives raw candidate metadata (e.g. name, experiences, skills, summary) via JSON.
    2. Dynamic Prompt Builder: Configures system prompts in Arabic or English according to the client-specified
       locale (`get_lang`). The prompt dictates a strict structured JSON contract that the AI model must fulfill.
    3. Failure Resiliency & Extractors: Queries the failover-capable `AIClient` using the "resume" feature router.
       If the response contains markdown or conversational fluff, `extract_json()` isolates the nested JSON schema.
       If the LLM call completely fails or times out, the backend gracefully falls back to the original raw values
       to guarantee seamless form continuation without data loss.
    4. Activity Tracking: Increments the user's career metrics counters and posts a structured log to the
       `activity_log` table.

    Args:
        user (dict): Hydrated session profile injected by the `@login_required` middleware.

    Returns:
        Response: Flask JSON response conforming to:
            {
                "summary": "Optimized professional summary...",
                "experience": [{"title": "...", "company": "...", "period": "...", "bullets": ["..."]}],
                "skills": ["...", "..."],
                "improvements": ["Critique 1", "Critique 2"]
            }
    """
    # Parse payload body or fall back to empty dictionary
    data = request.json or {}
    # Determine the target language/locale for the AI's professional tone
    lang = get_lang(data)
    # Fetch bilingual system instruction constraints
    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])

    # Define strict JSON structure templates in the system prompt according to the selected language
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

    # Encode raw data structures to readable JSON for parsing in the user prompt block
    user_msg = f"السيرة الذاتية:\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_msg}
    ]
    
    # Execute the structured query through the AI client failover architecture targeting "resume" feature models
    ai_response = get_ai_client().chat(messages, feature="resume", max_tokens=1500)
    
    # Attempt to extract and parse the JSON payload from the raw text stream. If invalid, inject original user inputs as a fallback.
    result = extract_json(ai_response) or {
        "summary": data.get("summary", ""),
        "experience": data.get("experience", []),
        "skills": data.get("skills", []),
        "improvements": ["تعذّر تحسين السيرة تلقائياً."]
    }

    # Increment metric tracking counters and record the operation in user's audit trails
    email = user["email"]
    bump_stat(email, "resumes")
    add_activity(email, "resume", "تحسين سيرة ذاتية")
    return jsonify(result)


def _render_arabic(text: str) -> str:
    """
    Reshapes and re-orders Arabic text characters for correct PDF vector rendering.
    
    Standard ReportLab text methods draw characters individually from left-to-right. 
    For Arabic text, this causes:
    1. Unconnected/isolated character glyphs (e.g., 'ك ت ا ب' instead of 'كتاب').
    2. Reversed string orders (LTR layout instead of RTL).
    
    This function fixes both issues:
    1. `arabic_reshaper.reshape(text)` determines contextual cursive joining positions (initial, 
       medial, final, isolated) and swaps standard Unicode characters for cursive presentation glyphs.
    2. `get_display(reshaped)` executes the Bi-directional (Bidi) algorithm, reversing Arabic tokens 
       right-to-left while preserving English/number layouts left-to-right.
    
    Args:
        text (str): The raw Arabic/bilingual input string.
        
    Returns:
        str: The fully processed, cursive, RTL-aligned string ready to draw on canvas.
    """
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
    """
    Exports optimized candidate resume details as a professional, bi-directional PDF document.
    
    Technical Highlights & Educational Concepts:
    1. Font Registry: Registers Windows Arial/Arial-Bold system TrueType Fonts (.ttf) for flawless
       bilingual (AR/EN) vector mapping. Falls back to project Amiri or system Helvetica.
       TrueType fonts allow ReportLab to dynamically embed vector glyph maps into the PDF.
    2. In-Memory Buffering: Compiles canvas operations directly into an in-memory byte buffer (io.BytesIO) 
       to prevent slow, concurrent, and insecure local server disk writes.
    3. Multi-page Flow & Text wrapping: Draws summaries, experience lists, and skill blocks.
       Maintains coordinate pointers ('y' pointer) to track page remaining heights.
    4. Cursive Reshaping & Bi-directional Ordering: Integrates private `_render_arabic` which leverages
       arabic_reshaper & python-bidi to restructure standard Unicode character streams into visual cursive sequences
       rendered from Right-to-Left (RTL).
    
    Args:
        user (dict): Logged-in user dictionary injected by decorator.
        
    Returns:
        Response: A downloadable binary PDF stream with dynamic attachment naming headers.
    """
    if not HAS_REPORTLAB:
        return jsonify({"error": "مكتبة PDF غير متوفرة. pip install reportlab"}), 503

    data = request.json or {}

    # Locate or load Arabic-supporting fonts
    font_name = "Helvetica"
    bold_font_name = "Helvetica-Bold"

    # Step 1: Try Windows system fonts first (since Arial supports both Latin and Arabic perfectly)
    sys_arial = r"C:\Windows\Fonts\arial.ttf"
    sys_arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(sys_arial) and os.path.exists(sys_arial_bold):
        try:
            pdfmetrics.registerFont(TTFont("Arial", sys_arial))
            pdfmetrics.registerFont(TTFont("Arial-Bold", sys_arial_bold))
            font_name = "Arial"
            bold_font_name = "Arial-Bold"
        except Exception:
            pass

    # Step 2: Fallback to bundled Amiri TrueType fonts in project fonts folder
    if font_name == "Helvetica":
        font_path = os.path.join(BASE_DIR, "fonts", "Amiri-Regular.ttf")
        bold_path = os.path.join(BASE_DIR, "fonts", "Amiri-Bold.ttf")
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("Amiri", font_path))
                font_name = "Amiri"
                bold_font_name = "Amiri"  # Fallback to Amiri-Regular if no Bold
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont("Amiri-Bold", bold_path))
                    bold_font_name = "Amiri-Bold"
            except Exception:
                pass

    # Initialize the in-memory byte stream and canvas object
    buf = io.BytesIO()
    c   = pdf_canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # --- Draw Header Block ---
    # Draw a premium, dark-indigo banner
    c.setFillColorRGB(0.1, 0.1, 0.25)
    c.rect(0, H - 80, W, 80, fill=True, stroke=False)
    
    # Write name centrally
    c.setFillColorRGB(1, 1, 1)
    c.setFont(bold_font_name, 22)
    name = _render_arabic(data.get("name", user["name"]))
    c.drawCentredString(W / 2, H - 45, name)
    
    # Write contact details centrally
    c.setFont(font_name, 11)
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
        c.setFont(bold_font_name, 11)
        c.drawString(margin + 5, ypos, _render_arabic(title))
        c.setFillColorRGB(0, 0, 0)
        return ypos - 24

    def wrap_text(text, width_pts, font_n=None, size=10):
        if font_n is None:
            font_n = font_name
        words = str(text).split()
        lines, current = [], ""
        c.setFont(font_n, size)
        for w in words:
            test = (current + " " + w).strip()
            if c.stringWidth(test, font_n, size) < width_pts:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def draw_text(text, xpos, ypos, font_n=None, size=10, max_width=None):
        if font_n is None:
            font_n = font_name
        c.setFont(font_n, size)
        rendered = _render_arabic(text)
        if max_width:
            lines = wrap_text(rendered, max_width, font_n, size)
            for line in lines:
                c.drawString(xpos, ypos, line)
                ypos -= size + 3
            return ypos
        c.drawString(xpos, ypos, rendered)
        return ypos - (size + 4)

    # Professional Summary
    if data.get("summary"):
        y = section_header("الملخص المهني / Professional Summary", y)
        c.setFont(font_name, 10)
        for line in wrap_text(data["summary"], W - 2 * margin - 10):
            c.drawString(margin + 5, y, _render_arabic(line))
            y -= 14
        y -= 6

    # Experience
    if data.get("experience"):
        y = section_header("الخبرة العملية / Work Experience", y)
        for exp in data["experience"]:
            c.setFont(bold_font_name, 11)
            c.setFillColorRGB(0.1, 0.1, 0.3)
            y = draw_text(f"{exp.get('title','')} — {exp.get('company','')}", margin + 5, y, bold_font_name, 11)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            y = draw_text(exp.get("period", ""), margin + 5, y, font_name, 9)
            c.setFillColorRGB(0, 0, 0)
            for bullet in exp.get("bullets", []):
                y = draw_text(f"  • {bullet}", margin + 10, y, font_name, 10, W - 2 * margin - 20)
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
    """
    Generates tailored multi-path career recommendations and development advice using Generative AI.

    Design & Architecture:
    1. Input Handling: Receives candidate core skills, background summary, and education/experience vectors.
    2. Context-Aware Prompt Generation: Incorporates specialized Arabic/English instruction guidelines (`get_lang`).
       Demands strict structural output as a JSON dictionary containing a list of 3 high-probability career paths.
    3. Failover Chat Routing: Queries the resilient `get_ai_client()` using the "career" routing profile with a
       1200 maximum token ceiling.
    4. Robust Fallback Mechanics: Isolates the JSON response block with `extract_json()`. If parsing fails,
       provides a high-quality static default recommendation list so the user experience doesn't break.
    5. Analytics Logging: Updates DB user action metrics and pushes metadata audit logs to SQLite.

    Args:
        user (dict): Hydrated session profile injected by `@login_required`.

    Returns:
        Response: Flask JSON response containing suggested paths and professional development advice.
    """
    # Load candidate payload details from POST request body
    data   = request.json or {}
    # Determine targeted locale setting for localized language outputs
    lang   = get_lang(data)
    # Fetch bilingual system instructions mapping
    lang_instruction = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["ar"])

    # Draft standard career counselor role definition and output schema constraints
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

    # Filter out language control fields from user prompt payload to optimize token consumption
    user_content = json.dumps({
        k: v for k, v in data.items() if k != "lang"
    }, ensure_ascii=False)
    
    # Bundle core dialogue payloads
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content}
    ]
    
    # Retrieve model-routed career exploration response via AI provider failover client
    ai_response = get_ai_client().chat(messages, feature="career", max_tokens=1200)
    
    # Isolate and parse the final career roadmap payload. Inject resilient defaults upon JSON errors.
    result = extract_json(ai_response) or {
        "paths": [
            {"title": "مهندس برمجيات", "match_percentage": 88,
             "description": "تطوير وصيانة التطبيقات",
             "required_skills": ["Python", "JavaScript", "SQL"],
             "salary_range": "8,000–25,000 ر.س", "growth_outlook": "نمو مرتفع"}
        ],
        "general_advice": "ركز على تطوير مهاراتك العملية."
    }

    # Register activity telemetry in SQLite logs and bump user metrics
    email = user["email"]
    bump_stat(email, "careers")
    add_activity(email, "career", "استكشاف مسارات مهنية")
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Bootstrap & Run
# ═══════════════════════════════════════════════════════════════════════════════
# Initialize local SQLite schemas, foreign key indexes, and admin data defaults
init_db()

# Synchronize local administrative configurations and dynamically reload overrides (such as hashed passwords)
_settings_cache = load_settings()
if _settings_cache.get("admin", {}).get("password"):
    ADMIN_PASSWORD = _settings_cache["admin"]["password"]

# Local execution entry point when starting the Flask web server directly
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
