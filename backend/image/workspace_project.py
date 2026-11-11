"""Portable original image stacks and reviewed workspace state.

Reading a package is deliberately pending: stored metadata and selections must
be checked again against freshly inspected assets before application.
"""

from pathlib import Path
import json
from threading import Event
from typing import Callable, Literal

from pydantic import Field, StrictInt, model_validator

from backend.image.assets import ImageAsset, ImageAssetImportCancelled
from backend.image.project import (GridRecipe, PendingImageProject, ProjectModel, ProjectSource,
    SourceProjectModel, read_source_project, write_source_project)
from backend.image.roi_collection import MAX_COLLECTION_BYTES, validate_collection
from backend.image.selection import build_plane_selection, build_selection, stack_plane_count
from backend.image.native_area_geometry import validate_area_roi
from backend.image.non_area_measure import NATIVE_TYPE_CODES, validate_non_area_roi
from backend.image.set_measurements import validate_measurement_redirect, validate_native_settings


MAX_WORKSPACE_MANIFEST_BYTES = 1024 * 1024


class WorkspaceSelection(ProjectModel):
    indices: dict[Literal["C", "Z", "T"], StrictInt] = Field(default_factory=dict)
    roi: dict | None = None
    extra_measurements: list[Literal["std_dev", "median", "mode", "integrated_density"]] = Field(default_factory=list, max_length=4)


class WorkspaceNativeMeasurement(ProjectModel):
    settings: dict
    roi: dict | None = None
    redirect_source: str | None = None
    redirect_plane: dict[Literal["C", "Z", "T"], StrictInt] | None = None


class WorkspaceSourceState(ProjectModel):
    collection: dict | None = None
    selection: WorkspaceSelection | None = None
    native_measurement: WorkspaceNativeMeasurement | None = None


class ImageWorkspaceProject(SourceProjectModel):
    schema_version: Literal["1.0", "1.1"]
    kind: str = Field(pattern=r"^image_workspace$")
    source_states: dict[str, WorkspaceSourceState] = Field(default_factory=dict)
    active_source_key: str | None = Field(default=None, pattern=r"^s[0-7]$")
    selected_source_keys: list[str] = Field(default_factory=list, max_length=8)
    grid: GridRecipe = Field(default_factory=lambda: GridRecipe(columns=1, gap_px=0))

    @model_validator(mode="after")
    def check_references(self):
        available = {source.key for source in self.sources}
        if (set(self.source_states) - available or set(self.selected_source_keys) - available
                or len(self.selected_source_keys) != len(set(self.selected_source_keys))
                or (self.active_source_key is not None and self.active_source_key not in available)):
            raise ValueError("Workspace state references an unknown or repeated source")
        for source_key, state in self.source_states.items():
            native = state.native_measurement
            if native is not None and (self.schema_version == "1.0" or (
                    native.redirect_source is not None and (
                        native.redirect_source not in available or native.redirect_source == source_key))):
                raise ValueError("Workspace native measurement has an invalid source reference or version")
        if self.grid.columns > len(self.sources):
            raise ValueError("Workspace grid columns exceed its source count")
        return self


class WorkspaceExportRequest(ProjectModel):
    asset_ids: list[str] = Field(min_length=1, max_length=8)
    source_states: dict[str, WorkspaceSourceState] = Field(default_factory=dict)
    active_asset_id: str | None = None
    selected_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    grid: GridRecipe


def normalize_workspace_state(asset: ImageAsset, state: WorkspaceSourceState,
                              sources: dict[str, ImageAsset]) -> WorkspaceSourceState:
    """Caller must supply live inspected metadata, never recorded package claims."""
    if state.collection is not None and len(json.dumps(state.collection, ensure_ascii=False).encode("utf-8")) > MAX_COLLECTION_BYTES:
        raise ValueError("Workspace ROI collection exceeds its 128 KiB budget")
    collection = validate_collection(asset, state.collection) if state.collection is not None else None
    selection = None
    if state.selection is not None:
        checked = build_selection(asset, state.selection.indices, state.selection.roi,
                                  state.selection.extra_measurements)
        selection = WorkspaceSelection(indices=checked.indices,
            roi=None if checked.roi["kind"] == "full" else checked.roi,
            extra_measurements=list(checked.extra_measurements))
    native = state.native_measurement
    if native is not None:
        axes, plane, width, height = build_plane_selection(asset, selection.indices if selection else {})
        settings = validate_native_settings(native.settings)
        roi = native.roi
        if roi is not None:
            count = stack_plane_count(axes)
            if count > 64:
                raise ValueError("原生区域最多支持 64 个线性平面。")
            kind = roi.get("kind")
            roi = (validate_non_area_roi(roi, width, height, count)
                   if isinstance(kind, str) and kind in NATIVE_TYPE_CODES else validate_area_roi(roi, width, height))
        target = sources.get(native.redirect_source) if native.redirect_source is not None else None
        if native.redirect_source is not None and target is None:
            raise ValueError("项目中缺少测量的第二来源。")
        redirect = validate_measurement_redirect(asset, axes, plane, target, native.redirect_plane)
        native = WorkspaceNativeMeasurement(settings=settings, roi=roi, redirect_source=native.redirect_source,
                                           redirect_plane=redirect["plane"] if redirect else None)
    return WorkspaceSourceState(collection=collection, selection=selection, native_measurement=native)


def save_workspace_project(assets: list[ImageAsset], states_by_asset: dict[str, dict | WorkspaceSourceState],
                           output: Path, *, active_asset_id: str | None = None,
                           selected_asset_ids: list[str] | None = None, grid: GridRecipe | None = None,
                           cancel: Event | None = None) -> ImageWorkspaceProject:
    identities = {asset.id: f"s{index}" for index, asset in enumerate(assets)}
    if not 1 <= len(assets) <= 8 or len(identities) != len(assets) or set(states_by_asset) - identities.keys():
        raise ValueError("Workspace sources or state identities are invalid")
    selected = [] if selected_asset_ids is None else selected_asset_ids
    if (set(selected) - identities.keys() or len(selected) != len(set(selected))
            or (active_asset_id is not None and active_asset_id not in identities)):
        raise ValueError("Workspace view references an unknown or repeated asset")
    states = {}
    sources = {asset.id: asset for asset in assets}
    for asset in assets:
        if cancel is not None and cancel.is_set():
            raise ImageAssetImportCancelled()
        if asset.id in states_by_asset:
            state = normalize_workspace_state(asset, WorkspaceSourceState.model_validate(states_by_asset[asset.id]),
                                              sources)
            if state.native_measurement and state.native_measurement.redirect_source is not None:
                state.native_measurement.redirect_source = identities[state.native_measurement.redirect_source]
            states[identities[asset.id]] = state
    manifest = ImageWorkspaceProject(schema_version="1.1", kind="image_workspace",
        sources=[ProjectSource(key=identities[asset.id], member=f"sources/{index}.bin",
            original_name=asset.name, bytes=asset.bytes, sha256=asset.sha256, recorded_metadata=asset.metadata)
            for index, asset in enumerate(assets)], source_states=states,
        active_source_key=identities[active_asset_id] if active_asset_id is not None else None,
        selected_source_keys=[identities[identifier] for identifier in selected],
        grid=grid or GridRecipe(columns=1, gap_px=0))
    write_source_project(assets, manifest, output, cancel, max_manifest_bytes=MAX_WORKSPACE_MANIFEST_BYTES)
    return manifest


def read_workspace_project(path: Path, destination: Path, cancel: Event | None = None, *,
                           before_extract: Callable[[ImageWorkspaceProject], None] | None = None
                           ) -> PendingImageProject[ImageWorkspaceProject]:
    return read_source_project(path, destination, ImageWorkspaceProject, cancel,
        before_extract=before_extract, max_manifest_bytes=MAX_WORKSPACE_MANIFEST_BYTES)
