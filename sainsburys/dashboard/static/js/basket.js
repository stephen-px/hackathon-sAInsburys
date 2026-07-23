/* basket.js — the Order Basket tab: the single weekly basket + the weekly chart. */

const STATUS_CFG = {
  open:      { bg:'rgba(5,168,49,0.18)',          fg:'var(--color-key-success)',       label:'In trolley', icon:'shopping_cart' },
  delivered: { bg:'rgba(87,140,255,0.18)',        fg:'var(--color-key-primary)',       label:'Delivered',  icon:'local_shipping' },
};
function StatusBadge({ s }) {
  const c = STATUS_CFG[s] || STATUS_CFG.open;
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:4, padding:'0 9px', height:24, borderRadius:99, background:c.bg, color:c.fg, fontSize:11, fontWeight:700 }}>
      <Icon name={c.icon} size={12} color={c.fg} />{c.label}
    </span>
  );
}
function BasketOrder({ order }) {
  const date = (() => {
    try { return 'w/c ' + new Date(order.delivery_date).toLocaleDateString('en-GB', { month:'short', day:'numeric' }); }
    catch { return order.delivery_date; }
  })();
  const accent = order.status==='delivered' ? 'var(--color-key-primary)' : 'var(--color-key-success)';
  return (
    <div style={{ flex:1, background:'var(--color-container-surface-low)', borderRadius:8, padding:16, border:'1px solid var(--color-border-subtle)', borderTop:`2px solid ${accent}` }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:14 }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <Icon name="local_shipping" size={14} color="var(--color-on-surface-subtle)" />
          <span style={{ fontSize:13, fontWeight:600 }}>{date}</span>
        </div>
        <StatusBadge s={order.status} />
      </div>
      {order.lines.map((l,i) => (
        <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
          <span style={{ fontSize:12, color:'var(--color-on-surface-subtle)' }}>
            <span style={{ fontFamily:"'Geist Mono',monospace", color:'var(--color-on-surface)', fontWeight:600 }}>{l.qty}×</span> <ProdLink name={l.name} url={l.url} />
          </span>
          <span style={{ fontFamily:"'Geist Mono',monospace", fontSize:12, color:'var(--color-on-surface-subtle)', marginLeft:8, flexShrink:0 }}>
            {fmt(l.qty * l.unit_price)}
          </span>
        </div>
      ))}
      <div style={{ borderTop:'1px solid var(--color-border-subtle)', marginTop:12, paddingTop:10, display:'flex', justifyContent:'space-between' }}>
        <span style={{ fontSize:11, color:'var(--color-on-surface-subtle)' }}>Total</span>
        <span style={{ fontFamily:"'Geist Mono',monospace", fontSize:15, fontWeight:700 }}>{fmt(order.total)}</span>
      </div>
    </div>
  );
}
function BasketStatus({ basket }) {
  const orders = basket.orders || [];
  return (
    <div style={{ ...card({ padding:0, overflow:'hidden' }) }}>
      <div style={{ padding:'14px 18px', display:'flex', alignItems:'center', gap:8, borderBottom:'1px solid var(--color-border-subtle)' }}>
        <Icon name="shopping_basket" size={16} color="var(--color-key-primary)" />
        <span style={{ fontWeight:600, fontSize:13 }}>This Week's Baskets</span>
        <span style={{ fontSize:11, color:'var(--color-on-surface-subtle)', marginLeft:4 }}>w/c {basket.week}</span>
      </div>
      {orders.length === 0 ? (
        <div style={{ padding:'44px 18px', textAlign:'center', color:'var(--color-on-surface-subtle)' }}>
          <div style={{ fontSize:34, marginBottom:10 }}>🛒</div>
          <div style={{ fontSize:14, fontWeight:600, color:'var(--color-on-surface)' }}>No baskets yet</div>
          <div style={{ fontSize:12, marginTop:4 }}>Run <code>/demo-aggregate</code> to build this week's baskets.</div>
        </div>
      ) : (
        <div style={{ display:'flex', gap:14, padding:18, flexWrap:'wrap' }}>
          {orders.map(o => <BasketOrder key={o.id} order={o} />)}
        </div>
      )}
    </div>
  );
}

/* ── Weekly chart ───────────────────────────────────────────────────── */
function WeeklyChart({ totals }) {
  try {
    if (!totals || totals.length === 0) return null;
    const W=580,H=100,PL=52,PR=12,PB=24;
    const cW = W-PL-PR;
    const max = Math.max(...totals.flatMap(t=>[t.claimed+t.wasted]))*1.15||60;
    const n   = totals.length, colW=cW/n, bW=colW*0.3;
    const yticks = [0, max/2, max].map(v=>({ v, y:H-(v/max)*H }));
    return (
      <div style={{ ...card({ padding:'18px 22px' }) }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:18 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <Icon name="bar_chart" size={16} color="var(--color-on-surface-subtle)" />
            <span style={{ fontWeight:600, fontSize:13 }}>Weekly Impact</span>
          </div>
          <div style={{ display:'flex', gap:20 }}>
            {[['Rescued','#70D913'],['Wasted','#FF5359']].map(([l,c])=>(
              <div key={l} style={{ display:'flex', alignItems:'center', gap:7 }}>
                <div style={{ width:10, height:10, borderRadius:3, background:c }}/>
                <span style={{ fontSize:12, color:'var(--color-on-surface-subtle)' }}>{l}</span>
              </div>
            ))}
          </div>
        </div>
        <svg viewBox={`0 0 ${W} ${H+PB}`} style={{ width:'100%', display:'block', overflow:'visible' }}>
          {yticks.map(t=>(
            <g key={t.y}>
              <line x1={PL} y1={t.y} x2={W-PR} y2={t.y} stroke="var(--color-border-subtle)" strokeWidth={1}/>
              <text x={PL-7} y={t.y+4} textAnchor="end" fontSize={9} fill="var(--color-on-surface-subtle)" fontFamily="Geist Mono,monospace">{fmt(t.v)}</text>
            </g>
          ))}
          {totals.map((t,i)=>{
            const cx=PL+i*colW+colW/2;
            const cH=(t.claimed/max)*H, wH=(t.wasted/max)*H;
            return (
              <g key={i}>
                <rect x={cx-bW-2} y={H-cH} width={bW} height={cH} fill="#70D913" rx={3} opacity={0.9}/>
                <rect x={cx+2}    y={H-wH}  width={bW} height={wH} fill="#FF5359" rx={3} opacity={0.9}/>
                <text x={cx} y={H+PB-3} textAnchor="middle" fontSize={10} fill="var(--color-on-surface-subtle)" fontFamily="Geist,sans-serif">{t.week}</text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  } catch(e) { console.error('[WeeklyChart]',e.message); return null; }
}
