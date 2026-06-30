import pytest
import yaml

from nav_benchmark.synthetic.config import SequenceConfig, load_config


def test_sequence_config_from_dict_builds_heading_script():
    cfg = SequenceConfig.from_dict(
        {
            "sequence": {"name": "unit", "duration_s": 1.5},
            "flight": {
                "start_heading_deg": 45.0,
                "heading_script": [
                    {"t_s": 0.0, "heading_deg": 45.0},
                    {"t_s": 1.0, "heading_deg": 90.0},
                ],
            },
            "camera": {"width": 32, "height": 24},
        }
    )

    assert cfg.sequence.name == "unit"
    assert cfg.sequence.duration_s == 1.5
    assert [point.heading_deg for point in cfg.flight.heading_script] == [45.0, 90.0]
    assert cfg.camera.width == 32
    assert cfg.raw["sequence"]["name"] == "unit"


def test_load_config_reads_yaml(tmp_path):
    path = tmp_path / "sequence.yaml"
    path.write_text(yaml.safe_dump({"sequence": {"name": "from_yaml"}}), encoding="utf-8")

    cfg = load_config(path)

    assert cfg.sequence.name == "from_yaml"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")
