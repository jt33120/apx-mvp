"""The model read from configuration beside the judge — a preference reported as a fact."""


def build(store, tenant):  # noqa: ANN001, ANN201
    return store.get_config(tenant, "model_name")
