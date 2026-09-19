# attest-hid — the hardware witness (Stage 4, L3)

A small macOS helper that runs beside the browser during a writing session. It listens to raw
HID keyboard reports, counts **physical key-downs** in 5-second windows, and signs each window
with a P-256 key in the Mac's Secure Enclave. The attest server compares those counts with the
ledger's content-free `kd` events: hardware may see *more* key-downs than the editor (shortcuts,
other apps) but never *fewer*. A window where the editor recorded keystrokes the hardware never
saw is injection, and the certificate stays at L2 with the window named.

**What it records:** per window — a count, per-device counts (`vendor:product#hash`, built-in or
not), the system idle time, its own code hash. **What it never records:** which keys, key-ups,
text in any application.

## Run

```bash
cd native/attest-hid
./bundle.sh                         # swift build + dist/attest-hid.app (ad-hoc signed)
open dist/attest-hid.app            # first launch: macOS asks for Input Monitoring
```

Grant it in *System Settings → Privacy & Security → Input Monitoring*, then relaunch. Logs and
key material live in `~/Library/Application Support/attest-hid/`. The browser detects the helper
on `127.0.0.1:8093`; the Ledger panel's **Hardware witness** section shows *not enrolled* →
**Enroll witness** → *witnessing*.

Development: `swift build -c release && .build/release/attest-hid --probe` prints every
physical key-down (the Stage A check: type, hold a key, then inject with AppleScript and confirm
the injected keys never appear).

Options: `--port 8093` · `--origin URL` (repeatable CORS allow-list; default `http://localhost:9100`)
· `--window-ms 5000` · `--data-dir DIR` · `--probe`.

## Pinning the build

`codesign -dvvv dist/attest-hid.app 2>&1 | grep CDHash` prints the code-directory hash the helper
reports in every statement. Set `ATTEST_HID_TRUSTED_CDHASHES='["<hash>"]'` on the server to accept
only that build; unset, the server accepts any helper and marks the witness *unverified build*.
See `docs/L3-hardware-witness.md` §6 for exactly what pinning does and does not prove.

## Trust

This is a *software witness*: the signatures prove the statements were not altered and came from
this Mac's Enclave key, and the anchors prove they are about this ledger — but macOS offers no way
for a non-App-Store program to prove its own identity (App Attest is iOS-only), so a determined
student could write a fake helper. L3 raises the bar from "one line of JavaScript" to "custom
native software coordinated live with an injection script". The certificate says `L3 (software
witness)` for that reason.

Dependencies: Apple frameworks only (IOKit, Security, Network, CryptoKit). No third-party code.
