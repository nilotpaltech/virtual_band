"""
Offline fixture tests for audio_io/pulse.py.
No audio, no MIDI, no sounddevice — just timestamp arithmetic.
"""
import pytest
from audio_io.pulse import PulseEstimator, MIN_IOIS_TO_START


def _make_timestamps(bpm: float, count: int, start: float = 10.0) -> list:
    """Generate perfectly-spaced onset timestamps at a given BPM."""
    period = 60.0 / bpm
    return [start + i * period for i in range(count)]


def _feed(pe: PulseEstimator, timestamps: list) -> None:
    for t in timestamps:
        pe.accept_onset(t)


# ---------------------------------------------------------------------------
# Basic convergence

def test_converges_to_correct_tempo_120bpm():
    pe = PulseEstimator(window_size=8)
    _feed(pe, _make_timestamps(120.0, 12))
    assert pe._tempo_s is not None
    assert abs(60.0 / pe._tempo_s - 120.0) < 2.0


def test_converges_to_correct_tempo_80bpm():
    pe = PulseEstimator(window_size=8)
    _feed(pe, _make_timestamps(80.0, 12))
    assert pe._tempo_s is not None
    assert abs(60.0 / pe._tempo_s - 80.0) < 2.0


def test_requires_min_iois_before_estimating():
    pe = PulseEstimator(window_size=8)
    # Only one onset -- no IOI can be computed yet
    pe.accept_onset(10.0)
    assert pe._accepted_iois == 0
    assert pe._tempo_s is None


# ---------------------------------------------------------------------------
# Noise tolerance

def test_ignores_doubled_onset():
    """A duplicate detection ~80 ms after a beat should not corrupt the estimate."""
    pe = PulseEstimator(window_size=8)
    timestamps = _make_timestamps(120.0, 10)
    # Inject a doubled onset 80 ms after beat 4
    doubled = sorted(timestamps + [timestamps[4] + 0.08])
    _feed(pe, doubled)
    assert pe._tempo_s is not None
    assert abs(60.0 / pe._tempo_s - 120.0) < 3.0


def test_handles_single_miss():
    """Removing one beat (missed onset) should not corrupt the estimate."""
    pe = PulseEstimator(window_size=8)
    timestamps = _make_timestamps(120.0, 12)
    timestamps_with_miss = [t for i, t in enumerate(timestamps) if i != 5]
    _feed(pe, timestamps_with_miss)
    assert pe._tempo_s is not None
    assert abs(60.0 / pe._tempo_s - 120.0) < 3.0


def test_combined_miss_and_double():
    """One miss and one double in a 12-onset sequence -- still converges."""
    pe = PulseEstimator(window_size=8)
    timestamps = _make_timestamps(100.0, 14)
    # Remove beat 3 (miss) and add a double 70 ms after beat 7
    noisy = sorted(
        [t for i, t in enumerate(timestamps) if i != 3]
        + [timestamps[7] + 0.07]
    )
    _feed(pe, noisy)
    assert pe._tempo_s is not None
    assert abs(60.0 / pe._tempo_s - 100.0) < 4.0


# ---------------------------------------------------------------------------
# Guard rails

def test_implausibly_fast_ioi_rejected():
    """Two onsets 50 ms apart (400 BPM -- outside guard rail) must not enter window."""
    pe = PulseEstimator(window_size=8)
    pe.accept_onset(10.0)
    pe.accept_onset(10.05)   # 50 ms gap -- below MIN_IOI_S
    assert pe._accepted_iois == 0


def test_implausibly_slow_ioi_rejected():
    """Two onsets 2 s apart (30 BPM -- outside guard rail) must not enter window."""
    pe = PulseEstimator(window_size=8)
    pe.accept_onset(10.0)
    pe.accept_onset(12.0)   # 2000 ms gap -- above MAX_IOI_S
    assert pe._accepted_iois == 0
