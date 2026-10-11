"""Why an editor's decision was not applied. Every message is safe to show."""


class UnknownItemError(LookupError):
    """No such match, or no such item of the partner on its feed this run."""


class DecisionError(ValueError):
    """A decision that cannot be applied now."""


class NotAwaitingError(DecisionError):
    def __init__(self) -> None:
        super().__init__("this item is not awaiting a decision")


class ReplayedSinceError(DecisionError):
    def __init__(self) -> None:
        super().__init__("the matchday has been replayed since; reload to see it")


class FullTimeError(DecisionError):
    def __init__(self) -> None:
        super().__init__("the match has reached full time; held items stay off air")


class CorrectedSinceError(DecisionError):
    def __init__(self) -> None:
        super().__init__("a correction has since changed this item's facts; it stays off air")


class NoRoomOnAirError(DecisionError):
    """Transient: the partner's graphics are full this minute."""

    def __init__(self) -> None:
        super().__init__("no room on air this minute; try again shortly")
