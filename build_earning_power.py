"""Total earning power per epoch from the Hydrex API (the frontend's headline number).
Uses power.effectiveEarningPower so the tile + chart match the Hydrex frontend exactly
(this is NOT on-chain voting power — earning power is boosted/decayed differently and is
~0.37-0.50x of totalSupply, not a fixed multiple). Output: earning_power_history.json."""
import json, subprocess
def fetch(ids):
    o=subprocess.run(["curl","-s","--max-time","70",f"https://api.hydrex.fi/epochs?ids={ids}"],
                     capture_output=True,text=True,timeout=80)
    return json.loads(o.stdout)
ids=",".join(str(i) for i in range(1,80))   # API returns only the epochs that exist
d=[e for e in fetch(ids) if e.get("power",{}).get("effectiveEarningPower") is not None]
d.sort(key=lambda e:e["epochId"])
out={"epochs":[e["epochId"] for e in d],
     "earning_power_m":[round(e["power"]["effectiveEarningPower"]/1e6,2) for e in d],
     "latest_epoch":d[-1]["epochId"],
     "latest_earning_power":d[-1]["power"]["effectiveEarningPower"]}
json.dump(out,open("earning_power_history.json","w"))
print(f"wrote earning_power_history.json: {len(d)} epochs, latest ep{out['latest_epoch']} = {out['latest_earning_power']/1e6:.2f}M")
