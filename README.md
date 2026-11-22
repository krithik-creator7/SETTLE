# Settle

A small expense-splitting app for groups — trips, roommates, dinners —
with support for multiple currencies and partial contributions (someone
can hand over cash for their own share on the spot, and the app still
works out the rest correctly).

Built with Flask + SQLAlchemy (SQLite) and a dependency-free vanilla JS
frontend. No build step, no framework.

## Why this exists

Splitting a group expense sounds simple until contributions get uneven:
one person pays the restaurant, another hands over cash for their own
seat, and now everyone's doing mental math to work out who owes whom.
Settle tracks all of that and reduces it to the minimum number of
payments needed to settle the group.

## Features

- Create a group, add participants, pick a currency (12 supported)
- Log expenses with flexible splits and optional direct contributions
- Live balances — who's owed money, who owes money
- A one-tap "settle up" view showing exactly who should pay whom
- Data persists in SQLite, so it survives a server restart
- A small test suite covering the settlement math and the API

## Project structure

```
settle/
├── app.py             # models, business logic, and routes
├── templates/
│   └── index.html     # the single-page UI
├── static/
│   ├── style.css
│   └── app.js
├── test_app.py
├── requirements.txt
└── Dockerfile
```

Everything backend-related lives in `app.py` on purpose — for a project
this size, one readable file beats a maze of modules. The one piece of
logic worth calling out is `compute_balances()`: it has to handle the
case where someone paid part of their own share directly (outside the
pooled expense), which is where the original version actually broke —
see "A bug worth mentioning" below.

## Getting started

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

### Running tests

```bash
pip install pytest
pytest
```

### Running with Docker

```bash
docker build -t settle .
docker run -p 5000:5000 settle
```

## API

| Method | Endpoint                                | Description                        |
|--------|-------------------------------------------|--------------------------------------|
| POST   | `/api/groups`                            | Create a group                      |
| GET    | `/api/groups/<id>`                       | Fetch a group                        |
| GET    | `/api/groups/<id>/expenses`              | List expenses                       |
| POST   | `/api/groups/<id>/expenses`              | Add an expense                      |
| DELETE | `/api/groups/<id>/expenses/<expense_id>` | Delete an expense                   |
| GET    | `/api/groups/<id>/balances`              | Per-person balances                 |
| GET    | `/api/groups/<id>/settlements`           | Balances + minimal settlement plan  |
| GET    | `/api/currencies`                        | Supported currencies                 |

Every endpoint validates its input and returns a clear `400` with an
`error` message on bad data, rather than a raw server error.

## A bug worth mentioning

Balances for a group must always sum to zero — every rupee owed has to
be owed *to* someone. An earlier version of the balance calculation
credited the payer the *full* expense amount, and then separately
subtracted direct contributions from the per-person split — double
counting that money. In practice this meant two people could both show
up as "owed" money with nobody owing anything. `test_app.py` has a
regression test (`test_balances_sum_to_zero_with_direct_contributions`)
covering exactly this case.

## License

MIT — do whatever you'd like with it.
