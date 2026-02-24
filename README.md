# AirDrop Plus

## [中文](README.zh-CN.md)

AirDrop Plus is a Windows tray app plus an iOS Shortcuts workflow for transferring clipboard text, images, and files between iPhone and Windows.

## Highlights

- Uses a generated 6-character `device_id` (`a-z`, `0-9`) instead of the Windows computer name.
- Supports mDNS host format: `http://<device_id>.local:<port>` (Bonjour required on Windows).
- Includes a first-run guide (QR install, device code setup, startup and save-path setup).
- iOS text uploads are converted to plain text and written directly to the Windows clipboard (instead of saving `.txt` / `.rtf` files).
- Bilingual UI (English / Chinese), including tray menu, guide, settings, and notifications.

## iOS Shortcuts

- Link: https://www.icloud.com/shortcuts/87c14547b1de4195b903ce1d18495c2f

![Shortcut QR](static/QR_code_en.PNG)

## Guide Assets (from `static/`)

![Device ID Setup](static/DeviceID_en.GIF)
![Home Screen Setup](static/Home_screen_en.GIF)
![Double Tap Setup](static/Double_tap_en.GIF)

## Requirements

- Windows 10/11
- Python 3.10+
- Bonjour Print Services for Windows (for `.local` host discovery)

## Run From Source

```powershell
pip install -r requirements.txt
python AirDropPlus.py
```

## Configuration

Edit `config/config.ini`:

- `key`: shared secret with your iOS shortcut.
- `port`: HTTP port used by the local server.
- `save_path`: received file folder (empty means `%USERPROFILE%\Downloads`).
- `device_id`: 6-char device code, auto-generated on first run.
- `auto_start`: launch on Windows startup (`1` or `0`).
- `startup_notify`: show startup notification (`1` or `0`).
- `basic_notifier`: switch notifier implementation (`0` modern / `1` basic).
- `language`: `en` or `zh` (auto-initialized on first run).

## API Summary

Headers required for most endpoints:

- `Authorization`: must match `config.key`
- `ShortcutVersion`: major/minor must match app version

Endpoints:

- `GET /device/info`
- `POST /file/send/list`
- `POST /file/send`
- `POST /file/receive`
- `GET /clipboard/receive`
- `POST /clipboard/send`

## Build


Build executable with PyInstaller:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -CleanOutput
```

Output folder:

- `dist\AirDropPlus`

If you need an MSI/bootstrapper workflow, build it locally with your own WiX/Burn setup.

## License

MIT. See `LICENSE`.
