"""Per-veNFT (per-account) dashboard: the top 500 individual veHYDX locks by power.
Each row = one veNFT (Account # = tokenId) -> owner wallet, lock power, what the owner
votes for, and whether the owner uses a Hydrex automation conduit.
Inputs: top500_venfts.json, venft_owner_behavior.json. Output: vehydx_venft_plain.html."""
import json, datetime as _dt
TOP=json.load(open("top500_venfts.json"))
BEH={k.lower():v for k,v in json.load(open("venft_owner_behavior.json")).items()}
EP39=1781136000; EPLEN=604800
try: CUR=json.load(open("earning_power_history.json"))["latest_epoch"]
except Exception: CUR=40
_s=EP39+(CUR-39)*EPLEN
EPR=_dt.datetime.utcfromtimestamp(_s).strftime("%b %-d")+" – "+_dt.datetime.utcfromtimestamp(_s+EPLEN).strftime("%b %-d, %Y")
rows=[]
for i,x in enumerate(TOP,1):
    o=x["owner"].lower(); b=BEH.get(o,{})
    rows.append({"rank":i,"account":x["tokenId"],"owner":x["owner"],
        "power":round(x["power"]/1e18),"cur":b.get("cur_targets") or [],
        "automated":bool(b.get("automated")),"strategy":b.get("strategy")})
n_auto=sum(1 for r in rows if r["automated"])
distinct=len({r["owner"].lower() for r in rows})
ROWS=json.dumps(rows)
DATA=json.dumps({"epoch":CUR,"epoch_range":EPR,"n":len(rows),"automated":n_auto,
    "distinct":distinct,"top_power":rows[0]["power"] if rows else 0})
html=r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hydrex veHYDX — Top Accounts</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--purple:#bc8cff;--cyan:#39d4cf;}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
h1{margin:0 0 24px;font-size:22px}
.cards{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;flex:0 1 300px}
.cl{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.cv{font-size:22px;font-weight:600}.cs{color:var(--muted);font-size:11px;margin-top:3px}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px}
.panel h3{margin:0 0 4px;font-size:14px}.hint{color:var(--muted);font-size:11px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);vertical-align:middle}
th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.5px;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--panel);z-index:1}
th:hover{color:var(--text)}.n{text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:rgba(255,255,255,.02)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.acct{font-weight:700;color:var(--cyan)}.sub2{color:var(--muted);font-size:11px}
.brd{font-weight:700;font-size:12px}
.md{display:inline-block;padding:2px 9px;border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap}
.md-Auto{background:rgba(188,140,255,.18);color:var(--purple)}
input{background:#0d1117;border:1px solid var(--border);color:var(--text);padding:8px 11px;border-radius:7px;font-size:13px;width:260px}
.tablewrap{max-height:680px;overflow:auto;border:1px solid var(--border);border-radius:10px}
.foot{color:var(--muted);font-size:11px;margin-top:16px;line-height:1.7}
@media(max-width:900px){.card{flex:1 1 100%}}
</style></head><body>
<h1>Hydrex veHYDX &mdash; Top Accounts (by lock)</h1>
<div class="cards" id="cards"></div>
<div class="panel">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px">
    <h3 style="margin:0">Top 500 veHYDX locks</h3>
    <input id="q" placeholder="filter account / owner / pool…" oninput="render()"/>
  </div>
  <div class="hint">each row = one veHYDX lock (veNFT). <b>Account #</b> = token ID &middot; ranked by the lock's own power. Voting &amp; automation are per-owner.</div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th class="n" onclick="sort('rank')">#</th>
    <th onclick="sort('account')">Account #</th>
    <th onclick="sort('owner')">Owner</th>
    <th class="n" onclick="sort('power')">veHYDX</th>
    <th>Votes for</th>
    <th onclick="sort('automated')">Automation</th>
  </tr></thead><tbody id="tb"></tbody></table></div>
</div>
<div class="foot">
<b>Account #</b> = the veNFT token ID (Hydrex's account id); <b>#1</b> is the protocol treasury &mdash; the genesis lock.
<b>Votes for</b> = the pool(s) the lock's <i>owner</i> currently votes (one owner casts one vote across all their locks).
<b>Automation</b> = the owner uses a Hydrex Account-Automation conduit (e.g. <span class="md md-Auto">Lock Maxi</span>, which auto-compounds the lock &mdash; it does not change the vote).
Top 500 of ~846 active locks; locks &ge;30K veHYDX are complete, the bottom ~50 (19&ndash;30K) may omit a few peers. Internal BD reference.
</div>
<script>
const ROWS=__ROWS__, D=__DATA__;
const VE=n=>(n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(0)+'K':n);
const sc=a=>a.slice(0,6)+'…'+a.slice(-4);
document.getElementById('cards').innerHTML=[
 ['Largest Lock','#'+ROWS[0].account,VE(D.top_power)+' veHYDX · treasury'],
 ['Accounts Shown',D.n.toLocaleString(),D.distinct+' distinct owners · '+D.automated+' automated'],
 ['Current Epoch','Epoch '+D.epoch,D.epoch_range],
].map(c=>`<div class="card"><div class="cl">${c[0]}</div><div class="cv">${c[1]}</div><div class="cs">${c[2]}</div></div>`).join('');
let sk='rank',sd=1;
function sort(k){sd=sk===k?-sd:1;sk=k;render();}
function render(){
 const q=document.getElementById('q').value.toLowerCase();
 let rows=ROWS.filter(r=>!q||(('#'+r.account)+' '+r.owner+' '+(r.cur.map(c=>c[0]).join(' '))+' '+(r.strategy||'')).toLowerCase().includes(q));
 rows.sort((a,b)=>{let x=a[sk],y=b[sk];return (typeof x==='number'?x-y:(''+x).localeCompare(''+y))*sd;});
 document.getElementById('tb').innerHTML=rows.map(r=>{
  const cur=r.cur||[];
  const votes = cur.length===0 ? `<span class="sub2">no active vote</span>`
    : `<span class="brd">${cur[0][0]}</span>${cur.length>1?`<div class="sub2">${cur.slice(1).map(c=>c[0]).join(', ')}</div>`:''}`;
  const aut = r.automated ? `<span class="md md-Auto">${r.strategy||'Automated'}</span>` : `<span style="color:var(--muted)">—</span>`;
  return `<tr>
   <td class="n" style="color:var(--muted)">${r.rank}</td>
   <td class="acct">#${r.account}</td>
   <td><a href="https://basescan.org/address/${r.owner}" target="_blank" title="${r.owner}">${sc(r.owner)}</a></td>
   <td class="n">${VE(r.power)}</td>
   <td>${votes}</td>
   <td>${aut}</td>
  </tr>`;}).join('');
}
render();
</script></body></html>"""
html=html.replace("__ROWS__",ROWS).replace("__DATA__",DATA)
open("vehydx_venft_plain.html","w").write(html)
print(f"wrote vehydx_venft_plain.html ({len(html)} bytes) | {len(rows)} locks, {n_auto} automated, {distinct} owners")
