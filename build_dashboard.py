import json, re, datetime as _dt
from collections import Counter
EP39_START=1781136000; EPLEN=604800   # epoch 39 start = 2026-06-11 00:00 UTC; 1 epoch = 1 week
def _eplab(K): return _dt.datetime.utcfromtimestamp(EP39_START+(K-38)*EPLEN).strftime("%b %-d")  # epoch END date (matches frontend axis)
R=json.load(open("vehydx_top100_labeled.json"))
# Headline constants are DERIVED from the data so they auto-update on each weekly refresh
# (previously hardcoded, which silently went stale). owner_power.json is the same snapshot the
# leaderboard rows come from, so TOTAL/TREASURY_PCT stay self-consistent with the table.
_op=json.load(open("owner_power.json"))["owner_power"]
TOTAL=sum(float(v) for v in _op.values())/1e18
_TREAS="0xd9e966a6bfa2ae2113a34bb4dd02ded921da50af"
_tp=float(_op.get(_TREAS) or _op.get(_TREAS.upper()) or 0)/1e18
TREASURY_PCT=_tp/TOTAL*100
try: HOLDERS=json.load(open("staker_history.json"))["stakers"][-1]   # = the stakers-chart endpoint, so tile==chart
except Exception: HOLDERS=len(_op)
# Earning power (Hydrex API, = frontend's headline). Treasury votes a sink gauge so it earns
# nothing; everyone else's lock is boosted ~1.30x. Per-wallet earning power is dominated by
# voting-power x base boost (the AnchorClub/options/Flex pieces that vary per lock are <1% of
# total), so scale each non-treasury wallet's voting power by earning_total / non-treasury-voting.
try:
    _EPH=json.load(open("earning_power_history.json"))
    EARN_TOTAL=_EPH["latest_earning_power"]; HAS_EARN=bool(_EPH.get("epochs"))
    EARN_SERIES={"epochs":[_eplab(e) for e in _EPH["epochs"]],"power":_EPH["earning_power_m"]}
except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
    EARN_TOTAL=TOTAL; HAS_EARN=False; EARN_SERIES={"epochs":[],"power":[]}
NONTREAS_VOTE=TOTAL*(1-TREASURY_PCT/100)
EARN_FACTOR=EARN_TOTAL/NONTREAS_VOTE if NONTREAS_VOTE else 1.0
for r in R:
    r["earn"]=round(r["vehydx"]*EARN_FACTOR)
    r["earn_pct"]=round(r["earn"]/EARN_TOTAL*100,3) if EARN_TOTAL else 0
    r["earn_delta"]=round(r["delta_last"]*EARN_FACTOR) if r.get("delta_last") is not None else None
# Per-veNFT table rows (top 500 individual locks; treasury genesis lock #1 excluded like before).
try:
    _TOPV=json.load(open("top500_venfts.json"))
    try: _CONS={k.lower():v for k,v in json.load(open("venft_consistency.json")).items()}
    except FileNotFoundError: _CONS={}
    try: _DEL=json.load(open("venft_delegatee.json"))
    except FileNotFoundError: _DEL={"locks":{},"voters":{}}
    _DLOCK=_DEL.get("locks",{}); _DVOTER={k.lower():v for k,v in _DEL.get("voters",{}).items()}
    CONSIST_BAR=0.6   # a pool voted in >=60% of an account's epochs counts as "consistently backed"
    _vr=[]
    for x in _TOPV:
        if int(x["tokenId"])==1: continue   # treasury genesis lock — excluded
        o=x["owner"].lower(); cn=_CONS.get(o,{}); earn=round(x["power"]/1e18*EARN_FACTOR)
        dl=_DLOCK.get(str(x["tokenId"]),{}); kind=dl.get("kind","manual"); voter=(dl.get("voter") or o).lower()
        lve=None; backs=[]
        if kind=="conduit":                      # an automation strategy picks the vote
            style="Automated"; bucket="Automated"; autlabel=dl.get("conduit_name")
        elif kind=="delegated":                  # voted by a personal wallet; pool detail is manual-only
            vc=_DVOTER.get(voter,{}); style=vc.get("style","—"); bucket=style; autlabel="Delegated"
        else:                                     # MANUAL — classify by the pools it CONSISTENTLY backs
            autlabel="Manual"; sstyle=cn.get("style","—"); lve=cn.get("last_voted_ep")
            if sstyle in ("No active vote","Did not vote","—"):
                style=sstyle; bucket=sstyle
            else:
                share=cn.get("pool_share") or {}
                backs=[p for p,sh in sorted(share.items(),key=lambda kv:-kv[1]) if sh>=CONSIST_BAR][:6]
                if not backs:        style="Fee-max"; bucket="Fee-max"        # no pool voted consistently => switcher
                elif len(backs)==1:  style="Same pool"; bucket="Same pool"    # always backs one pool
                elif len(backs)<=3:  style="1-3 pools"; bucket="1-3 pools"    # always backs a small set
                else:                style="Fee-max"; bucket="Fee-max"        # spreads, but always-includes shown
        _vr.append({"account":x["tokenId"],"owner":x["owner"],"earn":earn,
            "earn_pct":round(earn/EARN_TOTAL*100,3) if EARN_TOTAL else 0,
            "style":style,"bucket":bucket,"backs":backs,"last_voted_ep":lve,
            "kind":kind,"automated":kind=="conduit","strategy":autlabel})
    for i,r in enumerate(_vr,1): r["rank"]=i
    HAS_VENFT=bool(_vr)
except FileNotFoundError:
    _vr=[]; HAS_VENFT=False
VROWS=json.dumps(_vr)
N_VAUTO=sum(1 for r in _vr if r["automated"]); N_VMANUAL=sum(1 for r in _vr if r["kind"]=="manual"); N_VOWNERS=len({r["owner"].lower() for r in _vr})
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

# PUBLIC PROJECTION: the page is public, so ship ONLY the fields the UI renders. Never embed the
# internal attribution dossier (likely_who, safe_owners, confidence, entity_type, codehash,
# treasury_signer_match, behavior_10ep, cur_targets, ...) — those stay in R for build-time aggregates only.
_PUB=["rank","wallet","vehydx","earn","earn_pct","earn_delta","dom_pool","voting_style","vote_mode","automated","last_vote","cur","cur_targets","holdings"]
ROWS=json.dumps([{k:r.get(k) for k in _PUB} for r in R])
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
                 "styles":dict(style_ct),"modes":dict(mode_ct),"has_holdings":bool(EPN),"has_staker":HAS_STAKER,"has_earn":HAS_EARN,
                 "n_vauto":N_VAUTO,"n_vmanual":N_VMANUAL,"n_vowners":N_VOWNERS,"has_venft":HAS_VENFT})

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hydrex veHYDX Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--orange:#d29922;--purple:#bc8cff;--pink:#ff7b72;--cyan:#39d4cf;}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
h1{margin:0 0 24px;font-size:22px}.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
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
.md{display:inline-block;padding:2px 9px;border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap}
.md-Automated{background:rgba(188,140,255,.18);color:var(--purple)}
.md-Manual{background:rgba(57,212,207,.16);color:var(--cyan)}
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
    <h3 style="margin:0">Top Accounts (by lock)</h3>
    <input id="q" placeholder="filter account / owner / pool…" oninput="render()"/>
  </div>
  <div class="hint" id="styleline"></div>
  <div style="margin:6px 0 12px" id="chips"></div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th onclick="sort('rank')">#</th>
    <th onclick="sort('account')">Account #</th>
    <th>Owner</th>
    <th class="n" onclick="sort('earn')">Earning power</th>
    <th class="n" onclick="sort('earn_pct')">%</th>
    <th>Votes for</th>
    <th onclick="sort('automated')">Automation</th>
  </tr></thead><tbody id="tb"></tbody></table></div>
  <div class="sub2" style="margin-top:10px">* Each row is one veHYDX lock (veNFT); <b>Account #</b> = its token ID, ranked by the lock's own power. The treasury genesis lock (<b>Account #1</b>, <a href="https://basescan.org/address/0xd9e966a6bfa2ae2113a34bb4dd02ded921da50af" target="_blank">0xd9e9&hellip;50af</a>) is excluded &mdash; it parks its vote in a sink and earns nothing. Votes &amp; automation are resolved per-lock via its delegatee.</div>
</div>
<div class="panel" id="areaPanel" style="margin-bottom:20px"><h3>veHYDX holdings over epochs</h3><div class="hint">each line = one holder's veHYDX balance (not votes) &middot; top 12 + everyone else (top 100), last 10 epochs &mdash; who is accumulating vs unwinding</div><div style="position:relative;height:300px"><canvas id="area"></canvas></div></div>
<div class="row2" id="trends">
  <div class="panel"><h3>Stakers over time</h3><div class="hint">veHYDX holders per epoch since launch (current cohort) &mdash; protocol growth</div><div style="position:relative;height:250px"><canvas id="stakerChart"></canvas></div></div>
  <div class="panel"><h3>Total earning power over time</h3><div class="hint">effective earning power per epoch since launch (Hydrex API) &mdash; matches frontend</div><div style="position:relative;height:250px"><canvas id="totalChart"></canvas></div></div>
</div>
<div class="panel" style="margin-bottom:20px"><h3>Single Pool Voters</h3><div class="hint">wallets that commit all their veHYDX to one pool, and which pool</div><div id="backers"></div></div>
<div class="foot">
<b>Account #</b> = the veNFT token ID (Hydrex's account id); ranked by the lock's own power. Each lock is voted by its <b>delegatee</b> (<code>getLockDelegatee</code>): the owner itself (<i>manual</i>), a Hydrex automation <span class="md md-Automated">conduit</span>, or a personal <i>delegated</i> wallet. <b>Automation</b> = the exact conduit/strategy the lock is enrolled in (e.g. <span class="md md-Automated">USDC</span>, <span class="md md-Automated">Bitcoin</span>, <span class="md md-Automated">Hydrex Lock Maxi</span>; the conduit name = the output asset the yield is paid in). <b>Votes for</b> identifies a <b>manual</b> lock by the pool(s) it <i>consistently backs</i> — every pool it votes in &ge;60% of its last-10-epoch ballots: <b>1 pool</b> = same-pool backer, <b>2&ndash;3 pools</b> = a small set, and an account with no pool that consistent (a true switcher) reads <span class="brd">fee-max</span> (with its always-included pools shown beneath if it has any). <i>Automated</i> locks read <i>automation</i> (the conduit chooses — see the Automation column); <i>delegated</i> locks are voted by a personal wallet. <i>no active vote</i> / <i>did not vote</i> = no current gauge vote, verified against <code>lastVoted</code>.<br>
Top 500 of ~846 active locks; locks &ge;30K veHYDX are complete, the bottom ~50 (19&ndash;30K) may omit a few peers. The charts below are protocol-level / per-wallet. Internal BD reference.
</div>
<script>
const ROWS=__ROWS__, VROWS=__VROWS__, D=__DATA__, AREA=__AREA__, STAKER=__STAKER__, EARN=__EARN__;
const VE=n=>(n>=1e6?(n/1e6).toFixed(2)+'M':(n/1e3).toFixed(0)+'K');
const sc=a=>a.slice(0,6)+'…'+a.slice(-4);
const dlt=v=>(v==null?'<span style="color:var(--muted)">—</span>':v>0?'<span style="color:var(--green)">+'+Math.round(v).toLocaleString()+'</span>':v<0?'<span style="color:var(--red)">'+Math.round(v).toLocaleString()+'</span>':'<span style="color:var(--muted)">0</span>');
const tn={hydrex_treasury_or_team:'Hydrex team/treasury',managed_lock:'Hydrex managed-lock (unverified)',partner_project:'Partner projects',individual_whale:'Individual whales',alm_vault:'ALM vault',unknown:'Unknown'};
const tnShort={hydrex_treasury_or_team:'team',managed_lock:'mgd-lock?',partner_project:'partner',individual_whale:'individual',alm_vault:'vault',unknown:'unknown'};
const vsClass=s=>'vs-'+s.replace(' ','');
const mdClass=m=>'md-'+(m||'').replace(/[ -]/g,'');
const howMode=r=>r.automated?'Automated':(r.vote_mode==='Never voted'?'Never voted':'Manual');
// breadth (what they vote for) display from voting_style
document.getElementById('cards').innerHTML=[
 ['Total Earning Power',D.has_earn?VE(D.earning_total):'—',''],
 ['Accounts',D.holders.toLocaleString(),''],
 ['Current Epoch','Epoch '+D.epoch,D.epoch_range],
].map(c=>`<div class="card"><div class="cl">${c[0]}</div><div class="cv">${c[1]}</div><div class="cs">${c[2]}</div></div>`).join('');
if(D.has_staker){new Chart(document.getElementById('stakerChart'),{type:'line',data:{labels:STAKER.epochs,
   datasets:[{label:'Stakers',data:STAKER.stakers,borderColor:'#58a6ff',backgroundColor:'#58a6ff22',fill:true,tension:0.3,pointRadius:0,borderWidth:2}]},
   options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.parsed.y.toLocaleString()+' stakers'}}},
     scales:{x:{ticks:{color:'#8b949e',font:{size:10},maxTicksLimit:6,autoSkip:true},grid:{color:'#30363d'}},y:{beginAtZero:true,ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#30363d'}}}}});}
if(D.has_earn){new Chart(document.getElementById('totalChart'),{type:'line',data:{labels:EARN.epochs,
   datasets:[{label:'Earning power',data:EARN.power,borderColor:'#5cc8f5',backgroundColor:'#5cc8f51f',fill:true,tension:0.3,pointRadius:0,borderWidth:2}]},
   options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.parsed.y+'M earning power'}}},
     scales:{x:{ticks:{color:'#8b949e',font:{size:10},maxTicksLimit:6,autoSkip:true},grid:{color:'#30363d'}},y:{ticks:{color:'#8b949e',font:{size:10},callback:v=>v+'M'},grid:{color:'#30363d'}}}}});}
if(!D.has_staker&&!D.has_earn){document.getElementById('trends').style.display='none';}
if(D.has_holdings){
 const pal=['#bc8cff','#ff7b72','#58a6ff','#3fb950','#d29922','#39d4cf','#ff7b9d','#a5d6ff','#f85149','#ffa657','#7ce38b','#d2a8ff'];
 new Chart(document.getElementById('area'),{type:'line',data:{labels:AREA.epochs,
   datasets:AREA.series.map((s,i)=>{const c=i>=12?'#484f58':pal[i%pal.length];return {label:s.label,data:s.data,borderColor:c,backgroundColor:c+'66',fill:true,tension:0.25,pointRadius:0,borderWidth:1};})},
   options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
     plugins:{legend:{position:'right',labels:{color:'#8b949e',font:{size:10},boxWidth:10}},tooltip:{callbacks:{label:c=>c.dataset.label+': '+c.parsed.y+'M veHYDX'}}},
     scales:{x:{stacked:true,ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#30363d'}},y:{stacked:true,ticks:{color:'#8b949e',font:{size:10},callback:v=>v+'M'},grid:{color:'#30363d'}}}}});
}else{document.getElementById('areaPanel').style.display='none';}
const bk=ROWS.filter(r=>r.voting_style==='Anchored').sort((a,b)=>b.vehydx-a.vehydx).slice(0,12);
document.getElementById('backers').innerHTML=bk.map(r=>`<div class="pill"><b>${r.dom_pool}</b> <span class="m">${VE(r.earn)} · <a href="https://basescan.org/address/${r.wallet}" target="_blank">${sc(r.wallet)}</a></span></div>`).join('')||'—';
document.getElementById('styleline').innerHTML=`top <b>${VROWS.length}</b> locks (treasury #1 excluded) &middot; <b style="color:var(--purple)">${D.n_vauto} automated</b> (strategy picks the vote) &middot; <b>${D.n_vmanual} manual</b> &middot; of the human-voted: <b style="color:var(--green)">${VROWS.filter(r=>r.bucket==='Same pool').length} same pool</b> &middot; <b style="color:var(--cyan)">${VROWS.filter(r=>r.bucket==='1-3 pools').length} 1-3 pools</b> &middot; <b style="color:var(--orange)">${VROWS.filter(r=>r.bucket==='Fee-max').length} fee-max</b>`;
let modeFilter='All';
const chips=[['All','All'],['Automated','Automated'],['Manual','Manual'],['Same pool','Same pool'],['1-3 pools','1-3 pools'],['Fee-max','Fee-max']];
function chipCount(v){return v==='All'?VROWS.length:v==='Automated'?VROWS.filter(r=>r.automated).length:v==='Manual'?VROWS.filter(r=>r.kind==='manual').length:VROWS.filter(r=>r.bucket===v).length;}
function renderChips(){document.getElementById('chips').innerHTML=chips.map(([lbl,val])=>`<span class="chip ${val===modeFilter?'on':''}" onclick="setMode('${val}')">${lbl} <span style="opacity:.55">${chipCount(val)}</span></span>`).join('');}
function setMode(v){modeFilter=v;renderChips();render();}
let sk='rank',sd=1;
function sort(k){sd=sk===k?-sd:1;sk=k;render();}
function render(){
 const q=document.getElementById('q').value.toLowerCase();
 let rows=VROWS.filter(r=>( modeFilter==='All' ? true : modeFilter==='Automated' ? r.automated : modeFilter==='Manual' ? r.kind==='manual' : r.bucket===modeFilter )
   && (!q||(('#'+r.account)+' '+r.owner+' '+(r.backs||[]).join(' ')+' '+(r.style||'')+' '+(r.strategy||'')).toLowerCase().includes(q)));
 rows.sort((a,b)=>{let x=a[sk],y=b[sk];return (typeof x==='number'?x-y:(''+x).localeCompare(''+y))*sd;});
 document.getElementById('tb').innerHTML=rows.map(r=>{
  // consistency across the last 10 epochs: same pool / 1-3 pools / fee-max (switches)
  const b=r.backs||[];
  // conduit -> the automation picks; delegated -> a personal wallet picks (pool detail is manual-only);
  // manual -> the pools it CONSISTENTLY backs are its identity; only a true switcher reads "fee-max".
  const votesFor = r.kind==='conduit' ? `<span style="color:var(--muted)">automation</span>`
    : r.kind==='delegated' ? `<span style="color:var(--muted)">${(r.style||'—').toLowerCase()}</span>`
    : r.style==='Same pool' ? `<span class="brd">${b[0]||''}</span>`
    : r.style==='1-3 pools' ? `<span class="brd">${b[0]||''}</span>${b.length>1?`<div class="sub2">${b.slice(1).join(', ')}</div>`:''}`
    : r.style==='Fee-max' ? `<span class="brd">fee-max</span>${b.length?`<div class="sub2">always ${b.join(', ')}</div>`:''}`
    : r.style==='No active vote' ? `<span class="brd" style="color:var(--muted)">no active vote</span>${r.last_voted_ep?`<div class="sub2">last voted ep ${r.last_voted_ep}</div>`:''}`
    : `<span class="brd" style="color:var(--muted)">did not vote</span>`;
  const aut = r.kind==='conduit' ? `<span class="md md-Automated">${r.strategy}</span>`
    : `<span style="color:var(--muted)">${(r.strategy||'Manual').toLowerCase()}</span>`;
  return `<tr>
  <td class="n" style="color:var(--muted)">${r.rank}</td>
  <td style="font-weight:700;color:var(--cyan)">#${r.account}</td>
  <td><a href="https://basescan.org/address/${r.owner}" target="_blank" title="${r.owner}">${sc(r.owner)}</a></td>
  <td class="n">${VE(r.earn)}</td><td class="n">${r.earn_pct}%</td>
  <td>${votesFor}</td>
  <td>${aut}</td>
 </tr>`;}).join('');
}
renderChips();render();
</script></body></html>"""
html=html.replace("__ROWS__",ROWS).replace("__VROWS__",VROWS).replace("__DATA__",DATA).replace("__AREA__",AREA).replace("__STAKER__",STAKER).replace("__EARN__",EARN).replace("__EPOCH__",str(CUR_EPOCH)).replace("__EPRANGE__",EPOCH_RANGE)
open("vehydx_dashboard_plain.html","w").write(html)
print(f"wrote vehydx_dashboard_plain.html ({len(html)} bytes) | styles: {dict(style_ct)}")
