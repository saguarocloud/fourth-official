"""The match engine: a seeded possession-chain simulation emitting contract-valid match events.

The match advances one *phase* at a time. The player on the ball may be pressed and may be fouled
(a foul in the box is a penalty); then they pass, carry, cross or shoot, and the outcome depends on
distance, pressure and team style. Dead balls (throw-ins, goal kicks, corners, free kicks,
kick-offs) are where substitutions happen. Every transition is a pure function of a frozen
`MatchState` and a seeded random generator, so a setup always produces exactly the same match.

A storyline (see `storylines`) lays scripted moments over the match: style shifts, goals on cue,
VAR overturns, red cards, and the corrections issued after them.
"""

from fourth_official_simulator.engine.match import SimulatedMatch, play, simulate
from fourth_official_simulator.engine.state import MatchSetup, TeamSetup

__all__ = ["MatchSetup", "SimulatedMatch", "TeamSetup", "play", "simulate"]
