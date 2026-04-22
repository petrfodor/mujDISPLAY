# 🖥️ mujDISPLAY Monitor

**mujDISPLAY Monitor** is a sophisticated Windows hardware-monitoring solution that utilizes external **TJC (TaoJingChi)** or **Nextion** intelligent touch panels to visualize system statistics, weather data, and media controls in real-time.

Designed for power users and workstations, it provides a dedicated hardware dashboard, freeing up your main monitors for work and gaming.

---

## ✨ Key Features

* **📊 Real-Time System Monitoring**: Track CPU load, RAM usage, disk space, and network traffic (Auto-scaling bandwidth graphs).
* **📈 Dynamic Waveform Graphs (v1.5)**: High-resolution full-screen history graphs with automatic color shifting (Green 🟢 → Yellow 🟡 → Orange 🟠 → Red 🔴) based on load levels.
* **🎵 Media Control Center**: Full integration with Windows Media (Spotify, YouTube, VLC, etc.) showing Artist, Title, Progress, and Playback Status. Supports bi-directional control from the touch screen.
* **☁️ Intelligent Weather Station**: Automated geolocation via IP-API and detailed forecasts (Temp, Humidity, Wind, UV Index) via Open-Meteo.
* **📧 Email & Calendar Integration**: Live counters for Outlook/Thunderbird unread messages and upcoming calendar events.
* **🔄 Automatic HMI Updates**: Remote version check and one-click firmware flashing (`.tft` files) directly from the application.

---

## 🛠️ Technical Specifications

* **Platform**: Windows 10/11
* **Language**: Python 3.12+
* **Communication**: Serial (UART) over USB (CH340, CP2102, FTDI, etc.).
* **Supported Hardware**: TJC (USART HMI) and Nextion Smart Displays.
* **Core Libraries**: `psutil`, `pyserial`, `winsdk`, `requests`, `pyautogui`, `pystray`.

---

## 📦 Compilation to Executable (.exe)

For distribution or clean background operation, you can compile the script into a single standalone executable using **PyInstaller**. This ensures the application runs without a console window and includes all necessary assets.

### **Build Command**
Run the following command in your terminal from the project directory to create a professional build:

```powershell
pyinstaller --noconsole --onefile --collect-all plyer --version-file="file_version_info.txt" --add-data "logo.png;." --icon=logo.ico mujdisplay_Monitor.py
Command Breakdown:
--noconsole: Suppresses the command prompt window.
--onefile: Bundles everything into a single .exe file.
--collect-all plyer: Ensures notification dependencies are correctly packaged.
--version-file: Attaches metadata (Version, Author, Copyright) to the EXE file properties.
--add-data "logo.png;.": Embeds the tray icon image directly into the executable.
--icon=logo.ico: Sets the official application icon for the file and taskbar.

🚀 Installation & Setup
Connect Hardware: Plugin your TJC/Nextion panel via a USB-to-TTL adapter.
Install Dependencies:
Bash
pip install psutil pyserial winsdk requests pyautogui pystray Pillow plyer pywin32
Run:
Bash
python mujdisplay_Monitor.py
⚙️ Configuration
On first run, the app generates a config.ini. Key settings include:
Port: Set to Auto or a specific COM port.
BaudRate: Default 9600 for data, up to 921600 for flashing.
EmailClient: Toggle between Outlook, Thunderbird, or None.
Brightness: Default display intensity (0-100).

📝 Changelog
v1.6 (2026-04-22)
ADDED: Full-screen "Graph Mode" using Waveform component (ID 3).
ADDED: Dynamic color management (pco0) for graph channels based on system stress.
ADDED: Smart graph clearing (cle 3,255) when entering the graph page.
IMPROVED: Adaptive Media Icons (Play/Pause/Stop) based on playback feedback.
FIXED: Variable initialization to prevent local variable referenced before assignment errors.
FIXED: AppID synchronization for stable Windows Taskbar icon grouping.

Author: Petr Fodor, Controlsystems.cz
Version: v1.5 (2026-04-21)
License: MIT 
