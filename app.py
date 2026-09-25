"""
SETTLE - Python Flask Version v1.2
Smart Expense Splitting with Partial Contributions & Multi-Currency
"""

from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import json
import os
from functools import wraps

# Fix template and static folder paths
app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')
app.secret_key = 'settle-secret-key-2024'

# Currencies configuration
CURRENCIES = {
    'USD': {'symbol': '$', 'code': 'USD', 'name': 'US Dollar', 'locale': 'en_US'},
    'EUR': {'symbol': '€', 'code': 'EUR', 'name': 'Euro', 'locale': 'de_DE'},
    'GBP': {'symbol': '£', 'code': 'GBP', 'name': 'British Pound', 'locale': 'en_GB'},
    'INR': {'symbol': '₹', 'code': 'INR', 'name': 'Indian Rupee', 'locale': 'en_IN'},
    'AUD': {'symbol': 'A$', 'code': 'AUD', 'name': 'Australian Dollar', 'locale': 'en_AU'},
    'CAD': {'symbol': 'C$', 'code': 'CAD', 'name': 'Canadian Dollar', 'locale': 'en_CA'},
    'JPY': {'symbol': '¥', 'code': 'JPY', 'name': 'Japanese Yen', 'locale': 'ja_JP'},
    'CNY': {'symbol': '¥', 'code': 'CNY', 'name': 'Chinese Yuan', 'locale': 'zh_CN'},
    'SGD': {'symbol': 'S$', 'code': 'SGD', 'name': 'Singapore Dollar', 'locale': 'en_SG'},
    'AED': {'symbol': 'د.إ', 'code': 'AED', 'name': 'UAE Dirham', 'locale': 'ar_AE'},
    'MXN': {'symbol': '$', 'code': 'MXN', 'name': 'Mexican Peso', 'locale': 'es_MX'},
    'BRL': {'symbol': 'R$', 'code': 'BRL', 'name': 'Brazilian Real', 'locale': 'pt_BR'},
}

# ============================================================================
# DEBT SIMPLIFICATION ALGORITHM
# ============================================================================
def simplify_debts(balances):
    """
    Converts complex payment dependencies into minimal settlement transactions
    using a greedy matching algorithm
    """
    debtors = []
    creditors = []

    # Separate into those who owe and those owed to
    for person, amount in balances.items():
        if amount < -0.01:  # They owe
            debtors.append({'person': person, 'amount': abs(amount)})
        elif amount > 0.01:  # Owed to them
            creditors.append({'person': person, 'amount': amount})

    settlements = []

    # Greedy matching: match largest debts with largest credits
    while debtors and creditors:
        debtor = debtors[0]
        creditor = creditors[0]

        amount = min(debtor['amount'], creditor['amount'])
        settlements.append({
            'from': debtor['person'],
            'to': creditor['person'],
            'amount': round(amount, 2)
        })

        debtor['amount'] -= amount
        creditor['amount'] -= amount

        if debtor['amount'] < 0.01:
            debtors.pop(0)
        if creditor['amount'] < 0.01:
            creditors.pop(0)

    return settlements

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Home page - Setup or Dashboard"""
    return render_template('index.html', currencies=CURRENCIES)

@app.route('/api/groups', methods=['GET', 'POST'])
def manage_groups():
    """Get or create a group"""
    if request.method == 'POST':
        data = request.get_json()
        group_id = str(datetime.now().timestamp()).replace('.', '')
        
        group_data = {
            'id': group_id,
            'name': data['groupName'],
            'participants': data['participants'],
            'currency': data['currency'],
            'expenses': [],
            'created_at': datetime.now().isoformat()
        }
        
        # Store in session
        session['current_group'] = group_data
        session.modified = True
        
        return jsonify(group_data), 201
    
    # GET - return current group from session
    group = session.get('current_group')
    if group:
        return jsonify(group)
    return jsonify({'error': 'No group'}), 404

@app.route('/api/groups/<group_id>/expenses', methods=['GET', 'POST'])
def manage_expenses(group_id):
    """Get all expenses or add new expense"""
    group = session.get('current_group')
    if not group:
        return jsonify({'error': 'No group'}), 404

    if request.method == 'POST':
        data = request.get_json()
        
        # Calculate contributions total
        contributions = data.get('contributors', {})
        total_contributions = sum(float(c) for c in contributions.values() if c)
        
        if total_contributions > float(data['amount']):
            return jsonify({'error': 'Contributions exceed expense'}), 400
        
        # Calculate split
        amount_after_contributions = float(data['amount']) - total_contributions
        split_per_person = round(amount_after_contributions / len(data['splitAmong']), 2)
        
        expense = {
            'id': str(datetime.now().timestamp()).replace('.', ''),
            'description': data['description'],
            'amount': float(data['amount']),
            'paidBy': data['paidBy'],
            'splitAmong': data['splitAmong'],
            'splitPerPerson': split_per_person,
            'contributors': {k: float(v) for k, v in contributions.items() if v},
            'amountAfterContributions': amount_after_contributions,
            'created_at': datetime.now().isoformat()
        }
        
        group['expenses'].append(expense)
        session['current_group'] = group
        session.modified = True
        
        return jsonify(expense), 201
    
    # GET - return all expenses
    return jsonify(group['expenses'])

@app.route('/api/groups/<group_id>/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(group_id, expense_id):
    """Delete an expense"""
    group = session.get('current_group')
    if not group:
        return jsonify({'error': 'No group'}), 404
    
    group['expenses'] = [e for e in group['expenses'] if e['id'] != expense_id]
    session['current_group'] = group
    session.modified = True
    
    return jsonify({'success': True})

@app.route('/api/groups/<group_id>/balances', methods=['GET'])
def get_balances(group_id):
    """Calculate individual balances"""
    group = session.get('current_group')
    if not group:
        return jsonify({'error': 'No group'}), 404
    
    balances = {p: 0.0 for p in group['participants']}
    
    # Calculate balances from expenses
    for expense in group['expenses']:
        # Add to paidBy person
        balances[expense['paidBy']] += expense['amount']
        
        # Subtract from split participants (after contributions)
        for person in expense['splitAmong']:
            contribution = expense['contributors'].get(person, 0)
            balances[person] -= (expense['splitPerPerson'] - contribution)
    
    # Round to 2 decimals
    balances = {k: round(v, 2) for k, v in balances.items()}
    
    return jsonify(balances)

@app.route('/api/groups/<group_id>/settlements', methods=['GET'])
def get_settlements(group_id):
    """Get settlement instructions (who owes whom)"""
    group = session.get('current_group')
    if not group:
        return jsonify({'error': 'No group'}), 404
    
    # Get balances
    balances = {p: 0.0 for p in group['participants']}
    for expense in group['expenses']:
        balances[expense['paidBy']] += expense['amount']
        for person in expense['splitAmong']:
            contribution = expense['contributors'].get(person, 0)
            balances[person] -= (expense['splitPerPerson'] - contribution)
    
    balances = {k: round(v, 2) for k, v in balances.items()}
    
    # Simplify debts
    settlements = simplify_debts(balances)
    
    return jsonify({
        'balances': balances,
        'settlements': settlements
    })

@app.route('/api/groups/reset', methods=['POST'])
def reset_group():
    """Reset/clear all data"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/currencies', methods=['GET'])
def get_currencies():
    """Get list of supported currencies"""
    return jsonify(CURRENCIES)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
