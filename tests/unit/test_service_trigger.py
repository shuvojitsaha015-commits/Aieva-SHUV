"""When is the board worth reading again?"""

from PIL import Image

from aieva.core.service.triggers import TriggerPolicy, difference, fingerprint


def board(color: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """A picture of a board."""
    return Image.new("RGB", (320, 240), color)


def test_the_same_picture_is_not_read_twice() -> None:
    policy = TriggerPolicy(threshold=0.004, min_interval=0.0)
    assert policy.should_run(board()) is True
    assert policy.should_run(board()) is False


def test_a_new_picture_is_read() -> None:
    policy = TriggerPolicy(threshold=0.004, min_interval=0.0)
    assert policy.should_run(board((255, 255, 255))) is True
    assert policy.should_run(board((0, 0, 0))) is True


def test_the_minimum_interval_is_kept() -> None:
    policy = TriggerPolicy(threshold=0.0, min_interval=5.0)
    assert policy.should_run(board(), now=0.0) is True
    assert policy.should_run(board((0, 0, 0)), now=1.0) is False
    assert policy.should_run(board((0, 0, 0)), now=6.0) is True


def test_the_rate_limit_holds() -> None:
    policy = TriggerPolicy(threshold=0.0, min_interval=0.0, max_per_minute=3)
    for index in range(3):
        assert policy.should_run(board((index, 0, 0)), now=float(index)) is True
    assert policy.should_run(board((9, 9, 9)), now=10.0) is False


def test_remember_skips_the_picture() -> None:
    policy = TriggerPolicy(threshold=0.5, min_interval=0.0)
    policy.remember(board((0, 0, 0)))
    assert policy.should_run(board((0, 0, 0))) is False


def test_reset_forgets_everything() -> None:
    policy = TriggerPolicy(threshold=0.004, min_interval=0.0)
    assert policy.should_run(board()) is True
    policy.reset()
    assert policy.should_run(board()) is True


def test_the_difference_of_two_pictures() -> None:
    assert difference(fingerprint(board()), fingerprint(board())) == 0.0
    assert difference(fingerprint(board((0, 0, 0))), fingerprint(board((255, 255, 255)))) == 1.0
    assert difference((), (1, 2)) == 1.0
