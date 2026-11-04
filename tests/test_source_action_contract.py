"""Independent conformance check against the audited public source methods."""
import ast
from pathlib import Path

import pytest


@pytest.mark.dataset
def test_all_action_ids_conform_to_actual_published_feature_agent():
    from app.domain.actions import decode_action
    from app.domain.tiles import TILE_LIST
    source = Path(__file__).resolve().parents[1] / "datasets/references/feature.py"
    if not source.exists():
        pytest.skip("Published encoder reference not downloaded")
    module = ast.parse(source.read_text())
    definition = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "FeatureAgent")
    # Execute only inspected constants and pure action codecs; no imports,
    # native scoring, network calls, model weights, or historical error handling.
    definition.bases = []
    definition.body = [n for n in definition.body if isinstance(n, ast.Assign) or isinstance(n, ast.FunctionDef) and n.name in ("response2action", "action2response")]
    scope = {}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), scope)
    reference = scope["FeatureAgent"]()
    assert tuple(reference.TILE_LIST) == TILE_LIST
    for aid in range(235):
        action = decode_action(aid)
        response = action.action_type
        if action.action_type == "Chi":
            response += f" {action.tile} {action.chi_mid_tile}"
        elif action.tile is not None:
            response += f" {action.tile}"
        assert reference.response2action(response) == aid
