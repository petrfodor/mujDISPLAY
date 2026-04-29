# 🖥️ mujDISPLAY Monitor (v2.1)

**mujDISPLAY Monitor** is a sophisticated Windows hardware-monitoring solution that utilizes external **TJC (TaoJingChi)** or **Nextion** intelligent touch panels to visualize system statistics, weather data, and media controls in real-time.

Designed for power users and workstations, it provides a dedicated hardware dashboard, freeing up your main monitors for work and gaming.

---

## ✨ Key Features

* 📊 **Real-Time System Monitoring:** Track CPU load, RAM usage, disk space, and network traffic.
* 📈 **Dynamic Waveform Graphs:** High-resolution history graphs for CPU and RAM with automatic color shifting (🟢 → 🟡 → 🟠 → 🔴) based on system stress.
* 🎵 **Advanced Media Engine:** Full integration with Windows Media (Spotify, YouTube, VLC, etc.) showing Artist, Title, and Progress. Features bi-directional touch control (Play/Pause, Skip, Volume).
* ☁️ **Intelligent Weather Station:** Automated geolocation via IP-API and detailed forecasts (Temp, Humidity, Wind, UV Index) via Open-Meteo API.
* 📅 **International Name Days:** Real-time display of "who has a name day today" based on the application's language (supports CZ, SK, EN, DE, FR).
* 📧 **Smart Office Integration:** Live counters for **Outlook** (Unread emails, **Calendar events**, and **Tasks**) or Thunderbird.
* 📅 **Calendar Planner:** Displays the next upcoming meeting time and subject directly on the screen.
* 🔄 **Smart HMI Update:** Automatic detection of HW model (T135 vs T035) and version comparison. Downloads and flashes the correct `.tft` firmware directly from the server.
* 🌐 **Multi-language UI:** Fully localized interface and display outputs (CZ, SK, EN, DE, FR).

---

## 🛠️ Technical Specifications

* **Platform:** Windows 10/11
* **Architecture:** Modular Multi-threaded Python core
* **Language:** Python 3.12+
* **Communication:** Serial (UART) over USB (CH340, CP2102, FTDI, etc.)
* **Protocols:** Support for standard ASCII instructions and **Binary 0x71** data parsing.
* **Baud Rates:** 9600 (Data) / up to 921600 (Firmware Upload)
* **Supported Hardware:** TJC (USART HMI) and Nextion Smart Displays.

---

## 📦 Compilation to Executable (.exe)

For professional background operation, the application can be compiled into a standalone executable.

### Build Command
Run the following command to create a bundled executable including all assets:

```powershell
pyinstaller --noconsole --onefile --collect-all plyer --version-file="file_version_info.txt" --add-data "logo.png;." --add-data "lang;lang" --icon=logo.ico main.py
Key Parameters:

--noconsole: Suppresses the background terminal.

--add-data "lang;lang": Bundles all JSON localization files.

--collect-all plyer: Packages notification system dependencies.

🚀 Installation & Setup
Connect Hardware: Plug in your TJC/Nextion panel via a USB-to-TTL adapter.

Install Dependencies:

Bash
pip install psutil pyserial winsdk requests pyautogui pystray Pillow plyer pywin32
Run Application:

Bash
python main.py
⚙️ Configuration
On first run, the app generates a config.ini. Key settings are accessible via the System Tray:

Port: Set to Auto (smart scanning) or a fixed COM port.

Display Mode: Switch between PC Monitor, Meteo, Media, Graph, or Loop (auto-cycling).

Lock Settings: Configure display behavior when Windows is locked (Show Meteo, Dim to 0, or Sleep).

Language: Affects both the App menu and the "Name Day" source.
