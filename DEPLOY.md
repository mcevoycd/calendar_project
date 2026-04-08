Railway Deployment Guide (Django)

1) What this app now supports
- Environment-based production settings in app/settings.py
- PostgreSQL via DATABASE_URL
- Static files via WhiteNoise
- Gunicorn startup via Procfile
- Session and app data persistence in the database

2) Create services on Railway
- Create a new project from your GitHub repo.
- Add a PostgreSQL service to the same project.
- Add a Web service for this Django app.

3) Required environment variables (Web service)
- SECRET_KEY: long random string
- DEBUG: False
- ALLOWED_HOSTS: your-app.up.railway.app
- CSRF_TRUSTED_ORIGINS: https://your-app.up.railway.app
- DATABASE_URL: usually injected automatically when PostgreSQL is attached

4) Build/start behavior
- Railway should install dependencies from requirements.txt.
- Procfile starts Gunicorn automatically:
  web: gunicorn app.wsgi --log-file -

5) Run migrations and collect static files
Use Railway service command/one-off job:
- python manage.py migrate
- python manage.py collectstatic --noinput

6) Create an admin user (optional but recommended)
- python manage.py createsuperuser

7) Why To Do data now survives logout
- To Do, Diary, Notes, and auth/session data are persisted in database tables.
- Logging out clears only session state, not persisted rows.
- Ensure migrations are successfully applied in production.

8) Pre-go-live checklist
- DEBUG is False
- SECRET_KEY is set
- ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS include your Railway domain
- Database attached and migrations applied
- Static files collected
