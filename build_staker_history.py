"""Staker count + total veHYDX over epochs (protocol's full history) via archive RPC.
 - total veHYDX  = VotingEscrow.totalSupply() at each epoch block (1 call/epoch)
 - staker count  = # of current owners with balanceOf>0 at each epoch block
   (current-cohort approximation: counts when today's stakers joined; undercounts
    holders who have since fully exited, but captures the growth trend cleanly)
Output: staker_history.json -> {epochs:[...], stakers:[...], total_vehydx_m:[...]}."""
import json, subprocess, time
from Crypto.Hash import keccak
from eth_abi import encode, decode
RPCS=["https://mainnet.base.org","https://base.drpc.org"]
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"
VE="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
S_BAL=sb("balanceOf(address)"); S_TS=sb("totalSupply()"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
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
def mc(calldatas, block, batch=120):
    res=[None]*len(calldatas)
    def do(lo,hi,depth=0):
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(VE,True,c) for c in calldatas[lo:hi]]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},block])
        if r is None:
            if hi-lo<=3 or depth>8: return
            mid=(lo+hi)//2; do(lo,mid,depth+1); do(mid,hi,depth+1); return
        for j,(ok,ret) in enumerate(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0]): res[lo+j]=(ok,ret)
    for i in range(0,len(calldatas),batch): do(i,min(i+batch,len(calldatas)))
    return res

owners=list(json.load(open("owner_power.json"))["owner_power"].keys())
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39=1781136000; EPLEN=604800
def block_at(ts): return max(1,latest-(now-ts)//2)
CUR=39+(now-EP39)//EPLEN
while EP39+(CUR-39)*EPLEN+5*86400>now: CUR-=1
# full history: epoch 1 (~escrow launch Sep 2025) .. current
epochs=list(range(1,CUR+1))
print(f"staker history: {len(owners)} owners x {len(epochs)} epochs ({epochs[0]}..{epochs[-1]})", flush=True)
out={"epochs":[],"stakers":[],"total_vehydx_m":[]}
for K in epochs:
    blk=hex(block_at(EP39+(K-39)*EPLEN+5*86400))
    ts=rpc("eth_call",[{"to":VE,"data":"0x"+S_TS.hex()},blk]); tv=(int(ts,16)/1e18/1e6) if ts and ts!="0x" else 0
    res=mc([S_BAL+pad(w) for w in owners], blk)
    cnt=sum(1 for x in res if x and x[0] and int.from_bytes(x[1],"big")>0)
    out["epochs"].append(K); out["stakers"].append(cnt); out["total_vehydx_m"].append(round(tv,1))
    print(f"  ep{K}: stakers={cnt}  totalveHYDX={tv:.1f}M", flush=True)
json.dump(out, open("staker_history.json","w"))
print("DONE staker", flush=True)
