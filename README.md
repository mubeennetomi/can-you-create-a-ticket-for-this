# Can you create a ticket for this?

A web app that turns Slack threads into Jira tickets using GPT-4o. Paste a Slack thread URL (or the text directly), review the AI-generated ticket, edit if needed, and create it in Jira — with all attachments included.

![Flow: Slack thread → AI analysis → Review → Jira ticket]

---

## What it does

1. **Reads a Slack thread** — via URL (public/private channels, DMs) or pasted text
2. **Downloads attachments** — images and files from the thread are fetched automatically
3. **Analyzes with GPT-4o** — extracts summary, description, issue type, priority, labels, and custom fields
4. **Review screen** — you edit any field before anything is created
5. **Creates the Jira ticket** — with all attachments uploaded

---

## Requirements

- Python 3.11+
- A Slack account with permission to create a Slack app
- An OpenAI account with GPT-4o access (paid plan)
- A Jira/Atlassian account with permission to create issues

---

## Installation

### 1. Clone or download the project

```bash
git clone <repo-url>
cd "Slack Jira Ticket Creator"
```

Or download the ZIP and extract it.

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 3. Set up credentials

Copy the example env file:

```bash
cp .env.example .env
```

Then either edit `.env` directly, or run the app and fill in credentials via the **Settings** page (recommended).

### 4. Run the app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## Getting your credentials

### Slack User Token (`xoxp-...`)

The user token lets the app read threads and download attachments as you — including DMs and private channels.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**
2. Give it a name (e.g. "Ticket Creator") and pick your workspace
3. In the left sidebar go to **OAuth & Permissions**
4. Scroll to **User Token Scopes** and add:
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `files:read`
   - `users:read`
5. Scroll up and click **Install to Workspace** → **Allow**
6. Copy the **User OAuth Token** (starts with `xoxp-`)

### OpenAI API Key (`sk-proj-...`)

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **Create new secret key**
3. Copy the key immediately — it won't be shown again
4. Make sure your account has billing enabled (GPT-4o requires a paid plan)

### Jira credentials

You need four things:

| Field | Example | Where to find it |
|---|---|---|
| Server URL | `https://yourcompany.atlassian.net` | Your browser URL when logged into Jira |
| Project Key | `NET` | The prefix on ticket numbers — NET-123 → key is `NET` |
| Account Email | `you@company.com` | Your Atlassian login email |
| API Token | `ATATT3x...` | See steps below |

**Generating a Jira API token:**
1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Give it a label (e.g. "Ticket Creator") and click **Create**
4. Copy the token — it won't be shown again

> **Note:** The API token inherits your Jira permissions. You need at least "Create Issues" permission in your project.

---

## Configuration

### Credentials (Settings page)

After starting the app, go to [http://localhost:5000/settings](http://localhost:5000/settings) to enter and save all credentials. Click **Test Connections** to verify everything is working.

### Jira fields (Settings → Jira Ticket Fields)

The fields that appear on the review screen are fully configurable:

- **Add** new fields (e.g. custom Jira fields like Sprint, Epic Link)
- **Remove** fields you don't use
- **Reorder** by dragging
- **Edit** labels, options, defaults, and Jira field IDs

**Jira Type reference:**

| Type | Use for | Example Jira fields |
|---|---|---|
| `string` | Plain text | `summary`, `description` |
| `object_name` | Standard named objects | `issuetype`, `priority` |
| `object_value` | Custom select/dropdown fields | `customfield_11009` (POD) |
| `array_string` | List of strings | `labels` |
| `array_object_name` | List of named objects | `components` |

To find a custom field ID in Jira: go to **Jira Settings → Issues → Custom Fields**, click the field, and look at the URL — it ends in the field ID (e.g. `customfield_10020`).

---

## Usage

### Using a Slack thread URL

1. Open the Slack thread you want to turn into a ticket
2. Click the **⋮ More actions** menu on any message → **Copy link**
3. Paste the URL into the app
4. Optionally add instructions or extra attachments
5. Click **Analyze Threads →**

### Using pasted text

Use the **Paste Thread Text** tab for any case where you can't use a URL (e.g. copying from a screenshot). Include sender names for best results:

```
Alice: Should we add a loading spinner to the submit button?
Bob: Yes — it should show while the request is in progress.
```

### Review screen

- Edit any field before creating
- Uncheck tickets you don't want
- All Slack attachments (and any extra files you uploaded) will be attached to the Jira ticket

---

## Project structure

```
├── app.py               # Flask web server — routes and session management
├── slack_client.py      # Fetches Slack threads and downloads attachments
├── ai_analyzer.py       # GPT-4o analysis — converts thread to ticket JSON
├── jira_client.py       # Creates Jira issues and uploads attachments
├── fields_config.json   # Configurable Jira field definitions
├── requirements.txt
├── .env.example         # Template for credentials
└── templates/
    ├── base.html        # Shared layout
    ├── index.html       # Input page
    ├── review.html      # Ticket review/edit page
    ├── success.html     # Confirmation page
    └── settings.html    # Credentials and field configuration
```

---

## Troubleshooting

**`channel_not_found` error**
The bot/user token doesn't have access to that channel. Use the User Token (`xoxp-`) and make sure you're a member of the channel.

**`proxies` error on startup**
Your `httpx` version is incompatible. Run:
```bash
pip install "openai>=1.52.0" "httpx>=0.27.0,<0.28.0"
```

**Jira field error (e.g. `POD is required`)**
Your Jira project has required custom fields. Go to **Settings → Jira Ticket Fields**, add the missing field with its `customfield_XXXXX` ID, and set it as required.

**Attachments not downloading**
Make sure your Slack User Token has the `files:read` scope. Re-add the scope and reinstall the app to your workspace.

---

## Security notes

- Credentials are stored in the `.env` file on your machine — never commit this file to version control
- `.env` is already in `.gitignore` if you use git
- API tokens are masked by default in the Settings UI
- This app is intended for local use — if deploying, use a proper secrets manager (e.g. AWS Secrets Manager, Railway env vars)
