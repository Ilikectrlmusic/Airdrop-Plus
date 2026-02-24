# AirDrop Plus

## [English](README.md)

AirDrop Plus 是一个 Windows 托盘程序 + iOS 快捷指令方案，用于在 iPhone 与 Windows 之间传输剪贴板文本、图片和文件。

## 功能特点

- 使用自动生成的 6 位 `device_id`（小写字母+数字）作为设备识别码，不再依赖 Windows 设备名称。
- 支持 mDNS 地址：`http://<device_id>.local:<port>`（Windows 端需要 Bonjour）。
- 首次运行提供引导页（扫码安装、填写设备码、开机自启动和保存路径设置）。
- 手机发送文本时会直接写入 Windows 剪贴板，不再落地为 `.txt` / `.rtf` 文件。
- 支持中英文界面（托盘菜单、引导页、设置页、通知）。

## 快捷指令


- 链接：https://www.icloud.com/shortcuts/e3b3e7d39ee84a49892f8de547a943f2

![快捷指令二维码](static/QR_code.PNG)


## 引导页素材（来自 `static/`）

![设备码设置](static/DeviceID.GIF)
![添加到主屏幕](static/Home_screen.GIF)
![双击背面设置](static/Double_tap.GIF)

## 运行环境

- Windows 10/11
- Python 3.10+
- Bonjour Print Services for Windows（用于 `.local` 主机名发现）

## 源码运行

```powershell
pip install -r requirements.txt
python AirDropPlus.py
```

## 配置说明

编辑 `config/config.ini`：

- `key`：与快捷指令一致的密钥。
- `port`：本地 HTTP 服务端口。
- `save_path`：接收文件保存目录（留空为 `%USERPROFILE%\Downloads`）。
- `device_id`：6 位设备码，首次运行自动生成。
- `auto_start`：开机启动（`1` 或 `0`）。
- `startup_notify`：是否显示启动通知（`1` 或 `0`）。
- `basic_notifier`：通知实现切换（`0` 现代通知 / `1` 基础通知）。
- `language`：`zh` 或 `en`（首次运行自动初始化）。

## API 概览

大部分接口需要请求头：

- `Authorization`：必须等于 `config.key`
- `ShortcutVersion`：主次版本号需与程序匹配

接口列表：

- `GET /device/info`
- `POST /file/send/list`
- `POST /file/send`
- `POST /file/receive`
- `GET /clipboard/receive`
- `POST /clipboard/send`

## 打包说明


使用 PyInstaller 打包可执行文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -CleanOutput
```

输出目录：

- `dist\AirDropPlus`

如需 MSI / 引导安装器，请在本地使用你自己的 WiX/Burn 方案构建。

## 许可证

MIT，见 `LICENSE`。
