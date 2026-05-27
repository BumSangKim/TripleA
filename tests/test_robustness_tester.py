from api.optimization.robustness_tester import generate_perturbations, robustness_score


def test_robustness_perturbations_and_score():
    variants = generate_perturbations({"a": 1.0, "b": "x"})
    assert len(variants) == 2
    assert robustness_score(.8, [.79, .81]) > robustness_score(.8, [.1, .2])
