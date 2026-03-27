"""Flask web app: Slack → AI analysis → Review → Jira ticket creation."""

import json
import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from ai_analyzer import create_analyzer
from jira_client import JiraCreator
from slack_client import SlackFetcher

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# In-memory session store: session_id → {threads, tickets, attachments}
_store: dict[str, dict] = {}

FIELDS_CONFIG_PATH = Path(__file__).parent / "fields_config.json"


def load_fields_config() -> list:
    if FIELDS_CONFIG_PATH.exists():
        return json.loads(FIELDS_CONFIG_PATH.read_text())
    return []


def save_fields_config(fields: list):
    FIELDS_CONFIG_PATH.write_text(json.dumps(fields, indent=2))


def get_slack_fetcher() -> SlackFetcher:
    token = os.environ.get("SLACK_USER_TOKEN") or os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("SLACK_USER_TOKEN or SLACK_BOT_TOKEN not set")
    return SlackFetcher(token)


def get_ai_analyzer():
    provider = os.environ.get("AI_PROVIDER", "openai").lower()
    key_map = {
        "openai":    "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini":    "GEMINI_API_KEY",
    }
    env_var = key_map.get(provider, "OPENAI_API_KEY")
    key = os.environ.get(env_var, "")
    if not key:
        raise RuntimeError(f"{env_var} not set for provider '{provider}'")
    return create_analyzer(provider, key)


def get_jira_creator() -> JiraCreator:
    server = os.environ.get("JIRA_SERVER", "")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    project = os.environ.get("JIRA_PROJECT_KEY", "")
    if not all([server, email, token, project]):
        raise RuntimeError("Jira env vars not fully set (JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY)")
    return JiraCreator(server, email, token, project)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """Accept Slack thread URLs or pasted text, analyze, redirect to review page."""
    input_mode = request.form.get("input_mode", "url")
    instructions = request.form.get("instructions", "").strip()

    try:
        analyzer = get_ai_analyzer()
    except RuntimeError as e:
        return render_template("index.html", error=str(e))

    all_tickets = []
    all_attachments = []

    # Save any manually uploaded extra files
    extra_file_paths = []
    upload_dir = Path(tempfile.mkdtemp(prefix="extra_uploads_"))
    for f in request.files.getlist("extra_files"):
        if f and f.filename:
            dest = upload_dir / f.filename
            f.save(str(dest))
            extra_file_paths.append(str(dest))
            all_attachments.append({"name": f.filename, "path": str(dest), "mimetype": f.mimetype or "application/octet-stream"})

    if input_mode == "paste":
        thread_text = request.form.get("thread_text", "").strip()
        if not thread_text:
            return render_template("index.html", error="Please paste the thread text.")

        transcript = thread_text
        if instructions:
            transcript = f"Instructions from user: {instructions}\n\n{transcript}"

        try:
            tickets = analyzer.analyze(transcript, extra_file_paths)
            for t in tickets:
                t["_source_url"] = "pasted thread"
                t["_id"] = str(uuid.uuid4())
            all_tickets.extend(tickets)
        except Exception as e:
            return render_template("index.html", error=f"Error analyzing thread: {e}")

    else:
        urls_raw = request.form.get("slack_urls", "").strip()
        if not urls_raw:
            return render_template("index.html", error="Please enter at least one Slack thread URL.")

        urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]

        try:
            fetcher = get_slack_fetcher()
        except RuntimeError as e:
            return render_template("index.html", error=str(e))

        for url in urls:
            try:
                thread = fetcher.fetch_thread(url)
                transcript = fetcher.format_thread_for_ai(thread)
                if instructions:
                    transcript = f"Instructions from user: {instructions}\n\n{transcript}"
                attachment_paths = [a["path"] for a in thread.attachments] + extra_file_paths
                all_attachments.extend(thread.attachments)

                tickets = analyzer.analyze(transcript, attachment_paths)
                for t in tickets:
                    t["_source_url"] = url
                    t["_id"] = str(uuid.uuid4())
                all_tickets.extend(tickets)
            except Exception as e:
                return render_template("index.html", error=f"Error processing {url}: {e}")

    if not all_tickets:
        return render_template("index.html", error="No tickets could be extracted from the provided thread.")

    sess_id = str(uuid.uuid4())
    _store[sess_id] = {
        "tickets": all_tickets,
        "attachments": all_attachments,
    }
    session["sess_id"] = sess_id

    return redirect(url_for("review", sess_id=sess_id))


@app.route("/review/<sess_id>")
def review(sess_id: str):
    data = _store.get(sess_id)
    if not data:
        return redirect(url_for("index"))
    tickets = data["tickets"]
    attachments = data["attachments"]
    fields = load_fields_config()
    return render_template("review.html", tickets=tickets, attachments=attachments, sess_id=sess_id, fields=fields)


@app.route("/settings/fields", methods=["POST"])
def save_fields():
    try:
        fields = json.loads(request.form.get("fields_json", "[]"))
        save_fields_config(fields)
        return redirect(url_for("settings", saved_fields=1))
    except Exception as e:
        config = _load_env_config()
        return render_template("settings.html", config=config, saved=False,
                               error=f"Could not save fields: {e}",
                               fields=load_fields_config())


@app.route("/create", methods=["POST"])
def create():
    """Create approved/edited tickets in Jira."""
    sess_id = request.form.get("sess_id")
    data = _store.get(sess_id)
    if not data:
        return redirect(url_for("index"))

    # Parse edited ticket data from form
    tickets_json = request.form.get("tickets_json", "[]")
    try:
        tickets = json.loads(tickets_json)
    except json.JSONDecodeError:
        return render_template("review.html",
                               tickets=data["tickets"],
                               attachments=data["attachments"],
                               sess_id=sess_id,
                               fields=load_fields_config(),
                               error="Invalid ticket data. Please try again.")

    attachment_paths = [a["path"] for a in data["attachments"]]

    try:
        creator = get_jira_creator()
    except RuntimeError as e:
        return render_template("review.html",
                               tickets=data["tickets"],
                               attachments=data["attachments"],
                               sess_id=sess_id,
                               fields=load_fields_config(),
                               error=str(e))

    field_configs = load_fields_config()
    created = []
    errors = []
    for ticket in tickets:
        if not ticket.get("_selected", True):
            continue
        try:
            result = creator.create_ticket(ticket, attachment_paths, field_configs)
            result["summary"] = ticket["summary"]
            created.append(result)
        except Exception as e:
            errors.append({"summary": ticket.get("summary", "?"), "error": str(e)})

    # Clean up store
    if not errors:
        _store.pop(sess_id, None)

    return render_template("success.html", created=created, errors=errors)


ENV_KEYS = [
    "SLACK_USER_TOKEN", "SLACK_BOT_TOKEN",
    "AI_PROVIDER",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "JIRA_SERVER", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY",
    "FLASK_SECRET_KEY",
]


def _get_env_file_path() -> Path:
    return Path(__file__).parent / ".env"


def _load_env_config() -> dict:
    """Read current values from .env file."""
    config = {k: "" for k in ENV_KEYS}
    env_path = _get_env_file_path()
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                if key in config:
                    config[key] = val.strip()
    return config


def _save_env_config(new_values: dict):
    """Write updated values back to .env, preserving comments and order."""
    env_path = _get_env_file_path()
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in new_values:
                new_lines.append(f"{key}={new_values[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any new keys not already in the file
    for key, val in new_values.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n")

    # Reload into os.environ immediately
    for key, val in new_values.items():
        if val:
            os.environ[key] = val


@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved = False
    saved_fields = request.args.get("saved_fields", False)
    error = None
    if request.method == "POST":
        new_values = {k: request.form.get(k, "").strip() for k in ENV_KEYS}
        try:
            _save_env_config(new_values)
            saved = True
        except Exception as e:
            error = f"Could not save settings: {e}"
    config = _load_env_config()
    fields = load_fields_config()
    return render_template("settings.html", config=config, saved=saved,
                           saved_fields=saved_fields, error=error, fields=fields)


@app.route("/api/status")
def status():
    missing = []
    provider = os.environ.get("AI_PROVIDER", "openai").lower()
    ai_key = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider, "OPENAI_API_KEY")
    for var in [ai_key, "JIRA_SERVER", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"]:
        if not os.environ.get(var):
            missing.append(var)
    return jsonify({"ok": len(missing) == 0, "missing_env_vars": missing, "provider": provider})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
