"""Exact data-preparation protocol frozen from notebook cell 55.

This module deliberately preserves the reference notebook's choices, including
the meter identifier ``335546926``.  It is not a generic PLEIAData loader.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd


BLOCK = "A"
METER_A_ID = "335546926"
REQUIRED_SOURCE_FILES = (
    "data-sensor.csv",
    "data-cons.csv",
    "relations-sensor.csv",
    "MU62_dm.txt",
)


@dataclass(frozen=True)
class SourcePaths:
    """The four source files used by the notebook's reference branch."""

    sensor: Path
    consumption: Path
    sensor_relations: Path
    weather: Path


@dataclass(frozen=True)
class PreparedDataset:
    """Prepared hourly data and the auditable facts required to reproduce it."""

    hourly: pd.DataFrame
    source_paths: SourcePaths
    sensor_count: int
    meter_id: str
    energy_interval_seconds: float
    q_clip_lower_w: float
    q_clip_upper_w: float


def _required_present(directory: Path) -> bool:
    return all((directory / file_name).is_file() for file_name in REQUIRED_SOURCE_FILES)


def _safe_extract_reference_sources(archive: Path, destination: Path) -> Path:
    """Extract only M1 source files from the supplied Zenodo archive.

    The archive's actual layout is ``Data_Nature/data`` whereas the notebook
    expects ``Data_Nature/raw_data``.  The extraction keeps the archive layout
    intact and path resolution below documents that difference explicitly.
    """

    archive = archive.resolve()
    destination = destination.resolve()
    source_dir = destination / "Data_Nature" / "data"
    if _required_present(source_dir):
        return source_dir

    with zipfile.ZipFile(archive) as bundle:
        for file_name in REQUIRED_SOURCE_FILES:
            member_name = f"Data_Nature/data/{file_name}"
            try:
                member = bundle.getinfo(member_name)
            except KeyError as exc:
                raise FileNotFoundError(
                    f"{archive} does not contain the required member {member_name!r}."
                ) from exc
            target = (destination / member.filename).resolve()
            if destination not in target.parents:
                raise ValueError(f"Unsafe archive member rejected: {member.filename!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return source_dir


def resolve_source_paths(project_root: Path | str) -> SourcePaths:
    """Resolve or minimally extract the fixed M1 data sources.

    Resolution order is deliberately local and deterministic.  It supports the
    supplied archive without requiring a manually chosen path:

    1. ``data/raw/Data_Nature/data`` (our reproducible extraction location),
    2. ``Data_Nature/data`` or ``Data_Nature/raw_data`` at project root,
    3. minimal extraction of ``Data_Nature.zip`` to option 1.
    """

    root = Path(project_root).resolve()
    candidates = (
        root / "data" / "raw" / "Data_Nature" / "data",
        root / "Data_Nature" / "data",
        root / "Data_Nature" / "raw_data",
    )
    source_dir = next((path for path in candidates if _required_present(path)), None)
    if source_dir is None:
        archive = root / "Data_Nature.zip"
        if not archive.is_file():
            searched = ", ".join(str(path) for path in candidates)
            raise FileNotFoundError(
                "Reference source files were not found. Searched: "
                f"{searched}. Archive also absent: {archive}."
            )
        source_dir = _safe_extract_reference_sources(archive, root / "data" / "raw")

    return SourcePaths(
        sensor=source_dir / "data-sensor.csv",
        consumption=source_dir / "data-cons.csv",
        sensor_relations=source_dir / "relations-sensor.csv",
        weather=source_dir / "MU62_dm.txt",
    )


def _load_block_a_sensor_observations(source_paths: SourcePaths) -> tuple[pd.Series, int]:
    relations = pd.read_csv(source_paths.sensor_relations, sep=";")
    sensor_ids = (
        relations.loc[relations["block"].astype(str) == BLOCK, "ID"]
        .astype(str)
        .unique()
        .tolist()
    )
    selected_ids = set(sensor_ids)
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        source_paths.sensor,
        usecols=["IDdevice", "Date", "V2"],
        chunksize=1_000_000,
        sep=";",
    ):
        chunk["IDdevice"] = chunk["IDdevice"].astype(str)
        subset = chunk[chunk["IDdevice"].isin(selected_ids)]
        if not subset.empty:
            chunks.append(subset)
    if not chunks:
        raise ValueError(f"No sensor observations found for block {BLOCK!r}.")

    observations = pd.concat(chunks, ignore_index=True)
    observations["Date"] = pd.to_datetime(observations["Date"], errors="coerce", utc=True)
    observations["V2"] = pd.to_numeric(observations["V2"], errors="coerce")
    observations = observations.dropna(subset=["Date", "V2"])
    tin = observations.groupby("Date")["V2"].mean().rename("Tin").sort_index()
    return tin, len(sensor_ids)


def _load_notebook_hvac_proxy(source_paths: SourcePaths) -> tuple[pd.Series, float, float, float]:
    consumption = pd.read_csv(source_paths.consumption, sep=";")
    consumption["IDdevice"] = consumption["IDdevice"].astype(str)
    consumption["Date"] = pd.to_datetime(consumption["Date"], errors="coerce", utc=True)
    consumption["V22"] = pd.to_numeric(consumption["V22"], errors="coerce")
    consumption = consumption.dropna(subset=["Date", "V22"])

    meter = consumption.loc[consumption["IDdevice"] == METER_A_ID].copy().sort_values("Date")
    if meter.empty:
        raise ValueError(f"Meter {METER_A_ID} has no valid V22 observations.")
    energy_cumulative = meter.groupby("Date")["V22"].mean().rename("E_cum_kWh").sort_index()
    energy_interval = energy_cumulative.diff().rename("E_kWh_interval").dropna()
    interval_seconds = float(
        energy_interval.index.to_series().diff().dt.total_seconds().median()
    )
    q_hvac = (energy_interval * 3.6e6 / interval_seconds).rename("Qhvac_W_A")
    lower, upper = (float(value) for value in q_hvac.quantile([0.001, 0.999]))
    q_hvac = q_hvac.clip(lower=lower, upper=upper)
    return q_hvac, interval_seconds, lower, upper


def _load_outdoor_temperature(source_paths: SourcePaths) -> pd.Series:
    weather = pd.read_csv(source_paths.weather, sep=";", engine="python")
    weather.columns = [column.strip() for column in weather.columns]
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


def prepare_reference_dataset(project_root: Path | str) -> PreparedDataset:
    """Build the notebook-equivalent hourly dataframe for the fixed reference.

    Crucially, this retains the notebook's cross-period interpolation of Tout
    and Q before month splitting, does not interpolate Tin, and does not create
    an artificial complete hourly calendar.
    """

    source_paths = resolve_source_paths(project_root)
    tin, sensor_count = _load_block_a_sensor_observations(source_paths)
    q_hvac, interval_seconds, lower, upper = _load_notebook_hvac_proxy(source_paths)
    tout = _load_outdoor_temperature(source_paths)

    ten_minute = pd.concat([tin, tout, q_hvac], axis=1).sort_index()
    ten_minute["Tout"] = ten_minute["Tout"].interpolate("time")
    ten_minute["Qhvac_W_A"] = ten_minute["Qhvac_W_A"].interpolate("time")
    ten_minute = ten_minute.dropna(subset=["Tin"])
    hourly = pd.DataFrame(
        {
            "Tin": ten_minute["Tin"].resample("1h").mean(),
            "Tout": ten_minute["Tout"].resample("1h").mean(),
            "Qhvac_W_A": ten_minute["Qhvac_W_A"].resample("1h").mean(),
        }
    ).dropna()
    hourly.index.name = "Date"

    return PreparedDataset(
        hourly=hourly,
        source_paths=source_paths,
        sensor_count=sensor_count,
        meter_id=METER_A_ID,
        energy_interval_seconds=interval_seconds,
        q_clip_lower_w=lower,
        q_clip_upper_w=upper,
    )


def split_reference_months(hourly: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Apply the immutable Jan--Sep / Oct--Nov / Dec UTC month split."""

    ordered = hourly.dropna(subset=["Tin", "Tout", "Qhvac_W_A"]).sort_index().copy()
    return {
        "train": ordered[ordered.index.month.isin(range(1, 10))].copy(),
        "validation": ordered[ordered.index.month.isin([10, 11])].copy(),
        "test": ordered[ordered.index.month == 12].copy(),
    }


def write_prepared_dataset(dataset: PreparedDataset, project_root: Path | str) -> tuple[Path, Path]:
    """Persist the small, auditable M1 product and an execution manifest."""

    root = Path(project_root).resolve()
    processed_dir = root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    data_path = processed_dir / "hourly_reference.csv"
    manifest_path = processed_dir / "hourly_reference_manifest.json"
    dataset.hourly.to_csv(data_path, date_format="%Y-%m-%dT%H:%M:%S%z")
    splits = split_reference_months(dataset.hourly)
    manifest = {
        "protocol": "notebook_cell_55_reference",
        "source_data_directory": str(dataset.source_paths.sensor.parent.relative_to(root)),
        "meter_id": dataset.meter_id,
        "sensor_count": dataset.sensor_count,
        "energy_interval_seconds": dataset.energy_interval_seconds,
        "q_clip_lower_w": dataset.q_clip_lower_w,
        "q_clip_upper_w": dataset.q_clip_upper_w,
        "hourly_rows": int(len(dataset.hourly)),
        "range_utc": [str(dataset.hourly.index.min()), str(dataset.hourly.index.max())],
        "split_rows": {name: int(len(frame)) for name, frame in splits.items()},
        "residual_convention": "Tin_measured - Tin_estimated",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data_path, manifest_path
