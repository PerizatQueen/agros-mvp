-- AgrOS — миграция для админ-панели (пользователи, каталог, бонусы)
-- Выполнить ОДИН РАЗ в Supabase → SQL Editor → New query → Run
-- Безопасно к повторному запуску (IF NOT EXISTS / IF EXISTS).

-- 1. users: роль, активность, район
alter table users add column if not exists role text default 'farmer';
alter table users add column if not exists is_active boolean default true;
alter table users add column if not exists region text;
update users set role = 'farmer' where role is null;
update users set is_active = true where is_active is null;

-- 2. Каталог агросопровождения (админ → Каталог)
create table if not exists catalog_items (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text default 'service',
  price numeric default 0,
  description text,
  is_active boolean default true,
  created_at timestamptz default now()
);
alter table catalog_items disable row level security;

-- 3. Магазин бонусов (админ → Магазин бонусов)
create table if not exists bonus_items (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  cost integer default 0,
  stock integer default 0,
  is_active boolean default true,
  created_at timestamptz default now()
);
alter table bonus_items disable row level security;

create table if not exists bonus_redemptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete set null,
  farmer_name text,
  item_name text,
  cost integer default 0,
  created_at timestamptz default now()
);
alter table bonus_redemptions disable row level security;

-- 4. (необязательно) стартовый каталог для демо
insert into catalog_items (name, type, price, description) values
  ('Минеральное удобрение 25кг', 'product', 8500, 'Комплексное NPK'),
  ('Опрыскивание от плодожорки', 'service', 15000, 'Выезд бригады, 1 га'),
  ('Секатор садовый', 'equipment', 6000, 'Профессиональный')
on conflict do nothing;
