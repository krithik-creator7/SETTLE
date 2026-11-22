"""
A single test file covering the two things most worth guarding:

1. The debt-simplification math (simplify_debts) — pure, no Flask needed.
2. The full create-group -> add-expense -> settle-up flow, including the
   case that broke before: balances must always sum to zero, even when
   someone contributed part of their share directly.

Run with: pytest
"""
import pytest

from app import app, db, simplify_debts


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield client
        db.drop_all()


def create_group(client, participants=("Alice", "Bob", "Carol")):
    res = client.post("/api/groups", json={
        "groupName": "Trip", "currency": "USD", "participants": list(participants),
    })
    assert res.status_code == 201
    return res.get_json()


# ---- pure debt-simplification math --------------------------------------
def test_simple_two_person_debt():
    assert simplify_debts({"Alice": 50.0, "Bob": -50.0}) == [
        {"from": "Bob", "to": "Alice", "amount": 50.0}
    ]


def test_already_settled_produces_no_transactions():
    assert simplify_debts({"Alice": 0.0, "Bob": 0.0}) == []


# ---- full API flow --------------------------------------------------------
def test_full_expense_flow(client):
    group = create_group(client)

    res = client.post(f"/api/groups/{group['id']}/expenses", json={
        "description": "Dinner", "amount": 90,
        "paidBy": "Alice", "splitAmong": ["Alice", "Bob", "Carol"],
    })
    assert res.status_code == 201

    data = client.get(f"/api/groups/{group['id']}/settlements").get_json()
    assert data["balances"] == {"Alice": 60.0, "Bob": -30.0, "Carol": -30.0}
    assert len(data["settlements"]) == 2


def test_balances_sum_to_zero_with_direct_contributions(client):
    # Regression test: balances used to leak money whenever a direct
    # contribution was involved, because the payer was credited the full
    # expense amount *and* the contribution was subtracted a second time
    # from the per-person split — so two people could both show up as
    # "owed" money with nobody actually owing anything.
    group = create_group(client, participants=("Raj", "Aji"))

    client.post(f"/api/groups/{group['id']}/expenses", json={
        "description": "Groceries", "amount": 6000,
        "paidBy": "Raj", "splitAmong": ["Raj", "Aji"],
        "contributors": {"Aji": 2000},
    })
    client.post(f"/api/groups/{group['id']}/expenses", json={
        "description": "Fuel", "amount": 1200,
        "paidBy": "Aji", "splitAmong": ["Raj", "Aji"],
    })

    balances = client.get(f"/api/groups/{group['id']}/settlements").get_json()["balances"]
    assert round(sum(balances.values()), 2) == 0


def test_contributions_cannot_exceed_amount(client):
    group = create_group(client, participants=("Alice", "Bob"))
    res = client.post(f"/api/groups/{group['id']}/expenses", json={
        "description": "Snacks", "amount": 10,
        "paidBy": "Alice", "splitAmong": ["Alice", "Bob"],
        "contributors": {"Bob": 50},
    })
    assert res.status_code == 400


def test_unknown_group_returns_404(client):
    res = client.get("/api/groups/does-not-exist/balances")
    assert res.status_code == 404
