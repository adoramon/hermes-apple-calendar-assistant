# v2 Roadmap

This document tracks the v2.0-alpha direction without expanding the current
project boundary beyond Apple Calendar workflows.

## v2.0-alpha

Implemented or in progress:

- Natural-language event draft parsing with `scripts/nlp_event_parser.py`
- Confirmation-first create flow through `scripts/interactive_create.py`
- Default conflict checking for create drafts with `--check-conflict`
- Single-calendar conflict checking with `scripts/conflict_checker.py`
- Reminder candidate scanning with `scripts/reminder_worker.py scan`
- Reminder idempotency through `data/reminder_seen.json`
- launchd templates for flight location enhancement and reminder scanning

Safety boundaries:

- All normal writes still require confirmation
- `飞行计划` is not writable through normal create, update, or delete
- Flight location enhancement only writes the original event `location`
- Reminder worker does not send WeChat, Telegram, network calls, system
  notifications, or Calendar alarms
- Hermes conversations do not perform continuous monitoring

## Later v2 Work

Potential follow-up work:

- Broaden natural-language parsing coverage while keeping deterministic rules
- Add multi-calendar conflict checks
- Add reminder delivery adapters behind explicit opt-in configuration
- Add richer tests around date parsing, suggested slots, and reminder idempotency
- Improve update/delete candidate selection before confirmation

Still out of scope:

- Contacts integration
- Birthday and lunar birthday workflows
- Travel Time automation
- Extra flight preparation events
- Native Swift helper work
