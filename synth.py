import json, csv
from collections import Counter, defaultdict
F=json.load(open("top100_facts.json"))["facts"]
H=json.load(open("top100_history.json"))
prior={p["wallet"].lower():p for p in json.load(open("vehydx_labels.json"))}
# Hydrex treasury multisig signers — a wallet that IS one of these (EOA) is team too
TREAS={"0xea1bf482b7d3526ccf37a8a3fee330c960877f08","0x813f98f0f29509d558b2479d8ee0c8068c160bd3","0xb4d2861d525aef313be0c497c3335a58f637e73e"}

def partner_of(name):
    n=name.lower()
    for tok,proj in [("metacademax","Metacade"),("mcade","Metacade"),("theo","Autheo"),
        ("betr","Betr"),("nock","Nockchain"),("fxusd","f(x) Protocol"),("dextf","Memento/DEXTF"),
        ("lfi","LFI"),("bnkr","Bankr"),("clanker","Clanker"),("wtsgov","wtSGOV/RWA"),("wtcoin","wtCOIN/RWA"),
        ("wtmstr","wtMSTR/RWA"),("eurc","Circle EURC"),("auki","Auki"),("degen","Degen"),("fuego","Fuego"),
        ("40a","40 Acres"),("vvv","Venice"),("rfl","Reflect"),("kvcm","kVCM"),
        ("azusd","Azos Finance"),("tgn","Treegens"),("regen","Regen Network"),("tibbir","Ribbita/TIBBIR")]:
        if tok in n: return proj
    return None

# Codehash clusters seeded by prior agent labels. A codehash with MIXED seed types
# (e.g. 0x8203 = team manager + PartnerEscrow + 40 Acres vault) is a GENERIC managed-lock
# template that does NOT prove ownership — never propagate a specific identity from it.
ch_types=defaultdict(set); ch_first_label={}
for f in F:
    pl=prior.get(f["wallet"].lower())
    if pl and f["codehash"]!="EOA":
        ch_types[f["codehash"]].add(pl["entity_type"]); ch_first_label.setdefault(f["codehash"],pl["label"])
cluster_label={}
for ch,types in ch_types.items():
    cluster_label[ch]=("managed_lock","Hydrex managed-lock (owner unverified)") if len(types)>1 \
                      else (next(iter(types)), ch_first_label[ch])

def behavior(w):
    h=H.get(w,{})
    eps=sorted(int(k) for k in h.keys())
    active=[e for e in eps if h[str(e)].get("voted")]
    if not active: return "idle (never voted, last 10 ep)", None, 0
    tops=[h[str(e)]["top"][0][0] for e in active if h[str(e)].get("top")]
    if not tops: return "voted (target unresolved)", None, 0
    mode,cnt=Counter(tops).most_common(1)[0]
    consistency=cnt/len(active); first=min(active)
    s=f"{mode} {cnt}/{len(active)}ep"
    if len(active)<len(eps): s+=f"; idle {len(eps)-len(active)}"
    if first>31: s+=f"; since ep{first}"
    return s, mode, consistency

def vote_profile(w):
    """Classify voting behavior over the last 10 epochs.
    Anchored     = top vote hits the SAME pool in >=80% of voted epochs (clear allegiance)
    Focused   = one main pool (dom 50-80%) OR <=3 distinct top pools
    Fee Focus = spreads across 4+ pools with no dominant one (mercenary, chasing fees+bribes)
    Idle      = never voted"""
    h=H.get(w,{})
    eps=sorted(int(k) for k in h.keys()); total=len(eps)
    active=[e for e in eps if h[str(e)].get("voted")]
    tops=[h[str(e)]["top"][0][0] for e in active if h[str(e)].get("top")]
    ns=[h[str(e)].get("n",1) for e in active]
    if not tops:
        return {"epochs_voted":len(active),"epochs_total":total,"voting_style":"Idle",
                "dom_pool":None,"dom_share":0.0,"distinct_pools":0,"avg_pools_per_epoch":0.0}
    dom_pool,dom=Counter(tops).most_common(1)[0]
    dom_share=dom/len(tops); distinct=len(set(tops)); avg_n=sum(ns)/len(ns)
    # style needs BOTH within-epoch concentration (avg pools/epoch) AND cross-epoch consistency
    if avg_n<=3 and dom_share>=0.8: style="Anchored"          # ~one pool, same one >=80% of epochs (matches legend)
    elif avg_n<=6 and (dom_share>=0.5 or distinct<=3): style="Focused"  # a few pools, clear lean
    else: style="Fee Focus"                                 # sprays 4+/epoch or rotates -> mercenary
    return {"epochs_voted":len(active),"epochs_total":total,"voting_style":style,
            "dom_pool":dom_pool,"dom_share":round(dom_share,2),"distinct_pools":distinct,
            "avg_pools_per_epoch":round(avg_n,1)}

def short(lbl):
    # condense verbose prior labels into a tag
    l=lbl.lower()
    if "treasury" in l or "team" in l: return "Hydrex team/treasury"
    if "voting manager" in l or "voting-manager" in l: return "Hydrex voting-manager (team)"
    if "partnerescrow" in l or "partner-locker" in l or "partner escrow" in l: return "Hydrex PartnerEscrow"
    if "40 acres" in l: return "40 Acres vault"
    if "coinbase smart wallet" in l: return "individual (CB Smart Wallet)"
    if ".eth" in l or ".base" in l: return lbl.split(" ")[0]
    if "metacade" in l: return "Metacade-aligned"
    if "memento" in l or "dextf" in l: return "Memento/DEXTF"
    if "managed-lock" in l or "managed lock" in l: return "Hydrex managed-lock (unverified)"
    if "smart-contract voter" in l or "spread votes" in l: return "unknown contract (spreader)"
    if "individual" in l: return "individual (smart wallet)"
    return lbl[:40].rstrip()

rows=[]
for f in F:
    w=f["wallet"]; pl=prior.get(w.lower()); prof=vote_profile(w)
    beh, mode, consistency = behavior(w)
    partner = partner_of(mode) if (mode and consistency>=0.6) else None
    loyal_partner = partner_of(mode) if (mode and prof["voting_style"] in ("Anchored","Focused")) else None
    # --- owner identity (priority) ---
    who="unknown"; et="unknown"; conf="low"
    if f.get("treasury_signer_match") or w.lower() in TREAS:
        who="Hydrex team/treasury (signer-verified)"; et="hydrex_treasury_or_team"; conf="high"
    elif f["codehash"] in cluster_label:
        cet,lbl=cluster_label[f["codehash"]]
        if cet=="individual_whale": who="individual (smart wallet)"; et="individual_whale"; conf="low"
        elif cet in ("managed_lock","hydrex_treasury_or_team"):  # codehash alone never proves team ownership
            who="Hydrex managed-lock (unverified)"; et="managed_lock"; conf="low"
        else: who=short(lbl); et=cet; conf="medium"
    if pl and pl["confidence"] in ("high","medium"):
        who=short(pl["label"]); et=pl["entity_type"]; conf=pl["confidence"]
    # --- partner inference: a Anchored single-pool voter for a partner pool IS that project ---
    if et in ("unknown","managed_lock") and loyal_partner:
        who=f"likely {loyal_partner}"; et="partner_project"; conf="high" if prof["voting_style"]=="Anchored" else "medium"
    elif partner and et in ("partner_project","alm_vault","individual_whale") and partner.split('/')[0].lower() not in who.lower():
        who=f"{who} → votes {partner}"
    # --- QA calibration: never assert "team" without signer evidence (admin not checkable here) ---
    if et=="hydrex_treasury_or_team" and not (f.get("treasury_signer_match") or w.lower() in TREAS):
        who="Hydrex managed-lock (unverified)"; et="managed_lock"; conf="low"
    # --- fix entity contradiction: a PartnerEscrow contract is not an "individual" ---
    if "partnerescrow" in who.lower() and et=="individual_whale": et="partner_project"
    rows.append({**f,"likely_who":who,"entity_type":et,"confidence":conf,"behavior_10ep":beh,**prof})

rows.sort(key=lambda r:r["rank"])
# attach historical holdings series + epoch-over-epoch delta (Dune-style)
try:
    HOLD=json.load(open("top100_holdings.json"))
    for r in rows:
        h=HOLD.get(r["wallet"],{}); eps=sorted(int(k) for k in h.keys())
        r["holdings"]={str(e):h[str(e)] for e in eps}
        if len(eps)>=2:
            cur,prev=h[str(eps[-1])],h[str(eps[-2])]
            r["delta_last"]=round(cur-prev,2); r["delta_pct"]=round((cur-prev)/prev*100,3) if prev>0 else None
        else: r["delta_last"]=None; r["delta_pct"]=None
except FileNotFoundError:
    for r in rows: r["holdings"]={}; r["delta_last"]=None; r["delta_pct"]=None
# attach re-vote MODE (set-and-forget / automated / active / never) from lastVoted analysis
try:
    RV=json.load(open("top100_revote.json"))
    for r in rows:
        m=RV.get(r["wallet"],{})
        vm=m.get("mode","—"); r["vote_mode"]="Active" if vm=="Automated" else vm
        r["last_vote"]=m.get("last_vote"); r["n_revotes"]=m.get("n_revotes",0)
except FileNotFoundError:
    for r in rows: r["vote_mode"]="—"; r["tod_R"]=None; r["last_vote"]=None; r["n_revotes"]=0
with open("vehydx_top100_labeled.csv","w",newline="") as fp:
    wr=csv.writer(fp); wr.writerow(["rank","wallet","vehydx","pct","delta_last_epoch","vote_breadth","vote_mode","dom_pool","avg_pools_per_epoch","last_vote_utc","n_revotes","type","entity_type","confidence","likely_who","behavior_last_10_epochs","current_top_votes"])
    import datetime as _dt
    for r in rows:
        ct=", ".join(f"{p} {pc}%" for p,pc in r["cur_targets"])
        lv=_dt.datetime.utcfromtimestamp(r["last_vote"]).strftime("%Y-%m-%d %H:%M") if r.get("last_vote") else ""
        wr.writerow([r["rank"],r["wallet"],f"{r['vehydx']:.0f}",r["pct"],r.get("delta_last") if r.get("delta_last") is not None else "",r["voting_style"],r.get("vote_mode","—"),r["dom_pool"] or "",r["avg_pools_per_epoch"],lv,r.get("n_revotes",0),r["type"],r["entity_type"],r["confidence"],r["likely_who"],r["behavior_10ep"],ct])
json.dump(rows,open("vehydx_top100_labeled.json","w"),indent=1)
print(f"{'#':>3} {'veHYDX':>6} {'style':<10} {'ep':>5} {'dom%':>5} {'likely who':<30} dom pool")
for r in rows:
    print(f"{r['rank']:>3} {r['vehydx']/1e6:>4.2f}M {r['voting_style']:<10} {str(r['epochs_voted'])+'/'+str(r['epochs_total']):>5} {int(r['dom_share']*100):>4}% {r['likely_who'][:29]:<30} {r['dom_pool'] or '—'}")
print("\nentity tally:",dict(Counter(r["entity_type"] for r in rows)))
print("VOTING STYLE tally:",dict(Counter(r["voting_style"] for r in rows)))
print("wrote vehydx_top100_labeled.csv")
