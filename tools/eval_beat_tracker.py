"""
Offline evaluation script comparing aubio.tempo with our IOI-based PulseEstimator.
"""

import os
import sys
import pathlib
import wave
import numpy as np
import scipy.io.wavfile as wavfile
from typing import List, Tuple

# Ensure project root is in sys.path
_root = str(pathlib.Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from audio_io.pulse import PulseEstimator
import aubio

SAMPLE_RATE = 48000
BUFFER_SIZE = 128
FIXTURE_DIR = pathlib.Path(_root) / "tests" / "fixtures"
WAV_PATH = FIXTURE_DIR / "strumming.wav"
BEATS_PATH = FIXTURE_DIR / "strumming_beats.txt"

def generate_synthetic_fixture() -> Tuple[np.ndarray, List[float], int]:
    """Generates a synthetic strumming audio fixture with ground truth beats."""
    print("Generating synthetic fixture...")
    duration_s = 10.0
    bpm = 100.0
    beat_period = 60.0 / bpm
    
    # Ground truth beats
    beats = np.arange(1.0, duration_s, beat_period).tolist()
    
    # Create audio
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
    audio = np.zeros_like(t)
    
    # Add strums
    for beat_time in beats:
        # Simulate a dense strum (multiple transients)
        for offset in [0.0, 0.01, 0.02, 0.03, 0.04]:
            idx = int((beat_time + offset) * SAMPLE_RATE)
            if idx < len(audio):
                # Simple exponential decay transient
                length = int(SAMPLE_RATE * 0.1)
                transient = np.exp(-np.linspace(0, 10, length)) * np.random.randn(length)
                end_idx = min(idx + length, len(audio))
                audio[idx:end_idx] += transient[:end_idx - idx]
                
    # Add noise
    audio += np.random.randn(*audio.shape) * 0.01
    
    # Normalize
    audio /= np.max(np.abs(audio))
    
    return audio, beats, SAMPLE_RATE

def load_or_generate_fixture() -> Tuple[np.ndarray, List[float], int]:
    if WAV_PATH.exists() and BEATS_PATH.exists():
        print(f"Loading real fixture from {WAV_PATH}...")
        sr, audio = wavfile.read(str(WAV_PATH))
        if sr != SAMPLE_RATE:
            # Simple resample or warning. For now, assume 48k or warn.
            print(f"Warning: WAV file is {sr} Hz, expected {SAMPLE_RATE} Hz")
        
        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
            
        # Convert to float32 [-1, 1] if int
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
            
        with open(BEATS_PATH, "r") as f:
            beats = [float(line.strip()) for line in f if line.strip()]
            
        return audio, beats, sr
    else:
        print("Real fixture not found (need strumming.wav and strumming_beats.txt).")
        return generate_synthetic_fixture()

def evaluate_ioi(audio: np.ndarray, sr: int) -> List[float]:
    """Evaluates the IOI-based PulseEstimator."""
    print("Evaluating IOI estimator...")
    
    threshold = 0.15
    refractory_s = 0.495
    last_onset_time = -10.0 # start negative so first beat is accepted
    
    pulse = PulseEstimator()
    # We won't start the thread, just feed it onsets and observe the estimated tempo
    
    beat_decisions = []
    
    # Simulate the real-time loop
    for i in range(0, len(audio), BUFFER_SIZE):
        block = audio[i:i+BUFFER_SIZE]
        if len(block) < BUFFER_SIZE:
            break
            
        current_time = i / sr
        
        # OnsetDetector logic
        rms = np.sqrt(np.mean(block**2))
        if rms > threshold and (current_time - last_onset_time) > refractory_s:
            last_onset_time = current_time
            # Feed to pulse estimator
            accepted, bpm = pulse.accept_onset(current_time)
            
            # Record accepted onsets as beat decisions
            if accepted:
                beat_decisions.append(current_time)
                
    return beat_decisions

def evaluate_aubio(audio: np.ndarray, sr: int) -> List[float]:
    """Evaluates aubio.tempo."""
    print("Evaluating aubio.tempo...")
    
    # aubio requires float32 contiguous arrays
    audio = audio.astype(np.float32)
    
    hop_size = BUFFER_SIZE
    win_size = BUFFER_SIZE * 4 # Standard window size for 128 hop
    
    tempo = aubio.tempo("default", win_size, hop_size, sr)
    
    beat_decisions = []
    
    for i in range(0, len(audio), hop_size):
        block = audio[i:i+hop_size]
        if len(block) < hop_size:
            # Pad with zeros if necessary
            block = np.pad(block, (0, hop_size - len(block)))
            
        # aubio tempo returns True if a beat was detected in this block
        is_beat = tempo(block)
        if is_beat[0]:
            beat_decisions.append(tempo.get_last_s())
            
    return beat_decisions

def compute_metrics(ground_truth: List[float], estimated: List[float]) -> dict:
    if not estimated:
        return {"mean_error": float('inf'), "std_error": float('inf'), "missed": len(ground_truth)}
        
    errors = []
    missed = 0
    
    # Very simple nearest-neighbor evaluation
    for gt in ground_truth:
        # Find nearest estimated beat
        distances = [abs(gt - est) for est in estimated]
        min_dist = min(distances) if distances else float('inf')
        
        # If the nearest beat is within 150ms, consider it a match
        if min_dist < 0.150:
            errors.append(min_dist)
        else:
            missed += 1
            
    return {
        "mean_error": np.mean(errors) * 1000 if errors else float('inf'),
        "std_error": np.std(errors) * 1000 if errors else float('inf'),
        "missed": missed
    }

def get_bpm(beats: List[float]) -> float:
    if len(beats) < 2:
        return 0.0
    intervals = np.diff(beats)
    # filter out very long intervals if there are breaks, but average is simple
    return 60.0 / np.mean(intervals)

def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    audio, ground_truth, sr = load_or_generate_fixture()
    
    ioi_beats = evaluate_ioi(audio, sr)
    aubio_beats = evaluate_aubio(audio, sr)
    
    ioi_metrics = compute_metrics(ground_truth, ioi_beats)
    aubio_metrics = compute_metrics(ground_truth, aubio_beats)
    
    gt_bpm = get_bpm(ground_truth)
    ioi_bpm = get_bpm(ioi_beats)
    aubio_bpm = get_bpm(aubio_beats)
    
    print("\n" + "="*50)
    print("BEAT TRACKER EVALUATION RESULTS")
    print("="*50)
    print(f"Ground truth beats: {len(ground_truth)} ({gt_bpm:.1f} BPM)")
    print(f"IOI decisions:      {len(ioi_beats)}")
    print(f"aubio decisions:    {len(aubio_beats)}\n")
    
    print(f"{'Metric':<20} | {'IOI Estimator':<15} | {'aubio.tempo':<15}")
    print("-" * 56)
    
    def fmt(val, unit=""):
        if val == float('inf'):
            return "N/A"
        return f"{val:.1f}{unit}"
        
    print(f"{'Est. BPM':<20} | {fmt(ioi_bpm, ' BPM'):<15} | {fmt(aubio_bpm, ' BPM'):<15}")
    print(f"{'Mean Error':<20} | {fmt(ioi_metrics['mean_error'], 'ms'):<15} | {fmt(aubio_metrics['mean_error'], 'ms'):<15}")
    print(f"{'Std Dev (Jitter)':<20} | {fmt(ioi_metrics['std_error'], 'ms'):<15} | {fmt(aubio_metrics['std_error'], 'ms'):<15}")
    print(f"{'Missed Beats':<20} | {ioi_metrics['missed']:<15} | {aubio_metrics['missed']:<15}")
    print("="*50)

if __name__ == "__main__":
    main()
