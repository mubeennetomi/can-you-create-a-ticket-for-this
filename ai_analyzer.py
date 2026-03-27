"""AI analyzer: supports OpenAI, Anthropic, and Google Gemini."""

import base64
import json
from pathlib import Path


SYSTEM_PROMPT = """You are a product/engineering assistant that turns Slack conversation threads into well-structured Jira tickets.

Given a Slack thread transcript (and optionally images), extract one or more Jira tickets.

For each ticket output a JSON object with these fields:
- summary: short, action-oriented title (under 80 chars)
- issue_type: one of "Story", "Bug", "Task", "Improvement"
- priority: one of "Highest", "High", "Medium", "Low", "Lowest"
- description: full Jira ticket description in Jira markdown format. Include:
  * h2. Background — context from the thread
  * h2. Problem / Request — what needs to be done
  * h2. Acceptance Criteria — bullet list of done criteria
  * h2. Notes — any extra info, links, or quotes from the thread
- labels: list of relevant label strings (lowercase, no spaces, e.g. ["ui", "hyperlinks", "chat"])
- components: list of component names inferred from context (can be empty list)
- clients_affected: list of client/company names mentioned (can be empty list)
- pod: the most relevant POD from this list: "AI Engine", "Analytics", "Chat Widget", "CS", "DevOps", "Documentation", "Generic", "Hawkeye", "Heimdall", "Innovation", "LLM Pipeline", "Mobile SDK", "Passport", "Platform", "QA". Choose the one that best matches the ticket topic. Default to "Generic" if unsure.

If the thread contains requests for MULTIPLE independent tickets, return an array of ticket objects.
If it's a single ticket, return an array with one object.

IMPORTANT: Return ONLY valid JSON — an array of ticket objects, no prose before or after.
"""

USER_PROMPT = "Here is the Slack thread transcript:\n\n{transcript}\n\nPlease create the Jira ticket(s). Return a JSON array of ticket objects."


def _guess_mimetype(path: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(path.suffix.lower(), "application/octet-stream")


def _parse_response(raw: str) -> list[dict]:
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    data = json.loads(raw.strip())
    if isinstance(data, list):
        return data
    if "tickets" in data:
        return data["tickets"]
    return [data]


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIAnalyzer:
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)

    def analyze(self, transcript: str, attachment_paths: list[str] | None = None) -> list[dict]:
        user_content = []
        for path in (attachment_paths or []):
            p = Path(path)
            if not p.exists():
                continue
            mime = _guess_mimetype(p)
            if not mime.startswith("image/"):
                continue
            try:
                data = base64.standard_b64encode(p.read_bytes()).decode()
                user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}", "detail": "high"}})
            except Exception as e:
                print(f"Warning: could not encode {path}: {e}")

        user_content.append({"type": "text", "text": USER_PROMPT.format(transcript=transcript)})

        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        return _parse_response(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicAnalyzer:
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, transcript: str, attachment_paths: list[str] | None = None) -> list[dict]:
        content = []
        for path in (attachment_paths or []):
            p = Path(path)
            if not p.exists():
                continue
            mime = _guess_mimetype(p)
            if not mime.startswith("image/"):
                continue
            try:
                data = base64.standard_b64encode(p.read_bytes()).decode()
                content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
            except Exception as e:
                print(f"Warning: could not encode {path}: {e}")

        content.append({"type": "text", "text": USER_PROMPT.format(transcript=transcript)})

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        return _parse_response(response.content[0].text)


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

class GeminiAnalyzer:
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=SYSTEM_PROMPT,
        )

    def analyze(self, transcript: str, attachment_paths: list[str] | None = None) -> list[dict]:
        import google.generativeai as genai
        parts = []
        for path in (attachment_paths or []):
            p = Path(path)
            if not p.exists():
                continue
            mime = _guess_mimetype(p)
            if not mime.startswith("image/"):
                continue
            try:
                parts.append({"mime_type": mime, "data": p.read_bytes()})
            except Exception as e:
                print(f"Warning: could not read {path}: {e}")

        parts.append(USER_PROMPT.format(transcript=transcript))

        response = self.model.generate_content(
            parts,
            generation_config={"response_mime_type": "application/json", "max_output_tokens": 4096},
        )
        return _parse_response(response.text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_analyzer(provider: str, api_key: str):
    """Return the right analyzer for the given provider."""
    if provider == "anthropic":
        return AnthropicAnalyzer(api_key)
    elif provider == "gemini":
        return GeminiAnalyzer(api_key)
    else:
        return OpenAIAnalyzer(api_key)


# Legacy alias so existing imports don't break
AIAnalyzer = OpenAIAnalyzer
