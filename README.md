# SETTLE - Python Flask Version

**Quick Start (3 Steps)**

## Step 1: Install Python Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

## Step 2: Run the App

```bash
python app.py
```

You'll see:
```
 * Running on http://127.0.0.1:5000
```

## Step 3: Open in Browser

Go to `http://localhost:5000` and start splitting expenses!

---

## Features

✅ Expense tracking with contributions  
✅ Multi-currency support (12+)  
✅ Debt simplification algorithm  
✅ Mobile-responsive design  
✅ Partial contribution tracking  
✅ Real-time balance calculations  

## Project Structure

```
settle-python/
├── app.py                    ← Flask application
├── requirements.txt          ← Python dependencies
└── app/
    ├── templates/
    │   └── index.html        ← Single-page app UI
    └── static/
        └── css/
            └── style.css     ← Styling
```

## API Endpoints

- `GET /` - Main app page
- `POST /api/groups` - Create group
- `GET /api/groups/<id>/expenses` - Get expenses
- `POST /api/groups/<id>/expenses` - Add expense
- `DELETE /api/groups/<id>/expenses/<id>` - Delete expense
- `GET /api/groups/<id>/balances` - Get balances
- `GET /api/groups/<id>/settlements` - Get settlements
- `POST /api/groups/reset` - Reset all data

## Data Storage

- Data stored in Flask session (in-memory)
- For production, modify to use database

## Development

- Debug mode is ON
- Auto-reload on file changes
- Hot reload works with CSS/JS changes

## Deployment

For production deployment:

### Heroku
```bash
pip freeze > requirements.txt
heroku create
git push heroku main
```

### PythonAnywhere
```bash
Upload files to PythonAnywhere
Configure WSGI file
```

### Docker
```bash
docker build -t settle .
docker run -p 5000:5000 settle
```

---

**Enjoy Settle in Python!** 💚
