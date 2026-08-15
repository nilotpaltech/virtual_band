# Decisions log (most recent first)
- 2026-08-15 — Offline beat tracking evaluation complete. Evaluated `aubio.tempo` against our naive IOI `PulseEstimator`. Selected `aubio` because it is streaming-capable (unlike `librosa` or `madmom`). Discovered that both algorithms successfully extracted a ~120 BPM quarter-note pulse from real noisy guitar strumming (despite manual ground-truth annotations being sparsely marked at half-time). Proved `aubio` is viable for live pulse tracking on guitar transients.
- 2026-08-15 — ASIO initialization freeze workaround: KoordASIO triggers a device-reset upon client connection, which freezes Ableton's audio engine if Ableton is already using it. Workaround: Start the Python audio stream first, let the stream open and sleep for ~2 seconds to let the driver stabilize, and *then* initialize/restart Ableton's audio driver.
- 2026-08-15 — Added a ±5 BPM hysteresis to the IOI `PulseEstimator` to prevent erratic tempo jumping during continuous live strumming.
- 2026-08-15 — Task 8 pulse-following design: tempo estimated as median IOI over an 8-slot sliding window (median chosen for outlier resistance over mean). IOI guard rails: 300 ms–1200 ms (50–200 BPM). Doubles (short IOIs < 300 ms) discarded before entering window. Missed beats (IOI > 1.6× current estimate) folded back by halving before storing. Phase correction: 0.15-weight nudge of next_beat_time toward nearest expected beat boundary on each accepted onset. Pattern: kick (MIDI note 36) every beat. Tick thread coasts indefinitely at last known tempo when strumming stops. MIDI starts after 2 accepted IOIs.
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