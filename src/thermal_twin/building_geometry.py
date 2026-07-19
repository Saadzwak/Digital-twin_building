"""Building massing extracted from the supplied vector floor plans.

The outline is the concave envelope of the drawn ink on the ground-floor plan
(sheet frame, title block and legend excluded).  It is a *volume-scale*
representation: it is honest about being the building envelope, never a
per-wall or per-facade measurement.  All six floors share this footprint (one
physical volume); each floor keeps its own drawn-content density, used only to
drive the reveal animation, never a thermal claim.

The frozen result is journaled to ``runs/geometry/building_massing.json`` so the
web app never needs PyMuPDF at request time.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

import numpy as np

GROUND_PLAN = "Edificio PLEIADES (planta baja).pdf"
FLOOR_PLANS = (
    ("baja", "Edificio PLEIADES (planta baja).pdf"),
    ("1", "Edificio PLEIADES (planta 1ª).pdf"),
    ("2", "Edificio PLEIADES (planta 2ª).pdf"),
    ("3", "Edificio PLEIADES (planta 3ª).pdf"),
    ("4", "Edificio PLEIADES (planta 4ª).pdf"),
    ("5", "Edificio PLEIADES (planta 5ª).pdf"),
)
SCALE_LABEL = "1:250"
# Exclusion of the A3 sheet frame margin, the bottom legend band and the
# top-right title block, in page fractions. Tuned once against the rendered
# overlay and frozen.
FRAME_MARGIN = 0.05
LEGEND_Y = 0.83
TITLE_X, TITLE_Y = 0.84, 0.22
CONCAVE_RATIO = 0.12


@dataclass(frozen=True)
class FloorActivity:
    level: str
    drawing_count: int
    activity: float  # normalized 0..1 drawn-content density


@dataclass(frozen=True)
class BuildingMassing:
    footprint: list[list[float]]  # normalized [x,y] page fractions, y down
    footprint_area_fraction: float
    scale_label: str
    n_floors: int
    floors: list[dict]
    provenance: str
    honesty_note: str


def _extract_footprint(pdf_path: Path) -> tuple[list[list[float]], float]:
    import fitz  # local import: only needed when (re)building the artifact
    from shapely import concave_hull, MultiPoint

    document = fitz.open(pdf_path)
    page = document[0]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), colorspace=fitz.csGRAY, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)
    height, width = image.shape
    ink = image < 128
    margin = int(FRAME_MARGIN * min(height, width))
    ink[:margin] = False
    ink[height - margin:] = False
    ink[:, :margin] = False
    ink[:, width - margin:] = False
    ys, xs = np.where(ink)
    xn, yn = xs / width, ys / height
    keep = (yn < LEGEND_Y) & ~((xn > TITLE_X) & (yn < TITLE_Y))
    xs, ys = xs[keep], ys[keep]
    index = np.linspace(0, len(xs) - 1, min(len(xs), 9000)).astype(int)
    points = MultiPoint([(float(xs[i]), float(ys[i])) for i in index])
    hull = concave_hull(points, ratio=CONCAVE_RATIO)
    polygon = hull if hull.geom_type == "Polygon" else max(hull.geoms, key=lambda g: g.area)
    polygon = polygon.simplify(2.0)
    coords = [[round(x / width, 4), round(y / height, 4)] for x, y in polygon.exterior.coords]
    document.close()
    return coords, float(polygon.area / (height * width))


def _floor_activity(root: Path) -> list[FloorActivity]:
    import fitz

    counts: list[tuple[str, int]] = []
    for level, filename in FLOOR_PLANS:
        document = fitz.open(root / filename)
        counts.append((level, len(document[0].get_drawings())))
        document.close()
    values = np.array([c for _, c in counts], dtype=float)
    lo, hi = values.min(), values.max()
    normalized = (values - lo) / (hi - lo) if hi > lo else np.ones_like(values)
    return [FloorActivity(level=level, drawing_count=count, activity=round(float(n), 4))
            for (level, count), n in zip(counts, normalized)]


def build_massing(project_root: Path | str) -> BuildingMassing:
    root = Path(project_root).resolve()
    footprint, area = _extract_footprint(root / GROUND_PLAN)
    floors = _floor_activity(root)
    return BuildingMassing(
        footprint=footprint,
        footprint_area_fraction=round(area, 4),
        scale_label=SCALE_LABEL,
        n_floors=len(floors),
        floors=[asdict(floor) for floor in floors],
        provenance=(
            "Concave hull of the vector ink from the ground-floor plan, "
            "sheet frame/title block/legend excluded; drawn-content density per floor."
        ),
        honesty_note=(
            "Volume-scale representation. Individual walls are not measured "
            "separately; the geometry is not human-validated."
        ),
    )


def write_massing(project_root: Path | str) -> Path:
    root = Path(project_root).resolve()
    massing = build_massing(root)
    directory = root / "runs" / "geometry"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "building_massing.json"
    path.write_text(json.dumps(asdict(massing), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def load_massing(project_root: Path | str) -> dict | None:
    path = Path(project_root).resolve() / "runs" / "geometry" / "building_massing.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
