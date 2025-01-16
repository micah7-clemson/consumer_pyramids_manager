__version__ = "2.1.2"  # Semantic versioning
__build__ = "3"       # Build number

# build.spec
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.datastruct import Tree, TOC

a = Analysis(
    ['cpm.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),
        ('pyramid_ids.csv', '.'),
        ('pyramid_variables.yaml', '.')
    ],
    hiddenimports=[
        'pandas',
        'numpy',
        'yaml',
        'tkinter',
        'pyarrow',
        'pyarrow.parquet',
        'pandas.core.api',
        'pandas.core.frame',
        'pandas.core.series',
        'pandas.io.parsers'
    ],
    excludes=[
        'matplotlib',
        'scipy',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'IPython',
        'notebook',
        'jupyter',
        'pytest',
        'nose'
    ],
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Consumer Pyramids Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # False for GUI apps
    icon='icon.ico',  # Change to .ico for Windows
    version=f'{__version__}.{__build__}'
)
