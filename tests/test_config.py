import dataclasses
from pathlib import Path

from canvas_todoist.config import Config, load_config

ROOT = Path(__file__).parent.parent


def test_example_config_lists_every_setting_with_its_default():
    example = ROOT / "config.example.yaml"

    assert load_config(example) == Config()
    for setting in dataclasses.fields(Config):
        assert f"\n{setting.name}:" in example.read_text(encoding="utf-8")


def test_example_env_lists_both_secrets():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert {line.split("=")[0] for line in lines if "=" in line} == {"CANVAS_CALENDAR_FEED_URL", "TODOIST_TOKEN"}
