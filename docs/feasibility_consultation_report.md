# Virtual Band — Feasibility & Architecture Consultation

*Prepared as a technical consultation, not an implementation spec. Where the brief left something open, I've given a recommendation and said why — push back on any of it.*

---

## 1. Executive assessment

The core idea splits into two very different technical problems, and they deserve very different confidence levels:

- **"Listen to a guitar and estimate tempo/beat/chords in real time."** This is mature engineering. Every piece exists in open-source form, has existed for years, and the remaining work is integration and tuning, not invention.
- **"Behave like a responsive bandmate — anticipate, react proportionately, know when to lay out, never feel mechanical."** This is where the real project is. It's not a solved problem in general, but you don't need it solved *in general* — you need it solved for *you, on your guitar, in your genre*. That's a much smaller and much more tractable target, and it's the part worth spending most of your time on.

The closest existing research field to what you're describing is **automatic accompaniment / score following** (Christopher Raphael's "Music Plus One," Roger Dannenberg's "Orchestra in a Box," IRCAM's Antescofo) — decades of academic work on computers accompanying live soloists in real time. The important caveat: almost all of that work assumes the computer already knows the score in advance and is tracking *position within it*. Your hardest ask — a band that follows genuinely free playing with no prior score, purely from a few bars of listening — is the less-explored, harder version of that problem. Your own "songwriting mode" (teach the system a song first, then jam with it) is, not coincidentally, exactly the version of the problem that decades of score-following research says is tractable. I'd treat that mode as more central than the brief currently does — see §7 and §17.

**Bottom line:** feasible as a personal instrument, in a constrained style, built incrementally, with a beginner-friendly stack. Not feasible as "general AI musician for any genre" in a reasonable timeframe — but you weren't asking for that.

---

## 2. Feasibility analysis

### A. What's straightforward
- Real-time audio capture with low latency (well-trodden: ASIO/CoreAudio via standard libraries).
- Real-time pitch/onset detection on a single guitar signal.
- Real-time tempo/beat tracking — multiple open-source options are *specifically designed* for streaming/live use (not just adapted from offline tools).
- MIDI generation and routing, including virtual MIDI ports into a DAW.
- Driving UJAM instruments from generated MIDI — I verified this is a genuinely good fit (§6).
- Rule-based / state-machine arrangement logic (which pattern plays when) — this is ordinary software engineering, not ML.

### B. What's moderately hard
- **Real-time chord recognition from a live acoustic guitar signal.** Harder than monophonic pitch tracking because you're dealing with polyphonic, often-imperfect voicings, string noise, and strumming transients. Tractable with chroma-vector template matching plus temporal smoothing — a well-understood technique — but expect a real error rate and plan for it explicitly (confidence gating, not silent failure).
- **Tempo-following through rubato without hardcoding a score.** This is what score-following systems solve *given a known score*. Without one, you're building a lighter-weight version: a smoothed, continuously-updated tempo/phase estimate the band locks to, tolerant of drift. Doable with well-established filtering techniques (comb-filter tempo estimation, IOI histograms, light Kalman-style smoothing), not research-grade, but needs real tuning against your actual playing.
- **Detecting "something meaningful changed" without hardcoding section labels.** This is closely related to *music segmentation via self-similarity/novelty detection*, a standard (offline) MIR technique. Doing it causally, in real time, on a rolling buffer is a genuine engineering challenge but not a research one — you're trading some sensitivity for the ability to run online.

### C. What's genuinely research-grade (and where I'd deliberately scope down)
- **Scoreless, general-purpose prediction of "what comes next" musically**, with no prior exposure to the song. This is an open problem. Your "teach the song first" mode sidesteps it almost entirely — strongly recommend leaning into that rather than chasing blind prediction.
- **Arrangement decisions that consistently feel musical rather than mechanical** — deciding *when* a fill happens, *how much* the piano should thin out, *whether* this dynamic swell warrants a bigger response. This is closer to a craft/sound-design problem than an algorithms problem. No architecture solves it for you; only iterative listening and tuning does. This is also, correctly, what your own §24 identifies as the actual success criterion — I'd just flag that it's *also* the hardest and most time-consuming part, more than any of the audio-analysis stages.
- **General-purpose polyphonic transcription of acoustic guitar to note-perfect output** in noisy real-world conditions is still an active research area. You don't need this — you need chord-level, not note-perfect, recognition, which is a much smaller ask.

### F/G. Latency and compute (answering directly, since they shape everything else)
Acceptable *musical* latency for something to feel like a bandmate reacting rather than a machine lagging is roughly **in the same range as human ensemble reaction time — tens of milliseconds, not hundreds**. That budget has to cover: audio buffer capture → analysis → decision → MIDI → instrument's own internal note-to-sound latency. This is tight but achievable on a normal modern desktop *if* you keep the tight-timing path simple (beat/pulse tracking, MIDI I/O) and let the "smarter" analysis (chord confidence, section detection) run on a coarser update cycle — musical decisions like "should the piano get busier" don't need to happen every audio frame, they need to happen every beat or every bar. This coarse/fine split is the single most important architectural decision in this document (§3). No GPU is required for anything described here; this is CPU-class DSP and small models, not large neural generation.

---

## 3. Recommended architecture

**Split the system into two timing tiers, not one pipeline:**

1. **A tight, low-latency tier** that owns the clock: audio capture, onset/pulse detection, and MIDI output timing. This needs to be fast and simple.
2. **A coarser "brain" tier** that owns musical decisions: chord identity, section/state, arrangement choices, humanization parameters. This can run every beat or every bar, not every audio frame, which buys you enormous headroom to use heavier, more accurate (slower) analysis without hurting the *feel* of timing.

The tight tier keeps the band feeling responsive even while the brain tier is still "thinking." This is the same principle score-following systems use (fast tempo/phase tracking decoupled from slower harmonic/structural analysis), and it directly addresses your own concern in §10 (act confidently on what's confident, hedge on what isn't).

### Prototype (personal tool, first 3–6 months)
- **Standalone desktop app** (not a plugin) that captures guitar audio directly, runs the analysis pipeline, and emits MIDI.
- **Route MIDI into Ableton Live via a virtual MIDI port**, with your existing UJAM instruments loaded on tracks there. Ableton handles audio engine, mixing, and recording — you don't rebuild any of that.
- This is deliberately *not* the theoretically "purest" architecture — an in-process plugin host would avoid one extra hop — but it is dramatically faster to reach "there is a band playing with me," and it uses infrastructure you already have working. Optimize for that first; optimize latency-per-hop later once you know the musical logic is worth optimizing.

### Usable personal tool (6–12 months)
Same shape, matured: songwriting/teach mode, recording/export, a real arrangement/pattern library, humanization pass, and — if the virtual-MIDI-into-Ableton path turns out to have latency or jitter problems you can't tune away (§11) — an in-process VST3 host as a targeted fix, not a rewrite.

### Potential future product
A JUCE-based VST3/AU plugin exposing the same "brain," running as a MIDI-generating track in any DAW. Two sub-options worth deciding *later*, not now: stay a pure "control layer" over the user's own instruments (commercial precedent: Scaler, Captain Plugins), or bundle owned instruments to avoid depending on UJAM's licensing for resale. Don't decide this now — it doesn't affect anything you'd build in the next year.

---

## 4. Alternative architectures considered

| Option | Verdict |
|---|---|
| **C++/JUCE from day one** | Rejected for the prototype. Right tool eventually, wrong tool for rapid musical iteration with a beginner + coding agent. Premature optimization. |
| **Max for Live device** | Tempting given you already use Ableton — tight integration, mature real-time DSP objects, can shell out to Python/ONNX via OSC for the ML pieces. Worth a look *specifically for the low-latency tier* later, but it locks you to Ableton (you explicitly didn't want that) and Max is a genuinely different skill from anything else in this plan. Not recommended as the primary architecture. |
| **DAW-integrated MIDI generator via ReaScript (Reaper)** | Reaper's scripting is powerful and low-friction, but Lua/EEL2 is a worse environment for the MIR/ML work than Python. Same objection as Max: DAW lock-in you said you wanted to avoid. |
| **Pure Python standalone app + virtual MIDI** (recommended) | Best fit for "beginner, AI-assisted, fast iteration, DAW-agnostic." |
| **Hybrid: Python brain + lean C++/JUCE timing core, connected over a local low-latency channel** | This is the sensible *long-term* target once the musical logic is proven — see §3's two-tier split. Not the prototype; the destination. |

---

## 5. Recommended technology stack

**Language / core:** Python for everything except (eventually) the tight timing tier.

**Audio I/O:** a standard low-latency callback-based audio library with ASIO/CoreAudio support.

**MIDI I/O:** a standard real-time MIDI library, plus a virtual MIDI port utility (loopMIDI on Windows, IAC on Mac) to bridge into Ableton.

**Pitch/onset detection:** a lightweight, purpose-built real-time onset/pitch library as the primary real-time signal. Reserve heavier, more accurate neural pitch-detection models (like Spotify's Basic Pitch) for the **offline "teach me a song" path**, where you can afford a bigger analysis window and higher accuracy matters more than millisecond latency.

**Beat/tempo tracking:** use a tracker specifically designed for **streaming/live** use, not one designed for offline batch analysis — this distinction matters more than it looks. The most well-known general-purpose beat-tracking library in this space (madmom) is explicitly optimized for offline accuracy; there are other, newer trackers purpose-built for low-latency live use. Use the offline-optimized tool for the "teach mode" path (where accuracy matters and latency doesn't), and a live-oriented tracker for the real-time path.

**Chord recognition:** don't reach for a pretrained deep chord-recognition model first. Start with chroma-feature extraction + template matching against major/minor/7th chord shapes, with temporal smoothing. This is a well-understood, moderate-effort technique (days, not months) and gives you something to listen to and tune quickly. Upgrade only if it proves insufficiently robust on your actual guitar/room/pickup.

**Section/state-change detection:** a rolling self-similarity/novelty measure over recent feature history — flag "something changed," don't try to label *what* changed until much later, exactly as your own brief already suggests in §6.

**Sound generation for the prototype:** your existing UJAM instruments, hosted in Ableton, driven via the virtual MIDI bridge (§6). For early bring-up and testing *before* you've validated the UJAM MIDI mapping, a free local fallback (a SoundFont-based synth or a simple sample player) is useful so you can hear results without needing Ableton open for every test loop.

**Humanization source material:** rather than inventing timing/velocity "imperfection" from scratch, borrow from existing datasets of real human-performed MIDI (e.g., Magenta's Groove MIDI Dataset of real drummer performances) as a source of authentic micro-timing and velocity patterns per feel/style, and apply those as templates rather than random jitter. This directly answers your §12 concern about "musical imperfection vs. random number generator."

**Eventual plugin layer:** JUCE/C++, deferred until the musical brain is proven in Python. Don't port early.

---

## 6. Analysis of UJAM integration

I looked into how UJAM instruments actually respond to live MIDI rather than assuming. The findings are good news for this project:

- UJAM's "Player Mode" is *designed* for exactly this use case: an upper keyboard zone (typically from around C3 up) accepts **chord input** — UJAM's own chord-recognition logic interprets up to ~4 simultaneous notes and picks a sensible voicing/inversion, so you don't need to send it perfectly voiced chords, just the right notes.
- A **lower zone** (below the chord range) is used for **phrase/pattern/articulation selection** — this is the "keyswitch" mechanism, and it's exactly the hook you'd use to tell the instrument "be busier now" or "do a fill."
- **Sustain pedal (CC64) triggers latch** (hold the current chord) — useful for letting a chord ring while your left-hand/keyswitch stream continues independently.
- **Most parameters are MIDI-Learnable and automatable** via standard CC, which covers the "become more energetic" and intensity-mapping behavior you described.
- There are a few product-specific quirks worth knowing before you build against them — e.g., in the Virtual Guitarist series, switching between Player Mode and Instrument Mode is done via a *specific MIDI note* (not a CC), and the exact keyswitch layout differs by product line (Virtual Guitarist vs. Virtual Bassist vs. Virtual Pianist each have their own scheme, and it can vary between versions of the same instrument).

**Conclusion: the "UJAM as intelligent puppet, Virtual Band as the brain" strategy in your brief is sound**, and it also quietly solves a chunk of your humanization problem for free — UJAM's own engine already handles per-strum timing/voicing details once you've told it the chord and the phrase. Your system's job narrows to: pick the right chord, pick the right phrase/keyswitch, pick the right CC values, and *change your mind at musically sensible moments*. That's a meaningfully smaller job than generating raw MIDI note-by-note yourself.

**Recommended first action here (not later):** before writing any analysis code, spend an afternoon cataloging the exact keyswitch/CC map for the specific UJAM products you own (drummer, bassist, pianist, guitarist lines can each differ). This becomes a small set of data files your Conductor module reads — not hardcoded logic — so adding or swapping instruments later doesn't touch your core code.

---

## 7. MVP definition

Your proposed MVP (four-chord progression → synchronized drums and bass that follow you) is reasonable, but I'd insert one leaner milestone *before* it, because it isolates the single riskiest unknown — does the timing feel like a band or like a laggy machine — without chord-recognition accuracy muddying the signal:

- **MVP-0 (recommended first target): rhythm only.** No chord detection at all. A single drum voice (even just a kick/snare pattern) that locks onto your strumming pulse and tolerates tempo drift, pause, and resumption. This tells you, within days rather than weeks, whether your latency budget and beat-tracking choice can actually deliver "feels like a bandmate" — the thing your whole philosophical goal (§24) depends on. If this doesn't feel good, no amount of chord/harmony sophistication downstream will fix it.
- **MVP-1: your original proposal.** Add chord detection and a bass line that follows the progression, on top of a rhythm engine you already trust.

---

## 8. Development phases

Your 18-stage list is a reasonable inventory but is sequenced more like a checklist than a risk-driven plan. Regrouped:

| Phase | Content |
|---|---|
| 0 | Audio I/O, MIDI I/O, repo scaffolding, a debug visualizer (see what the analysis pipeline is "thinking" in real time) |
| 1 | Rhythm engine only — beat/tempo tracking driving one drum voice (**MVP-0**) |
| 2 | Chord recognition + bass following (**MVP-1**, your original proposed milestone) |
| 3 | Conductor: a confidence-aware state machine merging tempo/chord/section signals with hysteresis (don't flip on every noisy frame) |
| 4 | Arrangement/pattern library + intensity mapping; piano/guitar join |
| 5 | Humanization pass using groove-template material (§5) |
| 6 | Section/novelty change detection + fills triggered on transitions |
| 7 | Songwriting/"teach mode" — record and structure a song in advance, then use that structure to bias live following |
| 8 | Recording/export pipeline (stems, MIDI, structure metadata) |
| 9 | Full UJAM production integration, end-to-end |
| 10 (future, optional) | Plugin packaging (VST3/AU) once the musical brain is proven and stable |

---

## 9. Acceptance criteria for each phase

- **Phase 1:** drum onset stays audibly locked to your strum for a 2-minute take that includes a deliberate tempo ramp; recovers within ~1 bar after a pause.
- **Phase 2:** bass root correctly follows the `C–G–Am–F` loop for 90%+ of chord changes across 3 separate takes on different days (accounts for your guitar/room, not a lab recording).
- **Phase 3:** arrangement doesn't visibly "flicker" (rapid contradictory state changes) during 5 minutes of normal play; a deliberately ambiguous strum doesn't cause a full state reset.
- **Phase 4:** you can identify, by ear, at least two distinct intensity levels in the arrangement without being told which is which.
- **Phase 5:** in a blind-ish A/B listen (quantized vs. humanized), you consistently prefer the humanized version.
- **Phase 6:** a deliberate section change (verse → different progression) triggers a fill or transition within one bar, without false-triggering on a single wrong chord.
- **Phase 7:** after teaching a song once, a second live pass through it produces noticeably more appropriate accompaniment than blind following would.
- **Phase 8:** a full jam session produces a usable demo (stems + MIDI) with one button press / command.
- **Phase 9:** a 10-minute unattended jam session doesn't require any manual UJAM tweaking mid-session.

---

## 10. Major technical risks

1. **Cumulative latency.** Capture buffer + analysis + MIDI + UJAM's internal response time can add up past the point of feeling live, even if each piece is individually fast. Budget and measure this explicitly and early (§15, experiment #1) — don't discover it in month four.
2. **Guitar/room/pickup-specific chord recognition robustness.** Whatever you tune against your living-room take may not generalize to a different session. Build confidence gating in from the start (per your own §10 philosophy), not as a later patch.
3. **The "uncanny valley" arrangement problem.** Technically-correct-but-musically-dead output is the single biggest product risk and the one no architecture decision fixes — only iterative listening does. Budget real calendar time for this, not just engineering time.
4. **UJAM per-product idiosyncrasies** (differing keyswitch maps, mode-switch quirks) causing brittle integration code if hardcoded rather than data-driven.
5. **Scope creep from the 18-stage roadmap.** For a solo hobbyist project, there's real risk of spending months on infrastructure before ever hearing "a band" — which is demotivating and also just bad risk sequencing. MVP-0 exists specifically to front-load the payoff moment.
6. **Latency/jitter sources outside your model's control** — audio driver buffer size, virtual MIDI port overhead, Ableton's own buffer settings. Worth an early spike (§15) to characterize this floor before optimizing your own code against it.

---

## 11. Key unknowns that should be experimentally tested

- Actual measured round-trip latency on **your** machine: guitar in → simplest possible onset detector → MIDI out → UJAM sound. Get a real number before designing anything else.
- Whether the chroma-template chord recognizer is robust enough on your specific guitar/pickup/room, or whether you need a heavier model sooner than planned.
- Whether virtual-MIDI-into-Ableton introduces meaningful jitter versus an in-process plugin host — only worth investigating once §10's cumulative-latency number looks marginal.
- The exact UJAM keyswitch/CC map for your specific owned products.
- Whether a live-oriented beat tracker holds up on your actual strumming (these tools are typically validated on clean, curated datasets — your bedroom acoustic guitar is a different regime).

---

## 12. Suggested repository/project structure

```
virtualband/
  audio_io/          # capture, buffering, device handling
  analysis/
    pitch.py
    chord.py
    beat.py
    section.py        # each independently testable against recorded fixtures
  brain/
    state.py          # confidence-weighted musical state
    conductor.py       # decision logic / state machine
    behaviors/          # pattern library, per instrument
  output/
    midi_out.py
    ujam_maps/          # per-product keyswitch/CC definitions as DATA, not code
  humanize/
    groove_templates/
  song/                # "teach mode" song model + serialization
  recording/           # stem/MIDI/metadata export
  tools/
    offline_cli.py      # run any analysis module against a recorded wav, no live rig needed
    latency_probe.py
    visualizer.py
  tests/
    fixtures/            # short recorded guitar clips + hand-labeled ground truth
docs/
  architecture.md
  ujam_maps.md           # discovered mappings, written up from §6/§15 experiments
  decisions.md           # running log — see §13
```

The fixture-based testing setup is the important part: real-time audio systems are painful to unit-test live, so give every analysis module a way to be tested against a small library of recorded, hand-labeled clips. This also happens to be exactly what makes the project tractable for agentic development (§13).

---

## 13. Antigravity workflow

- **Give every module a fixture-testable contract.** An agent can't hear music. It *can* run `pitch.py` against `tests/fixtures/c_g_am_f_take1.wav` and check the output against a hand-labeled ground truth file. Structure the repo (§12) so that's true for every analysis module — this turns "make the chord detector better" from a vague ask into a measurable diff.
- **Reserve subjective "does this feel musical" evaluation for you.** After a short listening session, write down *specific, concrete* observations ("bass changed half a beat late on the third bar," "a fill fired while I was holding a chord") rather than "make it feel better" — that's what an agent can actually act on.
- **Use planning mode for cross-module changes** (e.g., "add a new UJAM product mapping" touches `ujam_maps/`, `conductor.py`, and probably a fixture test) and fast/inline mode for isolated single-file fixes.
- **Keep `docs/decisions.md` running.** Agent sessions don't retain context between tasks the way you do across the whole project's lifespan; a short, current decision log lets you paste in exactly the context a new task needs instead of re-explaining architecture each time.
- Antigravity supports project-scoped **skills** (packages of standing context loaded only when relevant) — worth writing one early that captures "how this repo's modules are structured, how to add a fixture test," so it's automatically available to every future task rather than re-explained per session.

---

## 14. Skills you need to learn

You don't need much, and almost none of it is deep theory:

- **MIDI:** solid practical fluency — note numbers, velocity, CC, channels, and specifically how virtual MIDI ports route into a DAW. You'll touch this constantly; learn it well.
- **Audio engineering (practical, not theoretical):** buffer size vs. latency tradeoffs, sample rate, how to route audio/MIDI between separate apps on your OS. Operational knowledge, not signal-processing math.
- **DSP:** the bare minimum — know what a spectrogram/chroma feature roughly represents and what "analysis window" means, so you can reason about *why* something is laggy or wrong. You do not need to derive an FFT.
- **Music information retrieval (MIR) concepts:** a working sense of what beat-tracking/chord-recognition/onset-detection algorithms are actually estimating and their typical failure modes — enough to debug musically ("it's probably confusing a passing tone for a chord change") rather than only technically.
- **C++/JUCE:** not needed for anything through Phase 9. Defer indefinitely; you may never need it personally if the eventual plugin step is scoped out or handled separately.

---

## 15. Recommended first experiments (in order)

1. **Latency probe.** Loop-back-record a simple click → onset-detector → MIDI-out → UJAM-drum-hit chain and measure the actual round-trip in milliseconds on your machine. Everything else is downstream of this number.
2. **UJAM mapping catalog.** Manually explore and document the keyswitch/CC layout for each UJAM product you own; write it up as the first `docs/ujam_maps.md` entry.
3. **Offline chord-recognition prototype.** No real-time pressure — record a few takes of your exact `C–G–Am–F` example and see how well chroma-template matching does, purely offline.
4. **MVP-0 smoke test.** A live-oriented beat tracker driving one kick-drum sample with naive pulse-following — no chords. This is the "does it feel like a band" gut-check.
5. **Manual UJAM trigger test.** Script a single sustained chord + one keyswitch note sent manually, confirm it sounds right through your actual Ableton setup, before any analysis code depends on it.

---

## 16. Things to deliberately postpone

- VST3/AU plugin packaging — entirely, until the musical brain is proven.
- Labeling sections as verse/chorus/bridge — do unsupervised change detection only, for a long time.
- Full polyphonic transcription / precise chord voicing capture — chord identity only.
- Generalizing beyond one target style/genre.
- Neural MIDI generation — start with the pattern-library approach; only reach for learned generation if that demonstrably runs out of expressiveness.
- Any commercial/licensing questions around UJAM redistribution.
- Sophisticated score-following-grade predictive modeling — a simple "continue the current hypothesis, decay confidence over time" approach is enough at first, consistent with your own §10 framing.

---

## 17. Long-term roadmap

Personal-tool maturity first (Phases 0–9, realistically 6–18 months of evenings/weekends depending on pace) before any productization question is worth revisiting. If it does become worth exploring commercially, the fork in the road is: stay a MIDI "control layer" over instruments the user already owns (lower liability, precedent exists — Scaler, Captain Plugins), or bundle owned instruments (more self-contained, more upfront licensing/production work). Nothing about the architecture recommended here forecloses either path — that's a business decision for later, not an engineering one for now.

---

## 18. What I would build if I were doing this myself

Start absurdly small: a single kick drum following your strum, nothing else, before touching chord recognition at all (MVP-0). That's the fastest way to find out whether your latency budget can deliver the actual magic you're after — and it's cheap to abandon or pivot if it doesn't. I'd keep essentially everything in Python for as long as possible and resist the pull toward C++/JUCE until the musical logic is genuinely stable and worth hardening. I'd lean hard on UJAM's own Player Mode intelligence rather than trying to out-humanize it myself — it already solves a real chunk of the problem for free. And I'd treat this explicitly as *building an instrument for one specific player* rather than a generalizable product, at least until it's good enough that you personally reach for it over just playing alone — which is, correctly, the metric your own brief already names in §24 and §25.
