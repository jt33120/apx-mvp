"""The defect Story 5.9 found on a court document: the adapter hands over a claim about the
READER's bytes, computed from whether a row in its own database carried an anchor."""
from apx.core.domain.matter_record import ChainVerdictLine


class Store:
    def export(self, trail, slices):
        return [
            ChainVerdictLine(
                chain_scope=sl.chain_scope,
                label_fr=sl.label_fr,
                entries=sl.entries,
                verified=sl.verified,
                recomputable_from_this_document=sl.verifiable_in_isolation,
            )
            for sl in slices
        ]
