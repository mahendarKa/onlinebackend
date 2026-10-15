# Online Exam Portal — Backend

FastAPI + SQLAlchemy + MySQL backend for the Online Exam Portal.

## Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Database

1. Create the MySQL database:

```sql
CREATE DATABASE online_exam_portal;
```

2. Configure `backend\.env` (already provided; adjust credentials if needed):

```
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/online_exam_portal
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200
```

3. Create tables and seed the first admin:

```powershell
python init_db.py
```

Default seeded admin: `admin@example.com` / `admin123` (override via
`ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars or edit `init_db.py`).

## Run

```powershell
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs
