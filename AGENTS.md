# Project Context

This project builds a custom Hermes skill for macOS Apple Calendar integration.

## Goal
The skill must support:
1. Conversational calendar CRUD for Hermes
2. Interactive confirmation before create/update/delete
3. Flight-calendar enhancement workflow
4. Birthday reminder workflow at 07:00

## Runtime
- macOS only
- Uses Calendar.app through osascript / AppleScript
- Deployed into Hermes profile: sunny-wechat-lite
- Tested through the Hermes WeChat assistant

## Code Rules
- Python 3.11+
- Use standard library first
- Keep scripts modular and small
- All destructive actions require confirmation
- Output logs clearly
- Never hardcode personal secrets
- Use JSON files for state and pending confirmation storage

## File Responsibilities
- scripts/calendar_ops.py: core CRUD operations
- scripts/interactive_create.py: slot filling and confirmation workflow
- scripts/flight_watcher.py: detect new flight events and propose enhancements
- scripts/birthday_notifier.py: morning birthday reminder generation
- scripts/util.py: shared helpers
- SKILL.md: Hermes skill instructions
- config/settings.json: runtime config

## Safety Rules
- Never delete or modify calendar events without explicit confirmation
- For flight enhancement, always ask for confirmation before writing back
- If birthday age cannot be determined, generate message without age