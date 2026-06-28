"""Per-LOCK automation + true voter, via VotingEscrow.getLockDelegatee(tokenId).
A veNFT's voting power is cast by its DELEGATEE:
  - delegatee == owner            -> MANUAL (owner self-votes)
  - delegatee is a Hydrex conduit -> AUTOMATED on that exact strategy (api.hydrex.fi/conduits)
  - delegatee is some other addr  -> DELEGATED (to a personal wallet / manager)
This is per-lock and resolves ALL conduits (USDC, Bitcoin, Bluechips, ...), unlike the
per-owner isApprovedForAll read which only ever caught Lock Maxi. The conduit/other-delegate
addresses are themselves the voters, so we also classify THEIR 10-epoch vote consistency
(same buckets as build_venft_history) so the dashboard's 'Votes for' follows the real voter.
Output: venft_delegatee.json -> {
  "locks":  {tokenId: {voter, kind, conduit_id, conduit_name}},
  "voters": {addr: {style, dom_pool, top_pools, is_conduit, conduit_name}}  # conduits + delegates only
}."""
import json, subprocess, time
from collections import Counter
from Crypto.Hash import keccak
from eth_abi import encode, decode
ESC="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"; V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"
MC3="0xca11bde05977b3631167028862be2a173976ca11"
RPCS=["https://mainnet.base.org","https://base.drpc.org","https://base-rpc.publicnode.com"]; _r=[0]
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
def rpc(m,p):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for t in range(10):
        u=RPCS[(_r[0]+t)%3]
        try:
            o=subprocess.run(["curl","-s","--max-time","50","-X","POST",u,"-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=60)
            d=json.loads(o.stdout)
            if d.get("result") is not None: _r[0]+=1; return d["result"]
        except Exception: pass
        time.sleep(0.35)
    return None
def get(u): return json.loads(subprocess.run(["curl","-s","--max-time","30",u],capture_output=True,text=True,timeout=40).stdout)
def pad(a): return bytes.fromhex(a[2:].lower().zfill(64))
def U(n): return int(n).to_bytes(32,"big")
S_DEL=sb("getLockDelegatee(uint256)"); S_LEN=sb("poolVoteLength(address)"); S_PV=sb("poolVote(address,uint256)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def mc(to, cds, block, batch=100):
    out=[]; i=0
    while i<len(cds):
        ch=cds[i:i+batch]
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(to,True,bytes(c)) for c in ch]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},block])
        if r is None or len(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0])!=len(ch):
            if batch>5: batch=max(5,batch//2); continue
            out.extend([(False,b"")]*len(ch)); i+=len(ch); continue
        out.extend(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0]); i+=len(ch)
    return out
def call1(to, payload, block):
    for _ in range(4):
        r=rpc("eth_call",[{"to":to,"data":"0x"+payload.hex()},block])
        if r is not None and r!="0x": return r
    return None

conduits=get("https://api.hydrex.fi/conduits")
CADDR={c["address"].lower():{"id":c["id"],"name":c["name"]} for c in conduits}
a2t={s["address"].lower():s.get("title") for s in get("https://api.hydrex.fi/strategies")}
top=json.load(open("top500_venfts.json"))
locks=[(int(x["tokenId"]), x["owner"].lower()) for x in top if int(x["tokenId"])!=1]
tids=[t for t,_ in locks]; owner_of=dict(locks)

# 1) per-lock delegatee (the true voter)
print(f"reading getLockDelegatee for {len(tids)} locks", flush=True)
res=mc(ESC,[S_DEL+U(t) for t in tids],"latest")
deleg={}
for t,(ok,b) in zip(tids,res): deleg[t]="0x"+b[-20:].hex() if (ok and b) else None
for t in [t for t in tids if deleg[t] is None]:
    r=call1(ESC,S_DEL+U(t),"latest")
    if r is not None and r!="0x": deleg[t]="0x"+r[-40:]
lock_out={}; kinds=Counter()
for t in tids:
    d=(deleg[t] or "").lower(); o=owner_of[t]
    if not d:                 kind,cid,cname="none",None,None
    elif d in CADDR:          kind,cid,cname="conduit",CADDR[d]["id"],CADDR[d]["name"]
    elif int(d,16)==0 or d==o:kind,cid,cname="manual",None,None
    else:                     kind,cid,cname="delegated",None,None
    kinds[kind]+=1
    lock_out[str(t)]={"voter":deleg[t],"kind":kind,"conduit_id":cid,"conduit_name":cname}
print("  per-lock kinds:", dict(kinds), flush=True)

# 2) classify the voters that are NOT owners (conduits + personal delegates) over 10 epochs
extra=sorted({(deleg[t] or "").lower() for t in tids
              if deleg[t] and int(deleg[t],16)!=0 and (deleg[t].lower() in CADDR or deleg[t].lower()!=owner_of[t])})
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39=1781136000; EPLEN=604800
CUR=39+(now-EP39)//EPLEN
while EP39+(CUR-39)*EPLEN+5*86400>now: CUR-=1
epochs=list(range(CUR-9,CUR+1)); blocks={K:hex(max(1,latest-(now-(EP39+(K-39)*EPLEN+5*86400))//2)) for K in epochs}
blocks["cur"]=hex(latest)
print(f"classifying {len(extra)} non-owner voters (conduits + delegates) over epochs {epochs[0]}..{epochs[-1]}+cur", flush=True)
ep_pools={w:{} for w in extra}
for K,BLK in blocks.items():
    lens=[int.from_bytes(b,"big") if (ok and b) else None for ok,b in mc(V,[S_LEN+pad(w) for w in extra],BLK)]
    for idx,w in enumerate(extra):
        if lens[idx] is None:
            r=call1(V,S_LEN+pad(w),BLK)
            if r is not None: lens[idx]=int(r,16)
    pv=[]; pvi=[]
    for w,n in zip(extra,lens):
        if n:
            for i in range(min(n,6)): pv.append(S_PV+pad(w)+U(i)); pvi.append(w)
    pools=["0x"+b[-20:].hex() if (ok and b) else None for ok,b in mc(V,pv,BLK)]
    by={}
    for w,p in zip(pvi,pools):
        if p: by.setdefault(w,[]).append(a2t.get(p.lower(),p[:10]))
    for w,n in zip(extra,lens):
        if n: ep_pools[w][K]={"n":n,"pools":by.get(w,[])}
def classify(d):
    voted=list(d.values())
    if not voted: return {"style":"No active vote","dom_pool":None,"top_pools":[]}
    avg=sum(v["n"] for v in voted)/len(voted); cnt=Counter(p for v in voted for p in v["pools"])
    distinct=len(cnt); dom,domc=cnt.most_common(1)[0] if cnt else (None,0); dom_share=domc/len(voted)
    if avg<=1.5 and dom_share>=0.8 and distinct<=2: style="Same pool"
    elif avg<=3.5 and dom_share>=0.5 and distinct<=5: style="1-3 pools"
    else: style="Fee-max"
    return {"style":style,"dom_pool":dom,"top_pools":[p for p,_ in cnt.most_common(3)]}
voters={}
for w in extra:
    c=classify(ep_pools[w]); c["is_conduit"]=w in CADDR; c["conduit_name"]=CADDR[w]["name"] if w in CADDR else None
    voters[w]=c
json.dump({"locks":lock_out,"voters":voters}, open("venft_delegatee.json","w"))
print("  voter styles:", dict(Counter(v["style"] for v in voters.values())), flush=True)
print("DONE delegatee", flush=True)
