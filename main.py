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
            if role == 'admin' and pin == ADMIN_PIN:
                session['user_id'] = 'admin'
                session['user_name'] = 'Администратор'
                session['role'] = 'admin'
                return redirect(url_for('admin_panel'))
            if role == 'agronomist' and pin == AGRONOMIST_PIN:
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
    # Фермер отправляет фотоотчёт → «на проверке». Бонус начисляет агроном при одобрении.
    data = request.get_json(silent=True) or {}
    note = (data.get('note') or '').strip()
    photo = data.get('photo') or ''
    if len(photo) > 400000:
        photo = ''
    fields = {'status': 'review', 'report_note': note}
    if photo:
        fields['photo_url'] = photo
    try:
        db.db_update('tasks', fields, {'id': f'eq.{task_id}'})
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/bonus-shop')
@farmer_required
def bonus_shop():
    user = db.get_user_by_id(session['user_id'])
    lg = lang()
    try:
        db_items = db.db_get('bonus_items', {'is_active': 'eq.true'}) or []
    except Exception:
        db_items = []
    if db_items:
        shop_items = [{
            'id': it['id'], 'icon': '🎁', 'name': it.get('name', ''),
            'description': it.get('description', ''), 'price': it.get('cost', 0) or 0,
        } for it in db_items]
    else:
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
    try:
        price = int(float(data.get('price', 0)))
    except Exception:
        price = 0
    item_id = data.get('id')
    item_name = data.get('name', '')
    user = db.get_user_by_id(session['user_id'])
    if user['bonus_balance'] < price:
        return jsonify({'status': 'error', 'message': 'Недостаточно бонусов'})
    db.update_bonus_balance(session['user_id'], -price)
    try:
        db.db_insert('bonus_redemptions', {
            'user_id': session['user_id'], 'farmer_name': user.get('name', ''),
            'item_name': item_name, 'cost': price
        })
        if item_id:
            it = db.db_get('bonus_items', {'id': f'eq.{item_id}'})
            if it and it[0].get('stock') is not None:
                db.db_update('bonus_items', {'stock': max(0, (it[0]['stock'] or 0) - 1)}, {'id': f'eq.{item_id}'})
    except Exception:
        pass
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
    data = request.get_json() or {}
    try:
        commercial = float(data.get('commercial_kg', 0) or 0)
        fallen = float(data.get('fallen_kg', 0) or 0)
    except Exception:
        commercial, fallen = 0, 0
    contracts = [c for c in db.get_contracts(session['user_id']) if c['status'] == 'active']
    contract_id = contracts[0]['id'] if contracts else None
    created = 0
    if commercial > 0:
        dest = 'warehouse' if commercial >= 15000 else 'reception'
        if db.db_insert('trips', {'user_id': session['user_id'], 'contract_id': contract_id,
                'cargo_type': 'commercial', 'volume_kg': commercial, 'destination': dest, 'status': 'planned'}):
            created += 1
    if fallen > 0:
        dest = 'factory' if fallen >= 15000 else 'reception'
        if db.db_insert('trips', {'user_id': session['user_id'], 'contract_id': contract_id,
                'cargo_type': 'fallen', 'volume_kg': fallen, 'destination': dest, 'status': 'planned'}):
            created += 1
    if created == 0:
        return jsonify({'status': 'error', 'message': 'Укажите объёмы (или не создана таблица trips — миграция №2)'})
    db.update_bonus_balance(session['user_id'], 200)
    return jsonify({'status': 'success', 'bonus': 200, 'trips': created})


@app.route('/trips')
@farmer_required
def trips():
    user = db.get_user_by_id(session['user_id'])
    try:
        user_trips = db.db_get('trips', {'user_id': f'eq.{session["user_id"]}'}, order='created_at.desc') or []
    except Exception:
        user_trips = []
    return render_template('my_trips.html', user=user, trips=user_trips, lang=lang())


# ===== АГРОСОПРОВОЖДЕНИЕ =====

@app.route('/agro-support')
@farmer_required
def agro_support():
    user = db.get_user_by_id(session['user_id'])
    try:
        catalog = db.db_get('catalog_items', {'is_active': 'eq.true'}) or []
    except Exception:
        catalog = []
    try:
        orders = db.db_get('agri_orders', {'user_id': f'eq.{session["user_id"]}'}, order='created_at.desc') or []
    except Exception:
        orders = []
    has_contract = any(c['status'] == 'active' for c in db.get_contracts(session['user_id']))
    return render_template('agro_support.html', user=user, catalog=catalog, orders=orders,
                           has_contract=has_contract, lang=lang())


@app.route('/agro-support/order', methods=['POST'])
@farmer_required
def agro_support_order():
    data = request.get_json() or {}
    item_name = (data.get('item_name') or '').strip()
    if not item_name:
        return jsonify({'status': 'error', 'message': 'Выберите товар'})
    try:
        qty = float(data.get('quantity', 1) or 1)
        price = float(data.get('price', 0) or 0)
    except Exception:
        qty, price = 1, 0
    payment = data.get('payment_method', 'cash')
    contracts = [c for c in db.get_contracts(session['user_id']) if c['status'] == 'active']
    contract_id = contracts[0]['id'] if contracts else None
    if payment == 'credit' and not contract_id:
        return jsonify({'status': 'error', 'message': 'Оплата в кредит доступна только при активном договоре'})
    res = db.db_insert('agri_orders', {
        'user_id': session['user_id'], 'contract_id': contract_id,
        'item_name': item_name, 'quantity': qty, 'payment_method': payment,
        'total_amount': price * qty, 'status': 'pending'
    })
    if not res:
        return jsonify({'status': 'error', 'message': 'Не удалось (таблица agri_orders — миграция №2?)'})
    return jsonify({'status': 'success'})


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

    # Роль/активность могут отсутствовать в схеме до миграции — показываем разумные дефолты
    for u in all_users:
        u.setdefault('role', 'farmer')
        u.setdefault('is_active', True)

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
        all_trips_raw = db.db_get('trips', order='created_at.desc') or []
    except Exception:
        all_trips_raw = []
    all_trips = []
    for tr in all_trips_raw:
        try:
            u = db.get_user_by_id(tr['user_id'])
            tr['farmer_name'] = u['name'] if u else ''
        except Exception:
            tr.setdefault('farmer_name', '')
        all_trips.append(tr)

    try:
        all_orders_raw = db.db_get('agri_orders', order='created_at.desc') or []
    except Exception:
        all_orders_raw = []
    all_orders = []
    for o in all_orders_raw:
        try:
            u = db.get_user_by_id(o['user_id'])
            o['farmer_name'] = u['name'] if u else ''
        except Exception:
            o.setdefault('farmer_name', '')
        all_orders.append(o)

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
        all_users=all_users,
        farmers=farmers,
        all_trips=all_trips,
        all_orders=all_orders,
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
    # Агроном одобряет → договор уходит фермеру на подпись (FLOW-002), не активируется сразу
    data = request.get_json() or {}
    db.db_update('contracts', {'status': 'awaiting_sign'}, {'id': f'eq.{data["contract_id"]}'})
    return jsonify({'status': 'success'})


def _auto_create_care_plan(user_id, plot_id):
    # ТЗ 3.6: система создаёт план ухода автоматически при подписании договора
    try:
        if db.db_get('tasks', {'user_id': f'eq.{user_id}'}):
            return
    except Exception:
        return
    plan = [
        ('Весенняя обрезка', 'Санитарная и формирующая обрезка деревьев', '2026-07-15', 30),
        ('Обработка от вредителей', 'Опрыскивание от яблонной плодожорки', '2026-07-25', 40),
        ('Внесение удобрений', 'Азотные удобрения под корень', '2026-08-05', 25),
        ('Мониторинг болезней', 'Осмотр листьев на признаки парши', '2026-08-20', 20),
        ('Подготовка к сбору', 'Проверка готовности плодов к сбору', '2026-09-10', 35),
    ]
    for title, desc, due, bonus in plan:
        try:
            db.db_insert('tasks', {
                'user_id': user_id, 'plot_id': plot_id, 'title': title,
                'description': desc, 'due_date': due, 'status': 'upcoming', 'bonus_amount': bonus
            })
        except Exception:
            pass


@app.route('/contracts/<contract_id>/sign', methods=['POST'])
@farmer_required
def sign_contract(contract_id):
    c = db.db_get('contracts', {'id': f'eq.{contract_id}', 'user_id': f'eq.{session["user_id"]}'})
    if not c:
        return jsonify({'status': 'error', 'message': 'Договор не найден'})
    if c[0].get('status') != 'awaiting_sign':
        return jsonify({'status': 'error', 'message': 'Договор не ожидает подписи'})
    db.db_update('contracts', {'status': 'active'}, {'id': f'eq.{contract_id}'})
    _auto_create_care_plan(session['user_id'], c[0].get('plot_id'))
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


@app.route('/agronomist/trip/advance', methods=['POST'])
@agronomist_required
def advance_trip():
    data = request.get_json() or {}
    trip_id = data.get('trip_id')
    flow = {'planned': 'confirmed', 'confirmed': 'received', 'received': 'paid', 'paid': 'completed'}
    t = db.db_get('trips', {'id': f'eq.{trip_id}'})
    if not t:
        return jsonify({'status': 'error', 'message': 'Рейс не найден'})
    nxt = flow.get(t[0].get('status', 'planned'), 'completed')
    db.db_update('trips', {'status': nxt}, {'id': f'eq.{trip_id}'})
    return jsonify({'status': 'success', 'new_status': nxt})


@app.route('/agronomist/order/decide', methods=['POST'])
@agronomist_required
def decide_agri_order():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    decision = data.get('decision')
    if decision not in ('confirmed', 'rejected'):
        return jsonify({'status': 'error', 'message': 'Некорректное решение'})
    db.db_update('agri_orders', {'status': decision}, {'id': f'eq.{order_id}'})
    return jsonify({'status': 'success'})


# ===== ADMIN: пользователи и каталог =====

@app.route('/admin/user/add', methods=['POST'])
@agronomist_required
def admin_add_user():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip().replace('+', '').replace(' ', '')
    role = data.get('role') or 'farmer'
    region = (data.get('region') or '').strip()
    if not name or not phone:
        return jsonify({'status': 'error', 'message': 'Укажите ФИО и телефон'})
    if db.get_user_by_phone(phone):
        return jsonify({'status': 'error', 'message': 'Пользователь с таким телефоном уже существует'})
    # PIN по умолчанию 0000 — пользователь меняет через «Сброс PIN по SMS»
    res = db.db_insert('users', {
        'name': name, 'phone': phone, 'pin_hash': hash_pin('0000'),
        'role': role, 'region': region, 'is_active': True, 'bonus_balance': 0
    })
    if not res:
        return jsonify({'status': 'error', 'message': 'Не удалось создать. Запущена ли SQL-миграция (колонки role/region/is_active)?'})
    return jsonify({'status': 'success'})


@app.route('/admin/user/toggle/<user_id>', methods=['POST'])
@agronomist_required
def admin_toggle_user(user_id):
    u = db.get_user_by_id(user_id)
    if not u:
        return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
    new_state = not u.get('is_active', True)
    res = db.db_update('users', {'is_active': new_state}, {'id': f'eq.{user_id}'})
    if res == []:
        return jsonify({'status': 'error', 'message': 'Не удалось. Запущена ли SQL-миграция (колонка is_active)?'})
    return jsonify({'status': 'success'})


@app.route('/admin/catalog/add', methods=['POST'])
@agronomist_required
def admin_add_catalog():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Укажите название'})
    try:
        price = float(data.get('price') or 0)
    except Exception:
        price = 0
    res = db.db_insert('catalog_items', {
        'name': name, 'type': data.get('type') or 'service',
        'price': price, 'description': (data.get('description') or '').strip(),
        'is_active': True
    })
    if not res:
        return jsonify({'status': 'error', 'message': 'Не удалось. Создана ли таблица catalog_items (SQL-миграция)?'})
    return jsonify({'status': 'success'})


@app.route('/admin/bonus/add', methods=['POST'])
@agronomist_required
def admin_add_bonus():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Укажите название'})
    try:
        cost = int(float(data.get('cost') or 0))
        stock = int(float(data.get('stock') or 0))
    except Exception:
        cost, stock = 0, 0
    res = db.db_insert('bonus_items', {
        'name': name, 'description': (data.get('description') or '').strip(),
        'cost': cost, 'stock': stock, 'is_active': True
    })
    if not res:
        return jsonify({'status': 'error', 'message': 'Не удалось. Создана ли таблица bonus_items (SQL-миграция)?'})
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
