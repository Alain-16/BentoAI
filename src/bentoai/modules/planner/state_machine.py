from bentoai.modules.planner.models import MissionStatus


ALLOWED_TRANSITIONS: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.DRAFT: frozenset({MissionStatus.PLANNING}),
    MissionStatus.PLANNING: frozenset({MissionStatus.SEARCHING}),
    MissionStatus.SEARCHING: frozenset({MissionStatus.EVALUATING}),
    MissionStatus.EVALUATING: frozenset({MissionStatus.REVIEW}),
    # The only state with a real choice: the customer either changes their mind
    # and we search again, or they accept and we move towards buying.
    MissionStatus.REVIEW: frozenset(
        {MissionStatus.SEARCHING, MissionStatus.BASKET_READY}
    ),
    MissionStatus.BASKET_READY: frozenset({MissionStatus.CHECKOUT_PENDING}),
    MissionStatus.CHECKOUT_PENDING: frozenset({MissionStatus.PURCHASED}),
    MissionStatus.PURCHASED: frozenset({MissionStatus.TRACKING}),
    MissionStatus.TRACKING: frozenset({MissionStatus.COMPLETE}),
    MissionStatus.COMPLETE: frozenset(),
}


class InvalidTransition(Exception):

    def __init__(self, current: MissionStatus, target: MissionStatus):

        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        allowed_text = ". ".join(sorted(s.values for s in allowed)) or "nothing"

        super().__init__(
            f"A mission in {current.value} cannot move to {target.value}. "
            f"from {current.value} it may only move to: {allowed_text}."
        )
        self.current = current
        self.target = target


def can_transition(current:MissionStatus, target:MissionStatus) -> bool:

    return target in ALLOWED_TRANSITIONS.get(current, frozenset())

def assert_can_transition(current:MissionStatus, target:MissionStatus) -> bool:

    if not can_transition(current,target):
        raise InvalidTransition(current, target)

