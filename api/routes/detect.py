"""POST /api/detect — photo → ball positions."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.models import DetectedBall, DetectResponse
from api.vision import detect_balls

router = APIRouter()


@router.post("/detect", response_model=DetectResponse)
async def detect(image: UploadFile = File(...)) -> DetectResponse:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    data = await image.read()
    if len(data) > 20 * 1024 * 1024:  # 20 MB cap
        raise HTTPException(status_code=413, detail="Image too large (max 20 MB).")

    try:
        balls, corners, w, h = detect_balls(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DetectResponse(
        balls=[
            DetectedBall(
                id=b.id,
                x_m=b.x_m,
                y_m=b.y_m,
                color_hsv=b.color_hsv,
                confidence=b.confidence,
                needs_confirm=b.needs_confirm,
                radius_px=b.radius_px,
            )
            for b in balls
        ],
        table_corners_px=corners,
        width_px=w,
        height_px=h,
    )
