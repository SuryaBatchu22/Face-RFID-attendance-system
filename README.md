# RFID + Face Recognition Attendance System

A Flask-based web application paired with an Arduino + MFRC522 RFID reader and your laptop’s webcam to capture attendance via **dual-factor verification** (RFID + face).  
Generates daily Excel sheets, emails students on registration & attendance, and automatically sends reports to professors.

---

## Key Features

- **Dual-factor check**: RFID card scan **and** live face match  
- **Multi-class support**: Separate schedules, student lists, and reports per subject  
- **Day-of-week controls**: Only active on designated class days  
- **Automated emails**:  
  - Students receive confirmation on registration & first attendance of the day  
  - Professors get the daily attendance sheet 20 min after class start  
- **Demo mode**: Test the full flow without hardware by returning hard-coded UIDs  
- **Web UI**:  
  - **Register** page (scan RFID → capture face → submit)  
  - **Attendance** page (scan RFID → capture face → confirm)  

---

## Prerequisites

- **Hardware**  
  - Arduino Uno R3  
  - MFRC522 RFID module wired to the Arduino (see sketch comments)  
  - Laptop with functional webcam  

- **Software**  
  - Python 3.8+  
  - [Arduino IDE](https://www.arduino.cc/en/software) for uploading the sketch  
  - A Gmail account for sending emails (with an **App Password**)  

---

## Installation

1. **Clone** the repository  
   ```bash
   git clone https://github.com/yourusername/Face-RFID-attendance-system.git
   cd Face-RFID-attendance-system
   ```
2. **Create & activate** a virtual environment  
   ```bash
   python3 -m venv venv
   # macOS/Linux
   source venv/bin/activate
   # Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   ```
3. **Install** dependencies  
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration

1. **Arduino sketch**  
   - Open `arduino/rfid_attendance/rfid_attendance.ino` in the Arduino IDE  
   - Wire MFRC522 pins to your Arduino per the comments in that sketch  
   - Upload the sketch to your Uno  

2. **Email & serial settings**  
   - In `app.py`, set your COM port if using real hardware (uncomment `serial.Serial(...)`)  
   - Edit the `CLASS_ACCOUNT` block with your Gmail address & app-password  
   - Each subject’s professor email lives in the `CLASSES` dict  

3. **Demo mode**  
   - To skip hardware, leave `DEMO_MODE = True` in `app.py`  
   - To use the real RFID reader, set `DEMO_MODE = False`  

---

## ▶Usage

1. **Start** the Flask server:  
   ```bash
   python app.py
   ```
2. **Open** your browser at `http://localhost:5000`  
3. **Register** students (only during the 10 min before → 20 min after class start)  
4. **Take Attendance** in the same window  

---

## Project Structure

```
attendance-system/
├── README.md
├── requirements.txt         # Python dependencies
├── .gitignore
│
├── arduino/
│   └── rfid_attendance.ino  # Arduino sketch
│
├── app.py                   # Flask server & logic
│
├── templates/
│   ├── attendance.html      # Attendance page
│   └── register.html        # Registration page
│
└── static/
    ├── scripts.js           # Front-end logic
    └── style.css            # Styling
```

---

## Contributing

1. Fork the repo  
2. Create a feature branch (`git checkout -b feature/my-change`)  
3. Commit your changes (`git commit -am "Add feature"`)  
4. Push to your branch (`git push origin feature/my-change`)  
5. Open a Pull Request  

---

## License

This project is licensed under the MIT License – see the [LICENSE] file for details.

© 2025 Surya Batchu

