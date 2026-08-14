"""
tools/midi_out_smoke_test.py
Minimal MIDI output smoke test for Phase 0.

Usage:
    python tools/midi_out_smoke_test.py [--port "VirtualBand"] [--note 60] [--bpm 60]

Sends a note-on / note-off pair once per second to the named MIDI output port.
Prints each message as it goes. Lists available ports and exits if the target
port is not found.
"""

import argparse
import time
from typing import Optional
import mido

TARGET_PORT_DEFAULT = "VirtualBand"
NOTE_DEFAULT = 60          # Middle C
VELOCITY = 100
NOTE_DURATION = 0.1        # seconds the note is held on before note-off


def list_ports() -> None:
    ports = mido.get_output_names()
    if ports:
        print("Available MIDI output ports:")
        for p in ports:
            print(f"  {p!r}")
    else:
        print("No MIDI output ports found. Is loopMIDI running?")


def find_port(target: str) -> Optional[str]:
    """Return the first port name that contains *target* (case-insensitive)."""
    for name in mido.get_output_names():
        if target.lower() in name.lower():
            return name
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="MIDI output smoke test")
    parser.add_argument("--port", default=TARGET_PORT_DEFAULT,
                        help="Target MIDI output port name (substring match)")
    parser.add_argument("--note", type=int, default=NOTE_DEFAULT,
                        help="MIDI note number to send (0-127, default: 60 = Middle C)")
    parser.add_argument("--bpm", type=float, default=60.0,
                        help="How many note-on/off pairs per minute (default: 60 = 1 per second)")
    args = parser.parse_args()

    period = 60.0 / args.bpm   # seconds between each note-on

    port_name = find_port(args.port)
    if port_name is None:
        print(f"ERROR: No MIDI output port matching {args.port!r} was found.\n")
        list_ports()
        return

    print(f"Opened MIDI output port: {port_name!r}")
    print(f"Sending note {args.note} at {args.bpm} BPM (period={period:.3f}s). Press Ctrl+C to stop.\n")

    note_on  = mido.Message("note_on",  note=args.note, velocity=VELOCITY,  channel=0)
    note_off = mido.Message("note_off", note=args.note, velocity=0,          channel=0)

    with mido.open_output(port_name) as port:
        try:
            while True:
                t0 = time.perf_counter()
                port.send(note_on)
                print(f"[{time.strftime('%H:%M:%S')}] SENT  {note_on}")
                time.sleep(NOTE_DURATION)
                port.send(note_off)
                print(f"[{time.strftime('%H:%M:%S')}] SENT  {note_off}")

                # Wait out the rest of the period
                elapsed = time.perf_counter() - t0
                remaining = period - elapsed
                if remaining > 0:
                    time.sleep(remaining)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
