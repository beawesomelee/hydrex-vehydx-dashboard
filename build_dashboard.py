import json, re
from collections import Counter
R=json.load(open("vehydx_top100_labeled.json"))
TOTAL=454586648.0; HOLDERS=3780; TREASURY_PCT=61.65
team=sum(r["vehydx"] for r in R if r["entity_type"]=="hydrex_treasury_or_team")
managed=sum(r["vehydx"] for r in R if r["entity_type"]=="managed_lock")
hydrex_ctrl = TREASURY_PCT + team/TOTAL*100          # verified Hydrex only (treasury + signer team)
managed_pct = managed/TOTAL*100                       # Hydrex-managed locks, owner unverified
top100sum=sum(r["vehydx"] for r in R)
by_type={}
for r in R: by_type[r["entity_type"]]=by_type.get(r["entity_type"],0)+r["vehydx"]
style_ct=Counter(r["voting_style"] for r in R)
for r in R:
    r["cur"]=", ".join(f"{x} {pc}%" for x,pc in r.get("cur_targets",[])) or "—"

ROWS=json.dumps(R)
TYPE=json.dumps([[k,round(v/1e6,2)] for k,v in sorted(by_type.items(),key=lambda x:-x[1])])
# stacked-area: top-12 holders' holdings over epochs + "Other (top 100)"
EPN=sorted({int(e) for r in R for e in r.get("holdings",{})})
def hser(r): return [round(r.get("holdings",{}).get(str(e),0)/1e6,3) for e in EPN]
hsorted=sorted(R,key=lambda r:r["vehydx"],reverse=True)
TOPN=12; top=hsorted[:TOPN]; rest=hsorted[TOPN:]
area=[{"label":f"#{r['rank']} {r['likely_who']}"[:30],"data":hser(r)} for r in top]
if rest: area.append({"label":"Other (top 100)","data":[round(sum(r.get('holdings',{}).get(str(e),0) for r in rest)/1e6,3) for e in EPN]})
AREA=json.dumps({"epochs":[f"ep{e}" for e in EPN],"series":area})
DATA=json.dumps({"total":TOTAL,"holders":HOLDERS,"treasury_pct":TREASURY_PCT,"managed_pct":round(managed_pct,1),
                 "hydrex_ctrl":round(hydrex_ctrl,1),"top100_pct":round(top100sum/TOTAL*100,1),
                 "styles":dict(style_ct),"has_holdings":bool(EPN)})

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hydrex veHYDX Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--orange:#d29922;--purple:#bc8cff;--pink:#ff7b72;--cyan:#39d4cf;}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
h1{margin:0 0 4px;font-size:22px}.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
.cl{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.cv{font-size:22px;font-weight:600}.cs{color:var(--muted);font-size:11px;margin-top:3px}
.row2{display:grid;grid-template-columns:1.25fr 1fr;gap:16px;margin-bottom:20px}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px}
.panel h3{margin:0 0 4px;font-size:14px}.panel .hint{color:var(--muted);font-size:11px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);vertical-align:middle}
th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.5px;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--panel);z-index:1}
th:hover{color:var(--text)}td.n{text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:rgba(255,255,255,.02)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.who{font-weight:600}.sub2{color:var(--muted);font-size:11px}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
.b-high{background:rgba(63,185,80,.16);color:var(--green)}.b-medium{background:rgba(210,153,34,.16);color:var(--orange)}.b-low{background:rgba(139,148,158,.16);color:var(--muted)}
.vs{display:inline-block;padding:2px 9px;border-radius:6px;font-size:11px;font-weight:700}
.vs-Anchored{background:rgba(63,185,80,.18);color:var(--green)}
.vs-Focused{background:rgba(57,212,207,.16);color:var(--cyan)}
.vs-FeeFocus{background:rgba(210,153,34,.16);color:var(--orange)}
.vs-Idle{background:rgba(139,148,158,.14);color:var(--muted)}
.vs-Occasional{background:rgba(139,148,158,.14);color:var(--muted)}
.et{font-size:9.5px;padding:1px 6px;border-radius:4px;margin-left:6px;white-space:nowrap}
.et-hydrex_treasury_or_team{background:rgba(188,140,255,.15);color:var(--purple)}
.et-managed_lock{background:rgba(188,140,255,.09);color:#b89bd6}
.et-partner_project{background:rgba(63,185,80,.15);color:var(--green)}
.et-individual_whale{background:rgba(88,166,255,.12);color:var(--accent)}
.et-unknown{background:rgba(139,148,158,.12);color:var(--muted)}.et-alm_vault{background:rgba(255,123,114,.15);color:var(--pink)}
input{background:#0d1117;border:1px solid var(--border);color:var(--text);padding:8px 11px;border-radius:7px;font-size:13px;width:240px}
.chip{display:inline-block;padding:5px 11px;margin:0 6px 0 0;border:1px solid var(--border);border-radius:20px;font-size:12px;cursor:pointer;color:var(--muted);user-select:none}
.chip.on{background:var(--accent);color:#0d1117;border-color:var(--accent);font-weight:700}
.tablewrap{max-height:620px;overflow:auto;border:1px solid var(--border);border-radius:10px}
.foot{color:var(--muted);font-size:11px;margin-top:18px;line-height:1.7}
.pill{display:inline-block;background:#0d1117;border:1px solid var(--border);border-radius:8px;padding:7px 10px;margin:0 7px 7px 0;font-size:12px}
.pill b{color:var(--text)}.pill .m{color:var(--muted)}
@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}.row2{grid-template-columns:1fr}}
</style></head><body>
<h1>Hydrex veHYDX &mdash; Holder Intelligence \U0001F3DB</h1>
<div class="sub">Who controls Hydrex emissions, how they vote across epochs, and who they likely are. Snapshot 2026-06-25 (epoch 40) &middot; on-chain veHYDX VotingEscrow + Voter, Base &middot; top 100 of 3,780 holders.</div>
<div class="cards" id="cards"></div>
<div class="panel">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:4px">
    <h3 style="margin:0">Protocol Holders</h3>
    <input id="q" placeholder="filter holder / pool / address…" oninput="render()"/>
  </div>
  <div class="hint" id="styleline"></div>
  <div style="margin:6px 0 12px" id="chips"></div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th onclick="sort('rank')">#</th>
    <th onclick="sort('likely_who')">Likely holder</th>
    <th class="n" onclick="sort('vehydx')">veHYDX</th>
    <th class="n" onclick="sort('pct')">%</th>
    <th class="n" onclick="sort('delta_last')">&Delta; epoch</th>
    <th class="n" onclick="sort('epochs_voted')">Epochs voted</th>
    <th onclick="sort('voting_style')">Voting style &middot; pool</th>
    <th onclick="sort('confidence')">Conf</th>
    <th>Addr</th>
  </tr></thead><tbody id="tb"></tbody></table></div>
  <div class="sub2" style="margin-top:10px">* Leaderboard starts at #2. The #1 holder &mdash; the <b>Hydrex Treasury Safe</b> (<a href="https://basescan.org/address/0xd9e966a6bfa2ae2113a34bb4dd02ded921da50af" target="_blank">0xd9e9&hellip;50af</a>), <b>280.3M veHYDX = 61.65%</b> &mdash; is held out of the leaderboard: it votes a void/sink gauge (SpecialGaugeToken1/2), so it does not compete for partner emissions. &Delta; epoch = change in veHYDX vs the previous epoch.</div>
</div>
<div class="panel" id="areaPanel" style="margin-bottom:20px"><h3>veHYDX holdings over epochs</h3><div class="hint">top 12 holders + everyone else (top 100), last 10 epochs &mdash; who is accumulating vs unwinding</div><div style="position:relative;height:300px"><canvas id="area"></canvas></div></div>
<div class="row2">
  <div class="panel"><h3>veHYDX by holder type</h3><div class="hint">top 100; #1 treasury Safe (61.65%) shown separately</div><canvas id="chart" height="155"></canvas></div>
  <div class="panel"><h3>Anchored / aligned backers</h3><div class="hint">vote the same pool ~every epoch &mdash; the ones to court</div><div id="backers"></div></div>
</div>
<div class="foot">
<b>Voting style</b> (last 10 epochs): <span class="vs vs-Anchored">Anchored</span> same pool &ge;80% of voted epochs &middot; <span class="vs vs-Focused">Focused</span> one main pool or &le;3 pools &middot; <span class="vs vs-FeeFocus">Fee Focus</span> spreads across 4+ pools, no allegiance (chasing fees+bribes) &middot; <span class="vs vs-Idle">Idle</span> hasn&rsquo;t voted. The pool shown is their dominant target; %=share of voted epochs on it.<br>
<b>Confidence:</b> <span class="badge b-high">high</span> signer-matched Safe / verified contract / exclusive vote &middot; <span class="badge b-medium">medium</span> codehash-cluster (template, admin not re-verified) &middot; <span class="badge b-low">low</span> owner unresolved. 49/100 owners unresolved; &ldquo;Hydrex team/treasury&rdquo; via codehash is medium. Internal BD intel, do not distribute.
</div>
<script>
const ROWS=__ROWS__, TYPE=__TYPE__, D=__DATA__, AREA=__AREA__;
const VE=n=>(n>=1e6?(n/1e6).toFixed(2)+'M':(n/1e3).toFixed(0)+'K');
const sc=a=>a.slice(0,6)+'…'+a.slice(-4);
const dlt=v=>(v==null?'<span style="color:var(--muted)">—</span>':v>0?'<span style="color:var(--green)">+'+Math.round(v).toLocaleString()+'</span>':v<0?'<span style="color:var(--red)">'+Math.round(v).toLocaleString()+'</span>':'<span style="color:var(--muted)">0</span>');
const tn={hydrex_treasury_or_team:'Hydrex team/treasury',managed_lock:'Hydrex managed-lock (unverified)',partner_project:'Partner projects',individual_whale:'Individual whales',alm_vault:'ALM vault',unknown:'Unknown'};
const tnShort={hydrex_treasury_or_team:'team',managed_lock:'mgd-lock?',partner_project:'partner',individual_whale:'individual',alm_vault:'vault',unknown:'unknown'};
const vsClass=s=>'vs-'+s.replace(' ','');
document.getElementById('cards').innerHTML=[
 ['Total voting power',VE(D.total),D.holders.toLocaleString()+' holders'],
 ['Hydrex (verified)',D.hydrex_ctrl+'%','treasury + signer team · +'+D.managed_pct+'% managed-locks'],
 ['#1 Treasury Safe',D.treasury_pct+'%','votes a void sink gauge'],
 ['Contestable',(100-D.hydrex_ctrl-D.managed_pct).toFixed(1)+'%','non-Hydrex holders'],
 ['Anchored / Focused',(D.styles.Anchored||0)+(D.styles.Focused||0)+' of 100','aligned voters (vs '+(D.styles['Fee Focus']||0)+' mercenary)'],
].map(c=>`<div class="card"><div class="cl">${c[0]}</div><div class="cv">${c[1]}</div><div class="cs">${c[2]}</div></div>`).join('');
new Chart(document.getElementById('chart'),{type:'doughnut',data:{labels:TYPE.map(t=>tn[t[0]]||t[0]),
 datasets:[{data:TYPE.map(t=>t[1]),backgroundColor:['#bc8cff','#3fb950','#58a6ff','#ff7b72','#8b949e','#d29922'],borderColor:'#161b22',borderWidth:2}]},
 options:{plugins:{legend:{position:'right',labels:{color:'#8b949e',font:{size:11},boxWidth:12}},tooltip:{callbacks:{label:c=>c.label+': '+c.parsed+'M veHYDX'}}}}});
if(D.has_holdings){
 const pal=['#bc8cff','#ff7b72','#58a6ff','#3fb950','#d29922','#39d4cf','#ff7b9d','#a5d6ff','#f85149','#ffa657','#7ce38b','#d2a8ff'];
 new Chart(document.getElementById('area'),{type:'line',data:{labels:AREA.epochs,
   datasets:AREA.series.map((s,i)=>{const c=i>=12?'#484f58':pal[i%pal.length];return {label:s.label,data:s.data,borderColor:c,backgroundColor:c+'66',fill:true,tension:0.25,pointRadius:0,borderWidth:1};})},
   options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
     plugins:{legend:{position:'right',labels:{color:'#8b949e',font:{size:10},boxWidth:10}},tooltip:{callbacks:{label:c=>c.dataset.label+': '+c.parsed.y+'M veHYDX'}}},
     scales:{x:{stacked:true,ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#30363d'}},y:{stacked:true,ticks:{color:'#8b949e',font:{size:10},callback:v=>v+'M'},grid:{color:'#30363d'}}}}});
}else{document.getElementById('areaPanel').style.display='none';}
const bk=ROWS.filter(r=>r.voting_style==='Anchored'&&r.entity_type!=='hydrex_treasury_or_team').sort((a,b)=>b.vehydx-a.vehydx).slice(0,12);
document.getElementById('backers').innerHTML=bk.map(r=>`<div class="pill"><b>${r.likely_who}</b> <span class="m">${VE(r.vehydx)}</span> &mdash; ${r.dom_pool} ${r.epochs_voted}/${r.epochs_total}ep</div>`).join('')||'—';
document.getElementById('styleline').innerHTML=`likely identity, how they vote across 10 epochs, and confidence &middot; <b style="color:var(--green)">${D.styles.Anchored||0} Anchored</b> &middot; <b style="color:var(--cyan)">${D.styles.Focused||0} Focused</b> &middot; <b style="color:var(--orange)">${D.styles['Fee Focus']||0} Fee Focus</b> &middot; <b style="color:var(--muted)">${D.styles.Idle||0} Idle</b>`;
let styleFilter='All';
const chips=['All','Anchored','Focused','Fee Focus','Occasional','Idle'];
function renderChips(){document.getElementById('chips').innerHTML=chips.map(c=>`<span class="chip ${c===styleFilter?'on':''}" onclick="setStyle('${c}')">${c}</span>`).join('');}
function setStyle(s){styleFilter=s;renderChips();render();}
let sk='rank',sd=1;
function sort(k){sd=sk===k?-sd:1;sk=k;render();}
function render(){
 const q=document.getElementById('q').value.toLowerCase();
 let rows=ROWS.filter(r=>(styleFilter==='All'||r.voting_style===styleFilter) && (!q||(r.likely_who+' '+(r.dom_pool||'')+' '+r.cur+' '+r.wallet).toLowerCase().includes(q)));
 rows.sort((a,b)=>{let x=a[sk],y=b[sk];return (typeof x==='number'?x-y:(''+x).localeCompare(''+y))*sd;});
 document.getElementById('tb').innerHTML=rows.map(r=>`<tr>
  <td class="n" style="color:var(--muted)">${r.rank}</td>
  <td><span class="who">${r.likely_who}</span><span class="et et-${r.entity_type}">${tnShort[r.entity_type]||r.entity_type}</span></td>
  <td class="n">${VE(r.vehydx)}</td><td class="n">${r.pct}%</td>
  <td class="n">${dlt(r.delta_last)}</td>
  <td class="n">${r.epochs_voted}/${r.epochs_total}</td>
  <td><span class="vs ${vsClass(r.voting_style)}">${r.voting_style}</span>${r.dom_pool?` <span class="tvpool">${r.dom_pool}</span><div class="sub2">top in ${Math.round(r.dom_share*r.epochs_voted)}/${r.epochs_voted}ep · spreads ${r.avg_pools_per_epoch} pools/ep</div>`:''}</td>
  <td><span class="badge b-${r.confidence}">${r.confidence}</span></td>
  <td><a href="https://basescan.org/address/${r.wallet}" target="_blank" title="${r.wallet}">${sc(r.wallet)} ↗</a></td>
 </tr>`).join('');
}
renderChips();render();
</script></body></html>"""
html=html.replace("__ROWS__",ROWS).replace("__TYPE__",TYPE).replace("__DATA__",DATA).replace("__AREA__",AREA)
open("vehydx_dashboard_plain.html","w").write(html)
print(f"wrote vehydx_dashboard_plain.html ({len(html)} bytes) | styles: {dict(style_ct)}")
