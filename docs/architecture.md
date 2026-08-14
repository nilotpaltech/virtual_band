# Architecture — current state

Last updated: [date] (Phase 0, Task 1)

## Settled decisions
- Standalone Python app, not a DAW plugin.
- Sound generation: existing UJAM instruments hosted in Ableton Live,
  driven via a virtual MIDI port. No in-process plugin hosting.
- Two-tier timing model: a tight low-latency loop (audio capture →
  onset/pulse detection → MIDI out) is decoupled from a slower "brain"
  loop (chord/section/arrangement decisions, not yet built).
- Every analysis module must have an offline fixture test
  (see tests/fixtures/, tools/offline_cli.py).

## Current modules
(none yet — filled in as Phase 0 tasks land)

## Deferred / not yet decided
- Whether virtual-MIDI-into-Ableton latency is acceptable, or an
  in-process VST3 host becomes necessary (see docs/decisions.md).
- Chord recognition approach (chroma template matching planned,
  unconfirmed).
- Everything from Phase 2 onward.

## Background
Full feasibility/architecture rationale: see
docs/feasibility-consultation.md (historical — not updated; that file
is the reasoning that led here, this file is the current source of truth).