"""
Pulse estimator: maintains a running tempo/phase estimate from onset timestamps
and drives a repeating kick pattern locked to that estimate.

Tolerates occasional doubled or missed onsets:
- Doubled onsets produce very short IOIs which are discarded (< MIN_IOI_S).
- Missed beats produce long IOIs which are halved before storing (fold-back).
- Tempo is the median of a fixed-size window, not the mean, so single outliers
  are ignored without special-casing.

The tick thread runs independently of the onset detector and coasts at the last
known tempo indefinitely when no new onsets arrive.
"""
import statistics
import threading
import time
from collections import deque
from typing import Optional

import mido

# Guard rails for plausible beat periods (50-200 BPM)
MIN_IOI_S = 0.300   # 200 BPM
MAX_IOI_S = 1.200   # 50 BPM

# If an IOI is this many times longer than the current estimate, treat it as a
# missed beat and halve it before storing.
FOLD_THRESHOLD = 1.6

# Phase correction weight per onset (0 = ignore, 1 = snap immediately).
# 0.15 nudges the next beat a little toward the observed onset without lurching.
PHASE_ALPHA = 0.15

# If the new median tempo estimate is within this many BPM of the current estimate,
# don't update — absorbs human timing variation without thrashing the tempo.
BPM_HYSTERESIS = 5.0

# How long a note-on is held before sending note-off (seconds)
NOTE_OFF_DELAY = 0.05

# Minimum accepted IOIs before the tick thread starts firing MIDI
MIN_IOIS_TO_START = 2


class PulseEstimator:
    """
    Estimates beat period from onset timestamps and fires a kick drum on each beat.

    Usage:
        pulse = PulseEstimator()
        pulse.start(midi_out, note_on, note_off)  # starts tick thread
        # in main loop:
        pulse.accept_onset(t)   # call with each onset timestamp (perf_counter)
        # on shutdown:
        pulse.stop()
    """

    def __init__(self, window_size: int = 8):
        self._iois: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._tempo_s: Optional[float] = None
        self._next_beat_time: Optional[float] = None
        self._last_onset_time: Optional[float] = None
        self._accepted_iois: int = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._first_beat_fired = False
        self._midi_out: Optional[mido.ports.BaseOutput] = None
        self._note_on: Optional[mido.Message] = None
        self._note_off: Optional[mido.Message] = None

    def accept_onset(self, t: float) -> tuple:
        """
        Update the tempo estimate with a new onset at time t (perf_counter seconds).
        Call this from the main thread for each detected onset.
        Returns (accepted: bool, bpm: float | None) for diagnostic logging.
        """
        with self._lock:
            if self._last_onset_time is None:
                # First ever onset -- just anchor the reference time
                self._last_onset_time = t
                return False, None

            ioi = t - self._last_onset_time

            # Discard implausibly short IOIs (doubled detection within one strum)
            if ioi < MIN_IOI_S:
                return False, None

            # Fold back a long IOI that is likely a missed beat (2x the true period)
            if self._tempo_s is not None and ioi > FOLD_THRESHOLD * self._tempo_s:
                ioi /= 2

            # After fold-back, discard anything still outside the plausible range
            if not (MIN_IOI_S <= ioi <= MAX_IOI_S):
                self._last_onset_time = t
                return False, None

            self._last_onset_time = t
            self._iois.append(ioi)
            self._accepted_iois += 1
            new_tempo_s = statistics.median(self._iois)
            current_bpm = 60.0 / new_tempo_s

            # Only shift tempo if the new estimate has drifted beyond the hysteresis band
            if self._tempo_s is None:
                self._tempo_s = new_tempo_s
            elif abs(current_bpm - (60.0 / self._tempo_s)) > BPM_HYSTERESIS:
                self._tempo_s = new_tempo_s
            # else: keep current tempo — variation is within ±5 BPM, ignore it
            current_bpm = 60.0 / self._tempo_s

            # Phase correction: nudge next_beat_time toward where this onset suggests
            # the next downbeat should land
            if self._next_beat_time is not None and self._tempo_s is not None:
                beats_ahead = (self._next_beat_time - t) / self._tempo_s
                # Round to the nearest positive beat boundary
                nearest = max(1, round(beats_ahead))
                expected_next = t + nearest * self._tempo_s
                correction = PHASE_ALPHA * (expected_next - self._next_beat_time)
                self._next_beat_time += correction

            return True, current_bpm

    def start(
        self,
        midi_out: mido.ports.BaseOutput,
        note_on: mido.Message,
        note_off: mido.Message,
    ) -> None:
        """Start the tick daemon thread."""
        self._midi_out = midi_out
        self._note_on = note_on
        self._note_off = note_off
        self._running = True
        self._thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="pulse-tick"
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the tick thread to stop and wait for it."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Internal tick loop -- runs on its own daemon thread

    def _tick_loop(self) -> None:
        while self._running:
            # Read shared state (brief lock -- no sleeping while holding it)
            with self._lock:
                tempo_s = self._tempo_s
                accepted = self._accepted_iois
                next_beat = self._next_beat_time

            # Wait until we have enough IOIs to make a reliable estimate
            if tempo_s is None or accepted < MIN_IOIS_TO_START:
                time.sleep(0.02)
                continue

            # First time we have a lock: schedule the first beat immediately
            if next_beat is None:
                with self._lock:
                    self._next_beat_time = time.perf_counter()
                    next_beat = self._next_beat_time

            # Sleep until the scheduled beat time
            sleep_s = next_beat - time.perf_counter()
            if sleep_s > 0:
                time.sleep(sleep_s)

            # Fire kick
            print(f"  [tick] sending note_on to {type(self._midi_out).__name__}")
            self._midi_out.send(self._note_on)
            time.sleep(NOTE_OFF_DELAY)
            self._midi_out.send(self._note_off)

            # Advance schedule using the latest tempo estimate
            with self._lock:
                self._next_beat_time += self._tempo_s
                bpm = round(60.0 / self._tempo_s)
                first = not self._first_beat_fired
                self._first_beat_fired = True

            if first:
                print(f"  Tempo locked at {bpm} BPM — kick running")
            else:
                print(f"  beat {bpm} BPM")
