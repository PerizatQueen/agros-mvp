import requests

SUPABASE_URL = 'https://jyaedutxxtpzhxxeizvp.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5YWVkdXR4eHRwemh4eGVpenZwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MzQ0MjExNCwiZXhwIjoyMDk5MDE4MTE0fQ.u3Cm-9a4OGFb1wLmXQCWVtggUTkQcY3afEENeGyMTjc'

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

REST = f'{SUPABASE_URL}/rest/v1'

def db_get(table, filters=None, select='*', order=None):
    params = {'select': select}
    if filters:
        params.update(filters)
    if order:
        params['order'] = order
    r = requests.get(f'{REST}/{table}', headers=HEADERS, params=params)
    return r.json() if r.ok else []

def db_insert(table, data):
    r = requests.post(f'{REST}/{table}', headers=HEADERS, json=data)
    return r.json() if r.ok else []

def db_update(table, data, filters):
    params = {}
    params.update(filters)
    r = requests.patch(f'{REST}/{table}', headers=HEADERS, json=data, params=params)
    return r.json() if r.ok else []

# ===== USERS =====
def get_user_by_phone(phone):
    result = db_get('users', {'phone': f'eq.{phone}'})
    return result[0] if result else None

def get_user_by_id(user_id):
    result = db_get('users', {'id': f'eq.{user_id}'})
    return result[0] if result else None

def update_bonus_balance(user_id, amount):
    user = get_user_by_id(user_id)
    if user:
        new_balance = user['bonus_balance'] + amount
        db_update('users', {'bonus_balance': new_balance}, {'id': f'eq.{user_id}'})
        return new_balance
    return 0

def create_user(phone, name, pin_hash, bonus_balance=0):
    result = db_insert('users', {
        'phone': phone,
        'name': name,
        'pin_hash': pin_hash,
        'bonus_balance': bonus_balance
    })
    return result[0] if result else None

# ===== PLOTS =====
def get_plots(user_id):
    plots = db_get('plots', {'user_id': f'eq.{user_id}'})
    for plot in plots:
        plot['varieties'] = db_get('plot_varieties', {'plot_id': f'eq.{plot["id"]}'})
    return plots

def get_plot(plot_id):
    result = db_get('plots', {'id': f'eq.{plot_id}'})
    if not result:
        return None
    plot = result[0]
    plot['varieties'] = db_get('plot_varieties', {'plot_id': f'eq.{plot_id}'})
    return plot

def create_plot(user_id, name, area_ha, garden_type, lat, lng, address, varieties):
    result = db_insert('plots', {
        'user_id': user_id,
        'name': name,
        'area_ha': float(area_ha),
        'garden_type': garden_type,
        'lat': float(lat) if lat else None,
        'lng': float(lng) if lng else None,
        'address': address
    })
    plot_id = result[0]['id']
    for v in varieties:
        db_insert('plot_varieties', {
            'plot_id': plot_id,
            'variety_name': v['name'],
            'area_ha': float(v.get('area_ha', 0)),
            'expected_yield': float(v.get('expected_yield', 0))
        })
    return plot_id

# ===== DEMAND PRICES =====
def get_demand_prices():
    return db_get('demand_prices')

# ===== CONTRACTS =====
def get_contracts(user_id):
    contracts = db_get('contracts', {'user_id': f'eq.{user_id}'}, order='created_at.desc')
    for c in contracts:
        c['contract_items'] = db_get('contract_items', {'contract_id': f'eq.{c["id"]}'})
        plots = db_get('plots', {'id': f'eq.{c["plot_id"]}'}, select='name')
        c['plot_name'] = plots[0]['name'] if plots else ''
    return contracts

def create_contract(user_id, plot_id, items):
    total = sum(float(i.get('volume_kg', 0)) * float(i.get('price_per_kg', 0)) for i in items)
    result = db_insert('contracts', {
        'user_id': user_id,
        'plot_id': plot_id,
        'status': 'pending',
        'total_amount': total
    })
    contract_id = result[0]['id']
    for item in items:
        db_insert('contract_items', {
            'contract_id': contract_id,
            'variety_name': item['variety_name'],
            'volume_kg': float(item.get('volume_kg', 0)),
            'price_per_kg': float(item.get('price_per_kg', 0))
        })
    return contract_id

# ===== TASKS =====
def get_tasks(user_id, month=None):
    tasks = db_get('tasks', {'user_id': f'eq.{user_id}'}, order='due_date')
    if month:
        tasks = [t for t in tasks if t.get('due_date', '').startswith(f'2026-{month:02d}')]
    for t in tasks:
        plots = db_get('plots', {'id': f'eq.{t["plot_id"]}'}, select='name')
        t['plot_name'] = plots[0]['name'] if plots else ''
    return tasks

def complete_task(task_id, user_id):
    db_update('tasks', {'status': 'approved'}, {'id': f'eq.{task_id}'})
    tasks = db_get('tasks', {'id': f'eq.{task_id}'}, select='bonus_amount')
    bonus = tasks[0]['bonus_amount'] if tasks else 0
    new_balance = update_bonus_balance(user_id, bonus)
    return bonus, new_balance
