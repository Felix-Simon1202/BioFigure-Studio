"""Portable grid recipes with original source bytes and untrusted metadata claims.

Opening a package produces pending inputs. It never grants Fiji verification
status or executes the stored annotations or recipe by itself.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from threading import Event
from typing import Callable, Generic, TypeVar
from zipfile import ZIP_STORED, ZipFile

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.image.annotations import create_overlay
from backend.image.assets import ImageAsset, ImageAssetImportCancelled, MAX_IMAGE_BYTES, MAX_SESSION_BYTES
from backend.image.montage import GridProof


MAX_MANIFEST_BYTES = 256 * 1024
MAX_PROJECT_BYTES = MAX_SESSION_BYTES + MAX_MANIFEST_BYTES


class ProjectModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProjectSource(ProjectModel):
    key: str = Field(pattern=r"^s[0-7]$")
    member: str = Field(pattern=r"^sources/[0-7]\.bin$")
    original_name: str = Field(min_length=1, max_length=200)
    bytes: int = Field(gt=0, le=MAX_IMAGE_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recorded_metadata: dict | None = None


class SourceProjectModel(ProjectModel):
    sources: list[ProjectSource] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_sources(self):
        if [(source.key, source.member) for source in self.sources] != [
                (f"s{index}", f"sources/{index}.bin") for index in range(len(self.sources))]:
            raise ValueError("Project source identities are invalid or duplicated")
        if sum(source.bytes for source in self.sources) > MAX_SESSION_BYTES:
            raise ValueError("Project sources exceed the interactive storage budget")
        return self


class GridRecipe(ProjectModel):
    columns: int = Field(ge=1, le=8)
    gap_px: int = Field(ge=0, le=1000)


class ImageGridProject(SourceProjectModel):
    schema_version: str = Field(pattern=r"^1\.0$")
    kind: str = Field(pattern=r"^exact_pixel_grid$")
    grid: GridRecipe
    annotations: list[dict] = Field(max_length=32)
    original_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def check_sources(self):
        if self.grid.columns > len(self.sources):
            raise ValueError("Project columns exceed its source count")
        return self


Manifest = TypeVar("Manifest", bound=SourceProjectModel)


@dataclass(frozen=True)
class PendingImageProject(Generic[Manifest]):
    manifest: Manifest
    source_paths: tuple[Path, ...]
    verification_status: str = "requires_fresh_inspection"


def _copy_hash(source, destination, cancel: Event | None = None, *, limit: int = MAX_IMAGE_BYTES) -> tuple[int, str]:
    count = 0
    digest = sha256()
    while chunk := source.read(4 * 1024 * 1024):
        if cancel is not None and cancel.is_set():
            raise ImageAssetImportCancelled()
        count += len(chunk)
        if count > limit:
            raise ValueError("Project source exceeds its byte budget")
        digest.update(chunk)
        destination.write(chunk)
    return count, digest.hexdigest()


def save_grid_project(assets: list[ImageAsset], proof: GridProof, annotations: list[dict],
                      output: Path) -> ImageGridProject:
    if proof.grid_recipe is None:
        raise ValueError("This result has no saved editable grid recipe")
    if [asset.id for asset in assets] != [placement.asset_id for placement in proof.placements]:
        raise ValueError("Project sources do not match the rendered grid")
    if len({asset.id for asset in assets}) != len(assets):
        raise ValueError("Project source identities must be distinct")
    items, _ = create_overlay(proof, annotations)
    keys = {asset.id: f"s{index}" for index, asset in enumerate(assets)}
    items = [{**item, "asset_id": keys[item["asset_id"]]} if "asset_id" in item else item for item in items]
    manifest = ImageGridProject(schema_version="1.0", kind="exact_pixel_grid", grid=proof.grid_recipe,
        sources=[ProjectSource(key=f"s{index}", member=f"sources/{index}.bin", original_name=asset.name,
                               bytes=asset.bytes, sha256=asset.sha256, recorded_metadata=asset.metadata)
                 for index, asset in enumerate(assets)], annotations=items,
        original_output_sha256=proof.output_sha256)
    write_source_project(assets, manifest, output)
    return manifest


def write_source_project(assets: list[ImageAsset], manifest: Manifest, output: Path,
                         cancel: Event | None = None, *, max_manifest_bytes: int = MAX_MANIFEST_BYTES) -> None:
    if (len(assets) != len(manifest.sources) or
            any((asset.bytes, asset.sha256) != (reference.bytes, reference.sha256)
                for asset, reference in zip(assets, manifest.sources, strict=True))):
        raise ValueError("Project source references do not match the assets")
    encoded = manifest.model_dump_json().encode("utf-8")
    if len(encoded) > max_manifest_bytes:
        raise ValueError("Project manifest exceeds its budget")
    if cancel is not None and cancel.is_set():
        raise ImageAssetImportCancelled()
    created = False
    try:
        with ZipFile(output, "x", compression=ZIP_STORED, allowZip64=True) as archive:
            created = True
            archive.writestr("project.json", encoded)
            for asset, reference in zip(assets, manifest.sources, strict=True):
                with asset.path.open("rb") as source, archive.open(reference.member, "w", force_zip64=True) as target:
                    count, digest = _copy_hash(source, target, cancel, limit=reference.bytes)
                if count != reference.bytes or digest != reference.sha256:
                    raise ValueError("Source changed while saving the project")
        if cancel is not None and cancel.is_set():
            raise ImageAssetImportCancelled()
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def read_grid_project(path: Path, destination: Path, cancel: Event | None = None, *,
                      before_extract: Callable[[ImageGridProject], None] | None = None) -> PendingImageProject[ImageGridProject]:
    return read_source_project(path, destination, ImageGridProject, cancel, before_extract=before_extract)


def read_source_project(path: Path, destination: Path, manifest_type: type[Manifest], cancel: Event | None = None, *,
                        before_extract: Callable[[Manifest], None] | None = None,
                        max_manifest_bytes: int = MAX_MANIFEST_BYTES) -> PendingImageProject[Manifest]:
    max_project_bytes = MAX_SESSION_BYTES + max_manifest_bytes
    if cancel is not None and cancel.is_set():
        raise ImageAssetImportCancelled()
    if path.stat().st_size > max_project_bytes + 65536:
        raise ValueError("Project archive exceeds its byte budget")
    created_paths = []
    created = False
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (not 2 <= len(entries) <= 9 or len(names) != len(set(names))
                    or "project.json" not in names
                    or any(entry.compress_type != ZIP_STORED or entry.flag_bits & 1 for entry in entries)
                    or sum(entry.file_size for entry in entries) > max_project_bytes):
                raise ValueError("Invalid or oversized image project archive")
            if archive.getinfo("project.json").file_size > max_manifest_bytes:
                raise ValueError("Project manifest exceeds its budget")
            manifest = manifest_type.model_validate_json(archive.read("project.json"))
            if set(names) != {"project.json", *(source.member for source in manifest.sources)}:
                raise ValueError("Project contains unexpected archive entries")
            if any(archive.getinfo(source.member).file_size != source.bytes for source in manifest.sources):
                raise ValueError("Project source sizes do not match the manifest")
            if before_extract is not None:
                before_extract(manifest)
            destination.mkdir(parents=True, exist_ok=False)
            created = True
            for reference in manifest.sources:
                # Archive paths never control extraction paths. Retain only a
                # safe suffix for the future image reader's format detection.
                suffix = "".join(Path(reference.original_name).suffixes[-2:]).lower()
                if not re.fullmatch(r"(?:\.[a-z0-9]{1,12}){0,2}", suffix):
                    suffix = ""
                target = destination / (reference.key + suffix)
                with archive.open(reference.member) as source, target.open("xb") as output:
                    created_paths.append(target)
                    count, digest = _copy_hash(source, output, cancel, limit=reference.bytes)
                if count != reference.bytes or digest != reference.sha256:
                    raise ValueError("Project source digest does not match")
        return PendingImageProject(manifest, tuple(created_paths))
    except BaseException:
        if created:
            for target in created_paths:
                if target.resolve().parent != destination.resolve():
                    raise ValueError("Refusing to clean a path outside the project staging directory")
                target.unlink(missing_ok=True)
            destination.rmdir()
        raise
