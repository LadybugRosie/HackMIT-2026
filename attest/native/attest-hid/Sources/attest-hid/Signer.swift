// The witness key. Preferred: a P-256 key inside the Secure Enclave (CryptoKit's SecureEnclave
// API keeps the encrypted key blob in a file we own, so no keychain entitlements are needed and
// the private scalar never exists outside the chip). Fallback when no Enclave is available (Intel
// Mac without T2, VM): a software P-256 key on disk, reported honestly as `key_backend: software`.
// Signing is silent — a witness that prompted every five seconds would be unusable; the person-
// binding happens at enrollment through the browser's authenticated session.
import CryptoKit
import Foundation
import Security

final class Signer {
    enum Backend: String { case secureEnclave = "secure_enclave", software }

    let backend: Backend
    let publicKeyX963: Data          // 65 bytes: 04 || X || Y
    private let seKey: SecureEnclave.P256.Signing.PrivateKey?
    private let swKey: P256.Signing.PrivateKey?

    var publicKeyHex: String { publicKeyX963.map { String(format: "%02x", $0) }.joined() }
    var keyID: String { String(Hash.sha256Hex(publicKeyX963).prefix(16)) }

    init(dataDir: URL) throws {
        try FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true)
        let seFile = dataDir.appendingPathComponent("se-key.bin")
        let swFile = dataDir.appendingPathComponent("sw-key.bin")
        if SecureEnclave.isAvailable {
            let key: SecureEnclave.P256.Signing.PrivateKey
            if let blob = try? Data(contentsOf: seFile) {
                key = try SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: blob)
            } else {
                // .privateKeyUsage only: no biometry gate, so signatures are silent.
                var err: Unmanaged<CFError>?
                guard let access = SecAccessControlCreateWithFlags(nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly, .privateKeyUsage, &err) else {
                    throw err!.takeRetainedValue() as Error
                }
                key = try SecureEnclave.P256.Signing.PrivateKey(accessControl: access)
                try key.dataRepresentation.write(to: seFile, options: [.atomic, .completeFileProtection])
            }
            seKey = key; swKey = nil; backend = .secureEnclave
            publicKeyX963 = key.publicKey.x963Representation
        } else {
            let key: P256.Signing.PrivateKey
            if let raw = try? Data(contentsOf: swFile) {
                key = try P256.Signing.PrivateKey(rawRepresentation: raw)
            } else {
                key = P256.Signing.PrivateKey()
                try key.rawRepresentation.write(to: swFile, options: [.atomic])
                try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: swFile.path)
            }
            swKey = key; seKey = nil; backend = .software
            publicKeyX963 = key.publicKey.x963Representation
        }
    }

    /// ECDSA-P256 over SHA-256(message), DER (X9.62) encoded — what attest's `ec.verify_sha256` expects.
    func sign(_ message: Data) throws -> Data {
        if let k = seKey { return try k.signature(for: message).derRepresentation }
        return try swKey!.signature(for: message).derRepresentation
    }
}

enum Hash {
    static func sha256Hex(_ s: String) -> String { sha256Hex(Data(s.utf8)) }
    static func sha256Hex(_ d: Data) -> String { SHA256.hash(data: d).map { String(format: "%02x", $0) }.joined() }
}

enum Base64URL {
    static func encode(_ d: Data) -> String {
        d.base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
    static func decode(_ s: String) -> Data? {
        var b = s.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        while b.count % 4 != 0 { b += "=" }
        return Data(base64Encoded: b)
    }
}

/// The helper's own code-directory hash (what `codesign -dvvv` prints as CDHash). A tampered
/// binary has a different one. See docs/L3-hardware-witness.md §6 for what this does and does
/// not prove — it is data in the report, pinned by the server, not a hardware attestation.
enum SelfIdentity {
    static func cdhash() -> String {
        var code: SecCode?
        guard SecCodeCopySelf(SecCSFlags(), &code) == errSecSuccess, let code = code else { return fallback() }
        var staticCode: SecStaticCode?
        guard SecCodeCopyStaticCode(code, SecCSFlags(), &staticCode) == errSecSuccess, let sc = staticCode else { return fallback() }
        var info: CFDictionary?
        guard SecCodeCopySigningInformation(sc, SecCSFlags(), &info) == errSecSuccess,
              let dict = info as? [String: Any], let unique = dict[kSecCodeInfoUnique as String] as? Data else { return fallback() }
        return unique.map { String(format: "%02x", $0) }.joined()
    }

    private static func fallback() -> String {
        // Unsigned binary: hash the executable file itself and say so.
        let path = Bundle.main.executablePath ?? CommandLine.arguments[0]
        guard let data = FileManager.default.contents(atPath: path) else { return "unsigned:unknown" }
        return "unsigned:" + Hash.sha256Hex(data).prefix(40)
    }
}
