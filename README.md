# DWTS Picks

A lightweight FastAPI app for friends to submit Dancing with the Stars elimination-order picks, view the leaderboard, and manage admin controls.

## Features

- Public leaderboard and participant selection viewer
- Name-based pick submissions with duplicate rejection per season
- Admin-only elimination recording and host-message updates
- SQLite persistence with no extra infrastructure required
- Static front-end for easy deployment and customization

## Setup

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

4. Serve the frontend:
   ```bash
   python3 -m http.server 8080 --directory frontend
   ```

## Admin Credentials

Set these environment variables before running:
- `DWTS_ADMIN_USERNAME`
- `DWTS_ADMIN_PASSWORD`
- `DWTS_ADMIN_KEY`

## Production Deployment

For small groups of friends, deploy on Render. Render's free tier has no persistent disk, so:

- Use a hosted Postgres database (e.g. [Neon](https://neon.tech)) via `DATABASE_URL` instead of SQLite — data written to local disk (including a SQLite file at the default `DWTS_DB_PATH`) is lost on every redeploy/restart on the free tier.
- Spotlight images are uploaded and stored as bytes directly in the database (see `Highlight.image_data`), not on the local filesystem, so they persist across redeploys as long as the database itself is persistent (e.g. Neon).

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment variables:**
  - `DWTS_ADMIN_USERNAME`
  - `DWTS_ADMIN_PASSWORD`
  - `DWTS_ADMIN_KEY`
  - `DATABASE_URL=<your Neon postgresql:// connection string>`

If you do have a persistent disk (e.g. a paid Render plan or self-hosted), you can instead use SQLite with `DWTS_DB_PATH=/data/dwts.db` pointed at the mounted volume.

**Important:** Keep admin credentials out of the repo.
