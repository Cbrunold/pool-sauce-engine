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
