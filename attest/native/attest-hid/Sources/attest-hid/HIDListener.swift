// Raw HID keyboard listener. Reports (timestamp, device) for every physical key-DOWN and nothing
// else: no usages (which key), no key-ups, no auto-repeats (the OS generates those, the device
// does not). Synthetic events (AppleScript `keystroke`, CGEventPost, dispatchEvent) never appear
// here because they were never HID reports — that is the whole point of the witness.
import Foundation
import IOKit
import IOKit.hid

struct KeyDown {
    let t: Int64          // Unix ms, derived from the report's mach timestamp
    let device: DeviceID
}

struct DeviceID: Hashable {
    let id: String        // "05ac:0341#9f2c" — vendor:product + short hash of location|serial
    let builtin: Bool
}

final class HIDListener {
    private var manager: IOHIDManager?
    private let onKeyDown: (KeyDown) -> Void
    private var deviceCache: [IOHIDDevice: DeviceID] = [:]
    private let clock = MachClock()

    init(onKeyDown: @escaping (KeyDown) -> Void) {
        self.onKeyDown = onKeyDown
    }

    /// TCC state for Input Monitoring without prompting (safe to call from a request handler).
    static func checkAccess() -> String {
        switch IOHIDCheckAccess(kIOHIDRequestTypeListenEvent) {
        case kIOHIDAccessTypeGranted: return "granted"
        case kIOHIDAccessTypeDenied: return "denied"
        default: return "unknown"
        }
    }

    /// Ask the system to prompt when the state is unknown (first launch). May block briefly.
    static func requestAccess() -> String {
        let state = checkAccess()
        if state != "unknown" { return state }
        return IOHIDRequestAccess(kIOHIDRequestTypeListenEvent) ? "granted" : "unknown"
    }

    func start() -> Bool {
        let m = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
        let matching: [[String: Any]] = [
            [kIOHIDDeviceUsagePageKey as String: kHIDPage_GenericDesktop, kIOHIDDeviceUsageKey as String: kHIDUsage_GD_Keyboard],
            [kIOHIDDeviceUsagePageKey as String: kHIDPage_GenericDesktop, kIOHIDDeviceUsageKey as String: kHIDUsage_GD_Keypad],
        ]
        IOHIDManagerSetDeviceMatchingMultiple(m, matching as CFArray)
        let ctx = Unmanaged.passUnretained(self).toOpaque()
        IOHIDManagerRegisterInputValueCallback(m, { context, _, _, value in
            guard let context = context else { return }
            Unmanaged<HIDListener>.fromOpaque(context).takeUnretainedValue().handle(value)
        }, ctx)
        IOHIDManagerScheduleWithRunLoop(m, CFRunLoopGetMain(), CFRunLoopMode.defaultMode.rawValue)
        let rc = IOHIDManagerOpen(m, IOOptionBits(kIOHIDOptionsTypeNone))
        manager = m
        return rc == kIOReturnSuccess
    }

    private func handle(_ value: IOHIDValue) {
        let element = IOHIDValueGetElement(value)
        // Keyboard/Keypad usage page; usages 4...0xE7 are keys (0xE0–0xE7 are modifiers — counted:
        // hardware may see more than the editor, never fewer). Value 1 = down; 0 = up (ignored).
        guard IOHIDElementGetUsagePage(element) == UInt32(kHIDPage_KeyboardOrKeypad) else { return }
        let usage = IOHIDElementGetUsage(element)
        guard usage >= 4, usage <= 0xE7, IOHIDValueGetIntegerValue(value) == 1 else { return }
        let device = IOHIDElementGetDevice(element)
        let id = deviceCache[device] ?? identify(device)
        deviceCache[device] = id
        onKeyDown(KeyDown(t: clock.unixMs(fromMach: IOHIDValueGetTimeStamp(value)), device: id))
    }

    private func identify(_ device: IOHIDDevice) -> DeviceID {
        func num(_ key: String) -> Int { (IOHIDDeviceGetProperty(device, key as CFString) as? NSNumber)?.intValue ?? 0 }
        func str(_ key: String) -> String { (IOHIDDeviceGetProperty(device, key as CFString) as? String) ?? "" }
        let vendor = num(kIOHIDVendorIDKey as String), product = num(kIOHIDProductIDKey as String)
        let location = num(kIOHIDLocationIDKey as String)
        let serial = str(kIOHIDSerialNumberKey as String)
        let transport = str(kIOHIDTransportKey as String)
        let name = str(kIOHIDProductKey as String)
        let tag = Hash.sha256Hex("\(location)|\(serial)").prefix(4)
        let builtin = transport == "SPI" || name.localizedCaseInsensitiveContains("Apple Internal")
            || (vendor == 0x05ac && transport != "USB" && transport != "Bluetooth")
        if vendor == 0 && product == 0 {
            let slug = (transport.isEmpty ? "hid" : transport.lowercased()) + ":" + (name.isEmpty ? "keyboard" : name.lowercased().replacingOccurrences(of: " ", with: "-"))
            return DeviceID(id: "\(slug)#\(tag)", builtin: builtin)
        }
        return DeviceID(id: String(format: "%04x:%04x#%@", vendor, product, String(tag)), builtin: builtin)
    }
}

/// Converts mach_absolute_time stamps (what IOHID reports carry) to Unix milliseconds using an
/// offset measured once, so witness windows live on the same clock as the browser's Date.now().
final class MachClock {
    private let numer: Double
    private let denom: Double
    private let offsetMs: Double

    init() {
        var info = mach_timebase_info_data_t()
        mach_timebase_info(&info)
        numer = Double(info.numer); denom = Double(info.denom)
        let machNowMs = Double(mach_absolute_time()) * numer / denom / 1_000_000
        offsetMs = Date().timeIntervalSince1970 * 1000 - machNowMs
    }

    func unixMs(fromMach t: UInt64) -> Int64 {
        Int64(Double(t) * numer / denom / 1_000_000 + offsetMs)
    }

    static func nowMs() -> Int64 { Int64(Date().timeIntervalSince1970 * 1000) }
}

/// HIDIdleTime from the IORegistry: nanoseconds since the last physical input of any kind.
enum IdleTime {
    static func ms() -> Int64 {
        let service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOHIDSystem"))
        guard service != 0 else { return 0 }
        defer { IOObjectRelease(service) }
        let prop = IORegistryEntryCreateCFProperty(service, "HIDIdleTime" as CFString, kCFAllocatorDefault, 0)
        let ns = (prop?.takeRetainedValue() as? NSNumber)?.int64Value ?? 0
        return ns / 1_000_000
    }
}
