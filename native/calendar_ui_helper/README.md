# calendar_ui_helper

Minimal macOS Swift CLI skeleton for future Calendar.app UI scripting tests.

## Build

```bash
swift build -c release
```

## Commands

```bash
./.build/release/calendar_ui_helper ping
```

```bash
./.build/release/calendar_ui_helper probe-permissions
```

This helper is intended for future UI scripting experiments, such as setting
Calendar.app Travel Time through the app UI. It will require Accessibility
permissions when real UI automation is added.
