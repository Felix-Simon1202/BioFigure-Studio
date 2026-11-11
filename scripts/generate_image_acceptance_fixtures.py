"""Generate anonymous pixel/axis fixtures and verify their encoded round trip.

Uses only the project's locked NumPy/Pillow dependencies. Output is test data,
never an image-processing implementation or evidence of Fiji parity.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from PIL import Image, TiffImagePlugin


def pixel_digest(array: np.ndarray) -> str:
    header = json.dumps({"dtype": array.dtype.str, "shape": list(array.shape)}, sort_keys=True).encode()
    return sha256(header + b"\n" + np.ascontiguousarray(array).tobytes()).hexdigest()


def generate(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    y, x = np.indices((24, 32), dtype=np.uint32)
    gray = ((x * 1901 + y * 3217) % 65536).astype(np.uint16)
    gray[0, :8] = [0, 1, 255, 256, 1023, 4095, 32768, 65535]
    rgb = np.stack(((x * 13 + y * 7) % 256, (x * 3 + y * 23) % 256, (255 - x * 5 + y * 2) % 256), axis=-1).astype(np.uint8)
    rgba = np.concatenate((rgb, ((x * 17 + y * 11) % 256).astype(np.uint8)[..., None]), axis=-1)
    rgba[0, 0] = [199, 33, 77, 0]  # Hidden RGB must survive lossless RGBA storage.
    floating = (x.astype(np.float32) / 7 - y.astype(np.float32) / 3 - 5).astype(np.float32)
    floating[0, :6] = [-100.25, -0.5, 0, 0.125, 1000.75, 65536.5]
    odd_y, odd_x = np.indices((37, 51), dtype=np.uint32)
    odd_rgb = np.stack(((odd_x * 11) % 256, (odd_y * 19) % 256, (odd_x + odd_y * 3) % 256), axis=-1).astype(np.uint8)
    cases = [
        ("rgb8.tif", rgb, "YXS", None, None),
        ("rgba8.png", rgba, "YXS", None, None),
        ("灰度16_非等距标定.tif", gray, "YX", (0.25, 0.5), None),
        ("float32_signed.tif", floating, "YX", (0.25, 0.5), None),
        ("channels16.tif", np.stack((gray, np.flip(gray, axis=1))), "CYX", (0.25, 0.5), "channels=2\nslices=1\nframes=1\n"),
        ("zstack16.tif", np.stack((gray, np.roll(gray, 1, axis=0), np.roll(gray, 2, axis=0))), "ZYX", (0.25, 0.5), "channels=1\nslices=3\nframes=1\nspacing=1.5\n"),
        ("time16.tif", np.stack([np.roll(gray, index, axis=1) for index in range(4)]), "TYX", (0.25, 0.5), "channels=1\nslices=1\nframes=4\nfinterval=2.0\n"),
        ("odd_rgb8.tif", odd_rgb, "YXS", (0.8, 0.8), None),
    ]
    records = []
    for filename, pixels, axes, scale, stack_header in cases:
        path = output / filename
        is_stack = axes in {"CYX", "ZYX", "TYX"}
        planes = list(pixels) if is_stack else [pixels]
        images = [Image.fromarray(plane) for plane in planes]
        kwargs = {}
        if path.suffix == ".tif":
            info = TiffImagePlugin.ImageFileDirectory_v2()
            if scale is not None:
                info[282], info[283], info[296] = 1 / scale[0], 1 / scale[1], 1
                info[270] = f"ImageJ=1.54\nimages={len(planes)}\n{stack_header or ''}unit=um\nhyperstack={'true' if is_stack else 'false'}\nmode=grayscale\n"
            # ImageJ's uncompressed hyperstack shortcut assumes contiguous planes;
            # Pillow writes per-page IFDs between planes. Deflate uses the normal
            # TIFF page decoder instead of misrepresenting that special layout.
            kwargs = {"tiffinfo": info, "compression": "tiff_deflate" if is_stack else "raw"}
            if is_stack:
                kwargs.update(save_all=True, append_images=images[1:])
        images[0].save(path, **kwargs)
        for image in images:
            image.close()
        # Decode through the locked reader and compare every stored sample.
        decoded = []
        with Image.open(path) as reopened:
            assert reopened.n_frames == len(planes), filename
            for index, plane in enumerate(planes):
                reopened.seek(index)
                sample = np.array(reopened)
                assert sample.dtype == plane.dtype, (filename, sample.dtype, plane.dtype)
                assert np.array_equal(sample, plane), (filename, index)
                decoded.append(sample)
            if scale is not None:
                assert float(reopened.tag_v2[282]) == 1 / scale[0], filename
                assert float(reopened.tag_v2[283]) == 1 / scale[1], filename
        decoded_pixels = np.stack(decoded) if is_stack else decoded[0]
        assert pixel_digest(decoded_pixels) == pixel_digest(pixels), filename
        np.save(output / (filename + ".expected.npy"), pixels, allow_pickle=False)
        records.append({
            "file": filename, "axes": axes, "shape": list(pixels.shape),
            "dtype": pixels.dtype.str, "bit_depth": pixels.dtype.itemsize * 8,
            "pixel_size_um_xy": scale, "z_spacing_um": 1.5 if axes == "ZYX" else None,
            "frame_interval_seconds": 2.0 if axes == "TYX" else None,
            "file_sha256": sha256(path.read_bytes()).hexdigest(),
            "pixel_sha256": pixel_digest(pixels),
            "expected_array": filename + ".expected.npy", "encoded_roundtrip_verified": True,
        })
    result = {"schema_version": "1.0", "source": "BioFigure Studio deterministic synthetic test patterns", "fiji_verified": False, "items": records}
    (output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory; existing data is never overwritten")
    options = parser.parse_args()
    manifest = generate(options.output)
    print(f"Verified {len(manifest['items'])} synthetic fixtures; Fiji interoperability remains to be tested.")
