__version__ = "2.1.0"  # Semantic versioning
__build__ = "2"       # Build number

# build.spec
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.datastruct import Tree, TOC
from PyInstaller.building.osx import BUNDLE


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
    [],
    exclude_binaries=True,
    name='ConsumerPyramidsManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # This should be False for GUI apps
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ConsumerPyramidsManager'
)

# Add BUNDLE for proper macOS app
app = BUNDLE(
    coll,
    name='Consumer Pyramids Manager.app',
    icon='icon.icns',  # Add your .icns file path here if you have one
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSBackgroundOnly': 'False',
        'NSRequiresAquaSystemAppearance': 'False',
        'CFBundleShortVersionString': __version__, 
        'CFBundleVersion': __build__              
    }
)