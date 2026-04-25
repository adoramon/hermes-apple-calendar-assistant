# ADR-001: Real Send Channel

## Status

Accepted for design direction. Not implemented.

## Context

The project has completed a local dry-run reminder/outbox chain:

```text
Apple Calendar
  -> reminder_worker
  -> message_adapter
  -> outbox_messages.jsonl
  -> outbox_consumer
  -> channel_sender
  -> hermes_dispatcher dry-run
  -> sent_dry_run
```

Real sending is still disabled. The next decision is which channel should own
the final outbound delivery.

## Options

Option A: Hermes local callback / local CLI.

The calendar assistant passes outbound messages to Hermes locally. Hermes owns
final dispatch.

Option B: Telegram Bot API.

The calendar assistant directly calls Telegram Bot API.

Option C: WeChat channel.

The calendar assistant drives Hermes WeChat profile or local WeChat automation.

## Decision

Choose Option A as the recommended direction.

Do not choose Option B or Option C for now.

## Rationale

- Do not store Telegram tokens or WeChat credentials in this project.
- Do not let this project directly request external network send APIs.
- Do not bypass Hermes scheduling, permission, audit, and confirmation logic.
- Keep this project focused on Calendar reading, drafting, outbox generation,
  and local handoff.
- Let Hermes decide how and whether to actually deliver messages.

## Required Confirmations Before Implementation

- Confirm whether Hermes supports a local dispatch CLI.
- Confirm whether `sunny-wechat-lite` exposes an outbound message API.
- Confirm whether a profile-local tool or handler is needed.
- Confirm whether the user must provide a second confirmation before real send.
- Confirm audit, retry, dedupe, rollback, and emergency disable behavior.

## Consequences

- Real send remains unavailable in this repository.
- `real_send_enabled` remains `false`.
- `real_send_gate.enabled` remains `false`.
- `hermes_dispatcher.py` remains a dry-run placeholder until Hermes dispatch
  capabilities are confirmed.
