# Decisions log (most recent first)

- 2026-08-14 — Buffer size of 128 samples selected for the real-time audio input stream. The smoke test verified stability at 128, 256, and 512 samples under Windows WASAPI Exclusive mode on Komplete Audio 1 with 0 dropouts/xruns; 128 samples is chosen to achieve the lowest possible input latency (~2.67ms at 48kHz).
- [date] — Phase 0 scope locked: rhythm/timing only, no chords, no
  plugin. Exit criteria: audible live reaction to strumming, with a
  measured latency number, before Phase 1 begins.
- [date] — Sound generation goes through existing UJAM instruments in
  Ableton Live via virtual MIDI, not an in-process plugin host, for
  the prototype. Revisit only if the latency measurement (Task 5)
  says otherwise.
- [date] — Standalone app chosen over plugin for the prototype;
  plugin packaging deferred indefinitely.
- [date] — Python chosen as primary language; C++/JUCE deferred
  until the musical logic is proven, if ever.