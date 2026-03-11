# 🕐 Chrono · Zenith — Python APK Builder

> A luxurious Pomodoro focus timer with 6 animated clock faces, sound effects, and haptics.  
> Built with **pure Python** — no Android Studio, no Gradle, works fully offline after one-time setup.

---

## ⚡ GitHub Actions — Zero Setup Build

Every push to `main` automatically builds the APK on GitHub's servers.

**To get your APK:**
1. Push any change to `main`
2. Go to **Actions** tab on GitHub
3. Click the latest run → **Artifacts** → **ChronoZenith-APK**
4. Download and install on your phone

**To publish a release:**
```bash
git tag v1.0
git push origin v1.0
```
GitHub will create a release with the APK attached automatically.

---

## 🏠 Build Locally (Offline After Setup)

### Requirements
- Python 3.8+
- Java JDK 17+
- Internet (first time only)

### Install Java
```bash
# Ubuntu / Debian
sudo apt install openjdk-17-jdk

# macOS
brew install openjdk@17

# Windows — download from https://adoptium.net
```

### Install Python dependency
```bash
pip install Pillow
```

### One-time setup (downloads ~150MB Android SDK)
```bash
python3 build.py setup
```

### Build the APK (fully offline)
```bash
python3 build.py build
```
→ Outputs: `ChronoZenith.apk`

### Install to phone
```bash
# USB (enable USB Debugging on phone first)
python3 build.py install

# Or copy ChronoZenith.apk to phone and tap to install
```

### All in one
```bash
python3 build.py all
```

---

## 📂 Project Structure

```
ChronoZenithPy/
├── build.py                     ← The entire build system (one file)
├── src/
│   └── assets/
│       └── www/
│           └── index.html       ← The full web app (clock + timer)
├── .github/
│   └── workflows/
│       └── build.yml            ← GitHub Actions CI (auto-build on push)
├── .gitignore
└── README.md

# Generated on first run (not committed):
├── sdk/                         ← Android SDK (downloaded by setup)
├── build/                       ← Intermediate build files
├── chrono-release.keystore      ← Debug signing key (auto-generated)
└── ChronoZenith.apk             ← Final output
```

---

## 🔧 Commands

| Command | Description |
|---|---|
| `python3 build.py setup` | Download Android SDK (once, needs internet) |
| `python3 build.py build` | Compile + package APK (offline) |
| `python3 build.py install` | Push APK to connected phone via ADB |
| `python3 build.py workflow` | Re-generate GitHub Actions workflow |
| `python3 build.py all` | setup + build + install |

---

## 📱 App Features

- **6 animated clock faces** — Orbit, Pendulum, Sigil, Terminal, Vapor, Nocturne
- **Pomodoro focus timer** — 25 min focus / 5 min short break / 15 min long break
- **Web Audio sound engine** — Synthesized sounds, no audio files needed
  - Soft tick, play whoosh, pause tone, done chime (C–E–G)
- **Haptic feedback** — Vibration patterns on every button
- **Constellation canvas** — Slow-drifting star field with connection lines
- **Immersive fullscreen** — System bars hidden, screen kept on during sessions
- **Portrait + Landscape** — Full cinematic 3D view transitions
- **Works offline** — All assets bundled, no internet needed after install

---

## 🔄 How the Build Works

```
Python build.py
     │
     ├── setup ──→ Download cmdline-tools zip from Google
     │              sdkmanager install build-tools + platform + adb
     │              keytool → generate signing keystore
     │
     └── build ──→ gen_sources()     Write Java + XML + icons
                   aapt2 compile     Compile res/ → .flat files  
                   aapt2 link        Link skeleton APK + generate R.java
                   javac             Compile Java → .class
                   d8                DEX .class → classes.dex
                   zipfile           Merge skeleton + dex + assets
                   zipalign          Align ZIP entries to 4-byte boundary
                   apksigner         Sign with keystore
                        │
                        └──→ ChronoZenith.apk ✅
```

---

## 📲 Install APK on Phone (without USB)

1. Upload `ChronoZenith.apk` to Google Drive
2. Open Drive on your phone → tap the file
3. Tap **Download** → tap the notification
4. Allow "Install from unknown sources" if prompted
5. Tap **Install** → **Open**

---

## App Info
- Package: `com.chrono.zenith`  
- Min Android: 5.0 (API 21)  
- Target Android: 14 (API 34)  
- Size: ~1–2 MB
