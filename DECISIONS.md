# Decisions

*An architectural decision log for Pool Sauce. Claude Code appends to this as it builds. Charles appends when direction shifts. Read before making structural choices.*

---

## D-001 — v0 scope is locked to BUILD_BRIEF_01.md

**Date:** 2026-04-19
**Context:** Charles is a solo builder with Claude Code. The temptation to expand scope is constant.
**Decision:** v0 is the physics engine + Pillar composer + CLI, as defined in `BUILD_BRIEF_01.md`. Nothing else. All features listed below are valid future work, but v0 ships first.
**Consequence:** Refuse additions to v0 even when they seem small. Log them here instead.

---

## D-002 — Physics engine must remain invertible

**Date:** 2026-04-19
**Context:** A planned future feature is *automatic voiceover over arbitrary pool footage* — computer vision ingests video, reconstructs ball trajectories, and Rō narrates in the Way. This requires solving shots in reverse: *observed trajectory → reconstructed intention / sauce*, not just the forward direction *intention → trajectory* that v0 targets.
**Decision:** v0 does not implement the inverse solver, but the forward physics core must not preclude it. Specifically:

- Keep ball state representations first-class and serializable (position, velocity, spin all cleanly decomposable from any frame).
- Keep the integration step pure: given state at time *t*, produce state at *t+dt* with no hidden globals.
- Avoid baking "intention" into physics primitives. Intention lives in Pillar I; physics primitives work on kinematic state.
- Expose every intermediate quantity (contact point, impulse, spin transfer) as computable and observable, not just the final resting positions.

**Consequence:** When the inverse problem is taken up later, the forward engine is already a reusable oracle — the solver becomes optimization over trajectory space, not a rewrite.

---

## D-003 — Projection is a render target, not a product

**Date:** 2026-04-19
**Context:** Charles explored the idea of a projector-on-table training system (per PPB, ICATS, Thorsten Hohmann's setup at Amsterdam Billiards). Insight: any laptop running Pool Sauce outputs HDMI → projector, and the existing Pillar schema fields (line_of_aim vectors, escape_route path points, risk zones) are already drawable geometry.
**Decision:** Projection integration is not a hardware build. It is a *render mode* for the same engine. v0 does not implement it, but the overlay-drawing module (when it exists in v1) must separate *what to draw* from *where to draw it* — the same Pillar-derived geometry should feed a web canvas, a video overlay, and a projector calibration mapping without branching logic.
**Consequence:** Don't build rendering into the physics core. Don't build rendering at all in v0. When rendering arrives in v1, it is a thin layer that consumes `pillars.schema.json` and targets one of {canvas, video, projector}.

---

## D-004 — Voice cloning and TTS are out of scope for v0

**Date:** 2026-04-19
**Context:** Automatic voiceover implies a TTS voice for Rō. This is real work (voice actor reference session, ElevenLabs or equivalent, prosody calibration for the "deadly calm, surgical" register).
**Decision:** Out of scope for v0. The v0 CLI emits plain text in Rō's voice. Audio generation happens when there is something worth narrating and a channel that needs it.
**Consequence:** Don't introduce audio dependencies into the v0 codebase. Keep text output as the single source of truth.

---

## D-005 — Game-specific rules remain out of scope

**Date:** 2026-04-19
**Context:** 8-ball, 9-ball, straight pool, snooker — each has its own rack logic, legal-shot rules, foul conditions. The engine is game-agnostic by design.
**Decision:** No game rules in v0. Shots, not matches. If a game layer is needed later, it wraps the engine, not the other way around.
**Consequence:** The engine's public API takes a shot request and returns a shot result. It never asks "whose turn is it" or "is this a legal shot in 9-ball." Those questions belong to a caller that may or may not ever exist.

---

## D-006 — Shot library format = JSON files validated against pillars.schema.json

**Date:** 2026-04-19
**Context:** Future work includes a library of famous shots, classic breaks, and drills. Charles wants Rō to eventually narrate any canonical shot in pool history.
**Decision:** A shot is a JSON file that validates against `pillars.schema.json`. A break is an ordered sequence of shots. A drill is a sequence plus scoring criteria. The library is a folder of such files, nothing more.
**Consequence:** No custom library format, no database, no CMS for v0. If Charles transcribes a single famous shot by hand in v0 as a test fixture, that is the shot library. Scale comes from repetition, not from infrastructure.

---

## D-007 — Challenge markets, multiplayer, wagering: not this decade's problem

**Date:** 2026-04-19
**Context:** Charles floated the idea of viewer-vs-streamer challenge markets with stakes. Legally complex, requires audience and infrastructure that don't exist yet.
**Decision:** Hard out of scope. Not a v0 concern, not a v1 concern, not a conversation until the teaching engine has an audience and a proven value proposition.
**Consequence:** If this comes up again before the channel has real metrics, point at this entry and move on.

---

## D-008 — The interaction layer is core, not an enhancement

**Date:** 2026-04-19
**Context:** Charles named the "bank system" (cushion rebounds, throw, correction intelligence) as day-one critical. He's right. A pool teaching engine that models shots as angle-in-equals-angle-out and ignores throw is teaching false pool. Aim is trivial; what separates players is the interaction physics.
**Decision:** The interaction layer is a first-class requirement of Unit B in `BUILD_BRIEF_01.md`, not a future refinement. Specifically:
- Cushion rebounds must model pace- and spin-dependence (running english widens, reverse shortens; high pace shortens, low pace widens).
- Collisions must model cut-induced throw and spin-induced throw.
- Simulation state must be inspectable at every collision and rebound so Pillar V can diagnose "what went wrong."
- Table and cushion parameters must be tunable (fast cloth vs. slow, fresh cushion vs. dead) — not hardcoded.
**Consequence:** v0 is a larger v0. Worth it. A toy engine that shortcuts the interaction layer would be embarrassing to the brand and unusable for teaching. Shipping later with real physics beats shipping sooner with cartoon physics.
**Reference:** For the rebound model, a good starting point is the Marlow cushion model (empirical fits for angle/pace/spin dependence) calibrated against measurements. For throw, Dr. Dave's published coefficients on cut-induced and spin-induced throw are the de facto reference in the teaching community.

---

## D-009 — Pool Sauce is bootstrapped

**Date:** 2026-04-19
**Context:** Charles briefly explored a $200k pre-seed raise and then, on reflection, rejected the path. The project is self-funded.
**Decision:** No outside capital in year 1. No equity sold. The channel and Rōnin v0 ship on founder time and personal funds. Monetization (course, Patreon tier, sponsorships, content licensing) funds year 2 from year-1 revenue.
**Consequence:**
- The brand stays uncompromised. No investor-driven scope or aesthetic revisions.
- Build scope stays disciplined — no feature gets built because it would "look good in a deck."
- If capital becomes useful later (e.g., a specific hire that accelerates a concrete milestone), revisit then from a position of traction, not from a position of need.
- `INVESTMENT_MEMO.md` is withdrawn from the kit. If a raise ever happens, it will be from an entirely different posture.

---

## D-010 — Python package `poolsauce`, flat layout, dataclasses + numpy

**Date:** 2026-04-20
**Context:** Unit A needed the first concrete Python scaffold. The brief specifies Python + NumPy for the physics core and solo-builder ergonomics.
**Decision:** Package name `poolsauce` (matches the working repo slug in BUILD_BRIEF_01). Flat layout — `poolsauce/` at the repo root, no `src/` directory. State lives in plain dataclasses with numpy arrays for vector quantities. Hatch is the build backend. Optional `dev` extras pull in pytest only.
**Consequence:** Editable install via `pip install -e .` is the single local workflow. Adding modules is as simple as dropping a file into `poolsauce/`. No import gymnastics, no src/package split to remember six months from now. If strict package isolation or PyPI publishing ever matters, revisit then.

---

## D-011 — Ball state: 2D position/velocity, 3D angular velocity; coordinate convention locked

**Date:** 2026-04-20
**Context:** `BUILD_BRIEF_01` left coordinate convention and spin representation as open decisions for Unit A. Settling both now so every later unit (physics, solver, composer) types against the same model.
**Decision:**

- **Coordinate convention.** Origin at the bottom-left corner of the playing surface. `x` runs along the width (short side, default 1.27 m). `y` runs along the length (long side, default 2.54 m). `y` is up. `z` is out of the cloth, currently implicit.
- **Position and velocity.** 2D numpy arrays, SI units. Motion is planar for v0 (the ball rests on cloth at `z = radius`). Jumps and massé arcs are deferred — when they arrive, positions and velocities broaden to 3D without reshaping anything else.
- **Angular velocity.** 3D world-frame numpy array `[ωx, ωy, ωz]` in rad/s, stored as the primary form. Horizontal components resolve into topspin/backspin and side english relative to the ball's velocity direction; `ωz` is the vertical (massé) axis. Decomposition into Sauce vocabulary is a *view*, not a storage format. This matches how the integrator and, later, the inverse solver (D-002) will consume state.
- **Pocket naming.** Matches `pillars.schema.json` exactly — `bottom-left`, `bottom-right`, `top-left`, `top-right`, `side-left`, `side-right`. Side pockets sit at the midpoints of the two long rails (`x = 0` and `x = width`).

**Consequence:**

- Schema serializers project internal state onto the schema shape (e.g., `table_size_m = [length, width]`) — internal representation optimizes for clarity, schema output optimizes for contract fidelity.
- The integrator in Unit B consumes `angular_velocity` as a vector without first decomposing it; the Sauce translator (Unit D) owns the decomposition.
- Widening to 3D motion is additive, not a rewrite. The angular-velocity field is already 3D.

---

## D-012 — Free-flight integrator is analytic per phase

**Date:** 2026-04-20
**Context:** Unit B.1 (free-flight physics: sliding, rolling, spin decay, no collisions) is the first cut into Unit B. The brief leaves the integration method open (Euler / RK4 / event-driven). Each free-flight phase is governed by a linear ODE with a closed-form solution, and slip decays along a fixed direction throughout the sliding phase — so there is no numerical advantage to stepping.
**Decision:** The free-flight integrator is analytic per phase. Within a single `step_free_flight(ball, dt, table)` call, the ball resolves sliding → rolling → stopped transitions exactly at the epochs they occur, using closed-form expressions for position, velocity, and spin under each regime. Vertical spin (ωz) decays independently at rate `5 μ_sp g / (2 R)` over the full step, decoupled from horizontal phases. Rolling-constraint spin is snapped exactly at phase transitions to prevent float drift from reinjecting slip.
**Consequence:**
- `step_free_flight` is pure and deterministic. No timestep tuning knob; no integration error to budget against.
- When Unit B.2 (cushion rebounds) and B.3 (ball-ball collisions) land, they become *events* that interrupt free flight at a computed time. The event loop in B.4 advances free flight analytically up to the next event, applies the event's impulse, and repeats. This is the event-driven choice implicit in D-002.
- Massé and jump shots (out-of-plane motion) will need a separate integrator when they arrive — but they were already out of v0 scope (see D-011).

---

## D-013 — Cushion model is Marlow-lite, impulse-based, calibratable per table

**Date:** 2026-04-20
**Context:** Unit B.2 needs a cushion rebound model that honors the interaction-layer requirements from D-008: pace-dependent rebounds, side-english coupling, tunable per-table. A full Marlow fit requires empirical data we don't have yet. A toy "angle-in-equals-angle-out" model teaches false pool and is disqualified by the brief.
**Decision:** `cushion_rebound` is an instantaneous impulse applied when a ball crosses the cushion contact line. The model has three elastic parameters, all on `Table`:
- **Normal restitution** `cushion_efficiency` — scales `-v_n` straight through, constant per table.
- **Tangential retention** `k_t(pace) = max(k_min, k_base − α · |v_n|)` — the pace-dependence lives here. High pace shortens the bank; low pace widens it.
- **Side-english coupling** `Δv_t = c_spin · R · ω_z` plus a `side_english_loss` fraction on `ω_z`. Running english widens the rebound and partly survives the bounce; reverse english shortens it.

Horizontal spin components (ωx, ωy in world frame) pass through the rebound unchanged. Their post-rebound effect — topspin becoming effective backspin after a head-on reversal, etc. — is carried naturally by free flight on the cloth. This matches the brief's "vertical spin affects path, not angle" directly.

**Consequence:**
- All five cushion parameters live on `Table`, so a fast cloth / dead rail / tournament slate can be expressed as a different `Table`. No global state; no rebuild.
- The model is calibratable, not correct. When measurements arrive (camera rig, real table tests), the same five knobs get fit and we revise defaults; the API does not change.
- Arbitrary cushion orientations work: `cushion_rebound` accepts any 2D unit normal, not only the four axis-aligned rails. Pocket facing chamfers and diamond-pocket slate rails become trivial later.
- Z-axis effects (ball hopping off rails from topspin, massé shots) are deliberately out of scope — the v0 model is planar (D-011).

---

## D-014 — Ball-ball collision: one friction impulse drives cut and spin throw

**Date:** 2026-04-20
**Context:** Unit B.3 must produce cut-induced throw and spin-induced throw as first-class effects (D-008). Two naive options were rejected: (a) "swap velocities along line of centers" — teaches false pool; (b) separate empirical lookup tables for cut throw and spin throw — fragile, brittle to calibrate, doesn't compose.
**Decision:** `ball_collision(a, b, table)` resolves the pair with two impulses:

1. **Normal impulse** along the line of centers: `J_n = m_red · (1 + e_bb) · u_n`. Standard 1D elastic collision; handles unequal masses naturally.
2. **Tangential impulse** along the in-plane tangent, magnitude `min(μ · |J_n|, m_eff_t · |u_t|)` — Coulomb sliding capped by the sticking impulse. The tangential slip that drives it is:
   `u_t = (v_a − v_b) · t̂ + R_a · ω_{a,z} + R_b · ω_{b,z}`.

Cut throw emerges from the `(v_a − v_b) · t̂` term; spin throw emerges from the `R · ω_z` term. No branching, no lookup, same impulse formula. The tangential impulse also applies as a z-axis torque on both balls, which produces spin transfer in the opposite sense to the cue's spin — the documented real-world behavior.

Horizontal spin components (ωx, ωy) couple only to the out-of-plane slip, which the cloth absorbs as a constraint force. They are therefore inert in the collision and ride through unchanged — their post-collision effect lives in free-flight cloth physics, consistent with the planar model (D-011).

**Consequence:**
- Two new `Table` parameters: `ball_ball_restitution` (default 0.92) and `ball_ball_friction` (default 0.06). Tunable per-table for different ball conditions (chalked, humid, polished).
- Conservation invariants are enforced by construction: linear momentum is conserved (impulse pair); relative normal velocity is reversed by exactly `-e_bb`; kinetic energy cannot increase; pure tests all pass.
- Model is calibratable, not correct. When measurements arrive, μ_bb and e_bb get fit; the API is stable.

---

## D-015 — Simulator is analytic per phase, event-driven across balls

**Date:** 2026-04-20
**Context:** Unit B.4 must advance the full table state (many balls) through collisions, rebounds, and friction until rest, and expose every interaction for Pillar V auditability. Two naive approaches were rejected: (a) fixed-step Euler — accumulates error, clips events mid-step, violates D-012's analytic guarantee; (b) per-ball sequential simulation — loses the interaction between balls entirely.
**Decision:** `simulate(state, max_time)` runs an event-driven outer loop over all balls simultaneously. Each iteration:

1. Compute each moving ball's **phase end** (time to the next sliding→rolling→stop transition). This caps how far the current trajectory polynomial stays valid.
2. Detect **cushion events** — one quadratic root per ball × rail.
3. Detect **ball-ball events** — one quartic root per pair (from `|Δp(t)|² = (R_a + R_b)²`, with `Δp` quadratic in `t` within a phase).
4. Pick the earliest event time `t_next` across all detections, capped by phase ends and `max_time`.
5. Advance every ball by `t_next` through `step_free_flight` (which itself is analytic per D-012).
6. Apply the triggering impulse (`cushion_rebound` or `ball_collision`) with a validity re-check — if a simultaneous earlier event changed the ball's state so it is now separating, the later event is skipped rather than forced.

Residual vertical spin is drained after horizontal motion ceases. The returned `SimulationResult` has `final_balls`, an ordered tuple of `SimEvent`s (each with absolute time, kind, ball ids, and optional rail detail), and the total elapsed sim time.

**Consequence:**
- Trajectory polynomials are closed-form within each phase, so detection is pure root-finding — no integration error, no tunable timestep. Consistent with D-012 (analytic per phase) and D-002 (inspectable intermediate state).
- Pockets are deliberately out of scope for B.4. A ball aimed at a corner currently bounces off the straight cushion line rather than entering the pocket. Pocket events will be added when the Pillar composer (Unit F) needs them — same machinery (circular-zone crossing = quadratic root).
- Phase transitions are not recorded as events. They are only a validity boundary for quadratic trajectory segments; the brief's "inspectable at every collision and rebound" requirement is about impulses, not free-flight phase changes.
- The event log is sufficient input for Pillar V chemistry audits: the cue's zone landing, which cushions were struck, which balls were touched in what order, and the state snapshots can all be reconstructed from `final_balls` plus `events`.

---

## D-016 — Pocket detection is a simulator event, reusing the quartic solver

**Date:** 2026-04-20
**Context:** B.4 originally shipped without pocket handling (documented in D-015). The first inverse-solver round-trip test exposed the gap: object balls aimed at corners bounced off a "cushion" where the pocket actually is, so the OB never reached a pocket center. Deferring the fix was not viable — the Pillar composer and all round-trip testing depend on knowing when a ball sinks.
**Decision:** Pocket entry is a first-class `SimEvent` kind, detected with the same machinery as ball-ball collisions. Each pocket is a circular zone of radius `pocket_mouth_m` around its center; the time at which a ball's center crosses into the zone is a root of the same quartic (distance² reaches threshold²) the ball-ball solver already computes. When a pocket event fires, the ball is frozen at the pocket's center with zero motion, added to a `pocketed` set, and excluded from all further event detection. The `SimulationResult` exposes the pocketed IDs as a tuple.

This specifically keeps cushion and pocket events competing head-to-head in the same scheduler: near a corner, the pocket time resolves before the (spurious) cushion time, so the ball sinks instead of bouncing. Away from pockets, the pocket radius is out of reach and the cushion wins — no regression in open-table dynamics.

**Consequence:**
- Pocket geometry is a single radius per table (`pocket_mouth_m`). Corner vs side pocket asymmetry and pocket facing geometry (jaws, slate drop) are not modeled. Good enough for the teaching plan; refine when measurements demand it.
- Balls pocketed at `t < total_time` remain in `final_balls` at pocket-center with zero motion, which keeps the downstream Pillar V audit trivially readable (loop `final_balls`, cross-reference `pocketed` and the event log).
- No new API surface on top of `SimEvent`; the existing `kind` field gained the `"pocket"` literal.

---

## D-017 — Unit C v0 is geometry + rolling-friction pace, direct shots only

**Date:** 2026-04-20
**Context:** The inverse problem (given intention → cue state) spans 5 DOF (cue velocity x/y, ωx/ωy/ωz) with a nonlinear forward map. A full optimizer is out of reach for v0 and, importantly, not needed to produce a valid Pillar II plan — players think in geometry and pace, not impulse vectors.
**Decision:** `solve_direct_shot` returns a `ShotPlan` with **geometry** (ghost ball, line of aim, cut angle, contact fraction, OB direction, natural tangent line) and a **pace floor** (minimum cue speed to sink the object ball). Blockers along the aim segment are flagged. Banks, kicks, throw compensation, and cue-ball destination matching are deferred.

The pace floor is derived analytically: the OB leaves the collision with no spin, so its stop distance follows the sliding-then-rolling formula from D-012. Invert that to find the post-impact OB speed required, back-propagate through the collision to find the cue speed at contact, and add the rolling-friction loss over the cue's travel (the `cue_state_for_plan` helper builds a pure-rolling cue, matching this assumption).

**Consequence:**
- `cue_state_for_plan(cue, plan, speed)` produces a simulable cue-ball state, so every plan is round-trippable: solve → simulate → verify the OB sinks. Three tests do exactly this at progressively wider cut angles.
- Throw compensation and cue destination are the next blades in the same unit — not a rewrite. The geometry already exposes `natural_tangent_line` (the stun path), which is the foundation for cue-destination matching via speed along the tangent and spin off it.
- Impossible cuts (≥ 90°) raise `ShotSolverError` with clear context. Blocked shots return a plan with `blockers` populated — the caller decides whether to fall back to a bank (future work) or label the shot unplayable.

---

## D-018 — Sauce translator: tip offsets in units of "tips", calibratable fraction

**Date:** 2026-04-20
**Context:** Unit D must translate between the Sauce vocabulary ("pinch of right", "zest of follow") and the angular velocity the forward physics consumes. The vocabulary is brand-specified; the physics is calibration-specified. Three knobs decide everything: the Sauce phrases and their numeric values (in tips), the ball-radius fraction that one tip represents, and the impulse-torque formula converting offset to ω.
**Decision:** One "tip" is defined as `TIP_FRACTION_OF_R = 0.20` of the ball radius — an anchor that reflects real cue-tip geometry (tip radius ≈ 0.21·R on standard gear). Each Sauce phrase maps to a signed tip value: `±0.25` (pinch / zest / whisper), `±0.50` (drop), `±1.00` (healthy pour / full). `stroke_to_cue_state` applies the standard impulse-torque formula `ω = 2.5·v·b/R²` along the correct axis: `+ẑ` for horizontal offset, `ẑ × d̂` for vertical offset — so right english gives `+ω_z`, and follow gives ω aligned with the natural rolling axis for the stroke direction.

The mapping is fully invertible: `angular_velocity_to_tip_offsets` reads back the stroke from an observed ω. Pillar V audits use this to describe what *actually* happened ("the stroke landed as drop of right, zest of follow") without needing to replay the stroke.

**Consequence:**
- Cue deflection ("squirt") and spin-induced cue-tip offset off line of aim are not modeled in v0. True for modest english; off by 1-3° at extreme offsets. API stays stable when the squirt model is added.
- The three knobs — phrase-to-tips table, `TIP_FRACTION_OF_R`, impulse constant — are separate and each tunable without touching the others. Re-anchoring tips against measured data changes one constant; re-anchoring the vocabulary mapping changes the dict. No code logic changes.
- `describe_stroke` is a nearest-phrase snap, so intermediate offsets (e.g., 0.48 tips) still map to a Sauce phrase. Rō's output never has to invent vocabulary; the brand-safe dictionary always provides a phrase.

---

## D-019 — Pillar schema `risk_zones` field renamed to `risk_zones_crossed`

**Date:** 2026-04-20
**Context:** The schema's `pillar_V.required` array listed `risk_zones`, but the corresponding `properties` entry was named `risk_zones_crossed`. The composer could not emit a valid document — the required name had no backing property and the backing property was not required.
**Decision:** `required` now reads `risk_zones_crossed`, matching the property name. This is a schema typo fix, not a semantic change — nothing in the rest of the stack referred to the old name.
**Consequence:** No API change. Documents previously drafted by hand against the old required name would have been invalid anyway.

---

## D-020 — Composer is the solver + sauce + simulator stitched into the Pillar schema

**Date:** 2026-04-20
**Context:** Unit F (Pillar I-III) and Unit G (Pillar V) must produce documents that validate against `pillars.schema.json`. The schema has many required fields and enum constraints; the upstream units (A-E) expose raw physics, not brand phrasing.
**Decision:** `compose_pillar_plan` takes an `Intention`, a `SauceChoice`, and the table state; runs `solve_direct_shot`, builds a simulation from the planned stroke, and assembles the Pillar I-III fields — translating angles, distances, and sauce phrases into the schema's enums (`force`, `acceleration`, `stroke.type`). `compose_debrief` takes a completed plan and a `SimulationResult`, auto-computes zone landing and pace control from the intended-vs-actual geometry, and leaves the subjective verdicts (spin chemistry, correct side, 1% excellent/fragile) to `DebriefOverrides` with safe defaults.

The schema's descriptive fields (`description` on LoA, contact, escape) are generated by small formatter helpers so Rō's voice can evolve without touching physics. The enums (force/acceleration/stroke type/pace control/correct side/spin verdict/risk zones) are validated up-front; an invalid override raises before any output is built.

**Consequence:**
- Round-trip is verified: every composed plan validates against the canonical schema, so the overlay pipeline can consume it without guessing.
- The debrief composer is deliberately half-automated: physics-derived fields (zone, pace) are computed; subjective fields are overridable. This matches the brief's "honesty engine" — Rō does not invent verdicts.
- Pillar IV is a literal const block. The engine will not fill it; the user owns execution.

---

## D-021 — CLI is the v0 front door: two subcommands, JSON-in/text-out

**Date:** 2026-04-20
**Context:** The v0 definition of done is a CLI that loads a table state from JSON, accepts an intention in text, and prints a Pillar plan — plus a debrief subcommand given a plan and outcome. No graphics, no persistence, no accounts.
**Decision:** `poolsauce plan` and `poolsauce debrief`. The `plan` subcommand takes `--state`, `--target`, `--pocket`, `--destination`, plus optional Sauce flags (`--english`, `--stroke`, `--force`, `--acceleration`), and prints the plan in the CLAUDE.md output format (or `--json` for the raw document). The `debrief` subcommand takes `--plan` + `--state`, simulates the planned stroke forward, and prints the full plan with a Pillar V block appended. An entry point is registered in `pyproject.toml` so `pip install -e .` gives `poolsauce` on PATH.

State JSON is the schema's `table_state` shape (same as the composer emits) — a ball list with `id`, `x_m`, `y_m`. Cue ball must have id `"cue"`.

**Consequence:**
- Round-trippable: plan → JSON → debrief → JSON. Every step of the ronin's routine is text-only, replayable, versionable.
- No REPL in v0. The CLI reads args and exits. Interactive flows are a future polish layer.
- Overlay integration is trivial when it arrives: the same JSON fed to the CLI is the exact shape the overlay UI consumes (D-003 — projection is a render target, not a product).

---

## D-022 — Solver compensates for cut-induced throw by default

**Date:** 2026-04-20
**Context:** D-017 shipped a direct-shot solver that returned the pure geometric ghost ball. This is wrong: real collisions throw the object ball 1-5° off the line of centers (D-014), and without compensation every cut shot misses by that margin. A Pillar II plan that ignores throw teaches false pool.
**Decision:** `solve_direct_shot` now shifts the ghost ball to counter cut-induced throw by default. The throw magnitude is derived from the same impulse physics the collision resolver uses — sticking regime for small cuts (`tan(θ) ≤ 3.5·μ·(1+e)`), sliding regime for larger cuts where throw asymptotes to `atan(μ)` (≈ 3.4° on default gear). A two-pass fixed-point iteration settles the aim, since changing the aim slightly changes the cut angle, which slightly changes the throw.

The throw direction is fixed by which side of the OB-to-pocket line the cue approaches from, determined before the fixed-point loop so it cannot oscillate. The final `ShotPlan` exposes `throw_angle_deg` (signed) so the overlay can render the correction. Compensation can be disabled with `compensate_throw=False` for diagnostics or teaching, which reproduces the old pure-geometric behavior.

Speed dependence of throw (shorter contact time at high pace → less friction impulse per unit momentum → smaller throw) is deliberately NOT modeled in v0. The time-averaged impulse approximation smears it out. Calibrate when camera-rig measurements arrive.

**Consequence:**
- A round-trip sanity test shows compensation reduces the OB's post-collision angular miss by ~3° on a wide-cut shot, matching the expected `atan(μ)` correction. Straight shots are unchanged (throw is zero).
- All other Pillar II fields (`cut_angle_deg`, `contact_fraction`, `natural_tangent_line`) reflect the *apparent* cut — the geometry the player sees from the cue-ball-to-pocket sightline. This is what they use to visualize the shot. The internal physical cut (between aim and the shifted LoC) differs by `throw_angle_deg`; the minimum cue speed uses the physical cut for correctness.
- When we add cue-ball destination matching (the next blade), the cue's post-collision tangent line is computed from the physical LoC, so throw compensation automatically propagates into destination planning.

---

## D-023 — Cue-ball destination matching is a grid-search solver

**Date:** 2026-04-20
**Context:** Direct shots now account for throw (D-022), but the solver still answers only *where to aim*, not *what stroke lands the cue on the 7*. That second question is the one players actually ask: given a Pillar II aim, find the (speed, vertical english, horizontal english) that puts the cue ball at a specified destination. The forward map is nonlinear (friction phases, collision impulse, rail bounces); a clean analytic inverse is out of reach for v0.
**Decision:** `solve_cue_destination` performs a brute-force grid search over three continuous variables — speed margin (multiple of the minimum), vertical tips, horizontal tips — simulating each candidate forward and picking the recipe whose final cue landing minimizes distance to the target. Scratches are filtered. Default grid is 7·5·5 = 175 candidates; each simulation is sub-millisecond so the full search completes in ~0.2s. The returned `CueDestinationRecipe` holds both the numeric tip offsets and the simulator-predicted landing so the caller can reproduce the shot or present it. The CLI's `plan --auto-sauce` invokes this when `--dest-xy` is supplied.

**Consequence:**
- Resolution is limited by the coarse grid. A 15 cm target is reliably found within B-zone (<30 cm); fine-grained positional control will need a local refinement pass (e.g., Nelder-Mead around the best grid point). Not added to v0 — the brand-visible output snaps to Sauce vocabulary anyway, which has ~5-10 cm quantization at typical cut angles.
- No scipy dependency. `numpy.linspace` + loop keeps the single-dependency footprint from D-010.
- The solver does not reason about *why* a recipe works (draw pulls cue back; follow carries it forward). It only sees final landings. If that becomes a teaching gap, a symbolic layer on top can annotate — the solver still owns the numeric truth.
- Round-trippable: building a cue state from the recipe and simulating reproduces the solver's predicted landing exactly (pinned by test).

---

## D-024 — Squirt (cue-ball deflection) is modeled; supersedes the D-017 deferral

**Date:** 2026-06-11
**Context:** D-017 deferred squirt with a noted 1–3° error at extreme english. But the product is an *aiming* tool — the moment an aim line is shown with any side english, ignoring squirt makes that line wrong by 1–3°, undermining the one thing the user must trust. Audited the engine against Dr. Dave Alciatore's technical proofs; squirt was the only gap that corrupts displayed output (massé/jump stay deferred per D-011; speed-dependent throw per D-022).
**Decision:** Model squirt with the **natural pivot-length** model: `tan(squirt) = tip_offset / pivot_length`, default pivot 0.279 m (11 in), exposed as `Table.squirt_pivot_length_m` (per-cue calibration knob). `sauce.squirt_angle_rad` computes it; `stroke_to_cue_state` deflects the launch velocity toward the side opposite the english (opt-in via `squirt_pivot_length_m`, so existing geometric callers are unchanged). `sauce.aim_for_cue_path` inverts it. The composer aims the stick off-line by the squirt angle so the simulated cue ball still travels the solved `line_of_aim`, and exposes both `squirt_deg` and `stick_aim_vector` under `pillar_II.line_of_aim` — "aim here, the ball travels there." The 30-degree rule is validated as an emergent property (test_thirty_degree_rule: half-ball settles at 29.6°).
**Consequence:**
- Squirt magnitude is only as right as the pivot length, which is per-cue. Default is a sane all-round value; true accuracy waits on the table/cue calibration ritual.
- `stroke_to_cue_state` keeps squirt **off by default** — diagnostics and teaching geometry stay pure; only the composer (live play) enables it.
- Schema gained no `additionalProperties: false`, so the new `line_of_aim` fields validate cleanly. Overlay can later draw the stick-aim line alongside the ball path.
- Gearing and speed-dependent throw remain deferred; massé/jump await the 3D extension (D-011).

---

## D-025 — Multi-rail bank solver: mirror seed, forward-sim verified

**Date:** 2026-06-11
**Context:** A direct shot can be geometrically impossible (the cut would pass through the ball) while the ball is still potable off the cushions. The engine was returning "cut angle not achievable" and stopping — wrong, when a bank exists. The D-018 deferral (multi-rail paths) became worth delivering once the user asked for a 1/2/3-rail selector.
**Decision:** New `poolsauce/banks.py` with `solve_bank_shot(state, target, pocket, num_rails)`. Method: for each rail sequence of the requested length (no consecutive repeats), reflect the pocket across those rails (reverse contact order) to get a virtual pocket — the mirror seed for the object-ball aim. Because our cushions are NOT ideal mirrors (efficiency 0.75, pace-dependent retention, D-013), the seed is only a starting point: sweep aim (±8°, seed-outward order) × speed (3–6.6 m/s) and forward-simulate each candidate, returning the first where the OB actually drops in the intended pocket. Rail count is verified from the OB's cushion `SimEvent`s, excluding incidental grazes on the rails the pocket physically sits on (`_POCKET_RAILS`), so a corner pot off one rail reads as a "1-railer". `compose_bank_plan` wraps it into a schema-valid Pillar plan carrying the OB zig-zag under `pillar_II.bank.ob_path_points_m`; the API `/api/plan` accepts `bank_rails`; the PWA has a Direct/1/2/3 selector and draws the path.
**Consequence:**
- The simulator is the source of truth: a returned BankPlan is *verified to pot*, not merely computed to. Mirror geometry only seeds the search.
- Success returns in ~0.5–1.5s (early exit on first pot). "No bank exists" is the slow path (~3–5s for 3 rails) since it must exhaust the grid — acceptable behind the "SEARCHING THE RAILS" spinner.
- A genuine bank that deliberately uses a pocket-adjacent rail is under-counted by `_POCKET_RAILS` exclusion. Acceptable for v1; revisit if it misleads.
- Kicks (cue ball banks off rails to reach the OB) are the sibling problem and remain unbuilt — the same mirror-seed + verify approach will apply.
- Grid resolution bounds precision; a finer local refinement (Nelder-Mead around the potting seed) can sharpen aim later without changing the contract.

---

## D-026 — The composer optimizes Sauce for position, not just the pot

**Date:** 2026-06-11
**Context:** The composer defaulted Pillar III to whatever SauceChoice it was handed (stun, in the API default) and wrote a rationale about the *pot* — "no spin needed." But that says nothing about the *leave*. A user flagged a shot where stun strands the cue at the top rail 1.14 m from the intended center-left position; a touch of running left english would open the rebound. The engine already had `solve_cue_destination` (D-023) but never called it from the composer — so the spin recommendation was never earned.
**Decision:** `compose_pillar_plan` gains `optimize_for_destination`. When set and the intention carries `destination_coordinates_m`, it runs `solve_cue_destination` to find the spin/speed that lands the cue on the leave, snaps the result to Sauce phrases via `describe_stroke`, and writes a rationale that reflects the position goal and how tight the angle is (`_position_rationale`, keyed on the solver's landing error). The API exposes `optimize_sauce`; the PWA has an "ADVISE SPIN FOR POSITION" toggle (on by default, enabled when a coordinate destination is set). On the flagged shot the optimizer returns *healthy pour of left + full follow* — confirming the player's instinct.
**Consequence:**
- Pillar III spin is now *derived* when a destination is given, not defaulted. The rationale is honest: it states when the leave is reachable vs when "the angle is tight" (large residual error).
- The optimizer can recommend aggressive spin (full english, high speed) when the leave is geometrically hard; the rationale's tight-angle phrasing flags that rather than overselling. A local refinement around the grid optimum (D-023 consequence) would sharpen amounts later.
- Direct shots without a coordinate destination still default to stun — the optimization is opt-in and coordinate-gated, so existing behavior and tests are unchanged.
- Squirt compensation (D-024) composes with the derived english automatically: the stick re-aims for whatever side spin the optimizer picks.

---

## D-027 — Position optimizer favors the most replicable stroke

**Date:** 2026-06-11
**Context:** D-026 made the engine optimize spin for position, but it minimized raw landing error — so it reached for maximum english and pace to claw the last centimeters of shape. The user's correction: maximum spin and speed multiply miscues, mistrokes, and failed attempts; the engine should recommend the *most replicable* strike, and position (not the pot — "sinking is not much of a challenge if you aim properly") is the priority objective.
**Decision:** `solve_cue_destination` selection is now two-stage. (1) Position priority: among candidates that pot the object ball (preferred over those that don't), find the best achievable landing error `E*`. (2) Replicability tiebreak: among candidates landing within `position_band_m` (default 0.06 m) of `E*`, return the one with the lowest replicability cost `spin_cost·(v²+h²) + speed_cost·max(0,margin−comfort)²`. So spin and pace are dropped unless they improve the leave by more than the band — they must earn their keep. A recommendation must pot the ball (a no-pot stroke is not a valid shot), but position drives the optimization on top of that.
**Consequence:**
- On the flagged shot the recommendation drops from "full pour of left + full follow" to "full follow, no english" — the left english bought ~1 cm and wasn't worth the risk. Follow + pace stay because the leave is genuinely far (the rationale says so: "the angle is tight").
- The old "land closest by any means, even a miss" behavior is gone; a prior test that asserted position accuracy via a non-potting stroke was corrected to require the pot and reward a gentle stroke.
- Weights (`spin_cost_weight`, `speed_cost_weight`, `comfort_margin`, `position_band_m`) are exposed for calibration. Real miscue/variance data would tune them; defaults encode "don't chase <6 cm of shape with extra spin."
- Replicability is still a proxy (tip-offset magnitude + excess pace), not a measured miscue model. A physical miscue-limit term (spin beyond ~0.5 R tip offset) can refine it later.

---

## D-028 — Beta scope is 3 balls; ranked stroke options to an exact target

**Date:** 2026-06-11
**Context:** Two requests. (1) Keep the beta focused: only the 8, 9, and cue ball, placed in that order (cue last). (2) Beyond zone presets, let the player pick the *exact* spot to land the cue, then offer several strokes ranked by how repeatable they are — like cheating an object ball into a pocket, where many strokes reach the same neighborhood by different spin at different difficulty.
**Decision:**
- *3-ball scope:* manual placement auto-assigns the next ball in `[8, 9, cue]` per tap; the target selector offers only the placed object balls (8/9); the old 1–9 sequence UI is gone.
- *Exact target + ranked options:* `solve_cue_destination_options` (new) simulates the speed×spin grid, keeps strokes that pot the ball and rates each by a replicability `difficulty = |v_tips| + |h_tips| + 0.6·excess_pace`, deduplicates to distinct stroke *styles* (draw/stun/follow × left/center/right), flags `makeable` (within `tolerance_m` of the target), and returns the top-N ranked most-replicable-first with labels stock/comfortable/tricky/hard. API `/api/cue-options`; the PWA has an "⊕ EXACT SPOT" tap-to-place on the table and a tappable ranked-options list that drives the strike insert.
**Consequence:**
- The optimizer's single-best path (D-026/D-027) and this ranked menu share the same physics; the menu surfaces the *trade-off* (easiest stroke lands at the zone edge; a slightly harder one lands dead-center) instead of hiding it behind one answer.
- Difficulty is the same replicability proxy as D-027 (tip magnitude + pace), not a measured miscue model — same calibration caveat.
- Scope is a UI/flow constraint, not an engine one: the physics still handles any ball set; widening the beta later is a frontend change.

---

## Template for future decisions

```
## D-NNN — <one-line title>

**Date:** YYYY-MM-DD
**Context:** What forced this decision.
**Decision:** What was decided.
**Consequence:** What this forbids or enables downstream.
```

---

*No movement until intention is pure.*
