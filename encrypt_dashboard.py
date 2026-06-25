#!/usr/bin/env python3
"""Seal an HTML file behind a client-side AES-256-GCM passphrase gate (Web Crypto compatible).
Usage: python3 encrypt_dashboard.py "<passphrase>" [input.html] [output.html]
The passphrase is used ONLY locally to encrypt; it is never stored in the output (only ciphertext is)."""
import sys, base64, json
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

ITER=250000
passphrase=sys.argv[1]
infile=sys.argv[2] if len(sys.argv)>2 else "vehydx_dashboard_plain.html"
outfile=sys.argv[3] if len(sys.argv)>3 else "vehydx_dashboard.html"
plain=open(infile,"rb").read()
salt=get_random_bytes(16); iv=get_random_bytes(12)
key=PBKDF2(passphrase, salt, dkLen=32, count=ITER, hmac_hash_module=SHA256)
ct,tag=AES.new(key, AES.MODE_GCM, nonce=iv).encrypt_and_digest(plain)
blob=ct+tag
B=lambda b: base64.b64encode(b).decode()

# self-verify round-trip (mimics what the browser will do)
k2=PBKDF2(passphrase, salt, dkLen=32, count=ITER, hmac_hash_module=SHA256)
dec=AES.new(k2, AES.MODE_GCM, nonce=iv).decrypt_and_verify(blob[:-16], blob[-16:])
assert dec==plain, "round-trip FAILED"
print("round-trip verify: OK")

shell="""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Hydrex veHYDX · Locked</title><style>
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.box{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:32px;width:340px;text-align:center}
.lock{font-size:30px;margin-bottom:10px}h1{font-size:16px;margin:0 0 4px}.s{color:#8b949e;font-size:12px;margin-bottom:18px}
input{width:100%;background:#0d1117;border:1px solid #30363d;color:#e6edf3;padding:11px;border-radius:8px;font-size:14px;margin-bottom:10px}
button{width:100%;background:#238636;border:0;color:#fff;padding:11px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#2ea043}.err{color:#f85149;font-size:12px;height:16px;margin-top:8px}
</style></head><body><div class="box">
<div class="lock">\U0001F512</div><h1>Hydrex veHYDX Intelligence</h1><div class="s">Enter passphrase to decrypt</div>
<input id="p" type="password" placeholder="passphrase" autofocus onkeydown="if(event.key==='Enter')go()"/>
<button onclick="go()">Unlock</button><div class="err" id="e"></div></div>
<script>
const SALT="__SALT__",IV="__IV__",CT="__CT__",ITER=__ITER__;
const u8=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function go(){
 const pass=document.getElementById('p').value, e=document.getElementById('e'); e.textContent='';
 try{
  const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:u8(SALT),iterations:ITER,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['decrypt']);
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:u8(IV)},key,u8(CT));
  const html=new TextDecoder().decode(pt);
  document.open();document.write(html);document.close();
 }catch(err){e.textContent='Wrong passphrase';}
}
</script></body></html>"""
out=(shell.replace("__SALT__",B(salt)).replace("__IV__",B(iv)).replace("__CT__",B(blob)).replace("__ITER__",str(ITER)))
open(outfile,"w").write(out)
print(f"wrote {outfile} ({len(out)} bytes) — passphrase NOT stored, ciphertext only")
