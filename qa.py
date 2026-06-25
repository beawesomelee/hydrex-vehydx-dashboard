#!/usr/bin/env python3
"""QA gate for the veHYDX dashboard pipeline. Run AFTER synth.py + build_dashboard.py +
encrypt_dashboard.py and BEFORE publishing. Exits non-zero if any check fails.

Every check encodes a real failure mode we actually hit, so a weekly auto-refresh
can't silently re-ship a known bug."""
import json, subprocess, sys, re
from collections import Counter

FAILS=[]; WARNS=[]; PASSES=0
def check(name, ok, detail="", warn=False):
    global PASSES
    if ok: PASSES+=1; print(f"  PASS  {name}")
    elif warn: WARNS.append(name); print(f"  WARN  {name}  {detail}")
    else: FAILS.append(name); print(f"  FAIL  {name}  {detail}")

def load(f):
    try: return json.load(open(f))
    except Exception as e: check(f"load {f}", False, str(e)); return None

print("== A. data integrity ==")
op=load("owner_power.json"); facts=load("top100_facts.json"); R=load("vehydx_top100_labeled.json"); H=load("top100_history.json")
if op:
    tot=sum(op["owner_power"].values()); declared=int(op.get("total_power_wei",0))
    check("owner_power sums to totalSupply (<=0.1% drift)",
          declared==0 or abs(tot-declared)/declared<0.001, f"sum={tot/1e18:.0f} vs {declared/1e18:.0f}")
if facts:
    check("top100_facts has 100 wallets", len(facts.get("facts",[]))==100, f"got {len(facts.get('facts',[]))}")
if R:
    check("labeled output has 100 rows", len(R)==100, f"got {len(R)}")
    need=["likely_who","entity_type","confidence","voting_style","epochs_voted","dom_pool","dom_share","avg_pools_per_epoch"]
    miss=[r["rank"] for r in R if any(k not in r for k in need)]
    check("every row has all required fields", not miss, f"missing on ranks {miss[:5]}")
    check("confidence values valid", all(r["confidence"] in ("high","medium","low") for r in R))
    check("entity_type values valid", all(r["entity_type"] in
          ("hydrex_treasury_or_team","partner_project","individual_whale","alm_vault","managed_lock","market_maker","unknown") for r in R))
    TREAS={"0xea1bf482b7d3526ccf37a8a3fee330c960877f08","0x813f98f0f29509d558b2479d8ee0c8068c160bd3","0xb4d2861d525aef313be0c497c3335a58f637e73e"}
    bad_team=[r["rank"] for r in R if r["entity_type"]=="hydrex_treasury_or_team"
              and not (r.get("treasury_signer_match") or r["wallet"].lower() in TREAS)]
    check("'team/treasury' asserted only with signer evidence (no codehash over-attribution)",
          not bad_team, f"ranks {bad_team} labeled team without a treasury-signer match")

print("\n== B. history sanity (regression: false-idle from RPC failures) ==")
if H:
    R_w={r["wallet"] for r in R} if R else set()
    per_epoch={}
    for w,h in H.items():
        for k,v in h.items():
            per_epoch.setdefault(int(k),[0,0,0]); per_epoch[int(k)][0]+=1
            if v.get("voted"): per_epoch[int(k)][1]+=1
            per_epoch[int(k)][2]+=v.get("failed_pools",0)
    eps=sorted(per_epoch)
    check("history has 10 epochs", len(eps)==10, f"got {len(eps)}")
    min_active=min(per_epoch[e][1] for e in eps) if eps else 0
    # current-epoch active ~80; any epoch with <30 active almost certainly = silent RPC failures
    check("no epoch looks like a silent-RPC-failure idle wall (>=30/100 active each epoch)",
          min_active>=30, f"min active in any epoch = {min_active} (false-idle bug signature)")
    tot_failed=sum(per_epoch[e][2] for e in eps)
    check("history pool-reads did not fail (failed_pools ~0)", tot_failed==0, f"{tot_failed} failed reads", warn=tot_failed>0 and tot_failed<200)

print("\n== C. classification sanity (regression: avg_n Anchored bug + style drift) ==")
if R:
    sc=Counter(r["voting_style"] for r in R)
    check("voting styles cover all 100", sum(sc.values())==100, dict(sc))
    check("Idle <=> epochs_voted==0",
          all((r["voting_style"]=="Idle")==(r["epochs_voted"]==0) for r in R))
    bad_loyal=[r["rank"] for r in R if r["voting_style"]=="Anchored" and (r["avg_pools_per_epoch"]>3 or r["dom_share"]<0.7)]
    check("every Anchored really is concentrated (<=3 pools/ep & dom>=70%)", not bad_loyal,
          f"ranks violating: {bad_loyal} (the 9.7-pools 'Anchored' bug)")
    # re-derive style from stored metrics and assert it matches (catches synth/output drift)
    def restyle(r):
        if r["epochs_voted"]==0 or not r["dom_pool"]: return "Idle"
        n=r["avg_pools_per_epoch"]; ds=r["dom_share"]; dp=r["distinct_pools"]
        if n<=3 and ds>=0.7: s="Anchored"
        elif n<=6 and (ds>=0.5 or dp<=3): s="Focused"
        else: s="Fee Focus"
        if s=="Fee Focus" and r["epochs_voted"]<3: s="Occasional"  # too few votes to call mercenary
        return s
    drift=[r["rank"] for r in R if restyle(r)!=r["voting_style"]]
    check("stored voting_style matches its own metrics (no logic drift)", not drift, f"ranks {drift[:5]}")

print("\n== D. label-vs-behavior consistency (regression: NOCK / over-propagated partner) ==")
if R:
    TOK={"metacade":"mcade|metacademax","memento":"dextf","dextf":"dextf","betr":"betr","nockchain":"nock",
         "kvcm":"kvcm","f(x)":"fxusd","bankr":"bnkr","auki":"auki","venice":"vvv","reflect":"rfl"}
    bad=[]
    for r in R:
        who=r["likely_who"].lower(); dom=(r["dom_pool"] or "").lower()
        m=re.search(r"likely (\w[\w()/]*)", who)  # "likely <Partner>" claims
        if m and r["dom_pool"]:
            key=m.group(1).lower()
            pat=TOK.get(key)
            if pat and not re.search(pat,dom): bad.append((r["rank"],r["likely_who"],r["dom_pool"]))
    check("'likely <Partner>' labels match their dominant vote pool", not bad,
          f"inconsistent: {bad[:3]} (NOCK-class mislabel)")

print("\n== E. dashboard + security integrity ==")
try:
    enc=open("vehydx_dashboard.html").read()
    check("encrypted dashboard has the lock UI", "Enter passphrase to decrypt" in enc)
    check("ciphertext present (long CT base64 blob)", bool(re.search(r'CT="[A-Za-z0-9+/=]{2000,}"', enc)))
    check("passphrase NOT embedded in encrypted file", "veHYDXbreakdown" not in enc and "demo-pass" not in enc)
    idx=open("index.html").read()
    check("index.html == encrypted dashboard (root serves it)", idx==enc)
except FileNotFoundError as e:
    check("dashboard files present", False, str(e))
# git: ensure no plaintext data/dashboard is tracked
tracked=subprocess.run(["git","ls-files"],capture_output=True,text=True).stdout.split()
leak=[f for f in tracked if f.endswith((".csv",)) or f=="vehydx_dashboard_plain.html"
      or (f.endswith(".json") and f!="package.json")]
check("no plaintext data/dashboard committed (gitignore working)", not leak, f"LEAKED: {leak}")

print(f"\n{'='*56}\nQA: {PASSES} passed, {len(WARNS)} warned, {len(FAILS)} FAILED")
if FAILS:
    print("BLOCKED — do not publish:"); [print("  -",f) for f in FAILS]; sys.exit(1)
print("OK to publish." + (f"  (warnings: {WARNS})" if WARNS else ""))
