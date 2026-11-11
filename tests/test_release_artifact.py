from pathlib import Path

import pytest

from scripts.record_release_artifact import select_installer


def test_installer_record_requires_one_current_version(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Expected only"):
        select_installer(tmp_path, "0.3.0")

    old = tmp_path / "BioFigure Studio_0.2.0_x64-setup.exe"
    old.write_bytes(b"old")
    with pytest.raises(ValueError, match="Expected only"):
        select_installer(tmp_path, "0.3.0")

    old.rename(tmp_path / "BioFigure Studio_0.3.0_x64-setup.exe")
    installer = select_installer(tmp_path, "0.3.0")
    assert installer.name == "BioFigure Studio_0.3.0_x64-setup.exe"

    (tmp_path / "another-setup.exe").write_bytes(b"extra")
    with pytest.raises(ValueError, match="Expected only"):
        select_installer(tmp_path, "0.3.0")
