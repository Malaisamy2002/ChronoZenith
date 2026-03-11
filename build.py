#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   CHRONO · ZENITH  —  Pure Python APK Builder                   ║
║   No Android Studio · No Gradle · Works Offline after setup     ║
║                                                                  ║
║   Usage:                                                         ║
║     python3 build.py setup     # Download SDK tools (once)      ║
║     python3 build.py build     # Build the APK                  ║
║     python3 build.py install   # Install to connected phone     ║
║     python3 build.py all       # setup + build + install        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, sys, json, shutil, zipfile, hashlib, struct, subprocess
import urllib.request, urllib.error, platform, time, textwrap, stat
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────
APP_NAME        = "Chrono Zenith"
APP_PACKAGE     = "com.chrono.zenith"
APP_VERSION     = "6.0"
APP_VERSION_CODE= 1
MIN_SDK         = 21
TARGET_SDK      = 34
COMPILE_SDK     = 34

# Paths
ROOT     = Path(__file__).parent.resolve()
SDK_DIR  = ROOT / "sdk"
BUILD_DIR= ROOT / "build"
SRC_DIR  = ROOT / "src"
ASSETS   = SRC_DIR / "assets" / "www"
OUT_APK  = ROOT / "ChronoZenith.apk"

# SDK download URLs (command-line tools only — small download ~150MB total)
SYSTEM = platform.system().lower()
SDK_TOOLS_URLS = {
    "linux":   "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip",
    "darwin":  "https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip",
    "windows": "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip",
}
SDK_URL = SDK_TOOLS_URLS.get(SYSTEM, SDK_TOOLS_URLS["linux"])

BUILD_TOOLS_VER = "34.0.0"
PLATFORM_VER    = f"android-{COMPILE_SDK}"

# ─────────────────────────────────────────────────────────────────
# TERMINAL COLORS
# ─────────────────────────────────────────────────────────────────
def col(code): return f"\033[{code}m" if sys.stdout.isatty() else ""
RESET = col(0); BOLD = col(1); DIM = col(2)
RED   = col(31); GREEN = col(32); YELLOW = col(33)
BLUE  = col(34); CYAN  = col(36); WHITE  = col(97)

def banner():
    print(f"""
{BOLD}{WHITE}╔══════════════════════════════════════════════════════╗
║   🕐  CHRONO · ZENITH  —  Python APK Builder         ║
║   No Android Studio · No Gradle · Fully Offline      ║
╚══════════════════════════════════════════════════════╝{RESET}
""")

def step(msg):   print(f"\n{BOLD}{BLUE}▶ {msg}{RESET}")
def ok(msg):     print(f"  {GREEN}✓ {msg}{RESET}")
def warn(msg):   print(f"  {YELLOW}⚠ {msg}{RESET}")
def err(msg):    print(f"  {RED}✗ {msg}{RESET}"); sys.exit(1)
def info(msg):   print(f"  {DIM}{msg}{RESET}")

def progress(done, total, label=""):
    pct = int(done / total * 40) if total else 0
    bar = "█" * pct + "░" * (40 - pct)
    pct2 = int(done / total * 100) if total else 0
    print(f"\r  {CYAN}[{bar}] {pct2:3d}%{RESET} {label}   ", end="", flush=True)

# ─────────────────────────────────────────────────────────────────
# TOOL PATHS (resolved after setup)
# ─────────────────────────────────────────────────────────────────
def sdkmanager_path():
    base = SDK_DIR / "cmdline-tools" / "latest" / "bin"
    name = "sdkmanager.bat" if SYSTEM == "windows" else "sdkmanager"
    return base / name

def aapt2_path():
    return SDK_DIR / "build-tools" / BUILD_TOOLS_VER / ("aapt2.exe" if SYSTEM=="windows" else "aapt2")

def d8_path():
    return SDK_DIR / "build-tools" / BUILD_TOOLS_VER / ("d8.bat" if SYSTEM=="windows" else "d8")

def zipalign_path():
    return SDK_DIR / "build-tools" / BUILD_TOOLS_VER / ("zipalign.exe" if SYSTEM=="windows" else "zipalign")

def apksigner_path():
    return SDK_DIR / "build-tools" / BUILD_TOOLS_VER / ("apksigner.bat" if SYSTEM=="windows" else "apksigner")

def adb_path():
    return SDK_DIR / "platform-tools" / ("adb.exe" if SYSTEM=="windows" else "adb")

def android_jar():
    return SDK_DIR / "platforms" / PLATFORM_VER / "android.jar"

def keystore_path():
    return ROOT / "chrono-release.keystore"

# ─────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────
def run(cmd, cwd=None, capture=False, env=None):
    """Run a shell command, stream output, raise on error."""
    if isinstance(cmd, str):
        cmd = cmd.split()
    e = os.environ.copy()
    e["ANDROID_HOME"]      = str(SDK_DIR)
    e["ANDROID_SDK_ROOT"]  = str(SDK_DIR)
    if env:
        e.update(env)

    cmd = [str(c) for c in cmd]   # ensure all args are strings

    if capture:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e)
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
        return r.stdout.strip()
    else:
        # Always capture output so we can print it on failure
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e)
        if r.stdout.strip():
            print(r.stdout)
        if r.returncode != 0:
            if r.stderr.strip():
                print(r.stderr)
            raise RuntimeError(f"Command failed (exit {r.returncode}): {' '.join(cmd)}")
        return r.returncode

def chmod_x(path):
    """Make a file executable (Unix)."""
    if SYSTEM != "windows":
        p = Path(path)
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

def download(url, dest, label=""):
    """Download with progress bar."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done  = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk: break
                    f.write(chunk)
                    done += len(chunk)
                    progress(done, total, label)
        print()  # newline after progress
    except urllib.error.URLError as e:
        err(f"Download failed: {e}\nNo internet? Run 'python3 build.py setup' with internet first.")

# ─────────────────────────────────────────────────────────────────
# PHASE 1 — SETUP (downloads SDK once, then offline forever)
# ─────────────────────────────────────────────────────────────────
def setup():
    step("PHASE 1: SDK Setup (one-time download ~150MB)")

    # 1a. Check Java
    try:
        ver = run(["java", "-version"], capture=True)
        ok(f"Java found")
    except:
        err("Java not found. Install JDK 17:\n"
            "  Ubuntu/Debian: sudo apt install openjdk-17-jdk\n"
            "  Mac:           brew install openjdk@17\n"
            "  Windows:       https://adoptium.net")

    # 1b. Download command-line tools if not present
    tools_zip = SDK_DIR / "cmdline-tools.zip"
    sdkmgr = sdkmanager_path()

    if not sdkmgr.exists():
        info(f"Downloading Android command-line tools from Google...")
        info(f"URL: {SDK_URL}")
        download(SDK_URL, tools_zip, "SDK tools")
        info("Extracting...")
        extract_dir = SDK_DIR / "cmdline-tools"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tools_zip) as zf:
            zf.extractall(extract_dir)
        # Rename to "latest" as required by sdkmanager
        for item in extract_dir.iterdir():
            if item.is_dir() and item.name != "latest":
                item.rename(extract_dir / "latest")
                break
        tools_zip.unlink(missing_ok=True)
        chmod_x(sdkmgr)
        ok("Command-line tools extracted")
    else:
        ok("Command-line tools already present")

    # 1c. Install SDK packages via sdkmanager
    packages_marker = SDK_DIR / ".packages_installed"
    if not packages_marker.exists():
        info("Installing Android SDK packages (needs internet, ~100MB)...")
        # Accept licenses automatically
        license_input = (b"y\n" * 20)
        proc = subprocess.Popen(
            [str(sdkmgr), "--licenses"],
            stdin=subprocess.PIPE,
            env={**os.environ, "ANDROID_HOME": str(SDK_DIR), "ANDROID_SDK_ROOT": str(SDK_DIR)}
        )
        proc.communicate(input=license_input)

        pkgs = [
            f"build-tools;{BUILD_TOOLS_VER}",
            f"platforms;{PLATFORM_VER}",
            "platform-tools",
        ]
        for pkg in pkgs:
            info(f"Installing {pkg}...")
            run([str(sdkmgr), "--sdk_root=" + str(SDK_DIR), pkg])
            ok(f"Installed {pkg}")

        packages_marker.touch()
        ok("All SDK packages installed")
    else:
        ok("SDK packages already installed")

    # 1d. Generate debug keystore if missing
    if not keystore_path().exists():
        info("Generating debug keystore...")
        run([
            "keytool", "-genkey", "-v",
            "-keystore", str(keystore_path()),
            "-alias", "chrono",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-storepass", "chronozenith",
            "-keypass",   "chronozenith",
            "-dname", "CN=Chrono Zenith, OU=Dev, O=Chrono, L=Earth, S=Universe, C=US",
        ])
        ok("Keystore generated: chrono-release.keystore")
    else:
        ok("Keystore already exists")

    print(f"\n{GREEN}{BOLD}✅ Setup complete! SDK is now offline-ready.{RESET}")
    print(f"   Run {CYAN}python3 build.py build{RESET} to compile the APK.")

# ─────────────────────────────────────────────────────────────────
# PHASE 2 — BUILD (fully offline after setup)
# ─────────────────────────────────────────────────────────────────
def build():
    step("PHASE 2: Building APK (offline)")

    # Validate tools exist
    for tool, path in [("aapt2", aapt2_path()), ("d8", d8_path()),
                       ("zipalign", zipalign_path()), ("apksigner", apksigner_path()),
                       ("android.jar", android_jar())]:
        if not Path(path).exists():
            err(f"{tool} not found at {path}\nRun: python3 build.py setup")
    ok("All build tools found")

    # Clean build dir
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    dirs = {
        "gen":    BUILD_DIR / "gen",
        "obj":    BUILD_DIR / "obj",
        "dex":    BUILD_DIR / "dex",
        "res":    BUILD_DIR / "res_flat",
        "apk_raw":BUILD_DIR / "apk_raw",
    }
    for d in dirs.values():
        d.mkdir(parents=True)

    # ── Step 2a: Generate source files ──────────────────────────
    step("  Generating Java source + resources")
    gen_sources()
    ok("Sources generated")

    # ── Step 2b: Compile resources with aapt2 ───────────────────
    step("  Compiling resources (aapt2)")
    compile_resources(dirs)
    ok("Resources compiled")

    # ── Step 2c: Link APK skeleton ──────────────────────────────
    step("  Linking APK skeleton (aapt2 link)")
    linked_apk = link_resources(dirs)
    ok("APK skeleton linked")

    # ── Step 2d: Compile Java → .class ──────────────────────────
    step("  Compiling Java → .class")
    compile_java(dirs)
    ok("Java compiled")

    # ── Step 2e: Dex .class → classes.dex ──────────────────────
    step("  Dexing classes (d8)")
    dex_classes(dirs)
    ok("DEX generated")

    # ── Step 2f: Assemble final APK ─────────────────────────────
    step("  Assembling APK")
    raw_apk = assemble_apk(dirs, linked_apk)
    ok("APK assembled")

    # ── Step 2g: Zipalign ───────────────────────────────────────
    step("  Zipaligning")
    aligned_apk = BUILD_DIR / "aligned.apk"
    run([str(zipalign_path()), "-v", "-p", "4", str(raw_apk), str(aligned_apk)])
    ok("Zipaligned")

    # ── Step 2h: Sign APK ───────────────────────────────────────
    step("  Signing APK")
    run([
        str(apksigner_path()), "sign",
        "--ks",           str(keystore_path()),
        "--ks-key-alias", "chrono",
        "--ks-pass",      "pass:chronozenith",
        "--key-pass",     "pass:chronozenith",
        "--out",          str(OUT_APK),
        str(aligned_apk),
    ])
    ok(f"APK signed → {OUT_APK.name}")

    # ── Done ────────────────────────────────────────────────────
    size_mb = OUT_APK.stat().st_size / 1024 / 1024
    print(f"\n{GREEN}{BOLD}✅ BUILD SUCCESSFUL!{RESET}")
    print(f"   📦 {CYAN}{OUT_APK}{RESET}  ({size_mb:.2f} MB)")
    print(f"\n   Install:  {YELLOW}python3 build.py install{RESET}")
    print(f"   Or copy APK to phone and tap to install.\n")

# ─────────────────────────────────────────────────────────────────
# SOURCE GENERATION
# ─────────────────────────────────────────────────────────────────
def gen_sources():
    """Write all Java source, manifest, and resource XML files."""

    # ── Java source ─────────────────────────────────────────────
    java_dir = SRC_DIR / "java" / "com" / "chrono" / "zenith"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "MainActivity.java").write_text(MAIN_ACTIVITY_JAVA)

    # ── AndroidManifest.xml ─────────────────────────────────────
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    (SRC_DIR / "AndroidManifest.xml").write_text(ANDROID_MANIFEST)

    # ── Resources ───────────────────────────────────────────────
    res_dir = SRC_DIR / "res"
    (res_dir / "values").mkdir(parents=True, exist_ok=True)
    (res_dir / "values" / "strings.xml").write_text(STRINGS_XML)
    (res_dir / "values" / "styles.xml").write_text(STYLES_XML)
    (res_dir / "values" / "colors.xml").write_text(COLORS_XML)

    # ── App icon (all densities) ─────────────────────────────────
    gen_icons(res_dir)

    # ── Web assets ──────────────────────────────────────────────
    ASSETS.mkdir(parents=True, exist_ok=True)
    html_file = ASSETS / "index.html"
    if not html_file.exists():
        # Try to find it next to this script
        candidates = [
            ROOT / "index.html",
            ROOT / "ChronoV6_Zenith.html",
            ROOT.parent / "ChronoV6_Zenith.html",
        ]
        for c in candidates:
            if c.exists():
                shutil.copy(c, html_file)
                info(f"Copied web app from {c.name}")
                break
        else:
            # Write embedded minimal fallback
            html_file.write_text(FALLBACK_HTML)
            warn("Used embedded fallback HTML — place your index.html in src/assets/www/")

def gen_icons(res_dir):
    """Generate PNG launcher icons using PIL."""
    try:
        from PIL import Image, ImageDraw
        densities = {
            "mipmap-mdpi":    48,
            "mipmap-hdpi":    72,
            "mipmap-xhdpi":   96,
            "mipmap-xxhdpi":  144,
            "mipmap-xxxhdpi": 192,
        }
        for dname, size in densities.items():
            d = res_dir / dname
            d.mkdir(parents=True, exist_ok=True)
            img = _make_icon(size)
            img.save(d / "ic_launcher.png")
            img.save(d / "ic_launcher_round.png")
        ok("Icons generated (all densities)")
    except ImportError:
        warn("PIL not found — using placeholder icons. Install: pip3 install Pillow")
        _write_placeholder_icons(res_dir)

def _make_icon(size):
    from PIL import Image, ImageDraw
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    # 3 orbital rings
    for radius, alpha in [(int(size*.38), 200), (int(size*.26), 140), (int(size*.14), 80)]:
        lw = max(1, size // 56)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            outline=(238, 238, 238, alpha), width=lw
        )
    # Core dot
    dc = max(2, size // 18)
    draw.ellipse([cx-dc, cy-dc, cx+dc, cy+dc], fill=(238, 238, 238, 255))
    # Convert to RGB (PNG without alpha for mipmap)
    bg = Image.new("RGB", (size, size), (0, 0, 0))
    bg.paste(img, mask=img.split()[3])
    return bg

def _write_placeholder_icons(res_dir):
    """Write a tiny valid 1x1 PNG as placeholder."""
    # Minimal valid 1x1 black PNG bytes
    png_1x1 = bytes([
        0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,  # PNG signature
        0x00,0x00,0x00,0x0d,0x49,0x48,0x44,0x52,  # IHDR length + type
        0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,  # width=1 height=1
        0x08,0x02,0x00,0x00,0x00,0x90,0x77,0x53,  # 8-bit RGB
        0xde,0x00,0x00,0x00,0x0c,0x49,0x44,0x41,  # IDAT
        0x54,0x08,0xd7,0x63,0x60,0x60,0x60,0x00,
        0x00,0x00,0x04,0x00,0x01,0x27,0x07,0x17,
        0x9c,0x00,0x00,0x00,0x00,0x49,0x45,0x4e,  # IEND
        0x44,0xae,0x42,0x60,0x82
    ])
    for dname in ["mipmap-mdpi","mipmap-hdpi","mipmap-xhdpi","mipmap-xxhdpi","mipmap-xxxhdpi"]:
        d = res_dir / dname
        d.mkdir(parents=True, exist_ok=True)
        (d / "ic_launcher.png").write_bytes(png_1x1)
        (d / "ic_launcher_round.png").write_bytes(png_1x1)

# ─────────────────────────────────────────────────────────────────
# COMPILE RESOURCES
# ─────────────────────────────────────────────────────────────────
def compile_resources(dirs):
    """Compile all res/ files with aapt2 compile."""
    res_dir  = SRC_DIR / "res"
    flat_dir = dirs["res"]
    count    = 0

    for resfile in res_dir.rglob("*"):
        if not resfile.is_file():
            continue
        if resfile.name.startswith("."):
            continue
        # aapt2 compile each resource file individually → produces .flat output
        try:
            run([
                str(aapt2_path()), "compile",
                str(resfile),
                "-o", str(flat_dir),
            ])
            count += 1
        except RuntimeError as e:
            warn(f"Skipping {resfile.name}: {e}")

    if count == 0:
        err("aapt2 compiled 0 resource files — check res/ directory.")
    info(f"Compiled {count} resource files → {flat_dir}")

def link_resources(dirs):
    """Link compiled resources into an APK skeleton with aapt2 link."""
    flat_dir  = dirs["res"]
    apk_skel  = BUILD_DIR / "skeleton.apk"
    gen_dir   = dirs["gen"]

    # aapt2 --java needs the package directory to already exist
    java_pkg_dir = gen_dir / "com" / "chrono" / "zenith"
    java_pkg_dir.mkdir(parents=True, exist_ok=True)

    # Collect all .flat files
    flat_files = list(flat_dir.glob("*.flat"))
    if not flat_files:
        err("No compiled resource files found.")

    info(f"Linking {len(flat_files)} resource files...")

    # NOTE: No --proto-format here — that's only for bundletool/AAB workflow.
    # Standard APK link uses plain zip format.
    cmd = [
        str(aapt2_path()), "link",
        "-o", str(apk_skel),
        "-I", str(android_jar()),
        "--manifest",            str(SRC_DIR / "AndroidManifest.xml"),
        "--java",                str(gen_dir),
        "--min-sdk-version",     str(MIN_SDK),
        "--target-sdk-version",  str(TARGET_SDK),
        "--version-code",        str(APP_VERSION_CODE),
        "--version-name",        APP_VERSION,
        "--auto-add-overlay",
    ]
    for f in flat_files:
        cmd += ["-R", str(f)]

    run(cmd)

    # Verify R.java was generated
    r_files = list(gen_dir.rglob("R.java"))
    if not r_files:
        err("R.java was not generated by aapt2 link — check manifest package name.")
    info(f"R.java generated: {r_files[0]}")

    return apk_skel

# ─────────────────────────────────────────────────────────────────
# COMPILE JAVA
# ─────────────────────────────────────────────────────────────────
def compile_java(dirs):
    """Compile Java sources to .class files using javac."""
    gen_dir  = dirs["gen"]
    obj_dir  = dirs["obj"]

    # Collect all Java files: src + generated R.java
    java_files = (
        list((SRC_DIR / "java").rglob("*.java")) +
        list(gen_dir.rglob("*.java"))
    )
    if not java_files:
        err("No Java source files found.")

    info(f"Compiling {len(java_files)} Java file(s)...")

    # Use --release 8 for modern JDK (replaces deprecated -source/-target)
    # Falls back to -source/-target for older JDK
    base_cmd = [
        "javac",
        "--release", "8",
        "-cp",  str(android_jar()),
        "-d",   str(obj_dir),
    ]
    try:
        run(base_cmd + [str(f) for f in java_files])
    except RuntimeError:
        # Fallback for JDK < 9
        info("Retrying with legacy -source/-target flags...")
        run([
            "javac",
            "-source", "1.8", "-target", "1.8",
            "-cp",    str(android_jar()),
            "-d",     str(obj_dir),
            *[str(f) for f in java_files],
        ])

# ─────────────────────────────────────────────────────────────────
# DEX
# ─────────────────────────────────────────────────────────────────
def dex_classes(dirs):
    """Convert .class files to DEX using d8."""
    obj_dir  = dirs["obj"]
    dex_dir  = dirs["dex"]

    class_files = list(obj_dir.rglob("*.class"))
    if not class_files:
        err("No .class files found to dex.")

    info(f"Dexing {len(class_files)} class file(s)...")
    run([
        str(d8_path()),
        "--min-api", str(MIN_SDK),
        "--output",  str(dex_dir),
        *[str(f) for f in class_files],
    ])

# ─────────────────────────────────────────────────────────────────
# ASSEMBLE APK
# ─────────────────────────────────────────────────────────────────
def assemble_apk(dirs, linked_apk):
    """Merge skeleton APK + dex + assets into final unaligned APK."""
    dex_dir   = dirs["dex"]
    raw_apk   = BUILD_DIR / "unaligned.apk"

    # The linked skeleton already contains resources.arsc + AndroidManifest.xml
    # We need to ADD dex + assets into it.
    # Copy skeleton first, then append new entries.
    shutil.copy(linked_apk, raw_apk)

    # Collect existing entries so we don't duplicate
    existing = set()
    with zipfile.ZipFile(raw_apk, "r") as zf:
        existing = set(zf.namelist())
    info(f"Skeleton contains {len(existing)} entries: {sorted(existing)[:5]}...")

    with zipfile.ZipFile(raw_apk, "a", compression=zipfile.ZIP_DEFLATED,
                         allowZip64=True) as zf:

        # Add classes.dex — STORED (uncompressed) for faster loading on device
        dex_file = dex_dir / "classes.dex"
        if not dex_file.exists():
            err(f"classes.dex not found at {dex_file}")
        if "classes.dex" not in existing:
            zf.write(dex_file, "classes.dex", compress_type=zipfile.ZIP_STORED)
            info(f"Added classes.dex ({dex_file.stat().st_size:,} bytes)")

        # Add web assets — STORED (no compression for HTML/JS — faster access)
        assets_root = SRC_DIR / "assets"
        for asset in assets_root.rglob("*"):
            if asset.is_file():
                arc = "assets/" + asset.relative_to(assets_root).as_posix()
                if arc not in existing:
                    zf.write(asset, arc, compress_type=zipfile.ZIP_STORED)
                    info(f"Added {arc} ({asset.stat().st_size:,} bytes)")
                else:
                    info(f"Skipped duplicate: {arc}")

    return raw_apk

# ─────────────────────────────────────────────────────────────────
# INSTALL
# ─────────────────────────────────────────────────────────────────
def install():
    step("Installing APK on connected device")
    if not OUT_APK.exists():
        err(f"APK not found: {OUT_APK}\nRun: python3 build.py build")
    adb = adb_path()
    if not adb.exists():
        err("adb not found. Run: python3 build.py setup")

    # Check devices
    devices = run([str(adb), "devices"], capture=True)
    lines = [l for l in devices.splitlines() if "\tdevice" in l]
    if not lines:
        err("No Android device connected.\n"
            "Connect via USB with USB Debugging ON, or use WiFi ADB:\n"
            "  adb pair <ip>:<port>   → then:\n"
            "  adb connect <ip>:<port>")

    ok(f"Found {len(lines)} device(s)")
    run([str(adb), "install", "-r", str(OUT_APK)])
    ok(f"✅ {APP_NAME} installed successfully!")
    info("Check your launcher — look for 'Chrono · Zenith'")

# ─────────────────────────────────────────────────────────────────
# EMBEDDED SOURCE FILES
# ─────────────────────────────────────────────────────────────────
MAIN_ACTIVITY_JAVA = '''\
package com.chrono.zenith;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private WebView webView;

    @SuppressLint({"SetJavaScriptEnabled","NewApi"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
            getWindow().setDecorFitsSystemWindows(false);

        webView = new WebView(this);
        setContentView(webView);
        hideSystemUI();

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1)
            s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setRenderPriority(WebSettings.RenderPriority.HIGH);
        s.setCacheMode(WebSettings.LOAD_CACHE_ELSE_NETWORK);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) { return false; }
        });
        webView.setWebChromeClient(new WebChromeClient());
        webView.setBackgroundColor(0xFF000000);
        webView.loadUrl("file:///android_asset/www/index.html");
    }

    @Override public void onWindowFocusChanged(boolean h) { super.onWindowFocusChanged(h); if(h) hideSystemUI(); }

    private void hideSystemUI() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT)
            webView.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|
                View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    @Override protected void onResume()  { super.onResume();  webView.onResume();  webView.resumeTimers(); }
    @Override protected void onPause()   { super.onPause();   webView.onPause();   webView.pauseTimers(); }
    @Override public    void onBackPressed() {}
    @Override protected void onDestroy() { if(webView!=null){webView.stopLoading();webView.destroy();} super.onDestroy(); }
}
'''

ANDROID_MANIFEST = f'''\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{APP_PACKAGE}">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.VIBRATE"/>
    <uses-permission android:name="android.permission.WAKE_LOCK"/>
    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:theme="@style/AppTheme"
        android:hardwareAccelerated="true"
        android:supportsRtl="true">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden|screenLayout|uiMode"
            android:screenOrientation="sensor"
            android:windowSoftInputMode="adjustPan"
            android:launchMode="singleTop">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
'''

STRINGS_XML = '''\
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Chrono · Zenith</string>
</resources>
'''

STYLES_XML = '''\
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:Theme.Material.NoActionBar">
        <item name="android:windowBackground">@android:color/black</item>
        <item name="android:windowFullscreen">true</item>
        <item name="android:windowNoTitle">true</item>
        <item name="android:windowContentOverlay">@null</item>
        <item name="android:windowIsTranslucent">false</item>
        <item name="android:windowAnimationStyle">@null</item>
        <item name="android:statusBarColor">@android:color/black</item>
        <item name="android:navigationBarColor">@android:color/black</item>
    </style>
</resources>
'''

COLORS_XML = '''\
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="black">#000000</color>
    <color name="white">#FFFFFF</color>
</resources>
'''

FALLBACK_HTML = '''\
<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Chrono · Zenith</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#eee;font-family:monospace;
     display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;}
h1{font-size:2em;letter-spacing:.15em;margin-bottom:.5em}
p{color:#555;font-size:.8em;letter-spacing:.1em}
</style></head>
<body>
<div>
  <h1>CHRONO · ZENITH</h1>
  <p>Place your index.html in src/assets/www/</p>
</div>
</body></html>
'''

# ─────────────────────────────────────────────────────────────────
# GITHUB ACTIONS CI WORKFLOW GENERATOR
# ─────────────────────────────────────────────────────────────────
def gen_workflow():
    """Generate .github/workflows/build.yml for automatic CI builds."""
    step("Generating GitHub Actions workflow")
    wf_dir = ROOT / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)

    workflow = """\
name: Build Chrono Zenith APK

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]
  workflow_dispatch:   # Manual trigger from GitHub UI

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Pillow (for icon generation)
        run: pip install Pillow

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Setup Android SDK + Build APK
        run: python3 build.py setup build
        env:
          ANDROID_HOME: ${{ github.workspace }}/sdk

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: ChronoZenith-debug
          path: ChronoZenith.apk
          retention-days: 30

      - name: Create Release (on tag push)
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v1
        with:
          files: ChronoZenith.apk
          name: Chrono Zenith ${{ github.ref_name }}
          body: |
            ## 🕐 Chrono · Zenith ${{ github.ref_name }}
            Luxurious Pomodoro focus timer with 6 animated clock faces.
            ### Install
            Download `ChronoZenith.apk` and install on your Android device.
"""
    (wf_dir / "build.yml").write_text(workflow)
    ok(f"Workflow written → .github/workflows/build.yml")

    # Also write a .gitignore
    gitignore = """\
# Build outputs
build/
*.apk
*.aab

# SDK (too large for git — downloaded by build.py setup)
sdk/

# Python cache
__pycache__/
*.pyc
*.pyo

# OS
.DS_Store
Thumbs.db

# Keystore (keep private — or commit if it's just a debug key)
# chrono-release.keystore
"""
    (ROOT / ".gitignore").write_text(gitignore)
    ok(".gitignore written")

    print(f"""
{GREEN}{BOLD}GitHub Actions Setup Complete!{RESET}

{BOLD}Every git push to main will:{RESET}
  1. Spin up Ubuntu runner (free)
  2. Run python3 build.py setup build
  3. Upload ChronoZenith.apk as a downloadable artifact

{BOLD}To download your APK from GitHub:{RESET}
  GitHub repo → Actions tab → latest run → Artifacts → ChronoZenith-debug

{BOLD}To create a release with the APK attached:{RESET}
  {CYAN}git tag v1.0 && git push origin v1.0{RESET}
""")

# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
COMMANDS = {
    "setup":    (setup,        "Download Android SDK tools (one-time, needs internet)"),
    "build":    (build,        "Build the APK (offline after setup)"),
    "install":  (install,      "Install APK to connected Android device"),
    "workflow": (gen_workflow,  "Generate GitHub Actions CI workflow"),
    "all":      (None,         "Run setup + build + install"),
}

def main():
    banner()
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"{BOLD}Usage:{RESET}  python3 build.py <command>\n")
        print(f"{BOLD}Commands:{RESET}")
        for cmd, (fn, desc) in COMMANDS.items():
            print(f"  {CYAN}{cmd:<12}{RESET} {desc}")
        print(f"""
{BOLD}Quick Start:{RESET}
  {YELLOW}python3 build.py setup{RESET}      ← Run once (needs internet, ~150MB)
  {YELLOW}python3 build.py build{RESET}      ← Build APK (offline)
  {YELLOW}python3 build.py install{RESET}    ← Push to phone via USB/WiFi
  {YELLOW}python3 build.py workflow{RESET}   ← Generate GitHub Actions CI

{BOLD}Or all at once:{RESET}
  {YELLOW}python3 build.py all{RESET}
""")
        sys.exit(0)

    cmd = sys.argv[1]
    t0  = time.time()

    if cmd == "all":
        setup(); build(); install()
    elif cmd == "setup build":
        setup(); build()
    else:
        COMMANDS[cmd][0]()

    elapsed = time.time() - t0
    print(f"\n{DIM}Completed in {elapsed:.1f}s{RESET}\n")

if __name__ == "__main__":
    main()
