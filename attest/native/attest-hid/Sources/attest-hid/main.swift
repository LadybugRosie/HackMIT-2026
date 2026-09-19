// attest-hid — the hardware witness for attest (Stage 4, L3).
//
//   attest-hid [--port 8093] [--origin http://localhost:9100]... [--window-ms 5000] [--data-dir DIR]
//   attest-hid --probe            print every physical key-down (device, ms) — the Stage A check
//
// Counts physical HID key-downs in fixed windows and signs each window with a Secure Enclave key.
// Never records which keys. See docs/L3-hardware-witness.md.
import Foundation

let VERSION = "0.1.0"

struct Options {
    var port: UInt16 = 8093
    var origins: [String] = ["http://localhost:9100", "http://127.0.0.1:9100"]
    var windowMs: Int64 = 5000
    var dataDir = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/attest-hid")
    var probe = false
}

func parseArgs() -> Options {
    var o = Options()
    var customOrigins: [String] = []
    var it = CommandLine.arguments.dropFirst().makeIterator()
    while let a = it.next() {
        switch a {
        case "--port": o.port = UInt16(it.next() ?? "") ?? o.port
        case "--origin": if let v = it.next() { customOrigins.append(v) }
        case "--window-ms": o.windowMs = Int64(it.next() ?? "") ?? o.windowMs
        case "--data-dir": if let v = it.next() { o.dataDir = URL(fileURLWithPath: v) }
        case "--probe": o.probe = true
        case "-h", "--help":
            print("usage: attest-hid [--port N] [--origin URL]... [--window-ms N] [--data-dir DIR] [--probe]")
            exit(0)
        default: FileHandle.standardError.write(Data("unknown argument \(a)\n".utf8)); exit(2)
        }
    }
    if !customOrigins.isEmpty { o.origins = customOrigins }
    return o
}

let opts = parseArgs()
let state = DispatchQueue(label: "attest-hid.state")
var witnesses: [String: Witness] = [:]
let permission = HIDListener.requestAccess()
let cdhash = SelfIdentity.cdhash()

let logFile: FileHandle? = {
    // When launched as a .app there is no terminal; keep a log next to the key material.
    try? FileManager.default.createDirectory(at: opts.dataDir, withIntermediateDirectories: true)
    let url = opts.dataDir.appendingPathComponent("attest-hid.log")
    if !FileManager.default.fileExists(atPath: url.path) { FileManager.default.createFile(atPath: url.path, contents: nil) }
    let fh = try? FileHandle(forWritingTo: url)
    fh?.seekToEndOfFile()
    return fh
}()

func log(_ s: String) {
    let line = Data("[attest-hid] \(ISO8601DateFormatter().string(from: Date())) \(s)\n".utf8)
    FileHandle.standardError.write(line)
    logFile?.write(line)
}

log("v\(VERSION) cdhash=\(cdhash.prefix(16))… input-monitoring=\(permission)")
if permission != "granted" {
    log("Input Monitoring is not granted. Enable it in System Settings → Privacy & Security → Input Monitoring for this app, then relaunch.")
}

// -- Stage A probe: just print key-downs -------------------------------------------------------
if opts.probe {
    let listener = HIDListener { k in
        print("\(k.t)  \(k.device.id)\(k.device.builtin ? " (built-in)" : "")")
        fflush(stdout)
    }
    log(listener.start() ? "listening — type, hold a key, then run: osascript -e 'tell application \"System Events\" to keystroke \"abc\"'"
                         : "IOHIDManagerOpen failed (permission?)")
    CFRunLoopRun()
    exit(0)
}

// -- Witness mode ------------------------------------------------------------------------------
let signer: Signer
do { signer = try Signer(dataDir: opts.dataDir) } catch { log("cannot create witness key: \(error)"); exit(1) }
log("key_id=\(signer.keyID) backend=\(signer.backend.rawValue)")

let listener = HIDListener { k in
    state.async { for w in witnesses.values { w.record(k) } }
}
if !listener.start() { log("IOHIDManagerOpen failed — statements will report zero key-downs until Input Monitoring is granted") }

// Close windows on a steady tick; drop sealed witnesses after ten minutes.
let ticker = DispatchSource.makeTimerSource(queue: state)
ticker.schedule(deadline: .now(), repeating: .milliseconds(500))
ticker.setEventHandler {
    let now = MachClock.nowMs()
    for (sid, w) in witnesses {
        do { try w.tick(now: now, signer: signer, cdhash: cdhash) } catch { log("sign failed for \(sid): \(error)") }
        if w.sealed, now - w.sealedAt > 600_000 { witnesses[sid] = nil }
    }
}
ticker.resume()

func route(_ req: HTTPRequest) -> HTTPResponse {
    var out: HTTPResponse = .error(404, "no such route")
    state.sync {
        switch (req.method, req.path) {
        case ("GET", "/status"):
            out = .ok(["running": true, "version": VERSION, "cdhash": cdhash, "key_id": signer.keyID,
                       "key_backend": signer.backend.rawValue, "permission": HIDListener.checkAccess(),
                       "window_ms": opts.windowMs, "sessions": witnesses.keys.sorted()])
        case ("GET", "/identity"):
            out = .ok(["public_key": signer.publicKeyHex, "key_id": signer.keyID, "cdhash": cdhash,
                       "key_backend": signer.backend.rawValue, "helper_version": VERSION])
        case ("POST", "/enroll-sign"):
            guard let ch = req.json()?["challenge"] as? String, let bytes = Base64URL.decode(ch) else { out = .error(400, "challenge (base64url) required"); break }
            do { out = .ok(["signature": Base64URL.encode(try signer.sign(bytes)), "key_id": signer.keyID]) }
            catch { out = .error(500, "sign failed: \(error)") }
        case ("POST", "/start"):
            guard let j = req.json(), let sid = j["sid"] as? String, let head = j["head"] as? String, head.count == 64 else {
                out = .error(400, "sid and head (hex) required"); break
            }
            if let w = witnesses[sid], !w.sealed {
                out = .ok(["sid": sid, "seg": w.seg, "resumed": true, "statements": w.statements.count])
            } else {
                let w = Witness(sid: sid, anchorHead: head, now: MachClock.nowMs(), windowMs: opts.windowMs)
                witnesses[sid] = w
                out = .ok(["sid": sid, "seg": w.seg, "resumed": false, "statements": 0])
            }
        case ("GET", "/statements"):
            guard let sid = req.query["sid"], let w = witnesses[sid] else { out = .error(404, "unknown sid"); break }
            let since = Int(req.query["since"] ?? "-1") ?? -1
            out = .ok(["sid": sid, "seg": w.seg, "sealed": w.sealed, "statements": w.statements(since: since)])
        case ("POST", "/seal"):
            guard let j = req.json(), let sid = j["sid"] as? String, let head = j["head"] as? String, head.count == 64 else {
                out = .error(400, "sid and head (hex) required"); break
            }
            guard let w = witnesses[sid] else { out = .error(404, "unknown sid"); break }
            do {
                try w.seal(head: head, now: MachClock.nowMs(), signer: signer, cdhash: cdhash)
                out = .ok(["sid": sid, "seg": w.seg, "sealed": true, "statements": w.statements.count])
            } catch { out = .error(500, "sign failed: \(error)") }
        default: break
        }
    }
    return out
}

// Held at top level on purpose: NWListener stops accepting when its owner is released.
let server: LocalServer
do {
    server = try LocalServer(port: opts.port, allowedOrigins: opts.origins, route: route)
    server.start()
    log("listening on http://127.0.0.1:\(opts.port) for origins \(opts.origins.joined(separator: ", "))")
} catch {
    log("cannot listen on port \(opts.port): \(error)"); exit(1)
}
CFRunLoopRun()
