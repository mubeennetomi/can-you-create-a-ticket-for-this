#!/bin/bash
set -e

echo "Setting up Slack → Jira Ticket Creator..."

# Create virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "Created .env — please fill in your credentials before running."
fi

echo ""
echo "Setup complete. To run:"
echo "  source .venv/bin/activate"
echo "  python app.py"
echo "  Then open http://localhost:5000"
