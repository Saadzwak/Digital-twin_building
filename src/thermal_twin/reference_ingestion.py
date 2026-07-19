"""Memory-bounded implementation of the frozen M1 preparation protocol.

The source notebook builds a list of selected sensor chunks and concatenates it
before aggregation.  The supplied raw file is large enough that this is not
safe under the project runtime memory limit.  This implementation preserves
the same arithmetic definition (mean V2 over every exact timestamp) by keeping
only per-timestamp sums and counts while streaming chunks.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import pandas as pd


BLOCK = "A"
METER_A_ID = "335546926"
ARCHIVE_DATA_DIRECTORY = "Data_Nature/data"
SOURCE_FILES = (
    "data-sensor.csv",
    "data-cons.csv",
    "relations-sensor.csv",
    "MU62_dm.txt",
)
EXPECTED_ARCHIVE_SHA256 = "6296cf25af1df0f5c416d1c4e6c31c979a9967e16051cf353c73df64a8f36416"


@dataclass(frozen=True)
class ReferenceSourcePaths:
    root: Path
    sensor: Path
    consumption: Path
    sensor_relations: Path
    weather: Path
    archive_sha256: str | None


@dataclass(frozen=True)
class ReferencePreparedDataset:
    hourly: pd.DataFrame
    source_paths: ReferenceSourcePaths
    sensor_count: int
    selected_sensor_observations: int
    unique_tin_timestamps: int
    meter_id: str
    energy_interval_seconds: float
    q_clip_lower_w: float
    q_clip_upper_w: float


def _has_all_sources(directory: Path) -> bool:
    return all((directory / name).is_file() for name in SOURCE_FILES)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_if_needed(archive: Path, target_root: Path) -> Path:
    """Extract only immutable M1 sources, keeping the archive's real layout."""

    source_root = target_root / ARCHIVE_DATA_DIRECTORY
    if _has_all_sources(source_root):
        return source_root
    target_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zip_file:
        for name in SOURCE_FILES:
            member_name = f"{ARCHIVE_DATA_DIRECTORY}/{name}"
            member = zip_file.getinfo(member_name)
            output_path = (target_root / member.filename).resolve()
            if target_root.resolve() not in output_path.parents:
                raise ValueError(f"Archive member escapes extraction root: {member.filename}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as source, output_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    return source_root


def resolve_reference_sources(project_root: Path | str) -> ReferenceSourcePaths:
    """Resolve actual supplied PLEIAData sources with no pre-aggregated fallback."""

    project = Path(project_root).resolve()
    candidate_roots = (
        project / "data" / "raw" / ARCHIVE_DATA_DIRECTORY,
        project / ARCHIVE_DATA_DIRECTORY,
        project / "Data_Nature" / "raw_data",
    )
    source_root = next((path for path in candidate_roots if _has_all_sources(path)), None)
    archive = project / "Data_Nature.zip"
    digest: str | None = None
    if archive.is_file():
        digest = _sha256(archive)
    if source_root is None:
        if not archive.is_file():
            raise FileNotFoundError(
                "Neither explicit raw sources nor Data_Nature.zip were found under "
                f"{project}."
            )
        source_root = _extract_if_needed(archive, project / "data" / "raw")
    return ReferenceSourcePaths(
        root=source_root,
        sensor=source_root / "data-sensor.csv",
        consumption=source_root / "data-cons.csv",
        sensor_relations=source_root / "relations-sensor.csv",
        weather=source_root / "MU62_dm.txt",
        archive_sha256=digest,
    )


def _load_tin(paths: ReferenceSourcePaths) -> tuple[pd.Series, int, int]:
    relations = pd.read_csv(paths.sensor_relations, sep=";")
    sensor_ids = (
        relations.loc[relations["block"].astype(str) == BLOCK, "ID"]
        .astype(str)
        .unique()
        .tolist()
    )
    selected = set(sensor_ids)
    aggregate: pd.DataFrame | None = None
    selected_rows = 0
    for chunk in pd.read_csv(
        paths.sensor,
        usecols=["IDdevice", "Date", "V2"],
        chunksize=1_000_000,
        sep=";",
    ):
        chunk["IDdevice"] = chunk["IDdevice"].astype(str)
        part = chunk.loc[chunk["IDdevice"].isin(selected), ["Date", "V2"]].copy()
        selected_rows += len(part)
        if part.empty:
            continue
        part["Date"] = pd.to_datetime(part["Date"], errors="coerce", utc=True)
        part["V2"] = pd.to_numeric(part["V2"], errors="coerce")
        part = part.dropna(subset=["Date", "V2"])
        stats = part.groupby("Date")["V2"].agg(["sum", "count"])
        aggregate = stats if aggregate is None else aggregate.add(stats, fill_value=0.0)
    if aggregate is None:
        raise ValueError(f"No valid V2 readings were found for block {BLOCK}.")
    tin = (aggregate["sum"] / aggregate["count"]).rename("Tin").sort_index()
    return tin, len(sensor_ids), selected_rows


def _load_q_hvac(paths: ReferenceSourcePaths) -> tuple[pd.Series, float, float, float]:
    consumption = pd.read_csv(paths.consumption, sep=";")
    consumption["IDdevice"] = consumption["IDdevice"].astype(str)
    consumption["Date"] = pd.to_datetime(consumption["Date"], errors="coerce", utc=True)
    consumption["V22"] = pd.to_numeric(consumption["V22"], errors="coerce")
    consumption = consumption.dropna(subset=["Date", "V22"])
    meter = consumption.loc[consumption["IDdevice"] == METER_A_ID].copy().sort_values("Date")
    energy_cumulative = meter.groupby("Date")["V22"].mean().rename("E_cum_kWh").sort_index()
    energy_interval = energy_cumulative.diff().rename("E_kWh_interval").dropna()
    interval_seconds = float(energy_interval.index.to_series().diff().dt.total_seconds().median())
    q_hvac = (energy_interval * 3.6e6 / interval_seconds).rename("Qhvac_W_A")
    q_lower, q_upper = (float(value) for value in q_hvac.quantile([0.001, 0.999]))
    return q_hvac.clip(lower=q_lower, upper=q_upper), interval_seconds, q_lower, q_upper


def _load_tout(paths: ReferenceSourcePaths) -> pd.Series:
    weather = pd.read_csv(paths.weather, sep=";", engine="python")
    weather.columns = [name.strip() for name in weather.columns]
    weather["fecha"] = weather["fecha"].astype(str).str.strip()
    weather["hora"] = weather["hora"].astype(str).str.strip()
    weather["Date"] = pd.to_datetime(
        weather["fecha"] + " " + weather["hora"],
        format="%d/%m/%y %H:%M:%S",
        errors="coerce",
        utc=True,
    )
    weather = weather.dropna(subset=["Date"]).set_index("Date").sort_index()
    weather["tmed"] = pd.to_numeric(weather["tmed"], errors="coerce")
    return weather["tmed"].dropna().rename("Tout")


def prepare_reference_dataset(project_root: Path | str) -> ReferencePreparedDataset:
    """Reproduce M1 with the fixed notebook transformations and UTC calendar."""

    paths = resolve_reference_sources(project_root)
    tin, sensor_count, selected_rows = _load_tin(paths)
    q_hvac, interval_seconds, q_lower, q_upper = _load_q_hvac(paths)
    tout = _load_tout(paths)
    merged = pd.concat([tin, tout, q_hvac], axis=1).sort_index()
    merged["Tout"] = merged["Tout"].interpolate("time")
    merged["Qhvac_W_A"] = merged["Qhvac_W_A"].interpolate("time")
    merged = merged.dropna(subset=["Tin"])
    hourly = pd.DataFrame(
        {
            "Tin": merged["Tin"].resample("1h").mean(),
            "Tout": merged["Tout"].resample("1h").mean(),
            "Qhvac_W_A": merged["Qhvac_W_A"].resample("1h").mean(),
        }
    ).dropna()
    hourly.index.name = "Date"
    return ReferencePreparedDataset(
        hourly=hourly,
        source_paths=paths,
        sensor_count=sensor_count,
        selected_sensor_observations=selected_rows,
        unique_tin_timestamps=len(tin),
        meter_id=METER_A_ID,
        energy_interval_seconds=interval_seconds,
        q_clip_lower_w=q_lower,
        q_clip_upper_w=q_upper,
    )


def split_reference_months(hourly: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The immutable month split of notebook cell 55."""

    data = hourly.dropna(subset=["Tin", "Tout", "Qhvac_W_A"]).sort_index().copy()
    return {
        "train": data[data.index.month.isin(range(1, 10))].copy(),
        "validation": data[data.index.month.isin([10, 11])].copy(),
        "test": data[data.index.month == 12].copy(),
    }


def write_reference_dataset(dataset: ReferencePreparedDataset, project_root: Path | str) -> tuple[Path, Path]:
    """Write the 8,604-row data product plus a provenance manifest."""

    root = Path(project_root).resolve()
    output = root / "data" / "processed"
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "hourly_reference.csv"
    manifest_path = output / "hourly_reference_manifest.json"
    dataset.hourly.to_csv(csv_path, date_format="%Y-%m-%dT%H:%M:%S%z")
    splits = split_reference_months(dataset.hourly)
    manifest = {
        "protocol": "notebook_cell_55_reference",
        "source_layout": ARCHIVE_DATA_DIRECTORY,
        "resolved_source_directory": str(dataset.source_paths.root.relative_to(root)),
        "archive_sha256": dataset.source_paths.archive_sha256,
        "known_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "block": BLOCK,
        "meter_id": dataset.meter_id,
        "sensor_count": dataset.sensor_count,
        "selected_sensor_observations": dataset.selected_sensor_observations,
        "unique_tin_timestamps": dataset.unique_tin_timestamps,
        "energy_interval_seconds": dataset.energy_interval_seconds,
        "q_clip_lower_w": dataset.q_clip_lower_w,
        "q_clip_upper_w": dataset.q_clip_upper_w,
        "hourly_rows": len(dataset.hourly),
        "range_utc": [str(dataset.hourly.index.min()), str(dataset.hourly.index.max())],
        "split_rows": {name: len(part) for name, part in splits.items()},
        "residual_convention": "Tin_measured - Tin_estimated",
        "pandas_frequency_adaptation": "1h replaces notebook literal 1H; pandas 3 rejects uppercase H and semantics are identical.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return csv_path, manifest_path
