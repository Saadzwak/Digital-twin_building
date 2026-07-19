"""Public M1 API bound to the real-data, memory-bounded reference protocol."""

from .reference_ingestion import (
    ARCHIVE_DATA_DIRECTORY,
    BLOCK,
    METER_A_ID,
    ReferencePreparedDataset,
    ReferenceSourcePaths,
    prepare_reference_dataset,
    resolve_reference_sources,
    split_reference_months,
    write_reference_dataset,
)


# Retain concise public names while ensuring all callers reach the implementation
# actually executed against the 505 MB source sensor file.
PreparedDataset = ReferencePreparedDataset
SourcePaths = ReferenceSourcePaths
write_prepared_dataset = write_reference_dataset

__all__ = [
    "ARCHIVE_DATA_DIRECTORY", "BLOCK", "METER_A_ID", "PreparedDataset", "SourcePaths",
    "prepare_reference_dataset", "resolve_reference_sources", "split_reference_months", "write_prepared_dataset",
]
