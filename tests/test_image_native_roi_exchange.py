"""Pre-Java bounds and strict source/ROI exchange contract."""

from hashlib import sha256
from io import BytesIO
import struct
from threading import Event
from zipfile import ZipFile

import pytest

from backend.image.assets import ImageAsset
from backend.image.native_roi_exchange import (preflight_roi, preflight_zip,
                                               validate_exchange_collection)


def rectangle_header() -> bytes:
    data = bytearray(128)
    data[:4] = b"Iout"
    struct.pack_into(">H", data, 4, 228)
    data[6] = 1
    struct.pack_into(">i", data, 60, 64)
    return bytes(data)


def archive(entries):
    stream = BytesIO()
    with ZipFile(stream, "w") as zipped:
        for name, data in entries:
            zipped.writestr(name, data)
    return stream.getvalue()


def test_roi_header_rejects_allocation_fields_before_java():
    good = rectangle_header()
    assert preflight_roi(good)["encoded_type"] == 1
    mutations = []
    for offset, fmt, value in ((36, ">i", 2**30), (60, ">i", 2**30),
                               (16, ">H", 65535), (48, ">H", 4),
                               (40, ">i", 0x123456), (4, ">H", 65535),
                               (50, ">H", 1024), (64 + 4, ">i", 65535)):
        bad = bytearray(good)
        struct.pack_into(fmt, bad, offset, value)
        mutations.append(bytes(bad))
    bad_name = bytearray(good)
    struct.pack_into(">i", bad_name, 64 + 16, 2**30)
    struct.pack_into(">i", bad_name, 64 + 20, 80)
    mutations.append(bytes(bad_name))
    bad_float = bytearray(good)
    struct.pack_into(">f", bad_float, 18, float("nan"))
    mutations.append(bytes(bad_float))
    bad_shape = bytearray(good)
    struct.pack_into(">i", bad_shape, 36, 1)
    struct.pack_into(">f", bad_shape, 64, 3.0)
    mutations.append(bytes(bad_shape))
    for bad in mutations:
        with pytest.raises(ValueError):
            preflight_roi(bad)


def test_zip_rejects_path_duplicate_manifest_and_expansion():
    roi = rectangle_header()
    identity = {"sha256": "a" * 64, "bytes": 10, "axes": []}
    assert len(preflight_zip(archive([("one.roi", roi)]), identity)[0]) == 1
    for entries in ([('../escape.roi', roi)], [('C:drive.roi', roi)],
                    [('one.roi', roi), ('ONE.roi', roi)],
                    [('one.roi', roi), ('one.roi', roi)],
                    [('unknown.bin', roi)], [('one.roi', roi),
                                            ('biofigure-source.json', b'{"sha256":"wrong"}')],
                    [('one.roi', b'x' * (32 * 1024 + 1))]):
        with pytest.raises(ValueError):
            preflight_zip(archive(entries), identity)


def test_collection_requires_real_source_and_strict_native_geometry(tmp_path):
    file = tmp_path / "source.tif"
    file.write_bytes(b"synthetic-source")
    asset = ImageAsset(id="synthetic", name=file.name, bytes=file.stat().st_size,
                       sha256=sha256(file.read_bytes()).hexdigest(), path=file,
                       metadata={"axes": [{"name": "X", "length": 20},
                                           {"name": "Y", "length": 20}]})
    source = {"sha256": asset.sha256, "bytes": asset.bytes, "axes": asset.metadata["axes"]}
    item = {"id": "a" * 32, "name": "Test ROI", "indices": {},
            "roi": {"version": "1.0", "kind": "line", "points": [
                {"x": 1.25, "y": 2.5}, {"x": 7.75, "y": 2.5}], "stroke_width": 2.5}}
    document = {"version": "2.0", "source": source, "items": [item]}
    assert validate_exchange_collection(asset, document, Event())["items"][0]["roi"]["kind"] == "line"
    for invalid in ({**document, "source": {**source, "sha256": "0" * 64}},
                    {**document, "items": [item, item]},
                    {**document, "items": [{**item, "roi": {**item["roi"], "extra": 1}}]}):
        with pytest.raises(ValueError):
            validate_exchange_collection(asset, invalid, Event())
    file.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        validate_exchange_collection(asset, document, Event())
