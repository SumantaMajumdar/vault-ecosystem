# Vault Ecosystem: Server & Android Companion

A lightweight, zero-overhead home media & automation suite designed for Linux servers (Gentoo/Debian/Arch) and Android devices.

---

## 🌟 Key Features

### 1. 🎵 Vault Jukebox (Server + Web UI)
- **Zero Idle CPU:** Automatically spawns `mpv` with hardware acceleration when audio is queued, and terminates it into complete idle when playback stops.
- **Single Synchronized Queue:** Allows multiple phones, tablets, and laptops on the local network to view, reorder, seek, and add songs concurrently.
- **Safety Clamping:** Volume defaults to 30% and is strictly capped at 80% to protect speakers from runaway volume.
- **Real-Time Web UI:** Glassmorphism dashboard with adaptive polling (1s during playback, 3.5s idle, 10s background).

### 2. 📱 Vault Companion (Android App & Widget)
- **Share to Queue:** Direct integration into the Android Share Sheet. Tap *Share* on any YouTube video, browser link, or search query to queue it on the server.
- **Magnet Link Handler:** Catches magnet links (`magnet:?xt=...`) from web browsers and passes them to the server's torrent client.
- **Home Screen Widget:** Real-time track display with direct touch controls (Play/Pause, Next Track, Volume Up, Volume Down).
- **Configurable Server IP:** Easily change the local server IP at any time without reinstalling or rebuilding the app.
- **NAS Shortcut:** One-click launcher to open your server's SMB shares in your preferred Android file manager (CX File Explorer, Solid Explorer, etc.).

---

## 📂 Repository Structure

```
├── android/
│   ├── VaultCompanion.apk          # Pre-built, signed APK ready to install
│   └── app/
│       ├── AndroidManifest.xml     # Permissions, activities, widget receivers
│       ├── build.ps1               # Automated standalone build & sign script
│       ├── res/                    # Layouts, widget XML, icons
│       └── src/                    # Java source code
└── server/
    └── ytqueue/
        ├── index.html              # Modern, responsive Web Jukebox UI
        ├── server.py               # Lightweight Python HTTP & mpv IPC server
        └── ytqueue.openrc          # OpenRC service file for Gentoo / Alpine
```

---

## 🚀 Server Setup

### Requirements
- Python 3.8+
- `mpv` (`sudo emerge media-video/mpv` on Gentoo or `sudo apt install mpv` on Debian/Ubuntu)
- `yt-dlp` (`pip install yt-dlp` or package manager)

### Starting the Server
```bash
python3 server/ytqueue/server.py
```
By default, the server listens on port `8085`. Access the dashboard at `http://<SERVER_IP>:8085`.

### Running as an OpenRC Service (Gentoo)
1. Copy `server/ytqueue/ytqueue.openrc` to `/etc/init.d/ytqueue`.
2. Make it executable:
   ```bash
   chmod +x /etc/init.d/ytqueue
   ```
3. Start and enable on boot:
   ```bash
   rc-service ytqueue start
   rc-update add ytqueue default
   ```

---

## 📲 Android Companion Installation

### Quick Install (Pre-built APK)
Install via ADB or transfer `android/VaultCompanion.apk` to your phone or tablet:
```bash
adb install -r android/VaultCompanion.apk
```

### Building from Source
Run the provided PowerShell build script:
```powershell
cd android/app
.\build.ps1
```

---

## 🔒 Privacy & Security
- No telemetry, analytics, or external trackers.
- All requests stay strictly on your local home network (LAN).
- Server IP is stored locally in Android's `SharedPreferences`.

## 📜 License
MIT License. Free to use, modify, and distribute.
