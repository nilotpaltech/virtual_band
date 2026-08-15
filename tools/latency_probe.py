"""
tools/latency_probe.py
Phase 0 latency probe: audio transient → MIDI note-on round-trip timer.

What this measures
------------------
The time between:
  T1 — first 128-sample block whose RMS crosses the threshold (perf_counter()
       captured at the top of the sounddevice callback, before any math)
  T2 — perf_counter() captured in the main thread immediately before
       mido sends note_on

(T2 - T1) is the Python detect-to-send latency. It does NOT include
downstream DAW or speaker latency.

Buffer size: 128 samples @ 48 kHz (~2.67 ms/block) — from decisions.md.

NOTE: Uses WASAPI shared mode (not exclusive) so the probe can run
alongside Ableton without fighting over the device. Exclusive mode
would give lower latency but requires Ableton to release the interface.

Usage
-----
    python tools/latency_probe.py [options]

Options
-------
    --port        loopMIDI port name substring (default: VirtualBand)
    --n           number of claps/attacks to collect (default: 10)
    --thresh      RMS threshold for transient detection (default: 0.05)
    --note        MIDI note number to send on detection (default: 60)
    --refractory  minimum gap between detections in ms (default: 200)
"""

import argparse
import queue
import statistics
import time
from typing import Optional

import mido
import numpy as np
import sounddevice as sd

# From decisions.md: 128 samples @ 48 kHz
BUFFER_SIZE   = 128
SAMPLE_RATE   = 48_000
NOTE_OFF_DELAY = 0.05  # seconds: hold note-on this long before note-off


# ---------------------------------------------------------------------------
# Port helpers (shared pattern with the other tools/ scripts)
# ---------------------------------------------------------------------------

def find_midi_port(target: str) -> Optional[str]:
    for name in mido.get_output_names():
        if target.lower() in name.lower():
            return name
    return None


def find_audio_device() -> Optional[int]:
    """Return the WASAPI device index for 'Line (Komplete Audio 1)'."""
    wasapi_idx = None
    for i, api in enumerate(sd.query_hostapis()):
        if "Windows WASAPI" in api["name"]:
            wasapi_idx = i
            break
    if wasapi_idx is None:
        return None
    for i, d in enumerate(sd.query_devices()):
        if (d["hostapi"] == wasapi_idx
                and "Komplete Audio" in d["name"]
                and d["max_input_channels"] > 0):
            return i
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Audio → MIDI latency probe")
    parser.add_argument("--port",       default="VirtualBand",
                        help="loopMIDI output port name (substring match)")
    parser.add_argument("--n",          type=int,   default=10,
                        help="Number of transients to collect (default: 10)")
    parser.add_argument("--thresh",     type=float, default=0.05,
                        help="RMS transient threshold (default: 0.05)")
    parser.add_argument("--note",       type=int,   default=60,
                        help="MIDI note to send on detection (default: 60 = C3)")
    parser.add_argument("--refractory", type=int,   default=200,
                        help="Minimum ms between detections (default: 200)")
    args = parser.parse_args()

    # --- Resolve MIDI port ------------------------------------------------
    port_name = find_midi_port(args.port)
    if port_name is None:
        print(f"ERROR: No MIDI output port matching {args.port!r}.\n")
        available = mido.get_output_names()
        if available:
            print("Available ports:")
            for p in available:
                print(f"  {p!r}")
        else:
            print("No MIDI output ports found — is loopMIDI running?")
        return

    # --- Resolve audio device ---------------------------------------------
    audio_device = find_audio_device()
    if audio_device is None:
        print("ERROR: Could not find 'Line (Komplete Audio 1)' WASAPI input.")
        print("Available WASAPI inputs:")
        for i, d in enumerate(sd.query_devices()):
            for api in sd.query_hostapis():
                if "WASAPI" in api["name"] and d["hostapi"] == list(sd.query_hostapis()).index(api):
                    if d["max_input_channels"] > 0:
                        print(f"  [{i}] {d['name']}")
        return

    dev_info    = sd.query_devices(audio_device)
    sample_rate = int(dev_info["default_samplerate"])  # should be 48000

    print(f"Audio : [{audio_device}] {dev_info['name']} @ {sample_rate} Hz, "
          f"blocksize={BUFFER_SIZE}")
    print(f"MIDI  : {port_name!r}  note={args.note}")
    print(f"Thresh: {args.thresh}  refractory={args.refractory} ms  n={args.n}")
    print()

    # Queue carries: (t_detect: float)  — perf_counter at callback entry
    detect_q: queue.Queue = queue.Queue()

    # Shared state accessed only from the audio callback thread
    last_detect_time: list = [-999.0]   # list so closure can mutate it
    refractory_s = args.refractory / 1000.0

    # --- Audio callback ---------------------------------------------------
    def audio_callback(indata: np.ndarray, frames: int,
                       time_info, status) -> None:
        # Capture timestamp first — before any processing
        t_now = time.perf_counter()

        if status:
            pass  # don't print from callback; would cause priority inversion

        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        if (rms >= args.thresh
                and (t_now - last_detect_time[0]) >= refractory_s):
            last_detect_time[0] = t_now
            try:
                detect_q.put_nowait(t_now)
            except queue.Full:
                pass   # main thread is falling behind; skip this event

    # --- Session loop -----------------------------------------------------
    latencies_ms: list = []
    collected = 0

    note_on  = mido.Message("note_on",  note=args.note, velocity=100, channel=0)
    note_off = mido.Message("note_off", note=args.note, velocity=0,   channel=0)

    # Shared WASAPI mode: coexists with Ableton on the same device.
    # Exclusive mode halves latency but requires Ableton to not hold the device.
    wasapi_settings = sd.WasapiSettings(exclusive=False)

    try:
        midi_out_cm  = mido.open_output(port_name)
        audio_in_cm  = sd.InputStream(device=audio_device,
                                      channels=1,
                                      samplerate=sample_rate,
                                      blocksize=BUFFER_SIZE,
                                      extra_settings=wasapi_settings,
                                      callback=audio_callback)
    except Exception as exc:
        print(f"\nERROR opening streams: {exc}")
        print("Tip: if Ableton is running in exclusive WASAPI mode, close it or")
        print("     switch its audio driver to shared mode, then retry.")
        return

    with midi_out_cm as midi_out, audio_in_cm:
        print(f"Listening — give me {args.n} sharp claps or hard pick attacks.\n")
        print(f"{'Clap':>6}  {'Detect→Send (ms)':>18}")
        print("-" * 28)

        while collected < args.n:
            try:
                t_detect = detect_q.get(timeout=30)
            except queue.Empty:
                print("Timed out waiting for a transient (30 s).")
                break

            # Send MIDI as soon as we're unblocked from the queue
            t_send = time.perf_counter()
            midi_out.send(note_on)

            elapsed_ms = (t_send - t_detect) * 1000.0
            latencies_ms.append(elapsed_ms)
            collected += 1

            print(f"#{collected:>5}  {elapsed_ms:>17.2f} ms")

            # Note-off after a short hold (non-blocking relative to detection)
            time.sleep(NOTE_OFF_DELAY)
            midi_out.send(note_off)

    # --- Summary ----------------------------------------------------------
    print()
    if len(latencies_ms) < 2:
        print("Not enough samples for statistics.")
        return

    print("=" * 28)
    print(f"  Samples : {len(latencies_ms)}")
    print(f"  Min     : {min(latencies_ms):.2f} ms")
    print(f"  Median  : {statistics.median(latencies_ms):.2f} ms")
    print(f"  Max     : {max(latencies_ms):.2f} ms")
    print("=" * 28)
    print()
    print("Note: this is Python detect-to-send latency only.")
    print("Downstream DAW/speaker latency is not included.")


if __name__ == "__main__":
    main()
