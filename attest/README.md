# attest — a verifiable human-writing ledger

`attest` records how a document was written as a **tamper-evident,
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
| **L2** | + the final chain head signed by a key that cannot leave the student's device (Secure Enclave / WebAuthn), with RFC 3161 trusted timestamps at checkpoints — *Stage 3, built* |
| **L3** | + a hardware witness below the browser saw a physical key-down for every keystroke the editor recorded — *Stage 4, built; labelled "software witness", see below* |

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

## Provenance and process signals (Stage 2)

A piece table (`server/attest/provenance.py`) replays the ledger and labels every span of
the current text **T** (typed), **INT** (pasted text copied from this document within 30 s —
re-derived from `copy` events in the ledger, never from the client's hint) or **EXT**
(pasted from outside). On top of that, pluggable signals in `server/attest/signals/` read
the *process*, each returning `genuine | review | suspicious | insufficient_data`:

| Signal | What it measures |
|---|---|
| `inter_key_interval` | Keystroke rhythm variability — humans are irregular; scripts are uniform or superhuman |
| `typed_speed` | Typed-only WPM in 10 s windows (pastes excluded) — catches "typed" text that arrived too fast |
| `transcription_cadence` | Whether pauses land at word/clause boundaries (composing) or mid-word in steady chunks (copying from a second screen) |
| `revision_effort` | Keystrokes + deletions per final character — rework leaves fingerprints |
| `edit_locality` | Share of edits that revisit earlier text vs. strictly append-only writing |

Timing comes from content-free `kd`/`ku` events (a key went down/up — no key identity),
falling back to edit timestamps. `scoring.py` aggregates with innocence-protecting gates:
`suspicious` needs at least two weighted votes, three unmeasured signals force `review`,
and warnings are phrased neutrally. Results ride along on every `/v1/ingest` response and
are embedded in the certificate's `claims.integrity`. Set `ATTEST_STORE=sqlite` to persist
sessions across restarts.

## Device binding and trusted time (Stage 3 — L2)

L1 proves the ledger is internally consistent and produces the text; it cannot tell a real
session from a script that emitted realistic-looking JSON. L2 reaches outside the JSON with two
signatures over the **same chain head**:

| Signer | Proves | How |
|---|---|---|
| Device key (WebAuthn platform authenticator — the Mac's Secure Enclave) | *which machine*, and at the seal *that the enrolled person was present* (Touch ID) | `navigator.credentials.get` with the chain head as challenge; ECDSA-P256 over `authenticatorData ‖ SHA256(clientDataJSON)` |
| Timestamp authority (RFC 3161, FreeTSA by default) | *no later than when* — by a clock the student does not control | server POSTs the head to the TSA, verifies the CMS signature against a pinned signer certificate, stores the token |

Flow: enroll once (`/enroll/options` → Touch ID → `/enroll` stores the public key under the
owner — a user in the classroom, the session in the demo) · every ~3 min the browser signs the
current head **silently** (`userVerification: discouraged`) · at submit it signs the final head
**with Touch ID** (`required`) · `build_certificate` verifies every attestation over its own head,
insists the head is a real state of *this* ledger, and raises the level to L2 **only** for a
verified device signature over the final chain root. Timestamps enrich but never raise the level
(they prove *when*, not *who*). Intermediate signatures are reported as checkpoints.

Everything needed to verify is embedded in the certificate (`attestations[]` with the public
key, the TSA token), and the verification code is standard-library only — a hand-written ECDSA
(P-256/P-384), DER, CBOR and RSA-PKCS1 in `server/attest/crypto/` — so
`verifier/attest_verify.py` checks L2 offline with no packages installed:

```
[PASS] webauthn[0]      final 775b07b77241… — device signature over head … (user verified)
[PASS] timestamp[1]     final 775b07b77241… — FreeTSA (freetsa.org) at 2026-09-19T22:52:32Z
[PASS] assurance_level  attestations support L2
```

A certificate that *claims* L2 without a verifiable signature over its root fails
`assurance_level`; swapping the embedded key or flipping a signature bit fails `webauthn[n]`.
Tests drive the whole path with a software authenticator (`tests/fake_authenticator.py`) and a
captured real FreeTSA token (`tests/fixtures/`). Settings: `ATTEST_WEBAUTHN_RP_ID`,
`ATTEST_WEBAUTHN_ORIGINS`, `ATTEST_TSA_URL` (empty disables), `ATTEST_TSA_TRUSTED_FINGERPRINTS`.

What L2 does **not** prove: that the keystrokes were physical (a script driving the editor on the
student's own Mac still passes — that is L3), or that the words are the student's own (signals,
stylometry).

## The issuer seal

Everything above is self-consistent by construction — a student running their own copy of this
server could mint a certificate whose chain, replay and device signature all check against the
keys *inside the file*. So the server signs every certificate it issues with its own P-256 key
(`issuer: {alg, key_id, public_key, signature}`, over the canonical certificate). The public half
is at `GET /v1/issuer`; the key file lives next to the database (`ATTEST_ISSUER_KEY_PATH`). The
server's own verify and the teacher's review page fail `issuer` for anything not signed by this
key; the offline CLI does the same with `--issuer-key <hex|file>` and otherwise reports the seal
as self-consistent only.

## The hardware witness (Stage 4 — L3)

L2 still cannot tell a finger on a key from `dispatchEvent`, an AppleScript `keystroke`, or a
macro tool. `native/attest-hid` is a small Swift helper that listens to raw HID reports via
IOHIDManager — below the browser, where synthetic events never appear — and every 5 s emits a
signed, hash-chained statement: *"between t₀ and t₁ I saw N physical key-downs from these devices;
the machine had been idle for I ms."* Statements are signed by a Secure Enclave key enrolled under
the student's account, anchored to a real ledger head at the start of each segment and to the
final chain root at the seal, and relayed by the browser (the helper is passive: no tokens, no
outbound connections). It never records *which* keys.

At seal the server lines the two streams up window by window. Hardware may see **more**
key-downs than the editor (shortcuts, other apps) but never **fewer**; a window where the editor
recorded ≥ 8 keystrokes and the hardware saw fewer than half is an *injection window*. Text that
arrived in a single `type` event without key events (`insertText`, dictation, a macro) counts as
one keystroke-equivalent per extra character, so it too must be matched by hardware.

```
L3  =  L2  +  gapless witness chain anchored to this ledger at both ends
           +  every ledger keystroke inside a witnessed window
           +  no injection window
```

Otherwise the certificate stays at **L2 and says why** (`claims.attestation.hid.reasons`), the
review page shows the offending window, and playback paints a red band over it. External
keyboards are reported (`devices: […]`) but not penalised.

**Why "software witness".** The signatures prove the statements are unaltered and from this Mac's
Enclave; the anchors prove they are about this ledger. What nothing can prove on macOS is that the
program writing them is *our* helper — Apple's App Attest exists only for iOS/App Store apps, and
the Mac App Store sandbox forbids Input Monitoring. A student could write a fake helper that
emits counts matching their injection script. Mitigations: ad-hoc/Developer-ID signing, the
helper's own code hash in every statement pinned server-side (`ATTEST_HID_TRUSTED_CDHASHES`), and
the enrolment binding to an authenticated, L2-verified session. Net: cheating past L3 means custom
native software, run unsigned on your own Mac, coordinated live with an injection script — a
material bar above the one-line attacks, but not L2's "the OS itself signs". Full design and
trust analysis: `docs/L3-hardware-witness.md`.

## The classroom around the engine (`server/classroom/`, `web/src/pages/`)

A sparse teaching platform built *around* attest, in the same server and SQLite file:

- **Roles**: students and teachers (email + password; stdlib scrypt, hashed bearer tokens).
- **Classes & assignments**: 6-letter join codes, assignments with per-check settings.
- **Attested writing**: the student's editor is bound to one ledger session per submission
  (`doc_id = submission_id`, `owner = user_id`). Engine routes for bound sessions are guarded
  (owner writes, teacher reads, only the owner enrolls keys or signs heads); the public engine
  demo at `/attest` stays open. A device key enrolled once serves all of a student's assignments.
- **Submit = the hard guarantee**: the server rebuilds the certificate from *its own* ledger copy
  and refuses unless it replays to exactly the submitted text (`409 not_bound | wrong_session |
  hash_mismatch`). No client claim is stored.
- **Review**: highlighted external spans, server re-verification, ledger download, process
  signals, grade + return, and **session playback** built from the ledger alone.
- **Citations & links**: DOIs resolved via doi.org's registration-agency lookup then Crossref or
  DataCite for metadata; URL reachability; author-year cites paired with the reference list and
  reported as *unverifiable*, never *fabricated*.
- **In-class similarity**: winnowing fingerprints (5-word grams, window 4, crc32), prompt text
  excluded, matched passages recovered on both sides and mirrored across submissions.

```bash
cd server && .venv/bin/uvicorn classroom.app:app --port 8090 --reload   # API + engine
cd web && pnpm dev                                                       # http://localhost:9100
cd server && .venv/bin/python -m classroom.seed                          # demo accounts + Ben's essay
```

## Layout

```
server/    FastAPI ledger service (Python 3.14)        verifier/  stdlib-only offline verifier CLI
web/       Vue 3 + Tiptap capture surface (port 9100)  docs/      design notes (L3 plan)
native/    attest-hid: Swift HID witness + Secure Enclave key (Stage 4, L3)
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
cd server && .venv/bin/pytest -q                  # 126 tests
cd server && .venv/bin/python walkthrough.py      # narrated end-to-end run of every feature (add --live-tsa for a real timestamp)
```

Offline verification of a downloaded certificate + ledger:
```bash
python3 verifier/attest_verify.py attest-cert.json essay.txt --events attest-ledger.json
```

## Third-party code (disclosure)

Everything in this directory was written during HackMIT 2026. Open-source dependencies:
FastAPI, Uvicorn, Pydantic, pydantic-settings, pytest, Hypothesis, httpx (server);
Vue 3, Vite, Tiptap v2 / ProseMirror (web); `cryptography` is used **only in tests** as a
reference implementation to cross-check the hand-written ECDSA. The native helper uses Apple
frameworks only (IOKit, Security, Network, CryptoKit). The offline verifier and all
attestation verification use only the Python standard library. FreeTSA (freetsa.org) is a
public timestamp service, not code. Code under `../prior_work/` is pre-hackathon reference material and is
**not** used by this project.
