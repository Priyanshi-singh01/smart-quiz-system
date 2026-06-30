# 🎓 Smart Online Quiz and Performance Analysis System

A full-stack web application for conducting online quizzes and analyzing student performance, built as a BCA Final Year Project.

🔗 **Live Demo:** [Add your Render link here after deployment]

---

## 📋 Project Overview

The **Smart Online Quiz and Performance Analysis System** is a complete exam management platform that allows administrators to schedule subject-wise quizzes and students to attempt them within a fixed time window. The system automatically calculates scores, generates leaderboards, and produces downloadable PDF reports.

---

## ✨ Key Features

### 👨‍🎓 Student Features
- Secure registration and login with Roll Number
- OTP-based secure password reset (via Gmail)
- View upcoming and active scheduled exams on dashboard
- Attempt subject-wise timed quizzes with randomized question order
- Auto-save answers — resume quiz if browser closes mid-exam
- Auto-submit when scheduled time ends
- Instant result with marks, percentage, and grade
- Personal performance trend chart (subject-wise)
- View own ranking on the leaderboard

### 👨‍💼 Admin Features
- Separate secure admin login
- Schedule subject-wise quizzes (Subject Name, Paper Code, Date, Start/End Time)
- Edit or delete scheduled quizzes
- Session-based subject selector — entire dashboard filters by selected subject
- Add/Edit/Delete questions with optional image upload
- Set custom marks per question
- Bulk question upload via CSV (subject-specific)
- Dynamic quiz timer — no fixed limit
- Allow/Block reattempt per quiz
- View subject-wise student list and results
- Export subject-wise PDF reports (Subject, Paper Code, Exam Date, Rankings)
- Manage registered students

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| Database | PostgreSQL |
| DB Driver | psycopg2-binary |
| Frontend | HTML5, CSS3, JavaScript |
| Email | Flask-Mail (Gmail SMTP, OTP system) |
| PDF Reports | ReportLab |
| Charts | Chart.js |
| Security | Werkzeug (password hashing) |

---

## 📂 Project Structure

```
quiz_app/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── demo_questions.csv      # Sample CSV for bulk upload
├── .env.example             # Environment variable template
├── static/
│   ├── css/style.css
│   └── js/main.js
├── templates/
│   ├── (student pages)
│   └── admin/
└── uploads/                 # Question images
```

---

## 🚀 Run Locally

### Prerequisites
- Python 3.9+
- PostgreSQL 13+

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Priyanshi-singh01/smart-quiz-system.git
cd smart-quiz-system

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE quiz_db;"

# 5. Set environment variables (copy .env.example to .env and fill in)
cp .env.example .env

# 6. Run the application
python app.py
```

Visit `http://localhost:5000`

### Default Admin Login
```
Email:    admin@quiz.com
Password: admin123
```
⚠️ Change this password immediately after first login.

---

## 🌐 Deployment

This project is deployed on **[Render](https://render.com)** — a free cloud platform supporting Flask and PostgreSQL.

**Live URL:** `https://smart-quiz-system.onrender.com` *(update after deploying)*

Render automatically builds and deploys the app from this GitHub repository using the `requirements.txt` and start command `python app.py`. The PostgreSQL database is hosted as a free Render Postgres instance, with credentials passed via environment variables.

> Note: Free tier services on Render sleep after 15 minutes of inactivity — the first request may take 30–50 seconds to wake up.

---

## 📊 Database Schema

| Table | Purpose |
|-------|---------|
| `users` | Student and admin accounts |
| `quiz_schedules` | Scheduled exams (subject, paper code, date, time) |
| `questions` | MCQ questions linked to schedules |
| `results` | Student attempts, scores, and saved progress |
| `quiz_settings` | Default timer configuration |
| `otp_store` | OTP codes for password reset |

---

## 👩‍💻 Author

**Priyanshi Singh**
BCA Final Year — RBMI College, Bareilly
📧 mispriyanshisingh@gmail.com
🔗 [GitHub](https://github.com/Priyanshi-singh01) | [LinkedIn](https://linkedin.com/in/priyanshisingh84)

---

## 📄 License

This project was developed for academic purposes as a BCA Final Year Project.
