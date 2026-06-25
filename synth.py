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
    rows.append({**f,"likely_who":who,"entity_type":et,"confidence":conf,"behavior_10ep":beh})

rows.sort(key=lambda r:r["rank"])
with open("vehydx_top100_labeled.csv","w",newline="") as fp:
    wr=csv.writer(fp); wr.writerow(["rank","wallet","vehydx","pct","type","entity_type","confidence","likely_who","behavior_last_10_epochs","current_top_votes"])
    for r in rows:
        ct=", ".join(f"{p} {pc}%" for p,pc in r["cur_targets"])
        wr.writerow([r["rank"],r["wallet"],f"{r['vehydx']:.0f}",r["pct"],r["type"],r["entity_type"],r["confidence"],r["likely_who"],r["behavior_10ep"],ct])
json.dump(rows,open("vehydx_top100_labeled.json","w"),indent=1)
print(f"{'#':>3} {'veHYDX':>6}{'%':>5} {'conf':<4} {'likely who':<34} behavior(10ep)")
for r in rows:
    print(f"{r['rank']:>3} {r['vehydx']/1e6:>4.2f}M{r['pct']:>5.2f} {r['confidence']:<4} {r['likely_who'][:33]:<34} {r['behavior_10ep'][:40]}")
print("\nentity tally:",dict(Counter(r["entity_type"] for r in rows)))
print("active-vote tally:", sum(1 for r in rows if "idle (never" not in r["behavior_10ep"]),"/100 voted in last 10ep")
print("wrote vehydx_top100_labeled.csv")
