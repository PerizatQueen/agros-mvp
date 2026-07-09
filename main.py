import os
import hashlib
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'agros-mvp-secret-2026')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

ADMIN_PHONE = 'admin'
ADMIN_PIN = '9999'
AGRONOMIST_PHONE = 'agro'
AGRONOMIST_PIN = '1111'


def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()


def lang():
    return session.get('lang', 'ru')


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
            if sms_code != '1234':
                return render_template('login.html', step='phone', phone=phone, role=role, error='Неверный SMS-код. Используйте 1234')
            # Новый фермер (нет в базе) → регистрация. Агроном/админ — всегда PIN.
            if role == 'farmer' and not db.get_user_by_phone(phone):
                return render_template('login.html', step='register', phone=phone, role=role)
            return render_template('login.html', step='pin', phone=phone, role=role)
        elif step == 'register':
            name = request.form.get('name', '').strip()
            pin_confirm = request.form.get('pin_confirm', '').strip()
            terms = request.form.get('terms', '')
            if not name:
                return render_template('login.html', step='register', phone=phone, role=role, error='Введите ФИО')
            if not (pin.isdigit() and len(pin) == 4):
                return render_template('login.html', step='register', phone=phone, role=role, name=name, error='PIN должен состоять из 4 цифр')
            if pin != pin_confirm:
                return render_template('login.html', step='register', phone=phone, role=role, name=name, error='PIN-коды не совпадают')
            if not terms:
                return render_template('login.html', step='register', phone=phone, role=role, name=name, error='Примите условия использования')
            if db.get_user_by_phone(phone):
                return render_template('login.html', step='pin', phone=phone, role=role, error='Аккаунт уже существует. Введите PIN.')
            new_user = db.create_user(phone, name, hash_pin(pin), bonus_balance=100)
            if not new_user:
                return render_template('login.html', step='register', phone=phone, role=role, name=name, error='Не удалось создать аккаунт. Попробуйте позже.')
            session['user_id'] = new_user['id']
            session['user_name'] = new_user['name']
            session['role'] = 'farmer'
            return redirect(url_for('dashboard') + '?bonus=100')
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


@app.route('/set-lang/<lg>')
def set_lang(lg):
    if lg in ['ru', 'kz']:
        session['lang'] = lg
    ref = request.referrer
    if ref:
        return redirect(ref)
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_panel'))
    elif role == 'agronomist':
        return redirect(url_for('agronomist_panel'))
    return redirect(url_for('dashboard'))


# ===== FARMER ROUTES =====

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
    return render_template('dashboard.html',
        user=user, plots=plots, contracts=active_contracts,
        tasks=upcoming_tasks, overdue_tasks=overdue_tasks, prices=prices[:4],
        has_plots=len(plots) > 0, has_contracts=len(contracts) > 0,
        has_active=len(active_contracts) > 0, lang=lang())


@app.route('/plots')
@farmer_required
def plots():
    user = db.get_user_by_id(session['user_id'])
    user_plots = db.get_plots(session['user_id'])
    plots_json = json.dumps([{
        'name': p.get('name', ''),
        'area_ha': p.get('area_ha', 0),
        'address': p.get('address', ''),
        'lat': p.get('lat') or p.get('latitude'),
        'lng': p.get('lng') or p.get('longitude')
    } for p in user_plots])
    return render_template('plots.html', user=user, plots=user_plots, plots_json=plots_json, lang=lang())


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
            except Exception:
                varieties = []
            db.create_plot(
                session['user_id'],
                request.form.get('name'),
                request.form.get('area_ha'),
                request.form.get('garden_type'),
                request.form.get('lat', '43.2551'),
                request.form.get('lng', '76.9126'),
                request.form.get('address', ''),
                varieties
            )
            db.update_bonus_balance(session['user_id'], 100)
            return redirect(url_for('plots') + '?bonus=100')
        return render_template('plots_create.html', user=user, step=int(step), form_data=request.form, lang=lang())
    return render_template('plots_create.html', user=user, step=1, form_data={}, lang=lang())


@app.route('/demand')
@farmer_required
def demand():
    user = db.get_user_by_id(session['user_id'])
    prices = db.get_demand_prices()
    user_plots = db.get_plots(session['user_id'])
    user_varieties = set()
    for p in user_plots:
        for v in p.get('varieties', []):
            user_varieties.add(v['variety_name'])
    for price in prices:
        price['on_my_plot'] = price['variety_name'] in user_varieties
    return render_template('demand.html', user=user, prices=prices, user_varieties=user_varieties, lang=lang())


@app.route('/contracts')
@farmer_required
def contracts():
    user = db.get_user_by_id(session['user_id'])
    user_contracts = db.get_contracts(session['user_id'])
    return render_template('contracts.html', user=user, contracts=user_contracts, lang=lang())


@app.route('/contracts/create', methods=['GET', 'POST'])
@farmer_required
def create_contract():
    user = db.get_user_by_id(session['user_id'])
    user_plots = db.get_plots(session['user_id'])
    prices = db.get_demand_prices()
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        if user['pin_hash'] != hash_pin(pin):
            return render_template('contracts_create.html', user=user, plots=user_plots, prices=prices,
                                   error='Неверный PIN-код', lang=lang())
        plot_id = request.form.get('plot_id')
        items_json = request.form.get('items_json', '[]')
        try:
            items = json.loads(items_json)
        except Exception:
            items = []
        db.create_contract(session['user_id'], plot_id, items)
        db.update_bonus_balance(session['user_id'], 50)
        return redirect(url_for('contracts') + '?bonus=50')
    return render_template('contracts_create.html', user=user, plots=user_plots, prices=prices, lang=lang())


@app.route('/tasks')
@farmer_required
def tasks():
    user = db.get_user_by_id(session['user_id'])
    month = request.args.get('month', type=int)
    try:
        user_tasks = db.get_tasks(session['user_id'], month)
    except Exception:
        user_tasks = []
    return render_template('tasks.html', user=user, tasks=user_tasks, current_month=month, lang=lang())


@app.route('/tasks/<task_id>/complete', methods=['POST'])
@farmer_required
def complete_task(task_id):
    try:
        bonus, new_balance = db.complete_task(task_id, session['user_id'])
        return jsonify({'status': 'success', 'bonus': bonus, 'new_balance': new_balance})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/bonus-shop')
@farmer_required
def bonus_shop():
    user = db.get_user_by_id(session['user_id'])
    lg = lang()
    shop_items = [
        {'id': '1', 'icon': '🌿', 'name': 'Удобрение 25кг' if lg == 'ru' else 'Тыңайтқыш 25кг', 'description': 'Минеральное удобрение', 'price': 150},
        {'id': '2', 'icon': '💚', 'name': 'Инсектицид 1л' if lg == 'ru' else 'Инсектицид 1л', 'description': 'От яблонной плодожорки', 'price': 200},
        {'id': '3', 'icon': '✂️', 'name': 'Садовые ножницы' if lg == 'ru' else 'Бақша қайшы', 'description': 'Для обрезки', 'price': 300},
        {'id': '4', 'icon': '🧤', 'name': 'Перчатки' if lg == 'ru' else 'Қолғап', 'description': 'Рабочие перчатки', 'price': 100},
        {'id': '5', 'icon': '📊', 'name': 'Консультация агронома' if lg == 'ru' else 'Агроном кеңесі', 'description': 'Выезд агронома', 'price': 500},
    ]
    return render_template('bonus_shop.html', user=user, shop_items=shop_items, lang=lg)


@app.route('/bonus-shop/buy', methods=['POST'])
@farmer_required
def buy_bonus_item():
    data = request.get_json() or {}
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
    user_contracts = db.get_contracts(session['user_id'])
    active = [c for c in user_contracts if c['status'] == 'active']
    return render_template('harvest.html', user=user, contracts=active, lang=lang())


@app.route('/harvest/submit', methods=['POST'])
@farmer_required
def submit_harvest():
    db.update_bonus_balance(session['user_id'], 200)
    return jsonify({'status': 'success', 'bonus': 200})


# ===== CHAT =====

@app.route('/chat')
@login_required
def chat():
    user = None
    if session.get('role') == 'farmer':
        user = db.get_user_by_id(session['user_id'])
    return render_template('chat.html', user=user, lang=lang())


@app.route('/chat/message', methods=['POST'])
@login_required
def chat_message():
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'reply': 'Пустое сообщение', 'type': 'ai'})
    if not GROQ_API_KEY:
        return jsonify({'reply': 'GROQ_API_KEY не настроен на сервере. Добавьте переменную в Railway.', 'type': 'ai'})
    try:
        import requests as _req
        lg = lang()
        sys_prompt = ('Ты — AI-агроном платформы AgrOS. Помогаешь фермерам и агрономам Казахстана. '
                      'Отвечай коротко (3-4 предложения), без приветствий, сразу давай практический совет. '
                      'Отвечай на том языке, на котором задан вопрос — русском или казахском. '
                      'Сен — AgrOS AI-агрономысың. Сұрақ қандай тілде болса, сол тілде жауап бер.')
        _resp = _req.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'llama-3.1-8b-instant',
                'messages': [
                    {'role': 'system', 'content': sys_prompt},
                    {'role': 'user', 'content': message}
                ],
                'max_tokens': 400
            },
            timeout=30
        )
        _resp.raise_for_status()
        reply = _resp.json()['choices'][0]['message']['content']
        return jsonify({'reply': reply, 'type': 'ai'})
    except Exception as e:
        return jsonify({'reply': f'Ошибка AI: {str(e)}', 'type': 'ai'})


# ===== AGRONOMIST / ADMIN PANELS =====

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
    try:
        all_users = db.db_get('users') or []
    except Exception:
        all_users = []
    farmers = []
    for u in all_users:
        try:
            plots = db.db_get('plots', {'user_id': f'eq.{u["id"]}'}) or []
            user_contracts = db.db_get('contracts', {'user_id': f'eq.{u["id"]}'}) or []
        except Exception:
            plots, user_contracts = [], []
        farmers.append({**u, 'plots_count': len(plots), 'contracts_count': len(user_contracts)})

    try:
        all_contracts_raw = db.db_get('contracts', order='created_at.desc') or []
    except Exception:
        all_contracts_raw = []
    all_contracts = []
    for c in all_contracts_raw:
        try:
            u = db.get_user_by_id(c['user_id'])
            plot = db.db_get('plots', {'id': f'eq.{c["plot_id"]}'})
            c['farmer_name'] = u['name'] if u else ''
            c['plot_name'] = plot[0]['name'] if plot else ''
            c['contract_items'] = db.db_get('contract_items', {'contract_id': f'eq.{c["id"]}'}) or []
        except Exception:
            c.setdefault('farmer_name', '')
            c.setdefault('plot_name', '')
            c.setdefault('contract_items', [])
        all_contracts.append(c)

    pending_contracts = [c for c in all_contracts if c.get('status') == 'pending']

    try:
        all_tasks_raw = db.db_get('tasks', order='due_date') or []
    except Exception:
        all_tasks_raw = []
    all_tasks = []
    for t in all_tasks_raw:
        try:
            u = db.get_user_by_id(t['user_id'])
            plot = db.db_get('plots', {'id': f'eq.{t["plot_id"]}'})
            t['farmer_name'] = u['name'] if u else ''
            t['plot_name'] = plot[0]['name'] if plot else ''
        except Exception:
            t.setdefault('farmer_name', '')
            t.setdefault('plot_name', '')
        all_tasks.append(t)

    try:
        prices = db.get_demand_prices() or []
    except Exception:
        prices = []

    try:
        bonus_items = db.db_get('bonus_items') or []
    except Exception:
        bonus_items = []

    try:
        bonus_redemptions = db.db_get('bonus_redemptions', order='created_at.desc') or []
    except Exception:
        bonus_redemptions = []

    try:
        catalog_items = db.db_get('catalog_items') or []
    except Exception:
        catalog_items = []

    stats = {
        'farmers': len(farmers),
        'active_contracts': len([c for c in all_contracts if c.get('status') == 'active']),
        'pending_contracts': len(pending_contracts),
        'pending_tasks': len([t for t in all_tasks if t.get('status') != 'approved']),
        'plots': sum(f.get('plots_count', 0) for f in farmers)
    }

    return render_template(template,
        farmers=farmers,
        all_contracts=all_contracts,
        pending_contracts=pending_contracts,
        all_tasks=all_tasks,
        prices=prices,
        stats=stats,
        bonus_items=bonus_items,
        bonus_redemptions=bonus_redemptions,
        catalog_items=catalog_items,
        role=session.get('role'),
        user_name=session.get('user_name'),
        lang=lang()
    )


@app.route('/agronomist/contract/approve', methods=['POST'])
@agronomist_required
def approve_contract():
    data = request.get_json() or {}
    db.db_update('contracts', {'status': 'active'}, {'id': f'eq.{data["contract_id"]}'})
    return jsonify({'status': 'success'})


@app.route('/agronomist/contract/reject', methods=['POST'])
@agronomist_required
def reject_contract():
    data = request.get_json() or {}
    db.db_update('contracts', {'status': 'rejected'}, {'id': f'eq.{data["contract_id"]}'})
    return jsonify({'status': 'success'})


@app.route('/agronomist/task/approve', methods=['POST'])
@agronomist_required
def approve_task():
    data = request.get_json() or {}
    task_id = data.get('task_id')
    try:
        task_list = db.db_get('tasks', {'id': f'eq.{task_id}'})
        if task_list:
            t = task_list[0]
            db.db_update('tasks', {'status': 'approved'}, {'id': f'eq.{task_id}'})
            db.update_bonus_balance(t['user_id'], t['bonus_amount'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    return jsonify({'status': 'success'})


@app.route('/agronomist/price/update', methods=['POST'])
@agronomist_required
def update_price():
    data = request.get_json() or {}
    try:
        db.db_update('demand_prices',
            {'price_commercial': float(data['price_commercial']), 'price_fallen': float(data['price_fallen'])},
            {'id': f'eq.{data["price_id"]}'}
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
