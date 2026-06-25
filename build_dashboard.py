import json, re
from collections import Counter
R=json.load(open("vehydx_top100_labeled.json"))
TOTAL=454586648.0; HOLDERS=3780; TREASURY_PCT=61.65
team=sum(r["vehydx"] for r in R if r["entity_type"]=="hydrex_treasury_or_team")
hydrex_ctrl = TREASURY_PCT + team/TOTAL*100
top100sum=sum(r["vehydx"] for r in R)
by_type={}
for r in R: by_type[r["entity_type"]]=by_type.get(r["entity_type"],0)+r["vehydx"]

# derive a clean "typically votes" string from the 10-epoch behavior
def typ_votes(r):
    b=r["behavior_10ep"]
    if b.startswith("idle"): return ("—","idle (no votes, 10 ep)")
    m=re.match(r"(.+?) (\d+)/(\d+)ep",b)
    if m:
        pool,c,a=m.group(1),int(m.group(2)),int(m.group(3))
        tag = "exclusive" if c==a==10 else ("consistent" if c/a>=0.7 else "rotates")
        return (pool, f"{c}/{a} epochs · {tag}")
    return ("—",b)
for r in R:
    p,d=typ_votes(r); r["tv_pool"]=p; r["tv_detail"]=d
    r["cur"]=", ".join(f"{x} {pc}%" for x,pc in r.get("cur_targets",[])) or "—"

ROWS=json.dumps(R)
TYPE=json.dumps([[k,round(v/1e6,2)] for k,v in sorted(by_type.items(),key=lambda x:-x[1])])
DATA=json.dumps({"total":TOTAL,"holders":HOLDERS,"treasury_pct":TREASURY_PCT,
                 "hydrex_ctrl":round(hydrex_ctrl,1),"top100_pct":round(top100sum/TOTAL*100,1)})

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hydrex veHYDX Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--orange:#d29922;--purple:#bc8cff;--pink:#ff7b72;}
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
.et{font-size:9.5px;padding:1px 6px;border-radius:4px;margin-left:6px;white-space:nowrap}
.et-hydrex_treasury_or_team{background:rgba(188,140,255,.15);color:var(--purple)}
.et-partner_project{background:rgba(63,185,80,.15);color:var(--green)}
.et-individual_whale{background:rgba(88,166,255,.12);color:var(--accent)}
.et-unknown{background:rgba(139,148,158,.12);color:var(--muted)}.et-alm_vault{background:rgba(255,123,114,.15);color:var(--pink)}
.tvpool{font-weight:600}
input{background:#0d1117;border:1px solid var(--border);color:var(--text);padding:8px 11px;border-radius:7px;font-size:13px;width:260px}
.tablewrap{max-height:620px;overflow:auto;border:1px solid var(--border);border-radius:10px}
.foot{color:var(--muted);font-size:11px;margin-top:18px;line-height:1.7}
.pill{display:inline-block;background:#0d1117;border:1px solid var(--border);border-radius:8px;padding:7px 10px;margin:0 7px 7px 0;font-size:12px}
.pill b{color:var(--text)}.pill .m{color:var(--muted)}
@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}.row2{grid-template-columns:1fr}}
</style></head><body>
<h1>Hydrex veHYDX &mdash; Holder Intelligence \U0001F3DB</h1>
<div class="sub">Who controls Hydrex emissions direction, what they vote for, and who they likely are. Snapshot 2026-06-25 (epoch 40) &middot; on-chain veHYDX VotingEscrow + Voter, Base &middot; top 100 of 3,780 holders.</div>
<div class="cards" id="cards"></div>
<div class="row2">
  <div class="panel"><h3>veHYDX by holder type</h3><div class="hint">top 100; #1 treasury Safe (61.65%) shown separately</div><canvas id="chart" height="155"></canvas></div>
  <div class="panel"><h3>Sticky partner backers</h3><div class="hint">vote one pool ~every epoch (8&ndash;10 of 10)</div><div id="backers"></div></div>
</div>
<div class="panel" style="margin-bottom:20px"><h3>Idle whales &mdash; recruit targets</h3><div class="hint">large holders that have NOT voted in 10 epochs (excl. Hydrex team)</div><div id="idle"></div></div>
<div class="panel">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
    <h3 style="margin:0">Protocol Holders</h3>
    <input id="q" placeholder="filter holder / pool / address…" oninput="render()"/>
  </div>
  <div class="hint">likely identity, what they typically vote with, and confidence &middot; click a column to sort</div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th onclick="sort('rank')">#</th>
    <th onclick="sort('likely_who')">Likely holder</th>
    <th class="n" onclick="sort('vehydx')">veHYDX</th>
    <th class="n" onclick="sort('pct')">%</th>
    <th onclick="sort('tv_pool')">Typically votes</th>
    <th onclick="sort('confidence')">Confidence</th>
    <th>Addr</th>
  </tr></thead><tbody id="tb"></tbody></table></div>
</div>
<div class="foot">
<b>Typically votes</b> = the wallet&rsquo;s dominant pool across the last 10 epochs (&ldquo;exclusive&rdquo; = same pool 10/10; &ldquo;consistent&rdquo; = &ge;70%; &ldquo;rotates&rdquo; = spreads around).<br>
<b>Confidence:</b> <span class="badge b-high">high</span> signer-matched Safe / verified contract / exclusive consistent vote &nbsp; <span class="badge b-medium">medium</span> codehash-cluster match (template, admin not re-verified) or single source &nbsp; <span class="badge b-low">low</span> owner unresolved.<br>
<b>Caveats:</b> 49/100 owners unresolved (need BaseScan/Arkham). &ldquo;Hydrex team/treasury&rdquo; via codehash is medium-confidence. Vote-weight absolute units have a decay quirk &mdash; rely on the relative % split. &mdash; Internal BD intel, do not distribute.
</div>
<script>
const ROWS=__ROWS__, TYPE=__TYPE__, D=__DATA__;
const VE=n=>(n>=1e6?(n/1e6).toFixed(2)+'M':(n/1e3).toFixed(0)+'K');
const sc=a=>a.slice(0,6)+'…'+a.slice(-4);
const tn={hydrex_treasury_or_team:'Hydrex team/treasury',partner_project:'Partner projects',individual_whale:'Individual whales',alm_vault:'ALM vault',unknown:'Unknown'};
const tnShort={hydrex_treasury_or_team:'team',partner_project:'partner',individual_whale:'individual',alm_vault:'vault',unknown:'unknown'};
document.getElementById('cards').innerHTML=[
 ['Total voting power',VE(D.total),D.holders.toLocaleString()+' holders'],
 ['Hydrex-controlled',D.hydrex_ctrl+'%','treasury + team wallets'],
 ['#1 Treasury Safe',D.treasury_pct+'%','votes a void sink gauge'],
 ['Contestable',(100-D.hydrex_ctrl).toFixed(1)+'%','everyone else'],
 ['Top 100 =',D.top100_pct+'%','of all veHYDX'],
].map(c=>`<div class="card"><div class="cl">${c[0]}</div><div class="cv">${c[1]}</div><div class="cs">${c[2]}</div></div>`).join('');
new Chart(document.getElementById('chart'),{type:'doughnut',data:{labels:TYPE.map(t=>tn[t[0]]||t[0]),
 datasets:[{data:TYPE.map(t=>t[1]),backgroundColor:['#bc8cff','#3fb950','#58a6ff','#ff7b72','#8b949e','#d29922'],borderColor:'#161b22',borderWidth:2}]},
 options:{plugins:{legend:{position:'right',labels:{color:'#8b949e',font:{size:11},boxWidth:12}},tooltip:{callbacks:{label:c=>c.label+': '+c.parsed+'M veHYDX'}}}}});
const bk=ROWS.filter(r=>/\\d+\\/(\\d+)ep/.test(r.behavior_10ep)&&!/idle \\(/.test(r.behavior_10ep)).filter(r=>{const m=/(\\d+)\\/(\\d+)ep/.exec(r.behavior_10ep);return +m[2]>=8&&(+m[1]/+m[2])>=0.8;}).slice(0,12);
document.getElementById('backers').innerHTML=bk.map(r=>`<div class="pill"><b>${r.likely_who}</b> <span class="m">${VE(r.vehydx)}</span> &mdash; ${r.tv_pool} ${r.behavior_10ep.match(/\\d+\\/\\d+ep/)[0]}</div>`).join('')||'—';
const idle=ROWS.filter(r=>/idle \\(never|idle \\(no/.test(r.behavior_10ep)&&r.entity_type!=='hydrex_treasury_or_team').slice(0,10);
document.getElementById('idle').innerHTML=idle.map(r=>`<div class="pill"><b>#${r.rank}</b> <span class="m">${VE(r.vehydx)} veHYDX</span> &mdash; ${r.likely_who}</div>`).join('')||'—';
let sk='rank',sd=1;
function sort(k){sd=sk===k?-sd:1;sk=k;render();}
function render(){
 const q=document.getElementById('q').value.toLowerCase();
 let rows=ROWS.filter(r=>!q||(r.likely_who+' '+r.tv_pool+' '+r.behavior_10ep+' '+r.cur+' '+r.wallet).toLowerCase().includes(q));
 rows.sort((a,b)=>{let x=a[sk],y=b[sk];return (typeof x==='number'?x-y:(''+x).localeCompare(''+y))*sd;});
 document.getElementById('tb').innerHTML=rows.map(r=>`<tr>
  <td class="n" style="color:var(--muted)">${r.rank}</td>
  <td><span class="who">${r.likely_who}</span><span class="et et-${r.entity_type}">${tnShort[r.entity_type]||r.entity_type}</span></td>
  <td class="n">${VE(r.vehydx)}</td><td class="n">${r.pct}%</td>
  <td><span class="tvpool">${r.tv_pool}</span><div class="sub2">${r.tv_detail}</div></td>
  <td><span class="badge b-${r.confidence}">${r.confidence}</span></td>
  <td><a href="https://basescan.org/address/${r.wallet}" target="_blank" title="${r.wallet}">${sc(r.wallet)} ↗</a></td>
 </tr>`).join('');
}
render();
</script></body></html>"""
html=html.replace("__ROWS__",ROWS).replace("__TYPE__",TYPE).replace("__DATA__",DATA)
open("vehydx_dashboard_plain.html","w").write(html)
print(f"wrote vehydx_dashboard_plain.html ({len(html)} bytes)")
