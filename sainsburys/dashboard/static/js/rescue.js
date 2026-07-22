/* rescue.js — the Rescue tab's board: expiry badges, claim button, table. */

function ExpiryBadge({ days }) {
  const pill = (bg, fg, label) => (
    <span style={{
      display:'inline-flex', alignItems:'center',
      padding:'0 9px', height:22, borderRadius:99,
      background:bg, color:fg, fontSize:11, fontWeight:700, whiteSpace:'nowrap',
    }}>{label}</span>
  );
  if (days <= 0)  return pill('var(--color-key-error)',      '#fff',                                   'TODAY');
  if (days === 1) return pill('var(--color-key-warning)',    '#111318',                                '1 day');
  if (days === 2) return pill('rgba(87,140,255,0.2)',        'var(--color-key-primary)',               '2 days');
  return pill('var(--color-border-subtle)', 'var(--color-on-surface-subtle)', `${days} days`);
}

function ClaimBtn({ item, onClaim }) {
  const [h, setH]   = useState(false);
  const [rip, setR] = useState(false);
  const ref         = useRef(null);
  function click(e) {
    try {
      setR(true); setTimeout(()=>setR(false), 600);
      const r = ref.current ? ref.current.getBoundingClientRect() : { left:e.clientX, top:e.clientY, width:0, height:0 };
      boom(r.left + r.width/2, r.top + r.height/2);
      onClaim(item);
    } catch(err) { console.error('[ClaimBtn]',err.message); }
  }
  return (
    <button ref={ref} onClick={click}
      onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{
        position:'relative', overflow:'hidden',
        display:'inline-flex', alignItems:'center', gap:5,
        padding:'0 13px', height:28,
        background: h ? 'rgba(5,168,49,0.22)' : 'rgba(5,168,49,0.1)',
        border:'none',
        boxShadow:'0 0 0 1.5px var(--color-key-success)',
        borderRadius:6,
        color:'var(--color-key-success)',
        cursor:'pointer', fontSize:12, fontWeight:700,
        fontFamily:"'Geist', sans-serif",
        transition:'background 0.15s',
      }}
    >
      {rip && <span style={{
        position:'absolute', top:'50%', left:'50%',
        width:36, height:36, marginTop:-18, marginLeft:-18,
        borderRadius:'50%',
        background:'rgba(5,168,49,0.4)',
        animation:'ripple 0.6s ease forwards',
        pointerEvents:'none',
      }}/>}
      <Icon name="volunteer_activism" size={13} color="var(--color-key-success)" />
      Claim
    </button>
  );
}

function RescueBoard({ items, onClaim }) {
  return (
    <div style={{ ...card({ padding:0, overflow:'hidden', flex:1, minWidth:0 }) }}>
      <div style={{
        padding:'14px 18px', borderBottom:'1px solid var(--color-border-subtle)',
        display:'flex', alignItems:'center', gap:8,
      }}>
        <Icon name="warning" size={16} color="var(--color-key-warning)" />
        <span style={{ fontWeight:600, fontSize:13 }}>Rescue Board</span>
        <span style={{ marginLeft:'auto', fontSize:11, color:'var(--color-on-surface-subtle)' }}>
          {items.length} items at risk · sorted by urgency
        </span>
      </div>
      {items.length === 0 ? (
        <div style={{ padding:'44px 18px', textAlign:'center', color:'var(--color-on-surface-subtle)' }}>
          <div style={{ fontSize:34, marginBottom:10 }}>🎉</div>
          <div style={{ fontSize:14, fontWeight:600, color:'var(--color-on-surface)' }}>Fridge is clear!</div>
          <div style={{ fontSize:12, marginTop:4 }}>Nothing left to rescue — nice work.</div>
        </div>
      ) : (
      <div style={{ overflowX:'auto' }}>
        <table style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead>
            <tr style={{ borderBottom:'1px solid var(--color-border-subtle)', background:'var(--color-container-surface-low)' }}>
              {['Item','Expires','Qty','Value at risk',''].map((h,i) => (
                <th key={i} style={{
                  padding:'8px 16px',
                  textAlign: i>=2 && i<4 ? 'right' : 'left',
                  fontSize:11, fontWeight:600,
                  color:'var(--color-on-surface-subtle)',
                  textTransform:'uppercase', letterSpacing:'0.04em',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => {
              const crit = item.days_left <= 0;
              return (
                <tr key={item.id} style={{
                  borderBottom: i < items.length-1 ? '1px solid var(--color-border-subtle)' : 'none',
                  background: crit ? 'rgba(255,83,89,0.04)' : 'transparent',
                  animation: crit ? 'pulse-red 2.5s ease infinite' : 'none',
                  transition:'background 0.2s',
                }}>
                  <td style={{ padding:'11px 16px', fontSize:13, fontWeight:500 }}>{item.name}</td>
                  <td style={{ padding:'11px 16px' }}><ExpiryBadge days={item.days_left}/></td>
                  <td style={{ padding:'11px 16px', textAlign:'right', fontFamily:"'Geist Mono',monospace", fontSize:12, color:'var(--color-on-surface-subtle)' }}>
                    ×{item.qty_remaining}
                  </td>
                  <td style={{
                    padding:'11px 16px', textAlign:'right',
                    fontFamily:"'Geist Mono',monospace", fontSize:13, fontWeight:600,
                    color: item.days_left<=1 ? 'var(--color-key-error)' : 'var(--color-on-surface)',
                  }}>
                    {fmt(item.qty_remaining * item.price)}
                  </td>
                  <td style={{ padding:'11px 16px' }}>
                    <ClaimBtn item={item} onClaim={onClaim} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
