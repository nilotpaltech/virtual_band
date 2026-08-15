"""
Visual helper script to annotate ground-truth beats in a WAV file.
Plots the waveform and lets you click exactly where the downbeats are.
Middle-click to remove the last point. Right-click to finish.
"""

import sys
import pathlib
import numpy as np
import scipy.io.wavfile as wavfile

# Ensure project root is in sys.path
_root = str(pathlib.Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

FIXTURE_DIR = pathlib.Path(_root) / "tests" / "fixtures"
WAV_PATH = FIXTURE_DIR / "strumming.wav"
BEATS_PATH = FIXTURE_DIR / "strumming_beats.txt"

def main():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Error: matplotlib is required. Run 'pip install matplotlib' first.")
        sys.exit(1)

    if not WAV_PATH.exists():
        print(f"Error: Could not find {WAV_PATH}")
        sys.exit(1)

    print(f"Loading {WAV_PATH}...")
    sr, audio = wavfile.read(str(WAV_PATH))
    
    # Mix to mono if stereo
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
        
    time_axis = np.arange(len(audio)) / sr

    print("\n" + "="*50)
    print("BEAT ANNOTATOR")
    print("="*50)
    print("Instructions:")
    print("1. Left-click to place a beat marker (red line)")
    print("2. Middle-click (or Backspace) to remove the last marker")
    print("3. Right-click (or Enter) when you are done to save and exit")
    print("4. Use the zoom/pan tools at the bottom of the window if you need more precision")
    print("="*50 + "\n")

    fig, ax = plt.subplots(figsize=(15, 6))
    ax.plot(time_axis, audio, color='black', alpha=0.6, linewidth=0.5)
    ax.set_title("Click on the waveform to annotate downbeats. Right-click to finish.")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Amplitude")
    plt.tight_layout()

    # Disable default keymaps for backspace/enter so they don't conflict
    try:
        plt.rcParams['keymap.back'].remove('backspace')
    except ValueError:
        pass
        
    try:
        plt.rcParams['keymap.quit'].remove('enter')
    except ValueError:
        pass

    # ginput returns a list of (x, y) tuples
    # n=-1 means infinite clicks, timeout=0 means no timeout
    clicks = plt.ginput(n=-1, timeout=0, show_clicks=True, mouse_add=1, mouse_pop=2, mouse_stop=3)

    plt.close()

    if not clicks:
        print("No beats annotated. Exiting without saving.")
        sys.exit(0)

    # Extract just the x-coordinates (time in seconds)
    beats = sorted([x for x, y in clicks])

    print(f"\nSaving {len(beats)} beats to {BEATS_PATH}...")
    with open(BEATS_PATH, "w") as f:
        for b in beats:
            f.write(f"{b:.3f}\n")
            
    print("Done! You can now run the evaluation script:")
    print("  python tools/eval_beat_tracker.py")

if __name__ == "__main__":
    main()
