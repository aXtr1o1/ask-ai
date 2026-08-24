"use client";

/**
 * DynamicDashboard — Gold & Silver Premium Edition
 * Rich gold & silver duotone, glassmorphism, CSS keyframe animations,
 * adaptive data-size layouts, entrance animations, podium glow effects.
 */

import React, { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend,
  PieChart, Pie, Cell,
  AreaChart, Area, LabelList,
  ScatterChart, Scatter, ZAxis
} from "recharts";

// ─── Design Tokens ────────────────────────────────────────────────────────────
const G = {
  // Gold
  gold:        "#D4AF37",
  goldBright:  "#F7EF8A",
  goldDim:     "#AA7C11",
  goldGlow:    "rgba(212,175,55,0.35)",
  goldBorder:  "rgba(212,175,55,0.28)",
  goldBg:      "rgba(212,175,55,0.07)",
  // Silver
  silver:      "#C0C0C0",
  silverBright:"#E8E8E8",
  silverDim:   "#808090",
  silverGlow:  "rgba(192,192,200,0.32)",
  silverBorder:"rgba(192,192,200,0.26)",
  silverBg:    "rgba(192,192,200,0.07)",
  // Bronze (for #3 podium)
  bronze:      "#CD7F32",
  // Glass
  glass:       "rgba(255,255,255,0.03)",
  glassBorder: "rgba(255,255,255,0.07)",
  textPrimary: "#f1f5f9",
  textMuted:   "rgba(255,255,255,0.45)",
  textFaint:   "rgba(255,255,255,0.22)",
};

// Podium accent per rank index (0-based)
function podiumColor(idx: number): string {
  if (idx === 0) return G.gold;
  if (idx === 1) return G.silver;
  if (idx === 2) return G.bronze;
  return G.textMuted;
}

// Rank-based fill: top bar = bright gold, bottom = muted slate.
// This replaces rainbow coloring with a professional monochromatic gradient.
function rankFill(idx: number, total: number): string {
  const t = total > 1 ? idx / (total - 1) : 0;
  // Interpolate: gold rgb(212,175,55) → slate rgb(96,100,120)
  const r = Math.round(212 - t * (212 - 96));
  const g = Math.round(175 - t * (175 - 100));
  const b = Math.round(55  + t * (120 - 55));
  return `rgb(${r},${g},${b})`;
}

// Cohesive multi-series palette (gold, silver, then harmonious accent colors)
const CHART_COLORS = [
  "#D4AF37","#C0C0C0","#818cf8","#34d399","#f472b6",
  "#fb923c","#60a5fa","#a78bfa","#4ade80","#fbbf24",
];

// KPI icon symbols per common metric title keywords
function kpiIcon(title: string): string {
  const t = title.toLowerCase();
  if (/total|count|sum/.test(t))   return "◈";
  if (/avg|average|mean/.test(t))  return "◎";
  if (/rate|ratio|pct|%/.test(t))  return "◐";
  if (/time|duration/.test(t))     return "◷";
  if (/revenue|cost|price/.test(t)) return "◇";
  if (/user|person|staff/.test(t)) return "◉";
  return "◈";
}

// ─── Animation injector ───────────────────────────────────────────────────────
function injectAnimations() {
  if (typeof document === "undefined") return;
  if (document.querySelector("style[data-dd]")) return;
  const s = document.createElement("style");
  s.setAttribute("data-dd", "1");
  s.textContent = `
    @keyframes ddFadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
    @keyframes ddGlowPulse{0%,100%{box-shadow:0 0 8px rgba(212,175,55,.28),0 0 24px rgba(212,175,55,.08)}50%{box-shadow:0 0 20px rgba(212,175,55,.55),0 0 48px rgba(212,175,55,.18)}}
    @keyframes ddGlowPulseSilver{0%,100%{box-shadow:0 0 8px rgba(192,192,200,.25),0 0 24px rgba(192,192,200,.07)}50%{box-shadow:0 0 18px rgba(192,192,200,.48),0 0 44px rgba(192,192,200,.16)}}
    @keyframes ddBarFill{from{width:0}}
    @keyframes ddCountUp{from{opacity:0;transform:scale(.82)}to{opacity:1;transform:scale(1)}}
    @keyframes ddShimmer{0%{background-position:-600px 0}100%{background-position:600px 0}}
    .ddCard{animation:ddFadeUp .48s cubic-bezier(.16,1,.3,1) both}
    .ddGlow{animation:ddGlowPulse 3.2s ease-in-out infinite}
    .ddGlowSilver{animation:ddGlowPulseSilver 3.6s ease-in-out infinite}
    .ddKpiVal{animation:ddCountUp .5s cubic-bezier(.16,1,.3,1) both}
    .ddBar{animation:ddBarFill .9s cubic-bezier(.4,0,.2,1) both}
    .ddCard:hover{transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease!important}
    .ddTr:hover td{background:rgba(212,175,55,.04)!important;transition:background .15s}
    .ddBtn{transition:all .15s ease;outline:none}
    .ddBtn:hover:not(:disabled){background:rgba(212,175,55,.18)!important;box-shadow:0 0 12px rgba(212,175,55,.22)}
    @media (max-width:640px){.ddGrid{grid-template-columns:1fr!important;}}
  `;
  document.head.appendChild(s);
}

// ─── Semantic color ───────────────────────────────────────────────────────────
function sem(label: string, idx: number): string {
  const n = label.toLowerCase().trim();
  if (/^(online|active|open|completed|yes|true|success|high)$/.test(n))      return "#10b981";
  if (/^(offline|inactive|closed|failed|no|false|critical|expired)$/.test(n)) return "#f43f5e";
  if (/^(pending|hold|warning|in progress|medium)$/.test(n))                  return "#f59e0b";
  return CHART_COLORS[idx % CHART_COLORS.length];
}

function humanKey(k: string): string {
  const s = k.replace(/([a-z])([A-Z])/g,"$1 $2").replace(/_/g," ").replace(/-/g," ");
  return s.split(" ").map(w=>w.charAt(0).toUpperCase()+w.slice(1).toLowerCase()).join(" ");
}

// ─── Types ────────────────────────────────────────────────────────────────────
interface KpiC   { type:"kpi"; title:string; value:string; raw:unknown; subtitle:string|null; sparkline?:number[]|null; delta?:number|null; delta_label?:string; }
interface SumC   { type:"dashboard_summary"; title:string; category_key:string; metric_key:string; total_value:number; data:Record<string,unknown>[]; }
interface RecC   { type:"record_cards"; title:string; data:Record<string,unknown>[]; }
interface BarC   { type:"bar_chart"; title:string; x_key:string; y_key:string; data:Record<string,unknown>[]; }
interface TsC    { type:"time_series_chart"; title:string; x_key:string; y_keys:string[]; data:Record<string,unknown>[]; }
interface TabC   { type:"table"; title:string; columns:string[]; rows:string[][]; note?:string; }
interface TxtC   { type:"text"; value:string; }
interface DonutC { type:"donut_chart"; title:string; category_key:string; metric_key:string; total_value:number; data:Record<string,unknown>[]; }
interface GrpBarC{ type:"grouped_bar_chart"; title:string; category_key:string; metric_keys:string[]; data:Record<string,unknown>[]; }
interface AreaC  { type:"area_chart"; title:string; x_key:string; y_keys:string[]; data:Record<string,unknown>[]; }
interface GaugeC { type:"gauge_chart"; title:string; value:number; unit:string; }
interface ScatterC { type:"scatter_chart"; title:string; x_key:string; y_key:string; label_key:string|null; data:Record<string,unknown>[]; }
type DC = KpiC|SumC|RecC|BarC|TsC|TabC|TxtC|DonutC|GrpBarC|AreaC|GaugeC|ScatterC;
interface DDProps { components:DC[]; explanation?:string; }

// ─── Shared styles ────────────────────────────────────────────────────────────
const goldPanel: React.CSSProperties = {
  background: `linear-gradient(135deg,rgba(212,175,55,.07) 0%,rgba(212,175,55,.01) 60%,rgba(255,255,255,.02) 100%)`,
  border: `1px solid ${G.goldBorder}`,
  borderRadius: 16,
  boxShadow: `0 6px 32px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.05)`,
};
// Silver variant panel — used for alternating KPI cards and secondary panels
const silverPanel: React.CSSProperties = {
  background: `linear-gradient(135deg,rgba(192,192,200,.07) 0%,rgba(192,192,200,.01) 60%,rgba(255,255,255,.02) 100%)`,
  border: `1px solid ${G.silverBorder}`,
  borderRadius: 16,
  boxShadow: `0 6px 32px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.05)`,
};
const glassCard: React.CSSProperties = {
  background: "linear-gradient(135deg,rgba(255,255,255,.055) 0%,rgba(255,255,255,.02) 100%)",
  border: `1px solid ${G.glassBorder}`,
  borderRadius: 14,
  boxShadow: "0 4px 24px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.06)",
};

// ─── Subcomponents ────────────────────────────────────────────────────────────
const Tip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{background:"rgba(6,6,10,.97)",border:`1px solid ${G.goldBorder}`,borderRadius:10,padding:"10px 16px",boxShadow:`0 8px 32px rgba(0,0,0,.7),0 0 20px ${G.goldGlow}`,fontFamily:"inherit",minWidth:110}}>
      {label && <p style={{margin:"0 0 6px",fontSize:10,color:G.textMuted,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em"}}>{String(label)}</p>}
      {payload.map((e:any,i:number)=>{
        const c=e.payload?.color||e.color||G.gold;
        return <p key={i} style={{margin:"2px 0",fontSize:13,fontWeight:800,color:c}}>{e.name?<span style={{fontWeight:500,color:G.textMuted,marginRight:4}}>{e.name}:</span>:null}{typeof e.value==="number"?e.value.toLocaleString():String(e.value)}</p>;
      })}
    </div>
  );
};

function SecLabel({label}:{label:string}) {
  if (!label) return null;
  return (
    <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
      <div style={{width:3,height:16,background:`linear-gradient(180deg,${G.goldBright},${G.goldDim})`,borderRadius:2,flexShrink:0,boxShadow:`0 0 6px ${G.goldGlow}`}}/>
      <h4 style={{margin:0,fontSize:11,fontWeight:900,color:G.gold,textTransform:"uppercase",letterSpacing:".1em",textShadow:`0 0 12px ${G.goldGlow}`}}>{label}</h4>
    </div>
  );
}

// ─── Custom Left-Aligned YAxis Tick
function CustomYTick({ y, payload, yW }: any) {
  const label = payload.value;
  const maxChars = Math.floor((yW - 16) / 6.8);
  const truncated = label && label.length > maxChars ? label.slice(0, maxChars - 1) + "…" : label;
  return (
    <g transform={`translate(10,${y})`}>
      <text x={0} y={4} fill="rgba(255,255,255,.8)" fontSize={10.5} textAnchor="start" fontFamily="inherit">
        {truncated}
      </text>
    </g>
  );
}

function PBtn({disabled,onClick,children}:{disabled:boolean;onClick:()=>void;children:React.ReactNode}) {
  return (
    <button onClick={onClick} disabled={disabled} className="ddBtn" style={{background:disabled?"transparent":G.goldBg,border:`1px solid ${disabled?G.glassBorder:G.goldBorder}`,borderRadius:7,color:disabled?G.textFaint:G.gold,fontSize:11,fontWeight:700,padding:"5px 16px",cursor:disabled?"default":"pointer",fontFamily:"inherit"}}>
      {children}
    </button>
  );
}


function getFilteredKpiValue(kpi: KpiC, activeFilter: {key: string; value: string} | null, allComponents: DC[]) {
  if (!activeFilter) return { value: kpi.value, labelSuffix: "" };

  const cleanTitle = kpi.title.toLowerCase().replace(/^(total|avg|average|mean|sum)\s+/, "").trim();
  
  if (cleanTitle === "categories" || cleanTitle === "records" || cleanTitle === "count") {
    for (const comp of allComponents) {
      if ("data" in comp && Array.isArray(comp.data) && comp.data.length > 0) {
        const filtered = comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value);
        if (cleanTitle === "categories" && "category_key" in comp) {
          const uniqueCats = new Set(filtered.map(r => String(r[(comp as any).category_key])));
          return { value: uniqueCats.size.toLocaleString(), labelSuffix: " (filtered)" };
        }
        return { value: filtered.length.toLocaleString(), labelSuffix: " (filtered)" };
      }
    }
  }

  for (const comp of allComponents) {
    if ("data" in comp && Array.isArray(comp.data) && comp.data.length > 0) {
      const dataKeys = Object.keys(comp.data[0]);
      const matchingKey = dataKeys.find(k => k.toLowerCase() === cleanTitle || humanKey(k).toLowerCase() === cleanTitle);
      
      if (matchingKey) {
        const filtered = comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value);
        const valsFiltered = filtered.map(r => Number(r[matchingKey])).filter(v => !isNaN(v));
        
        if (valsFiltered.length > 0) {
          const sumFiltered = valsFiltered.reduce((a, b) => a + b, 0);
          const isAvg = kpi.title.toLowerCase().startsWith("avg") || kpi.title.toLowerCase().startsWith("average");
          const finalVal = isAvg ? (sumFiltered / valsFiltered.length) : sumFiltered;
          
          let formatted = "";
          const isCurrency = kpi.value.startsWith("$");
          if (isCurrency) {
            formatted = `$${finalVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
          } else {
            formatted = finalVal.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 2});
          }
          
          return { value: formatted, labelSuffix: " (filtered)" };
        }
      }
    }
  }
  
  return { value: kpi.value, labelSuffix: " (global)" };
}

// ─── KPI Grid — NextAdmin-style Sparkline Metric Cards
function KpiGrid({items, activeFilter, allComponents}:{items:KpiC[]; activeFilter: {key: string; value: string} | null; allComponents: DC[]}) {
  useEffect(()=>{injectAnimations();},[]);
  const n=items.length;
  const cols=n===1?1:n===2?2:n<=4?2:n<=6?3:4;
  const iconColors=[G.gold,G.silver,"#34d399","#818cf8","#f472b6","#fb923c","#60a5fa"];
  return (
    <div style={{display:"grid",gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,gap:12,width:"100%"}}>
      {items.map((kpi,i)=>{
        const isSilver=i%2===1;
        const panel=isSilver?silverPanel:goldPanel;
        const valGrad=isSilver
          ?`linear-gradient(135deg,${G.silverBright} 0%,${G.silver} 50%,${G.silverDim} 100%)`
          :`linear-gradient(135deg,${G.goldBright}  0%,${G.gold}  50%,${G.goldDim}  100%)`;
        const accentC=isSilver?G.silver:G.gold;
        const glowCls=isSilver?"ddCard ddGlowSilver":"ddCard ddGlow";
        const ic=iconColors[i%iconColors.length];
        const glowFilter=isSilver?`drop-shadow(0 0 6px ${G.silverGlow})`:`drop-shadow(0 0 6px ${G.goldGlow})`;

        // BUG 1.4 FIX — suppress flat sparklines where all values are identical
        const sparkData = kpi.sparkline
          ? kpi.sparkline.map((v: number, idx: number) => ({ id: idx, value: v }))
          : [];
        const hasVariance = sparkData.length > 1 &&
          sparkData.some(d => d.value !== sparkData[0].value);
        const hasSpark = hasVariance;

        const { value: displayValue, labelSuffix } = getFilteredKpiValue(kpi, activeFilter, allComponents);

        return (
          <div key={i} className={glowCls} style={{...panel,padding:"16px 20px",display:"flex",flexDirection:"column",cursor:"default",animationDelay:`${i*.07}s`,position:"relative",overflow:"hidden",minHeight:118}}>
            {/* Top row: title + icon badge */}
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
              <span style={{fontSize:10,fontWeight:700,color:G.textMuted,textTransform:"uppercase",letterSpacing:".08em",lineHeight:1.4,maxWidth:"70%"}}>{kpi.title}{labelSuffix}</span>
              <div style={{width:30,height:30,borderRadius:8,background:`${ic}14`,border:`1px solid ${ic}33`,display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                <span style={{fontSize:14,color:ic,filter:`drop-shadow(0 0 4px ${ic}66)`}}>{kpiIcon(kpi.title)}</span>
              </div>
            </div>
            {/* Value + Sparkline layout */}
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",marginTop:"auto",gap:8}}>
              <span className="ddKpiVal" style={{fontSize:21,fontWeight:900,lineHeight:1,whiteSpace:"nowrap",background:valGrad,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",backgroundClip:"text",animationDelay:`${i*.07+.1}s`,filter:glowFilter,marginBottom:2}}>{displayValue}</span>
              
              {/* Sparkline chart */}
              {hasSpark && (
                <div style={{width:60,height:20,opacity:0.75,flexShrink:0,marginRight:4}}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sparkData}>
                      <Line type="monotone" dataKey="value" stroke={accentC} strokeWidth={1.5} dot={false} isAnimationActive={false}/>
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
            {/* Subtitle / trend row */}
            <div style={{display:"flex",alignItems:"center",gap:6,marginTop:8}}>
              {kpi.delta !== undefined && kpi.delta !== null ? (
                <span style={{
                  fontSize: 9,
                  fontWeight: 700,
                  padding: "2px 6px",
                  borderRadius: 4,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 3,
                  color: kpi.delta > 0 ? "#10b981" : kpi.delta < 0 ? "#ef4444" : G.textMuted,
                  background: kpi.delta > 0 ? "rgba(16,185,129,0.12)" : kpi.delta < 0 ? "rgba(239,68,68,0.12)" : "rgba(255,255,255,0.05)"
                }}>
                  {/* BUG 1.5 FIX — cap delta display to 999% to avoid partial-week inflation */}
                  {(() => {
                    const safeDelta = Math.min(Math.abs(kpi.delta!), 999);
                    const sign = kpi.delta! > 0 ? "+" : kpi.delta! < 0 ? "-" : "";
                    if (kpi.delta! > 0) return `▲ +${safeDelta}%`;
                    if (kpi.delta! < 0) return `▼ -${safeDelta}%`;
                    return `● No change`;
                  })()}
                  {kpi.delta_label && <span style={{color: G.textFaint, fontWeight: 400, marginLeft: 2}}>{kpi.delta_label}</span>}
                </span>
              ) : kpi.subtitle ? (
                <span style={{fontSize:10,color:G.textFaint}}>{kpi.subtitle}</span>
              ) : (
                <span style={{fontSize:10,color:G.textFaint,fontStyle:"italic"}}>—</span>
              )}
            </div>
            {/* Bottom accent line */}
            <div style={{position:"absolute",bottom:0,left:0,right:0,height:2,background:`linear-gradient(90deg,transparent,${accentC},transparent)`,opacity:.35}}/>
          </div>
        );
      })}
    </div>
  );
}

// ─── Dashboard Summary ────────────────────────────────────────────────────────
const SPAGE=20;
function SummaryPanel({comp, activeFilter, toggleFilter}:{comp:SumC; activeFilter: {key: string; value: string} | null; toggleFilter: (key: string, value: string) => void}) {
  const [page,setPage]=useState(0);
  useEffect(()=>{injectAnimations();},[]);
  // BUG 7.3 FIX — reset page when filter changes
  useEffect(()=>{ setPage(0); },[activeFilter]);
  if (!comp.data?.length) return null;

  const isOriginator = activeFilter && activeFilter.key === comp.category_key;
  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && !isOriginator && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  const displayTotalValue = (activeFilter && !isOriginator && hasFilterKey)
    ? displayData.reduce((acc, r) => acc + (Number(r[comp.metric_key]) || 0), 0)
    : comp.total_value;

  const rows = displayData.map((r, i) => {
    const rv = r[comp.metric_key];
    const v = typeof rv === "number" ? rv : Number(rv) || 0;
    const pct = displayTotalValue > 0 ? (v / displayTotalValue) * 100 : 0;
    const lbl = String(r[comp.category_key] || "Unknown");
    return { ...r, name: lbl, value: v, pct, color: sem(lbl, i) };
  });

  const sorted=[...rows].sort((a,b)=>b.value-a.value);
  const total=sorted.length;
  const isS=total<=6,isM=total>6&&total<=25,isL=total>25;
  const tPages=Math.ceil(total/SPAGE);
  const paged=tPages>1?sorted.slice(page*SPAGE,(page+1)*SPAGE):sorted;
  const barH=Math.min(Math.max(paged.length*28+40,200),560);
  
  const ml=Math.max(...sorted.map(d=>d.name.length), 1);
  const yW=Math.min(Math.max(ml*7.2,100),260);
  const globalMax=sorted[0]?.value||1;
  const topList = isL ? sorted.slice(0, 15) : sorted.slice(0, 10);

  const Header=(
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",borderBottom:`1px solid ${G.goldBorder}`,paddingBottom:14,marginBottom:4}}>
      <div>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:3}}>
          <div style={{width:4,height:18,background:`linear-gradient(180deg,${G.goldBright},${G.goldDim})`,borderRadius:2,boxShadow:`0 0 8px ${G.goldGlow}`}}/>
          <h3 style={{margin:0,fontSize:13,fontWeight:900,background:`linear-gradient(90deg,${G.goldBright},${G.gold})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",textTransform:"uppercase",letterSpacing:".1em"}}>{comp.title}</h3>
        </div>
        <p style={{margin:0,fontSize:11,color:G.textMuted}}>{total.toLocaleString()} categories · Breakdown &amp; Distribution{activeFilter && !isOriginator && " (filtered)"}</p>
      </div>
      <div style={{textAlign:"right",flexShrink:0,marginLeft:16,background:G.goldBg,border:`1px solid ${G.goldBorder}`,borderRadius:10,padding:"8px 14px"}}>
        <span style={{fontSize:9,fontWeight:700,color:G.textMuted,textTransform:"uppercase",letterSpacing:".06em",display:"block"}}>Total{activeFilter && !isOriginator && " (filtered)"}</span>
        <span style={{fontSize:20,fontWeight:900,background:`linear-gradient(135deg,${G.goldBright},${G.gold})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>{displayTotalValue.toLocaleString()}</span>
      </div>
    </div>
  );

  if (isS) return (
    <div className="ddCard" style={{...goldPanel,padding:"20px",display:"flex",flexDirection:"column",gap:16}}>
      {Header}
      <div style={{display:"flex",flexDirection:"row",flexWrap:"wrap",gap:24,alignItems:"center"}}>
        <div style={{flex:"0 0 200px",height:200,position:"relative"}}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie 
                data={sorted} 
                cx="50%" 
                cy="50%" 
                innerRadius={58} 
                outerRadius={80} 
                paddingAngle={3} 
                dataKey="value" 
                stroke="none"
                onClick={(data) => {
                  if (data && data.name) {
                    toggleFilter(comp.category_key, data.name);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                {sorted.map((e,i)=>{
                  const isSelected = activeFilter && isOriginator && e.name === activeFilter.value;
                  const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
                  return <Cell key={i} fill={e.color} opacity={opacity}/>;
                })}
              </Pie>
              <Tooltip content={<Tip/>}/>
            </PieChart>
          </ResponsiveContainer>
          <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",pointerEvents:"none"}}>
            <span style={{fontSize:22,fontWeight:900,background:`linear-gradient(135deg,${G.goldBright},${G.gold})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>{displayTotalValue.toLocaleString()}</span>
            <span style={{fontSize:9,color:G.textMuted,textTransform:"uppercase",letterSpacing:".05em",marginTop:3}}>Total</span>
          </div>
        </div>
        <div style={{flex:"1 1 200px",display:"flex",flexDirection:"column",gap:12}}>
          {sorted.map((item,idx)=>{
            const isSelected = activeFilter && isOriginator && item.name === activeFilter.value;
            const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
            return (
              <div 
                key={idx} 
                onClick={() => toggleFilter(comp.category_key, item.name)}
                style={{
                  display:"flex", 
                  flexDirection:"column", 
                  gap:5, 
                  cursor: "pointer",
                  opacity,
                  transition: "opacity 0.2s"
                }}
              >
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <div style={{display:"flex",alignItems:"center",gap:8}}>
                    <div style={{width:8,height:8,borderRadius:"50%",background:item.color,boxShadow:`0 0 6px ${item.color}`,flexShrink:0}}/>
                    <span style={{fontSize:12,fontWeight:600,color:G.textPrimary}}>{item.name}</span>
                  </div>
                  <div style={{fontSize:12,fontWeight:800,color:"#fff",whiteSpace:"nowrap"}}>{item.value.toLocaleString()}<span style={{fontSize:10,fontWeight:400,color:G.textFaint,marginLeft:5}}>({item.pct.toFixed(1)}%)</span></div>
                </div>
                <div style={{width:"100%",height:5,background:"rgba(255,255,255,.06)",borderRadius:3,overflow:"hidden"}}>
                  <div className="ddBar" style={{width:`${item.pct}%`,height:"100%",borderRadius:3,animationDelay:`${idx*.08}s`,background:`linear-gradient(90deg,${item.color}cc,${item.color})`,boxShadow:`0 0 6px ${item.color}88`}}/>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );

  return (
    <div className="ddCard" style={{...goldPanel,padding:"20px",display:"flex",flexDirection:"column",gap:16}}>
      {Header}
      {/* Large dataset: chart on left + stats sidebar on right */}
      <div style={{display:"flex",flexDirection:"row",gap:16,alignItems:"flex-start",flexWrap:"wrap"}}>
        {/* Main bar chart */}
        <div style={{flex:"1 1 0",minWidth:0,height:barH}}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={paged} layout="vertical" margin={{top:2,right:16,bottom:4,left:8}}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" horizontal={false}/>
              <XAxis type="number" domain={[0,globalMax]} tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false} tickFormatter={(v:number)=>v>=1000?`${(v/1000).toFixed(1)}k`:v.toLocaleString()}/>
              <YAxis type="category" dataKey="name" width={yW} tick={<CustomYTick yW={yW}/>} axisLine={false} tickLine={false} />
              <Tooltip content={<Tip/>} cursor={{fill:"rgba(255,255,255,.03)"}}/>
              <Bar 
                dataKey="value" 
                radius={[0,4,4,0]} 
                maxBarSize={10} 
                isAnimationActive={paged.length<60}
                onClick={(data) => {
                  if (data && data.name) {
                    toggleFilter(comp.category_key, data.name);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                {paged.map((e,i)=>{
                  const isSelected = activeFilter && isOriginator && e.name === activeFilter.value;
                  const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
                  return <Cell key={i} fill={rankFill(i,paged.length)} opacity={opacity}/>;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        {/* Stats sidebar — fills the right horizontal space, pagination anchored bottom */}
        <div style={{flex:"1 1 180px",minWidth:180,display:"flex",flexDirection:"column",gap:10,minHeight:barH}}>
          {/* Total — most important stat, shown at top */}
          <div style={{background:G.goldBg,border:`1px solid ${G.goldBorder}`,borderRadius:10,padding:"12px 14px",display:"flex",flexDirection:"column",gap:3}}>
            <span style={{fontSize:9,fontWeight:700,color:G.textMuted,textTransform:"uppercase",letterSpacing:".06em"}}>Total</span>
            <span style={{fontSize:22,fontWeight:900,background:`linear-gradient(135deg,${G.goldBright},${G.gold})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>{displayTotalValue.toLocaleString()}</span>
            <span style={{fontSize:10,color:G.textFaint}}>{total.toLocaleString()} categories</span>
          </div>
          {/* Avg per category */}
          {(()=>{
            const avg=Math.round(displayTotalValue/(total||1));
            return (
              <div style={{background:G.silverBg,border:`1px solid ${G.silverBorder}`,borderRadius:10,padding:"10px 14px",display:"flex",flexDirection:"column",gap:3}}>
                <span style={{fontSize:9,fontWeight:700,color:G.textMuted,textTransform:"uppercase",letterSpacing:".06em"}}>Avg / Category</span>
                <span style={{fontSize:16,fontWeight:900,background:`linear-gradient(135deg,${G.silverBright},${G.silver})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>{avg.toLocaleString()}</span>
              </div>
            );
          })()}
          {/* Top-5 mini leaderboard — grows to fill available space */}
          <div style={{background:"rgba(255,255,255,.03)",border:`1px solid ${G.glassBorder}`,borderRadius:10,padding:"10px 14px",flex:1,display:"flex",flexDirection:"column",gap:8,overflow:"hidden"}}>
            <span style={{fontSize:9,fontWeight:700,color:G.textMuted,textTransform:"uppercase",letterSpacing:".06em"}}>Top 5 Overall</span>
            {sorted.slice(0,5).map((item,idx)=>{
              const pc=podiumColor(idx);
              const isSelected = activeFilter && isOriginator && item.name === activeFilter.value;
              const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
              return (
                <div 
                  key={idx} 
                  onClick={() => toggleFilter(comp.category_key, item.name)}
                  style={{
                    display:"flex",
                    flexDirection:"column",
                    gap:3,
                    cursor: "pointer",
                    opacity,
                    transition: "opacity 0.2s"
                  }}
                >
                  <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                    <span style={{fontSize:10,color:idx<3?pc:G.textPrimary,fontWeight:600,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",maxWidth:105}} title={item.name}>{item.name}</span>
                    <span style={{fontSize:10,fontWeight:800,color:idx<3?pc:"#fff",flexShrink:0,marginLeft:4}}>{item.value.toLocaleString()}</span>
                  </div>
                  <div style={{width:"100%",height:3,background:"rgba(255,255,255,.06)",borderRadius:2,overflow:"hidden"}}>
                    <div className="ddBar" style={{width:`${item.pct}%`,height:"100%",borderRadius:2,background:`linear-gradient(90deg,${pc}88,${pc})`,animationDelay:`${idx*.05}s`}}/>
                  </div>
                </div>
              );
            })}
          </div>
          {/* Pagination — anchored to bottom of sidebar */}
          {tPages>1&&(
            <div style={{marginTop:"auto",display:"flex",flexDirection:"column",gap:6}}>
              <div style={{display:"flex",gap:6}}>
                <PBtn disabled={page===0} onClick={()=>setPage(p=>Math.max(0,p-1))}>‹ Prev</PBtn>
                <PBtn disabled={page>=tPages-1} onClick={()=>setPage(p=>Math.min(tPages-1,p+1))}>Next ›</PBtn>
              </div>
              <span style={{fontSize:10,color:G.textFaint}}>Page {page+1} of {tPages} · items {page*SPAGE+1}–{Math.min((page+1)*SPAGE,total)}</span>
            </div>
          )}
        </div>
      </div>
      {(isM || isL) && (
        <div style={{borderTop:`1px solid ${G.goldBorder}`,paddingTop:14}}>
          <span style={{fontSize:9,fontWeight:800,color:G.textMuted,textTransform:"uppercase",letterSpacing:".1em",display:"block",marginBottom:10}}>Top {topList.length} by Volume</span>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            {topList.map((item,idx)=>{
              const pc=podiumColor(idx);
              const pctW=item.pct;
              const isSelected = activeFilter && isOriginator && item.name === activeFilter.value;
              const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
              return (
                <div 
                  key={idx} 
                  onClick={() => toggleFilter(comp.category_key, item.name)}
                  style={{
                    display:"flex",
                    alignItems:"center",
                    gap:10,
                    fontSize:11,
                    cursor: "pointer",
                    opacity,
                    transition: "opacity 0.2s"
                  }}
                >
                  <span style={{fontSize:10,fontWeight:800,color:pc,width:22,textAlign:"right",flexShrink:0,textShadow:idx<3?`0 0 6px ${pc}66`:"none"}}>#{idx+1}</span>
                  <span style={{width:130,color:G.textPrimary,fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",flexShrink:0}} title={item.name}>{item.name}</span>
                  <div style={{flex:1,height:6,background:"rgba(255,255,255,.06)",borderRadius:3,overflow:"hidden"}}>
                    <div className="ddBar" style={{width:`${pctW}%`,height:"100%",borderRadius:3,background:`linear-gradient(90deg,${pc}88,${pc})`,animationDelay:`${idx*.04}s`}}/>
                  </div>
                  <span style={{fontWeight:800,color:idx<3?pc:"#fff",whiteSpace:"nowrap",width:60,textAlign:"right",textShadow:idx<3?`0 0 6px ${pc}44`:"none"}}>{item.value.toLocaleString()}</span>
                  <span style={{color:G.textFaint,whiteSpace:"nowrap",width:42,textAlign:"right"}}>{item.pct.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Record Cards ─────────────────────────────────────────────────────────────
const CP=6,TP=20;
function RecordCards({comp, activeFilter}:{comp:RecC; activeFilter: {key: string; value: string} | null}) {
  const [mode,setMode]=useState<"card"|"table">("card");
  const [page,setPage]=useState(0);
  useEffect(()=>{injectAnimations();},[]);
  if (!comp.data?.length) return null;

  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  if (!displayData.length) return null;
  const ps=mode==="card"?CP:TP;
  const tp=Math.ceil(displayData.length/ps);
  const vis=displayData.slice(page*ps,(page+1)*ps);
  const first=displayData[0];
  const keys=Object.keys(first).filter(k=>!k.startsWith("_"));
  const sk=keys.filter(k=>typeof first[k]==="string");
  const tk=sk.find(k=>!/id|code|tag|pk|no|serial|phone|email/i.test(k))||sk[0]||keys[0];
  const bk=keys.find(k=>k!==tk&&/code|tag|no|serial|status/i.test(k));
  const isSingle=comp.data.length===1;
  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:2}}>
            <div style={{width:3,height:16,background:`linear-gradient(180deg,${G.goldBright},${G.goldDim})`,borderRadius:2,boxShadow:`0 0 6px ${G.goldGlow}`}}/>
            <h3 style={{margin:0,fontSize:13,fontWeight:900,background:`linear-gradient(90deg,${G.goldBright},${G.gold})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",textTransform:"uppercase",letterSpacing:".08em"}}>{comp.title}</h3>
          </div>
          <p style={{margin:0,fontSize:11,color:G.textMuted}}>{isSingle?"Detail View":`${comp.data.length} records`}</p>
        </div>
        {!isSingle&&<button onClick={()=>{setMode(v=>v==="card"?"table":"card");setPage(0);}} className="ddBtn" style={{background:G.goldBg,border:`1px solid ${G.goldBorder}`,borderRadius:8,color:G.gold,fontSize:11,fontWeight:700,padding:"7px 14px",cursor:"pointer",fontFamily:"inherit"}}>{mode==="card"?"⊞ Table View":"⊟ Card View"}</button>}
      </div>
      {mode==="card"&&isSingle&&(
        <div className="ddCard" style={{...goldPanel,padding:"20px",display:"flex",flexDirection:"column",gap:14}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",borderBottom:`1px solid ${G.goldBorder}`,paddingBottom:12}}>
            <span style={{fontSize:15,fontWeight:800,color:G.gold,textShadow:`0 0 10px ${G.goldGlow}`}}>{String(first[tk]||"Record Details")}</span>
            {!!(bk&&first[bk])&&<span style={{fontSize:9,fontWeight:800,color:G.goldBright,background:G.goldBg,border:`1px solid ${G.goldBorder}`,borderRadius:5,padding:"3px 9px",textTransform:"uppercase"}}>{String(first[bk])}</span>}
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))",gap:"12px 18px"}}>
            {keys.filter(k=>k!==tk&&k!==bk).map(key=>(
              <div key={key} style={{display:"flex",flexDirection:"column",gap:3}}>
                <span style={{fontSize:9,color:G.textMuted,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em"}}>{humanKey(key)}</span>
                <span style={{fontSize:12,color:G.textPrimary,fontWeight:500,wordBreak:"break-word"}}>{(first[key]===null||first[key]===undefined||first[key]===""||String(first[key])==="null")?<span style={{color:G.textFaint}}>—</span>:String(first[key])}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {mode==="card"&&!isSingle&&(
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(280px,1fr))",gap:12,padding:"0 4px",boxSizing:"border-box"}}>
          {vis.map((item,idx)=>{
            const ct=String(item[tk]||"Record");
            const cb=bk?String(item[bk]):"";
            const dk=keys.filter(k=>k!==tk&&k!==bk).slice(0,6);
            return (
              <div key={idx} className="ddCard" style={{...glassCard,padding:"14px 16px",display:"flex",flexDirection:"column",gap:10,cursor:"default",transition:"border-color .2s,box-shadow .2s",animationDelay:`${idx*.06}s`}}
                onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.borderColor=G.goldBorder;(e.currentTarget as HTMLElement).style.boxShadow=`0 8px 32px rgba(0,0,0,.5),0 0 24px ${G.goldGlow}`;}}
                onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.borderColor=G.glassBorder;(e.currentTarget as HTMLElement).style.boxShadow=glassCard.boxShadow as string;}}
              >
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:10}}>
                  <span style={{fontSize:13,fontWeight:700,color:"#fff",lineHeight:1.3}}>{ct}</span>
                  {cb&&<span style={{fontSize:9,fontWeight:800,color:G.goldBright,background:G.goldBg,border:`1px solid ${G.goldBorder}`,borderRadius:4,padding:"2px 7px",textTransform:"uppercase",whiteSpace:"nowrap",flexShrink:0}}>{cb}</span>}
                </div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,borderTop:`1px solid ${G.glassBorder}`,paddingTop:10}}>
                  {dk.map(key=>(
                    <div key={key} style={{display:"flex",flexDirection:"column",gap:2}}>
                      <span style={{fontSize:9,color:G.textMuted,fontWeight:700,textTransform:"uppercase",letterSpacing:".04em"}}>{humanKey(key)}</span>
                      <span style={{fontSize:11,color:G.textPrimary,fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={(item[key]===null||item[key]===undefined||String(item[key])==="null")?"":String(item[key])}>{(item[key]===null||item[key]===undefined||item[key]===""||String(item[key])==="null")?<span style={{color:G.textFaint}}>—</span>:String(item[key])}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {mode==="table"&&(
        <div style={{overflowX:"auto",WebkitOverflowScrolling:"touch",borderRadius:10,border:`1px solid ${G.goldBorder}`,boxShadow:`0 0 24px rgba(0,0,0,.3)`}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:12,textAlign:"left"}}>
            <thead><tr style={{background:`linear-gradient(90deg,rgba(212,175,55,.12),rgba(212,175,55,.04))`,borderBottom:`1.5px solid ${G.goldBorder}`}}>{keys.map(col=><th key={col} style={{padding:"10px 14px",fontWeight:800,color:G.gold,fontSize:10,textTransform:"uppercase",letterSpacing:".06em",whiteSpace:"nowrap"}}>{humanKey(col)}</th>)}</tr></thead>
            <tbody>{vis.map((row,ri)=><tr key={ri} className="ddTr" style={{borderBottom:`1px solid ${G.glassBorder}`,background:ri%2===1?"rgba(255,255,255,.012)":"transparent"}}>{keys.map(k=><td key={k} style={{padding:"8px 14px",color:G.textPrimary}}>{(row[k] === null || row[k] === undefined || row[k] === "" || String(row[k]) === "null") ? <span style={{color:G.textFaint}}>—</span> : String(row[k])}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
      {tp>1&&<div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:10,marginTop:4}}><PBtn disabled={page===0} onClick={()=>setPage(p=>Math.max(0,p-1))}>‹ Prev</PBtn><span style={{fontSize:11,color:G.textMuted}}>Page {page+1} / {tp} · {comp.data.length} records</span><PBtn disabled={page>=tp-1} onClick={()=>setPage(p=>Math.min(tp-1,p+1))}>Next ›</PBtn></div>}
    </div>
  );
}



// ─── Bar Chart ────────────────────────────────────────────────────────────────
function DynBar({comp, activeFilter, toggleFilter}:{comp:BarC; activeFilter: {key: string; value: string} | null; toggleFilter: (key: string, value: string) => void}) {
  useEffect(()=>{injectAnimations();},[]);
  if (!comp.data?.length) return null;

  const isOriginator = activeFilter && activeFilter.key === comp.x_key;
  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && !isOriginator && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  const d=displayData.map(r=>({...r,[comp.y_key]:typeof r[comp.y_key]==="number"?r[comp.y_key]:Number(r[comp.y_key])||0}));
  const ml=Math.max(...d.map((r:any)=>String(r[comp.x_key]||"").length), 1);
  const yW=Math.min(Math.max(ml*7.2, 80), 180);
  return (
    <div style={{display:"flex",flexDirection:"column"}}>
      <SecLabel label={comp.title}/>
      <div style={{overflowX:"auto",WebkitOverflowScrolling:"touch",width:"100%",height:Math.min(d.length*28+60,380)}}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={d} layout="vertical" margin={{top:4,right:20,bottom:4,left:8}}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" horizontal={false}/>
            <XAxis type="number" tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false} tickFormatter={(v:number)=>v>=1000?`${(v/1000).toFixed(1)}k`:v.toLocaleString()}/>
            <YAxis type="category" dataKey={comp.x_key} width={yW} tick={<CustomYTick yW={yW}/>} axisLine={false} tickLine={false} />
            <Tooltip content={<Tip/>} cursor={{fill:"rgba(255,255,255,.03)"}}/>
            <Bar 
              dataKey={comp.y_key} 
              maxBarSize={10} 
              radius={[0,3,3,0]} 
              fill={G.gold} 
              name={humanKey(comp.y_key)}
              onClick={(data: any) => {
                const val = data?.payload?.[comp.x_key];
                if (val !== undefined) {
                  toggleFilter(comp.x_key, String(val));
                }
              }}
              style={{ cursor: "pointer" }}
            >
              {d.map((entry, idx) => {
                const isSelected = activeFilter && isOriginator && String(entry[comp.x_key]) === activeFilter.value;
                const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
                return <Cell key={`cell-${idx}`} fill={G.gold} opacity={opacity} />;
              })}
              {d.length < 30 && (
                <LabelList dataKey={comp.y_key} position="right" fill={G.textMuted} fontSize={9} offset={5} />
              )}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Time Series ──────────────────────────────────────────────────────────────
function DynTs({comp, activeFilter}:{comp:TsC; activeFilter: {key: string; value: string} | null}) {
  useEffect(()=>{injectAnimations();},[]);
  if (!comp.data?.length) return null;

  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  return (
    <div style={{display:"flex",flexDirection:"column"}}>
      <SecLabel label={comp.title}/>
      <div style={{overflowX:"auto",WebkitOverflowScrolling:"touch",width:"100%",height:240}}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={displayData} margin={{top:4,right:24,bottom:4,left:0}}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)"/>
            {/* BUG 2.3 FIX — angled labels prevent overlap on mobile */}
            <XAxis dataKey={comp.x_key} tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false} interval="preserveStartEnd" angle={-35} textAnchor="end" height={45}/>
            <YAxis tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false} tickFormatter={(v:number)=>v>=1000?`${(v/1000).toFixed(1)}k`:v.toLocaleString()}/>
            <Tooltip content={<Tip/>}/>
            {comp.y_keys.length>1&&<Legend wrapperStyle={{fontSize:11,color:G.textMuted}}/>}
            {comp.y_keys.map((k,i)=>(
              <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i%CHART_COLORS.length]} strokeWidth={2.5} dot={{r:3,fill:CHART_COLORS[i%CHART_COLORS.length],strokeWidth:0}} activeDot={{r:6,strokeWidth:2,stroke:G.gold}} name={k}/>
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Status detection via sem() — no hardcoded word list in table renderer ────
// sem() returns the same color for known status words regardless of idx,
// but falls through to CHART_COLORS[idx % length] for everything else.
// If sem(cell, 0) === sem(cell, 1) → a status keyword was matched.
function isStatusValue(cell: string): boolean {
  // BUG 6.4 FIX — normalize case before checking
  if (!cell || cell.length > 24) return false;
  const n = cell.toLowerCase().trim();
  return sem(n, 0) === sem(n, 1);
}

function getStatusStyle(cell: string): { color: string; bg: string } | null {
  if (!isStatusValue(cell)) return null;
  const color = sem(cell, 0);
  const bgMap: Record<string, string> = {
    "#10b981": "rgba(16,185,129,0.12)",
    "#f43f5e": "rgba(244,63,94,0.12)",
    "#f59e0b": "rgba(245,158,11,0.12)",
  };
  return { color, bg: bgMap[color] || "rgba(255,255,255,0.05)" };
}

// ─── Table ────────────────────────────────────────────────────────────────────
function DynTable({comp, activeFilter, toggleFilter}:{comp:TabC; activeFilter: {key: string; value: string} | null; toggleFilter: (key: string, value: string) => void}) {
  const [page,setPage]=useState(0);
  useEffect(()=>{injectAnimations();},[]);
  if (!comp.columns?.length||!comp.rows?.length) return null;

  const filterColIdx = activeFilter 
    ? comp.columns.findIndex(colName => colName.toLowerCase() === activeFilter.key.toLowerCase() || humanKey(activeFilter.key).toLowerCase() === colName.toLowerCase())
    : -1;

  const displayRows = (activeFilter && filterColIdx !== -1)
    ? comp.rows.filter(row => String(row[filterColIdx]) === activeFilter.value)
    : comp.rows;

  const tp=Math.ceil(displayRows.length/TP);
  const vis=displayRows.slice(page*TP,(page+1)*TP);

  // Compute column statistics for conditional formatting
  const parsedCols = comp.columns.map((colName, colIdx) => {
    const vals = displayRows
      .map(row => {
        const str = row[colIdx];
        if (!str || str === "—") return null;
        const clean = str.replace(/[$,%]/g, "").trim();
        const val = Number(clean);
        return isNaN(val) ? null : val;
      })
      .filter((v): v is number => v !== null);
    if (vals.length === 0) return { isNumeric: false, threshold: 0 };
    const sorted = [...vals].sort((a, b) => b - a);
    const index = Math.max(0, Math.floor(sorted.length * 0.2) - 1);
    const threshold = sorted[index] ?? 0;
    return { isNumeric: true, threshold };
  });

  return (
    <div style={{display:"flex",flexDirection:"column",gap:10}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <SecLabel label={comp.title}/>
        {comp.note&&<span style={{fontSize:10,color:G.textFaint,fontStyle:"italic"}}>{comp.note}</span>}
      </div>
      <div style={{overflowX:"auto",borderRadius:10,border:`1px solid ${G.goldBorder}`,boxShadow:`0 0 24px rgba(0,0,0,.3)`}}>
        {/* BUG 6.3 FIX — tableLayout:fixed prevents single long cell from stretching table */}
        <table style={{width:"100%",tableLayout:"fixed",borderCollapse:"collapse",fontSize:12,textAlign:"left"}}>
          <thead>
            <tr style={{background:`linear-gradient(90deg,rgba(212,175,55,.12),rgba(212,175,55,.04))`,borderBottom:`1.5px solid ${G.goldBorder}`}}>
              {comp.columns.map((c, ci)=>(
                <th key={c} style={{
                  padding:"10px 14px",
                  fontWeight:800,
                  color:G.gold,
                  whiteSpace:"nowrap",
                  fontSize:10,
                  letterSpacing:".06em",
                  textTransform:"uppercase",
                  textAlign: parsedCols[ci].isNumeric ? "right" : "left"
                }}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vis.map((row,ri)=>(
              <tr key={ri} className="ddTr" style={{borderBottom:ri<vis.length-1?`1px solid ${G.glassBorder}`:"none",background:ri%2===1?"rgba(255,255,255,.012)":"transparent"}}>
                {row.map((cell,ci)=>{
                  const isNumeric = parsedCols[ci].isNumeric;
                  const isPercent = cell.endsWith("%") && !isNaN(parseFloat(cell));
                  const statusStyle = getStatusStyle(cell);

                  let cellContent: React.ReactNode = cell;
                  if (cell === "—") {
                    cellContent = <span style={{color:G.textFaint}}>—</span>;
                  } else if (statusStyle) {
                    cellContent = (
                      <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "2px 8px",
                        borderRadius: 12,
                        fontSize: 10,
                        fontWeight: 700,
                        color: statusStyle.color,
                        background: statusStyle.bg,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em"
                      }}>
                        {cell}
                      </span>
                    );
                  } else if (isPercent) {
                    const val = parseFloat(cell);
                    cellContent = (
                      <div style={{display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end"}}>
                        <span style={{fontSize: 11, width: 42, textAlign: "right"}}>{cell}</span>
                        <div style={{flex: 1, maxWidth: 80, height: 6, background: "rgba(255,255,255,.06)", borderRadius: 3, overflow: "hidden", minWidth: 40}}>
                          <div style={{width: `${Math.min(Math.max(val, 0), 100)}%`, height: "100%", background: G.gold, borderRadius: 3}} />
                        </div>
                      </div>
                    );
                  } else if (isNumeric) {
                    const clean = cell.replace(/[$,%]/g, "").trim();
                    const val = Number(clean);
                    const isTop20 = !isNaN(val) && val >= parsedCols[ci].threshold;
                    cellContent = (
                      <span style={{
                        padding: isTop20 ? "2px 6px" : "0px",
                        borderRadius: 4,
                        background: isTop20 ? "rgba(212,175,55,0.08)" : "transparent",
                        color: isTop20 ? G.gold : G.textPrimary,
                        fontWeight: isTop20 ? 700 : 500
                      }}>
                        {cell}
                      </span>
                    );
                  }

                  return (
                    <td key={ci} style={{
                      padding:"9px 14px",
                      color:G.textPrimary,
                      maxWidth:300,
                      overflow:"hidden",
                      textOverflow:"ellipsis",
                      whiteSpace:"nowrap",
                      textAlign: isNumeric ? "right" : "left"
                    }} title={cell}>
                      {cellContent}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tp>1&&<div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:10}}><PBtn disabled={page===0} onClick={()=>setPage(p=>Math.max(0,p-1))}>‹ Prev</PBtn><span style={{fontSize:11,color:G.textMuted}}>Page {page+1} / {tp} · {displayRows.length} rows</span><PBtn disabled={page>=tp-1} onClick={()=>setPage(p=>Math.min(tp-1,p+1))}>Next ›</PBtn></div>}
    </div>
  );
}

// ─── Text ─────────────────────────────────────────────────────────────────────
function TxtBlock({value}:{value:string}) {
  useEffect(()=>{injectAnimations();},[]);
  const isBullet=value.includes("\n•")||value.startsWith("•");
  if (isBullet) {
    return (
      <div style={{display:"flex",flexDirection:"column",gap:8}}>
        {value.split("\n").filter(l=>l.trim()).map((line,i)=>(
          <div key={i} style={{display:"flex",alignItems:"flex-start",gap:10}}>
            <span style={{color:G.gold,flexShrink:0,marginTop:2,fontSize:13,filter:`drop-shadow(0 0 4px ${G.goldGlow})`}}>◆</span>
            <span style={{fontSize:13,color:G.textPrimary,lineHeight:1.65}}>{line.replace(/^•\s*/,"").trim()}</span>
          </div>
        ))}
      </div>
    );
  }
  return <p style={{margin:0,fontSize:13,color:"rgba(255,255,255,.72)",lineHeight:1.7}}>{value}</p>;
}

// ─── Layout Grouper — pairs components to fill horizontal space ───────────────
// Rules:
//   • bar_chart + time_series_chart adjacent → 60/40 split row
//   • bar_chart + bar_chart adjacent → 50/50 split row
//   • time_series + time_series → 50/50 split row
//   • text + table (small) → 35/65 split row
//   • everything else → full-width row
// ─── Donut / Pie Chart ───────────────────────────────────────────────────────
function DynDonut({comp, activeFilter, toggleFilter}:{comp:DonutC; activeFilter: {key: string; value: string} | null; toggleFilter: (key: string, value: string) => void}) {
  if (!comp.data?.length) return null;

  const isOriginator = activeFilter && activeFilter.key === comp.category_key;
  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && !isOriginator && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  const rows = displayData.map((r,i)=>{
    const v = typeof r[comp.metric_key]==="number"?r[comp.metric_key] as number:Number(r[comp.metric_key])||0;
    const name = String(r[comp.category_key]||"?");
    return {name, value:v, color:sem(name,i)};
  });

  // BUG 4.2 FIX — total must always reflect only the currently visible filtered rows
  const total = rows.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:4}}>
      <SecLabel label={comp.title}/>
      <div style={{display:"flex",flexDirection:"row",gap:20,alignItems:"center",flexWrap:"wrap"}}>
        <div style={{position:"relative",width:170,height:170,flexShrink:0}}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie 
                data={rows} 
                cx="50%" 
                cy="50%" 
                innerRadius={50} 
                outerRadius={78} 
                paddingAngle={3} 
                dataKey="value" 
                stroke="none" 
                animationBegin={0}
                onClick={(data) => {
                  if (data && data.name) {
                    toggleFilter(comp.category_key, data.name);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                {rows.map((e,i)=>{
                  const isSelected = activeFilter && isOriginator && e.name === activeFilter.value;
                  const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
                  return <Cell key={i} fill={e.color} opacity={opacity}/>;
                })}
              </Pie>
              <Tooltip content={<Tip/>}/>
            </PieChart>
          </ResponsiveContainer>
          <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",pointerEvents:"none"}}>
            <span style={{fontSize:17,fontWeight:900,background:`linear-gradient(135deg,${G.goldBright},${G.gold})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>{total.toLocaleString()}</span>
            <span style={{fontSize:9,color:G.textMuted,textTransform:"uppercase",letterSpacing:".05em"}}>Total</span>
          </div>
        </div>
        <div style={{flex:1,minWidth:120,display:"flex",flexDirection:"column",gap:6,maxHeight:200,overflowY:"auto",flexWrap:"nowrap"}}>
          {rows.map((item,idx)=>{
            const isSelected = activeFilter && isOriginator && item.name === activeFilter.value;
            const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
            return (
              <div 
                key={idx} 
                onClick={() => toggleFilter(comp.category_key, item.name)}
                style={{
                  display:"flex",
                  alignItems:"center",
                  gap:8,
                  cursor:"pointer",
                  opacity,
                  transition:"opacity 0.2s"
                }}
              >
                <div style={{width:8,height:8,borderRadius:2,background:item.color,flexShrink:0}}/>
                <span style={{flex:1,fontSize:11,color:G.textPrimary,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={item.name}>{item.name}</span>
                <span style={{fontSize:11,fontWeight:800,color:"#fff",whiteSpace:"nowrap"}}>{item.value.toLocaleString()}</span>
                <span style={{fontSize:10,color:G.textFaint,width:38,textAlign:"right"}}>{total>0?((item.value/total)*100).toFixed(1):0}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Grouped Bar Chart ────────────────────────────────────────────────────────
function DynGroupedBar({comp, activeFilter, toggleFilter}:{comp:GrpBarC; activeFilter: {key: string; value: string} | null; toggleFilter: (key: string, value: string) => void}) {
  const [page, setPage] = useState(0);
  useEffect(()=>{injectAnimations();},[]);
  // BUG 3.3 FIX — reset to page 0 whenever the active filter changes
  useEffect(()=>{ setPage(0); },[activeFilter]);
  if (!comp.data?.length) return null;

  const isOriginator = activeFilter && activeFilter.key === comp.category_key;
  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && !isOriginator && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  const d = displayData.map(r=>({
    ...r,
    [comp.category_key]: String(r[comp.category_key]||"")
  }));
  const total = d.length;
  const GPAGE = 6; // Compact view per page for clustered bars
  const tPages = Math.ceil(total / GPAGE);
  const paged = d.slice(page * GPAGE, (page + 1) * GPAGE);

  // Spacing: fits 8 clustered bars per row beautifully without overlapping
  const barH = Math.min(paged.length * (comp.metric_keys.length * 9 + 20) + 60, 580);
  
  const ml = Math.max(...d.map((r:any)=>String(r[comp.category_key]).length), 1);
  const yW = Math.min(Math.max(ml*7.2, 80), 180);
  const GRP_COLORS = [G.gold,G.silver,"#818cf8","#34d399","#f472b6","#fb923c","#60a5fa","#a78bfa"];
  
  return (
    <div style={{display:"flex",flexDirection:"column",gap:4}}>
      <SecLabel label={comp.title}/>
      <div style={{overflowX:"auto",WebkitOverflowScrolling:"touch",width:"100%",height:barH}}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={paged} layout="vertical" margin={{top:4,right:20,bottom:4,left:8}}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" horizontal={false}/>
            <XAxis type="number" tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false}
              tickFormatter={(v:number)=>v>=1000?`${(v/1000).toFixed(1)}k`:v.toLocaleString()}/>
            <YAxis type="category" dataKey={comp.category_key} width={yW} tick={<CustomYTick yW={yW}/>} axisLine={false} tickLine={false} />
            <Tooltip content={<Tip/>} cursor={{fill:"rgba(255,255,255,.03)"}}/>
            <Legend wrapperStyle={{fontSize:10,color:G.textMuted,paddingTop:6}} formatter={(v:string)=>humanKey(v)}/>
            {comp.metric_keys.map((k,i)=>(
              <Bar 
                key={k} 
                dataKey={k} 
                fill={GRP_COLORS[i%GRP_COLORS.length]}
                radius={[0,3,3,0]} 
                maxBarSize={14} 
                name={humanKey(k)}
                onClick={(data: any) => {
                  const val = data?.payload?.[comp.category_key];
                  if (val !== undefined) {
                    toggleFilter(comp.category_key, String(val));
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                {paged.map((entry, idx) => {
                  const isSelected = activeFilter && isOriginator && String(entry[comp.category_key]) === activeFilter.value;
                  const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
                  return <Cell key={`cell-${idx}`} fill={GRP_COLORS[i%GRP_COLORS.length]} opacity={opacity} />;
                })}
                {comp.metric_keys.length === 1 && paged.length < 20 && (
                  <LabelList dataKey={k} position="right" fill={G.textMuted} fontSize={10} offset={6}
                    formatter={(v: unknown) => { const n = Number(v); return isNaN(n) ? String(v) : n >= 1000 ? `${(n/1000).toFixed(1)}k` : Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1); }}
                  />
                )}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* Pagination controls inside dashboard card */}
      {tPages > 1 && (
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:14,borderTop:"1px solid rgba(255,255,255,.05)",paddingTop:12}}>
          <PBtn disabled={page===0} onClick={()=>setPage(p=>p-1)}>‹ Previous</PBtn>
          <span style={{fontSize:11,color:G.textMuted}}>Showing {page*GPAGE+1}–{Math.min((page+1)*GPAGE,total)} of {total} categories</span>
          <PBtn disabled={page>=tPages-1} onClick={()=>setPage(p=>p+1)}>Next ›</PBtn>
        </div>
      )}
    </div>
  );
}

// ─── Area Chart ───────────────────────────────────────────────────────────────
function DynArea({comp, activeFilter}:{comp:AreaC; activeFilter: {key: string; value: string} | null}) {
  if (!comp.data?.length) return null;

  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  const AREA_COLORS = [G.gold,G.silver,"#818cf8","#34d399","#f472b6"];
  return (
    <div style={{display:"flex",flexDirection:"column",gap:4}}>
      <SecLabel label={comp.title}/>
      <div style={{overflowX:"auto",WebkitOverflowScrolling:"touch",width:"100%",height:230}}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={displayData} margin={{top:4,right:20,bottom:4,left:0}}>
            <defs>
              {comp.y_keys.map((k,i)=>(
                // BUG 2.4 FIX — unique gradient IDs prevent ID clashes across multiple area chart instances
                <linearGradient key={k} id={`aGrad_${comp.title.replace(/\s/g,'_')}_${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={AREA_COLORS[i%AREA_COLORS.length]} stopOpacity={0.28}/>
                  <stop offset="95%" stopColor={AREA_COLORS[i%AREA_COLORS.length]} stopOpacity={0}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)"/>
            {/* BUG 2.3 FIX — angled labels prevent overlap on mobile */}
            <XAxis dataKey={comp.x_key} tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false} interval="preserveStartEnd" angle={-35} textAnchor="end" height={45}/>
            <YAxis tick={{fill:G.textMuted,fontSize:10}} axisLine={false} tickLine={false}
              tickFormatter={(v:number)=>v>=1000?`${(v/1000).toFixed(1)}k`:v.toLocaleString()}/>
            <Tooltip content={<Tip/>}/>
            {comp.y_keys.length>1&&<Legend wrapperStyle={{fontSize:10,color:G.textMuted}} formatter={(v:string)=>humanKey(v)}/>}
            {comp.y_keys.map((k,i)=>(
              <Area key={k} type="monotone" dataKey={k} stroke={AREA_COLORS[i%AREA_COLORS.length]}
                fill={`url(#aGrad_${comp.title.replace(/\s/g,'_')}_${i})`} strokeWidth={2} dot={false} activeDot={{r:4}} name={humanKey(k)}/>
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Gauge Chart ──────────────────────────────────────────────────────────────
function DynGauge({comp}:{comp:GaugeC}) {
  const val = Math.min(Math.max(comp.value, 0), 100);
  const data = [
    { name: "Value", value: val },
    { name: "Remaining", value: 100 - val }
  ];
  return (
    <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",height:"100%"}}>
      <SecLabel label={comp.title}/>
      <div style={{position:"relative",width:200,height:120,marginTop:10}}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius={58}
              outerRadius={75}
              paddingAngle={0}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={G.gold} />
              <Cell fill="rgba(255,255,255,0.06)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div style={{
          position: "absolute",
          bottom: 10,
          left: 0,
          right: 0,
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center"
        }}>
          <span style={{fontSize: 22, fontWeight: 900, color: "#fff", lineHeight: 1}}>{val}%</span>
        </div>
      </div>
    </div>
  );
}

// ─── Scatter Chart ────────────────────────────────────────────────────────────
function DynScatter({comp, activeFilter, toggleFilter}:{comp:ScatterC; activeFilter: {key: string; value: string} | null; toggleFilter: (key: string, value: string) => void}) {
  useEffect(()=>{injectAnimations();},[]);
  if (!comp.data?.length) return null;

  const categoryKey = comp.label_key;
  const isOriginator = activeFilter && categoryKey && activeFilter.key === categoryKey;
  const hasFilterKey = activeFilter && comp.data && comp.data.length > 0 && (activeFilter.key in comp.data[0]);
  const displayData = (activeFilter && !isOriginator && hasFilterKey)
    ? comp.data.filter(r => String(r[activeFilter.key]) === activeFilter.value)
    : comp.data;

  const data = displayData.map((r, idx) => ({
    ...r,
    x: Number(r[comp.x_key]) || 0,
    y: Number(r[comp.y_key]) || 0,
    label: comp.label_key ? String(r[comp.label_key] || "") : `Point ${idx + 1}`
  }));

  return (
    <div style={{display:"flex",flexDirection:"column",gap:4}}>
      <SecLabel label={comp.title}/>
      {/* BUG 8.2 FIX — axis title text rendered above/below instead of as axis label props */}
      <div style={{fontSize:9,color:G.textMuted,textAlign:"center",marginBottom:2}}>{humanKey(comp.y_key)} vs {humanKey(comp.x_key)}</div>
      <div style={{overflowX:"auto",WebkitOverflowScrolling:"touch",width:"100%",height:240}}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{top:12,right:20,bottom:4,left:0}}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)"/>
            <XAxis 
              type="number" 
              dataKey="x" 
              name={humanKey(comp.x_key)} 
              tick={{fill:G.textMuted,fontSize:10}} 
              axisLine={false} 
              tickLine={false}
            />
            <YAxis 
              type="number" 
              dataKey="y" 
              name={humanKey(comp.y_key)} 
              tick={{fill:G.textMuted,fontSize:10}} 
              axisLine={false} 
              tickLine={false}
            />
            <Tooltip 
              cursor={{ strokeDasharray: '3 3' }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload;
                  return (
                    <div style={{background:"rgba(20,20,20,0.9)",border:`1px solid ${G.goldBorder}`,padding:"8px 12px",borderRadius:8,fontSize:11}}>
                      <div style={{fontWeight:700,color:"#fff",marginBottom:4}}>{d.label}</div>
                      <div style={{color:G.textMuted}}>{humanKey(comp.x_key)}: <span style={{color:"#fff",fontWeight:600}}>{d.x.toLocaleString()}</span></div>
                      <div style={{color:G.textMuted}}>{humanKey(comp.y_key)}: <span style={{color:"#fff",fontWeight:600}}>{d.y.toLocaleString()}</span></div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Scatter 
              name={comp.title} 
              data={data}
              onClick={(dData: any) => {
                if (categoryKey && dData && dData.payload && (dData.payload as any)[categoryKey]) {
                  toggleFilter(categoryKey, String((dData.payload as any)[categoryKey]));
                }
              }}
              style={{ cursor: categoryKey ? "pointer" : "default" }}
            >
              {data.map((entry, idx) => {
                const isSelected = activeFilter && isOriginator && categoryKey && String((entry as any)[categoryKey]) === activeFilter.value;
                const opacity = activeFilter && isOriginator ? (isSelected ? 1.0 : 0.25) : 1.0;
                return (
                  <Cell 
                    key={`cell-${idx}`} 
                    fill={G.gold} 
                    stroke={G.goldDim} 
                    strokeWidth={0.5}
                    r={5}
                    opacity={opacity}
                  />
                );
              })}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {/* BUG 8.2 FIX — x-axis title below chart */}
      <div style={{fontSize:9,color:G.textMuted,textAlign:"center",marginTop:4}}>{humanKey(comp.x_key)}</div>
    </div>
  );
}

type LayoutGroup = { comps: DC[]; cols: string };
function layoutGroups(comps: DC[]): LayoutGroup[] {
  const groups: LayoutGroup[] = [];
  const CHART_TYPES = new Set(["bar_chart", "time_series_chart", "area_chart", "grouped_bar_chart", "dashboard_summary", "donut_chart", "scatter_chart", "gauge_chart"]);
  
  let i = 0;
  while (i < comps.length) {
    const a = comps[i];
    const b = comps[i + 1];
    
    // Rule 1: bar_chart + time_series_chart (or vice versa) -> "3fr 2fr" or "2fr 3fr"
    if (b && a.type === "bar_chart" && b.type === "time_series_chart") {
      groups.push({ comps: [a, b], cols: "3fr 2fr" });
      i += 2;
    } else if (b && a.type === "time_series_chart" && b.type === "bar_chart") {
      groups.push({ comps: [a, b], cols: "2fr 3fr" });
      i += 2;
    }
    // Rule 2: donut_chart + bar_chart (or vice versa) -> "2fr 3fr" or "3fr 2fr"
    else if (b && a.type === "donut_chart" && b.type === "bar_chart") {
      groups.push({ comps: [a, b], cols: "2fr 3fr" });
      i += 2;
    } else if (b && a.type === "bar_chart" && b.type === "donut_chart") {
      groups.push({ comps: [a, b], cols: "3fr 2fr" });
      i += 2;
    }
    // Rule 3: time_series_chart + bar_chart -> "1fr 1fr"
    else if (b && a.type === "time_series_chart" && b.type === "bar_chart") {
      groups.push({ comps: [a, b], cols: "1fr 1fr" });
      i += 2;
    }
    // Rule 4: bar_chart + bar_chart -> "1fr 1fr"
    else if (b && a.type === "bar_chart" && b.type === "bar_chart") {
      groups.push({ comps: [a, b], cols: "1fr 1fr" });
      i += 2;
    }
    // Rule 5: text + table (or vice versa) -> "2fr 3fr" or "3fr 2fr"
    else if (b && a.type === "text" && b.type === "table") {
      groups.push({ comps: [a, b], cols: "2fr 3fr" });
      i += 2;
    } else if (b && a.type === "table" && b.type === "text") {
      groups.push({ comps: [a, b], cols: "3fr 2fr" });
      i += 2;
    }
    // Fallback: General Donut pairing with other summary/grouped_bar
    else if (b && a.type === "donut_chart" && (b.type === "dashboard_summary" || b.type === "grouped_bar_chart")) {
      groups.push({ comps: [a, b], cols: "2fr 3fr" });
      i += 2;
    } else if (b && (a.type === "dashboard_summary" || a.type === "grouped_bar_chart") && b.type === "donut_chart") {
      groups.push({ comps: [a, b], cols: "3fr 2fr" });
      i += 2;
    }
    // Fallback: Pair two same-type charts side-by-side (50/50 split)
    else if (b && CHART_TYPES.has(a.type) && CHART_TYPES.has(b.type) && a.type === b.type) {
      groups.push({ comps: [a, b], cols: "1fr 1fr" });
      i += 2;
    }
    // Fallback: Pair text block next to chart
    else if (b && a.type === "text" && CHART_TYPES.has(b.type)) {
      groups.push({ comps: [a, b], cols: "2fr 3fr" });
      i += 2;
    } else if (b && CHART_TYPES.has(a.type) && b.type === "text") {
      groups.push({ comps: [a, b], cols: "3fr 2fr" });
      i += 2;
    } else {
      groups.push({ comps: [a], cols: "1fr" });
      i++;
    }
  }
  return groups;
}

// ─── Router ───────────────────────────────────────────────────────────────────
function renderComp(
  comp: DC,
  index: number,
  activeFilter: {key: string; value: string} | null,
  toggleFilter: (key: string, value: string) => void
): React.ReactNode {
  const wrap=(children:React.ReactNode)=>(
    <div key={index} className="ddCard" style={{...goldPanel,padding:"16px 20px",animationDelay:`${index*.06}s`,height:"100%",boxSizing:"border-box"}}>{children}</div>
  );
  switch(comp.type){
    case "kpi":               return null;
    case "dashboard_summary": return <div key={index}><SummaryPanel comp={comp} activeFilter={activeFilter} toggleFilter={toggleFilter}/></div>;
    case "record_cards":      return <div key={index} className="ddCard" style={{...goldPanel,padding:"18px 20px",animationDelay:`${index*.06}s`}}><RecordCards comp={comp} activeFilter={activeFilter}/></div>;
    case "bar_chart":         return wrap(<DynBar comp={comp} activeFilter={activeFilter} toggleFilter={toggleFilter}/>);
    case "time_series_chart": return wrap(<DynTs comp={comp} activeFilter={activeFilter}/>);
    case "table":             return wrap(<DynTable comp={comp} activeFilter={activeFilter} toggleFilter={toggleFilter}/>);
    case "text":              return (comp as TxtC).value === "No records returned." ? null : wrap(<TxtBlock value={(comp as TxtC).value}/>);
    case "donut_chart":       return wrap(<DynDonut comp={comp} activeFilter={activeFilter} toggleFilter={toggleFilter}/>);
    case "grouped_bar_chart": return wrap(<DynGroupedBar comp={comp} activeFilter={activeFilter} toggleFilter={toggleFilter}/>);
    case "area_chart":        return wrap(<DynArea comp={comp} activeFilter={activeFilter}/>);
    case "gauge_chart":       return wrap(<DynGauge comp={comp}/>);
    case "scatter_chart":     return wrap(<DynScatter comp={comp} activeFilter={activeFilter} toggleFilter={toggleFilter}/>);
    default:                  return null;
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function DynamicDashboard({components,explanation}:DDProps) {
  const [activeFilter, setActiveFilter] = useState<{key: string; value: string} | null>(null);
  const toggleFilter = (key: string, value: string) => {
    setActiveFilter(curr => {
      if (curr && curr.key === key && curr.value === value) {
        return null;
      }
      return { key, value };
    });
  };

  useEffect(()=>{injectAnimations();},[]);
  if (!components||components.length===0) return null;
  const kpis=components.filter((c):c is KpiC=>c.type==="kpi");
  const rest=components.filter(c=>c.type!=="kpi" && !(c.type==="text" && !(c as TxtC).value.trim()));
  const groups=layoutGroups(rest);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:14,fontFamily:"var(--font-sans,'Inter',sans-serif)",width:"100%"}}>
      {explanation&&(
        <div className="ddCard" style={{...goldPanel,padding:"12px 18px",borderLeft:`3px solid ${G.goldBorder}`}}>
          <p style={{margin:0,fontSize:13,lineHeight:1.7,color:"rgba(255,255,255,.72)"}}>{explanation}</p>
        </div>
      )}
      
      {activeFilter && (
        <div className="ddCard" style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          background: G.goldBg,
          border: `1px solid ${G.goldBorder}`,
          padding: "8px 16px",
          borderRadius: 10,
          alignSelf: "flex-start",
          animation: "ddFadeUp .3s ease",
          boxShadow: `0 4px 12px rgba(0,0,0,0.2)`,
          flexWrap: "wrap",
          maxWidth: "100%",
          wordBreak: "break-word"
        }}>
          <span style={{ fontSize: 12, color: G.textPrimary }}>
            Active Filter: <strong style={{ color: G.goldBright }}>{humanKey(activeFilter.key)} = {activeFilter.value}</strong>
          </span>
          <button 
            onClick={() => setActiveFilter(null)}
            className="ddBtn"
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: G.textPrimary,
              borderRadius: 6,
              fontSize: 10,
              fontWeight: 700,
              padding: "2px 8px",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Clear Filter
          </button>
        </div>
      )}

      {/* BUG 9.1 FIX — show message when filter returns no results */}
      {activeFilter && (
        (() => {
          const anyData = components.some(c => {
            if ("data" in c && Array.isArray((c as any).data)) {
              return ((c as any).data as Record<string,unknown>[]).some(
                r => String(r[(activeFilter as {key:string;value:string}).key]) === activeFilter.value
              );
            }
            return false;
          });
          if (anyData) return null;
          return (
            <div style={{
              padding: "14px 20px",
              borderRadius: 10,
              background: "rgba(244,63,94,0.08)",
              border: "1px solid rgba(244,63,94,0.25)",
              color: "#f43f5e",
              fontSize: 13,
              fontWeight: 600
            }}>
              No records match this filter. Click Clear Filter to reset.
            </div>
          );
        })()
      )}

      {kpis.length>0&&<KpiGrid items={kpis} activeFilter={activeFilter} allComponents={components}/>}
      
      {groups.map((group,gi)=>(
        group.comps.length===1
          // Single component — full width
          ? <React.Fragment key={gi}>{renderComp(group.comps[0],gi,activeFilter,toggleFilter)}</React.Fragment>
          // Paired components — side by side, using full horizontal space
          : <div key={gi} className="ddGrid" style={{display:"grid",gridTemplateColumns:group.cols,gap:12,alignItems:"stretch"}}>
              {group.comps.map((comp,ci)=>(
                <React.Fragment key={ci}>{renderComp(comp,gi*10+ci,activeFilter,toggleFilter)}</React.Fragment>
              ))}
            </div>
      ))}
    </div>
  );
}
