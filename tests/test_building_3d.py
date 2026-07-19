"""Real 3D footprints (IGN BD TOPO cache) — guards against a degenerate 'cube'.

The map must extrude the real emprise polygon (with setbacks), not a rectangle
synthesised from a floor area. These tests pin that the cached geometry is a real
multi-vertex polygon at a plausible urban height, that the target is present, and
that a dense urban context of neighbours accompanies it.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thermal_twin.building_3d import load_buildings, TARGET_RNB


def test_cache_present_and_sourced_from_bdtopo():
    data = load_buildings(ROOT)
    assert data is not None, "runs/geometry/wazemmes_buildings.json must be cached"
    assert data["source"] == "ign_bdtopo_wfs"
    assert data["count"] >= 50, "expected a dense Wazemmes neighbourhood"
    assert "BD TOPO" in data["attribution"]


def test_target_is_a_real_polygon_not_a_rectangle():
    data = load_buildings(ROOT)
    target = [b for b in data["buildings"] if b["is_target"]]
    assert len(target) == 1, "the target building must be identified by RNB"
    t = target[0]
    assert data["target_rnb"] == TARGET_RNB
    ring = t["rings"][0]
    # A rectangle has 5 points (closed). The real emprise has setbacks => many more.
    assert len(ring) > 8, f"expected a real polygon with setbacks, got {len(ring)} points"
    # every vertex is a [lon, lat] pair near the real Wazemmes coordinates
    for lon, lat in ring:
        assert 3.0 < lon < 3.1 and 50.6 < lat < 50.65
    assert 6.0 <= t["height"] <= 30.0, "plausible R+n height in metres"


def test_neighbours_carry_real_heights():
    data = load_buildings(ROOT)
    neighbours = [b for b in data["buildings"] if not b["is_target"]]
    assert len(neighbours) >= 50
    heights = [b["height"] for b in neighbours]
    assert all(1.0 <= h <= 60.0 for h in heights)
    # not all identical => real per-building heights, not a constant stand-in
    assert len(set(round(h) for h in heights)) > 5
