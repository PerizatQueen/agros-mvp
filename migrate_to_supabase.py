from supabase import create_client
from datetime import datetime, timedelta
import hashlib

SUPABASE_URL = 'https://jyaedutxxtpzhxxeizvp.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5YWVkdXR4eHRwemh4eGVpenZwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MzQ0MjExNCwiZXhwIjoyMDk5MDE4MTE0fQ.u3Cm-9a4OGFb1wLmXQCWVtggUTkQcY3afEENeGyMTjc'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

print('🌾 AgrOS — Загрузка тестовых данных')
print('=' * 40)

# Проверяем есть ли уже данные
try:
    existing = supabase.table('users').select('id').eq('phone', '7771234567').execute()
    if existing.data:
        print('ℹ️  Тестовые данные уже есть!')
        print('📱 Телефон: 7771234567')
        print('🔐 PIN: 1234')
        exit()
except Exception as e:
    print(f'⚠️  Ошибка проверки: {e}')

# 1. Фермер
user = supabase.table('users').insert({
    'phone': '7771234567',
    'name': 'Серик Алматов',
    'pin_hash': hash_pin('1234'),
    'bonus_balance': 250,
    'created_at': datetime.now().isoformat()
}).execute()
user_id = user.data[0]['id']
print(f'✅ Фермер: Серик Алматов')

# 2. Участки
plot1 = supabase.table('plots').insert({
    'user_id': user_id,
    'name': 'Сад Жетысу',
    'area_ha': 5.0,
    'garden_type': 'intensive',
    'lat': 43.2551,
    'lng': 76.9126,
    'address': 'Алматинская область'
}).execute()
plot1_id = plot1.data[0]['id']

plot2 = supabase.table('plots').insert({
    'user_id': user_id,
    'name': 'Верхний сад',
    'area_ha': 3.0,
    'garden_type': 'semi_intensive',
    'lat': 43.2600,
    'lng': 76.9200,
    'address': 'Алматинская область'
}).execute()
plot2_id = plot2.data[0]['id']
print('✅ Участки: Сад Жетысу, Верхний сад')

# 3. Сорта
supabase.table('plot_varieties').insert([
    {'plot_id': plot1_id, 'variety_name': 'Гала', 'area_ha': 3.0, 'expected_yield': 180},
    {'plot_id': plot1_id, 'variety_name': 'Голден', 'area_ha': 2.0, 'expected_yield': 120},
    {'plot_id': plot2_id, 'variety_name': 'Апорт', 'area_ha': 3.0, 'expected_yield': 90},
]).execute()
print('✅ Сорта добавлены')

# 4. Цены
supabase.table('demand_prices').insert([
    {'variety_name': 'Гала', 'price_commercial': 180, 'price_fallen': 40, 'season': '2026'},
    {'variety_name': 'Голден', 'price_commercial': 160, 'price_fallen': 35, 'season': '2026'},
    {'variety_name': 'Апорт', 'price_commercial': 200, 'price_fallen': 45, 'season': '2026'},
    {'variety_name': 'Симиренко', 'price_commercial': 150, 'price_fallen': 30, 'season': '2026'},
]).execute()
print('✅ Цены добавлены')

# 5. Договор
contract = supabase.table('contracts').insert({
    'user_id': user_id,
    'plot_id': plot1_id,
    'status': 'active',
    'total_amount': 57600,
    'created_at': datetime.now().isoformat()
}).execute()
contract_id = contract.data[0]['id']
supabase.table('contract_items').insert([
    {'contract_id': contract_id, 'variety_name': 'Гала', 'volume_kg': 180000, 'price_per_kg': 180},
    {'contract_id': contract_id, 'variety_name': 'Голден', 'volume_kg': 120000, 'price_per_kg': 160},
]).execute()
print('✅ Договор создан')

# 6. Задачи
now = datetime.now()
supabase.table('tasks').insert([
    {'user_id': user_id, 'plot_id': plot1_id, 'title': 'Обрезка деревьев', 'description': 'Провести формирующую обрезку яблонь', 'due_date': (now + timedelta(days=5)).isoformat(), 'status': 'upcoming', 'bonus_amount': 50},
    {'user_id': user_id, 'plot_id': plot1_id, 'title': 'Внесение удобрений', 'description': 'Внести азотные удобрения под корень', 'due_date': (now + timedelta(days=2)).isoformat(), 'status': 'soon', 'bonus_amount': 30},
    {'user_id': user_id, 'plot_id': plot2_id, 'title': 'Обработка от вредителей', 'description': 'Опрыскивание от яблонной плодожорки', 'due_date': (now - timedelta(days=3)).isoformat(), 'status': 'overdue', 'bonus_amount': 40},
    {'user_id': user_id, 'plot_id': plot1_id, 'title': 'Полив сада', 'description': 'Капельный полив — норма 30 л/дерево', 'due_date': (now + timedelta(days=10)).isoformat(), 'status': 'in_progress', 'bonus_amount': 20},
    {'user_id': user_id, 'plot_id': plot2_id, 'title': 'Мониторинг болезней', 'description': 'Осмотр листьев на признаки парши', 'due_date': (now + timedelta(days=1)).isoformat(), 'status': 'approved', 'bonus_amount': 25},
]).execute()
print('✅ Задачи созданы (5 шт)')

print()
print('✅ ГОТОВО!')
print('📱 Телефон: 7771234567')
print('🔐 PIN: 1234')
print('👤 Имя: Серик Алматов')
