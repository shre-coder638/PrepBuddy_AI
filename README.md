# PrepBuddy - AI

PrepBuddy is a clinical preparation and patient-management platform. It
combines a Django backend with a React dashboard to help clinical teams manage
patients, procedures, protocols, reminders, and preparation questions in one
place.

## Features

- Patient, clinic, procedure, and protocol management
- Source-grounded AI chatbot for preparation questions
- Scheduled reminders and missed-reminder follow-ups
- Optional WhatsApp notifications
- Django-rendered pages and a React/Tailwind dashboard
- REST endpoints for the frontend and integrations
- 

## Technology

- **Backend:** Django, Django REST Framework, PostgreSQL
- **Frontend:** React, Vite, Tailwind CSS
- **Background work:** Celery with Redis
- **Integrations:** WhatsApp/OpenWA

## Getting started

### Backend

1. Create and activate a Python virtual environment.
2. Install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Configure the database and service credentials in a `.env` file. At
   minimum, provide `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and
   `DB_HOST`. Set the WhatsApp and Redis variables when those integrations are
   enabled.
4. Apply migrations and start Django:

   ```powershell
   python manage.py migrate
   python manage.py runserver
   ```

### Frontend

The React client lives in [`frontend-ui`](./frontend-ui):

```powershell
cd frontend-ui
npm install
npm run dev
```

For the Django-served production bundle:

```powershell
npm run build
```

The build outputs `app.js` and `styles.css` to `static/react`.

### Background workers

Redis must be running before starting Celery. In separate terminals, run:

```powershell
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

## Testing

Run the Django test suite with:

```powershell
pytest
```
