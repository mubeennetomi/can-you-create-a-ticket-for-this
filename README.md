# Can you create a ticket for this?

Turn any Slack thread into a Jira ticket in seconds. Paste a thread URL, review the AI-drafted ticket, edit if needed, and create it in Jira — attachments and all.

![can-you-create](https://github.com/user-attachments/assets/4758dec8-6dd9-414b-98c3-d5cf12ae3984)

<img width="563" height="533" alt="Can-you-create-tool" src="https://github.com/user-attachments/assets/ff7c167c-9a47-47ee-ad59-d37ec3d42ac2" />

---

## How it works

1. **Paste a Slack thread URL** (or paste the text directly for DMs)
2. **AI analyzes the conversation** — reads the full thread, downloads images and files
3. **Review the draft** — edit any field before anything is created
4. **One click** — ticket created in Jira with all attachments uploaded

---

## Features

- Reads **any Slack thread** — public channels, private channels, DMs, group DMs
- **Downloads attachments** from Slack automatically — images, files, screenshots
- **AI-powered analysis** — extracts summary, description, issue type, priority, labels, and custom fields
- **Supports OpenAI (GPT-4o), Anthropic (Claude), and Google Gemini** — switch providers any time
- **Add instructions** — tell the AI extra context before it drafts the ticket
- **Upload extra files** — drag and drop additional screenshots or docs
- **Fully configurable Jira fields** — add, remove, reorder fields from the UI (including custom fields)
- **Review before creating** — edit every field, deselect tickets you don't want

---

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/mubeennetomi/can-you-create-a-ticket-for-this
cd "can-you-create-a-ticket-for-this"
```

### 2. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate      # Mac/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### 3. Run the app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) — then go to **⚙️ Settings** to enter your credentials.

---

## Credentials you'll need

| Credential | Where to get it |
|---|---|
| **Slack User Token** (`xoxp-`) | api.slack.com/apps → OAuth & Permissions → User Token Scopes → Install |
| **OpenAI API Key** | platform.openai.com/api-keys |
| **Anthropic API Key** | console.anthropic.com/settings/keys |
| **Gemini API Key** | aistudio.google.com/app/apikey (free tier available) |
| **Jira Server URL** | Your Atlassian domain e.g. `https://yourcompany.atlassian.net` |
| **Jira Project Key** | The prefix on your tickets e.g. `NET` for NET-123 |
| **Jira API Token** | id.atlassian.com/manage-profile/security/api-tokens |

All credentials are entered through the Settings UI — no need to edit files manually. Each field has step-by-step instructions built in.

---

## AI providers

You can use any of the three — all support vision (images from threads are analyzed):

| Provider | Model | Notes |
|---|---|---|
| **OpenAI** | GPT-4o | Requires paid plan |
| **Anthropic** | Claude Opus | Requires paid plan |
| **Google Gemini** | Gemini 1.5 Pro | Has a free tier |

Switch between providers any time in Settings without losing your other keys.

---

## Configuring Jira fields

The fields shown on the review screen are fully configurable in **Settings → Jira Ticket Fields**:

- **Add** custom Jira fields (e.g. Sprint, Epic Link, any `customfield_XXXXX`)
- **Remove** fields you don't use
- **Reorder** by dragging
- Set options, defaults, and placeholders

To find a custom field ID: Jira Settings → Issues → Custom Fields → click the field → check the URL for `customfield_XXXXX`.

---

## Troubleshooting

**`channel_not_found`** — Use a Slack User Token (`xoxp-`), not a Bot Token. The user token can read DMs and private channels without needing bot invites.

**`proxies` error on startup** — Version conflict with httpx. Run:
```bash
pip install "openai>=1.52.0" "httpx>=0.27.0,<0.28.0"
```

**Jira required field error** — Your project has a required custom field not in the form. Go to Settings → Jira Ticket Fields, add it with the correct `customfield_XXXXX` ID.

**Attachments not downloading** — Make sure your Slack User Token has `files:read` scope. Re-add the scope and reinstall the app to your workspace.

---

## Project structure

```
├── app.py               # Flask web server
├── slack_client.py      # Fetches Slack threads and downloads attachments
├── ai_analyzer.py       # OpenAI / Anthropic / Gemini analysis
├── jira_client.py       # Creates Jira issues and uploads attachments
├── fields_config.json   # Configurable Jira field definitions
├── requirements.txt
├── .env.example
└── templates/
    ├── base.html
    ├── index.html       # Input page
    ├── review.html      # Ticket review/edit page
    ├── success.html     # Confirmation page
    └── settings.html    # Credentials + field configuration
```

## Requirements

- Python 3.11+
- A Slack account with permission to create a Slack app
- One of: OpenAI, Anthropic, or Google account with API access
- A Jira/Atlassian account with permission to create issues

## Security

Credentials are stored in a local `.env` file which is excluded from git via `.gitignore`. API tokens are masked by default in the Settings UI. If deploying, use a proper secrets manager instead of `.env`.
