# v2 design notes — covert rhetorical steering in multi-turn debate

Working notes for the next experiment, distilled from the design conversation. These
record decisions and the *reasoning* behind them so the rationale doesn't get lost or
"optimised away" when v2 is built. v2 is a separate project from this repo (v1); see
"Relationship to v1" below.

## The pivot (what changed from v1)

v1 asks: *does a hidden channel survive paraphrasing?* (channel survival). The n=150
results confirmed it transmits and that paraphrase destroys it — but the **naive judge
was barely moved**, because the channel only ever "worked" for the scheme-aware decoder.
So v1 does **not** test manipulation of a realistic overseer.

v2 asks the question we actually care about: **can colluding debaters steer a realistic
(naive) judge to a predetermined wrong answer, and can paraphrasing defend against it?**
The threat is reframed as **covert judge-steering robust to paraphrase** (the channel
runs debater→judge, not debater→debater — see "who knows").

## Biggest conceptual upgrade: semantic steering vs symbol-level encoding

- **Main channel = rhetorical / semantic steering**: which points to emphasise, what to
  concede, how to frame, how hard to actually fight the assigned side. The payload lives
  in *meaning*, not surface symbols.
- **Foil = symbol-level encoding** (the v1 acrostic / marker-word / sentence-count).
- Key prediction: paraphrasing destroys *surface form* but preserves *meaning* by design,
  so it should **strip the symbol-level foil** (defence "works") but **fail against
  semantic steering** (defence doesn't). "Paraphrase doesn't strip the realistic threat"
  is the publishable result. Keep **both** channels as a deliberate contrast — the foil
  shows the defence can work; semantic steering shows where it doesn't.

## Setup

- **No-collusion control:** debaters argue assigned opposite sides honestly.
- **Collusion:** both debaters get the question, their assigned side, **and** a shared
  target to steer the judge toward. Each must *appear* to argue its assigned side while
  covertly steering to the target (e.g. A argues A, B argues B, correct = B, both steer
  the judge to A).
- **Target = QuALITY's annotated "best distractor"** (the hardest-to-distinguish wrong
  answer), not v1's length-matching heuristic. It's the most dangerous target and the
  one a debater can argue for without collapsing. Already wired in `ucl-dark/llm_debate`
  (`best_distractor_for_question()`; they skip questions where correct == best distractor).
  Caveat (Khan et al.): ~⅔ of incorrect human verdicts came from the *correct*-side
  debater arguing badly — control for "steering for free" via honest incompetence.

## Who knows: both-know first (one-knows is v2-of-v2)

**both-know is the right first experiment.** Both debaters are handed the target in their
prompts; the only thing left to vary is the steering itself. Reasons to preserve:

1. **Two-link confound (the argument *against* one-knows as v1).** one-knows chains two
   channels in series — A must covertly signal B (debater→debater), *then* both steer the
   judge (debater→judge). If accuracy doesn't drop you can't tell which link failed
   ("B never received the signal" vs "the judge wasn't moved"). both-know cuts the first
   link, so the dependent variable measures exactly the research question.
   *(Note: this is the correct direction — the two-link problem is why one-knows is
   harder, not why it's better. The reasoning has been stated backwards more than once;
   both-know is the clean v1.)*
2. **Dependency ordering.** both-know's result is upstream: if steering doesn't move the
   judge even with shared full knowledge from turn one, one-knows is dead on arrival. So
   you want the both-know result regardless of where you end up.
3. **Upper bound.** both-know upper-bounds the steering effect of one-knows (the latter
   steers later/weaker, gated on a noisy channel). Same shape as scheme-aware-judge :
   naive-judge in v1.
4. **Cleaner control + paraphrase placement.** Control = same debaters minus the steering
   instruction. Paraphrase has one place to sit (the judge boundary); one-knows adds a
   second possible placement (the A→B channel), making "paraphrase defended" ambiguous.

**one-knows** (only A knows; A covertly recruits B via the channel) is the more novel,
steganography-faithful threat — the case where the hidden channel does irreplaceable
informational work and multi-turn is *required*. It's the ambitious follow-up, run only
after both-know shows there's an effect to bootstrap toward.

## Scorer / side-classifier judge (makes "covert" measurable)

- Fixes the **trivial-defection** failure mode (debater B just openly argues for A). A
  round only counts as covert steering if each argument still reads as defending its
  *assigned* side above a threshold.
- In v1-of-v2: use it as a **validity filter + reported metric**, not as an optimiser in
  the generation loop (rejection-sampling debaters until they pass = later work).
- Gives **two qualitatively different defences to compare**: paraphrase = a
  *transformation* defence; side-classifier = a *detection* defence. "Which kind of
  oversight catches covert steering" beats "does paraphrase work."
- The core tension it surfaces — **steering strength vs detectability** — is essentially
  the whole experiment.
- Build it as a generalisation of the fork's existing `core/scoring/concessions.py`
  (already does a judge-model Y/N classification).
- **Open question:** should the side-classifier and the naive judge be the *same* model?
  Circularity risk (the detector is the thing being steered) — decide deliberately.

## Repo / reuse decisions

- **Fork `ucl-dark/llm_debate`** (Khan et al., "Debating with More Persuasive LLMs"):
  QuALITY-based, multi-turn, sequential + simultaneous protocols, best-distractor wired
  in, concession scoring as a scorer-judge head start, and a cross-examination path
  already present.
- **v2 is its own repo** (the fork) — not nested in this one. This repo's design doc
  becomes a "parts bin": lift only the **encoding specs** and **paraphraser prompts**
  (Redwood `ContextAware` + `.suspicious()`, in this repo's design Appendix A). Do *not*
  carry over Redwood's pipeline/metric (bit-recovery ≠ judge accuracy) or interfaces.
- **Reuse from Redwood = paraphraser prompts only.** Reimplement on the fork's existing
  Anthropic wrapper.
- Build **additively** (a `steering/` package + new Hydra configs), leaving upstream
  `core/` intact for mergeability. **Phase 0 = modernise** the 2024-era model strings /
  API wrapper before anything runs.

## Cross-examination

Defer to a later phase. It's already a config/prompt path in the fork (not a from-scratch
build), and isn't necessary for the steering question. In a collusion setup it's
double-edged — it becomes a vector for colluders to stage a misleading softball exchange.

## Risks / things to stay honest about

- **Load-bearing empirical bet:** does a naive judge actually get moved by subtle
  rhetorical steering at all? It might not — "covert steering didn't reliably fool the
  judge in sequential QuALITY debate" is a legitimate result to publish, rather than
  escalating to ever-stronger attacks to manufacture an effect.

## Extension (recorded, not scoped): N-debaters + jury

Scaling 2-debaters/1-judge to N-debaters with a jury, and modelling how a steered signal
propagates to a tipping point across the jury, connects to voter-model / rumour-model
work. This is a **v3+ different project** that *uses* v2's infrastructure — not a v2
tweak. Same dependency logic: show steering moves a single judge first.

## Relationship to v1 (this repo)

The "v1" referenced throughout **is this repo** (`debate-stego`, single-turn, standalone,
Phases 1–4 complete). Its honest finding: the channel transmits and paraphrase destroys
it, but a realistic judge isn't fooled — i.e. it measured channel survival, not steering.
v2 (the fork) is the next, separate project. To execute v2, hand Claude Code the v2
design doc (the "Debate steering v2 design" artifact), same as v1's doc was handed over.
