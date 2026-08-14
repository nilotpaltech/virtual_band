"""
tools/ujam_trigger_test.py
One-off manual test: VD-Brute pattern trigger via VirtualBand loopMIDI port.

Sequence (from docs/ujam_mapping.md):
  1. Verse  — C3 / note 60 — hold 4 s
  2. Chorus — C4 / note 72 — hold 4 s
  3. Stop   — B4 / note 83 — note-on only (instant halt)

Run:
    python tools/ujam_trigger_test.py [--port "VirtualBand"]
"""

import argparse
import time
from typing import Optional

import mido

TARGET_PORT_DEFAULT = "VirtualBand"
VELOCITY = 100

# VD-Brute style keys (docs/ujam_mapping.md — Ableton C3 = MIDI 60)
PATTERNS = [
    {"name": "Verse (C3)",  "note": 60, "hold": 4.0},
    {"name": "Chorus (C4)", "note": 72, "hold": 4.0},
    {"name": "Stop (B4)",   "note": 83, "hold": None},   # instant, no hold
]


def find_port(target: str) -> Optional[str]:
    """Return the first port whose name contains *target* (case-insensitive)."""
    for name in mido.get_output_names():
        if target.lower() in name.lower():
            return name
    return None


def ts() -> str:
    return time.strftime("%H:%M:%S")


def send(port: mido.ports.BaseOutput, name: str, note: int,
         velocity: int, kind: str) -> None:
    msg = mido.Message(kind, note=note, velocity=velocity, channel=0)
    port.send(msg)
    print(f"[{ts()}]  {kind:8s}  {name:20s}  note={note}  vel={velocity}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VD-Brute pattern trigger test")
    parser.add_argument("--port", default=TARGET_PORT_DEFAULT,
                        help="loopMIDI output port name (substring match)")
    args = parser.parse_args()

    port_name = find_port(args.port)
    if port_name is None:
        print(f"ERROR: No MIDI output port matching {args.port!r} found.\n")
        available = mido.get_output_names()
        if available:
            print("Available MIDI output ports:")
            for p in available:
                print(f"  {p!r}")
        else:
            print("No MIDI output ports found — is loopMIDI running?")
        return

    print(f"Port  : {port_name!r}")
    print(f"Device: VD-Brute (UJAM Virtual Drummer)")
    print()

    with mido.open_output(port_name) as port:
        for pat in PATTERNS:
            name  = pat["name"]
            note  = pat["note"]
            hold  = pat["hold"]

            send(port, name, note, VELOCITY, "note_on")

            if hold is not None:
                time.sleep(hold)
                send(port, name, note, 0, "note_off")
            # Stop key: no note_off needed — VD-Brute latches on note_on alone

    print()
    print("Done.")


if __name__ == "__main__":
    main()
