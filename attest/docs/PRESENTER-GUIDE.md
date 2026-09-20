# attest — presenter's guide

*Everything in this repository, beginning to end, in the order you'd explain it. Built at HackMIT 2026.*

---

## 1. The one-sentence pitch

**attest turns "I wrote this" into evidence: a tamper-proof record of how a document was written, bound to the exact text, sealed by the student's own device, and checkable by anyone offline — without recording what they typed.**

The problem it answers: AI detectors guess from the finished text and get it wrong both ways. Surveillance tools (webcams, screen recording) invade privacy and still can't tell a student from a script. attest changes the question from *"does this text look human?"* to *"can this student prove how it came to exist?"* — and makes the proof something a teacher can check, not something they have to trust.

---

## 2. What's in the repository

```
attest/
  server/attest/       the engine: ledger, chain, replay, certificate, attestation, crypto   (Python, FastAPI)
  server/classroom/    the product around it: accounts, classes, submissions, review, citations, similarity
  server/tests/        127 tests, including a software Touch ID and a software hardware witness
  server/walkthrough.py  narrated end-to-end run of every feature
  web/                 Vue 3 + Tiptap editor, ledger panel, student & teacher pages           (JavaScript)
  native/attest-hid/   the hardware witness: Swift, IOHIDManager, Secure Enclave
  verifier/            attest_verify.py — offline verifier, Python standard library only
  docs/                L3 design plan, this guide
  dev.sh               one command to run the whole stack
```

Two things to say out loud: every line here was written during the hackathon; and the only third-party code is the frameworks (FastAPI, Vue, Tiptap, Pydantic) — the cryptography that *verifies* anything is hand-written standard-library Python so the verifier can be audited and run with nothing installed.

---

## 3. The engine — how a writing session becomes evidence

### 3.1 The ledger (`web/src/extensions/capture.js`, `lib/chain.js`, `lib/sync.js`)

The editor is Tiptap (ProseMirror). Every transaction is diffed against the previous text and becomes one **event**:

```
{ seq, ts, p, d, i, k, src, prev, hash }
  seq  position in the ledger          k   type | paste | ckpt | copy | kd | ku
  ts   ms timestamp                     src paste hint from the client (recorded, never trusted)
  p    code-point position              prev hash of the previous event
  d    code points deleted              hash SHA-256(canonical event || prev)
  i    text inserted
```

`kd`/`ku` are **content-free**: a key went down or up, no key identity. They exist so timing can be analysed without keylogging. `copy` records what was copied so the server can later decide for itself whether a paste was internal.

**The chain.** Each event's hash covers the previous event's hash, so the events form a chain from a `genesis = SHA256(session_id : server_nonce)`. Change any byte of any event and every hash after it is wrong. The **browser** computes the hashes before sending; the server recomputes every one and refuses a batch that doesn't continue exactly from its stored head (`409 chain_break`). That blocks replays, gaps, reordering, edits, forks, and two tabs writing the same session.

Batches ship every 5 s / 50 events / on blur. The server (`routers/ingest.py`) verifies the chain, then **replays** the whole ledger and compares to the hash of the text the browser says it has (`replay_ok`) — so client and server can't silently drift.

### 3.2 Replay (`attest/replay.py`)

Ten lines: `text[:p] + i + text[p+d:]` per event, `ckpt` resets. Deterministic, code-point based, identical in Python and JavaScript. Its job is not to produce text you already have — it's to **check** that the ledger produces exactly the submitted text. Without it, a ledger is a diary; with it, the ledger is a complete account of *this* document: every character explained by an event, every event contributing.

### 3.3 The certificate (`attest/certificate.py`)

`finalize` issues a **Proof-of-Writing certificate** only if the chain verifies *and* `replay(events) == final_text`:

```
doc_sha256    hash of the text                  → "which document"
chain_root    hash of the last event            → "which history" (timestamps included)
merkle_root   Merkle root over all event hashes → same, provable per event
event_count, genesis, created_ms
assurance_level  L0 | L1 | L2 | L3
claims.integrity  provenance mix + process signals
attestations[]    device signatures, timestamps, witness statements
issuer            the server's seal (§7)
```

After finalize the session is frozen: the client stops recording, the server refuses ingest. Edit the text and verify → `doc_sha256 FAIL`; undo → PASS. The certificate is a snapshot of the history at the seal, not a live dashboard.

### 3.4 The assurance ladder

| Level | Adds | Signed by |
|---|---|---|
| **L0** | ledger internally valid | hash chain |
| **L1** | …and it produces exactly this text | replay |
| **L2** | …on *this* device, sealed by the enrolled person, by *this* time | Secure Enclave + timestamp authority |
| **L3** | …and every keystroke was a physical key press | hardware witness |

A level is only ever raised by something the **server verified**; a client claiming a level changes nothing (`attestors/base.py: compute_assurance_level`). `unknown` always means *not verified*, never *clean*.

---

## 4. The statistical layer — provenance and process signals

Cryptography says whether the record is authentic. It cannot say whether a human composed the words. That's the second, clearly separated layer.

**Provenance** (`attest/provenance.py`): a piece table replays the ledger and labels every span **T** (typed), **INT** (pasted text that matches a `copy` event from this document within 30 s), or **EXT** (pasted from outside). The client's `src` hint is ignored; internal-ness is re-derived from the chain. Output: the mix bar (typed/internal/external %) and the red-highlighted spans on the review page.

**Signals** (`attest/signals/`): five plugin functions over a shared `SessionContext`, each returning `genuine | review | suspicious | insufficient_data`:

| Signal | Measures | Catches |
|---|---|---|
| `inter_key_interval` | rhythm variability (CV of gaps; needs ≥30) | metronomic or superhuman input |
| `typed_speed` | typed-only WPM in 10 s windows | "typed" text that arrived at machine speed |
| `transcription_cadence` | do pauses land at word boundaries or mid-word in steady chunks? | copying from a second screen |
| `revision_effort` | (typed + deleted) / final chars | pasted or transcribed text has no rework |
| `edit_locality` | share of edits that revisit earlier text | strictly append-only writing |

`scoring.py` aggregates with **innocence-protecting gates**: `suspicious` needs two weighted votes; three unmeasured signals force `review`; labels are neutral. This layer never says "cheated" — it says "review", and the teacher judges.

---

## 5. L2 — the device and the clock

**Problem:** everything so far arrived as JSON. A script can emit a perfect ledger. L2 reaches outside the JSON with two signatures over the **same chain head**.

**Device key** (`attestors/webauthn.py`, `web/src/lib/webauthn.js`). WebAuthn — the browser API behind "sign in with Touch ID". Enrollment creates a P-256 key in the Mac's Secure Enclave; the private half cannot leave the chip. At the seal, the browser calls `navigator.credentials.get` with the chain head as the challenge; the chip signs `authenticatorData ‖ SHA256(clientDataJSON)` after Touch ID. The server checks type, challenge = head, allowed origin, rpIdHash, user-presence flag, then the ECDSA signature against the enrolled public key. We parse the CBOR/COSE registration ourselves (`crypto/cbor.py`, `crypto/ec.py`).

**Timestamp authority** (`attestors/timestamp.py`). RFC 3161: POST the head's hash to FreeTSA, get back a CMS-signed token with the time. We parse the DER, check `messageImprint` is our head, `messageDigest` matches TSTInfo, verify the ECDSA-P384/SHA-512 signature with the embedded signer certificate, and pin that certificate's fingerprint. The browser's clock is the student's; the TSA's is not. Every ~3 min the head is timestamped **silently** (no device key — macOS prompts for every passkey use, so device signatures are Touch-ID-at-seal only).

**Policy** (`attestors/policy.py`): L2 requires a verified device signature over the *final* chain root — the whole ledger was on the device when sealed. Intermediate signatures are "checkpoints", timestamps "timestamps": reported, never level-raising alone (they prove *when*, not *who*).

**Why both:** device alone can't prove *when* (student controls the Mac's clock); TSA alone can't prove *who/where* (anyone can timestamp any hash). Signing the same bytes interlocks them.

---

## 6. L3 — the hardware witness (`native/attest-hid`, `attestors/hid.py`)

**Problem:** L2 still can't tell a finger on a key from `dispatchEvent`, an AppleScript `keystroke`, or a macro tool running on the student's own Mac.

**Idea:** a small Swift helper below the browser listens to raw HID reports via `IOHIDManager` — synthetic events never appear there — and every 5 s emits a signed, hash-chained **statement**: *"between t₀ and t₁ I saw N physical key-downs from these devices; the machine had been idle I ms."* Counts only; never which key. Signed with its own Secure Enclave key (CryptoKit `SecureEnclave.P256`). Served on `127.0.0.1:8093` with a CORS allow-list; the helper is passive — no tokens, no outbound connections — the browser relays statements.

**Anchoring:** each segment's first statement is anchored to a real ledger head; the terminal statement (at seal) is anchored to the final chain root. So statements can't be borrowed from another session or trimmed.

**Correlation:** the server buckets the ledger's `kd` events into the same windows. Hardware may see **more** key-downs than the editor (shortcuts, other apps) but never **fewer**. A window with ≥ 8 editor keystrokes and < half that in hardware is an **injection window**. Text arriving in one `type` event without key events (`insertText`, dictation) counts as one keystroke-equivalent per extra character — found in live testing.

**L3 = L2 + gapless witness anchored both ends + every keystroke inside a witnessed window + no injection window.** Otherwise the certificate stays at L2 *and says why*; the review page shows the window; playback paints a red band.

**Honest label — "software witness":** the signatures prove statements are unaltered and from this Mac's Enclave; anchors prove they're about this ledger. What macOS *cannot* prove is that the program writing them is ours (App Attest is iOS/App Store only; the Mac App Store sandbox forbids Input Monitoring). Mitigations: code signing, the helper's `cdhash` in every statement pinned server-side, enrollment bound to an authenticated L2 session. Net: cheating past L3 means custom native software on your own Mac coordinated live with an injection script — a real bar, not L2's "the OS itself signs". Say this before anyone asks.

---

## 7. The issuer seal (`attest/issuer.py`)

Everything above is self-consistent by construction; a student running their own copy of this server could mint a certificate whose chain, replay and device signature all check against the keys inside the file. So the server signs every certificate with its own P-256 key (`issuer: {alg, key_id, public_key, signature}` over the canonical certificate). Public key at `GET /v1/issuer`. The server's verify and the teacher's review page **fail** `issuer` for anything not signed by this key; the offline CLI does the same with `--issuer-key`. A diploma anyone can type; the registrar's seal makes it a diploma.

---

## 8. Offline verification (`verifier/attest_verify.py`)

One file, standard library only, no server: `python3 attest_verify.py cert.json essay.txt --events ledger.json --issuer-key <hex>`. Re-derives the chain, Merkle root, replay, device signatures, timestamp token, witness chain/anchors/coverage/correlation, and the issuer seal, printing PASS/INFO/FAIL per check. The ECDSA (P-256/P-384), DER, CBOR and RSA code it needs is ours and readable — that is the point: a verifier you can audit.

---

## 9. The classroom (`server/classroom/`, `web/src/pages/`)

A sparse teaching platform *around* the engine, same server, same SQLite file.

- **Auth**: email + password (stdlib scrypt), bearer tokens stored hashed, 14-day TTL. Roles student/teacher.
- **Classes**: 6-letter join codes; **assignments** with per-check settings.
- **Ledger binding**: a submission owns one engine session (`doc_id = submission_id`, `owner = user_id`). Engine routes for bound sessions are guarded: only the owner writes/enrolls/signs; the teacher reads; other students get 404.
- **Submit is the hard guarantee**: the server rebuilds the certificate from **its own** ledger copy and refuses (`409 not_bound | wrong_session | hash_mismatch`) unless it replays to exactly the submitted text. No client claim is stored. After submit the ledger is frozen.
- **Review** (`GradeSubmission.vue`): pasted spans in red, classmate-overlap dashed, certificate card with server re-verify, process signals, citation report, similarity report, grade + feedback → return.
- **Playback** (`classroom/playback.py`, `lib/playback.js`): rebuilt from the ledger alone — provenance-coloured, pause ticks, paste/delete markers, injection bands, 1–16× or real time.
- **Citations** (`classroom/factcheck.py`): extracts DOIs/URLs/author-year cites; resolves DOIs via doi.org's registration-agency lookup then Crossref or DataCite; checks URLs; pairs cites with the reference list. Reports *unverifiable*, never *fabricated*. Background task, 7-day cache.
- **Similarity** (`classroom/similarity.py`): winnowing fingerprints (5-word grams, window 4, crc32) — any shared run of ≥ 8 words is guaranteed detected; prompt text excluded; matched passages recovered on both sides and shown, never a bare score.

Demo data: `python -m classroom.seed` — teacher `prof@demo.edu`, students `ana@ ben@ cara@demo.edu`, password `Passw0rd!x`, class code `DEMO26`, Ben's essay pre-submitted from a synthetic human ledger.

---

## 10. Tooling

- `./dev.sh up | down | restart | status | logs | reset | seed` — the whole stack.
- `server/walkthrough.py` — 13 narrated sections, one ✓ per claim, software Touch ID + software witness, `--live-tsa` for a real timestamp.
- `pytest` — 127 tests. Property-based (Hypothesis) proof that *any* single-field mutation of *any* event breaks the chain; byte-compatible fake authenticator and fake helper; captured real FreeTSA token; ECDSA cross-checked against the `cryptography` library.

---

## 11. Threat model — what stops what

| Attack | Stopped by |
|---|---|
| Edit the ledger after the fact | hash chain (L0) |
| Submit a different essay than the one written | replay binding (L1) |
| Fabricate a plausible ledger + paste a ChatGPT essay | device seal + TSA (L2); hardware witness (L3) |
| Backdate a session / fake timestamps | TSA (L2) |
| Run the forgery on another machine | Secure Enclave key enrolled to the student (L2) |
| Script types into the editor (`dispatchEvent`, AppleScript, macro, `insertText`, dictation) | hardware witness (L3) |
| Mint a perfect certificate on your own server | issuer seal |
| Paste text and call it typed | provenance (EXT spans) |
| Human transcribes AI output by hand | *not cryptographic* — cadence/revision/locality signals → review |
| USB typing gadget (is a real keyboard) | *not stopped*; visible as an external device + inhuman rhythm signals |
| Fake witness helper coordinated with an injection script | *not stopped* — the "software witness" caveat |

---

## 12. Honest limits (say these first)

1. L3 is a *software* witness — macOS has no App Attest for non-store apps.
2. Nothing proves whose fingers; the signals are statistical and say "review".
3. Thresholds in the signals are hand-picked, not fitted to data.
4. Stylometry is a stub socket (deliberately not wired: pre-hackathon model).
5. Helper is ad-hoc signed, unpinned in dev; notarization needs a paid Developer ID.
6. Single-file SQLite, one classroom — a hackathon product, not a deployment.

---

## 13. Demo script (2 minutes)

`./dev.sh reset`, then:

1. **/attest** — type; point at head changing, acks, signals. Paste → red. *"Every keystroke is chained before it leaves the browser; the server refuses anything that doesn't continue the chain."*
2. **Enroll this device** (Touch ID), **Enroll witness**, type a line → *editor N · keyboard N ✓*. *"A helper below the browser is counting real key presses."*
3. Console: `document.querySelector('.attest-editor').focus(); document.execCommand('insertText', false, 'This was injected by a script. ')` → red row. *"The editor saw 33 keystrokes; the keyboard saw none."*
4. **Finalize** → Touch ID → **L2, and it says why**. Undo the injection first for **L3**. **Verify** → the check list. *"Every line is something a third party can recompute."*
5. **Classroom** — Prof → Position paper → Ben → review page: spans, verify (issuer PASS), citations (real DOI valid), similarity, **Playback** at 4×.
6. Terminal: `python3 verifier/attest_verify.py … --issuer-key …` → PASS; edit one letter → FAIL. *"No server, no packages."*

Fallbacks: FreeTSA down → "no TSA" note, everything else works. Touch ID cancelled → seals at L1, says so.

---

## 14. Questions you'll get

**"Isn't this just a keylogger?"** No key identities are ever recorded — `kd` events are timing only, and the hardware witness reports counts. The ledger contains the text you submitted anyway; nothing about other apps.

**"What stops me faking the ledger?"** The chain stops editing it; replay stops swapping the essay; the device seal + TSA stop fabricating it elsewhere or backdating; the witness stops injecting it. What's left is a human typing someone else's words — statistics, not proof.

**"Why not detect AI text?"** Detectors guess from output and fail both ways. We make the *process* verifiable and leave judgement to the teacher.

**"Why L3 is 'software witness'?"** §6. Say it before they do.

**"Could a school actually run this?"** One Python process, one SQLite file, a Vue build, an optional helper. The certificate format and verifier are the durable part; the classroom is a thin shell.

**"What's the ZK idea?"** Future: prove "this certificate is valid at L3" without revealing the ledger — privacy of verification, not stronger evidence.

**"What was pre-existing?"** Nothing under `attest/`. `prior_work/` is reference for product shape only, never imported. Disclosed in the README.
