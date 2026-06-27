"""Owner behavior (current votes + automation conduit) for the owners of the top-500 veNFTs.
Reuses already-computed top-100 wallet data; scans only the new owners on-chain.
Output: venft_owner_behavior.json -> {owner_lower: {cur_targets, automated, strategy}}."""
import json, subprocess, time
from Crypto.Hash import keccak
from eth_abi import encode, decode
ESC="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"
VOTER="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"; MC3="0xca11bde05977b3631167028862be2a173976ca11"
RPCS=["https://mainnet.base.org","https://base.drpc.org"]
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
_r=[0]
def rpc(m,p):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for t in range(8):
        u=RPCS[(_r[0]+t)%2]
        try:
            o=subprocess.run(["curl","-s","--max-time","45","-X","POST",u,"-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=55)
            r=json.loads(o.stdout).get("result")
            if r is not None: _r[0]+=1; return r
        except Exception: pass
        time.sleep(0.3)
    return None
def get(u): return subprocess.run(["curl","-s","--max-time","30",u],capture_output=True,text=True,timeout=40).stdout
def pad(a): return bytes.fromhex(a[2:].lower().zfill(64))
def U(n): return int(n).to_bytes(32,"big")
S_VOTES=sb("votes(address,address)"); S_IAFA=sb("isApprovedForAll(address,address)")
S_LEN=sb("length()"); S_POOLS=sb("pools(uint256)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def mc(target,cds,batch=150):
    out=[]
    def do(lo,hi,d=0):
        ch=cds[lo:hi]
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(target,True,bytes(c)) for c in ch]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},"latest"])
        if r is None:
            if hi-lo<=4 or d>9: out.extend([(False,b"")]*(hi-lo)); return
            m=(lo+hi)//2; do(lo,m,d+1); do(m,hi,d+1); return
        out.extend(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0])
    for i in range(0,len(cds),batch): do(i,min(i+batch,len(cds)))
    return out

owners=sorted({x["owner"].lower() for x in json.load(open("top500_venfts.json"))})
print(f"{len(owners)} distinct owners in top500", flush=True)
# reuse top-100 wallet data where available
have={r["wallet"].lower():r for r in json.load(open("vehydx_top100_labeled.json"))}
auto={k.lower():v for k,v in json.load(open("automation.json")).items()}
out={}
new=[]
for o in owners:
    if o in have:
        r=have[o]; a=auto.get(o,{})
        out[o]={"cur_targets":r.get("cur_targets") or [], "automated":bool(a.get("automated")), "strategy":a.get("strategy")}
    else: new.append(o)
print(f"reused {len(out)}; scanning {len(new)} new owners", flush=True)
# pools + titles
n=int(rpc("eth_call",[{"to":VOTER,"data":"0x"+S_LEN.hex()},"latest"]),16)
pools=[]
for ok,ret in mc(VOTER,[S_POOLS+U(i) for i in range(n)]):
    pools.append("0x"+ret[-20:].hex() if ok and ret else None)
strat=json.loads(get("https://api.hydrex.fi/strategies")); a2t={s["address"].lower():s.get("title") for s in strat}
conduits=[{"name":c["name"],"addr":c["address"].lower()} for c in json.loads(get("https://api.hydrex.fi/conduits"))]
# scan new owners: votes across all pools + automation conduits
for gi,o in enumerate(new):
    vc=mc(VOTER,[S_VOTES+pad(o)+pad(p) for p in pools if p])
    vt=[]
    for p,(ok,ret) in zip([p for p in pools if p],vc):
        w=int.from_bytes(ret,"big") if ok and ret else 0
        if w>0: vt.append((a2t.get(p.lower(),p[:8]),w))
    vt.sort(key=lambda x:-x[1]); tot=sum(w for _,w in vt) or 1
    cur=[[t,round(w/tot*100)] for t,w in vt[:3]]
    ac=mc(ESC,[S_IAFA+pad(o)+pad(c["addr"]) for c in conduits])
    strat_name=None; automated=False
    for c,(ok,ret) in zip(conduits,ac):
        if ok and ret and int.from_bytes(ret,"big"): automated=True; strat_name=c["name"]; break
    out[o]={"cur_targets":cur,"automated":automated,"strategy":strat_name}
    if gi%20==0: print(f"  scanned {gi}/{len(new)}", flush=True)
json.dump(out,open("venft_owner_behavior.json","w"))
print(f"DONE: behavior for {len(out)} owners", flush=True)
