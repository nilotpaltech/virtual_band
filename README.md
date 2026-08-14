# Virtual Band

A personal tool: I play acoustic guitar, software listens in real time
and drives virtual instruments (UJAM, via Ableton Live) to accompany me
like a live band.

**Status:** Phase 0 — proving core latency/audio/MIDI viability. No
chord recognition or arrangement logic yet.

See `AGENTS.md` for agent working rules, `docs/architecture.md` for
current architecture, `docs/decisions.md` for decision history.

## Setup
1. Ensure you are using **Python 3.9** (newer versions may not have pre-compiled wheels for all audio libraries).
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install the project requirements:
   ```bash
   pip install -e ".[dev]"
   ```

## Running the Smoke Test
The first task for Phase 0 is to test the audio input latency floor.

1. Connect your audio interface.
2. Run the smoke test script:
   ```bash
   python audio_io/smoke_test.py
   ```
This script uses WASAPI Exclusive Mode to achieve ultra-low latency without requiring ASIO. It will automatically detect your input device and run a 5-second RMS volume check at buffer sizes of 128, 256, and 512 samples to test for dropouts.