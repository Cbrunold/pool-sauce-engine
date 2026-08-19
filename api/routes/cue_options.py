"""POST /api/cue-options — ranked strokes to an exact cue destination."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from api.models import CueOptionsRequest, CueOptionsResponse, RankedOption
from poolsauce import (
    Ball,
    Table,
    TableState,
    solve_cue_destination_options,
    solve_direct_shot,
)
from poolsauce.sauce import describe_stroke
from poolsauce.solver import ShotSolverError

router = APIRouter()


@router.post("/cue-options", response_model=CueOptionsResponse)
def cue_options(req: CueOptionsRequest) -> CueOptionsResponse:
    try:
        length, width = req.state.table_size_m
        table = Table(length_m=length, width_m=width)
        balls = [Ball(id=b.id, position=[b.x_m, b.y_m]) for b in req.state.balls]
        state = TableState(table=table, balls=balls)

        plan = solve_direct_shot(
            state, req.intention.target_ball_id, req.intention.pocket,
            cue_ball_id=req.cue_ball_id,
        )
        target = np.array(req.target_position_m, dtype=float)
        ranked = solve_cue_destination_options(
            state, plan, target,
            cue_ball_id=req.cue_ball_id,
            tolerance_m=req.tolerance_m,
            max_options=req.max_options,
        )

        options = []
        for r in ranked:
            presc = describe_stroke(r.recipe.vertical_tips, r.recipe.horizontal_tips)
            options.append(RankedOption(
                rank=r.rank,
                difficulty_label=r.difficulty_label,
                difficulty=round(r.difficulty, 3),
                makeable=r.makeable,
                english=presc.english,
                stroke=presc.stroke,
                vertical_tips=r.recipe.vertical_tips,
                horizontal_tips=r.recipe.horizontal_tips,
                speed_margin=r.recipe.speed_margin,
                predicted_landing_m=(
                    float(r.recipe.predicted_cue_landing_m[0]),
                    float(r.recipe.predicted_cue_landing_m[1]),
                ),
                landing_error_m=round(r.recipe.landing_error_m, 3),
            ))
        return CueOptionsResponse(options=options)

    except ShotSolverError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
