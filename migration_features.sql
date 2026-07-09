-- AgrOS — миграция №2: рейсы, транспорт, агросопровождение, фотоотчёты задач
-- Выполнить ОДИН РАЗ в Supabase → SQL Editor → Run (Run without RLS).
-- Идемпотентно (IF NOT EXISTS).

-- Транспорт фермера (ТЗ 3.9 / 4.5)
create table if not exists transport (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  brand text,
  vehicle_type text,
  body_type text,
  capacity_kg numeric,
  is_archived boolean default false,
  created_at timestamptz default now()
);
alter table transport disable row level security;

-- Рейсы / сдача урожая (ТЗ 4.5)
create table if not exists trips (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  contract_id uuid references contracts(id) on delete set null,
  cargo_type text,                         -- commercial | fallen
  volume_kg numeric default 0,
  destination text,                        -- reception | warehouse | factory
  transport_id uuid references transport(id) on delete set null,
  slot_date date,
  status text default 'planned',           -- planned|confirmed|receiving|received|paid|completed|cancelled
  created_at timestamptz default now()
);
alter table trips disable row level security;

-- Агросопровождение — заказы (ТЗ 4.6)
create table if not exists agri_orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  contract_id uuid references contracts(id) on delete set null,
  item_name text,
  quantity numeric default 1,
  payment_method text default 'cash',      -- cash | credit
  total_amount numeric default 0,
  status text default 'pending',           -- pending|confirmed|rejected|completed
  created_at timestamptz default now()
);
alter table agri_orders disable row level security;

-- Задачи: фотоотчёт (ТЗ 4.4)
alter table tasks add column if not exists report_note text;
alter table tasks add column if not exists photo_url text;
