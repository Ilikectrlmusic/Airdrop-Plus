# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['AirDropPlus.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), ('static', 'static')],
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
