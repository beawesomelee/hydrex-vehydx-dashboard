"""Per-owner voting CONSISTENCY across the last 10 epochs, for the top-500-lock owners.
Reads the SET of pools each owner has a standing vote on, at each epoch block (archive)
plus the current epoch (latest block), via Voter.poolVoteLength + poolVote -> classify:
  'Same pool'      = ~1 pool, the same one >=80% of voted epochs
  '1-3 pools'      = a small stable set (<=3/epoch, few distinct)
  'Fee-max'        = switches pools across epochs / sprays many (mercenary)
  'No active vote' = voted at some point in-window (lastVoted in range) but holds no
                     standing gauge vote now / at any sample (e.g. voted once then went
                     passive on a compounding automation)
  'Did not vote'   = lastVoted is 0 or older than the window AND no standing vote anywhere

Robustness (the 'false did-not-vote' fix): a failed RPC read is NEVER silently counted
as 0 — every poolVoteLength miss is retried per-owner, and lastVoted(owner) is an
independent backstop so an owner who voted in-window can't be mislabeled idle even if a
per-epoch standing read happens to be 0 (late vote / reset-then-revote / current epoch).
Output: venft_consistency.json -> {owner: {style, dom_pool, top_pools, avg_pools,
                                            epochs_voted, distinct, last_voted_ep}}."""
import json, subprocess, time
from collections import Counter
from Crypto.Hash import keccak
from eth_abi import encode, decode
V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"; MC3="0xca11bde05977b3631167028862be2a173976ca11"
RPCS=["https://mainnet.base.org","https://base.drpc.org","https://base-rpc.publicnode.com"]
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
_r=[0]
def rpc(m,p):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for t in range(10):
        u=RPCS[(_r[0]+t)%len(RPCS)]
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
S_LEN=sb("poolVoteLength(address)"); S_PV=sb("poolVote(address,uint256)"); S_LV=sb("lastVoted(address)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def mc(cds, block, batch=70):
    """strict, aligned; each element is (ok, bytes). A failed call is (False, b'') — NEVER a fake 0."""
    out=[]; i=0
    while i<len(cds):
        ch=cds[i:i+batch]
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(V,True,bytes(c)) for c in ch]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},block])
        if r is None or len(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0])!=len(ch):
            if batch>5: batch=max(5,batch//2); continue
            out.extend([(False,b"")]*len(ch)); i+=len(ch); continue
        out.extend(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0]); i+=len(ch)
    return out
def call1(sel_payload, block):
    for _ in range(4):
        r=rpc("eth_call",[{"to":V,"data":"0x"+sel_payload.hex()},block])
        if r is not None and r!="0x": return r
    return None

owners=sorted({x["owner"].lower() for x in json.load(open("top500_venfts.json"))})
a2t={s["address"].lower():s.get("title") for s in get("https://api.hydrex.fi/strategies")}
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39=1781136000; EPLEN=604800
CUR=39+(now-EP39)//EPLEN
while EP39+(CUR-39)*EPLEN+5*86400>now: CUR-=1
epochs=list(range(CUR-9,CUR+1)); blocks={K:hex(max(1,latest-(now-(EP39+(K-39)*EPLEN+5*86400))//2)) for K in epochs}
WIN_START=EP39+(epochs[0]-39)*EPLEN
def ep_of(ts): return 39+(ts-EP39)//EPLEN
print(f"consistency scan: {len(owners)} owners x epochs {epochs[0]}..{epochs[-1]} (+current @latest)", flush=True)

def scan(block):
    """returns {owner: {'n':len,'pools':[...]}} for owners with a standing vote; owners
    whose length read could not be confirmed are recorded as {'unread':True}."""
    lens=[int.from_bytes(b,"big") if (ok and b) else None for ok,b in mc([S_LEN+pad(w) for w in owners], block)]
    for idx,w in enumerate(owners):              # retry every UNREAD length per-owner (no silent 0)
        if lens[idx] is None:
            r=call1(S_LEN+pad(w), block)
            if r is not None: lens[idx]=int(r,16)
    pv_calls=[]; pv_idx=[]
    for w,n in zip(owners,lens):
        if n:
            for i in range(min(n,6)): pv_calls.append(S_PV+pad(w)+U(i)); pv_idx.append(w)
    pools=["0x"+b[-20:].hex() if (ok and b) else None for ok,b in mc(pv_calls, block)]
    by={}
    for w,p in zip(pv_idx,pools):
        if p: by.setdefault(w,[]).append(a2t.get(p.lower(),p[:10]))
    out={}
    for w,n in zip(owners,lens):
        if n is None: out[w]={"unread":True}
        elif n>0:     out[w]={"n":n,"pools":by.get(w,[])}
    return out

# lastVoted(owner) — authoritative single read, the backstop against false "did not vote"
lv={}; res=mc([S_LV+pad(w) for w in owners], hex(latest))
for w,(ok,b) in zip(owners,res): lv[w]=int.from_bytes(b,"big") if (ok and b) else None
for w in [w for w in owners if lv[w] is None]:
    r=call1(S_LV+pad(w), hex(latest))
    if r is not None: lv[w]=int(r,16)
print(f"  lastVoted read for {sum(1 for w in owners if lv[w] is not None)}/{len(owners)} owners", flush=True)

ep_pools={w:{} for w in owners}
for K in epochs:
    s=scan(blocks[K])
    for w,d in s.items():
        if "n" in d: ep_pools[w][K]=d
    print(f"  epoch {K}: {sum(1 for w in owners if K in ep_pools[w])}/{len(owners)} have a standing vote", flush=True)
scur=scan(hex(latest))                            # current epoch — catches live voters past the +5d samples
for w,d in scur.items():
    if "n" in d: ep_pools[w]["cur"]=d
print(f"  current @latest: {sum(1 for w in owners if 'cur' in ep_pools[w])}/{len(owners)} have a live standing vote", flush=True)

def classify(d, lvt):
    voted=[v for v in d.values()]
    if voted:
        nep=len(voted); avg=sum(v["n"] for v in voted)/nep
        cnt=Counter(p for v in voted for p in v["pools"])
        pep=Counter()                         # epochs each pool appears in (set per epoch)
        for v in voted:
            for p in set(v["pools"]): pep[p]+=1
        distinct=len(cnt); dom,domc=cnt.most_common(1)[0] if cnt else (None,0)
        dom_share=domc/nep
        if avg<=1.5 and dom_share>=0.8 and distinct<=2: style="Same pool"
        elif avg<=3.5 and dom_share>=0.5 and distinct<=5: style="1-3 pools"
        else: style="Fee-max"
        top=[p for p,_ in cnt.most_common(3)]
        # stable core = pools voted in >=80% of voted epochs (needs >=3 epochs to claim consistency).
        # for a Fee-max account this is what they back EVERY epoch despite spreading; empty => they switch.
        stable=[p for p,c in pep.most_common() if nep>=3 and c>=0.8*nep][:4]
        return {"style":style,"dom_pool":dom,"top_pools":top,"stable_pools":stable,"avg_pools":round(avg,1),
                "epochs_voted":nep,"distinct":distinct,"last_voted_ep":(ep_of(lvt) if lvt else None)}
    # no standing vote at any sample (incl. current): split idle vs voted-then-passive via lastVoted
    if lvt and lvt>=WIN_START:
        return {"style":"No active vote","dom_pool":None,"top_pools":[],"avg_pools":0,
                "epochs_voted":0,"distinct":0,"last_voted_ep":ep_of(lvt)}
    return {"style":"Did not vote","dom_pool":None,"top_pools":[],"avg_pools":0,
            "epochs_voted":0,"distinct":0,"last_voted_ep":(ep_of(lvt) if lvt else None)}

out={w:classify(ep_pools[w], lv.get(w)) for w in owners}
json.dump(out,open("venft_consistency.json","w"))
print("tally:", dict(Counter(v["style"] for v in out.values())), flush=True)
print("DONE consistency", flush=True)
