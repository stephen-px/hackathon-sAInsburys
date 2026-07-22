-- SQLite schema — mirrors schema.sql (Postgres); text[]/jsonb columns stored as JSON text.

create table if not exists users (
  slack_id  text primary key,
  name      text,
  dietary   text default '[]',   -- JSON array
  taste     text default '{}'    -- JSON object
);

create table if not exists products (
  id               integer primary key autoincrement,
  name             text,
  category         text,
  price            real,
  shelf_life_days  integer,
  url              text
);

create table if not exists meals (
  id          integer primary key autoincrement,
  name        text,
  description text,
  tags        text default '[]'  -- JSON array
);

create table if not exists meal_products (
  meal_id    integer references meals(id),
  product_id integer references products(id),
  qty        real
);

create table if not exists selections (
  id             integer primary key autoincrement,
  week           text,            -- ISO date, Monday of the week
  half           text check (half in ('early','late')),
  user_slack_id  text references users(slack_id),
  meal_id        integer references meals(id),
  freeform       text,
  parsed         text,            -- JSON object
  status         text default 'pending'
);

create table if not exists orders (
  id            integer primary key autoincrement,
  week          text,
  delivery_date text,
  status        text default 'draft'
);

create table if not exists order_lines (
  order_id   integer references orders(id),
  product_id integer references products(id),
  qty        real,
  unit_price real
);

create table if not exists inventory_lots (
  id            integer primary key autoincrement,
  product_id    integer references products(id),
  delivery_date text,
  expiry_date   text,
  qty_delivered real,
  qty_remaining real
);

create table if not exists events (
  id            integer primary key autoincrement,
  ts            text default (datetime('now')),
  kind          text check (kind in ('consumed','claimed','wasted')),
  user_slack_id text,
  lot_id        integer references inventory_lots(id),
  qty           real,
  value         real
);

create view if not exists leftovers as
  select l.*, p.name, p.price,
         cast(julianday(l.expiry_date) - julianday(date('now')) as integer) as days_left
  from inventory_lots l join products p on p.id = l.product_id
  where l.qty_remaining > 0;

create view if not exists leaderboard as
  select user_slack_id, sum(value) as saved
  from events where kind = 'claimed'
  group by user_slack_id order by saved desc;

create view if not exists weekly_totals as
  select date(ts, 'weekday 0', '-6 days') as week, kind, sum(value) as total
  from events group by 1, 2;
