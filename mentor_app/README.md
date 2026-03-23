# MentorBridge — Mentor-Mentee Communication Platform

A full-scale Flask web application for structured mentorship communication.

## Features
- **Dual Role System**: Separate login flows for Mentors (Admin) and Mentees (Users)
- **Issue Tracking**: Raise, categorize, prioritize, and resolve issues
- **Direct Messaging**: Real-time conversation threads between users
- **Announcements**: Mentors can broadcast pinned announcements to all mentees
- **User Management**: Mentors can view, activate/deactivate mentee accounts
- **Comments**: Discussion threads on every issue
- **Profile Management**: Edit bio, expertise, display name

## Demo Credentials
- **Mentor**: `mentor@demo.com` / `mentor123`
- **Mentee**: `mentee@demo.com` / `mentee123`

## Local Setup

```bash
cd mentor_app
pip install -r requirements.txt
python app.py
```
Visit: http://localhost:5000

## Deploy to Render (Free)

1. Push this folder to a GitHub repository
2. Go to https://render.com → New Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add environment variable: `SECRET_KEY` = any random string
6. Deploy!

## Deploy to Railway

```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

## Deploy to Heroku

```bash
heroku create your-app-name
git push heroku main
heroku open
```

## Environment Variables
| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret | auto-generated |
| `DATABASE_URL` | PostgreSQL URL (production) | SQLite (dev) |

## Tech Stack
- **Backend**: Python Flask
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Frontend**: Jinja2 templates, vanilla CSS/JS
- **Auth**: Werkzeug password hashing, Flask sessions
- **Deployment**: Gunicorn WSGI server
