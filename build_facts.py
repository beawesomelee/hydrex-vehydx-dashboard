import json, subprocess, sys
from Crypto.Hash import keccak
from eth_abi import encode, decode
RPCS=["https://mainnet.base.org","https://base.drpc.org","https://base-rpc.publicnode.com"]
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"; V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"
TREAS=set(["0xea1bf482b7d3526ccf37a8a3fee330c960877f08","0x813f98f0f29509d558b2479d8ee0c8068c160bd3","0xb4d2861d525aef313be0c497c3335a58f637e73e"])
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
S_POOLS=sb("pools(uint256)");S_VOTES=sb("votes(address,address)");S_AGG=sb("aggregate3((address,bool,bytes)[])");S_OWN=sb("getOwners()")
def rpc(m,p,tries=3):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for _ in range(tries):
        for u in RPCS:
            try:
                o=subprocess.run(["curl","-s","--max-time","40","-X","POST",u,"-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=50)
                d=json.loads(o.stdout)
                if d.get("result") is not None: return d["result"]
            except Exception: pass
    return None
def mc(calls, block="latest"):
    tup=[(t,True,d) for t,d in calls]
    data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[tup])).hex()
    r=rpc("eth_call",[{"to":MC3,"data":data},block])
    return decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0] if r else None
def pad(a): return bytes.fromhex("0"*24+a[2:])
U=lambda n:n.to_bytes(32,"big")
def codehash(a):
    c=rpc("eth_getCode",[a,"latest"])
    if not c or c=="0x": return "EOA"
    k=keccak.new(digest_bits=256);k.update(bytes.fromhex(c[2:]));return "0x"+k.hexdigest()[:16]
def safe_owners(a):
    r=rpc("eth_call",[{"to":a,"data":"0x"+S_OWN.hex()},"latest"])
    if not r or r=="0x": return None
    b=bytes.fromhex(r[2:])
    try:
        n=int.from_bytes(b[32:64],"big"); return ["0x"+b[64+i*32+12:64+i*32+32].hex() for i in range(n)]
    except: return None

titles=json.load(open("pool_titles.json"))
d=json.load(open("owner_power.json"))
ranked=sorted(d["owner_power"].items(),key=lambda kv:kv[1],reverse=True)
tot=sum(d["owner_power"].values())
top=ranked[1:101]  # skip #1 treasury -> 100 wallets
# pool list
n=int(rpc("eth_call",[{"to":V,"data":"0x"+sb("length()").hex()},"latest"]),16)
pools=[]
for i in range(0,n,150):
    res=mc([(V,S_POOLS+U(j)) for j in range(i,min(i+150,n))])
    pools+=["0x"+r[-20:].hex() for ok,r in res if ok and len(r)>=32]
print(f"pools={len(pools)} wallets={len(top)}", flush=True)
facts=[]; relevant=set()
for idx,(w,p) in enumerate(top):
    ch=codehash(w); so=safe_owners(w)
    # current votes
    nz={}
    for i in range(0,len(pools),150):
        chunk=pools[i:i+150]
        res=mc([(V,S_VOTES+pad(w)+pad(pl)) for pl in chunk])
        if not res: continue
        for pl,(ok,r) in zip(chunk,res):
            wt=int.from_bytes(r,"big") if ok and len(r)>=32 else 0
            if wt>0: nz[pl]=wt
    relevant|=set(nz.keys())
    s=sum(nz.values()) or 1
    tops=sorted(nz.items(),key=lambda x:-x[1])[:3]
    is_treas_safe = bool(so) and len(set(o.lower() for o in so)&TREAS)>0
    facts.append({"rank":idx+2,"wallet":w,"vehydx":p/1e18,"pct":round(p/tot*100,3),
        "type":"EOA" if ch=="EOA" else "contract","codehash":ch,
        "safe":bool(so),"safe_owners":so,"treasury_signer_match":is_treas_safe,
        "cur_targets":[(titles.get(pl,pl), round(wt/s*100)) for pl,wt in tops]})
    if (idx+1)%20==0: print(f"  {idx+1}/100 facts", flush=True)
json.dump({"facts":facts,"relevant_pools":sorted(relevant)}, open("top100_facts.json","w"))
print(f"DONE facts. relevant pools={len(relevant)}", flush=True)
