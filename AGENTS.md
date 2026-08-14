# AGENTS.md — Virtual Band

## What this is
A personal tool: acoustic guitar audio is analyzed in real time and drives
existing UJAM virtual instruments (hosted in Ableton Live) via generated
MIDI, so they accompany the player like a live band.

## Current phase
Phase 0 — proving core technical viability only: audio capture, MIDI
output, and whether a UJAM instrument can be triggered live with
acceptable latency. NOT building chord recognition. NOT building
arrangement/humanization logic. NOT building a plugin.

## Non-negotiable architecture — flag it to me before changing any of this
- Standalone Python app, not a DAW plugin, for the foreseeable future.
- Two-tier timing model: a tight, low-latency loop owns beat/pulse
  tracking and MIDI-out timing; a separate, slower "brain" loop (later
  phases) owns chord/section/arrangement decisions. Keep these decoupled
  from day one, even while the brain loop doesn't exist yet.
- Sound generation = existing UJAM instruments hosted in Ableton Live,
  driven through a virtual MIDI port. Do not host VST3 plugins in-process.
  Do not try to bypass Ableton.
- Every analysis module must be runnable and testable offline against a
  recorded .wav fixture with a hand-labeled expected output — not just
  "runs live, seems fine." Add a fixture test in the same task you add
  the module, not later.

## Explicitly out of scope right now
- VST3/AU packaging, JUCE, any C++.
- Chord/harmony recognition (Phase 0 is rhythm/timing only).
- Arrangement intelligence, humanization, section detection, song memory.
- New frameworks, databases, web servers, or dependencies beyond the
  stack listed below, without asking first.
- Refactoring anything outside the current task's stated scope.

## Stack — don't swap without asking
- Python 3.x, numpy/scipy as needed.
- One real-time audio library (sounddevice or PyAudio — pick one at
  Phase 0 kickoff, don't mix both).
- python-rtmidi / mido for MIDI.
- pytest for tests.

## Working style
- Simplest thing that meets the stated acceptance criteria. No added
  config options, abstractions, or "future-proofing" beyond what the
  current task needs.
- If a task seems to require an architecture change, stop and explain
  why instead of proceeding.
- If a decision is a judgment call (especially anything musical), ask
  rather than guess.
- One task = one feature branch. Never commit to main. Never merge,
  push, force-push, or rewrite history — that's done by the human.
- Small, scoped commits with messages that say what and why.

## Where to find context
- docs/architecture.md — current-state architecture (source of truth,
  keep it updated as we build)
- docs/decisions.md — running decision log, most recent first