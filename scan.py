"""Scan all veHYDX NFTs via Multicall3 -> aggregate voting power by owner wallet."""
import subprocess, json, sys, time
from Crypto.Hash import keccak
from eth_abi import encode, decode

RPCS = ["https://mainnet.base.org","https://base.llamarpc.com","https://base-rpc.publicnode.com","https://1rpc.io/base"]
VE = "0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"
MC3 = "0xcA11bde05977b3631167028862bE2a173976CA11"

def sel(sig):
    k=keccak.new(digest_bits=256); k.update(sig.encode()); return bytes.fromhex(k.hexdigest()[:8])
S_OWNER = sel("ownerOf(uint256)")
S_BAL   = sel("balanceOfNFT(uint256)")
S_AGG3  = sel("aggregate3((address,bool,bytes)[])")

def rpc(method, params, tries=3):
    payload=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params})
    for attempt in range(tries):
        for url in RPCS:
            try:
                out=subprocess.run(["curl","-s","--max-time","40","-X","POST",url,
                    "-H","Content-Type: application/json","--data",payload],
                    capture_output=True,text=True,timeout=50)
                d=json.loads(out.stdout)
                if "result" in d and d["result"] is not None: return d["result"]
            except Exception: continue
        time.sleep(1.0)
    return None

def multicall(tids):
    calls=[]
    for t in tids:
        arg=t.to_bytes(32,"big")
        calls.append((VE, True, S_OWNER+arg))
        calls.append((VE, True, S_BAL+arg))
    data="0x"+(S_AGG3+encode(["(address,bool,bytes)[]"],[calls])).hex()
    res=rpc("eth_call",[{"to":MC3,"data":data},"latest"])
    if not res: return None
    out=decode(["(bool,bytes)[]"], bytes.fromhex(res[2:]))[0]
    # pair up: [ (ok,ret) ownerOf, (ok,ret) bal ] per token
    pairs=[]
    for i,t in enumerate(tids):
        ok_o,ret_o = out[2*i]; ok_b,ret_b = out[2*i+1]
        owner = ("0x"+ret_o[-20:].hex()) if ok_o and len(ret_o)>=32 else None
        power = int.from_bytes(ret_b,"big") if ok_b and len(ret_b)>=32 else 0
        pairs.append((t,owner,power))
    return pairs

if __name__=="__main__":
    # quick self-test on a known range
    test=list(range(4100,4130))
    pr=multicall(test)
    print("test batch (token, owner, veHYDX):")
    for t,o,p in pr[:6]:
        print(f"  {t}  {o}  {p/1e18:.6f}")
    nz=[x for x in pr if x[2]>0]
    print(f"nonzero in test: {len(nz)}/{len(pr)}")
