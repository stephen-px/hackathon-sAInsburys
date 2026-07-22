/* widgets.js — shared dashboard chrome and cross-tab widgets. */

/* ── Toast ──────────────────────────────────────────────────────────── */
function Toast({ t, onClose }) {
  useEffect(() => { const id = setTimeout(onClose, 4000); return ()=>clearTimeout(id); }, []);
  return (
    <div onClick={onClose} style={{
      background: 'var(--color-container-surface)',
      borderRadius: 10,
      boxShadow: '0 8px 32px rgba(0,0,0,0.5), inset 0 0 0 1px var(--color-key-primary)',
      padding: '14px 18px',
      display: 'flex', alignItems: 'center', gap: 14,
      animation: 'toast-in 0.4s cubic-bezier(0.34,1.56,0.64,1)',
      cursor: 'pointer', minWidth: 280, maxWidth: 340,
    }}>
      <span style={{ fontSize: 32, lineHeight: 1 }}>{t.emoji}</span>
      <div>
        <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-key-primary)', marginBottom: 3 }}>{t.title}</div>
        <div style={{ fontSize: 12, color: 'var(--color-on-surface-subtle)' }}>{t.body}</div>
      </div>
    </div>
  );
}

/* ── Header ─────────────────────────────────────────────────────────── */
function Header({ theme, onToggle, live, onSim }) {
  const [h, setH] = useState(false);
  return (
    <header style={{
      height: 54,
      background: 'var(--color-surface-1)',
      borderBottom: '1px solid var(--color-border-subtle)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 28px', position: 'sticky', top: 0, zIndex: 100,
      backdropFilter: 'blur(12px)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, overflow: 'hidden',
        }}>
          <Morrison size={40} />
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.1 }}>sAInsburys</div>
          <div style={{ fontSize: 11, color: 'var(--color-on-surface-subtle)', letterSpacing: '0.04em' }}>WASTE THE DIFFERENCE</div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          onClick={onSim}
          onMouseEnter={()=>setH(true)}
          onMouseLeave={()=>setH(false)}
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '0 16px', height: 34,
            background: h ? 'rgba(87,140,255,0.22)' : 'rgba(87,140,255,0.1)',
            border: 'none',
            boxShadow: '0 0 0 1.5px var(--color-key-primary)',
            borderRadius: 6,
            color: 'var(--color-key-primary)',
            cursor: 'pointer', fontSize: 12, fontWeight: 700,
            fontFamily: "'Geist', sans-serif",
            transition: 'background 0.15s, box-shadow 0.15s',
            letterSpacing: '0.02em',
          }}
        >
          <Icon name="bolt" size={15} color="var(--color-key-primary)" />
          Simulate Claim
        </button>

        {live && (
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            <div style={{
              width:7, height:7, borderRadius:'50%',
              background:'var(--color-key-success)',
              boxShadow:'0 0 0 3px rgba(5,168,49,0.25)',
            }}/>
            <span style={{ fontSize:11, color:'var(--color-key-success)', fontWeight:600 }}>LIVE</span>
          </div>
        )}

        <button onClick={onToggle} style={{
          width:34, height:34, display:'flex', alignItems:'center', justifyContent:'center',
          background:'transparent', border:'none', borderRadius:6,
          color:'var(--color-on-surface-subtle)', cursor:'pointer',
        }}>
          <Icon name={theme==='dark'?'light_mode':'dark_mode'} size={18} />
        </button>
      </div>
    </header>
  );
}

/* ── Float-up ───────────────────────────────────────────────────────── */
function FloatUp({ value, onDone }) {
  useEffect(() => { const t = setTimeout(onDone, 2000); return ()=>clearTimeout(t); }, []);
  return (
    <span style={{
      position:'absolute', left:'50%', bottom:56,
      pointerEvents:'none',
      color:'var(--color-key-success)',
      fontSize:26, fontWeight:800,
      animation:'float-up 2s ease-out forwards',
      whiteSpace:'nowrap',
      textShadow:'0 0 28px rgba(5,168,49,0.7)',
      zIndex:2, letterSpacing:'-0.01em',
    }}>+{fmt(value)}</span>
  );
}

/* ── Hero ───────────────────────────────────────────────────────────── */
function Hero({ total, floats, onExpireFloat }) {
  const smooth = useSmoothVal(total, 900);
  const numRef = useRef(null);
  const prev   = useRef(total);
  useEffect(() => {
    try {
      if (numRef.current && total !== prev.current) {
        numRef.current.style.animation='none';
        void numRef.current.offsetHeight;
        numRef.current.style.animation='count-bounce 0.55s cubic-bezier(0.34,1.56,0.64,1)';
        prev.current = total;
      }
    } catch(e) { console.error('[Hero]',e.message); }
  }, [total]);

  const mile    = nextMile(total);
  const prevM   = MILES[MILES.indexOf(mile)-1] || 0;
  const milePct = Math.min(((total - prevM) / (mile - prevM)) * 100, 100);

  return (
    <div style={{
      textAlign:'center', padding:'52px 32px 38px',
      borderRadius:12, position:'relative', overflow:'hidden',
      background:'var(--color-container-surface)',
      boxShadow:'0 8px 32px var(--color-elevation-2-shadow), inset 0 0 0 1px var(--color-elevation-inset)',
    }}>
      {/* Radial glow */}
      <div style={{
        position:'absolute', inset:0, pointerEvents:'none',
        background:'radial-gradient(ellipse 70% 80% at 50% 110%, rgba(87,140,255,0.18) 0%, transparent 70%)',
        animation:'glow 4s ease-in-out infinite',
      }}/>

      <div style={{ position:'relative', marginBottom:12 }}>
        <Morrison size={100} />
      </div>

      <div style={{
        fontSize:11, letterSpacing:'0.14em', textTransform:'uppercase',
        color:'var(--color-on-surface-subtle)', marginBottom:18, position:'relative',
      }}>
        Total rescued this week
      </div>

      <div ref={numRef} style={{
        fontSize:96, fontWeight:200, letterSpacing:'-0.04em', lineHeight:1,
        color:'var(--color-key-primary)', position:'relative',
        fontFamily:"'Geist', sans-serif",
        textShadow:'0 0 80px rgba(87,140,255,0.3)',
      }}>
        {fmt(smooth)}
      </div>

      <div style={{ fontSize:14, color:'var(--color-on-surface-subtle)', marginTop:16, position:'relative' }}>
        saved from the bin 🎉 — helping the planet, one falafel at a time
      </div>

      {/* Milestone bar */}
      <div style={{ maxWidth:480, margin:'28px auto 0', position:'relative' }}>
        <div style={{
          display:'flex', justifyContent:'space-between',
          fontSize:11, color:'var(--color-on-surface-subtle)', marginBottom:8,
        }}>
          <span>Next milestone</span>
          <span style={{ color:'var(--color-key-primary)', fontWeight:700 }}>
            {fmt(total)} / {fmt(mile)}
          </span>
        </div>
        <div style={{ height:8, background:'var(--color-border-subtle)', borderRadius:99, overflow:'hidden', position:'relative' }}>
          <div style={{
            height:'100%', width:`${milePct}%`, borderRadius:99,
            background:'linear-gradient(90deg, var(--color-key-primary) 0%, #70D913 100%)',
            transition:'width 1.1s cubic-bezier(0.4,0,0.2,1)',
            boxShadow:'0 0 16px rgba(87,140,255,0.5)',
          }}/>
        </div>
        <div style={{ display:'flex', justifyContent:'space-between', marginTop:6 }}>
          {MILES.filter(m => m <= mile * 1.2 && m >= prevM).map(m => {
            const hit = total >= m;
            const p   = Math.min(((m - prevM) / (mile - prevM)) * 100, 100);
            return (
              <div key={m} style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:2 }}>
                <div style={{ width:2, height:6, background: hit ? 'var(--color-key-primary)' : 'var(--color-border-subtle)', borderRadius:1 }}/>
                <span style={{ fontSize:9, fontWeight: hit?700:400, color: hit ? 'var(--color-key-primary)' : 'var(--color-on-surface-subtle)' }}>
                  {hit ? '✓' : ''}{fmt(m)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {floats.map(f => <FloatUp key={f.id} value={f.value} onDone={()=>onExpireFloat(f.id)}/>)}
    </div>
  );
}

/* ── Stat tiles ─────────────────────────────────────────────────────── */
function StatTile({ icon, value, label, accent, sub }) {
  return (
    <div style={{
      ...card({ padding:'18px 20px' }),
      display:'flex', flexDirection:'column', gap:10,
      borderTop:`2px solid ${accent}`,
      animation:'slide-up 0.4s ease both',
    }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <span style={{ fontSize:11, color:'var(--color-on-surface-subtle)', fontWeight:500, letterSpacing:'0.04em', textTransform:'uppercase' }}>
          {label}
        </span>
        <Icon name={icon} size={17} color={accent} />
      </div>
      <div style={{ fontSize:32, fontWeight:300, letterSpacing:'-0.02em', lineHeight:1, color:'var(--color-on-surface)' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize:11, color:'var(--color-on-surface-subtle)', borderTop:'1px solid var(--color-border-subtle)', paddingTop:8 }}>{sub}</div>}
    </div>
  );
}

/* ── Fridge HP ──────────────────────────────────────────────────────── */
function FridgeHP({ rescue }) {
  const expiring = rescue.filter(r => r.days_left <= 1).length;
  const total    = rescue.length || 1;
  const hp       = Math.round(((total - expiring) / total) * 100);
  const color    = hp > 65 ? '#70D913' : hp > 35 ? 'var(--color-key-warning)' : 'var(--color-key-error)';
  const label    = hp > 65 ? 'Healthy' : hp > 35 ? 'At Risk' : 'Critical';
  const TICKS    = [0,20,40,60,80,100];
  return (
    <div style={{ ...card({ padding:'18px 22px' }) }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:14 }}>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <Icon name="kitchen" size={17} color={color} />
          <span style={{ fontWeight:600, fontSize:13 }}>Fridge HP</span>
          <span style={{ fontSize:36, fontWeight:200, lineHeight:1, color, fontFamily:"'Geist Mono',monospace" }}>{hp}</span>
          <span style={{ fontSize:13, color:'var(--color-on-surface-subtle)', marginTop:4 }}>/ 100</span>
          <span style={{
            fontSize:11, fontWeight:700, padding:'2px 10px', borderRadius:99,
            background:color, color:'#111318', marginLeft:4,
          }}>{label}</span>
        </div>
        <div style={{ display:'flex', gap:20, fontSize:11, color:'var(--color-on-surface-subtle)' }}>
          <span style={{ color:'var(--color-key-error)', fontWeight:600 }}>{expiring} expiring soon</span>
          <span>{total-expiring} safe</span>
        </div>
      </div>
      <div style={{ position:'relative' }}>
        <div style={{ height:12, background:'var(--color-border-subtle)', borderRadius:99, overflow:'hidden' }}>
          <div style={{
            height:'100%', width:`${hp}%`, borderRadius:99,
            background:`linear-gradient(90deg, ${hp<=35?'var(--color-key-error)':'var(--color-key-success)'} 0%, ${color} 100%)`,
            transition:'width 900ms cubic-bezier(0.4,0,0.2,1)',
            boxShadow:`0 0 18px ${color}55`,
          }}/>
        </div>
        <div style={{ display:'flex', justifyContent:'space-between', marginTop:5 }}>
          {TICKS.map(t => (
            <div key={t} style={{ display:'flex', flexDirection:'column', alignItems:'center' }}>
              <div style={{
                width:1, height:5,
                background: hp>=t ? color : 'var(--color-border-subtle)',
                animation: hp>=t && hp<t+20 ? 'hp-flash 1.2s ease-in-out infinite' : 'none',
              }}/>
              <span style={{ fontSize:9, color:'var(--color-on-surface-subtle)', marginTop:2 }}>{t}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Activity feed ──────────────────────────────────────────────────── */
const EV_ICONS = { claimed:'🥗', consumed:'✅', wasted:'😬' };
function ActivityFeed({ events }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = 0; }, [events.length]);
  return (
    <div style={{ ...card({ padding:0, overflow:'hidden', width:272, flexShrink:0 }) }}>
      <div style={{
        padding:'13px 18px', borderBottom:'1px solid var(--color-border-subtle)',
        display:'flex', alignItems:'center', gap:8,
      }}>
        <Icon name="bolt" size={15} color="var(--color-key-primary)" />
        <span style={{ fontWeight:600, fontSize:13 }}>Live Activity</span>
        <span style={{
          marginLeft:'auto', fontSize:10, fontWeight:700,
          padding:'1px 7px', borderRadius:99,
          background:'rgba(87,140,255,0.15)', color:'var(--color-key-primary)',
          letterSpacing:'0.05em',
        }}>LIVE</span>
      </div>
      <div ref={ref} style={{ maxHeight:310, overflowY:'auto', padding:'4px 0' }}>
        {events.length === 0 && (
          <div style={{ padding:'28px 18px', color:'var(--color-on-surface-subtle)', fontSize:12, textAlign:'center' }}>
            <div style={{ fontSize:28, marginBottom:8 }}>👀</div>
            Watching for activity…
          </div>
        )}
        {events.map((ev, i) => (
          <div key={ev.id} style={{
            padding:'9px 18px', display:'flex', alignItems:'center', gap:10,
            borderBottom: i < events.length-1 ? '1px solid var(--color-border-subtle)' : 'none',
            animation: i===0 ? 'feed-enter 0.3s ease' : 'none',
          }}>
            <span style={{ fontSize:18, flexShrink:0 }}>{EV_ICONS[ev.kind] || '📦'}</span>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ fontSize:12, fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {ev.user}
              </div>
              <div style={{ fontSize:11, color:'var(--color-on-surface-subtle)', marginTop:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {ev.item}
              </div>
            </div>
            <span style={{
              fontFamily:"'Geist Mono',monospace", fontSize:12, flexShrink:0,
              color: ev.kind==='claimed' ? 'var(--color-key-success)' : 'var(--color-on-surface-subtle)',
              fontWeight:600,
            }}>+{fmt(ev.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Department Battle ──────────────────────────────────────────────── */
function DeptBattle({ departments }) {
  const entries  = Object.entries(departments).sort((a,b)=>b[1]-a[1]);
  const totalVal = entries.reduce((s,[,v])=>s+v,0)||1;
  const COLORS   = ['var(--color-key-primary)','#70D913','#e96d00','#FF5359'];
  const winner   = entries[0][0];
  return (
    <div style={{ ...card({ padding:'18px 22px', flex:1 }) }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:18 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <Icon name="groups" size={16} color="var(--color-key-primary)" />
          <span style={{ fontWeight:600, fontSize:13 }}>Department Battle</span>
        </div>
        <span style={{ fontSize:12, color:'#DC9E17', fontWeight:700 }}>🏆 {winner} is winning</span>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
        {entries.map(([dept, val], i) => {
          const pct = (val / totalVal) * 100;
          return (
            <div key={dept}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
                <span style={{ fontSize:13, fontWeight: i===0 ? 700 : 400 }}>{dept}</span>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <span style={{ fontFamily:"'Geist Mono',monospace", fontSize:12, color:COLORS[i], fontWeight:600 }}>
                    {fmt(val)}
                  </span>
                  <span style={{ fontSize:11, color:'var(--color-on-surface-subtle)' }}>
                    {Math.round(pct)}%
                  </span>
                </div>
              </div>
              <div style={{ height:10, background:'var(--color-border-subtle)', borderRadius:99, overflow:'hidden' }}>
                <div style={{
                  height:'100%', width:`${pct}%`, borderRadius:99,
                  background:COLORS[i],
                  transition:'width 1.3s cubic-bezier(0.4,0,0.2,1)',
                  boxShadow: i===0 ? `0 0 12px ${COLORS[i]}55` : 'none',
                }}/>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{
        marginTop:16, padding:'10px 14px', borderRadius:8,
        background:'var(--color-container-surface-low)',
        fontSize:11, color:'var(--color-on-surface-subtle)', textAlign:'center',
      }}>
        💪 Claim an item to push your department ahead
      </div>
    </div>
  );
}

/* ── Weekly challenge ───────────────────────────────────────────────── */
function WeeklyChallenge({ saved, challenge }) {
  const pct  = Math.min((saved / challenge.goal) * 100, 100);
  const done = saved >= challenge.goal;
  return (
    <div style={{ ...card({ padding:'18px 22px', width:280, flexShrink:0 }) }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
        <Icon name="military_tech" size={16} color="#DC9E17" />
        <span style={{ fontWeight:600, fontSize:13 }}>Weekly Challenge</span>
        {done && (
          <span style={{
            marginLeft:'auto', fontSize:10, fontWeight:700,
            padding:'2px 8px', borderRadius:99,
            background:'rgba(5,168,49,0.18)', color:'var(--color-key-success)',
          }}>✓ COMPLETE</span>
        )}
      </div>
      <div style={{ fontSize:12, color:'var(--color-on-surface-subtle)', marginBottom:14 }}>{challenge.label}</div>
      <div style={{ height:10, background:'var(--color-border-subtle)', borderRadius:99, overflow:'hidden', marginBottom:8 }}>
        <div style={{
          height:'100%', width:`${pct}%`, borderRadius:99,
          background: done
            ? 'linear-gradient(90deg, var(--color-key-success), #70D913)'
            : 'linear-gradient(90deg, var(--color-key-primary), #70D913)',
          transition:'width 1.2s cubic-bezier(0.4,0,0.2,1)',
          boxShadow: done ? '0 0 14px rgba(5,168,49,0.5)' : 'none',
        }}/>
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'var(--color-on-surface-subtle)' }}>
        <span style={{ color: done ? 'var(--color-key-success)' : 'var(--color-on-surface)', fontWeight:600 }}>
          {fmt(saved)}
        </span>
        <span>Goal {fmt(challenge.goal)}</span>
      </div>
      <div style={{
        marginTop:14, padding:'10px 14px', borderRadius:8,
        background:'var(--color-container-surface-low)',
        fontSize:11, display:'flex', alignItems:'center', gap:6,
      }}>
        <span>⚡</span>
        <span style={{ color:'var(--color-on-surface-subtle)' }}>
          Complete for <span style={{ color:'#DC9E17', fontWeight:700 }}>+500 bonus XP</span>
        </span>
      </div>
    </div>
  );
}

/* ── Tab bar ────────────────────────────────────────────────────────── */
const TABS = [
  { id: 'rescue',      label: 'Rescue',       icon: 'volunteer_activism' },
  { id: 'basket',      label: 'Order Basket', icon: 'shopping_basket' },
  { id: 'leaderboard', label: 'Leaderboard',  icon: 'emoji_events' },
];
function TabBar({ active, onSelect, counts }) {
  return (
    <div style={{
      display:'flex', gap:6,
      background:'var(--color-surface-1)',
      borderBottom:'1px solid var(--color-border-subtle)',
      padding:'0 28px', position:'sticky', top:54, zIndex:90,
      backdropFilter:'blur(12px)',
    }}>
      {TABS.map(t => {
        const on = t.id === active;
        const badge = counts && counts[t.id];
        return (
          <button key={t.id} onClick={()=>onSelect(t.id)} style={{
            display:'flex', alignItems:'center', gap:7,
            padding:'0 16px', height:46,
            background:'transparent', border:'none',
            borderBottom: on ? '2px solid var(--color-key-primary)' : '2px solid transparent',
            color: on ? 'var(--color-key-primary)' : 'var(--color-on-surface-subtle)',
            cursor:'pointer', fontSize:13, fontWeight: on ? 700 : 500,
            fontFamily:"'Geist', sans-serif", marginBottom:-1,
            transition:'color 0.15s, border-color 0.15s',
          }}>
            <Icon name={t.icon} size={16} color={on ? 'var(--color-key-primary)' : 'var(--color-on-surface-subtle)'} />
            {t.label}
            {badge ? (
              <span style={{
                fontSize:10, fontWeight:700, minWidth:18, height:18,
                padding:'0 5px', borderRadius:99,
                display:'inline-flex', alignItems:'center', justifyContent:'center',
                background: on ? 'var(--color-key-primary)' : 'var(--color-border-subtle)',
                color: on ? '#fff' : 'var(--color-on-surface-subtle)',
              }}>{badge}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
