from __future__ import annotations

SOURCE_GROUNDED_CONTRACT_VERSION = "source-grounded-v2"
STRUCTURED_HANDOFF_KEYS = (
    "answerSections",
    "citationMap",
    "passages",
    "selectedEvidence",
    "claimCards",
    "candidateClaimCards",
    "citedClaimCards",
    "passageWindows",
    "answerPlan",
    "coverageReport",
)


def engine_contract_payload(*, engine_name: str) -> dict[str, object]:
    return {
        "name": engine_name,
        "contractVersion": SOURCE_GROUNDED_CONTRACT_VERSION,
        "handoffKeys": list(STRUCTURED_HANDOFF_KEYS),
    }
