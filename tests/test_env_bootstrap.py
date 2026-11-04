import sys


def test_supported_python_and_real_library_calculations():
    from scripts.check_env import verify_environment

    assert (3, 11) <= sys.version_info[:2] < (3, 13)
    report = verify_environment()
    assert report["pymahjonggb_ok"] is True
    assert report["sample_shanten"] == 0
    assert report["sample_nine_gates_fan"] == 92
    assert report["dependencies"]["PyMahjongGB"] == "1.4.0"
