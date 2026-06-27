"""Top-500 individual veNFTs by power (per-account / per-lock view).
A lock's power can't exceed its owner's total power, so enumerating every owner with
total power >= 30K is a guaranteed superset of the owners of the top-500 locks.
For each such owner: balanceOf -> tokenOfOwnerByIndex -> balanceOfNFT(tokenId).
Output: top500_venfts.json -> [{tokenId, owner, power}] (top 500 by power)."""
import json, subprocess, time
from Crypto.Hash import keccak
from eth_abi import encode, decode
ESC="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"; MC3="0xca11bde05977b3631167028862be2a173976ca11"
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
            if r: _r[0]+=1; return r
        except Exception: pass
        time.sleep(0.3)
    return None
def pad(a): return bytes.fromhex(a[2:].lower().zfill(64))
def U(n): return int(n).to_bytes(32,"big")
S_BAL=sb("balanceOf(address)"); S_TOK=sb("tokenOfOwnerByIndex(address,uint256)"); S_BNFT=sb("balanceOfNFT(uint256)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
def mc(cds,batch=140):
    out=[]
    def do(lo,hi,depth=0):
        ch=cds[lo:hi]
        data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[[(ESC,True,bytes(c)) for c in ch]])).hex()
        r=rpc("eth_call",[{"to":MC3,"data":data},"latest"])
        if r is None:
            if hi-lo<=4 or depth>9: out.extend([(False,b"")]*(hi-lo)); return
            mid=(lo+hi)//2; do(lo,mid,depth+1); do(mid,hi,depth+1); return
        out.extend(decode(["(bool,bytes)[]"],bytes.fromhex(r[2:]))[0])
    for i in range(0,len(cds),batch): do(i,min(i+batch,len(cds)))
    return out
op=json.load(open("owner_power.json"))["owner_power"]
owners=sorted((k for k,v in op.items() if float(v)/1e18>=30000), key=lambda k:-float(op[k]))
print(f"enumerating {len(owners)} owners (>=30K power)…", flush=True)
bals=[int.from_bytes(r,"big") if ok and r else 0 for ok,r in mc([S_BAL+pad(w) for w in owners])]
print(f"total veNFTs to read: {sum(bals)}", flush=True)
tcalls=[]; towner=[]
for w,b in zip(owners,bals):
    for i in range(b): tcalls.append(S_TOK+pad(w)+U(i)); towner.append(w)
toks=[int.from_bytes(r,"big") if ok and r else None for ok,r in mc(tcalls)]
print(f"got {sum(1 for t in toks if t is not None)} token ids; reading power…", flush=True)
pairs=[(t,w) for t,w in zip(toks,towner) if t is not None]
pows=[int.from_bytes(r,"big") if ok and r else 0 for ok,r in mc([S_BNFT+U(t) for t,_ in pairs])]
allnfts=sorted(({"tokenId":t,"owner":w,"power":p} for (t,w),p in zip(pairs,pows) if p>0), key=lambda x:-x["power"])
top=allnfts[:500]
json.dump(top, open("top500_venfts.json","w"))
print(f"DONE: {len(allnfts)} locks total; top500 power range {top[0]['power']/1e18:.0f} .. {top[-1]['power']/1e18:.0f}", flush=True)
print(f"completeness: 500th lock = {top[-1]['power']/1e18:.0f} veHYDX (must be > 30000 enum floor: {'OK' if top[-1]['power']/1e18>30000 else 'LOWER THRESHOLD'})", flush=True)
print(f"distinct owners in top500: {len({x['owner'] for x in top})}", flush=True)
