// A minimal HTTP/1.1 responder on 127.0.0.1 — the helper's mailbox for the browser. It never opens
// outbound connections and never holds a token; the browser relays statements to the attest server.
// CORS headers are emitted only for allow-listed origins, so an arbitrary page cannot drive it.
import Foundation
import Network

struct HTTPRequest {
    let method: String
    let path: String
    let query: [String: String]
    let headers: [String: String]
    let body: Data

    func json() -> [String: Any]? {
        (try? JSONSerialization.jsonObject(with: body)) as? [String: Any]
    }
}

struct HTTPResponse {
    var status: Int
    var body: Any?                // JSON-serialisable
    static func ok(_ body: Any) -> HTTPResponse { HTTPResponse(status: 200, body: body) }
    static func error(_ status: Int, _ message: String) -> HTTPResponse { HTTPResponse(status: status, body: ["error": message]) }
}

final class LocalServer {
    private let listener: NWListener
    private let queue = DispatchQueue(label: "attest-hid.http")
    private let allowedOrigins: Set<String>
    private let route: (HTTPRequest) -> HTTPResponse

    init(port: UInt16, allowedOrigins: [String], route: @escaping (HTTPRequest) -> HTTPResponse) throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: NWEndpoint.Port(rawValue: port)!)
        params.allowLocalEndpointReuse = true
        listener = try NWListener(using: params)
        self.allowedOrigins = Set(allowedOrigins)
        self.route = route
    }

    func start() {
        listener.newConnectionHandler = { [weak self] conn in self?.serve(conn) }
        listener.stateUpdateHandler = { st in
            if case .failed(let e) = st { FileHandle.standardError.write(Data("[attest-hid] listener failed: \(e)\n".utf8)) }
            if Debug.on { FileHandle.standardError.write(Data("[attest-hid] listener \(st)\n".utf8)) }
        }
        listener.start(queue: queue)
    }

    private func serve(_ conn: NWConnection) {
        var buffer = Data()
        func readMore() {
            conn.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
                guard let self = self else { return }
                if let data = data { buffer.append(data) }
                if let req = self.parse(buffer) {
                    self.respond(conn, req)
                } else if isComplete || error != nil || buffer.count > 4_000_000 {
                    conn.cancel()
                } else {
                    readMore()
                }
            }
        }
        conn.stateUpdateHandler = { st in
            if Debug.on { FileHandle.standardError.write(Data("[attest-hid] conn \(st)\n".utf8)) }
            if case .ready = st { readMore() }
            if case .failed = st { conn.cancel() }
        }
        conn.start(queue: queue)
    }

    private func parse(_ data: Data) -> HTTPRequest? {
        guard let headerEnd = data.range(of: Data("\r\n\r\n".utf8)) else { return nil }
        guard let head = String(data: data[..<headerEnd.lowerBound], encoding: .utf8) else { return nil }
        var lines = head.components(separatedBy: "\r\n")
        let requestLine = lines.removeFirst().split(separator: " ")
        guard requestLine.count >= 2 else { return nil }
        var headers: [String: String] = [:]
        for line in lines {
            if let i = line.firstIndex(of: ":") {
                headers[line[..<i].lowercased()] = line[line.index(after: i)...].trimmingCharacters(in: .whitespaces)
            }
        }
        let length = Int(headers["content-length"] ?? "0") ?? 0
        let bodyStart = headerEnd.upperBound
        guard data.count - bodyStart >= length else { return nil }
        let target = String(requestLine[1])
        let parts = target.split(separator: "?", maxSplits: 1)
        var query: [String: String] = [:]
        if parts.count == 2 {
            for kv in parts[1].split(separator: "&") {
                let p = kv.split(separator: "=", maxSplits: 1)
                query[String(p[0]).removingPercentEncoding ?? String(p[0])] = p.count == 2 ? (String(p[1]).removingPercentEncoding ?? String(p[1])) : ""
            }
        }
        return HTTPRequest(method: String(requestLine[0]), path: String(parts[0]), query: query, headers: headers,
                           body: data[bodyStart..<(bodyStart + length)])
    }

    private func respond(_ conn: NWConnection, _ req: HTTPRequest) {
        let origin = req.headers["origin"]
        var extra = ""
        if let o = origin, allowedOrigins.contains(o) {
            extra = "Access-Control-Allow-Origin: \(o)\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                + "Access-Control-Allow-Headers: content-type\r\nAccess-Control-Max-Age: 600\r\nVary: Origin\r\n"
        }
        let res: HTTPResponse
        if req.method == "OPTIONS" {
            res = HTTPResponse(status: 204, body: nil)
        } else if let o = origin, !allowedOrigins.contains(o) {
            res = .error(403, "origin not allowed")
        } else {
            res = route(req)
        }
        let body = res.body.map { try! JSONSerialization.data(withJSONObject: $0, options: [.withoutEscapingSlashes]) } ?? Data()
        let reason = [200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
                      409: "Conflict", 500: "Internal Server Error"][res.status] ?? "OK"
        var head = "HTTP/1.1 \(res.status) \(reason)\r\nContent-Type: application/json\r\nContent-Length: \(body.count)\r\n"
        head += extra + "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
        var out = Data(head.utf8)
        out.append(body)
        conn.send(content: out, completion: .contentProcessed { _ in conn.cancel() })
    }
}

enum Debug { static var on = ProcessInfo.processInfo.environment["ATTEST_HID_DEBUG"] != nil }
