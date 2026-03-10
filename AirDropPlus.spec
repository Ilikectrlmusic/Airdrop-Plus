# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


def _build_static_datas():
    static_dir = Path('static')
    items = []
    for file_path in static_dir.rglob('*'):
        if not file_path.is_file():
            continue
        if file_path.name.lower() == 'demo.mp4':
            continue
        relative_parent = file_path.relative_to(static_dir).parent
        dest_dir = Path('static') if str(relative_parent) == '.' else Path('static') / relative_parent
        items.append((str(file_path), str(dest_dir)))
    return items


STATIC_DATAS = _build_static_datas()


a = Analysis(
    ['AirDropPlus.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), *STATIC_DATAS],
    hiddenimports=['waitress'],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'numpy.typing', 'numpy._core', 'numpy.linalg', 'numpy.random', 'numpy.f2py'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AirDropPlus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['static\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AirDropPlus',
)
