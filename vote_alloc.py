import json, subprocess, sys
from Crypto.Hash import keccak
from eth_abi import encode, decode
RPCS=["https://mainnet.base.org","https://base.llamarpc.com","https://base-rpc.publicnode.com"]
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"
V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"  # Voter
def sb(sig):
    k=keccak.new(digest_bits=256); k.update(sig.encode()); return bytes.fromhex(k.hexdigest()[:8])
S_POOLS=sb("pools(uint256)"); S_VOTES=sb("votes(address,address)"); S_AGG3=sb("aggregate3((address,bool,bytes)[])")
def rpc(method,params,tries=3):
    p=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params})
    for _ in range(tries):
        for u in RPCS:
            try:
                o=subprocess.run(["curl","-s","--max-time","40","-X","POST",u,"-H","Content-Type: application/json","--data",p],capture_output=True,text=True,timeout=50)
                d=json.loads(o.stdout)
                if d.get("result") is not None: return d["result"]
            except Exception: pass
    return None
def mc(calls):
    tup=[(t,True,d) for t,d in calls]
    data="0x"+(S_AGG3+encode(["(address,bool,bytes)[]"],[tup])).hex()
    r=rpc("eth_call",[{"to":MC3,"data":data},"latest"])
    return decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0] if r else None
def pad(a): return bytes.fromhex("0"*24+a[2:])
U=lambda n: n.to_bytes(32,"big")

titles=json.load(open("pool_titles.json"))
N=int(sys.argv[1]) if len(sys.argv)>1 else 20
d=json.load(open("owner_power.json")); 
ranked=sorted(d["owner_power"].items(),key=lambda kv:kv[1],reverse=True)
tot=sum(d["owner_power"].values())
# pool list
npool=int(rpc("eth_call",[{"to":V,"data":"0x"+keccak.new(digest_bits=256,data=b'length()').hexdigest()[:8]},"latest"]),16)
pools=[]
for i in range(0,npool,150):
    res=mc([(V,S_POOLS+U(j)) for j in range(i,min(i+150,npool))])
    pools+=["0x"+r[-20:].hex() for ok,r in res if ok and len(r)>=32]
# arg order via #1 holder
h=ranked[0][0]
def alloc(holder,order="ap"):
    out={}
    for i in range(0,len(pools),150):
        chunk=pools[i:i+150]
        calls=[(V, S_VOTES+(pad(holder)+pad(p) if order=="ap" else pad(p)+pad(holder))) for p in chunk]
        res=mc(calls)
        for p,(ok,r) in zip(chunk,res):
            w=int.from_bytes(r,"big") if ok and len(r)>=32 else 0
            if w>0: out[p]=w
    return out
a_ap=alloc(h,"ap"); 
order = "ap" if sum(a_ap.values())>0 else "pa"
print(f"vote arg order = {order} (acct,pool) | #pools={len(pools)}\n")
def getcode(a): 
    c=rpc("eth_getCode",[a,"latest"]); return bool(c and c!="0x")
rows=[]
print(f"{'#':>2} {'wallet':<13}{'veHYDX':>13}{'%':>6} {'type':<8} top vote targets")
for i,(w,p) in enumerate(ranked[:N],1):
    al=alloc(w,order); s=sum(al.values()) or 1
    top=sorted(al.items(),key=lambda x:-x[1])[:3]
    tgt=", ".join(f"{titles.get(pl,'?')} {wt/s*100:.0f}%" for pl,wt in top) or "(not voting)"
    typ="contract" if getcode(w) else "EOA"
    rows.append((i,w,p/1e18,p/tot*100,typ,tgt))
    print(f"{i:>2} {w[:12]}…{p/1e18:>13,.0f}{p/tot*100:>5.1f}% {typ:<8} {tgt}")
import csv
with open("vehydx_top_holders_votes.csv","w",newline="") as f:
    wr=csv.writer(f); wr.writerow(["rank","wallet","vehydx","pct","type","top_vote_targets"])
    for r in rows: wr.writerow([r[0],r[1],f"{r[2]:.0f}",f"{r[3]:.2f}",r[4],r[5]])
print("\nwrote vehydx_top_holders_votes.csv")
