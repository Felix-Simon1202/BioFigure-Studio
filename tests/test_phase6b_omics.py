from io import BytesIO, StringIO
import json
from tempfile import NamedTemporaryFile

import anndata as ad
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.api.app import app


client = TestClient(app)


def _chart(dataset_id: str, chart_type: str, **extra: object) -> dict[str, object]:
    return {
        "spec_version": "1.1", "dataset_id": dataset_id, "chart_type": chart_type,
        "title": "phase 6B", "theme_id": "scientific_clear", "palette_id": "theme",
        "width_mm": 160, "height_mm": 105, "dpi": 120, "font_size": 10, "line_width": 1.2,
        **extra,
    }


def test_spatial_h5ad_renders_existing_coordinates() -> None:
    data = ad.AnnData(X=np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 1.0]]), obs=pd.DataFrame({"cluster": ["A", "B", "A"], "score": [1.0, 2.0, 3.0]}), var=pd.DataFrame(index=["G1", "G2"]))
    data.obsm["spatial"] = np.array([[0, 0], [1, 0], [0, 1]], dtype=float)
    with NamedTemporaryFile(suffix=".h5ad", delete=False) as handle:
        temporary_name = handle.name
    try:
        data.write_h5ad(temporary_name)
        payload = open(temporary_name, "rb").read()
    finally:
        import os
        os.unlink(temporary_name)
    uploaded = client.post("/api/datasets", files={"file": ("spatial.h5ad", payload, "application/octet-stream")})
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["dataset_id"]
    rendered = client.post("/api/renders", json={"chart": _chart(dataset_id, "spatial_categorical", coordinate_key="spatial", color_field="cluster")})
    assert rendered.status_code == 201
    assert client.get(f"/api/renders/{rendered.json()['render_id']}.svg").status_code == 200


def test_circos_manifest_renders() -> None:
    manifest = {"kind": "circos", "version": "1.0", "sectors": {"chr1": 10, "chr2": 8}, "tracks": [{"sector": "chr1", "x": [1, 4, 7], "y": [2, 5, 3]}, {"sector": "chr2", "x": [1, 4, 7], "y": [4, 2, 5]}], "links": [{"source": ["chr1", 2, 5], "target": ["chr2", 1, 3]}]}
    uploaded = client.post("/api/datasets", files={"file": ("circos.json", json.dumps(manifest).encode(), "application/json")})
    assert uploaded.status_code == 201
    rendered = client.post("/api/renders", json={"chart": _chart(uploaded.json()["dataset_id"], "circos")})
    assert rendered.status_code == 201, rendered.text
    assert client.get(f"/api/renders/{rendered.json()['render_id']}.png").headers["content-type"].startswith("image/png")


def test_genbank_and_genome_track_render() -> None:
    record = SeqRecord(Seq("ATGC" * 30), id="plasmid-demo", name="plasmid-demo", description="synthetic")
    record.annotations["molecule_type"] = "DNA"
    record.features = [SeqFeature(FeatureLocation(2, 20), type="CDS", qualifiers={"gene": ["demoA"]}), SeqFeature(FeatureLocation(30, 70, strand=-1), type="misc_feature", qualifiers={"label": ["origin"]})]
    buffer = StringIO(); SeqIO.write(record, buffer, "genbank")
    uploaded = client.post("/api/datasets", files={"file": ("demo.gbk", buffer.getvalue().encode(), "text/plain")})
    assert uploaded.status_code == 201
    rendered = client.post("/api/renders", json={"chart": _chart(uploaded.json()["dataset_id"], "dna_features")})
    assert rendered.status_code == 201, rendered.text

    track = "chr1\t0\t10\tfeature\nchr1\t12\t20\tfeature2\n"
    track_upload = client.post("/api/datasets", files={"file": ("genes.bed", track.encode(), "text/plain")})
    assert track_upload.status_code == 201
    track_render = client.post("/api/renders", json={"chart": _chart(track_upload.json()["dataset_id"], "genome_tracks")})
    assert track_render.status_code == 201, track_render.text


def test_r_ggplot_plugin_renders_when_r_is_installed() -> None:
    frame = pd.DataFrame({"x": [1, 2, 3, 4], "y": [2, 1, 4, 3], "group": ["A", "A", "B", "B"]})
    payload = frame.to_csv(index=False).encode()
    uploaded = client.post("/api/datasets", files={"file": ("r-demo.csv", payload, "text/csv")})
    assert uploaded.status_code == 201
    rendered = client.post("/api/renders", json={"chart": _chart(uploaded.json()["dataset_id"], "r_ggplot", x_column="x", y_column="y", group_column="group")})
    assert rendered.status_code == 201, rendered.text
