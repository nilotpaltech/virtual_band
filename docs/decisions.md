# Decisions log (most recent first)
- 2026-08-15 — Root cause of ~300ms perceived delay: Komplete Audio 1 doesn't support multi-client ASIO; Ableton falls back to DirectSound (high output latency) when Python needs simultaneous input access. Fixed by routing both Ableton and Python through KoordASIO (shared-mode ASIO wrapper) instead of native NI driver. Result: ~90ms guitar-to-drum-sound, measured via phone recording. This is now the Phase 0 latency baseline. Task 7 raw onset→hit: latency acceptable (~90ms), but detector produces occasional doubles/misses/brief chaotic bursts on live strumming. Expected — deferring to Task 8's pulse-following to absorb this rather than over-tuning the raw detector.

- 2026-08-15 — Komplete Audio 1 only supports one ASIO client at a time. Current workaround: Python holds the device via WASAPI exclusive mode, Ableton runs on DirectSound. Tradeoff: Python input latency is good, Ableton output latency may be worse than native ASIO. Revisit if output latency becomes the bottleneck.

- 2026-08-15 — Fine-tuned the energy-based onset detector for acoustic guitar strumming. A threshold of 0.15 combined with a refractory period of 480.0 ms reliably ignores the ringing tail of a chord and registers a single hit per strum without missing quiet strums for the most part. This is not yet perfect.

- 2026-08-14 — Phase 0 Python detect-to-send latency measured at **min 0.05 ms / median 0.08 ms / max 0.11 ms** (10 samples, WASAPI shared mode, Line (Komplete Audio 1) @ 48 kHz / blocksize 128, VirtualBand loopMIDI port). This is Python-only latency (audio callback threshold cross → mido note_on sent); downstream Ableton/UJAM/speaker latency is not included. Result confirms Python is not the bottleneck in the signal chain.
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