"""Bounded local datasets for tables and existing single-cell results."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import uuid4

import anndata as ad
import h5py
import numpy as np
import pandas as pd
from scipy import sparse
from Bio import SeqIO


MAX_TABLE_BYTES = 5 * 1024 * 1024
MAX_H5AD_BYTES = 200 * 1024 * 1024
MAX_PROJECT_BYTES = 220 * 1024 * 1024
MAX_CELLS = 500_000
MAX_GENES = 100_000
MAX_OMICS_BYTES = 50 * 1024 * 1024
MAX_SEQUENCE_LENGTH = 5_000_000
MAX_SESSION_DATASETS = 8
MAX_SESSION_DATASET_BYTES = 384 * 1024 * 1024


@dataclass(frozen=True)
class DatasetRecord:
    kind: str
    filename: str
    payload: bytes
    digest: str
    dataframe: pd.DataFrame | None = None
    adata: ad.AnnData | None = None
    manifest: dict[str, object] | None = None
    sequence_record: object | None = None


_datasets: dict[str, DatasetRecord] = {}
_dataset_lock = RLock()


class DatasetCapacityError(ValueError):
    """A declared dataset exceeds the interactive memory budget."""


def _preflight_h5ad(path: str, payload_bytes: int) -> None:
    size = payload_bytes
    def inspect(_name: str, item: object) -> None:
        nonlocal size
        if isinstance(item, h5py.Dataset):
            size += int(item.size) * item.dtype.itemsize
            if size > MAX_SESSION_DATASET_BYTES:
                raise DatasetCapacityError("H5AD 解压后的数组超过本机会话内存上限（384 MB）；请筛选或分批导入。")
    with h5py.File(path, "r") as source:
        source.visititems(inspect)


def _matrix_bytes(matrix: object) -> int:
    if sparse.issparse(matrix):
        return int(matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes)
    return int(getattr(matrix, "nbytes", 0))


def _record_bytes(record: DatasetRecord) -> int:
    """Estimate retained payload and parsed arrays before accepting another dataset."""
    size = len(record.payload)
    if record.dataframe is not None:
        size += int(record.dataframe.memory_usage(index=True, deep=True).sum())
    if record.adata is not None:
        value = record.adata
        size += _matrix_bytes(value.X)
        size += sum(_matrix_bytes(layer) for layer in value.layers.values())
        if value.raw is not None:
            size += _matrix_bytes(value.raw.X)
        size += int(value.obs.memory_usage(index=True, deep=True).sum())
        size += int(value.var.memory_usage(index=True, deep=True).sum())
        size += sum(_matrix_bytes(points) for points in value.obsm.values())
    return size


def store_dataframe(dataframe: pd.DataFrame, filename: str = "generated.csv", payload: bytes | None = None) -> str:
    raw = payload if payload is not None else dataframe.to_csv(index=False).encode("utf-8")
    return store_record(DatasetRecord("table", filename, raw, sha256(raw).hexdigest(), dataframe=dataframe))


def store_record(record: DatasetRecord) -> str:
    size = _record_bytes(record)
    if size > MAX_SESSION_DATASET_BYTES:
        raise ValueError("数据集解压后超过本机会话内存上限（384 MB）；请筛选或分批导入。")
    dataset_id = f"local-{uuid4().hex}"
    with _dataset_lock:
        while _datasets and (len(_datasets) >= MAX_SESSION_DATASETS or sum(_record_bytes(item) for item in _datasets.values()) + size > MAX_SESSION_DATASET_BYTES):
            del _datasets[next(iter(_datasets))]
        _datasets[dataset_id] = record
    return dataset_id


def get_record(dataset_id: str) -> DatasetRecord:
    with _dataset_lock:
        return _datasets[dataset_id]


def get_dataframe(dataset_id: str) -> pd.DataFrame:
    record = get_record(dataset_id)
    if record.dataframe is None:
        raise ValueError("该数据集不是表格数据。")
    return record.dataframe


def get_anndata(dataset_id: str) -> ad.AnnData:
    record = get_record(dataset_id)
    if record.adata is None:
        raise ValueError("该数据集不是单细胞 .h5ad 数据。")
    return record.adata


def parse_upload(filename: str, payload: bytes) -> pd.DataFrame:
    record = parse_dataset(filename, payload)
    if record.dataframe is None:
        raise ValueError("该文件不是表格数据。")
    return record.dataframe


def parse_dataset(filename: str, payload: bytes) -> DatasetRecord:
    """Parse a reviewed local format with explicit file and matrix limits."""
    if not payload:
        raise ValueError("文件为空。")
    lower_filename = filename.lower()
    suffix = Path(filename).suffix.lower()
    if suffix in {".csv", ".xlsx"}:
        if len(payload) > MAX_TABLE_BYTES:
            raise ValueError("表格文件超过 5 MB 限制。")
        try:
            frame = pd.read_csv(StringIO(payload.decode("utf-8-sig"))) if suffix == ".csv" else pd.read_excel(BytesIO(payload), engine="openpyxl")
        except (UnicodeDecodeError, ValueError, OSError) as error:
            raise ValueError("无法读取文件；请使用 UTF-8 CSV 或有效的 XLSX 文件。") from error
        return DatasetRecord("table", Path(filename).name, payload, sha256(payload).hexdigest(), dataframe=frame)
    if suffix in {".gb", ".gbk", ".genbank"}:
        if len(payload) > MAX_OMICS_BYTES:
            raise ValueError("GenBank 文件超过 50 MB 限制。")
        try:
            record = SeqIO.read(StringIO(payload.decode("utf-8")), "genbank")
        except Exception as error:
            raise ValueError("无法读取 GenBank 文件；请确认文件包含一个有效序列记录。") from error
        if not record.seq or len(record.seq) > MAX_SEQUENCE_LENGTH:
            raise ValueError(f"序列长度必须在 1 到 {MAX_SEQUENCE_LENGTH:,} bp 之间。")
        return DatasetRecord("dna", Path(filename).name, payload, sha256(payload).hexdigest(), sequence_record=record)
    if suffix in {".bed", ".bedgraph", ".gff", ".gff3", ".gtf"} or lower_filename.endswith(".chrom.sizes"):
        if len(payload) > MAX_OMICS_BYTES:
            raise ValueError("基因组轨道文件超过 50 MB 限制。")
        return _parse_genome_track(filename, payload)
    if suffix == ".json":
        if len(payload) > MAX_OMICS_BYTES:
            raise ValueError("组学 manifest 超过 50 MB 限制。")
        try:
            manifest = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("无法读取组学 JSON manifest。") from error
        if not isinstance(manifest, dict) or manifest.get("kind") not in {"circos", "genome_tracks"}:
            raise ValueError("JSON manifest 的 kind 必须是 circos 或 genome_tracks。")
        return DatasetRecord("omics_manifest", Path(filename).name, payload, sha256(payload).hexdigest(), manifest=manifest)
    if suffix != ".h5ad":
        raise ValueError("仅支持 CSV、XLSX、H5AD、GenBank、BED/GFF3 或组学 JSON manifest。")
    if len(payload) > MAX_H5AD_BYTES:
        raise ValueError("H5AD 文件超过 200 MB 限制。")
    temporary_name = ""
    try:
        with NamedTemporaryFile(suffix=".h5ad", delete=False) as handle:
            handle.write(payload)
            temporary_name = handle.name
        _preflight_h5ad(temporary_name, len(payload))
        adata = ad.read_h5ad(temporary_name)
    except DatasetCapacityError:
        raise
    except Exception as error:
        raise ValueError("无法读取 H5AD；请确认文件完整且符合 AnnData 格式。") from error
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    if adata.n_obs == 0 or adata.n_vars == 0:
        raise ValueError("H5AD 不包含可用的细胞或基因。")
    if adata.n_obs > MAX_CELLS:
        raise ValueError(f"细胞数超过 {MAX_CELLS:,} 的本阶段上限。")
    if adata.n_vars > MAX_GENES:
        raise ValueError(f"基因数超过 {MAX_GENES:,} 的本阶段上限。")
    return DatasetRecord("single_cell", Path(filename).name, payload, sha256(payload).hexdigest(), adata=adata)


def dataset_summary(dataset_id: str, value: DatasetRecord | pd.DataFrame, source: str) -> dict[str, object]:
    """Create bounded preview metadata without returning a local path."""
    record = DatasetRecord("table", "generated.csv", b"", "0" * 64, dataframe=value) if isinstance(value, pd.DataFrame) else value
    if record.dataframe is not None:
        dataframe = record.dataframe
        return {
            "dataset_id": dataset_id, "kind": "genome_tracks" if record.kind == "genome_track" else "table", "source": source,
            "source_name": record.filename, "sha256": record.digest,
            "row_count": len(dataframe.index),
            "columns": [{"name": str(column), "dtype": str(dataframe[column].dtype), "missing_count": int(dataframe[column].isna().sum())} for column in dataframe.columns],
            "rows": dataframe.head(8).where(dataframe.notna(), None).to_dict(orient="records"),
        }
    adata = record.adata
    if adata is None and record.manifest is not None:
        manifest = record.manifest
        return {
            "dataset_id": dataset_id, "kind": str(manifest.get("kind", record.kind)), "source": source,
            "source_name": record.filename, "sha256": record.digest,
            "manifest_version": manifest.get("version", "1.0"),
            "summary": manifest.get("summary", "本地组学 manifest"), "columns": [], "rows": [],
        }
    if adata is None and record.sequence_record is not None:
        sequence = record.sequence_record
        return {
            "dataset_id": dataset_id, "kind": "dna", "source": source,
            "source_name": record.filename, "sha256": record.digest,
            "sequence_id": str(sequence.id), "sequence_length": len(sequence.seq),
            "feature_count": len(sequence.features),
            "feature_types": sorted({str(feature.type) for feature in sequence.features}), "columns": [], "rows": [],
        }
    assert adata is not None
    coordinates = [{"key": str(key), "dimensions": int(value.shape[1])} for key, value in adata.obsm.items() if getattr(value, "ndim", 0) == 2 and value.shape[0] == adata.n_obs and value.shape[1] >= 2]
    preview = adata.obs.head(8).copy()
    preview.insert(0, "cell_id", adata.obs_names[: len(preview)].astype(str))
    preview = preview.astype(object).where(pd.notna(preview), None)
    return {
        "dataset_id": dataset_id, "kind": "single_cell", "source": source,
        "source_name": record.filename, "sha256": record.digest,
        "row_count": int(adata.n_obs), "cell_count": int(adata.n_obs), "gene_count": int(adata.n_vars),
        "columns": [{"name": str(column), "dtype": str(adata.obs[column].dtype), "missing_count": int(adata.obs[column].isna().sum())} for column in adata.obs.columns],
        "rows": _json_rows(preview), "coordinates": coordinates,
        "layers": [str(key) for key in adata.layers.keys() if key is not None], "has_raw": adata.raw is not None,
        "matrix_format": "sparse" if sparse.issparse(adata.X) else "dense",
        "gene_names": [str(name) for name in adata.var_names[:500]], "gene_names_truncated": adata.n_vars > 500,
    }


def search_genes(dataset_id: str, query: str, limit: int = 50) -> list[str]:
    adata = get_anndata(dataset_id)
    needle = query.casefold().strip()
    if not needle:
        return list(map(str, adata.var_names[:limit]))
    return [name for name in map(str, adata.var_names) if needle in name.casefold()][:limit]


def _json_rows(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    return [{key: (value.item() if isinstance(value, np.generic) else value) for key, value in row.items()} for row in dataframe.to_dict(orient="records")]


def _parse_genome_track(filename: str, payload: bytes) -> DatasetRecord:
    suffix = Path(filename).suffix.lower()
    try:
        text = payload.decode("utf-8-sig")
        rows: list[dict[str, object]] = []
        if suffix in {".bed", ".bedgraph"} or filename.lower().endswith(".chrom.sizes"):
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip() or line.startswith(("#", "track", "browser")):
                    continue
                parts = line.split("\t")
                if filename.lower().endswith(".chrom.sizes"):
                    if len(parts) < 2:
                        raise ValueError(f"第 {line_number} 行 chrom.sizes 缺少长度。")
                    row = {"chrom": parts[0], "start": 0, "end": int(parts[1])}
                else:
                    if len(parts) < 3:
                        raise ValueError(f"第 {line_number} 行至少需要 chromosome、start、end。")
                    row = {"chrom": parts[0], "start": int(parts[1]), "end": int(parts[2])}
                if suffix == ".bedgraph":
                    if len(parts) < 4:
                        raise ValueError(f"第 {line_number} 行 bedGraph 缺少 value。")
                    row["value"] = float(parts[3])
                elif len(parts) >= 4:
                    row["label"] = parts[3]
                rows.append(row)
        else:
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 5:
                    raise ValueError(f"第 {line_number} 行 GFF/GTF 至少需要 5 列。")
                rows.append({"chrom": parts[0], "source": parts[1], "feature": parts[2], "start": int(parts[3]), "end": int(parts[4]), "score": parts[5] if len(parts) > 5 else ".", "strand": parts[6] if len(parts) > 6 else ".", "attributes": parts[8] if len(parts) > 8 else ""})
        if not rows:
            raise ValueError("轨道文件没有可用记录。")
        frame = pd.DataFrame(rows)
    except (UnicodeDecodeError, ValueError, OverflowError) as error:
        if isinstance(error, ValueError) and str(error).startswith("第"):
            raise
        raise ValueError("无法读取基因组轨道；请使用 UTF-8 BED、bedGraph、GFF3 或 GTF。") from error
    return DatasetRecord("genome_track", Path(filename).name, payload, sha256(payload).hexdigest(), dataframe=frame)
