Here’s an improved, polished version of your README snippet, with clearer language, consistent formatting, and some minor grammar fixes:

---

# *OpenLM: An Open-Source Pixel Super-Resolution Platform for Lens-Free Microscopy*

OpenLM is a fully open-source, 3D-printed lens-free microscopy platform that integrates affordable, commercially available components with a pixel super-resolution algorithm. It features an intuitive graphical user interface and supports both **Raspberry Pi OS** and **Windows OS** for seamless camera control, real-time preview, image acquisition, and image processing — all without requiring prior experience in lens-free imaging.

---

## 🔧 Features

* Affordable, accessible hardware (Raspberry Pi, LED array, filters, and Pi Camera)
* Pixel super-resolution algorithm for enhanced image quality
* User-friendly GUI applications for both Raspberry Pi and Windows
* Fully open-source software paired with 3D-printable hardware designs

---

## 🔧 MAterial List

| Component                      | Quantity   | Price    |
|-------------------------------|------------|----------|
| Raspberry Pi Camera Module 2   | 1 unit     | $14.99   |
| Thorlab 532 nm Filter          | 1 unit     | $164.67  |
| Adafruit DotStar 8x8 LED array | 1 unit     | $24.95   |
| Small Neodymium Magnets (6 mm)       | 4 units    | $0.08    |
| Raspberry Pi 4B                | 1 unit     | $75.00   |
| PLA for 3D Printed Casing     | 187 g      | $4.68    |
| **Total**                     |            | **$284.37** |


---
## 📦 Installation (Dependencies)

Ensure Python and pip are installed, then run:

```bash
sudo pip install adafruit-circuitpython-dotstar
sudo pip install rawpy
sudo pip install scipy
sudo pip install flask_socketio
sudo pip install imageio
sudo pip install scikit-image
sudo pip install image_registration
```

---

## 🛠 Common Issues & Fixes

**Issue:**
`ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject`

**Solution:**
Install a compatible NumPy version:

```bash
sudo pip install numpy==1.26.4
```

---

**Issue:**
Permission denied when saving files

**Solution:**
Run the application with elevated privileges:

```bash
sudo python /path/to/OpenLM_RP.py
```

---

## 🔗 Mounting a Windows Shared Folder on Raspberry Pi

To access a Windows shared folder from your Raspberry Pi:

```bash
sudo apt install cifs-utils
mkdir ~/shared
sudo mount -t cifs //YourPCName/SharedFolder ~/shared -o username=YourWindowsUsername
```

---

## 🖥️ GUI Usage Instructions

### Raspberry Pi GUI

<p align="center">
  <img src="https://github.com/user-attachments/assets/41488388-7405-4c47-b223-502a17911934" width="450" height="300" alt="Raspberry Pi GUI">
</p>

1. **Left checkbox:** Select to analyze the captured hologram on a connected desktop.
2. **Middle checkbox:** Select to perform hologram focusing directly on the Raspberry Pi. (Raspberry Pi 4B or above can handle single hologram focusing but results are not guaranteed.)
3. **Right checkbox:** Select to enable real-time pixel super-resolution (PSR). Note: The "client" checkbox must be checked to use this option. Real-time PSR significantly reduces processing time for each capture event.

<p align="center">
  <img src="https://github.com/user-attachments/assets/86fec282-12ef-4f2c-9caf-b0bf16f5e25e" alt="Optional Settings">
</p>

4. 

---




