"""AI analyzer: uses OpenAI to extract Jira ticket drafts from Slack threads."""

import base64
import json
import os
from pathlib import Path

from openai import OpenAI


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


class AIAnalyzer:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analyze(self, thread_transcript: str, attachment_paths: list[str] | None = None) -> list[dict]:
        """
        Analyze a Slack thread and return a list of proposed Jira ticket dicts.
        attachment_paths: local file paths to images to include in the prompt.
        """
        messages = self._build_messages(thread_transcript, attachment_paths or [])

        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            messages=messages,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()

        data = json.loads(raw)
        # Model may return {"tickets": [...]} or directly [...]
        if isinstance(data, list):
            tickets = data
        elif "tickets" in data:
            tickets = data["tickets"]
        else:
            # Single ticket returned as object
            tickets = [data]

        return tickets

    def _build_messages(self, transcript: str, attachment_paths: list[str]) -> list:
        user_content = []

        # Add images (GPT-4o supports vision)
        for path in attachment_paths:
            p = Path(path)
            if not p.exists():
                continue
            mimetype = self._guess_mimetype(p)
            if not mimetype.startswith("image/"):
                continue
            try:
                data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mimetype};base64,{data}",
                        "detail": "high",
                    },
                })
            except Exception as e:
                print(f"Warning: could not encode image {path}: {e}")

        user_content.append({
            "type": "text",
            "text": f"Here is the Slack thread transcript:\n\n{transcript}\n\nPlease create the Jira ticket(s). Return a JSON array of ticket objects.",
        })

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def _guess_mimetype(self, path: Path) -> str:
        ext = path.suffix.lower()
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
        }
        return mapping.get(ext, "application/octet-stream")
