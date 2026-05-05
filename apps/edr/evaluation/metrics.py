def evidence_precision(supported_claims: int, total_claims: int) -> float:
    if total_claims == 0:
        return 0.0
    return supported_claims / total_claims


def refusal_accuracy(correct_refusals: int, required_refusals: int) -> float:
    if required_refusals == 0:
        return 1.0
    return correct_refusals / required_refusals
