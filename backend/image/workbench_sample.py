"""Prepare an isolated, synthetic image for the paired Fiji connector."""

from io import BytesIO

from PIL import Image, ImageDraw
from starlette.datastructures import UploadFile

from backend.image.assets import ImageAsset, ImageAssetStore
from backend.image.fiji_process import RECEIPT, RUNTIME
from backend.image.jobs import ImageJob, manager
from backend.image.paths import image_work_dir


def fiji_sample_available() -> bool:
    return RECEIPT.is_file() and (RUNTIME / "fiji-windows-x64.exe").is_file()


async def _store_sample(image: Image.Image, filename: str) -> tuple[ImageAssetStore, ImageAsset]:
    buffer = BytesIO()
    with image:
        image.save(buffer, format="TIFF", compression="tiff_lzw")
    buffer.seek(0)
    store = ImageAssetStore(image_work_dir("workbench-sample-inputs"), max_assets=1,
                            max_session_bytes=1024 * 1024, max_image_bytes=1024 * 1024)
    try:
        asset = await store.add(UploadFile(buffer, filename=filename))
        return store, asset
    except BaseException:
        store.close()
        raise


async def publication_sample() -> tuple[ImageAssetStore, ImageAsset]:
    image = Image.new("L", (800, 560), 23)
    draw = ImageDraw.Draw(image)
    for x, y, radius in ((170, 150, 55), (335, 400, 73), (520, 185, 63), (625, 385, 61)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=56, outline=145, width=6)
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=118)
    return await _store_sample(image, "synthetic-publication-image.tif")


async def submit_fiji_sample() -> ImageJob:
    # The same image goes through the existing queue, engine verification and
    # metadata reader as a normal source. Its separate store is task-owned.
    pixels = bytes(index * 17 % 256 for index in range(24 * 16))
    store, asset = await _store_sample(Image.frombytes("L", (24, 16), pixels), "synthetic-fiji-sample.tif")
    try:
        return manager.submit_inspection(store, asset.id, close_lease_store_on_finish=True,
                                         source_label="合成 TIFF · Fiji 检查")
    except BaseException:
        store.close()
        raise
