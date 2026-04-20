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

# Cushion — fraction of kinetic energy retained on rail contact.
CUSHION_EFFICIENCY: float = 0.75

# Ball-to-ball coefficient of restitution.
BALL_BALL_RESTITUTION: float = 0.92
