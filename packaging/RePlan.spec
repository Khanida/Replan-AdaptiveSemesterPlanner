from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).resolve().parent.parent
assets = [
    "replanv2.html",
    "replanv2.css",
    "replanv2.js",
    "replanv2-calendar.js",
    "replanv2-engine.js",
    "replanv2-pdf.js",
    "replanv2-auth.js",
    "replan-auth.json",
]
datas = [(str(root / name), ".") for name in assets if (root / name).is_file()]

a = Analysis(
    [str(root / "replanv2_1.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("webview"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RePlan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RePlan",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="RePlan.app",
        bundle_identifier="io.replan.desktop",
        info_plist={"CFBundleName": "RePlan", "CFBundleDisplayName": "RePlan"},
    )
