# DWTS Picks League

A lightweight FastAPI app for a small group of friends to submit their Dancing with the Stars elimination-order picks, view the leaderboard, and keep the host message and admin controls private.

## Features

- Public leaderboard and participant selection viewer
- Name-based pick submissions with duplicate rejection per season
- Admin-only elimination recording and host-message updates
- SQLite persistence with no extra infrastructure required
- Static front-end for easy deployment and customization

## Local setup

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the environment example and set your own secrets:
   ```bash
   cp .env.example .env
   ```

3. Start the backend:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Serve the frontend from the project root with a static host, for example:
   ```bash
   python3 -m http.server 8080 --directory frontend
   ```

5. Open the app at http://127.0.0.1:8080/

## Admin login

The admin credentials are controlled by environment variables:

- `DWTS_ADMIN_USERNAME`
- `DWTS_ADMIN_PASSWORD`
- `DWTS_ADMIN_KEY`

Set these in your shell or `.env` file before running the app.

## Production deployment ideas

This app is intentionally small and simple enough for deployment to:

- Render
- Fly.io
- Railway
- a cheap VPS behind a reverse proxy

For a small friend group, a single app instance with SQLite is usually enough.
