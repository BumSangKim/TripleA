from api.optimization.candidate_generator import generate_initial_candidates


def test_candidate_generator_is_deterministic_and_small():
    first = generate_initial_candidates(limit=3)
    second = generate_initial_candidates(limit=3)
    assert first == second
    assert len(first) == 3
