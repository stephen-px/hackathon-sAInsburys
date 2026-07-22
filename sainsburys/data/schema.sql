create table users (
  slack_id  text primary key,
  name      text,
  dietary   text[] default '{}',
  taste     jsonb  default '{}'
);

create table products (
  id               serial primary key,
  name             text,
  category         text,
  price            numeric,
  shelf_life_days  int,
  url              text
);

create table meals (
  id          serial primary key,
  name        text,
  description text,
  tags        text[]
);

create table meal_products (
  meal_id    int references meals,
  product_id int references products,
  qty        numeric
);

create table selections (
  id             serial primary key,
  week           date,
  half           text check (half in ('early','late')),
  user_slack_id  text references users,
  meal_id        int references meals,
  freeform       text,
  parsed         jsonb,
  status         text default 'pending'
);

create table orders (
  id            serial primary key,
  week          date,
  delivery_date date,
  status        text default 'draft'
);

create table order_lines (
  order_id   int references orders,
  product_id int references products,
  qty        numeric,
  unit_price numeric
);

create table inventory_lots (
  id            serial primary key,
  product_id    int references products,
  delivery_date date,
  expiry_date   date,
  qty_delivered numeric,
  qty_remaining numeric
);

create table events (
  id            serial primary key,
  ts            timestamptz default now(),
  kind          text check (kind in ('consumed','claimed','wasted')),
  user_slack_id text,
  lot_id        int references inventory_lots,
  qty           numeric,
  value         numeric
);
