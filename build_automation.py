"""Manual vs Automated detection for each top-100 wallet.
A wallet uses Hydrex Account Automation iff it approved the automation manager
0x53388a4e98bb56f8571433f5461010fc287929d3 as an operator on its veNFTs
(setApprovalForAll). Authoritative on-chain read: escrow.isApprovedForAll(wallet, AUTO).
Output: automation.json  ->  {wallet_lower: true/false}."""
import json, subprocess
from Crypto.Hash import keccak
from eth_abi import encode, decode
ESCROW="0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"
AUTO="0x53388a4e98bb56f8571433f5461010fc287929d3"   # Hydrex Account Automation manager
MC3="0xcA11bde05977b3631167028862bE2a173976CA11"
def sb(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return bytes.fromhex(k.hexdigest()[:8])
def rpc(m,p):
    pl=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p})
    o=subprocess.run(["curl","-s","--max-time","40","-X","POST","https://mainnet.base.org","-H","Content-Type: application/json","--data",pl],capture_output=True,text=True,timeout=50)
    return json.loads(o.stdout).get("result")
def pad(a): return bytes.fromhex(a[2:].zfill(64))
R=json.load(open("vehydx_top100_labeled.json"))
S_IAFA=sb("isApprovedForAll(address,address)"); S_AGG=sb("aggregate3((address,bool,bytes)[])")
calls=[(ESCROW,True,S_IAFA+pad(r["wallet"])+pad(AUTO)) for r in R]
data="0x"+(S_AGG+encode(["(address,bool,bytes)[]"],[calls])).hex()
res=decode(["(bool,bytes)[]"],bytes.fromhex(rpc("eth_call",[{"to":MC3,"data":data},"latest"])[2:]))[0]
out={}
for r,(ok,ret) in zip(R,res):
    out[r["wallet"].lower()]=bool(int.from_bytes(ret,"big")) if ok and ret else False
json.dump(out,open("automation.json","w"))
n=sum(out.values())
print(f"wrote automation.json: {n} automated, {len(out)-n} manual (of {len(out)})")
