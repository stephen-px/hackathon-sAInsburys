/* core.js — shared helpers, mascot, level system, mock data, confetti, hooks.
   Loaded first: everything here is referenced by the component and app files. */
const { useState, useEffect, useRef, useCallback } = React;

/* ── Design helpers ─────────────────────────────────────────────────── */
const card = (extra = {}) => ({
  background: 'var(--color-container-surface)',
  borderRadius: 10,
  boxShadow: '0 4px 16px var(--color-elevation-2-shadow), inset 0 0 0 1px var(--color-elevation-inset)',
  ...extra,
});
const fmt  = n => '£' + Number(n).toFixed(2);
const Icon = ({ name, size = 16, color }) =>
  <span className="mi" style={{ fontSize: size, color }}>{name}</span>;

function PXMark({ size = 22 }) {
  return <img src="/assets/px-logo.png" width={size} height={size} style={{ display:'block', objectFit:'contain' }} alt="PX" />;
}

/* ── Morrison mascot ────────────────────────────────────────────────── */
function Morrison({ size = 120 }) {
  const [tickled, setTickled] = useState(false);
  const scale = size / 248;
  const handleClick = useCallback(() => {
    setTickled(true);
    setTimeout(() => setTickled(false), 600);
  }, []);
  return (
    <svg
      className={`morrison-svg${tickled ? ' tickled' : ''}`}
      style={{ '--blink-dur': '4.5s', width: size, height: size }}
      onClick={handleClick}
      viewBox="0 0 248 248"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* shadow */}
      <ellipse cx="124" cy="238" rx="44" ry="7" fill="black" opacity="0.25"/>
      {/* body */}
      <circle cx="124" cy="118" r="96" fill="#F06D00"/>
      {/* eyes */}
      {!tickled ? (<>
        <g className="morrison-el morrison-blink-l"><circle cx="100" cy="116" r="11" fill="#1A1C20"/><circle cx="96" cy="112" r="3.5" fill="white" opacity="0.75"/></g>
        <g className="morrison-er morrison-blink-r"><circle cx="148" cy="116" r="11" fill="#1A1C20"/><circle cx="144" cy="112" r="3.5" fill="white" opacity="0.75"/></g>
        <path d="M 107 142 Q 124 157 141 142" stroke="#1A1C20" strokeWidth="4.5" strokeLinecap="round" fill="none"/>
      </>) : (<>
        <path d="M 89 114 Q 100 106 111 114" stroke="#1A1C20" strokeWidth="4" strokeLinecap="round" fill="none"/>
        <path d="M 137 114 Q 148 106 159 114" stroke="#1A1C20" strokeWidth="4" strokeLinecap="round" fill="none"/>
        <path d="M 104 144 Q 124 164 144 144" stroke="#1A1C20" strokeWidth="5" strokeLinecap="round" fill="none"/>
        {/* rosy cheeks */}
        <ellipse cx="86" cy="134" rx="14" ry="8" fill="#FF9B4E" opacity="0.45"/>
        <ellipse cx="162" cy="134" rx="14" ry="8" fill="#FF9B4E" opacity="0.45"/>
      </>)}
      {/* sandwich hat */}
      <g transform="translate(86, 4)">
        {/* top bun — domed */}
        <ellipse cx="38" cy="10" rx="34" ry="12" fill="#F5C842"/>
        <ellipse cx="38" cy="8" rx="28" ry="7" fill="#F7D060" opacity="0.6"/>
        {/* sesame seeds */}
        <ellipse cx="28" cy="7" rx="3" ry="1.5" fill="#E8A820" opacity="0.8" transform="rotate(-20 28 7)"/>
        <ellipse cx="38" cy="5" rx="3" ry="1.5" fill="#E8A820" opacity="0.8"/>
        <ellipse cx="48" cy="7" rx="3" ry="1.5" fill="#E8A820" opacity="0.8" transform="rotate(20 48 7)"/>
        {/* lettuce */}
        <path d="M 5 20 Q 12 16 20 20 Q 28 24 36 19 Q 44 15 52 19 Q 60 23 68 20 L 68 24 Q 60 27 52 23 Q 44 19 36 23 Q 28 27 20 24 Q 12 21 5 24 Z" fill="#5DBB63"/>
        {/* tomato */}
        <rect x="8" y="24" width="60" height="7" rx="3" fill="#E84040" opacity="0.85"/>
        {/* cheese */}
        <path d="M 6 31 L 6 37 L 70 37 L 70 31 Q 62 35 54 31 Q 46 27 38 31 Q 30 35 22 31 Q 14 27 6 31 Z" fill="#F5C842" opacity="0.9"/>
        {/* bottom bun */}
        <rect x="4" y="37" width="68" height="12" rx="6" fill="#F5C842"/>
        <rect x="4" y="37" width="68" height="5" rx="3" fill="#F7D060" opacity="0.4"/>
      </g>
    </svg>
  );
}

/* ── XP / Level system ──────────────────────────────────────────────── */
const LEVELS = [
  { name: 'Sprout',   min: 0,    max: 99,   emoji: '🌱', color: '#70D913', bg: 'rgba(112,217,19,0.15)' },
  { name: 'Seedling', min: 100,  max: 249,  emoji: '🌿', color: '#3396FF', bg: 'rgba(51,150,255,0.15)' },
  { name: 'Grower',   min: 250,  max: 499,  emoji: '🌳', color: '#578cff', bg: 'rgba(87,140,255,0.15)' },
  { name: 'Champion', min: 500,  max: 999,  emoji: '⚡', color: '#e96d00', bg: 'rgba(233,109,0,0.15)'  },
  { name: 'Legend',   min: 1000, max: 9999, emoji: '👑', color: '#DC9E17', bg: 'rgba(220,158,23,0.15)' },
];
function getLevel(xp) { return LEVELS.find(l => xp >= l.min && xp <= l.max) || LEVELS[LEVELS.length - 1]; }
function xpFromSaved(saved) { return Math.round(saved * 10); }

/* ── Mock data (fallback only — used when the API server is unreachable) ── */
const MOCK_NAMES = ['Alice Chen','Bob Smith','Carol Jones','Dave Kumar','Eve Williams','Frank Lee','Grace Park'];
const MOCK = {
  stats: { saved_week: 47.30, items_rescued: 12, pending_orders: 1, active_claimers: 7 },
  leaderboard: [
    { slack_id: 'U001', name: 'Alice Chen',   saved: 18.50, streak: 4 },
    { slack_id: 'U002', name: 'Bob Smith',    saved: 12.30, streak: 2 },
    { slack_id: 'U003', name: 'Carol Jones',  saved:  9.80, streak: 3 },
    { slack_id: 'U004', name: 'Dave Kumar',   saved:  4.20, streak: 1 },
    { slack_id: 'U005', name: 'Eve Williams', saved:  2.50, streak: 1 },
  ],
  rescue: [
    { id: 1, name: 'Hummus & Flatbreads',  days_left: 0, qty_remaining: 2, price: 2.50, risk_score: 6.2 },
    { id: 2, name: 'Mixed Leaf Salad',     days_left: 1, qty_remaining: 3, price: 1.80, risk_score: 4.1 },
    { id: 3, name: 'Chicken Caesar Wrap',  days_left: 2, qty_remaining: 1, price: 3.50, risk_score: 2.5 },
    { id: 4, name: 'Fruit Pot',            days_left: 2, qty_remaining: 4, price: 2.00, risk_score: 2.3 },
    { id: 5, name: 'Falafel Bowl',         days_left: 3, qty_remaining: 2, price: 4.50, risk_score: 1.8 },
    { id: 6, name: 'Spiced Chickpea Wrap', days_left: 4, qty_remaining: 5, price: 3.50, risk_score: 1.2 },
  ],
  basket: {
    week: '2026-07-20',
    orders: [
      { id: 1, delivery_date: '2026-07-21', status: 'approved', total: 87.40,
        lines: [
          { name: 'Chicken Caesar Wrap', qty: 8, unit_price: 3.50 },
          { name: 'Hummus & Flatbreads', qty: 6, unit_price: 2.50 },
          { name: 'Mixed Leaf Salad',    qty: 5, unit_price: 1.80 },
        ] },
      { id: 2, delivery_date: '2026-07-23', status: 'draft', total: 62.20,
        lines: [
          { name: 'Falafel Bowl',              qty: 6, unit_price: 4.50 },
          { name: 'Fruit Pot',                 qty: 8, unit_price: 2.00 },
          { name: 'Cheese & Chutney Baguette', qty: 5, unit_price: 3.20 },
        ] },
    ],
  },
  totals: [
    { week: '06-29', claimed: 32.10, wasted: 18.50 },
    { week: '07-06', claimed: 41.20, wasted: 12.30 },
    { week: '07-13', claimed: 38.80, wasted:  9.50 },
    { week: '07-20', claimed: 47.30, wasted:  5.20 },
  ],
  departments: { Engineering: 32.10, Operations: 10.80, Product: 4.40 },
  challenge: { goal: 60, label: 'Team goal: save £60 this week' },
};

/* ── Confetti ───────────────────────────────────────────────────────── */
const CC = ['#578cff','#70D913','#FF5359','#DC9E17','#e96d00','#ffffff','#3396FF','#b0e0ff'];
let cparts = [], craf = null;
function boom(cx, cy) {
  try {
    const cv = document.getElementById('ccanvas');
    if (!cv) return;
    cv.width = window.innerWidth; cv.height = window.innerHeight;
    const x = cx != null ? cx : cv.width / 2;
    const y = cy != null ? cy : cv.height * 0.28;
    for (let i = 0; i < 110; i++) {
      const a = (Math.PI * 2 * i) / 110 + (Math.random() - 0.5);
      const s = 3 + Math.random() * 9;
      cparts.push({ x, y, vx: Math.cos(a)*s, vy: Math.sin(a)*s - 5,
        color: CC[Math.floor(Math.random()*CC.length)],
        alpha: 1, rot: Math.random()*360, rv: (Math.random()-0.5)*14,
        w: 5+Math.random()*6, h: 3+Math.random()*4 });
    }
    if (!craf) rafConfetti();
  } catch(e) { console.error('[boom]', e.message); }
}
function rafConfetti() {
  try {
    const cv = document.getElementById('ccanvas');
    if (!cv) return;
    const ctx = cv.getContext('2d');
    ctx.clearRect(0,0,cv.width,cv.height);
    cparts = cparts.filter(p => p.alpha > 0.02);
    cparts.forEach(p => {
      p.x+=p.vx; p.y+=p.vy; p.vy+=0.28; p.vx*=0.99;
      p.rot+=p.rv; p.alpha -= 0.011;
      ctx.save(); ctx.globalAlpha = Math.max(0,p.alpha);
      ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
      ctx.fillStyle=p.color; ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);
      ctx.restore();
    });
    if (cparts.length>0) { craf = requestAnimationFrame(rafConfetti); }
    else { craf=null; ctx.clearRect(0,0,cv.width,cv.height); }
  } catch(e) { craf=null; console.error('[rafConfetti]',e.message); }
}

/* ── Smooth animated counter ───────────────────────────────────────── */
function useSmoothVal(target, ms = 900) {
  const [val, setVal] = useState(target);
  const from = useRef(target);
  const raf  = useRef(null);
  const t0   = useRef(null);
  useEffect(() => {
    try {
      const start = from.current;
      const diff  = target - start;
      if (Math.abs(diff) < 0.005) { setVal(target); return; }
      t0.current = null;
      if (raf.current) cancelAnimationFrame(raf.current);
      function step(ts) {
        if (!t0.current) t0.current = ts;
        const t = Math.min((ts - t0.current) / ms, 1);
        const e = t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
        setVal(start + diff * e);
        if (t < 1) { raf.current = requestAnimationFrame(step); }
        else { from.current = target; raf.current = null; }
      }
      raf.current = requestAnimationFrame(step);
      return () => { if (raf.current) cancelAnimationFrame(raf.current); };
    } catch(e) { console.error('[useSmoothVal]',e.message); }
  }, [target]);
  return val;
}

/* ── Milestones ─────────────────────────────────────────────────────── */
const MILES = [50,100,150,200,300,500];
function nextMile(v) { return MILES.find(m => m > v) || MILES[MILES.length-1]; }
