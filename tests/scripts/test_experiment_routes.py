from types import SimpleNamespace

import numpy as np

import scripts.experiment_routes as experiment_routes


def test_run_matcher_on_crop_success(monkeypatch):
    drone_img = np.zeros((8, 8, 3), dtype=np.uint8)
    ref_img = np.zeros((16, 16, 3), dtype=np.uint8)
    keypoints = [object(), object()]
    descriptors = np.ones((2, 32), dtype=np.uint8)

    monkeypatch.setattr(experiment_routes, "_preprocess_pair", lambda drone, ref, edge_mode: (drone, ref))
    monkeypatch.setattr(
        experiment_routes, "_detect_orb_features", lambda drone, ref: (keypoints, descriptors, keypoints, descriptors)
    )
    monkeypatch.setattr(experiment_routes, "match_descriptors", lambda *_args, **_kwargs: ([1, 2, 3], [1, 2, 3]))
    monkeypatch.setattr(
        experiment_routes, "estimate_homography", lambda *_args, **_kwargs: (np.eye(3), list(range(12)))
    )
    monkeypatch.setattr(experiment_routes, "_project_crop_center", lambda *_args: (42.0, -71.0))

    result = experiment_routes.run_matcher_on_crop(drone_img, ref_img, {"meta": "ok"})

    assert result == (42.0, -71.0, 3, 12, "success")


def test_run_matcher_on_crop_failure(monkeypatch):
    drone_img = np.zeros((8, 8, 3), dtype=np.uint8)
    ref_img = np.zeros((16, 16, 3), dtype=np.uint8)

    monkeypatch.setattr(experiment_routes, "_preprocess_pair", lambda drone, ref, edge_mode: (drone, ref))
    monkeypatch.setattr(experiment_routes, "_detect_orb_features", lambda drone, ref: ([], None, [], None))

    result = experiment_routes.run_matcher_on_crop(drone_img, ref_img, {"meta": "ok"})

    assert result == (0.0, 0.0, 0, 0, "failed")


def test_print_verdict_branches(capsys):
    experiment_routes._print_verdict("failed", 0, 0.0, 0.0, 0.0, 0.0)
    experiment_routes._print_verdict("success", 12, 1.0, 1.0, 1.0, 1.0)
    experiment_routes._print_verdict("low_confidence", 5, 2.0, 2.0, 1.0, 1.0)

    output = capsys.readouterr().out
    assert "Matcher failed" in output
    assert "correctly localized" in output
    assert "WRONG place" in output


def test_main_runs_each_route_waypoint(monkeypatch, capsys):
    ref_img = np.zeros((20, 20, 3), dtype=np.uint8)
    calls = []

    monkeypatch.setattr(experiment_routes, "_load_reference", lambda: (ref_img, {"meta": "ok"}))
    monkeypatch.setattr(
        experiment_routes,
        "_routes",
        lambda width, height: {"Positive": [(1, 2)], "Negative": [(3, 4)]},
    )
    monkeypatch.setattr(
        experiment_routes,
        "_run_route_waypoint",
        lambda *args: calls.append(SimpleNamespace(route=args[0], waypoint=args[1], control=args[2])),
    )

    experiment_routes.main()

    assert [(call.route, call.waypoint, call.control) for call in calls] == [
        ("Positive", 1, (1, 2)),
        ("Negative", 1, (3, 4)),
    ]
    assert "MAP MATCHING EXPERIMENT" in capsys.readouterr().out
