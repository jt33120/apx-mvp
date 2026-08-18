"""The door: a fixture stand-in for core/app/rank.py, so the check can find it."""


def identity_inputs(**kw):  # noqa: ANN003, ANN201
    return RankingIdentityInputs(**kw)  # noqa: F821
