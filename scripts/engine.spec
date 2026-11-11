# Build with the existing Python environment plus reviewed packaging tools.
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent
fiji_scripts = [(str(path), 'scripts') for path in sorted((root / 'scripts').glob('fiji_*.groovy'))]
# Project exports record these installed versions through importlib.metadata.
project_metadata = copy_metadata('matplotlib') + copy_metadata('pandas')
a = Analysis([str(root / 'scripts/engine_entry.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root / 'apps/web/dist'), 'apps/web/dist'), (str(root / 'assets/fonts'), 'assets/fonts'),
                        (str(root / 'docs/FIJI_COMMAND_INVENTORY.json'), 'docs'), *fiji_scripts, *project_metadata],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
                   'uvicorn.lifespan.off', 'openpyxl',
                   'matplotlib.backends.backend_svg', 'matplotlib.backends.backend_pdf',
                   'anndata', 'h5py', 'scipy', 'scipy.sparse', 'zarr', 'numcodecs',
                   'Bio', 'Bio.SeqIO', 'pycirclize', 'dna_features_viewer'],
    hookspath=[], hooksconfig={'matplotlib': {'backends': ['Agg']}},
    excludes=['tkinter', 'pytest', 'IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='biofigure-engine',
          console=True, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='biofigure-engine')
