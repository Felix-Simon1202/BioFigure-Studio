"""Provide a fixed CSV suitable for demonstrating the local workflow."""

from io import StringIO
from hashlib import sha256

import pandas as pd


SIMULATED_DATASET_ID = "simulated-cell-response-v1"
SIMULATED_ECOLOGY_DATASET_ID = "simulated-ecology-composition-v1"
SIMULATED_ECOLOGY_ALPHA_DATASET_ID = "simulated-ecology-alpha-v1"
SIMULATED_ECOLOGY_BETA_DATASET_ID = "simulated-ecology-beta-v1"
SIMULATED_ECOLOGY_ORDINATION_DATASET_ID = "simulated-ecology-ordination-v1"
SIMULATED_ECOLOGY_ENVIRONMENT_DATASET_ID = "simulated-ecology-environment-v1"
SIMULATED_ECOLOGY_TIME_DATASET_ID = "simulated-ecology-time-v1"
SIMULATED_ECOLOGY_SPATIAL_DATASET_ID = "simulated-ecology-spatial-v1"
SIMULATED_CSV = """sample,condition,response,viability\nS01,Control,0.82,91\nS02,Control,0.76,88\nS03,Control,0.90,94\nS04,Treatment A,1.35,79\nS05,Treatment A,1.52,74\nS06,Treatment A,1.44,77\nS07,Treatment B,1.10,84\nS08,Treatment B,1.18,82\nS09,Treatment B,1.05,86\n"""


def simulated_dataframe() -> pd.DataFrame:
    """Return a fresh dataframe so callers cannot mutate shared data."""
    return pd.read_csv(StringIO(SIMULATED_CSV))


def preview_payload(limit: int = 8) -> dict[str, object]:
    """Return bounded metadata and records without disclosing filesystem paths."""
    dataframe = simulated_dataframe()
    return {
        "dataset_id": SIMULATED_DATASET_ID,
        "source": "built-in simulated CSV",
        "row_count": len(dataframe.index),
        "columns": [
            {"name": column, "dtype": str(dataframe[column].dtype)}
            for column in dataframe.columns
        ],
        "rows": dataframe.head(limit).to_dict(orient="records"),
    }


SIMULATED_ECOLOGY_CSV = """sample,site,taxon,abundance
S01,Forest,Oak,0.45
S01,Forest,Fern,0.35
S01,Forest,Moss,0.20
S02,Forest,Oak,0.30
S02,Forest,Fern,0.50
S02,Forest,Moss,0.20
S03,Meadow,Oak,0.20
S03,Meadow,Fern,0.25
S03,Meadow,Moss,0.55
S04,Meadow,Oak,0.25
S04,Meadow,Fern,0.35
S04,Meadow,Moss,0.40
"""


def simulated_ecology_dataframe() -> pd.DataFrame:
    """Return a fresh bounded long table for community composition previews."""
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_CSV))


def ecology_preview_payload(limit: int = 8) -> dict[str, object]:
    dataframe = simulated_ecology_dataframe()
    return {
        "dataset_id": SIMULATED_ECOLOGY_DATASET_ID,
        "kind": "ecology_composition",
        "source": "built-in simulated ecology composition",
        "source_name": "simulated-ecology-composition.csv",
        "row_count": len(dataframe.index),
        "columns": [
            {"name": column, "dtype": str(dataframe[column].dtype), "missing_count": int(dataframe[column].isna().sum())}
            for column in dataframe.columns
        ],
        "rows": dataframe.head(limit).to_dict(orient="records"),
    }


SIMULATED_ECOLOGY_ALPHA_CSV = """sample,group,metric,value
S01,Forest,Shannon,2.1
S02,Forest,Shannon,2.4
S03,Forest,Shannon,2.2
S04,Meadow,Shannon,1.5
S05,Meadow,Shannon,1.8
S06,Meadow,Shannon,1.7
S01,Forest,Simpson,0.82
S02,Forest,Simpson,0.86
S03,Forest,Simpson,0.80
S04,Meadow,Simpson,0.62
S05,Meadow,Simpson,0.69
S06,Meadow,Simpson,0.66
"""
SIMULATED_ECOLOGY_BETA_CSV = """sample,group,PCoA1,PCoA2
S01,Forest,-0.42,0.18
S02,Forest,-0.28,0.26
S03,Forest,-0.35,0.05
S04,Meadow,0.31,-0.16
S05,Meadow,0.44,-0.28
S06,Meadow,0.26,-0.37
"""
SIMULATED_ECOLOGY_ORDINATION_CSV = """entity,entity_type,group,axis_1,axis_2
S01,sample,Forest,-0.42,0.18
S02,sample,Forest,-0.28,0.26
S03,sample,Meadow,0.31,-0.16
S04,sample,Meadow,0.44,-0.28
Oak,taxon,,0.62,0.48
Fern,taxon,,-0.28,0.72
Moss,taxon,,0.18,-0.64
"""
SIMULATED_ECOLOGY_ENVIRONMENT_CSV = """entity,entity_type,group,axis_1,axis_2,nitrate
S01,sample,Forest,-0.42,0.18,3.2
S02,sample,Forest,-0.28,0.26,4.1
S03,sample,Forest,-0.35,0.05,3.7
S04,sample,Meadow,0.31,-0.16,8.5
S05,sample,Meadow,0.44,-0.28,9.2
S06,sample,Meadow,0.26,-0.37,7.8
"""
SIMULATED_ECOLOGY_TIME_CSV = """sample,time,value,group,replicate,error
S01,1,4.2,Forest,R1,0.3
S01,2,5.1,Forest,R1,0.4
S01,3,6.4,Forest,R1,0.5
S02,1,3.4,Meadow,R1,0.2
S02,2,3.9,Meadow,R1,0.3
S02,3,4.8,Meadow,R1,0.4
S03,1,4.0,Forest,R2,0.3
S03,2,5.4,Forest,R2,0.4
S03,3,6.0,Forest,R2,0.5
"""
SIMULATED_ECOLOGY_SPATIAL_CSV = """sample,group,longitude,latitude
P01,Forest,-1.20,0.80
P02,Forest,-0.62,1.35
P03,Forest,0.05,0.72
P04,Meadow,0.48,-0.18
P05,Meadow,1.12,-0.74
P06,Meadow,1.58,-0.05
"""


def simulated_ecology_alpha_dataframe() -> pd.DataFrame:
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_ALPHA_CSV))


def simulated_ecology_beta_dataframe() -> pd.DataFrame:
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_BETA_CSV))

def simulated_ecology_ordination_dataframe() -> pd.DataFrame:
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_ORDINATION_CSV))


def simulated_ecology_environment_dataframe() -> pd.DataFrame:
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_ENVIRONMENT_CSV))

def simulated_ecology_time_dataframe() -> pd.DataFrame:
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_TIME_CSV))


def simulated_ecology_spatial_dataframe() -> pd.DataFrame:
    return pd.read_csv(StringIO(SIMULATED_ECOLOGY_SPATIAL_CSV))


def _ecology_diversity_preview(dataset_id: str, filename: str, dataframe: pd.DataFrame, summary: str, limit: int = 8) -> dict[str, object]:
    source_csv = {
        SIMULATED_ECOLOGY_ALPHA_DATASET_ID: SIMULATED_ECOLOGY_ALPHA_CSV,
        SIMULATED_ECOLOGY_BETA_DATASET_ID: SIMULATED_ECOLOGY_BETA_CSV,
        SIMULATED_ECOLOGY_ORDINATION_DATASET_ID: SIMULATED_ECOLOGY_ORDINATION_CSV,
    }.get(dataset_id)
    return {
        "dataset_id": dataset_id, "kind": "ecology_diversity", "source": summary, "source_name": filename,
        "sha256": sha256(source_csv.encode("utf-8")).hexdigest() if source_csv is not None else None,
        "row_count": len(dataframe.index),
        "columns": [{"name": column, "dtype": str(dataframe[column].dtype), "missing_count": int(dataframe[column].isna().sum())} for column in dataframe.columns],
        "rows": dataframe.head(limit).to_dict(orient="records"),
    }


def ecology_alpha_preview_payload(limit: int = 8) -> dict[str, object]:
    return _ecology_diversity_preview(SIMULATED_ECOLOGY_ALPHA_DATASET_ID, "simulated-ecology-alpha.csv", simulated_ecology_alpha_dataframe(), "built-in simulated alpha diversity", limit)


def ecology_beta_preview_payload(limit: int = 8) -> dict[str, object]:
    return _ecology_diversity_preview(SIMULATED_ECOLOGY_BETA_DATASET_ID, "simulated-ecology-beta.csv", simulated_ecology_beta_dataframe(), "built-in simulated beta ordination", limit)

def ecology_ordination_preview_payload(limit: int = 8) -> dict[str, object]:
    return _ecology_diversity_preview(SIMULATED_ECOLOGY_ORDINATION_DATASET_ID, "simulated-ecology-ordination.csv", simulated_ecology_ordination_dataframe(), "built-in simulated ordination biplot", limit)


def ecology_environment_preview_payload(limit: int = 8) -> dict[str, object]:
    payload = _ecology_diversity_preview(SIMULATED_ECOLOGY_ENVIRONMENT_DATASET_ID, "simulated-ecology-environment.csv", simulated_ecology_environment_dataframe(), "built-in simulated environment gradient", limit)
    payload["kind"] = "ecology_environment_gradient"
    return payload

def ecology_time_preview_payload(limit: int = 8) -> dict[str, object]:
    dataframe = simulated_ecology_time_dataframe()
    return {"dataset_id": SIMULATED_ECOLOGY_TIME_DATASET_ID, "kind": "ecology_time_series", "source": "built-in simulated ecology time series", "source_name": "simulated-ecology-time.csv", "row_count": len(dataframe.index), "columns": [{"name": c, "dtype": str(dataframe[c].dtype), "missing_count": int(dataframe[c].isna().sum())} for c in dataframe.columns], "rows": dataframe.head(limit).to_dict(orient="records")}


def ecology_spatial_preview_payload(limit: int = 8) -> dict[str, object]:
    dataframe = simulated_ecology_spatial_dataframe()
    return {
        "dataset_id": SIMULATED_ECOLOGY_SPATIAL_DATASET_ID,
        "kind": "ecology_spatial_points",
        "source": "built-in synthetic spatial ecology points",
        "source_name": "simulated-ecology-spatial.csv",
        "sha256": sha256(SIMULATED_ECOLOGY_SPATIAL_CSV.encode("utf-8")).hexdigest(),
        "row_count": len(dataframe.index),
        "columns": [{"name": c, "dtype": str(dataframe[c].dtype), "missing_count": int(dataframe[c].isna().sum())} for c in dataframe.columns],
        "rows": dataframe.head(limit).to_dict(orient="records"),
    }
