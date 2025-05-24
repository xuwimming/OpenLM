---

# *OpenLM: An Open-Source Pixel Super-Resolution Platform for Lens-Free Microscopy*

OpenLM is an open-source, 3D-printed lens-free microscopy platform that combines low-cost, commercially available components with a pixel super-resolution algorithm. It features a user-friendly interface and supports both **Raspberry Pi OS** and **Windows OS** for camera control, real-time preview, image acquisition, and image processing—no prior expertise in lens-free imaging is required.

---

## 🔧 Features

* Low-cost, accessible hardware (Raspberry Pi, LED array, filters, and Pi Camera)
* Pixel super-resolution algorithm for enhanced image quality
* Intuitive GUI applications for both Raspberry Pi and Windows
* Fully open-source software and 3D-printable hardware design

---

## 📦 Installation (Dependencies)

Make sure you have Python and pip installed. Then install the required packages:

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

**Issue**:
`ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject`

**Solution**:
Install a compatible NumPy version:

```bash
sudo pip install numpy==1.26.4
```

---

## 🔗 Mounting a Windows Shared Folder on Raspberry Pi

To access a shared folder from your PC on Raspberry Pi:

```bash
sudo apt install cifs-utils
mkdir ~/shared
sudo mount -t cifs //YourPCName/SharedFolder ~/shared -o username=YourWindowsUsername
```

---

Let me know if you'd like to add sections for:

* GUI usage instructions
* System requirements
* Hardware setup (e.g., wiring diagram or STL files for the 3D print)



