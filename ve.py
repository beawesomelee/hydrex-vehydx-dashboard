"""Minimal on-chain reader for Hydrex veHYDX (Aerodrome-style VotingEscrow) on Base.
RPC via curl subprocess (clean SSL); selectors via keccak (pycryptodome)."""
import subprocess, json
from Crypto.Hash import keccak

RPCS = ["https://mainnet.base.org", "https://base.llamarpc.com", "https://base-rpc.publicnode.com"]
VE   = "0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1"   # veHYDX VotingEscrow (proxy)
HYDX = "0x00000e7efa313F4E11Bfff432471eD9423AC6B30"

def sel(sig):
    k = keccak.new(digest_bits=256); k.update(sig.encode()); return k.hexdigest()[:8]

def rpc(method, params):
    payload = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params})
    for url in RPCS:
        try:
            out = subprocess.run(["curl","-s","--max-time","30","-X","POST",url,
                                  "-H","Content-Type: application/json","--data",payload],
                                 capture_output=True, text=True, timeout=40)
            d = json.loads(out.stdout)
            if "result" in d and d["result"] is not None:
                return d["result"]
        except Exception:
            continue
    return None

def eth_call(to, sig, args_hex=""):
    return rpc("eth_call", [{"to": to, "data": "0x"+sel(sig)+args_hex}, "latest"])

def U(n): return f"{int(n):064x}"
def d_uint(h): return int(h, 16) if h and h != "0x" else None
def d_addr(h): return ("0x"+h[-40:]) if h and len(h) >= 42 else None
def d_str(h):
    if not h: return None
    b = bytes.fromhex(h[2:] if h.startswith("0x") else h)
    if len(b) < 64: return None
    ln = int.from_bytes(b[32:64], "big"); return b[64:64+ln].decode("utf-8","ignore")

if __name__ == "__main__":
    print("== veHYDX VotingEscrow probe ==", VE)
    print("name        :", d_str(eth_call(VE, "name()")))
    print("symbol      :", d_str(eth_call(VE, "symbol()")))
    print("totalSupply :", d_uint(eth_call(VE, "totalSupply()")), "(ERC721 enumerable NFT count?)")
    print("tokenId ctr :", d_uint(eth_call(VE, "tokenId()")), "(last minted id?)")
    print("supply      :", (lambda x: x/1e18 if x else x)(d_uint(eth_call(VE, "supply()"))), "(total locked HYDX?)")
    print("voter()     :", d_addr(eth_call(VE, "voter()")))
    print("team()      :", d_addr(eth_call(VE, "team()")))
    print("token()     :", d_addr(eth_call(VE, "token()")))
    print("epoch()     :", d_uint(eth_call(VE, "epoch()")))
    # sample NFT #2197 (seen on Element)
    tid = 2197
    print(f"\n-- sample tokenId {tid} --")
    print("ownerOf       :", d_addr(eth_call(VE, "ownerOf(uint256)", U(tid))))
    print("balanceOfNFT  :", (lambda x: x/1e18 if x else x)(d_uint(eth_call(VE, "balanceOfNFT(uint256)", U(tid)))), "(voting power)")
    print("locked raw    :", eth_call(VE, "locked(uint256)", U(tid)))
