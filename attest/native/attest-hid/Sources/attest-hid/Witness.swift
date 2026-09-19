// Windows, statements and the hash chain — the mirror of server/attest/attestors/hid.py.
//
//   statement = {v, sid, seg, seq, t0, t1, kd, devices:[{id, kd, builtin}], idle_ms, cdhash,
//                anchor: {head} | null, final, prev}  (+ hash, sig)
//   canon     = JSON(statement; keys sorted; compact; no escaping of "/")
//   hash      = SHA256(canon || prev)        prev of seq 0 == anchor.head
//   sig       = ECDSA-P256 over SHA256(hash-hex as ASCII)
//
// A Witness follows one ledger session. A page reload reuses it; a helper restart starts a new
// segment (seg = Unix seconds at start, so segments sort chronologically on the server).
import Foundation

struct Statement {
    let dict: [String: Any]     // canonical fields + hash + sig
    var seq: Int { dict["seq"] as! Int }
    var isFinal: Bool { dict["final"] as! Bool }
}

final class Witness {
    let sid: String
    let seg: Int
    let windowMs: Int64
    private(set) var statements: [Statement] = []
    private(set) var sealed = false
    private(set) var sealedAt: Int64 = 0
    private var seq = 0
    private var prev: String
    private var windowStart: Int64
    private var pending: [KeyDown] = []
    private var anchor: [String: Any]?

    init(sid: String, anchorHead: String, now: Int64, windowMs: Int64) {
        self.sid = sid
        self.seg = Int(now / 1000)
        self.windowMs = windowMs
        prev = anchorHead
        windowStart = now
        anchor = ["head": anchorHead]
    }

    func record(_ k: KeyDown) {
        guard !sealed else { return }
        pending.append(k)
    }

    /// Close every window whose end has passed (plus a small grace for late reports).
    func tick(now: Int64, signer: Signer, cdhash: String) throws {
        while !sealed, now >= windowStart + windowMs + 100 {
            try closeWindow(t1: windowStart + windowMs, final: false, anchorHead: nil, signer: signer, cdhash: cdhash)
        }
    }

    /// Close the running window at `now`, then emit the terminal statement anchored to `head`.
    func seal(head: String, now: Int64, signer: Signer, cdhash: String) throws {
        guard !sealed else { return }
        if now > windowStart {
            try closeWindow(t1: now, final: false, anchorHead: nil, signer: signer, cdhash: cdhash)
        }
        try closeWindow(t1: windowStart, final: true, anchorHead: head, signer: signer, cdhash: cdhash)
        sealed = true
        sealedAt = now
    }

    private func closeWindow(t1: Int64, final: Bool, anchorHead: String?, signer: Signer, cdhash: String) throws {
        let t0 = windowStart
        let inWindow = pending.filter { $0.t < t1 }
        pending.removeAll { $0.t < t1 }
        var perDevice: [DeviceID: Int] = [:]
        for k in inWindow { perDevice[k.device, default: 0] += 1 }
        let devices: [[String: Any]] = perDevice.keys.sorted { $0.id < $1.id }.map { d in
            ["id": d.id, "kd": perDevice[d]!, "builtin": d.builtin]
        }
        let idle: Int64 = final ? 0 : IdleTime.ms()
        let anchorValue: Any
        if let h = anchorHead { anchorValue = ["head": h] }
        else if seq == 0, let a = anchor { anchorValue = a }
        else { anchorValue = NSNull() }
        var st: [String: Any] = [
            "v": 1, "sid": sid, "seg": seg, "seq": seq, "t0": t0, "t1": t1,
            "kd": inWindow.count, "devices": devices, "idle_ms": idle, "cdhash": cdhash,
            "anchor": anchorValue, "final": final, "prev": prev,
        ]
        let hash = Canon.hash(st)
        st["hash"] = hash
        st["sig"] = Base64URL.encode(try signer.sign(Data(hash.utf8)))
        statements.append(Statement(dict: st))
        prev = hash
        seq += 1
        windowStart = t1
    }

    func statements(since: Int) -> [[String: Any]] {
        statements.filter { $0.seq > since }.map { $0.dict }
    }
}

enum Canon {
    static let keys: Set<String> = ["v", "sid", "seg", "seq", "t0", "t1", "kd", "devices", "idle_ms", "cdhash", "anchor", "final", "prev"]

    static func bytes(_ st: [String: Any]) -> Data {
        var body: [String: Any] = [:]
        for k in keys { body[k] = st[k] ?? NSNull() }
        // JSONSerialization with .sortedKeys sorts nested dictionaries too; no whitespace is emitted.
        return try! JSONSerialization.data(withJSONObject: body, options: [.sortedKeys, .withoutEscapingSlashes])
    }

    static func hash(_ st: [String: Any]) -> String {
        var d = bytes(st)
        d.append(Data((st["prev"] as! String).utf8))
        return Hash.sha256Hex(d)
    }
}
