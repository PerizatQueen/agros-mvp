-- AgrOS — миграция №4: тикеты, шаблоны ухода, субсидии, слоты
-- Supabase → SQL Editor → Run without RLS. Идемпотентно.

-- Тикеты поддержки — 3-й канал чата
alter table messages add column if not exists channel text default 'agronomist';

-- Субсидии (админ управляет, фермер видит на дашборде)
create table if not exists subsidies (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  org text,
  description text,
  url text,
  is_active boolean default true,
  created_at timestamptz default now()
);
alter table subsidies disable row level security;

-- Слоты пункта приёма (суточная вместимость)
create table if not exists reception_slots (
  id uuid primary key default gen_random_uuid(),
  slot_date date,
  capacity integer default 0,
  booked integer default 0,
  created_at timestamptz default now()
);
alter table reception_slots disable row level security;

-- Шаблоны плана ухода (конструктор агронома)
create table if not exists care_templates (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  month integer,
  bonus_amount integer default 20,
  garden_type text,
  created_at timestamptz default now()
);
alter table care_templates disable row level security;
