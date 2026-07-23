/* leaderboard.js — the Leaderboard tab's XP ranking. */

const MEDALS      = ['emoji_events','military_tech','workspace_premium'];
const MEDAL_COLS  = ['#DC9E17','#AAABB1','#AD5D08'];

function XPLeaderboard({ entries }) {
  return (
    <div style={{ ...card({ padding:0, width:320, flexShrink:0, overflow:'hidden' }) }}>
      <div style={{
        padding:'14px 18px', borderBottom:'1px solid var(--color-border-subtle)',
        display:'flex', alignItems:'center', gap:8,
      }}>
        <Icon name="emoji_events" size={16} color="#DC9E17" />
        <span style={{ fontWeight:600, fontSize:13 }}>XP Leaderboard</span>
        <span style={{ fontSize:11, color:'var(--color-on-surface-subtle)', marginLeft:'auto' }}>
          Weekly rankings
        </span>
      </div>
      <div>
        {entries.length === 0 && (
          <div style={{ padding:'32px 18px', textAlign:'center', color:'var(--color-on-surface-subtle)', fontSize:12 }}>
            <div style={{ fontSize:28, marginBottom:8 }}>🏅</div>
            No claims yet — be the first hero.
          </div>
        )}
        {entries.map((e, i) => {
          const xp    = xpFromSaved(Math.max(0, e.saved));  // net can go negative; XP floors at 0
          const level = getLevel(xp);
          const nextL = LEVELS[LEVELS.indexOf(level)+1];
          const xpPct = nextL ? ((xp - level.min) / (nextL.min - level.min)) * 100 : 100;
          const streak= e.streak || 0;
          const isTop = i === 0;

          return (
            <div key={e.slack_id} style={{
              padding:'14px 18px',
              borderBottom: i < entries.length-1 ? '1px solid var(--color-border-subtle)' : 'none',
              background: isTop ? 'rgba(87,140,255,0.06)' : 'transparent',
              borderLeft: isTop ? '3px solid var(--color-key-primary)' : '3px solid transparent',
            }}>
              {/* Row 1: rank + name + emoji + £ */}
              <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
                <span style={{ width:20, display:'flex', justifyContent:'center', flexShrink:0 }}>
                  {i < 3
                    ? <Icon name={MEDALS[i]} size={17} color={MEDAL_COLS[i]} />
                    : <span style={{ fontSize:11, color:'var(--color-on-surface-subtle)', fontFamily:"'Geist Mono',monospace" }}>{i+1}</span>
                  }
                </span>
                <span style={{
                  flex:1, fontSize:13, fontWeight: isTop ? 700 : 500,
                  overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
                  color: isTop ? 'var(--color-key-primary)' : 'var(--color-on-surface)',
                }}>{e.name}</span>
                {streak >= 2 && (
                  <span title={`${streak}-week streak`} style={{ fontSize:13 }}>
                    {'🔥'.repeat(Math.min(streak, 3))}
                  </span>
                )}
                {(e.wasted || 0) > 0 && (
                  <span title={`${fmt(e.wasted)} wasted`} style={{
                    fontFamily:"'Geist Mono',monospace", fontSize:11, fontWeight:700,
                    color:'#D64545', flexShrink:0,
                  }}>🗑️ −{fmt(e.wasted)}</span>
                )}
                <span style={{
                  fontFamily:"'Geist Mono',monospace", fontSize:13, fontWeight:700, flexShrink:0,
                  color: e.saved < 0 ? '#D64545'
                       : isTop ? 'var(--color-key-primary)' : 'var(--color-on-surface)',
                }}>{fmt(e.saved)}</span>
              </div>

              {/* Row 2: level badge + XP bar + XP count */}
              <div style={{ display:'flex', alignItems:'center', gap:8, paddingLeft:30 }}>
                <span style={{
                  display:'inline-flex', alignItems:'center', gap:4,
                  padding:'2px 8px', borderRadius:99,
                  background: level.bg,
                  fontSize:11, fontWeight:700, color:level.color,
                  flexShrink:0, whiteSpace:'nowrap',
                }}>
                  {level.emoji} {level.name}
                </span>
                <div style={{ flex:1, height:8, background:'var(--color-border-subtle)', borderRadius:99, overflow:'hidden' }}>
                  <div style={{
                    height:'100%', width:`${xpPct}%`, borderRadius:99,
                    background:`linear-gradient(90deg, ${level.color}99, ${level.color})`,
                    boxShadow:`0 0 8px ${level.color}55`,
                    transition:'width 1.2s cubic-bezier(0.4,0,0.2,1)',
                    animation:'xp-grow 1.2s cubic-bezier(0.4,0,0.2,1)',
                  }}/>
                </div>
                <span style={{
                  fontFamily:"'Geist Mono',monospace", fontSize:11, flexShrink:0,
                  color:'var(--color-on-surface-subtle)', fontWeight:600,
                }}>{xp} XP</span>
              </div>
              {/* Next level hint */}
              {nextL && (
                <div style={{ paddingLeft:30, marginTop:4, fontSize:10, color:'var(--color-on-surface-subtle)' }}>
                  {nextL.min - xp} XP to <span style={{ color:nextL.color, fontWeight:600 }}>{nextL.emoji} {nextL.name}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Wall of shame — biggest wasters (net points lost to the bin) */}
      {entries.some(e => (e.wasted || 0) > 0) && (
        <div style={{ borderTop:'1px solid var(--color-border-subtle)', padding:'12px 18px' }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:8 }}>
            <span style={{ fontSize:13 }}>🗑️</span>
            <span style={{ fontSize:12, fontWeight:700, color:'#D64545' }}>Biggest wasters</span>
          </div>
          {[...entries].filter(e => (e.wasted || 0) > 0)
            .sort((a, b) => b.wasted - a.wasted).slice(0, 3)
            .map((e, i) => (
              <div key={e.slack_id} style={{
                display:'flex', alignItems:'center', gap:8, padding:'3px 0', fontSize:12,
              }}>
                <span style={{ width:16, textAlign:'center' }}>{['🥇','🥈','🥉'][i]}</span>
                <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{e.name}</span>
                <span style={{ fontFamily:"'Geist Mono',monospace", fontWeight:700, color:'#D64545' }}>
                  −{fmt(e.wasted)}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
