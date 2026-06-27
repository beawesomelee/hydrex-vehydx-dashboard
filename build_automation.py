"""Manual vs Automated + exact strategy (Hydrex 'conduits') per wallet.
Each Hydrex Account Automation strategy is a 'conduit' with its OWN address
(api.hydrex.fi/conduits -> id, name, address). A wallet is on a conduit iff it
approved that conduit as an operator: escrow.isApprovedForAll(wallet, conduit.address).
So the conduit a wallet approved == its exact strategy name.
Output: automation.json -> {wallet_lower: {automated, strategy, conduit_id, n_conduits}}."""
import json, subprocess
from Crypto.Hash import keccak
from eth_abi import encode, decode
ESCROW="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
def rpc(m,p):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    o=subprocess.run(["curl","-s","--max-time","45","-X","POST","https://mainnet.base.org","-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=55)
    return json.loads(o.stdout).get("result")
def pad(a): return bytes.fromhex(a[2:].zfill(64))
def get(url):
    return subprocess.run(["curl","-s","--max-time","30",url],capture_output=True,text=True,timeout=40).stdout
conduits=[{"id":c["id"],"name":c["name"],"addr":c["address"].lower()} for c in json.loads(get("https://api.hydrex.fi/conduits"))]
print(f"{len(conduits)} conduits (strategies) loaded from api.hydrex.fi/conduits")
R=json.load(open("vehydx_top100_labeled.json"))
S_IAFA=sb("isApprovedForAll(address,address)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
pairs=[(r["wallet"].lower(), c) for r in R for c in conduits]
calls=[(ESCROW,True,S_IAFA+pad(w)+pad(c["addr"])) for w,c in pairs]
results=[]
for i in range(0,len(calls),300):
    chunk=calls[i:i+300]
    data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[chunk])).hex()
    results+=decode(["(bool,bytes)[]"],bytes.fromhex(rpc("eth_call",[{"to":MC3,"data":data},"latest"])[2:]))[0]
approved={}
for (w,c),(ok,ret) in zip(pairs,results):
    if ok and ret and int.from_bytes(ret,"big"): approved.setdefault(w,[]).append(c)
out={}; multi=0
for r in R:
    w=r["wallet"].lower(); cs=approved.get(w,[])
    if cs:
        if len(cs)>1: multi+=1
        out[w]={"automated":True,"strategy":cs[0]["name"],"conduit_id":cs[0]["id"],"n_conduits":len(cs)}
    else:
        out[w]={"automated":False,"strategy":None,"conduit_id":None,"n_conduits":0}
json.dump(out,open("automation.json","w"))
from collections import Counter
n=sum(1 for v in out.values() if v["automated"])
print(f"wrote automation.json: {n} automated / {len(out)-n} manual; {multi} approved >1 conduit")
print("strategy tally:", dict(Counter(v["strategy"] for v in out.values() if v["strategy"])))
