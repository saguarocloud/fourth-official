"""Detection thresholds, calibrated on simulated matches (see docs/moments.md)."""

# A shot that did not go in is a big chance from this expected-goals value up.
BIG_CHANCE_XG = 0.35

# Pressing shifts compare the last five minutes with the fifteen before them.
PRESS_CURRENT_WINDOW = "5m"
PRESS_BASELINE_WINDOW = "15m"
PRESS_BASELINE_LAG_MINUTES = 5
# Collapse: the current rate falls to this share of the baseline or less. Surge: it rises to this
# multiple or more.
PRESS_COLLAPSE_RATIO = 0.4
PRESS_SURGE_RATIO = 2.5
# Below this many pressures per opponent touch there is no press to speak of.
PRESS_FLOOR = 0.15
# A shift must hold at this many consecutive minute checks before it is a moment.
PERSIST_CHECKS = 3

# Shift rules start once a full baseline exists: the baseline window plus its lag.
FIRST_CHECK_MINUTE = 20
# The same kind of shift for the same club is not reported again within this many minutes.
COOLDOWN_MINUTES = 15
