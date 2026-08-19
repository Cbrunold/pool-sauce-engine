"""POST /api/debrief — compose a Pillar V debrief.

The debrief route re-runs the planned stroke through the physics simulator
to obtain an authoritative SimulationResult, then overrides the cue ball's
final position with the reported actual landing before computing zone/pace.
This approach keeps the debrief honest: physics + human report, not physics
alone.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from api.models import DebriefRequest, DebriefResponse
from poolsauce import (
    Ball,
    Table,
    TableState,
    compose_debrief,
    simulate,
)
from poolsauce.debrief import DebriefOverrides
from poolsauce.sauce import cue_state_from_sauce
from poolsauce.solver import solve_direct_shot, ShotSolverError

router = APIRouter()


def _rebuild_state(plan: dict) -> TableState:
    ts = plan.get("table_state", {})
    length, width = ts.get("table_size_m", [2.54, 1.27])
    table = Table(length_m=length, width_m=width)
    balls = []
    cb = ts.get("cue_ball", {})
    if cb:
        balls.append(Ball(id="cue", position=[cb["x_m"], cb["y_m"]]))
    for b in ts.get("balls", []):
        balls.append(Ball(id=b["id"], position=[b["x_m"], b["y_m"]]))
    return TableState(table=table, balls=balls)


@router.post("/debrief", response_model=DebriefResponse)
def debrief(req: DebriefRequest) -> DebriefResponse:
    try:
        plan = req.plan
        state = _rebuild_state(plan)

        # Re-solve the shot to build cue launch state
        p1 = plan.get("pillar_I", {})
        p3 = plan.get("pillar_III", {})
        pocket = p1.get("pocket", "top-right")
        target_id = p1.get("target", {}).get("ball", "1")

        shot_plan = solve_direct_shot(state, target_id, pocket)

        english = p3.get("english", {}).get("sauce_term", "none")
        stroke = p3.get("stroke", {}).get("sauce_term", "spoon of stun")
        speed_window = plan.get("pillar_II", {}).get("speed_window", {})
        speed_m_s = speed_window.get("min_m_s", 1.5) * 1.15

        cue = state.cue_ball
        direction = shot_plan.line_of_aim
        cue_launched = cue_state_from_sauce(
            cue, direction, speed_m_s, english, stroke
        )

        # Forward simulate
        sim_state = TableState(table=state.table, balls=[
            b for b in state.balls if b.id != "cue"
        ] + [cue_launched])
        sim_result = simulate(sim_state, duration=10.0)

        # Override cue final position with reported actual if provided
        if req.actual_cue_position_m is not None:
            ax, ay = req.actual_cue_position_m
            for ball in sim_result.final_state.balls:
                if ball.id == "cue":
                    ball.position = np.array([ax, ay])
                    break

        overrides = DebriefOverrides(
            spin_verdict=req.overrides.spin_verdict,
            spin_notes=req.overrides.spin_notes,
            pace_control=req.overrides.pace_control,
            correct_side=req.overrides.correct_side,
            risk_zones_crossed=tuple(req.overrides.risk_zones_crossed),
            mastery_excellent=req.overrides.mastery_excellent,
            mastery_fragile=req.overrides.mastery_fragile,
        )

        result = compose_debrief(plan, sim_result, overrides)
        return DebriefResponse(plan=result)

    except ShotSolverError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
