from app.scoring import compute_score


def test_worked_example():
    # mean 56.25, par 3 over 4 films -> 42, minus 1 strike = 37
    assert compute_score([20, 55, 80, 70], 3, 1) == 37


def test_shorter_than_par_gets_no_bonus():
    assert compute_score([50, 50], 3, 0) == 50


def test_never_negative():
    assert compute_score([0, 0, 0], 3, 3) == 0
