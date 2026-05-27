from __future__ import annotations


def generate_perturbations(parameters: dict, pct: float = 0.10) -> list[dict]:
    variants = []
    for key, value in parameters.items():
        if isinstance(value, (int, float)):
            variants.append({**parameters, key: value * (1 - pct)})
            variants.append({**parameters, key: value * (1 + pct)})
    return variants


def robustness_score(base_score: float, perturbed_scores: list[float]) -> float:
    if not perturbed_scores:
        return 0.0
    average_gap = sum(abs(base_score - score) for score in perturbed_scores) / len(perturbed_scores)
    return max(0.0, min(1.0, 1.0 - average_gap))
