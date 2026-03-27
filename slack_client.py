"""Slack client: fetches thread messages and downloads attachments."""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackThread:
    def __init__(self, channel_id: str, thread_ts: str, messages: list, attachments: list):
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.messages = messages          # list of dicts with text, user, ts, files
        self.attachments = attachments    # list of dicts with name, path, url, mimetype


def parse_slack_url(url: str) -> tuple[str, Optional[str]]:
    """
    Parse a Slack thread URL into (channel_id, thread_ts).
    Supported formats:
      https://workspace.slack.com/archives/C12345/p1234567890123456
      https://workspace.slack.com/archives/C12345/p1234567890123456?thread_ts=...&cid=...
    """
    # Extract path like /archives/C12345/p1234567890123456
    match = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", url)
    if not match:
        raise ValueError(f"Cannot parse Slack URL: {url}")
    channel_id = match.group(1)
    # Slack encodes ts as integer without dot; convert to float string
    raw_ts = match.group(2)
    thread_ts = f"{raw_ts[:-6]}.{raw_ts[-6:]}"

    # If URL has thread_ts param, the message is a reply; use that as thread root
    from urllib.parse import parse_qs
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "thread_ts" in qs:
        thread_ts = qs["thread_ts"][0]

    return channel_id, thread_ts


class SlackFetcher:
    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="slack_attachments_"))

    def fetch_thread(self, url: str) -> SlackThread:
        channel_id, thread_ts = parse_slack_url(url)
        messages = self._get_thread_messages(channel_id, thread_ts)
        attachments = self._download_attachments(messages)
        return SlackThread(channel_id, thread_ts, messages, attachments)

    def _get_thread_messages(self, channel_id: str, thread_ts: str) -> list:
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=200,
            )
        except SlackApiError as e:
            raise RuntimeError(f"Slack API error fetching thread: {e.response['error']}")

        messages = []
        for msg in response.get("messages", []):
            # Resolve user display name
            user_name = self._resolve_user(msg.get("user") or msg.get("bot_id", "unknown"))
            files = msg.get("files", [])
            attachments_in_msg = msg.get("attachments", [])

            messages.append({
                "user": user_name,
                "ts": msg.get("ts"),
                "text": msg.get("text", ""),
                "files": files,
                "attachments": attachments_in_msg,
            })
        return messages

    def _resolve_user(self, user_id: str) -> str:
        try:
            resp = self.client.users_info(user=user_id)
            profile = resp["user"]["profile"]
            return profile.get("display_name") or profile.get("real_name") or user_id
        except Exception:
            return user_id

    def _download_attachments(self, messages: list) -> list:
        """Download all files attached to messages and return metadata."""
        downloaded = []
        headers = {"Authorization": f"Bearer {self.client.token}"}

        for msg in messages:
            for file_info in msg.get("files", []):
                url = file_info.get("url_private_download") or file_info.get("url_private")
                if not url:
                    continue
                name = file_info.get("name", "attachment")
                mimetype = file_info.get("mimetype", "application/octet-stream")
                file_id = file_info.get("id", name)
                dest = self._tmp_dir / f"{file_id}_{name}"

                try:
                    r = requests.get(url, headers=headers, timeout=30)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                    downloaded.append({
                        "name": name,
                        "path": str(dest),
                        "url": url,
                        "mimetype": mimetype,
                        "size": len(r.content),
                    })
                except Exception as e:
                    print(f"Warning: could not download {name}: {e}")

        return downloaded

    def format_thread_for_ai(self, thread: SlackThread) -> str:
        """Format thread messages into a plain-text transcript for the AI."""
        lines = []
        for msg in thread.messages:
            lines.append(f"[{msg['user']}]: {msg['text']}")
            for att in msg.get("attachments", []):
                if att.get("text"):
                    lines.append(f"  [attachment]: {att['text']}")
            for f in msg.get("files", []):
                lines.append(f"  [file attached]: {f.get('name', 'unknown')} ({f.get('mimetype', '')})")
        return "\n".join(lines)
