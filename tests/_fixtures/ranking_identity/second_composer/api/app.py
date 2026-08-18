"""A second composer, with its own literals — the shape the check forbids."""


def build():  # noqa: ANN201
    return RankingIdentityInputs(  # noqa: F821
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        temperature=0.0, sampling={"top_p": 1.0})
