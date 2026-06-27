# Hydrex veHYDX — Holder Intelligence Dashboard

Public dashboard of the top veHYDX voting-power holders on Hydrex (Base): who controls
emissions, what they vote for over the last 10 epochs, how they vote (set-and-forget vs
active re-voter), protocol earning-power and staker growth over time.

**`index.html` (plaintext) is the published file** — served at the GitHub Pages root, no
password. All raw data files (`*.json`, `*.csv`) are git-ignored and never committed; only
the rendered HTML + the build scripts are tracked. The page intentionally exposes the
public, on-chain-derived columns only — `build_dashboard.py` projects each row down to the
fields the UI renders and never embeds the internal attribution dossier (`likely_who`,
`safe_owners`, `confidence`, `entity_type`, `codehash`, …). `qa.py` enforces that.

## Use
Open `index.html` (or the GitHub Pages URL). No passphrase, no backend.
(`encrypt_dashboard.py` remains for an optional AES-gated build but is not part of the
public publish flow.)

## Refresh the data (weekly)
```
python3 build_facts.py             # top-100 wallets, current votes, contract/Safe facts (~5 min)
python3 build_history.py           # last-10-epoch vote history via archive RPC (~15 min)
python3 build_holdings_history.py  # last-10-epoch holdings: Δ column + area chart (~15 min)
python3 build_revote_history.py    # lastVoted analysis -> vote mode (set-and-forget/active/never) (~2 min)
python3 build_staker_history.py    # staker count + on-chain veHYDX per epoch, full history (~8 min)
python3 build_earning_power.py     # total earning power per epoch from api.hydrex.fi/epochs (matches frontend)
python3 build_automation.py        # Manual vs Automated per wallet (isApprovedForAll to the automation manager)
python3 synth.py                   # votes-for (breadth) + vote mode + Δ -> vehydx_top100_labeled.json
python3 build_dashboard.py         # render -> vehydx_dashboard_plain.html
cp vehydx_dashboard_plain.html index.html   # publish the plaintext root
python3 qa.py                      # QA GATE — must pass (exit 0) before publishing
```
(Full holder scan, if rebuilding from scratch: `python3 runner.py`.)

Headline constants (TOTAL voting power, holder count, treasury %) are derived from
`owner_power.json` / `staker_history.json` at build time, so they auto-update each refresh.

## QA (run before every publish)
- **`qa.py`** — deterministic gate (27 checks): data integrity, history sanity (catches
  silent-RPC-failure "idle walls"), classification correctness (Anchored = same pool ≥80%
  of epochs; no style drift), label-vs-vote consistency, holdings sanity, and public-page
  integrity (no password gate, **no attribution/dossier fields leaked**, no raw data
  committed). Exits non-zero and blocks publish on any failure.
- **`vehydx-dashboard-qa` workflow** (optional, deeper) — adversarial multi-agent audit that
  re-derives every number from on-chain + the Hydrex API and verifies each finding.

## Data sources (on-chain, Base 8453)
- veHYDX VotingEscrow `0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1` — `getVotes(addr)`, `balanceOfNFT(id)`, `totalSupply()`
- Voter `0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b` — `votes(account,pool)`, `lastVoted(addr)`, `weights(pool)`
- Archive RPC (mainnet.base.org / base.drpc.org) for per-epoch history
- `api.hydrex.fi/epochs` — `power.effectiveEarningPower` (frontend's Total Earning Power); `api.hydrex.fi/strategies` for pool names
