"""POST /api/plan — compose a Pillar I-III shot plan."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import PlanRequest, PlanResponse
from poolsauce import (
    Ball,
    Intention,
    SauceChoice,
    Table,
    TableState,
    compose_bank_plan,
    compose_pillar_plan,
)
from poolsauce.solver import ShotSolverError

router = APIRouter()


def _build_table_state(req: PlanRequest) -> TableState:
    length, width = req.state.table_size_m
    table = Table(length_m=length, width_m=width)
    balls = [Ball(id=b.id, position=[b.x_m, b.y_m]) for b in req.state.balls]
    return TableState(table=table, balls=balls)


def _map_force(force: str) -> str:
    mapping = {
        "soft": "soft",
        "measured": "measured dose",
        "firm": "firm",
        "break": "break",
    }
    return mapping.get(force, "measured dose")


def _map_acceleration(accel: str) -> str:
    mapping = {
        "decelerating": "decelerating into",
        "controlled": "controlled",
        "accelerating": "accelerating through",
    }
    return mapping.get(accel, "controlled")


@router.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    try:
        state = _build_table_state(req)
        intention = Intention(
            target_ball_id=req.intention.target_ball_id,
            pocket=req.intention.pocket,
            destination_descriptor=req.intention.destination_descriptor,
            destination_coordinates_m=req.intention.destination_coordinates_m,
            destination_tolerance_m=req.intention.destination_tolerance_m,
        )

        # Bank shot path — forced rail count.
        if req.bank_rails and req.bank_rails > 0:
            result = compose_bank_plan(
                state,
                req.shot_id,
                intention,
                req.bank_rails,
                cue_ball_id=req.cue_ball_id,
                doctrine_line=req.doctrine_line,
            )
            return PlanResponse(plan=result)

        sauce = SauceChoice(
            english=req.sauce.english,
            stroke=req.sauce.stroke,
            force=_map_force(req.sauce.force),
            acceleration=_map_acceleration(req.sauce.acceleration),
            recipe_rationale=req.sauce.recipe_rationale,
            speed_margin=req.sauce.speed_margin,
            vertical_tips=req.sauce.vertical_tips,
            horizontal_tips=req.sauce.horizontal_tips,
        )
        result = compose_pillar_plan(
            state,
            req.shot_id,
            intention,
            sauce,
            cue_ball_id=req.cue_ball_id,
            doctrine_line=req.doctrine_line,
            optimize_for_destination=req.optimize_sauce,
            cut_offset_deg=req.cut_offset_deg,
        )
        return PlanResponse(plan=result)
    except ShotSolverError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
