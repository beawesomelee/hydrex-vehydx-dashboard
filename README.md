# Hydrex veHYDX — Holder Intelligence Dashboard

Password-protected (client-side AES-256-GCM) dashboard of the top veHYDX voting-power
holders on Hydrex (Base): who controls emissions, what they typically vote for over the
last 10 epochs, likely identity, and a confidence score.

**Only `vehydx_dashboard.html` (encrypted) is committed.** The unencrypted dashboard and
all raw data are git-ignored — this repo is safe to make public; the data is ciphertext.

## Use
Open `vehydx_dashboard.html`, enter the passphrase, it decrypts in-browser. Host it on
GitHub Pages or open the file directly. No backend.

## Set / change the passphrase (do this before sharing)
```
python3 encrypt_dashboard.py "your-strong-passphrase"   # overwrites vehydx_dashboard.html
```
The passphrase is used only locally to encrypt; it is never stored (only ciphertext is).

## Refresh the data (weekly)
```
python3 build_facts.py        # top-100 wallets, current votes, contract/Safe facts (~5 min)
python3 build_history.py      # last-10-epoch vote history via archive RPC (~15 min)
python3 build_holdings_history.py  # last-10-epoch holdings: Δ column + area chart (~15 min)
python3 build_revote_history.py    # lastVoted analysis -> vote mode (set-forget/automated/active) (~2 min)
python3 synth.py              # votes-for (breadth) + vote mode + Δ -> vehydx_top100_labeled.csv
python3 build_dashboard.py    # render dashboard
python3 encrypt_dashboard.py "your-passphrase"   # re-seal
python3 qa.py                 # QA GATE — must pass (exit 0) before publishing
```
(Full holder scan, if rebuilding from scratch: `python3 runner.py`.)

## QA (run before every publish)
- **`qa.py`** — deterministic gate. 19 checks for data integrity, history sanity
  (catches silent-RPC-failure "idle walls"), classification correctness (Anchored really
  is concentrated; no style drift), label-vs-vote consistency (catches mislabels), and
  dashboard/security integrity (ciphertext present, passphrase absent, no plaintext data
  committed). Exits non-zero and blocks publish on any failure. Each check encodes a real
  bug we hit, so a weekly auto-refresh can't silently re-ship one.
- **QA agent** (optional, deeper) — adversarial LLM review of the labels/classifications
  for judgment-call errors (mislabels, mis-calibrated confidence, crackable unknowns).
  Run via the `vehydx-qa-agent` workflow over `vehydx_top100_labeled.json`.

## Data sources (on-chain, Base)
- veHYDX VotingEscrow `0x25b2ed7149fb8a05f6ef9407d9c8f878f59cd1e1` — `getVotes(addr)`, `balanceOfNFT(id)`
- Voter `0xc69e3ef39e3ffbce2a1c570f8d3adf76909ef17b` — `votes(account,pool)`, `weights(pool)`
- Archive RPC (mainnet.base.org / base.drpc.org) for per-epoch history; api.hydrex.fi/strategies for pool names

Internal BD intel — do not distribute.
