# attest — a verifiable human-writing ledger

Built at HackMIT 2026. `attest` records how a document was written as a **tamper-evident,
hash-chained event ledger**, binds that ledger to the exact submitted text, and issues a
portable **Proof-of-Writing certificate** anyone can verify offline. Later stages add
device- and hardware-rooted attestation (Secure Enclave, HID-level keystroke origin),
keystroke-timing forensics, stylometry reconciliation, and a zero-knowledge proof mode.

## Why

Integrity tools today either trust the client's word or demand full surveillance of a
student's keystrokes. `attest` makes the *evidence itself* unforgeable and separates two
questions that usually get conflated:

| Question | Answered by | Nature |
|---|---|---|
| Is this log authentic and unaltered, and did it produce exactly this text? | hash chain + replay + certificate | cryptographic |
| Did the input come from physical hardware, on this device, at this time? | Secure Enclave / WebAuthn signatures, HID attestation, RFC 3161 timestamps | cryptographic (Stages 3–4) |
| Does the *process* look like a human composing (vs. transcribing an AI)? | keystroke-timing signals + stylometry | statistical (Stages 2, 5) |

## Assurance levels

| Level | Meaning |
|---|---|
| **L0** | Ledger chain is internally valid |
| **L1** | + certificate binds the ledger to the submitted text (replay reproduces it) — *Stage 1* |
| **L2** | + chain heads signed by a device-bound key at checkpoints, trusted timestamp — *Stage 3* |
| **L3** | + keystrokes attested as hardware-originated by a Secure-Enclave-signed HID helper — *Stage 4* |

`unknown`/`could not check` always means *not verified*, never *clean*.

## How the ledger works (Stage 1)

Each edit becomes one event `{seq, ts, p, d, i, k, src, prev, hash}`:
`hash = SHA256(canon(event) || prev)`, with `genesis = SHA256(session_id:nonce)`.
The **browser computes every hash before sending**; the server re-derives each link and
refuses any batch that does not continue exactly from its recorded head (HTTP 409).
`replay(events)` reconstructs the document; a certificate is issued only if the replay
equals the submitted text byte-for-byte. Timestamps and positions are integers (code
points) so JavaScript and Python canonicalize identically.

The append-only invariant is checked by property-based tests
(`server/tests/test_chain.py`): for arbitrary edit sequences the built chain verifies and
replays, and *any* single-field mutation of *any* event breaks verification at that index.

## Layout

```
server/    FastAPI ledger service (Python 3.14)        verifier/  stdlib-only offline verifier CLI
web/       Vue 3 + Tiptap capture surface (port 9100)  tools/     adversary/demo scripts
native/    Swift HID + Secure Enclave helper (Stage 4) zk/        zkVM proof (Stage 6)
```

## Run locally

```bash
cd server && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn attest.main:app --port 8090 --reload
```
```bash
cd web && pnpm install && pnpm dev        # http://localhost:9100
```
```bash
cd server && .venv/bin/pytest -q
```

Offline verification of a downloaded certificate + ledger:
```bash
python3 verifier/attest_verify.py attest-cert.json essay.txt --events attest-ledger.json
```

## Third-party code (disclosure)

Everything in this directory was written during HackMIT 2026. Open-source dependencies:
FastAPI, Uvicorn, Pydantic, pydantic-settings, pytest, Hypothesis, httpx (server);
Vue 3, Vite, Tiptap v2 / ProseMirror (web). The offline verifier uses only the Python
standard library. Code under `../prior_work/` is pre-hackathon reference material and is
**not** used by this project.
