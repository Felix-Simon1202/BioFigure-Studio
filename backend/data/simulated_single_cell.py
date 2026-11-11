"""Deterministic anonymous AnnData fixture for local onboarding and QA."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

import anndata as ad
import numpy as np
import pandas as pd

from backend.data.store import DatasetRecord


@lru_cache(maxsize=1)
def simulated_single_cell_record() -> DatasetRecord:
    matrix = np.array([[1, 0, 2], [2, 1, 0], [0, 2, 3], [4, 0, 1], [3, 1, 2], [1, 3, 0]], dtype=float)
    data = ad.AnnData(
        X=matrix,
        obs=pd.DataFrame({"cluster": ["A", "A", "B", "B", "C", "C"], "score": [.1, .4, .8, .2, .9, .5]}, index=[f"cell-{i}" for i in range(6)]),
        var=pd.DataFrame(index=["G1", "G2", "G3"]),
    )
    data.obsm["X_umap"] = np.array([[0, 0], [1, 0], [0, 1], [1, 1], [2, 0], [2, 1]], dtype=float)
    data.layers["counts"] = matrix
    temporary_name = ""
    try:
        with NamedTemporaryFile(suffix=".h5ad", delete=False) as handle:
            temporary_name = handle.name
        data.write_h5ad(temporary_name)
        payload = Path(temporary_name).read_bytes()
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    return DatasetRecord("single_cell", "synthetic-anonymous.h5ad", payload, sha256(payload).hexdigest(), adata=data)
