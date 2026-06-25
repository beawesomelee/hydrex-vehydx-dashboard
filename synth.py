import json, csv
from collections import Counter
F=json.load(open("top100_facts.json"))["facts"]
H=json.load(open("top100_history.json"))
prior={p["wallet"].lower():p for p in json.load(open("vehydx_labels.json"))}

def partner_of(name):
    n=name.lower()
    for tok,proj in [("metacademax","Metacade"),("mcade","Metacade"),("theo","Autheo"),
        ("betr","Betr"),("nock","Nockchain"),("fxusd","f(x) Protocol"),("dextf","Memento/DEXTF"),
        ("lfi","LFI"),("bnkr","Bankr"),("wtsgov","wtSGOV/RWA"),("wtcoin","wtCOIN/RWA"),("wtmstr","wtMSTR/RWA"),
        ("eurc","Circle EURC"),("auki","Auki"),("degen","Degen"),("fuego","Fuego"),("40a","40 Acres"),
        ("vvv","Venice"),("rfl","Reflect"),("kvcm","kVCM")]:
        if tok in n: return proj
    return None

# codehash clusters seeded by prior agent labels (one ID extends to identical contracts)
ch2type=Counter(); ch_examples={}
for f in F:
    pl=prior.get(f["wallet"].lower())
    if pl and f["codehash"]!="EOA":
        ch2type[(f["codehash"],pl["entity_type"])]+=1
        ch_examples.setdefault(f["codehash"],pl["label"])
cluster_label={}
for (ch,et),_ in ch2type.most_common():
    cluster_label.setdefault(ch,(et,ch_examples.get(ch,"")))

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
    Loyal     = top vote hits the SAME pool in >=80% of voted epochs (clear allegiance)
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
    if avg_n<=3 and dom_share>=0.7: style="Loyal"          # ~one pool, same one each epoch
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
    return lbl[:34]

rows=[]
for f in F:
    w=f["wallet"]; pl=prior.get(w.lower())
    beh, mode, consistency = behavior(w)
    partner = partner_of(mode) if (mode and consistency>=0.6) else None
    # --- owner identity (priority) ---
    who="unknown"; et="unknown"; conf="low"
    if f.get("treasury_signer_match"):
        who="Hydrex team/treasury Safe"; et="hydrex_treasury_or_team"; conf="high"
    elif f["codehash"] in cluster_label:
        et,lbl=cluster_label[f["codehash"]]
        if et=="individual_whale": who="individual (smart wallet)"; conf="low"  # cluster = wallet TYPE, not a partner
        else: who=short(lbl); conf="medium"  # codehash-only (admin not re-verified) => medium, not high
    if pl and pl["confidence"] in ("high","medium"):
        who=short(pl["label"]); et=pl["entity_type"]; conf=pl["confidence"]
    # --- partner inference: set identity only for genuinely-unknown owners; else annotate with own votes ---
    if partner:
        pcore=partner.split('/')[0].lower()
        if et=="unknown":
            who=f"likely {partner}"; et="partner_project"; conf="high" if consistency>=0.8 else "medium"
        elif et in ("partner_project","alm_vault","individual_whale") and pcore not in who.lower():
            who=f"{who} → votes {partner}"
    rows.append({**f,"likely_who":who,"entity_type":et,"confidence":conf,"behavior_10ep":beh,**vote_profile(w)})

rows.sort(key=lambda r:r["rank"])
with open("vehydx_top100_labeled.csv","w",newline="") as fp:
    wr=csv.writer(fp); wr.writerow(["rank","wallet","vehydx","pct","type","entity_type","confidence","likely_who","voting_style","epochs_voted","dom_pool","dom_share","distinct_pools","avg_pools_per_epoch","behavior_last_10_epochs","current_top_votes"])
    for r in rows:
        ct=", ".join(f"{p} {pc}%" for p,pc in r["cur_targets"])
        wr.writerow([r["rank"],r["wallet"],f"{r['vehydx']:.0f}",r["pct"],r["type"],r["entity_type"],r["confidence"],r["likely_who"],r["voting_style"],f"{r['epochs_voted']}/{r['epochs_total']}",r["dom_pool"] or "",r["dom_share"],r["distinct_pools"],r["avg_pools_per_epoch"],r["behavior_10ep"],ct])
json.dump(rows,open("vehydx_top100_labeled.json","w"),indent=1)
print(f"{'#':>3} {'veHYDX':>6} {'style':<10} {'ep':>5} {'dom%':>5} {'likely who':<30} dom pool")
for r in rows:
    print(f"{r['rank']:>3} {r['vehydx']/1e6:>4.2f}M {r['voting_style']:<10} {str(r['epochs_voted'])+'/'+str(r['epochs_total']):>5} {int(r['dom_share']*100):>4}% {r['likely_who'][:29]:<30} {r['dom_pool'] or '—'}")
print("\nentity tally:",dict(Counter(r["entity_type"] for r in rows)))
print("VOTING STYLE tally:",dict(Counter(r["voting_style"] for r in rows)))
print("wrote vehydx_top100_labeled.csv")
