import json, subprocess, time
from Crypto.Hash import keccak
from eth_abi import encode, decode
RPCS=["https://mainnet.base.org","https://base.drpc.org"]
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"; V="0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b"
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
S_VOTES=sb("votes(address,address)");S_AGG=sb("aggregate3((address,bool,bytes)[])")
_rr=[0]
def rpc(m,p,tries=8):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    for t in range(tries):
        u=RPCS[(_rr[0]+t)%len(RPCS)]
        try:
            o=subprocess.run(["curl","-s","--max-time","50","-X","POST",u,"-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=60)
            d=json.loads(o.stdout)
            if d.get("result") is not None: _rr[0]+=1; return d["result"]
        except Exception: pass
        time.sleep(0.4)
    return None
def pad(a): return bytes.fromhex("0"*24+a[2:])
def mc_votes(w, pools, block):
    """Return ({pool:weight}, n_failed_pools) for a wallet at block. Never raises."""
    out={}; failed=[0]
    def do(chunk, depth=0):
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(V,True,S_VOTES+pad(w)+pad(p)) for p in chunk]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},block])
        if r is None:
            if len(chunk)<=4 or depth>8:
                failed[0]+=len(chunk); return
            mid=len(chunk)//2; do(chunk[:mid],depth+1); do(chunk[mid:],depth+1); return
        for p,(ok,ret) in zip(chunk, decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0]):
            wt=int.from_bytes(ret,"big") if ok and len(ret)>=32 else 0
            if wt>0: out[p]=wt
    for i in range(0,len(pools),80):
        do(pools[i:i+80])
    return out, failed[0]

titles=json.load(open("pool_titles.json"))
F=json.load(open("top100_facts.json")); wallets=[f["wallet"] for f in F["facts"]]; pools=F["relevant_pools"]
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39=1781136000; EPLEN=604800
def block_at(ts): return max(1,latest-(now-ts)//2)
epochs=list(range(31,41))
ep_block={K:("latest" if K==40 else hex(block_at(EP39+(K-39)*EPLEN+5*86400))) for K in epochs}
print(f"history(robust v2): {len(wallets)}w x {len(pools)}p x {len(epochs)}ep", flush=True)
hist={w:{} for w in wallets}
for K in epochs:
    block=ep_block[K]; epnz=0; epfail=0
    for w in wallets:
        try:
            nz,nf=mc_votes(w,pools,block)
        except Exception:
            nz,nf={},len(pools)
        epfail+=nf; s=sum(nz.values())
        if s==0: hist[w][K]={"voted":False,"failed_pools":nf}
        else:
            epnz+=1; tops=sorted(nz.items(),key=lambda x:-x[1])[:2]
            hist[w][K]={"voted":True,"total":s/1e18,"n":len(nz),"failed_pools":nf,
                "top":[(titles.get(p,p[:10]), round(wt/s*100)) for p,wt in tops]}
    json.dump(hist, open("top100_history.json","w"))
    print(f"  epoch {K}: {epnz}/{len(wallets)} active  (pool-reads failed: {epfail})", flush=True)
print("DONE history", flush=True)
