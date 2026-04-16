import Foundation

struct CLIError: Error, CustomStringConvertible {
    let description: String
}

func jsonValue(_ value: Any) -> String {
    guard JSONSerialization.isValidJSONObject(value),
          let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]),
          let text = String(data: data, encoding: .utf8) else {
        return #"{"ok":false,"data":null,"error":"failed to encode JSON"}"#
    }
    return text
}

func result(ok: Bool, data: Any? = nil, error: String? = nil) -> [String: Any] {
    [
        "ok": ok,
        "data": data ?? NSNull(),
        "error": error ?? NSNull()
    ]
}

func ping() -> [String: Any] {
    result(ok: true, data: ["message": "pong"])
}

func probePermissions() -> [String: Any] {
    // First-version skeleton only. Future commands such as set-travel-time-ui
    // can add Accessibility checks and Calendar.app UI automation here.
    result(
        ok: true,
        data: [
            "helper": "calendar_ui_helper",
            "purpose": "UI scripting helper for Calendar.app",
            "requiresAccessibilityPermission": true,
            "status": "skeleton only; no Calendar UI operation was attempted"
        ]
    )
}

func usage() -> [String: Any] {
    result(
        ok: false,
        data: [
            "commands": [
                "ping",
                "probe-permissions"
            ]
        ],
        error: "unknown or invalid command"
    )
}

let args = Array(CommandLine.arguments.dropFirst())
let output: [String: Any]

switch args.first {
case "ping":
    output = ping()
case "probe-permissions":
    output = probePermissions()
default:
    output = usage()
}

print(jsonValue(output))
exit((output["ok"] as? Bool) == true ? 0 : 1)
