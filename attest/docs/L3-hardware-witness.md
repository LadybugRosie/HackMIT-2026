# Plan: Stage 4 — L3, the hardware witness

*Status: built (Stages B–D, F) — see README §"The hardware witness". Deviations from this plan: HID batches use a dedicated `POST /attest-hid` route rather than `kind:"hid"` in `/attest`; segments are numbered by Unix seconds at start; text arriving in one `type` event without key events counts as keystroke-equivalents (§4.4 addition found in live testing); witness checks are informational in verify output unless the certificate claims L3. Stage A (physical typing + injector) and Stage E (demo recording) need a person at the keyboard.*

---

## 0. Why this stage exists

After L2 a certificate says: *this exact ledger was on this student's Mac, the enrolled person
sealed it with Touch ID, and an independent clock saw its checkpoints.* What it still cannot say
is whether the keystrokes in that ledger were **typed**.

The browser records `KeyboardEvent`s and cannot tell a finger on a key from any of these, all of
which produce a flawless L2 ledger on the student's own machine:

| Attack | How it works | Cost |
|---|---|---|
| `dispatchEvent` from the console | Fabricated `KeyboardEvent` + `input` events straight into the editor | one line of JavaScript |
| AppleScript `keystroke` | `osascript -e 'tell app "System Events" to keystroke "…"'` types into whatever has focus | one line of shell |
| Accessibility "typing" tools | Text-expanders, macro apps, `xdotool`-style utilities | free download |
| USB typing gadget | An Arduino/Digispark that *is* a keyboard and types a stored essay with jittered timing | ~$12 |

The first three never touch a physical input device. L3 puts a witness **below the browser**, at
the layer where macOS receives input from hardware, and requires the ledger to agree with it.
The fourth *is* a physical device; L3 cannot rule it out but makes it visible (§4.6).

**What L3 will and will not claim.** L3 proves that every keystroke the editor recorded had a
matching key-down from a real input device, on this Mac, in the same five-second window. It does
not prove whose finger it was, nor that the words are original — those stay with the timing
signals and stylometry. And unlike L1/L2, L3 rests on a program *we* ship rather than on the OS
itself, so its trust story is "materially harder and detectable," not "cryptographically
impossible" (§6). The certificate will label it **`L3 (software witness)`** and the README will
say exactly this.

---

## 1. The idea in one paragraph

A small native helper (`attest-hid`) runs on the Mac during writing. It listens to raw HID
key-down reports — counts and timestamps only, never which key — and every 5 s emits a signed,
hash-chained *statement*: "between t₀ and t₁ I saw N physical key-downs from these devices, and
the machine had been idle for I ms." The browser forwards statements to the attest server, which
already holds the ledger's content-free `kd` events. At seal, the server lines the two streams up
window by window. Hardware may see *more* key-downs than the editor (shortcuts, typing in another
app) but never *fewer*: a window where the editor recorded 40 keystrokes and the hardware saw 0 is
injection. If the witness chain is gapless, anchored to this ledger at both ends, signed by the
student's enrolled helper key, and agrees with the ledger everywhere, the certificate reaches L3.

```
   keyboard ──HID──▶ macOS ──▶ IOHIDManager ──▶ attest-hid ──signed statements──▶ browser ──▶ server
                        │                        (counts only)                                  │
                        └──KeyboardEvent──▶ Tiptap editor ──kd events──▶ ledger ────────────────┘
                                                                                                ▼
                                                                          per-window: hw_kd ≥ ledger_kd ?
```

---

## 2. Components

```
attest/
  native/attest-hid/           NEW  Swift package → attest-hid.app (LSUIElement, no windows)
    Sources/attest-hid/
      main.swift               arg parsing, permission request, run loop
      HIDListener.swift        IOHIDManager: key-down callback → (t, deviceID)
      Windows.swift            5 s windows → Statement; hash chain
      Signer.swift             Secure Enclave P-256 key; ECDSA over statement hash
      LocalServer.swift        HTTP/1.1 on 127.0.0.1:8093 (NWListener), CORS-restricted
      SelfIdentity.swift       cdhash via SecCodeCopySelf; HIDIdleTime
    bundle.sh                  wraps the executable into attest-hid.app + Info.plist, ad-hoc signs
  server/attest/
    attestors/hid.py           NEW  statement verification + chain + correlation with the ledger
    attestors/policy.py        MOD  assess_attestations gains the L2 → L3 rule
    routers/attestation.py     MOD  POST /enroll-hid, kind:"hid" batches in POST /attest
    models.py                  MOD  HidStatement, HidBatch, EnrollHidRequest
    settings.py                MOD  HID_TRUSTED_CDHASHES, HID_WINDOW_MS, HID_TOLERANCE
  server/tests/
    fake_hid.py                NEW  software helper: honest / injection / gap / wrong-anchor modes
    test_hid.py                NEW
  web/src/
    lib/hid.js                 NEW  detect / start / poll / seal against 127.0.0.1:8093
    lib/sync.js                MOD  hid state, polling, seal ordering
    extensions/capture.js      MOD  ignore `e.repeat` on kd/ku (held keys are one HID down)
    components/LedgerPanel.vue MOD  "Hardware witness" section with live window bar
    components/CertificateCard.vue MOD  L3 chip + witness summary
    lib/playback.js, PlaybackViewer.vue  MOD  window markers, red injection bands
  verifier/attest_verify.py    (no change — policy module is stdlib and already imported)
```

---

## 3. The helper (`native/attest-hid`)

### 3.1 What it listens to

`IOHIDManager` with a matching dictionary for usage page **Generic Desktop / Keyboard** (`0x01/0x06`)
and **Keypad** (`0x01/0x07`). The input-value callback fires for every HID element change; we
count an event when the element's usage page is Keyboard/Keypad (`0x07`) and the value transitions
to 1 (key **down**). Key-ups and repeats are ignored. Per event we keep exactly two things:

- `t` — the report timestamp (`IOHIDValueGetTimeStamp`, mach absolute) converted to Unix ms
  with an offset measured at start-up, so it lives on the same clock as the browser's `Date.now()`.
- `device` — a stable label for the device: `vendorID:productID` plus a short hash of
  `LocationID|SerialNumber`, e.g. `05ac:0341#9f2c`. Apple's built-in keyboard (transport `SPI`, or
  product name containing "Apple Internal") is tagged `builtin: true`.

**What it deliberately does not record:** the usage (which key), modifiers, key-ups, typing in
other applications as text. The helper cannot reconstruct anything anyone typed; it produces
counts.

### 3.2 Statements and the chain

Every `HID_WINDOW_MS = 5000` ms (aligned to the segment start) the helper closes a window:

```json
{
  "v": 1, "sid": "<ledger session id>", "seg": 0, "seq": 41,
  "t0": 1758232390000, "t1": 1758232395000,
  "kd": 87,
  "devices": [{"id": "05ac:0341#9f2c", "kd": 87, "builtin": true}],
  "idle_ms": 210,
  "cdhash": "a4f1…",
  "anchor": null,
  "prev": "<hash of seq 40>", "hash": "<sha256(canon || prev)>",
  "sig": "<base64url DER ECDSA over hash>"
}
```

- `canon` is the statement without `hash`/`sig`, keys sorted, compact JSON — the same rule as the
  ledger, so the server and the offline CLI verify it with code they already have.
- `seq 0` of every **segment** carries `anchor: {"head": "<ledger chain head at that moment>"}`;
  the last statement (emitted on `/seal`) carries `anchor: {"head": "<final chain head>"}`.
  A segment is one uninterrupted run of the helper for one session; a page reload continues the
  same segment (the helper keeps state per `sid`), a helper restart starts segment 1.
- `idle_ms` is `HIDIdleTime` from the IORegistry at `t1`: how long since *any* physical input.
  This is the "background presence" signal — now signed. A window with `kd > 0` and
  `idle_ms > 5000` is self-contradictory and fails verification.
- `cdhash` is the helper's own code-directory hash from `SecCodeCopySigningInformation`
  (`kSecCodeInfoUnique`). Its role is discussed honestly in §6.

### 3.3 Signing

On first run the helper creates a P-256 key in the Secure Enclave
(`SecKeyCreateRandomKey` with `kSecAttrTokenIDSecureEnclave` and access control
`.privateKeyUsage` only — no biometry, so signing is **silent**; a witness that prompted every 5 s
would be unusable). The key is tagged `xyz.attest.hid` in the keychain and reused across runs.
Its public key (65-byte uncompressed point) and a `key_id = sha256(pubkey)[:16]` are exposed at
`GET /identity`.

Binding the key to a *person* happens at enrollment (§4.2), through the browser's authenticated
session — the helper itself holds no credentials and never talks to the attest server.

### 3.4 Local API (127.0.0.1:8093)

A minimal HTTP/1.1 responder over `NWListener`. CORS: `Access-Control-Allow-Origin` echoes the
request origin **only** if it is in the helper's allow-list (default `http://localhost:9100`);
everything else gets no CORS headers, so a random web page cannot drive the witness.

| Route | Purpose |
|---|---|
| `GET /status` | `{running, version, cdhash, key_id, permission: "granted"\|"denied"\|"unknown", sessions:[sid]}` — the browser's detection probe |
| `GET /identity` | public key + key_id + cdhash (for enrollment) |
| `POST /enroll-sign {challenge}` | signs the server's enrollment challenge with the Enclave key → `{signature}` |
| `POST /start {sid, head}` | begin (or resume) witnessing `sid`; opens a segment anchored at `head` |
| `GET /statements?sid=&since=` | closed statements with `seq > since` (browser forwards them) |
| `POST /seal {sid, head}` | close the current window early, emit the terminal statement anchored at `head`, stop witnessing `sid` |

The helper never initiates network connections. It is a passive witness with a local mailbox.

### 3.5 Permissions and packaging

Listening to HID input requires macOS **Input Monitoring** (`IOHIDRequestAccess(kIOHIDRequestTypeListenEvent)`).
Two facts shape the packaging:

1. TCC grants the permission to the **responsible application**. A bare executable launched from
   Terminal gets Terminal's permission, not its own. So the helper ships as a minimal `.app`
   bundle (`LSUIElement = true`, no Dock icon) even though it has no UI; `bundle.sh` produces it.
2. The first launch triggers the system prompt and the user must flip the switch in
   *System Settings → Privacy & Security → Input Monitoring*, then relaunch. **This is the step
   that needs you at the keyboard**, once per machine.

Code signing: ad-hoc (`codesign -s -`) during the hackathon. Notarization needs a paid Developer
ID; the plan documents it as the production step and §6 explains what it would and wouldn't buy.

### 3.6 Validation the helper must pass before anything else is built (Stage A)

- Type in the editor → callback fires once per key-down; count matches keystrokes.
- Hold a key → **one** HID down (auto-repeat is generated by the OS, not the device). This is why
  `capture.js` must start ignoring `e.repeat`.
- `osascript … keystroke "abc"` → **zero** HID events (synthetic CGEvents do not traverse
  IOHIDManager device callbacks). If this turns out false on the current macOS, L3 as designed is
  not viable and we stop here — so it is the first thing to test.
- Bluetooth keyboard → appears as a second device id, non-builtin.
- `HIDIdleTime` resets on any key/mouse activity.

---

## 4. Server

### 4.1 Storage

No schema change. HID statements are stored through the existing `attestations` table as
records of `kind: "hid"`, one record per forwarded **batch** (`{kind, statements:[…], key_id,
public_key, cdhash}`); verification concatenates all batches and sorts by `(seg, seq)`. The helper
key is a row in `credentials` with `type: "hid"` and the same `owner` scoping as WebAuthn keys.

### 4.2 Enrollment — `POST /v1/session/{id}/enroll-hid`

1. Browser: `GET /v1/session/{id}/enroll/options` (reuses the WebAuthn challenge machinery) →
   `challenge`.
2. Browser → helper: `GET /identity`, then `POST /enroll-sign {challenge}`.
3. Browser → server: `POST /enroll-hid {public_key, key_id, cdhash, signature}`.
4. Server: verify the ECDSA signature over `challenge` with `public_key`; store the credential
   under `rec.owner`. Classroom guard: owning student only (the existing `guard_session_owner`).

The person-binding is the authenticated browser session (plus, in the classroom, the bearer
token). Optional hardening for later: require an L2 WebAuthn signature over `sha256(hid_pubkey)`
at enrollment so the *Touch-ID-verified* person vouches for the helper key.

### 4.3 Ingest — `kind: "hid"` in `POST /v1/session/{id}/attest`

For each batch the server checks, before storing:

- every statement's `sid` equals the session, `cdhash` and `key_id` are consistent within the batch;
- signatures verify with the enrolled key whose `owner` is the session's owner;
- the batch continues the stored chain for that segment (`seq`, `prev`) — a 409 `hid_chain_break`
  otherwise, mirroring `/v1/ingest`;
- any `anchor.head` is a real state of this ledger (genesis or an event hash), recorded with its
  `at_event_count`.

Batches are accepted while the session is open; the terminal statement is accepted up to and
including the finalize call (the browser sends it just before `/finalize`, after the WebAuthn seal).

### 4.4 Verification — `attestors/hid.py`

Pure functions, stdlib only, so the offline CLI gets them for free.

```
assess_hid(statements, ledger_events, genesis, chain_root, known_heads, trusted_cdhashes)
  -> HidSummary(ok, level_supports_l3, reasons[], windows, coverage_ratio, ledger_kd, hw_kd,
                injection_windows[], devices[], segments, helper_trusted, correlation_basis)
```

Checks, in order (each becomes a named `Check` in the certificate's verify output):

| Check | Passes when |
|---|---|
| `hid_signatures` | every statement's `sig` verifies with the embedded/enrolled key |
| `hid_chain` | within each segment: `seq` contiguous from 0, `prev` links, `hash` recomputes, `t1[k] == t0[k+1]` (gapless windows) |
| `hid_anchors` | every segment's first `anchor.head` ∈ known heads of *this* ledger; terminal statement's `anchor.head == chain_root` |
| `hid_helper` | `cdhash` ∈ `HID_TRUSTED_CDHASHES`; if the trusted set is empty → **pass with flag** `helper_unverified` (dev mode) |
| `hid_consistency` | no window with `kd > 0` and `idle_ms > window length` |
| `hid_coverage` | every ledger keystroke timestamp falls inside some verified window (±250 ms skew allowance); reported as `coverage_ratio` |
| `hid_correlation` | no injection window (below) |

**Correlation.** `correlation_basis` is `"kd"` when the ledger has `kd` events (every session the
current client produces), else `"edits"` (single-code-point `type` inserts — a fallback for old
ledgers, reported as weaker). For each window `w`:

```
ledger_kd(w) = # ledger keystroke events with t0 ≤ ts < t1      (paste events excluded)
hw_kd(w)     = statement.kd
```

Rule: `hw_kd(w) ≥ ledger_kd(w) − tol(w)` where `tol(w) = 2 + ⌈0.05 · ledger_kd(w)⌉` absorbs
key-downs that straddle a window boundary and the browser's slightly later timestamp.
A window with `ledger_kd ≥ 8` and `hw_kd < 0.5 · ledger_kd` is an **injection window**; any one of
them fails `hid_correlation`. The asymmetry is intentional: hardware seeing *more* than the editor
is normal (Cmd-S, typing in another app, arrow keys the editor doesn't count) and never counts
against the student.

**Why 5 s windows and counts, not per-keystroke matching.** Per-event matching would need the
helper to expose event timestamps (a keystroke-timing side channel) and would break on the
~1–15 ms jitter between the HID report and the DOM event. Windowed counts give the injection
detector everything it needs while keeping the helper's output content-free.

### 4.5 Policy — `policy.py`

```
L3 requires:  L2 (verified WebAuthn signature over chain_root)
          AND assess_hid(...).ok           (all seven checks)
          AND coverage_ratio == 1.0        (every keystroke witnessed)
```

Anything less stays L2 and the summary says why, e.g. `reasons: ["injection window 14:47:05–:10:
editor 84, hardware 0"]` or `["coverage 0.91 — 47 keystrokes before the witness started"]`.
`claims.attestation.hid` carries the whole `HidSummary` so the review page can show it without
recomputing. The certificate `assurance_level` string becomes `"L3"`, with
`claims.attestation.hid.helper_trusted` telling the reader whether the helper's identity was
pinned — the UI renders `L3 (software witness)` either way (§6).

### 4.6 Devices

`devices[]` in the summary aggregates per device id across all windows: `{id, builtin, kd, share}`.
A USB typing gadget passes the count check (it *is* a keyboard) but appears as a second,
non-builtin device that typed most of the essay. The certificate reports it plainly
(`devices: [{05ac:0341 builtin 12%}, {1a86:7523 unknown 88%}]`) and the review page shows a
"typed from an external device" note. Whether that is a Bluetooth keyboard or a gadget is the
teacher's judgement — the same posture as the timing signals: evidence, not verdict. A virtual
keyboard driver (Karabiner-style DriverKit extension) is the same case with a recognisable
vendor id, and needs a user-approved system extension to install.

---

## 5. Browser

### 5.1 `lib/hid.js`

```
detect()                 GET 127.0.0.1:8093/status with an 800 ms timeout → status | null
identity()               GET /identity
enrollSign(challenge)    POST /enroll-sign
start(sid, head)         POST /start
statements(sid, since)   GET /statements
seal(sid, head)          POST /seal → terminal statement
```

### 5.2 `sync.js`

- On `start()` / `resume()`: `detect()`; if the helper is running and a `hid` credential exists
  for the owner, `hid.start(sid, chain.head)` after the first flush (so the anchor is a server-known
  head), then poll `statements` every 10 s and forward each batch to `POST /attest`. State exposed:
  `hid: {available, permission, enrolled, segments, windows, lastWindow: {ledgerKd, hwKd, ok}, injections, error}`.
- `record()` counts the client's own `kd` events per window so the panel can show *live*
  agreement without waiting for the server.
- `finalize()` ordering becomes: `sealing = true` → flush → WebAuthn seal (Touch ID) → **`hid.seal(head)`**
  → forward terminal batch → `/finalize`. The HID seal comes after the WebAuthn seal because both
  are over the same final head and the head must not move in between (`sealing` guarantees that).

### 5.3 UI

**LedgerPanel — "Hardware witness" section**

- Helper not detected: one line, *"Install attest-hid for L3 — the certificate proves the
  keystrokes were physical"*, with a link to `native/README`.
- Detected, permission missing: *"Grant Input Monitoring in System Settings, then relaunch."*
- Detected, not enrolled: **Enroll witness** button (no Touch ID — the Enclave key signs silently;
  the browser session is the person-binding).
- Running: `witnessing · 118 windows · seal → L3`, and a live bar for the last window:
  `editor 12 · keyboard 12 ✓`. On a mismatch the bar turns red and stays in a list:
  `14:47:05 editor 84 · keyboard 0 — injected`. Level preview drops to L2.

**CertificateCard**: `L3` chip (title: "software witness — see README §L3"), one summary line:
*"Hardware witness: 118 windows, 100% coverage, 1 device (built-in), no injection, helper pinned."*

**Playback**: a thin track under the timeline with one tick per window; injection windows as red
bands; hover shows editor vs hardware counts. Teachers see *where* in the essay the injected
paragraph is.

### 5.4 `capture.js`

One-line engine change: `if (e.repeat) return` before emitting `kd`/`ku`. A held Backspace
produces one HID down and, today, dozens of ledger `kd` events; without this the honest student
fails correlation.

---

## 6. Trust story — what "software witness" means

Stated plainly so a reviewer can decide whether the label is honest.

**What is cryptographically solid:** each statement is signed by a key that cannot leave the
Mac's Secure Enclave and was enrolled under the student's account. Statements are hash-chained
and anchored to this ledger at both ends, so they cannot be edited, reordered, dropped in the
middle, or borrowed from another session. The correlation is computed by the verifier from two
independently recorded streams.

**What is not:** that the program that produced the statements is *our* helper. macOS offers no
way for a non-App-Store program to prove its own identity to a remote party (Apple's App Attest is
iOS/App Store only; the Mac App Store sandbox forbids Input Monitoring). So a student who writes
a fake helper that emits counts matching their injection script, signed with their own Enclave
key, would pass. The mitigations and their exact value:

| Measure | Stops | Doesn't stop |
|---|---|---|
| Ad-hoc / Developer ID signing + notarization | silently swapping a patched binary; Gatekeeper warns | a student who right-click-opens anyway |
| `cdhash` in every statement, pinned server-side | casual tampering with our helper | a fake helper that *copies* our published cdhash into its statements (it's just data in the report) |
| Enclave key enrolled through the student's authenticated, L2-verified session | running the forgery on a different machine or by someone else | the student on their own Mac |
| Correlation with the ledger | any injection the helper honestly reports | a fake helper coordinated in real time with the injection script |

Net effect: cheating past L3 requires writing custom native software, running it unsigned on your
own machine, and keeping two fabricated streams consistent live. That is a real bar — far above
the one-line attacks in §0 — but it is not L2's "the OS itself signs." Hence `L3 (software
witness)`, and the README sentence: *"L3 makes synthetic input much harder and detectable, not
impossible. The hardware-strength version of this guarantee exists only inside Apple's App Attest,
i.e. as an iPad app."*

---

## 7. Stages, in build order

| # | Stage | What | ~h | Verify |
|---|---|---|---|---|
| **A** | Feasibility spike | Swift CLI: IOHIDManager listener printing `(t, device)` per key-down; test the §3.6 list, especially `osascript` → 0 events | 1 | You grant Input Monitoring once; we see counts in a terminal |
| **B** | Helper | Windows + chain + Enclave signer + local HTTP + `/status /identity /enroll-sign /start /statements /seal`; `bundle.sh` | 2.5 | `curl` the routes; statements verify with the server's `ec.verify` |
| **C** | Server verify | `attestors/hid.py`, `fake_hid.py`, policy rule, `enroll-hid` + `hid` batches in the router, certificate summary | 2 | `test_hid.py`: honest → L3; injection / gap / wrong anchor / tampered / unpinned → L2 with the named reason; teacher & other student 404; offline CLI passes L3 |
| **D** | Browser | `hid.js`, `sync.js` polling + seal ordering, `capture.js` repeat filter, LedgerPanel section, CertificateCard, PlaybackViewer bands | 1.5 | Type → live bar agrees, seal → L3 card |
| **E** | Demo | Type a paragraph normally, then `osascript` types the next one: bar goes red, seal lands at L2 with the injection window named; playback shows the red band | 0.5 | Screen recording for the pitch |
| **F** | Docs | `native/README.md` (install, permission, what is/isn't recorded), README L3 section with §6 verbatim, disclosure line for Swift deps (none beyond Apple frameworks) | 0.5 | — |

Total ≈ 8 h. Stage A is a hard gate: if synthetic events are visible to IOHIDManager on current
macOS, the design changes (CGEventTap with `kCGEventSourceStateID` filtering, which is weaker) and
we reassess before building B–F.

**Needs you present:** Stage A (Input Monitoring prompt, ~5 min) and the first run of the bundled
helper in Stage B (same prompt, since the `.app` is a new responsible process). Everything else
is scriptable, and all of Stage C runs without the helper via `fake_hid.py`.

---

## 8. Decisions I've made — flag any you disagree with

1. **Counts per 5 s window, not per-keystroke timestamps.** Privacy and robustness (§4.4). Cost:
   an injection of fewer than ~8 keystrokes in a window is below the detection floor.
2. **Hardware ≥ editor, one-directional.** Never penalise a student for typing outside the editor.
3. **Browser mediates; helper is passive.** The helper never holds a token or opens outbound
   connections; a compromised helper can lie but cannot exfiltrate.
4. **Silent Enclave key for the helper.** A witness that prompts is not a witness. Person-binding
   comes from the authenticated enrollment, not from biometrics on every statement.
5. **L3 requires L2.** No hardware witness without a device-sealed ledger.
6. **`.app` bundle, ad-hoc signed, no notarization for the hackathon.** Notarization needs a paid
   Developer ID and adds nothing to the security argument that §6 doesn't already concede.
7. **Empty `HID_TRUSTED_CDHASHES` = dev mode.** Accept any helper but flag `helper_unverified`
   in the summary; production pins the published cdhash.
8. **Label it `L3 (software witness)`.** The alternative — calling it L3 unqualified — would
   overstate what it proves.

## 9. Open questions for you

- Should a **non-builtin device typing >50%** of the essay cap the level at L2, or stay L3 with a
  visible note (current plan: note only — a Bluetooth keyboard is legitimate)?
- Is **100% coverage** the right bar, or should we tolerate a short unwitnessed prefix (e.g. the
  first 20 keystrokes before the helper's first window closes)? Current plan: 100%, because the
  helper starts before the first flush and the first window is anchored to the head at that time.
- Do you want the **WebAuthn-signed helper enrollment** (Touch ID once to vouch for the helper
  key) in v1, or leave it as the documented hardening step?
