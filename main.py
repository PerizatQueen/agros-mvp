import os
import hashlib
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from groq import Groq
import db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'agros-mvp-secret-2026')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
YANDEX_MAPS_KEY = os.environ.get('YANDEX_MAPS_API_KEY', '')

ADMIN_PHONE = 'admin'
ADMIN_PIN = '9999'
AGRONOMIST_PHONE = 'agro'
AGRONOMIST_PIN = '1111'

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def agronomist_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') not in ['agronomist', 'admin']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def farmer_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'farmer':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_panel'))
    elif role == 'agronomist':
        return redirect(url_for('agronomist_panel'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip().replace('+', '').replace(' ', '')
        pin = request.form.get('pin', '').strip()
        step = request.form.get('step', 'phone')
        role = request.form.get('role', 'farmer')
        if step == 'phone':
            sms_code = request.form.get('sms_code', '')
            if sms_code == '1234':
                return render_template('login.html', step='pin', phone=phone, role=role)
            return render_template('login.html', step='sms', phone=phone, role=role, error='Неверный SMS-код. Используйте 1234')
        elif step == 'sms':
            sms_code = request.form.get('sms_code', '')
            if sms_code == '1234':
                return render_template('login.html', step='pin', phone=phone, role=role)
            return render_template('login.html', step='sms', phone=phone, role=role, error='Неверный SMS-код')
        elif step == 'pin':
            if role == 'admin' and phone == ADMIN_PHONE and pin == ADMIN_PIN:
                session['user_id'] = 'admin'
                session['user_name'] = 'Администратор'
                session['role'] = 'admin'
                return redirect(url_for('admin_panel'))
            if role == 'agronomist' and phone == AGRONOMIST_PHONE and pin == AGRONOMIST_PIN:
                session['user_id'] = 'agronomist'
                session['user_name'] = 'Агроном'
                session['role'] = 'agronomist'
                return redirect(url_for('agronomist_panel'))
            if role == 'farmer':
                user = db.get_user_by_phone(phone)
                if user and user['pin_hash'] == hash_pin(pin):
                    session['user_id'] = user['id']
                    session['user_name'] = user['name']
                    session['role'] = 'farmer'
                    return redirect(url_for('dashboard'))
            return render_template('login.html', step='pin', phone=phone, role=role, error='Неверный PIN-код')
    return render_template('login.html', step='phone', role='farmer')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@farmer_required
def dashboard():
    user = db.get_user_by_id(session['user_id'])
    plots = db.get_plots(session['user_id'])
    contracts = db.get_contracts(session['user_id'])
    tasks = db.get_tasks(session['user_id'])
    prices = db.get_demand_prices()
    active_contracts = [c for c in contracts if c['status'] == 'active']
    upcoming_tasks = [t for t in tasks if t['status'] in ('soon', 'upcoming')][:3]
    overdue_tasks = [t for t in tasks if t['status'] == 'overdue']
    lang = session.get('lang', 'ru')
    return render_template('dashboard.html', user=user, plots=plots, contracts=active_contracts,
        tasks=upcoming_tasks, overdue_tasks=overdue_tasks, prices=prices[:4],
        has_plots=len(plots) > 0, has_contracts=len(contracts) > 0,
        has_active=len(active_contracts) > 0, lang=lang)

@app.route('/plots')
@farmer_required
def plots():
    user = db.get_user_by_id(session['user_id'])
    plots = db.get_plots(session['user_id'])
    return render_template('plots.html', user=user, plots=plots, yandex_key=YANDEX_MAPS_KEY, lang=session.get('lang','ru'))

@app.route('/plots/create', methods=['GET', 'POST'])
@farmer_required
def create_plot():
    user = db.get_user_by_id(session['user_id'])
    if request.method == 'POST':
        step = request.form.get('step', '1')
        if step == '3':
            varieties_json = request.form.get('varieties_json', '[]')
            try:
                varieties = json.loads(varieties_json)
            except:
                varieties = []
            db.create_plot(session['user_id'], request.form.get('name'), request.form.get('area_ha'),
                request.form.get('garden_type'), request.form.get('lat', '43.2551'),
                request.form.get('lng', '76.9126'), request.form.get('address', ''), varieties)
            db.update_bonus_balance(session['user_id'], 100)
            return redirect(url_for('plots') + '?bonus=100')
        return render_template('plots_create.html', user=user, step=int(step), form_data=request.form, yandex_key=YANDEX_MAPS_KEY)
    return render_template('plots_create.html', user=user, step=1, form_data={}, yandex_key=YANDEX_MAPS_KEY)

@app.route('/demand')
@farmer_required
def demand():
    user = db.get_user_by_id(session['user_id'])
    prices = db.get_demand_prices()
    plots = db.get_plots(session['user_id'])
    user_varieties = set()
    for p in plots:
        for v in p.get('varieties', []):
            user_varieties.add(v['variety_name'])
    for price in prices:
        price['on_my_plot'] = price['variety_name'] in user_varieties
    return render_template('demand.html', user=user, prices=prices, user_varieties=user_varieties, lang=session.get('lang','ru'))

@app.route('/contracts')
@farmer_required
def contracts():
    user = db.get_user_by_id(session['user_id'])
    contracts = db.get_contracts(session['user_id'])
    return render_template('contracts.html', user=user, contracts=contracts, lang=session.get('lang','ru'))

@app.route('/contracts/create', methods=['GET', 'POST'])
@farmer_required
def create_contract():
    user = db.get_user_by_id(session['user_id'])
    plots = db.get_plots(session['user_id'])
    prices = db.get_demand_prices()
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        if user['pin_hash'] != hash_pin(pin):
            return render_template('contracts_create.html', user=user, plots=plots, prices=prices, error='Неверный PIN-код')
        plot_id = request.form.get('plot_id')
        items_json = request.form.get('items_json', '[]')
        try:
            items = json.loads(items_json)
        except:
            items = []
        db.create_contract(session['user_id'], plot_id, items)
        db.update_bonus_balance(session['user_id'], 50)
        return redirect(url_for('contracts') + '?bonus=50')
    return render_template('contracts_create.html', user=user, plots=plots, prices=prices)

@app.route('/tasks')
@farmer_required
def tasks():
    user = db.get_user_by_id(session['user_id'])
    month = request.args.get('month', type=int)
    tasks = db.get_tasks(session['user_id'], month)
    return render_template('tasks.html', user=user, tasks=tasks, current_month=month, lang=session.get('lang','ru'))

@app.route('/tasks/<task_id>/complete', methods=['POST'])
@farmer_required
def complete_task(task_id):
    bonus, new_balance = db.complete_task(task_id, session['user_id'])
    return jsonify({'status': 'success', 'bonus': bonus, 'new_balance': new_balance})

@app.route('/chat')
@farmer_required
def chat():
    user = db.get_user_by_id(session['user_id'])
    return render_template('chat.html', user=user, lang=session.get('lang','ru'))

@app.route('/chat/message', methods=['POST'])
@farmer_required
def chat_message():
    data = request.get_json()
    message = data.get('message', '')
    chat_type = data.get('type', 'ai')
    if chat_type == 'agronomist':
        return jsonify({'reply': 'Агроном 1 сағат ішінде жауап береді. Рахмет!', 'type': 'agronomist'})
    elif chat_type == 'support':
        return jsonify({'reply': 'Сұрағыңыз қолдау қызметіне жіберілді.', 'type': 'support'})
    try:
        client = Groq(api_key=GROQ_API_KEY)
        lang = session.get('lang', 'ru')
        sys_prompt = 'Ты агроном-консультант по яблоководству Казахстана. Отвечай коротко, максимум 3-4 предложения. Без приветствий. Сразу давай практический совет.'
        if lang == 'kz':
            sys_prompt += ' Қазақ тілінде жауап бер.'
        response = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': message}],
            max_tokens=300
        )
        return jsonify({'reply': response.choices[0].message.content, 'type': 'ai'})
    except Exception as e:
        return jsonify({'reply': f'Ошибка: {str(e)}', 'type': 'ai'})

@app.route('/bonus-shop')
@farmer_required
def bonus_shop():
    user = db.get_user_by_id(session['user_id'])
    lang = session.get('lang', 'ru')
    shop_items = [
        {'id': '1', 'icon': '🌿', 'name': 'Удобрение 25кг' if lang=='ru' else 'Тыңайтқыш 25кг', 'description': 'Минеральное удобрение', 'price': 150},
        {'id': '2', 'icon': '💚', 'name': 'Инсектицид 1л' if lang=='ru' else 'Инсектицид 1л', 'description': 'От яблонной плодожорки', 'price': 200},
        {'id': '3', 'icon': '✂️', 'name': 'Садовые ножницы' if lang=='ru' else 'Бақша қайшы', 'description': 'Для обрезки', 'price': 300},
        {'id': '4', 'icon': '🧤', 'name': 'Перчатки' if lang=='ru' else 'Қолғап', 'description': 'Рабочие перчатки', 'price': 100},
        {'id': '5', 'icon': '📊', 'name': 'Консультация агронома' if lang=='ru' else 'Агроном кеңесі', 'description': 'Выезд агронома', 'price': 500},
    ]
    return render_template('bonus_shop.html', user=user, shop_items=shop_items, lang=lang)

@app.route('/bonus-shop/buy', methods=['POST'])
@farmer_required
def buy_bonus_item():
    data = request.get_json()
    price = int(data.get('price', 0))
    user = db.get_user_by_id(session['user_id'])
    if user['bonus_balance'] < price:
        return jsonify({'status': 'error', 'message': 'Недостаточно бонусов'})
    db.update_bonus_balance(session['user_id'], -price)
    return jsonify({'status': 'success'})

@app.route('/harvest')
@farmer_required
def harvest():
    user = db.get_user_by_id(session['user_id'])
    contracts = db.get_contracts(session['user_id'])
    active = [c for c in contracts if c['status'] == 'active']
    return render_template('harvest.html', user=user, contracts=active, lang=session.get('lang','ru'))

@app.route('/harvest/submit', methods=['POST'])
@farmer_required
def submit_harvest():
    db.update_bonus_balance(session['user_id'], 200)
    return jsonify({'status': 'success', 'bonus': 200})

@app.route('/set-lang/<lang>')
def set_lang(lang):
    if lang in ['ru', 'kz']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/agronomist')
@agronomist_required
def agronomist_panel():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_panel'))
    return _get_panel_data('agronomist.html')

@app.route('/admin')
@agronomist_required
def admin_panel():
    return _get_panel_data('admin.html')

def _get_panel_data(template):
    all_users = db.db_get('users')
    farmers = []
    for u in all_users:
        plots = db.db_get('plots', {'user_id': f'eq.{u["id"]}'})
        contracts = db.db_get('contracts', {'user_id': f'eq.{u["id"]}'})
        farmers.append({**u, 'plots_count': len(plots), 'contracts_count': len(contracts)})
    all_contracts_raw = db.db_get('contracts', order='created_at.desc')
    all_contracts = []
    for c in all_contracts_raw:
        user = db.get_user_by_id(c['user_id'])
        plot = db.db_get('plots', {'id': f'eq.{c["plot_id"]}'})
        c['farmer_name'] = user['name'] if user else ''
        c['plot_name'] = plot[0]['name'] if plot else ''
        c['contract_items'] = db.db_get('contract_items', {'contract_id': f'eq.{c["id"]}'})
        all_contracts.append(c)
    pending_contracts = [c for c in all_contracts if c['status'] == 'pending']
    all_tasks_raw = db.db_get('tasks', order='due_date')
    all_tasks = []
    for t in all_tasks_raw:
        user = db.get_user_by_id(t['user_id'])
        plot = db.db_get('plots', {'id': f'eq.{t["plot_id"]}'})
        t['farmer_name'] = user['name'] if user else ''
        t['plot_name'] = plot[0]['name'] if plot else ''
        all_tasks.append(t)
    prices = db.get_demand_prices()
    stats = {
        'farmers': len(farmers),
        'active_contracts': len([c for c in all_contracts if c['status'] == 'active']),
        'pending_contracts': len(pending_contracts),
        'pending_tasks': len([t for t in all_tasks if t['status'] != 'approved']),
        'plots': sum(f['plots_count'] for f in farmers)
    }
    return render_template(template, farmers=farmers, all_contracts=all_contracts,
        pending_contracts=pending_contracts, all_tasks=all_tasks,
        prices=prices, stats=stats, role=session.get('role'), user_name=session.get('user_name'))

@app.route('/agronomist/contract/approve', methods=['POST'])
@agronomist_required
def approve_contract():
    data = request.get_json()
    db.db_update('contracts', {'status': 'active'}, {'id': f'eq.{data["contract_id"]}'})
    return jsonify({'status': 'success'})

@app.route('/agronomist/contract/reject', methods=['POST'])
@agronomist_required
def reject_contract():
    data = request.get_json()
    db.db_update('contracts', {'status': 'rejected'}, {'id': f'eq.{data["contract_id"]}'})
    return jsonify({'status': 'success'})

@app.route('/agronomist/task/approve', methods=['POST'])
@agronomist_required
def approve_task():
    data = request.get_json()
    task_id = data['task_id']
    tasks = db.db_get('tasks', {'id': f'eq.{task_id}'})
    if tasks:
        t = tasks[0]
        db.db_update('tasks', {'status': 'approved'}, {'id': f'eq.{task_id}'})
        db.update_bonus_balance(t['user_id'], t['bonus_amount'])
    return jsonify({'status': 'success'})

@app.route('/agronomist/price/update', methods=['POST'])
@agronomist_required
def update_price():
    data = request.get_json()
    db.db_update('demand_prices',
        {'price_commercial': float(data['price_commercial']), 'price_fallen': float(data['price_fallen'])},
        {'id': f'eq.{data["price_id"]}'}
    )
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
