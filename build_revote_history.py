"""Detect HOW each top-100 wallet votes (not just what) via Voter.lastVoted(account).
Votes persist across epochs in this ve(3,3), so 'votes pool X every epoch' is ambiguous.
lastVoted (read at each epoch block + latest) reveals the re-vote pattern:
  - never changes      -> SET-AND-FORGET (voted once long ago, vote just carries forward)
  - changes ~weekly at a TIGHT time-of-day -> AUTOMATED (bot/keeper on a schedule)
  - changes ~weekly at SCATTERED times     -> ACTIVE (manual human re-voting)
  - lastVoted == 0     -> NEVER VOTED
Output: top100_revote.json -> {wallet: {mode, n_revotes, last_vote, tod_R, revotes:[ts...]}}."""
import json, subprocess, time, math
from Crypto.Hash import keccak
from eth_abi import encode, decode
RPCS=["https://mainnet.base.org","https://base.drpc.org"]
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"; V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
S_LV=sb("lastVoted(address)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def pad(a): return bytes.fromhex("0"*24+a[2:])
_rr=[0]
def rpc(m,p,tries=8):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for t in range(tries):
        u=RPCS[(_rr[0]+t)%len(RPCS)]
        try:
            o=subprocess.run(["curl","-s","--max-time","45","-X","POST",u,"-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=55)
            d=json.loads(o.stdout)
            if d.get("result") is not None: _rr[0]+=1; return d["result"]
        except Exception: pass
        time.sleep(0.3)
    return None
def mc_lv(wallets, block):
    out={}
    def do(lo,hi,depth=0):
        ch=wallets[lo:hi]
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(V,True,S_LV+pad(w)) for w in ch]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},block])
        if r is None:
            if hi-lo<=3 or depth>8: return
            mid=(lo+hi)//2; do(lo,mid,depth+1); do(mid,hi,depth+1); return
        for w,(ok,ret) in zip(ch, decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0]):
            out[w]=int.from_bytes(ret,"big") if ok and len(ret)>=32 else 0
    for i in range(0,len(wallets),80): do(i,min(i+80,len(wallets)))
    return out

wallets=[f["wallet"] for f in json.load(open("top100_facts.json"))["facts"]]
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39=1781136000; EPLEN=604800
def block_at(ts): return max(1,latest-(now-ts)//2)
blocks=[hex(block_at(EP39+(K-39)*EPLEN+5*86400)) for K in range(31,41)]+["latest"]
print(f"revote scan: {len(wallets)} wallets x {len(blocks)} samples", flush=True)
series={w:[] for w in wallets}
for blk in blocks:
    res=mc_lv(wallets, blk)
    for w in wallets: series[w].append(res.get(w,0))
    print(f"  sampled {blk}", flush=True)

def classify(ts_list):
    distinct=sorted(set(t for t in ts_list if t>0))
    if not distinct: return {"mode":"Never voted","n_revotes":0,"last_vote":None,"tod_R":None,"revotes":[]}
    n=len(distinct); last=distinct[-1]
    if n==1: return {"mode":"Set-and-forget","n_revotes":1,"last_vote":last,"tod_R":None,"revotes":distinct}
    # time-of-day concentration (circular): R near 1 = same time daily = automated
    ang=[2*math.pi*(t%86400)/86400 for t in distinct]
    R=math.hypot(sum(math.cos(a) for a in ang),sum(math.sin(a) for a in ang))/n
    mode="Automated" if R>=0.85 else "Active"
    return {"mode":mode,"n_revotes":n,"last_vote":last,"tod_R":round(R,3),"revotes":distinct}

out={w:classify(series[w]) for w in wallets}
json.dump(out, open("top100_revote.json","w"))
from collections import Counter
print("\nMODE tally:", dict(Counter(v["mode"] for v in out.values())), flush=True)
print("DONE revote", flush=True)
