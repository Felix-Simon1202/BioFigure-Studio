from hashlib import sha256
from threading import Event

from PIL import Image
import pytest

from backend.image import batch
from backend.image.assets import ImageAsset
from backend.image.montage import MontageCancelled


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.png"
    Image.new("RGBA", (7, 5), (199, 33, 77, 0)).save(path)
    return ImageAsset("source", path.name, path.stat().st_size, sha256(path.read_bytes()).hexdigest(), path)


def test_existing_partial_file_is_never_deleted_on_open_failure(tmp_path, source):
    output = tmp_path / "batch.zip"
    partial = output.with_name("batch.zip.partial")
    partial.write_bytes(b"keep-existing-partial")
    with pytest.raises(FileExistsError):
        batch.run_grid_batch([[source]], 1, 0, output, Event())
    assert partial.read_bytes() == b"keep-existing-partial"
    assert not output.exists()
    assert list(tmp_path.glob("grid-batch-*")) == []


def test_zip_limit_includes_manifest_and_closed_central_directory(tmp_path, monkeypatch, source):
    # The small TIFF body fits in 512 bytes; its full archive does not.
    monkeypatch.setattr(batch, "MAX_BATCH_ZIP_BYTES", 512)
    output = tmp_path / "batch.zip"
    completed = []
    with pytest.raises(ValueError, match="上限"):
        batch.run_grid_batch([[source]], 1, 0, output, Event(), lambda *args: completed.append(True))
    assert completed == [True]  # It reached the manifest rather than the TIFF limit.
    assert not output.exists() and not output.with_name("batch.zip.partial").exists()


def test_cancel_while_verifying_archive_never_publishes(tmp_path, monkeypatch, source):
    token = Event()
    original = batch._hash_stream
    calls = []

    def cancelled_hash(stream, check):
        calls.append(True)
        token.set()
        return original(stream, check)

    monkeypatch.setattr(batch, "_hash_stream", cancelled_hash)
    output = tmp_path / "batch.zip"
    with pytest.raises(MontageCancelled):
        batch.run_grid_batch([[source]], 1, 0, output, token)
    assert calls == [True]
    assert not output.exists() and not output.with_name("batch.zip.partial").exists()


def test_deadline_still_applies_after_last_group(tmp_path, monkeypatch, source):
    now = [0.0]
    monkeypatch.setattr(batch.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(batch, "MAX_BATCH_SECONDS", 1)
    output = tmp_path / "batch.zip"
    with pytest.raises(TimeoutError):
        batch.run_grid_batch([[source]], 1, 0, output, Event(), lambda *args: now.__setitem__(0, 2.0))
    assert not output.exists() and not output.with_name("batch.zip.partial").exists()


def test_publication_does_not_replace_a_file_created_during_the_batch(tmp_path, source):
    output = tmp_path / "batch.zip"
    with pytest.raises(FileExistsError):
        batch.run_grid_batch([[source]], 1, 0, output, Event(), lambda *args: output.write_bytes(b"keep-raced-output"))
    assert output.read_bytes() == b"keep-raced-output"
    assert not output.with_name("batch.zip.partial").exists()
