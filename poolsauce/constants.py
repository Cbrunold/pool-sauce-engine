"""Physical constants for Pool Sauce. SI units throughout."""
from __future__ import annotations

# Ball — 2-1/4 inch pool ball.
BALL_RADIUS_M: float = 0.028575
BALL_MASS_KG: float = 0.170

# 9-foot table playing surface (inside cushions).
TABLE_9FT_LENGTH_M: float = 2.54
TABLE_9FT_WIDTH_M: float = 1.27

# Worsted tournament cloth, typical values.
CLOTH_SLIDING_FRICTION: float = 0.2
CLOTH_ROLLING_FRICTION: float = 0.01
CLOTH_SPINNING_FRICTION: float = 0.044

# Cushion — Marlow-lite rebound model.
#
# CUSHION_EFFICIENCY is the normal-velocity restitution (magnitude kept after
# the bounce). CUSHION_TANGENTIAL_* drive a pace-dependent tangential retention:
# high-pace banks shorten, low-pace widen. CUSHION_SIDE_ENGLISH_* govern how
# vertical-axis spin (side english) couples into tangential rebound velocity —
# running english widens, reverse shortens — and how much of that spin is lost
# to rail friction in the process.
CUSHION_EFFICIENCY: float = 0.75
CUSHION_TANGENTIAL_RETENTION: float = 0.90
CUSHION_TANGENTIAL_PACE_FALLOFF: float = 0.15
CUSHION_TANGENTIAL_RETENTION_MIN: float = 0.50
CUSHION_SIDE_ENGLISH_COUPLING: float = 0.25
CUSHION_SIDE_ENGLISH_LOSS: float = 0.30

# Ball-to-ball collision.
#
# BALL_BALL_RESTITUTION is the coefficient of restitution along the line of
# centers (~0.92 for phenolic balls under tournament conditions).
# BALL_BALL_FRICTION is the sliding friction coefficient between ball surfaces
# at contact; it drives both cut-induced and spin-induced throw. Typical
# published values sit around 0.06 for clean polished balls.
BALL_BALL_RESTITUTION: float = 0.92
BALL_BALL_FRICTION: float = 0.06
