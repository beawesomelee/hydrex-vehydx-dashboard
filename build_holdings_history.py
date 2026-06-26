"""Historical veHYDX holdings per top-100 wallet, per epoch (last 10 epochs) via archive RPC.
Holdings = sum of balanceOfNFT over the wallet's veNFTs AT each epoch block (matches the
dashboard's current column + Dune semantics; NOT getVotes, which is delegation-based and
reads 0 for the ~39% of holders that never self-delegated).
Output: top100_holdings.json -> {wallet: {epoch: veHYDX_power}}."""
import json, subprocess, time
from Crypto.Hash import keccak
from eth_abi import encode, decode
RPCS=["https://mainnet.base.org","https://base.drpc.org"]  # archive-capable only
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"
VE="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
S_BAL=sb("balanceOf(address)"); S_TOI=sb("tokenOfOwnerByIndex(address,uint256)")
S_BALNFT=sb("balanceOfNFT(uint256)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def pad(a): return bytes.fromhex("0"*24+a[2:])
def U(n): return n.to_bytes(32,"big")
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
def mc(calldatas, block, batch=80):
    """Multicall to VE; returns aligned list of (ok,ret_bytes) or None per item. Never raises."""
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
def U_uint(x): return int.from_bytes(x[1],"big") if x and x[0] and len(x[1])>=32 else 0

wallets=[f["wallet"] for f in json.load(open("top100_facts.json"))["facts"]]
latest=int(rpc("eth_blockNumber",[]),16); now=int(rpc("eth_getBlockByNumber",[hex(latest),False])["timestamp"],16)
EP39_START=1781136000; EPLEN=604800
def block_at(ts): return max(1,latest-(now-ts)//2)
CUR=39+(now-EP39_START)//EPLEN
while EP39_START+(CUR-39)*EPLEN+5*86400>now: CUR-=1   # latest epoch whose +5d sample has passed
epochs=list(range(CUR-9,CUR+1))                        # rolling last 10 epochs -> auto-advances each refresh
ep_block={K: hex(block_at(EP39_START+(K-39)*EPLEN+5*86400)) for K in epochs}
print(f"holdings scan (balanceOfNFT-sum): {len(wallets)} wallets x {len(epochs)} epochs", flush=True)
hist={w:{} for w in wallets}
for K in epochs:
    blk=ep_block[K]
    counts=[min(U_uint(x),120) for x in mc([S_BAL+pad(w) for w in wallets], blk)]  # NFT count per wallet (cap 120)
    # enumerate each wallet's token IDs at this block
    idx_calls=[]; idx_owner=[]
    for w,c in zip(wallets,counts):
        for i in range(c): idx_calls.append(S_TOI+pad(w)+U(i)); idx_owner.append(w)
    tids=[U_uint(x) for x in mc(idx_calls, blk)] if idx_calls else []
    # sum balanceOfNFT per owner
    powers=[U_uint(x)/1e18 for x in mc([S_BALNFT+U(t) for t in tids], blk)] if tids else []
    agg={w:0.0 for w in wallets}
    for w,p in zip(idx_owner,powers): agg[w]+=p
    for w in wallets: hist[w][K]=round(agg[w],2)
    print(f"  epoch {K}: {sum(1 for w in wallets if agg[w]>0)}/{len(wallets)} nonzero, {len(tids)} NFTs read", flush=True)
json.dump(hist, open("top100_holdings.json","w"))
print("DONE holdings", flush=True)
