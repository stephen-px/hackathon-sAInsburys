create view leftovers as
  select l.*, p.name, p.price,
         (l.expiry_date - current_date) as days_left
  from inventory_lots l join products p on p.id = l.product_id
  where l.qty_remaining > 0;

create view leaderboard as
  select user_slack_id, sum(value) as saved
  from events where kind = 'claimed'
  group by user_slack_id order by saved desc;

create view weekly_totals as
  select date_trunc('week', ts) as week, kind, sum(value) as total
  from events group by 1, 2;
