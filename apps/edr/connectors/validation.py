"""Validate connector responses against the EvidenceObject schema."""

from typing import Any

from apps.edr.schemas.evidence import EvidenceObject


def validate_evidence_payload(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Validate a connector response payload against the EvidenceObject schema.

    Expected payload format::

        {"evidence": [EvidenceObject, ...]}

    Returns a list of validated ``EvidenceObject`` instances.

    Raises:
        ValueError: if the payload is not a dict, or ``evidence`` is missing
            or not a list.
        pydantic.ValidationError: if any item in the evidence list fails
            schema validation.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected dict payload, got {type(payload).__name__}"
        )

    raw_evidence = payload.get("evidence", [])
    if not isinstance(raw_evidence, list):
        raise ValueError(
            f"Expected 'evidence' to be a list, got {type(raw_evidence).__name__}"
        )

    return [EvidenceObject.model_validate(item) for item in raw_evidence]
