# PrepBuddy React frontend

This directory contains the React + Tailwind CSS frontend for the PrepBuddy
clinical dashboard. It is intentionally separate from the Django `frontend`
app so the existing server-rendered application can continue to run while the
React client is integrated with the API.

## Run locally

```powershell
cd frontend-ui
npm install
npm run dev
```

Create a production build with:

```powershell
npm run build
```

The build writes `app.js` and `styles.css` to `../static/react`, which is the
directory served by Django. Django renders `templates/react_app.html` for the
authenticated root dashboard, so the Vite development server is only needed
for frontend development.

The dashboard currently uses representative patient data in `src/App.jsx`.
The action handlers are isolated and ready to be replaced with calls to the
existing Django endpoints.
