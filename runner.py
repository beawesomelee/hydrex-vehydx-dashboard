import json, time, sys
from scan import multicall, rpc, VE
from ve import eth_call, d_uint

MAXID = 111595
BATCH = 300
ckpt_path = "owner_power.json"
log = open("scan_progress.log","w")
def L(m):
    log.write(m+"\n"); log.flush(); print(m, flush=True)

t_supply = d_uint(eth_call(VE,"totalSupply()")) or 0  # total voting power (wei)
L(f"total voting power (totalSupply): {t_supply/1e18:,.2f} veHYDX")

owner_power={}; owner_nfts={}; scanned=0; nonzero=0; failed_ranges=[]
t0=time.time()
tid=1
while tid<=MAXID:
    batch=list(range(tid, min(tid+BATCH, MAXID+1)))
    pr=multicall(batch)
    if pr is None:
        # retry smaller
        half=len(batch)//2 or 1
        ok=True
        for sub in (batch[:half], batch[half:]):
            if not sub: continue
            p2=multicall(sub)
            if p2 is None:
                failed_ranges.append((sub[0],sub[-1])); ok=False; continue
            for t,o,p in p2:
                if o:
                    owner_power[o]=owner_power.get(o,0)+p
                    if p>0: owner_nfts[o]=owner_nfts.get(o,0)+1
        if not ok: L(f"  WARN failed near {batch[0]}")
    else:
        for t,o,p in pr:
            if o:
                owner_power[o]=owner_power.get(o,0)+p
                if p>0:
                    owner_nfts[o]=owner_nfts.get(o,0)+1; nonzero+=1
    scanned+=len(batch); tid+=BATCH
    if (tid//BATCH)%25==0:
        rate=scanned/(time.time()-t0+1e-9)
        L(f"  scanned {scanned}/{MAXID}  owners={len(owner_power)}  nonzeroNFTs={nonzero}  {rate:.0f} tok/s")
        json.dump({"owner_power":owner_power,"owner_nfts":owner_nfts,"scanned":scanned}, open(ckpt_path,"w"))

json.dump({"owner_power":owner_power,"owner_nfts":owner_nfts,"scanned":scanned,
           "total_power_wei":str(t_supply),"failed":failed_ranges}, open(ckpt_path,"w"))

# rank
ranked=sorted(owner_power.items(), key=lambda kv: kv[1], reverse=True)
tot=sum(owner_power.values()) or 1
with open("vehydx_top_holders.csv","w") as f:
    f.write("rank,wallet,vehydx_power,pct_of_total,nfts_with_power\n")
    for i,(w,p) in enumerate(ranked[:100],1):
        f.write(f"{i},{w},{p/1e18:.4f},{p/tot*100:.4f},{owner_nfts.get(w,0)}\n")
L(f"\nDONE. unique owners={len(owner_power)}  summed_power={tot/1e18:,.2f}  (vs totalSupply {t_supply/1e18:,.2f})")
L("TOP 20:")
for i,(w,p) in enumerate(ranked[:20],1):
    L(f"{i:>2} {w} {p/1e18:>14,.2f}  {p/tot*100:>6.2f}%  nfts={owner_nfts.get(w,0)}")
if failed_ranges: L(f"failed ranges: {failed_ranges}")
