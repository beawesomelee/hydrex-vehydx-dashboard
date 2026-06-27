import json, re, datetime as _dt
from collections import Counter
EP39_START=1781136000; EPLEN=604800   # epoch 39 start = 2026-06-11 00:00 UTC; 1 epoch = 1 week
def _eplab(K): return _dt.datetime.utcfromtimestamp(EP39_START+(K-38)*EPLEN).strftime("%b %-d")  # epoch END date (matches frontend axis)
R=json.load(open("vehydx_top100_labeled.json"))
TOTAL=454586648.0; HOLDERS=3780; TREASURY_PCT=61.65
# Earning power (Hydrex API, = frontend's headline). Treasury votes a sink gauge so it earns
# nothing; everyone else's lock is boosted ~1.30x. Per-wallet earning power is dominated by
# voting-power x base boost (the AnchorClub/options/Flex pieces that vary per lock are <1% of
# total), so scale each non-treasury wallet's voting power by earning_total / non-treasury-voting.
try:
    _EPH=json.load(open("earning_power_history.json"))
    EARN_TOTAL=_EPH["latest_earning_power"]; HAS_EARN=bool(_EPH.get("epochs"))
    EARN_SERIES={"epochs":[_eplab(e) for e in _EPH["epochs"]],"power":_EPH["earning_power_m"]}
except FileNotFoundError:
    EARN_TOTAL=TOTAL; HAS_EARN=False; EARN_SERIES={"epochs":[],"power":[]}
NONTREAS_VOTE=TOTAL*(1-TREASURY_PCT/100)
EARN_FACTOR=EARN_TOTAL/NONTREAS_VOTE if NONTREAS_VOTE else 1.0
for r in R:
    r["earn"]=round(r["vehydx"]*EARN_FACTOR)
    r["earn_pct"]=round(r["earn"]/EARN_TOTAL*100,3) if EARN_TOTAL else 0
    r["earn_delta"]=round(r["delta_last"]*EARN_FACTOR) if r.get("delta_last") is not None else None
team=sum(r["vehydx"] for r in R if r["entity_type"]=="hydrex_treasury_or_team")
managed=sum(r["vehydx"] for r in R if r["entity_type"]=="managed_lock")
hydrex_ctrl = TREASURY_PCT + team/TOTAL*100          # verified Hydrex only (treasury + signer team)
managed_pct = managed/TOTAL*100                       # Hydrex-managed locks, owner unverified
top100sum=sum(r["vehydx"] for r in R)
by_type={}
for r in R: by_type[r["entity_type"]]=by_type.get(r["entity_type"],0)+r["vehydx"]
style_ct=Counter(r["voting_style"] for r in R)
mode_ct=Counter(r.get("vote_mode","—") for r in R)
for r in R:
    r["cur"]=", ".join(f"{x} {pc}%" for x,pc in r.get("cur_targets",[])) or "—"

ROWS=json.dumps(R)
TYPE=json.dumps([[k,round(v/1e6,2)] for k,v in sorted(by_type.items(),key=lambda x:-x[1])])
# stacked-area: top-12 holders' holdings over epochs + "Other (top 100)"
EPN=sorted({int(e) for r in R for e in r.get("holdings",{})})
def hser(r): return [round(r.get("holdings",{}).get(str(e),0)/1e6,3) for e in EPN]
hsorted=sorted(R,key=lambda r:r["vehydx"],reverse=True)
TOPN=12; top=hsorted[:TOPN]; rest=hsorted[TOPN:]
area=[{"label":f"#{r['rank']} {r['wallet'][:6]}…{r['wallet'][-4:]}","data":hser(r)} for r in top]
if rest: area.append({"label":"Other (top 100)","data":[round(sum(r.get('holdings',{}).get(str(e),0) for r in rest)/1e6,3) for e in EPN]})
AREA=json.dumps({"epochs":[f"ep{e}" for e in EPN],"series":area})
# Staker count + total veHYDX over the protocol's full history (Dune-style growth)
try:
    SH=json.load(open("staker_history.json"))
    STAKER=json.dumps({"epochs":[_eplab(e) for e in SH["epochs"]],"stakers":SH["stakers"],"total":SH["total_vehydx_m"]})
    HAS_STAKER=bool(SH.get("epochs"))
except FileNotFoundError:
    STAKER=json.dumps({"epochs":[],"stakers":[],"total":[]}); HAS_STAKER=False
EARN=json.dumps(EARN_SERIES)   # total earning-power-over-time series for the chart
# Current epoch derived from the data (max epoch present) so it auto-updates each refresh.
CUR_EPOCH=max(EPN) if EPN else 40
_s=EP39_START+(CUR_EPOCH-39)*EPLEN
EPOCH_RANGE=_dt.datetime.utcfromtimestamp(_s).strftime("%b %-d")+" – "+_dt.datetime.utcfromtimestamp(_s+EPLEN).strftime("%b %-d, %Y")
DATA=json.dumps({"total":TOTAL,"holders":HOLDERS,"treasury_pct":TREASURY_PCT,"managed_pct":round(managed_pct,1),
                 "hydrex_ctrl":round(hydrex_ctrl,1),"top100_pct":round(top100sum/TOTAL*100,1),
                 "epoch":CUR_EPOCH,"epoch_range":EPOCH_RANGE,"earning_total":EARN_TOTAL,
                 "styles":dict(style_ct),"modes":dict(mode_ct),"has_holdings":bool(EPN),"has_staker":HAS_STAKER,"has_earn":HAS_EARN})

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hydrex veHYDX Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--orange:#d29922;--purple:#bc8cff;--pink:#ff7b72;--cyan:#39d4cf;}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
h1{margin:0 0 4px;font-size:22px}.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
.cards{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;flex:0 1 300px}
.cl{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.cv{font-size:22px;font-weight:600}.cs{color:var(--muted);font-size:11px;margin-top:3px}
.row2{display:grid;grid-template-columns:1.25fr 1fr;gap:16px;margin-bottom:20px}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px}
.panel h3{margin:0 0 4px;font-size:14px}.panel .hint{color:var(--muted);font-size:11px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);vertical-align:middle}
th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.5px;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--panel);z-index:1}
th:hover{color:var(--text)}.n{text-align:right;font-variant-numeric:tabular-nums}
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
.md{display:inline-block;padding:2px 9px;border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap}
.md-Automated{background:rgba(210,153,34,.18);color:var(--orange)}
.md-Active{background:rgba(57,212,207,.16);color:var(--cyan)}
.md-Setandforget{background:rgba(63,185,80,.16);color:var(--green)}
.md-Nevervoted{background:rgba(139,148,158,.14);color:var(--muted)}
.brd{font-weight:700;font-size:12px}
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
@media(max-width:900px){.card{flex:1 1 100%}.row2{grid-template-columns:1fr}}
</style></head><body>
<h1>Hydrex veHYDX &mdash; Holder Intelligence</h1>
<div class="cards" id="cards"></div>
<div class="panel">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:4px">
    <h3 style="margin:0">Voter Behavior</h3>
    <input id="q" placeholder="filter pool / mode / address…" oninput="render()"/>
  </div>
  <div class="hint" id="styleline"></div>
  <div style="margin:6px 0 12px" id="chips"></div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th onclick="sort('rank')">#</th>
    <th>Wallet</th>
    <th class="n" onclick="sort('earn')">Earning power</th>
    <th class="n" onclick="sort('earn_pct')">%</th>
    <th class="n" onclick="sort('earn_delta')">&Delta; epoch</th>
    <th onclick="sort('voting_style')">Votes for</th>
    <th onclick="sort('vote_mode')">How they vote</th>
  </tr></thead><tbody id="tb"></tbody></table></div>
  <div class="sub2" style="margin-top:10px">* Leaderboard starts at #2. The #1 holder, the <b>Hydrex Treasury Safe</b> (<a href="https://basescan.org/address/0xd9e966a6bfa2ae2113a34bb4dd02ded921da50af" target="_blank">0xd9e9&hellip;50af</a>), is excluded because it <b>does not vote on any active pool</b>, so it earns nothing. Earning power = veHYDX voting power boosted ~1.3&times; (matches the Hydrex frontend); &Delta; epoch = change vs the previous epoch.</div>
</div>
<div class="panel" id="areaPanel" style="margin-bottom:20px"><h3>veHYDX holdings over epochs</h3><div class="hint">each line = one holder's veHYDX balance (not votes) &middot; top 12 + everyone else (top 100), last 10 epochs &mdash; who is accumulating vs unwinding</div><div style="position:relative;height:300px"><canvas id="area"></canvas></div></div>
<div class="row2" id="trends">
  <div class="panel"><h3>Stakers over time</h3><div class="hint">veHYDX holders per epoch since launch (current cohort) &mdash; protocol growth</div><div style="position:relative;height:250px"><canvas id="stakerChart"></canvas></div></div>
  <div class="panel"><h3>Total earning power over time</h3><div class="hint">effective earning power per epoch since launch (Hydrex API) &mdash; matches frontend</div><div style="position:relative;height:250px"><canvas id="totalChart"></canvas></div></div>
</div>
<div class="panel" style="margin-bottom:20px"><h3>Single Pool Voters</h3><div class="hint">wallets that commit all their veHYDX to one pool, and which pool</div><div id="backers"></div></div>
<div class="foot">
<b>Votes for</b> (last 10 epochs): <span class="brd">one pool</span> = same single pool &ge;80% of epochs &middot; <span class="brd">1-3 pools</span> = one main pool or a small fixed set &middot; <span class="brd">fee-max</span> = spreads across 4+ pools, no allegiance.<br>
<b>How they vote</b> (from on-chain <code>lastVoted</code>): <span class="md md-Setandforget">Set-and-forget</span> voted once, the vote just persists &middot; <span class="md md-Active">Active</span> actively re-votes (changes its vote) &middot; <span class="md md-Nevervoted">Never</span> holds veHYDX but has not voted.<br>
<b>Pattern:</b> single-pool holders are predominantly set-and-forget (committed, passive); fee-maximizers are predominantly active re-voters (chasing the best bribe).
</div>
<script>
const ROWS=__ROWS__, D=__DATA__, AREA=__AREA__, STAKER=__STAKER__, EARN=__EARN__;
const VE=n=>(n>=1e6?(n/1e6).toFixed(2)+'M':(n/1e3).toFixed(0)+'K');
const sc=a=>a.slice(0,6)+'…'+a.slice(-4);
const dlt=v=>(v==null?'<span style="color:var(--muted)">—</span>':v>0?'<span style="color:var(--green)">+'+Math.round(v).toLocaleString()+'</span>':v<0?'<span style="color:var(--red)">'+Math.round(v).toLocaleString()+'</span>':'<span style="color:var(--muted)">0</span>');
const tn={hydrex_treasury_or_team:'Hydrex team/treasury',managed_lock:'Hydrex managed-lock (unverified)',partner_project:'Partner projects',individual_whale:'Individual whales',alm_vault:'ALM vault',unknown:'Unknown'};
const tnShort={hydrex_treasury_or_team:'team',managed_lock:'mgd-lock?',partner_project:'partner',individual_whale:'individual',alm_vault:'vault',unknown:'unknown'};
const vsClass=s=>'vs-'+s.replace(' ','');
const mdClass=m=>'md-'+(m||'').replace(/[ -]/g,'');
// breadth (what they vote for) display from voting_style
const brd={Anchored:'one pool',Focused:'1-3 pools','Fee Focus':'fee-max',Occasional:'occasional',Idle:'—'};
document.getElementById('cards').innerHTML=[
 ['Total Earning Power',VE(D.earning_total),'effective earning power (excl. non-voting treasury)'],
 ['Accounts',D.holders.toLocaleString(),'veHYDX holders'],
 ['Current Epoch','Epoch '+D.epoch,D.epoch_range],
].map(c=>`<div class="card"><div class="cl">${c[0]}</div><div class="cv">${c[1]}</div><div class="cs">${c[2]}</div></div>`).join('');
if(D.has_staker){
 new Chart(document.getElementById('stakerChart'),{type:'line',data:{labels:STAKER.epochs,
   datasets:[{label:'Stakers',data:STAKER.stakers,borderColor:'#58a6ff',backgroundColor:'#58a6ff22',fill:true,tension:0.3,pointRadius:0,borderWidth:2}]},
   options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.parsed.y.toLocaleString()+' stakers'}}},
     scales:{x:{ticks:{color:'#8b949e',font:{size:10},maxTicksLimit:6,autoSkip:true},grid:{color:'#30363d'}},y:{beginAtZero:true,ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#30363d'}}}}});
 if(D.has_earn){new Chart(document.getElementById('totalChart'),{type:'line',data:{labels:EARN.epochs,
   datasets:[{label:'Earning power',data:EARN.power,borderColor:'#5cc8f5',backgroundColor:'#5cc8f51f',fill:true,tension:0.3,pointRadius:0,borderWidth:2}]},
   options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.parsed.y+'M earning power'}}},
     scales:{x:{ticks:{color:'#8b949e',font:{size:10},maxTicksLimit:6,autoSkip:true},grid:{color:'#30363d'}},y:{ticks:{color:'#8b949e',font:{size:10},callback:v=>v+'M'},grid:{color:'#30363d'}}}}});}
}else{document.getElementById('trends').style.display='none';}
if(D.has_holdings){
 const pal=['#bc8cff','#ff7b72','#58a6ff','#3fb950','#d29922','#39d4cf','#ff7b9d','#a5d6ff','#f85149','#ffa657','#7ce38b','#d2a8ff'];
 new Chart(document.getElementById('area'),{type:'line',data:{labels:AREA.epochs,
   datasets:AREA.series.map((s,i)=>{const c=i>=12?'#484f58':pal[i%pal.length];return {label:s.label,data:s.data,borderColor:c,backgroundColor:c+'66',fill:true,tension:0.25,pointRadius:0,borderWidth:1};})},
   options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
     plugins:{legend:{position:'right',labels:{color:'#8b949e',font:{size:10},boxWidth:10}},tooltip:{callbacks:{label:c=>c.dataset.label+': '+c.parsed.y+'M veHYDX'}}},
     scales:{x:{stacked:true,ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#30363d'}},y:{stacked:true,ticks:{color:'#8b949e',font:{size:10},callback:v=>v+'M'},grid:{color:'#30363d'}}}}});
}else{document.getElementById('areaPanel').style.display='none';}
const bk=ROWS.filter(r=>r.voting_style==='Anchored').sort((a,b)=>b.vehydx-a.vehydx).slice(0,12);
document.getElementById('backers').innerHTML=bk.map(r=>`<div class="pill"><b>${r.dom_pool}</b> <span class="m">${VE(r.earn)} · ${r.vote_mode.toLowerCase()}</span></div>`).join('')||'—';
document.getElementById('styleline').innerHTML=`each wallet by <b>what they vote for</b> &times; <b>how they vote</b> &middot; <b style="color:var(--cyan)">${D.modes.Active||0} active</b> &middot; <b style="color:var(--green)">${D.modes['Set-and-forget']||0} set-and-forget</b> &middot; <b style="color:var(--muted)">${D.modes['Never voted']||0} never</b>`;
let modeFilter='All';
const chips=[['All','All'],['Active','Active'],['Set-and-forget','Set-and-forget'],['Never voted','Never voted']];
function renderChips(){document.getElementById('chips').innerHTML=chips.map(([lbl,val])=>`<span class="chip ${val===modeFilter?'on':''}" onclick="setMode('${val}')">${lbl}</span>`).join('');}
function setMode(v){modeFilter=v;renderChips();render();}
let sk='rank',sd=1;
function sort(k){sd=sk===k?-sd:1;sk=k;render();}
function render(){
 const q=document.getElementById('q').value.toLowerCase();
 let rows=ROWS.filter(r=>(modeFilter==='All'||r.vote_mode===modeFilter) && (!q||((r.dom_pool||'')+' '+r.vote_mode+' '+r.voting_style+' '+r.cur+' '+r.wallet).toLowerCase().includes(q)));
 rows.sort((a,b)=>{let x=a[sk],y=b[sk];return (typeof x==='number'?x-y:(''+x).localeCompare(''+y))*sd;});
 document.getElementById('tb').innerHTML=rows.map(r=>{
  const votesFor = !r.dom_pool ? `<span class="brd" style="color:var(--muted)">does not vote</span>`
    : r.voting_style==='Fee Focus' ? `<span class="brd">fee-max</span>`
    : `<span class="brd">${brd[r.voting_style]||'—'}</span><div class="sub2">${r.dom_pool}</div>`;
  const lvSub = r.vote_mode==='Set-and-forget'&&r.last_vote ? `<div class="sub2">since ${new Date(r.last_vote*1000).toISOString().slice(0,10)}</div>` : '';
  return `<tr>
  <td style="color:var(--muted)">${r.rank}</td>
  <td><a href="https://basescan.org/address/${r.wallet}" target="_blank" title="${r.wallet}">${sc(r.wallet)}</a></td>
  <td class="n">${VE(r.earn)}</td><td class="n">${r.earn_pct}%</td>
  <td class="n">${dlt(r.earn_delta)}</td>
  <td>${votesFor}</td>
  <td><span class="md ${mdClass(r.vote_mode)}">${r.vote_mode}</span>${lvSub}</td>
 </tr>`;}).join('');
}
renderChips();render();
</script></body></html>"""
html=html.replace("__ROWS__",ROWS).replace("__DATA__",DATA).replace("__AREA__",AREA).replace("__STAKER__",STAKER).replace("__EARN__",EARN).replace("__EPOCH__",str(CUR_EPOCH)).replace("__EPRANGE__",EPOCH_RANGE)
open("vehydx_dashboard_plain.html","w").write(html)
print(f"wrote vehydx_dashboard_plain.html ({len(html)} bytes) | styles: {dict(style_ct)}")
