/* app.js — top-level App: data polling, live claim stream, and tab routing.
   Loaded last: depends on everything defined in the other js files. */

const EMPTY = {
  stats:       { saved_week: 0, items_rescued: 0, pending_orders: 0, active_claimers: 0 },
  leaderboard: [],
  rescue:      [],
  basket:      { week: '', orders: [] },
  totals:      [],
  departments: {},            // no backend source — populated only in mock/demo
  challenge:   MOCK.challenge, // goal is config, not fake data — kept
};

function App() {
  const [theme,  setTheme]  = useState('dark');
  const [tab,    setTab]    = useState('rescue');
  const [data,   setData]   = useState(EMPTY);
  const [apiOk,  setApiOk]  = useState(false);   // true once server responds
  const [floats, setFloats] = useState([]);
  const [live,   setLive]   = useState(false);
  const [toasts, setToasts] = useState([]);
  const [feed,   setFeed]   = useState([]);
  const [demo,   setDemo]   = useState(false);   // true = showing mock/demo data
  const uid = useRef(0);

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light');
  }, [theme]);

  const handleClaim = useCallback((value, itemName, user) => {
    try {
      setData(d => {
        const was = d.stats.saved_week;
        const nxt = was + value;
        const hit = [50,100,150,200,300].find(m => was < m && nxt >= m);
        if (hit) {
          setToasts(ts => [...ts, {
            id: uid.current++,
            emoji:'🎉',
            title:`${fmt(hit)} Milestone!`,
            body:`The team has saved ${fmt(nxt)} worth of food this week.`,
          }]);
        }
        return {
          ...d,
          stats: {
            ...d.stats,
            saved_week:    nxt,
            items_rescued: d.stats.items_rescued + 1,
          },
        };
      });
      setFloats(f => [...f, { id: uid.current++, value }]);
      setFeed(f => [{
        id: uid.current++, kind:'claimed',
        user: user || 'Someone',
        item: itemName || 'an item',
        value,
      }, ...f.slice(0, 19)]);
    } catch(e) { console.error('[handleClaim]',e.message); }
  }, []);

  /* Poll — real data from API, MOCK only if server is completely unreachable */
  useEffect(() => {
    const go = async () => {
      try {
        const [s,lb,r,b,t,dp] = await Promise.all([
          fetch('/api/stats'), fetch('/api/leaderboard'),
          fetch('/api/rescue'), fetch('/api/basket'), fetch('/api/totals'),
          fetch('/api/departments'),
        ]);
        if (!s.ok) return;
        const [stats,leaderboard,rescue,basket,totals,departments] = await Promise.all([
          s.json(),lb.json(),r.json(),b.json(),t.json(),dp.json()
        ]);
        setApiOk(true);
        setDemo(false);   // real API responded — not the client mock fallback
        setData(d => ({ ...d, stats, leaderboard, rescue, basket, totals, departments }));
      } catch(_) {
        // API server unreachable — fall back to demo data so the UI isn't blank
        if (!apiOk) { setData(MOCK); setDemo(true); }
      }
    };
    go();
    const id = setInterval(go, 5000);
    return () => clearInterval(id);
  }, []);

  /* SSE */
  useEffect(() => {
    let es;
    try {
      es = new EventSource('/api/events/stream');
      es.onopen  = () => setLive(true);
      es.onerror = () => setLive(false);
      es.onmessage = e => {
        try {
          const ev = JSON.parse(e.data);
          if (ev.kind==='claimed' && ev.value>0) {
            // a claim landed (from Slack) — celebrate on the dashboard
            boom(null, null);
            handleClaim(ev.value, ev.item||'an item', ev.user||'Someone');
          }
        } catch(err) { console.error('[SSE]',err.message); }
      };
    } catch(_) {}
    return () => { try { es && es.close(); } catch(_) {} };
  }, [handleClaim]);

  const expFloat = useCallback(id => setFloats(f => f.filter(x=>x.id!==id)), []);
  const expToast = useCallback(id => setToasts(t => t.filter(x=>x.id!==id)), []);

  // Data-source state: 'demo' = fabricated mock data; 'empty' = server up but no
  // live DB seeded; otherwise real DB data (no banner).
  const isDemo  = demo || Object.keys(data.departments || {}).length > 0;
  const isEmpty = !isDemo && data.stats.live === false;

  return (
    <div>
      <Header theme={theme} onToggle={()=>setTheme(t=>t==='dark'?'light':'dark')} live={live}/>
      <TabBar
        active={tab}
        onSelect={setTab}
        counts={{ rescue: data.rescue.length, basket: (data.basket.orders||[]).length }}
      />

      {(isDemo || isEmpty) && (
        <div style={{
          display:'flex', alignItems:'center', justifyContent:'center', gap:8,
          padding:'7px 14px', fontSize:12, fontWeight:600,
          background: isDemo ? 'rgba(233,109,0,0.12)' : 'rgba(170,171,177,0.12)',
          color: isDemo ? 'var(--color-key-warning)' : 'var(--color-on-surface-subtle)',
          borderBottom:'1px solid var(--color-border-subtle)',
        }}>
          <Icon name={isDemo ? 'science' : 'database'} size={15}
                color={isDemo ? 'var(--color-key-warning)' : 'var(--color-on-surface-subtle)'} />
          {isDemo
            ? 'Showing demo data — not from the live database (DASHBOARD_MOCK is on, or the API is unreachable).'
            : 'Connected, but no live data yet — seed the database with data/demo_reset.py.'}
        </div>
      )}

      {/* Toast stack */}
      <div style={{ position:'fixed', right:20, top:68, display:'flex', flexDirection:'column', gap:10, zIndex:500, pointerEvents:'none' }}>
        {toasts.map(t => (
          <div key={t.id} style={{ pointerEvents:'auto' }}>
            <Toast t={t} onClose={()=>expToast(t.id)}/>
          </div>
        ))}
      </div>

      <main style={{ maxWidth:1260, margin:'0 auto', padding:'22px 28px 56px', display:'flex', flexDirection:'column', gap:16 }}>

        {/* ── Rescue tab ─────────────────────────────────────────────── */}
        {tab === 'rescue' && (
          <>
            <Hero total={data.stats.saved_week} floats={floats} onExpireFloat={expFloat}/>

            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14 }}>
              <StatTile icon="savings"       value={fmt(data.stats.saved_week)} label="Saved this week"   accent="var(--color-key-success)" sub="vs £89 same time last week" />
              <StatTile icon="recycling"     value={data.stats.items_rescued}   label="Items rescued"     accent="#70D913" />
              <StatTile icon="shopping_cart" value={data.stats.pending_orders}  label="Open baskets" accent="var(--color-key-warning)" />
              <StatTile icon="group"         value={data.stats.active_claimers} label="Active heroes"     accent="var(--color-key-primary)" />
            </div>

            <FridgeHP rescue={data.rescue}/>

            <div style={{ display:'flex', gap:16, alignItems:'flex-start' }}>
              <RescueBoard items={data.rescue}/>
              <ActivityFeed events={feed}/>
            </div>
          </>
        )}

        {/* ── Order Basket tab ───────────────────────────────────────── */}
        {tab === 'basket' && (
          <>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:14 }}>
              <StatTile icon="shopping_cart"  value={(data.basket.orders||[]).length} label="Basket this week" accent="var(--color-key-primary)" />
              <StatTile icon="group"           value={data.stats.active_claimers}     label="Active heroes" accent="var(--color-key-warning)" />
              <StatTile icon="payments"        value={fmt((data.basket.orders||[]).reduce((s,o)=>s+(o.total||0),0))} label="Total basket value" accent="#70D913" />
            </div>
            <BasketStatus basket={data.basket}/>
          </>
        )}

        {/* ── Leaderboard tab ────────────────────────────────────────── */}
        {tab === 'leaderboard' && (
          <>
            <div style={{ display:'flex', gap:16, alignItems:'flex-start', flexWrap:'wrap' }}>
              <XPLeaderboard entries={data.leaderboard}/>
              <div style={{ display:'flex', flexDirection:'column', gap:16, flex:1, minWidth:280 }}>
                {Object.keys(data.departments || {}).length > 0 &&
                  <DeptBattle departments={data.departments}/>}
                <WeeklyChallenge saved={data.stats.saved_week} challenge={data.challenge || MOCK.challenge}/>
              </div>
            </div>
            <WeeklyChart totals={data.totals}/>
          </>
        )}

      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
