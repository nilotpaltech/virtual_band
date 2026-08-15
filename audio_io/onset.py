"""
Continuous energy-based onset detector for the live audio stream.
"""
import time
from typing import Optional, Callable

import numpy as np
import sounddevice as sd

# Default settings from architecture / phase 0 decisions
BUFFER_SIZE = 128
SAMPLE_RATE = 48_000

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

class OnsetDetector:
    def __init__(self, 
                 threshold: float = 0.15, 
                 refractory_ms: float = 480.0,
                 on_onset: Optional[Callable[[float], None]] = None):
        """
        :param threshold: RMS threshold for transient detection.
        :param refractory_ms: Minimum gap between detections in milliseconds.
        :param on_onset: Optional callback taking a timestamp (perf_counter) when an onset is detected.
        """
        self.threshold = threshold
        self.refractory_s = refractory_ms / 1000.0
        self.on_onset = on_onset
        self.last_detect_time = -999.0
        self.stream: Optional[sd.InputStream] = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        # Capture timestamp before any processing
        t_now = time.perf_counter()

        if status:
            pass  # Don't print from callback; would cause priority inversion

        # Calculate RMS (Channel 2 is index 1)
        rms = float(np.sqrt(np.mean(indata[:, 1] ** 2)))
        
        if rms >= self.threshold and (t_now - self.last_detect_time) >= self.refractory_s:
            self.last_detect_time = t_now
            if self.on_onset:
                self.on_onset(t_now)

    def start(self) -> None:
        """Start the audio stream and onset detection."""
        device_idx = find_audio_device()
        if device_idx is None:
            raise RuntimeError("Could not find 'Komplete Audio 1' WASAPI input.")

        # Shared WASAPI mode to coexist with Ableton
        wasapi_settings = sd.WasapiSettings(exclusive=False)
        
        self.stream = sd.InputStream(
            device=device_idx,
            channels=2,
            samplerate=SAMPLE_RATE,
            blocksize=BUFFER_SIZE,
            extra_settings=wasapi_settings,
            callback=self._audio_callback
        )
        self.stream.start()

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

    def handle_onset(timestamp: float):
        try:
            detect_q.put_nowait(timestamp)
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
    
    print("Starting continuous onset detector...")
    print(f"Threshold: {detector.threshold}, Refractory: {detector.refractory_s * 1000} ms")
    print("Waiting for transients. Press Ctrl+C to stop.\n")
    
    try:
        detector.start()
        count = 0
        while True:
            # Block until an onset is detected
            t = detect_q.get()
            count += 1
            wall_time = time.strftime('%H:%M:%S')
            print(f"[{wall_time}] Onset #{count:>3} detected at perf_counter {t:.4f}")
            
    except KeyboardInterrupt:
        print("\nStopping detector...")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        detector.stop()
