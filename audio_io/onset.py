"""
Continuous energy-based onset detector for the live audio stream.
"""
import os
import time
from typing import Optional, Callable

# Must be set before sounddevice is imported so PortAudio loads the ASIO-enabled DLL
os.environ.setdefault("SD_ENABLE_ASIO", "1")

import mido
import numpy as np
import sounddevice as sd

# Default settings from architecture / phase 0 decisions
BUFFER_SIZE = 128
SAMPLE_RATE = 48_000
NOTE_OFF_DELAY = 0.05

def find_midi_port(target: str) -> Optional[str]:
    for name in mido.get_output_names():
        if target.lower() in name.lower():
            return name
    return None

def find_audio_device() -> Optional[int]:
    """Return the ASIO device index for KoordASIO."""
    asio_idx = None
    for i, api in enumerate(sd.query_hostapis()):
        if "ASIO" in api["name"]:
            asio_idx = i
            break
    if asio_idx is None:
        return None
    for i, d in enumerate(sd.query_devices()):
        if (d["hostapi"] == asio_idx
                and "KoordASIO" in d["name"]
                and d["max_input_channels"] > 0):
            return i
    return None

class OnsetDetector:
    def __init__(self, 
                 threshold: float = 0.16, 
                 refractory_ms: float = 495.0,
                 on_onset: Optional[Callable[[float, float], None]] = None):
        """
        :param threshold: RMS threshold for transient detection.
        :param refractory_ms: Minimum gap between detections in milliseconds.
        :param on_onset: Optional callback taking timestamps (t_buffer, t_flag) when an onset is detected.
        """
        self.threshold = threshold
        self.refractory_s = refractory_ms / 1000.0
        self.on_onset = on_onset
        self.last_detect_time = -999.0
        self.stream: Optional[sd.InputStream] = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        # Capture timestamp before any processing
        t_buffer = time.perf_counter()

        if status:
            pass  # Don't print from callback; would cause priority inversion

        # Calculate RMS (Channel 2 is index 1)
        rms = float(np.sqrt(np.mean(indata[:, 1] ** 2)))
        
        if rms >= self.threshold and (t_buffer - self.last_detect_time) >= self.refractory_s:
            t_flag = time.perf_counter()
            self.last_detect_time = t_buffer
            if self.on_onset:
                self.on_onset(t_buffer, t_flag)

    def start(self) -> None:
        """Start the audio stream and onset detection."""
        device_idx = find_audio_device()
        if device_idx is None:
            raise RuntimeError("Could not find KoordASIO input device. Is KoordASIO installed and configured?")

        dev_info = sd.query_devices(device_idx)
        api_name = sd.query_hostapis()[dev_info["hostapi"]]["name"]
        print(f"Audio Stream Opening:")
        print(f"  Device: {dev_info['name']}")
        print(f"  Driver: {api_name} (shared ASIO via KoordASIO)")

        # KoordASIO is a shared-mode ASIO driver — no WasapiSettings needed
        try:
            self.stream = sd.InputStream(
                device=device_idx,
                channels=2,
                samplerate=SAMPLE_RATE,
                blocksize=BUFFER_SIZE,
                callback=self._audio_callback,
                latency='low'
            )
            self.stream.start()
            print("  KoordASIO shared mode: SUCCESS")
        except sd.PortAudioError as e:
            print(f"  KoordASIO shared mode: FAILED")
            raise RuntimeError(f"Could not open KoordASIO stream. (Error: {e})") from e

    def stop(self) -> None:
        """Stop the audio stream."""
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

if __name__ == "__main__":
    import queue
    import sys

    # Use a queue to safely log from the main thread instead of the audio callback
    detect_q: queue.Queue = queue.Queue()

    def handle_onset(t_buffer: float, t_flag: float):
        try:
            detect_q.put_nowait((t_buffer, t_flag))
        except queue.Full:
            pass

    # To fix "multiple onsets per strum", adjust these two values:
    # 1. threshold: RMS energy required to trigger.
    #    Scale is 0.0 to 1.0. Try increasing in small steps of 0.01 (e.g., 0.06, 0.08) 
    #    to ignore softer secondary peaks in the strum.
    # 2. refractory_ms: Minimum milliseconds to wait before allowing another trigger.
    #    If a strum rings out unevenly for a while, increase this to 300.0 or 400.0 
    #    so the detector doesn't re-trigger on the tail end of the same chord.
    detector = OnsetDetector(on_onset=handle_onset)
    
    port_name = find_midi_port("VirtualBand")
    if port_name is None:
        print("ERROR: Could not find MIDI output port matching 'VirtualBand'.")
        sys.exit(1)

    print("Available ASIO Input Devices:")
    hostapis = sd.query_hostapis()
    for i, d in enumerate(sd.query_devices()):
        if "ASIO" in hostapis[d["hostapi"]]["name"] and d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']} (API: {hostapis[d['hostapi']]['name']})")
    print()

    print("Starting continuous onset detector...")
    print(f"Threshold: {detector.threshold}, Refractory: {detector.refractory_s * 1000} ms")
    print(f"MIDI Port: {port_name}")
    print("Waiting for transients. Press Ctrl+C to stop.\n")
    
    try:
        midi_out = mido.open_output(port_name)
        note_on = mido.Message("note_on", note=36, velocity=100, channel=0)
        note_off = mido.Message("note_off", note=36, velocity=0, channel=0)
        
        detector.start()
        print(f"Reported stream input latency: {detector.stream.latency * 1000.0:.2f} ms\n")
        
        count = 0
        while True:
            # Block until an onset is detected
            t_buffer, t_flag = detect_q.get()
            
            # Immediately send note on
            t_midi = time.perf_counter()
            midi_out.send(note_on)
            
            count += 1
            wall_time = time.strftime('%H:%M:%S')
            
            delta_buffer_flag = (t_flag - t_buffer) * 1000.0
            delta_flag_midi = (t_midi - t_flag) * 1000.0
            
            print(f"[{wall_time}] Onset #{count:>3} | buf->flag: {delta_buffer_flag:>5.2f} ms | flag->midi: {delta_flag_midi:>5.2f} ms -> Kick")
            
            # Sleep briefly and send note off
            time.sleep(NOTE_OFF_DELAY)
            midi_out.send(note_off)
            
    except KeyboardInterrupt:
        print("\nStopping detector...")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        detector.stop()
        if 'midi_out' in locals():
            midi_out.close()
