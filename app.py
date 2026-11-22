"""
SETTLE — Smart Expense Splitting with Partial Contributions & Multi-Currency
"""
import os
import uuid
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# ============================================================================
# APP SETUP
# ============================================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///settle.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

CURRENCIES = {
    "USD": {"symbol": "$", "name": "US Dollar"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar"},
    "AED": {"symbol": "د.إ", "name": "UAE Dirham"},
    "MXN": {"symbol": "$", "name": "Mexican Peso"},
    "BRL": {"symbol": "R$", "name": "Brazilian Real"},
}


def _uuid() -> str:
    return uuid.uuid4().hex


# ============================================================================
# MODELS
# ============================================================================
class Group(db.Model):
    id = db.Column(db.String(32), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    participants = db.relationship("Participant", backref="group", cascade="all, delete-orphan")
    expenses = db.relationship(
        "Expense", backref="group", cascade="all, delete-orphan",
        order_by="Expense.created_at",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "currency": self.currency,
            "participants": [p.name for p in self.participants],
            "created_at": self.created_at.isoformat(),
        }


class Participant(db.Model):
    id = db.Column(db.String(32), primary_key=True, default=_uuid)
    group_id = db.Column(db.String(32), db.ForeignKey("group.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)


class Expense(db.Model):
    id = db.Column(db.String(32), primary_key=True, default=_uuid)
    group_id = db.Column(db.String(32), db.ForeignKey("group.id"), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_by_id = db.Column(db.String(32), db.ForeignKey("participant.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    paid_by = db.relationship("Participant")
    shares = db.relationship("ExpenseShare", backref="expense", cascade="all, delete-orphan")

    def to_dict(self):
        total_contributions = sum(s.contribution for s in self.shares)
        remaining = self.amount - total_contributions
        per_person = round(remaining / len(self.shares), 2) if self.shares else 0.0
        return {
            "id": self.id,
            "description": self.description,
            "amount": self.amount,
            "paidBy": self.paid_by.name,
            "splitAmong": [s.participant.name for s in self.shares],
            "contributors": {s.participant.name: s.contribution for s in self.shares if s.contribution},
            "splitPerPerson": per_person,
            "amountAfterContributions": round(remaining, 2),
            "created_at": self.created_at.isoformat(),
        }


class ExpenseShare(db.Model):
    """One participant's slice of one expense, plus whatever they already
    paid directly toward it on the spot."""

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    expense_id = db.Column(db.String(32), db.ForeignKey("expense.id"), nullable=False)
    participant_id = db.Column(db.String(32), db.ForeignKey("participant.id"), nullable=False)
    contribution = db.Column(db.Float, nullable=False, default=0.0)

    participant = db.relationship("Participant")


# ============================================================================
# BALANCE & DEBT-SIMPLIFICATION LOGIC
# ============================================================================
EPSILON = 0.01


def compute_balances(group: Group) -> dict:
    """Positive balance = owed money. Negative = owes money."""
    balances = {p.name: 0.0 for p in group.participants}

    for expense in group.expenses:
        shares = expense.shares
        if not shares:
            continue

        full_share = expense.amount / len(shares)
        total_contributions = sum(s.contribution for s in shares)

        # The payer fronted the full amount, but anyone who contributed
        # directly (handed cash over on the spot) already reimbursed the
        # payer for that slice outside the app — so the payer is only
        # still waiting on (amount - total_contributions). Each person's
        # own debt is still their full even share minus whatever they
        # already contributed. Subtracting contributions from BOTH sides
        # would double-count them and stop balances summing to zero.
        balances[expense.paid_by.name] += expense.amount - total_contributions

        for share in shares:
            balances[share.participant.name] -= (full_share - share.contribution)

    return {name: round(amount, 2) for name, amount in balances.items()}


def simplify_debts(balances: dict) -> list:
    """Greedily matches the largest debtor against the largest creditor
    until everyone is settled. Not guaranteed to be the theoretical
    minimum number of transactions, but fast and easy to reason about."""
    debtors = sorted(
        ({"person": n, "amount": -a} for n, a in balances.items() if a < -EPSILON),
        key=lambda d: d["amount"], reverse=True,
    )
    creditors = sorted(
        ({"person": n, "amount": a} for n, a in balances.items() if a > EPSILON),
        key=lambda c: c["amount"], reverse=True,
    )

    settlements = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, creditor = debtors[i], creditors[j]
        amount = min(debtor["amount"], creditor["amount"])
        settlements.append({"from": debtor["person"], "to": creditor["person"], "amount": round(amount, 2)})

        debtor["amount"] -= amount
        creditor["amount"] -= amount
        if debtor["amount"] < EPSILON:
            i += 1
        if creditor["amount"] < EPSILON:
            j += 1

    return settlements


# ============================================================================
# API ERRORS
# ============================================================================
class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify({"error": err.message}), err.status


def get_group_or_404(group_id):
    group = db.session.get(Group, group_id)
    if group is None:
        raise ApiError("Group not found", 404)
    return group


def require(data, *fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise ApiError(f"Missing required field(s): {', '.join(missing)}")


# ============================================================================
# ROUTES — pages
# ============================================================================
@app.route("/")
def index():
    return render_template("index.html", currencies=CURRENCIES)


# ============================================================================
# ROUTES — API
# ============================================================================
@app.route("/api/groups", methods=["POST"])
def create_group():
    data = request.get_json(silent=True) or {}
    require(data, "groupName", "participants")

    participants = [p.strip() for p in data["participants"] if p and p.strip()]
    if len(participants) < 2:
        raise ApiError("A group needs at least two participants")
    if len(set(participants)) != len(participants):
        raise ApiError("Participant names must be unique")

    currency = data.get("currency", "USD")
    if currency not in CURRENCIES:
        raise ApiError(f"Unsupported currency: {currency}")

    group = Group(name=data["groupName"].strip(), currency=currency)
    group.participants = [Participant(name=name) for name in participants]
    db.session.add(group)
    db.session.commit()

    return jsonify(group.to_dict()), 201


@app.route("/api/groups/<group_id>", methods=["GET"])
def get_group(group_id):
    return jsonify(get_group_or_404(group_id).to_dict())


@app.route("/api/groups/<group_id>/expenses", methods=["GET"])
def list_expenses(group_id):
    group = get_group_or_404(group_id)
    return jsonify([e.to_dict() for e in group.expenses])


@app.route("/api/groups/<group_id>/expenses", methods=["POST"])
def add_expense(group_id):
    group = get_group_or_404(group_id)
    data = request.get_json(silent=True) or {}
    require(data, "description", "amount", "paidBy", "splitAmong")

    by_name = {p.name: p for p in group.participants}
    if data["paidBy"] not in by_name:
        raise ApiError(f"Unknown participant: {data['paidBy']}")

    split_among = data["splitAmong"]
    if not split_among:
        raise ApiError("splitAmong must include at least one participant")
    unknown = [n for n in split_among if n not in by_name]
    if unknown:
        raise ApiError(f"Unknown participant(s): {', '.join(unknown)}")

    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        raise ApiError("amount must be a number")
    if amount <= 0:
        raise ApiError("amount must be greater than zero")

    contributions = data.get("contributors", {}) or {}
    try:
        contributions = {k: float(v) for k, v in contributions.items() if v}
    except (TypeError, ValueError):
        raise ApiError("contributions must be numbers")

    if any(n not in split_among for n in contributions):
        raise ApiError("Contributors must be part of splitAmong")
    if sum(contributions.values()) > amount + 1e-9:
        raise ApiError("Contributions exceed the expense amount")

    expense = Expense(
        description=data["description"].strip(),
        amount=amount,
        paid_by_id=by_name[data["paidBy"]].id,
        group_id=group.id,
    )
    expense.shares = [
        ExpenseShare(participant_id=by_name[name].id, contribution=contributions.get(name, 0.0))
        for name in split_among
    ]
    db.session.add(expense)
    db.session.commit()

    return jsonify(expense.to_dict()), 201


@app.route("/api/groups/<group_id>/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(group_id, expense_id):
    group = get_group_or_404(group_id)
    expense = next((e for e in group.expenses if e.id == expense_id), None)
    if expense is None:
        raise ApiError("Expense not found", 404)

    db.session.delete(expense)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/groups/<group_id>/balances", methods=["GET"])
def get_balances(group_id):
    return jsonify(compute_balances(get_group_or_404(group_id)))


@app.route("/api/groups/<group_id>/settlements", methods=["GET"])
def get_settlements(group_id):
    group = get_group_or_404(group_id)
    balances = compute_balances(group)
    return jsonify({"balances": balances, "settlements": simplify_debts(balances)})


@app.route("/api/currencies", methods=["GET"])
def get_currencies():
    return jsonify(CURRENCIES)


# ============================================================================
# RUN
# ============================================================================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
