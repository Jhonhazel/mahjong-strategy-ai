from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_tile_assets_regenerate_identically_from_one_canonical_catalog(tmp_path):
    from scripts.build_tile_assets import build_assets
    build_assets(tmp_path)
    for relative in ('tiles.svg', 'phase4/catalog.mjs'):
        assert (tmp_path/relative).read_bytes() == (ROOT/'app/static'/relative).read_bytes()


def contrast(first, second):
    def luminance(color):
        channels = [int(color[index:index+2], 16)/255 for index in (1, 3, 5)]
        channels = [value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4 for value in channels]
        return sum(weight*value for weight, value in zip((.2126, .7152, .0722), channels))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light+.05)/(dark+.05)


@pytest.mark.parametrize('foreground,background', [
    ('--ink','--ivory'), ('--muted','--paper'), ('--forest','--ivory'),
    ('--paper','--forest'), ('--gold-ink','--ivory'), ('--jade','--gold'), ('--error','--ivory'),
])
def test_design_text_tokens_have_aa_normal_text_contrast(foreground, background):
    css = (ROOT/'app/static/phase3.css').read_text()
    tokens = dict(re.findall(r'(--[\w-]+):\s*(#[0-9a-f]{6})', css))
    assert contrast(tokens[foreground], tokens[background]) >= 4.5


def test_frontend_uses_local_modules_safe_dom_and_reduced_motion_rules():
    modules = [ROOT/'app/static/phase3.js', *(ROOT/'app/static/phase4').glob('*.mjs')]
    for path in modules:
        source = path.read_text()
        assert not re.search(r'\.innerHTML\s*=|insertAdjacentHTML\s*\(|\beval\s*\(|new Function\s*\(', source), path
        assert 'localStorage' not in source and 'sessionStorage' not in source, path
        assert not re.search(r"(?:import|from)\s*['\"]https?://", source), path
    css = (ROOT/'app/static/phase3.css').read_text()
    assert '@media (prefers-reduced-motion: reduce)' in css
    assert 'transition: none !important' in css and 'animation: none !important' in css


def test_scrollable_hand_never_uses_unsafe_center_alignment():
    css = (ROOT/'app/static/phase3.css').read_text()
    rules = re.findall(r'\.human-hand\s*\{([^}]+)\}', css)
    assert rules
    assert not any(re.search(r'justify-content:\s*center\s*;', rule) for rule in rules)
