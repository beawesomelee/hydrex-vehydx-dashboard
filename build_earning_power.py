"""Total earning power per epoch from the Hydrex API (the frontend's headline number).
Uses power.effectiveEarningPower so the tile + chart match the Hydrex frontend exactly
(this is NOT on-chain voting power — earning power is boosted/decayed differently and is
~0.37-0.50x of totalSupply, not a fixed multiple). Output: earning_power_history.json."""
import json, subprocess, sys
def fetch(ids):
    for _ in range(3):   # retry transient API blips
        try:
            o=subprocess.run(["curl","-s","--max-time","70",f"https://api.hydrex.fi/epochs?ids={ids}"],
                             capture_output=True,text=True,timeout=80)
            r=json.loads(o.stdout)
            if isinstance(r,list) and r: return r
        except Exception: pass
    return []
ids=",".join(str(i) for i in range(1,80))   # API returns only the epochs that exist
d=[e for e in fetch(ids) if isinstance(e,dict) and e.get("power",{}).get("effectiveEarningPower") is not None]
d.sort(key=lambda e:e["epochId"])
if not d:   # never overwrite a good file with an empty/failed fetch
    print("ERROR: no epochs from API — leaving earning_power_history.json untouched"); sys.exit(1)
out={"epochs":[e["epochId"] for e in d],
     "earning_power_m":[round(e["power"]["effectiveEarningPower"]/1e6,2) for e in d],
     "latest_epoch":d[-1]["epochId"],
     "latest_earning_power":d[-1]["power"]["effectiveEarningPower"]}
json.dump(out,open("earning_power_history.json","w"))
print(f"wrote earning_power_history.json: {len(d)} epochs, latest ep{out['latest_epoch']} = {out['latest_earning_power']/1e6:.2f}M")
