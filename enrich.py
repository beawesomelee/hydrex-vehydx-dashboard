"""Enrich wallet addresses: Basenames reverse + contract/EOA detection."""
import subprocess, json
from Crypto.Hash import keccak
RPCS=["https://mainnet.base.org","https://base.llamarpc.com"]
L2RESOLVER="0xC6d566A56A1aFf6508b41f6c90ff131615583BCD"  # Base Basenames L2 Resolver
BASE_COINTYPE_HEX="80002105"  # ENSIP-11 base reverse

def k(b):
    h=keccak.new(digest_bits=256); h.update(b); return h.digest()
def sel(sig): return k(sig.encode())[:4]
def rpc(method,params):
    payload=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params})
    for url in RPCS:
        try:
            out=subprocess.run(["curl","-s","--max-time","25","-X","POST",url,"-H","Content-Type: application/json","--data",payload],capture_output=True,text=True,timeout=30)
            d=json.loads(out.stdout)
            if "result" in d and d["result"] is not None: return d["result"]
        except Exception: continue
    return None
def namehash(name):
    node=b"\x00"*32
    if name:
        for label in reversed(name.split(".")):
            node=k(node+k(label.encode()))
    return node
def dec_str(h):
    if not h or h=="0x": return None
    b=bytes.fromhex(h[2:])
    if len(b)<64: return None
    ln=int.from_bytes(b[32:64],"big"); s=b[64:64+ln].decode("utf-8","ignore")
    return s or None
def basename(addr):
    rev=addr[2:].lower()+"."+BASE_COINTYPE_HEX+".reverse"
    node=namehash(rev)
    data="0x"+(sel("name(bytes32)")+node).hex()
    return dec_str(rpc("eth_call",[{"to":L2RESOLVER,"data":data},"latest"]))
def is_contract(addr):
    code=rpc("eth_getCode",[addr,"latest"])
    return bool(code and code!="0x" and len(code)>2)

if __name__=="__main__":
    for a in ["0x83f6255d5278dcfc3c41546f95540d71126bb72e",
              "0xc141dcc16e0a1e46438d5c4ebe92285dcda01c28",
              "0x5b4e6e8181d408677a7598b19b1fdd58b3d7ab21"]:
        print(f"{a}  basename={basename(a)!r}  contract={is_contract(a)}")
