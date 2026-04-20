# Pool Sauce — Build Brief 01

*This document is a kickoff prompt for Claude Code. Paired with `CLAUDE.md` (the Rōnin operating doctrine), it defines what to build first, what to defer, and what to refuse.*

---

## Project

**Name:** Pool Sauce (working title — `poolsauce` as repo slug)
**Owner:** Charles Brunold (solo for v0, collaborators later)
**Mission:** Build the computational core of *The Way of the Pool Player* — a physics-grounded shot intelligence engine that teaches pool through the Five Pillars.

**Not in scope yet:** mobile apps, multiplayer, streaming integration, challenge markets, monetization, UI polish. These wait until the engine teaches well.

**In scope now:** a physics core that, given a table state and a stated intention, produces a valid Pillar I–III plan and, given an outcome, produces a valid Pillar V debrief.

---

## Constraints

1. **Game-agnostic.** No 8-ball rules, no 9-ball rules, no rack logic. The engine reasons about *shots*, not matches. Game-specific logic can be layered on later by other code; the core must not assume a game.

2. **Output is the product.** Every computed shot must serialize cleanly to `pillars.schema.json`. The schema is the data contract. If a computation can't produce a valid Pillar output, the computation is incomplete.

3. **Physics before polish.** No rendering, no animation, no UI. A CLI or notebook that prints Pillar outputs from table state is a complete v0.

4. **Solo-builder ergonomics.** Code should be readable by Charles six months from now with no docs beyond what's in the repo. No clever metaprogramming. No premature abstraction.

5. **Rō voice when it helps, silence when it doesn't.** Code comments are technical. README and user-facing strings carry the Way. Don't force doctrine into docstrings.

---

## What to build, in the order you choose

Claude Code picks the milestone sequence. The following are the *units of work* that must all exist before v0 is done, but their order is yours to determine based on what unblocks what.

### Unit A — Table & ball state
A clean data model for a pool table and the balls on it. SI units, coordinates from bottom-left corner. Ball radius, table dimensions, cloth properties (friction coefficients) all configurable. Default: 9-foot table, standard pool ball.

### Unit B — Shot physics (the interaction layer)
Given initial cue ball state (position, velocity vector, angular velocity / spin), simulate the cue ball's trajectory including all of the following. **These are not optional refinements — they are what Pool Sauce teaches. Without them the engine lies.**

- **Rolling and sliding friction** — cloth drag differentiated for rolling vs. sliding phases, with spin decay.
- **Cushion rebounds (the bank model).** *Not* angle-in-equals-angle-out. Rebounds are a function of:
  - Incoming angle
  - Incoming pace (high-pace banks shorten; low-pace banks widen)
  - Incoming spin (running english widens, reverse english shortens, vertical spin affects the cue ball's post-rebound path but not the angle)
  - Cushion efficiency (tunable per-table to capture "fast" vs. "dead" cushions)
- **Ball-to-ball collisions, including throw.** Cut-induced throw (the object ball departing a degree or two off the geometric line because of friction at impact) and spin-induced throw (side english on the cue ball imparting transverse motion on the object ball). Both measurable, both teaching-critical.
- **Spin transfer and decay.** English on the cue ball partially transfers to the object ball on contact (small but non-zero). Cue ball spin evolves over time: sliding → rolling, english decays at a different rate from top/back spin.
- **Counter-cut and correction hooks.** When the engine is asked "I aimed here and hit there," it must be able to reason backwards: was it throw? pace? english? cue elevation? The simulation must expose enough intermediate state to answer that question.

Output: a time series of cue ball and object ball positions, full intermediate state at every collision and rebound (so Pillar V debriefs can audit chemistry), and final resting positions of all balls touched.

### Unit C — Inverse shot solver
Given an intention (target ball, pocket, desired cue ball destination), solve for the cue-ball initial state that produces it. This is Pillar II in code: line of aim, contact point, cut angle, escape route, rails involved, required speed window.

### Unit D — Sauce translator
A bidirectional mapping between physical parameters (tip offset in mm, spin rate in rad/s, cue speed in m/s) and Sauce vocabulary ("a pinch of right", "a zest of follow", "measured dose"). Both directions matter: compute → Sauce phrase (for output), Sauce phrase → physics (for user-authored shots).

### Unit E — Zone evaluator
Given a target destination and an actual cue ball landing position, classify the result as A/B/C zone. Zones are defined relative to the *next shot's requirements*, not absolute table coordinates. Requires an optional "next target" input.

### Unit F — Pillar I–III composer
Pulls from Units A–E to produce a full Pillar I–III plan that validates against `pillars.schema.json`. The public function Rō calls.

### Unit G — Pillar V composer
Given a plan (from Unit F) and a reported outcome (actual ball landing, actual spin behavior, etc.), produces a Pillar V debrief that validates against the schema. The honesty engine.

### Unit H — CLI / REPL
A human-facing entry point. At minimum: load a table state from JSON, state an intention in text, get a Pillar plan back. No graphics. A ronin works with less.

---

## Decisions to make as you go

These are open questions. Make them, document them in a `DECISIONS.md`, move on. Don't ask Charles to pick unless truly blocking.

- Numeric integration method for shot physics (Euler vs. RK4 vs. event-driven).
- How to represent spin (axis-angle? angular velocity vector? both?).
- Table coordinate convention (origin bottom-left, y-up, SI meters — unless a stronger reason emerges).
- How Pillar III maps tip offset to spin numerically (calibration will refine later; pick a sensible default).
- Testing strategy (property-based tests on physics invariants are encouraged; energy conservation under friction is a classic check).

---

## Definition of done for v0

You can demonstrate, from a fresh clone, in under five minutes:

1. A CLI command that takes a JSON table state and a text intention ("6 in the top-left, leave on the 7 center-table").
2. Output that is a valid instance of `pillars.schema.json`, Pillars I through III.
3. A follow-up command that accepts an outcome ("cue ball landed at [x, y], missed the 6") and produces a valid Pillar V debrief.
4. The printed output reads in Rō's voice — short, surgical, one line of doctrine max.

No web UI. No database. No auth. No users. Just the engine and its voice.

---

## What to refuse

If Charles asks you to build any of the following during v0, cite this brief and decline:

- Any UI beyond CLI
- Mobile or web app scaffolding
- User accounts, login, profiles
- Streaming integration
- Challenge/wagering mechanics
- Game-specific rule engines (8-ball, 9-ball, etc.)
- AR / computer vision from phone cameras

These are all valid future work. They are not v0. The Way is built inside-out.

---

## First move

Read `CLAUDE.md`. Read `pillars.schema.json`. Then pick your first unit and begin.

*No movement until intention is pure.*

— Charles
