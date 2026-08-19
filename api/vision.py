"""Ball detection pipeline: photo → ball positions in table metres.

Pipeline
--------
1. Decode image → BGR numpy array.
2. Detect table boundary via green/blue felt edge detection → 4 corners.
   Fallback: use image bounds if detection fails.
3. Homography transform → top-down rectified image.
4. Hough circle detection on rectified image.
5. Per-circle: sample HSV histogram → classify 9-ball color → assign id.
6. Return DetectedBall list with metre coordinates and confidence.

Blue cloth note
---------------
The 2-ball (blue solid) is the hardest to isolate on a blue table.
Detections where the dominant HSV hue overlaps the cloth color are flagged
with confidence < 0.5 and needs_confirm=True.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

# Table physical dimensions (metres)
TABLE_LENGTH_M = 2.54
TABLE_WIDTH_M = 1.27

# Ball HSV colour definitions (hue 0-179, sat 0-255, val 0-255)
# Format: (hue_lo, hue_hi, sat_lo, val_lo, val_hi)
_BALL_COLORS: dict[str, tuple[int, int, int, int, int]] = {
    "cue":  (0,   10,  0,   180, 255),   # white — high val, low sat
    "1":    (20,  35,  150, 100, 255),   # yellow
    "2":    (100, 130, 120,  60, 220),   # blue
    "3":    (0,   10,  150,  50, 200),   # red (hue wraps; also check 170-179)
    "4":    (135, 155, 100,  40, 160),   # purple
    "5":    (10,  22,  180,  80, 220),   # orange
    "6":    (0,   10,  120,  30,  90),   # maroon / dark red
    "7":    (80, 100,  120,  80, 200),   # turquoise
    "8":    (0,   10,   0,    0,  50),   # black — very low val
    "9":    (20,  35,  100, 100, 255),   # bumblebee (stripe) — near yellow
}

# Confidence penalty when ball hue overlaps cloth hue
_CLOTH_HUE_LO = 95
_CLOTH_HUE_HI = 135
_CONFIDENCE_FLOOR = 0.3
_CONFIDENCE_THRESHOLD = 0.7

# Pixels per metre in the rectified image
_PIXELS_PER_METRE = 300


@dataclass
class DetectedBall:
    id: str | None
    x_m: float
    y_m: float
    color_hsv: tuple[float, float, float]
    confidence: float
    needs_confirm: bool
    radius_px: int


def detect_balls(image_bytes: bytes) -> tuple[list[DetectedBall], list[tuple[int, int]] | None, int, int]:
    """Main entry point.

    Returns
    -------
    balls
        Detected balls with metre coordinates.
    table_corners_px
        Four table corner pixel coordinates in the *original* image, or None.
    width_px, height_px
        Dimensions of the original image.
    """
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(
            "Could not decode image. iPhone HEIC photos must be converted to "
            "JPEG before upload."
        )

    # Guard against oversized inputs: Hough circle detection on a full-res
    # 12MP frame is slow and memory-heavy. Cap the longest side.
    _MAX_DIM = 2000
    h0, w0 = img.shape[:2]
    longest = max(h0, w0)
    if longest > _MAX_DIM:
        scale = _MAX_DIM / longest
        img = cv2.resize(img, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)

    h, w = img.shape[:2]
    corners = _detect_table_corners(img)
    rectified, scale_x, scale_y = _rectify(img, corners)
    balls = _find_balls(rectified, scale_x, scale_y)
    return balls, corners, w, h


def _detect_table_corners(img: np.ndarray) -> list[tuple[int, int]] | None:
    """Try to find the four rail inner corners via felt-color masking."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Felt mask: blue-green range
    mask = cv2.inRange(hsv, np.array([85, 60, 60]), np.array([140, 255, 255]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 0.1 * img.shape[0] * img.shape[1]:
        return None

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        # Fall back to bounding rect corners
        x, y, bw, bh = cv2.boundingRect(largest)
        return [(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)]

    pts = approx.reshape(4, 2).tolist()
    return [tuple(p) for p in pts]  # type: ignore[return-value]


def _order_corners(pts: list[tuple[int, int]]) -> np.ndarray:
    """Order corners: top-left, top-right, bottom-right, bottom-left."""
    pts_arr = np.array(pts, dtype="float32")
    s = pts_arr.sum(axis=1)
    diff = np.diff(pts_arr, axis=1)
    ordered = np.zeros((4, 2), dtype="float32")
    ordered[0] = pts_arr[np.argmin(s)]    # top-left
    ordered[2] = pts_arr[np.argmax(s)]    # bottom-right
    ordered[1] = pts_arr[np.argmin(diff)] # top-right
    ordered[3] = pts_arr[np.argmax(diff)] # bottom-left
    return ordered


def _rectify(
    img: np.ndarray,
    corners: list[tuple[int, int]] | None,
) -> tuple[np.ndarray, float, float]:
    """Warp perspective to a top-down rectangle.

    Returns the rectified image and pixels-per-metre scale factors.
    """
    out_w = int(TABLE_WIDTH_M * _PIXELS_PER_METRE)
    out_h = int(TABLE_LENGTH_M * _PIXELS_PER_METRE)

    if corners is None:
        rectified = cv2.resize(img, (out_w, out_h))
        return rectified, _PIXELS_PER_METRE, _PIXELS_PER_METRE

    src = _order_corners(corners)
    dst = np.array([
        [0, 0],
        [out_w - 1, 0],
        [out_w - 1, out_h - 1],
        [0, out_h - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(src, dst)
    rectified = cv2.warpPerspective(img, M, (out_w, out_h))
    return rectified, _PIXELS_PER_METRE, _PIXELS_PER_METRE


def _find_balls(
    rectified: np.ndarray,
    scale_x: float,
    scale_y: float,
) -> list[DetectedBall]:
    gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)

    # Expected ball diameter in pixels
    ball_r_px = int(0.028575 * scale_x)  # ball radius in metres × px/m
    min_r = max(6, ball_r_px - 6)
    max_r = ball_r_px + 10

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=int(ball_r_px * 2.0),
        param1=60,
        param2=22,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is None:
        return []

    circles = np.round(circles[0]).astype(int)
    hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
    h_img, w_img = rectified.shape[:2]

    balls: list[DetectedBall] = []
    assigned: set[str] = set()

    for cx, cy, r in circles:
        # Sample HSV in a disc around the circle centre
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        cv2.circle(mask, (cx, cy), max(r - 3, 3), 255, -1)
        mean_hsv = cv2.mean(hsv, mask=mask)[:3]

        ball_id, confidence = _classify_color(mean_hsv, assigned)
        if ball_id is not None:
            assigned.add(ball_id)

        # Convert pixel position to metres
        # Origin: bottom-left of rectified image
        x_m = cx / scale_x
        y_m = (h_img - cy) / scale_y

        # Clamp to table bounds
        x_m = max(0.0, min(x_m, TABLE_WIDTH_M))
        y_m = max(0.0, min(y_m, TABLE_LENGTH_M))

        balls.append(DetectedBall(
            id=ball_id,
            x_m=round(x_m, 4),
            y_m=round(y_m, 4),
            color_hsv=(round(float(mean_hsv[0]), 1),
                       round(float(mean_hsv[1]), 1),
                       round(float(mean_hsv[2]), 1)),
            confidence=round(confidence, 3),
            needs_confirm=confidence < _CONFIDENCE_THRESHOLD,
            radius_px=int(r),
        ))

    return balls


def _classify_color(
    hsv: tuple[float, float, float],
    already_assigned: set[str],
) -> tuple[str | None, float]:
    """Return (ball_id, confidence) for a sampled HSV mean."""
    h, s, v = hsv
    best_id: str | None = None
    best_score = -1.0

    for ball_id, (h_lo, h_hi, s_lo, v_lo, v_hi) in _BALL_COLORS.items():
        if ball_id in already_assigned:
            continue

        # Special case: white cue ball — very high brightness, low saturation
        if ball_id == "cue":
            score = _score_cue(s, v)
        # Special case: black 8-ball — very low value
        elif ball_id == "8":
            score = _score_black(v)
        # Red wraps around hue 0
        elif ball_id == "3":
            score = _score_red(h, s, v)
        else:
            score = _score_generic(h, s, v, h_lo, h_hi, s_lo, v_lo, v_hi)

        # Penalise if hue overlaps with cloth
        if _CLOTH_HUE_LO <= h <= _CLOTH_HUE_HI and ball_id not in ("2", "7"):
            score *= 0.4

        if score > best_score:
            best_score = score
            best_id = ball_id

    confidence = max(_CONFIDENCE_FLOOR, min(1.0, best_score))
    return (best_id if confidence > _CONFIDENCE_FLOOR else None), confidence


def _score_generic(h, s, v, h_lo, h_hi, s_lo, v_lo, v_hi) -> float:
    if not (h_lo <= h <= h_hi):
        return 0.0
    h_range = max(1, h_hi - h_lo)
    h_center = (h_lo + h_hi) / 2
    hue_score = 1.0 - abs(h - h_center) / (h_range / 2)
    sat_score = min(1.0, max(0.0, (s - s_lo) / 100))
    val_ok = 1.0 if v_lo <= v <= v_hi else 0.3
    return hue_score * sat_score * val_ok


def _score_cue(s, v) -> float:
    # White: low saturation, high brightness
    sat_score = max(0.0, 1.0 - s / 60)
    val_score = min(1.0, max(0.0, (v - 150) / 105))
    return sat_score * val_score


def _score_black(v) -> float:
    return max(0.0, 1.0 - v / 60)


def _score_red(h, s, v) -> float:
    # Red hue wraps: 0-10 or 170-179
    in_range = (0 <= h <= 10) or (170 <= h <= 179)
    if not in_range:
        return 0.0
    sat_score = min(1.0, max(0.0, (s - 120) / 135))
    val_ok = 1.0 if 50 <= v <= 200 else 0.3
    return sat_score * val_ok
