# RoArm Mission Manager — PyInstaller build spec
#
# Build with:
#   pip install pyinstaller
#   pyinstaller RoArmManager.spec
#
# Output: dist/RoArmManager.exe  (single file, no console window)

from PyInstaller.building.build_main import Analysis, PYZ, EXE

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    # Bundle server.py and index.html so they're available at runtime
    datas=[
        ('server.py',   '.'),
        ('index.html',  '.'),
    ],
    hiddenimports=[
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RoArmManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',   # uncomment and add icon.ico to use a custom icon
)
