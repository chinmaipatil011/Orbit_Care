# Orbit Care — Full-stack customer care demo

This version has a real Flask backend and SQLite database. Admin edits are sent to the backend and persisted in SQLite; they are not browser-only mock changes.

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Demo admin login
- Username: `admin`
- Password: `OrbitDemo2026!`

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables before the first run to choose different initial credentials. The default credentials are for local demonstration only; change them before any public deployment. Set a strong `SECRET_KEY` environment variable for stable sessions.

## Pages
- `/` or `/customer` — Customer dashboard
- `/chat` — Rule-based chatbot
- `/complaint` — Submit a ticket
- `/track` — Track by ticket ID
- `/admin/login` — Admin sign in
- `/admin` — Admin dashboard (login required)

## Database
SQLite file `orbit_care.db` is created automatically next to `app.py`. Sample tickets are seeded only when the ticket table is empty. The database persists on a local disk. On serverless hosting such as Vercel, local SQLite storage may be ephemeral or read-only; use a hosted database (for example Postgres) for persistent production deployments.

## Important security notes
This is a college project starter. Admin routes and mutations require a session login and passwords are hashed. The public demo ticket listing endpoint is intentionally convenient for the frontend demo; for a real customer support service, restrict list access and add CSRF/rate-limiting and stronger operational controls.
