"""Per-owner voting CONSISTENCY across the last 10 epochs, for the top-500-lock owners.
Uses Voter.poolVoteLength(account) + poolVote(account,i) at each epoch block (archive) to
get the SET of pools each owner voted per epoch -> classify:
  'Same pool'  = ~1 pool, the same one >=80% of voted epochs
  '1-3 pools'  = a small stable set (<=3/epoch, few distinct)
  'Fee-max'    = switches pools across epochs / sprays many (mercenary)
Output: venft_consistency.json -> {owner: {style, dom_pool, avg_pools, epochs_voted}}."""
import json, subprocess, time
from collections import Counter
from Crypto.Hash import keccak
from eth_abi import encode, decode
V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"; MC3="0xca11bde05977b3631167028862be2a173976ca11"
RPCS=["https://mainnet.base.org","https://base.drpc.org"]
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
_r=[0]
def rpc(m,p):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for t in range(8):
        u=RPCS[(_r[0]+t)%2]
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
S_LEN=sb("poolVoteLength(address)"); S_PV=sb("poolVote(address,uint256)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def mc(cds,batch=70):
    out=[]; i=0
    while i<len(cds):
        ch=cds[i:i+batch]
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(V,True,bytes(c)) for c in ch]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},BLOCK])
        if r is None or len(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0])!=len(ch):
            if batch>5: batch=max(5,batch//2); continue
            out.extend([(False,b"")]*len(ch)); i+=len(ch); continue
        out.extend(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0]); i+=len(ch)
    return out
owners=sorted({x["owner"].lower() for x in json.load(open("top500_venfts.json"))})
a2t={s["address"].lower():s.get("title") for s in get("https://api.hydrex.fi/strategies")}
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39=1781136000; EPLEN=604800
CUR=39+(now-EP39)//EPLEN
while EP39+(CUR-39)*EPLEN+5*86400>now: CUR-=1
epochs=list(range(CUR-9,CUR+1)); blocks={K:hex(max(1,latest-(now-(EP39+(K-39)*EPLEN+5*86400))//2)) for K in epochs}
print(f"consistency scan: {len(owners)} owners x epochs {epochs[0]}..{epochs[-1]}", flush=True)
ep_pools={w:{} for w in owners}   # owner -> {epoch: [pool titles]}
for K in epochs:
    BLOCK=blocks[K]
    lens=[int.from_bytes(r,"big") if ok and r else 0 for ok,r in mc([S_LEN+pad(w) for w in owners])]
    pv_calls=[]; pv_idx=[]
    for w,n in zip(owners,lens):
        for i in range(min(n,6)): pv_calls.append(S_PV+pad(w)+U(i)); pv_idx.append(w)
    pools=["0x"+r[-20:].hex() if ok and r else None for ok,r in mc(pv_calls)]
    by={}
    for w,p in zip(pv_idx,pools):
        if p: by.setdefault(w,[]).append(a2t.get(p.lower(),p[:10]))
    for w,n in zip(owners,lens):
        if n>0: ep_pools[w][K]={"n":n,"pools":by.get(w,[])}
    print(f"  epoch {K}: {sum(1 for w in owners if K in ep_pools[w])}/{len(owners)} voted", flush=True)
def classify(d):
    voted=[v for v in d.values()]
    if not voted: return {"style":"—","dom_pool":None,"avg_pools":0,"epochs_voted":0}
    avg=sum(v["n"] for v in voted)/len(voted)
    cnt=Counter(p for v in voted for p in v["pools"])
    distinct=len(cnt); dom,domc=cnt.most_common(1)[0] if cnt else (None,0)
    dom_share=domc/len(voted)
    if avg<=1.5 and dom_share>=0.8 and distinct<=2: style="Same pool"
    elif avg<=3.5 and dom_share>=0.5 and distinct<=5: style="1-3 pools"
    else: style="Fee-max"
    top=[p for p,_ in cnt.most_common(3)]
    return {"style":style,"dom_pool":dom,"top_pools":top,"avg_pools":round(avg,1),"epochs_voted":len(voted),"distinct":distinct}
out={w:classify(ep_pools[w]) for w in owners}
json.dump(out,open("venft_consistency.json","w"))
print("tally:", dict(Counter(v["style"] for v in out.values())), flush=True)
print("DONE consistency", flush=True)
