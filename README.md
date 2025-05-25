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

## 📋 Material List

| Component                      | Quantity   | Price    |
|-------------------------------|------------|----------|
| Raspberry Pi Camera Module 2   | 1 unit     | $14.99   |
| Thorlab 532 nm Filter          | 1 unit     | $164.67  |
| Adafruit DotStar 8x8 LED array | 1 unit     | $24.95   |
| 6mm Neodymium Magnets       | 4 units    | $0.08    |
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

---

### Raspberry Pi GUI

<p align="center">
  <img src="https://github.com/user-attachments/assets/41488388-7405-4c47-b223-502a17911934" width="450" height="300" alt="Raspberry Pi GUI">
</p>

1. **Left Checkbox** – Enable analysis of the captured hologram on a connected desktop.
2. **Middle Checkbox** – Perform focusing directly on the Raspberry Pi. *(Note: Raspberry Pi 4B or above is recommended for reliable performance.)*
3. **Right Checkbox** – Enable **real-time pixel super-resolution (PSR)**.

   > Requires the **"Client"** checkbox to be selected. This significantly reduces processing time during image capture.

<p align="center">
  <img src="https://github.com/user-attachments/assets/86fec282-12ef-4f2c-9caf-b0bf16f5e25e" alt="Optional Settings">
</p>

4. **LED Array Preview** – The effective LEDs used during imaging are highlighted in red:

<p align="center">
  <img src="https://github.com/user-attachments/assets/698db4ed-451b-473d-9f9c-e3c2b3f5aecd" width="300" alt="LED Array">
</p>

5. **Current Time Display** – Shows the timestamp of the image currently displayed.

   > This is especially useful when PSR processing takes longer than the image capture interval.

<p align="center">
  <img src="https://github.com/user-attachments/assets/b1c6a0e5-c3bc-4932-995a-9d330dcac1b6" width="400" alt="Current Time Display">
</p>

---

### 🖥️ Windows GUI

<p align="center">
  <img src="https://github.com/user-attachments/assets/c4c244bc-6181-4683-aba6-f8f9b38276a7" width="800" alt="Windows GUI">
</p>

1. **Connection Indicator** – When the connection to the Raspberry Pi is established successfully, the status indicator turns **green**.

   <p align="center">
     <img src="https://github.com/user-attachments/assets/c24ba83f-06c6-4e23-b7be-e4fda69f1d8f" width="300" alt="Connection Indicator">
   </p>

2. **Frames** – Specifies the number of frames the user wishes to process.

   <p align="center">
     <img src="https://github.com/user-attachments/assets/11136239-55ce-4d2b-b063-4ec5bcbf6873" width="400" alt="Frame Setting">
   </p>

Got it! Here's your section with a neat symbol added at the start — a simple folder emoji 📁 fits nicely for folder structure sections:

---

### 🗂️ Save Image Folder Structure

**Single LR Hologram Capture**

Selected Folder

  └── Selected file name.jpg and .dng

**Single HR Hologram Capture**

Selected Folder

  ├── 0.jpg and 0.dng

  ├── 1.jpg and 1.dng

  ├── ...

  └── 63.jpg and 63.dng

**Time-Lapse Hologram Capture**

Selected Folder

├── 0

│   ├── 28 jpg files

│   └── 28 dng files

├── 1

│   ├── 28 jpg files

│   └── 28 dng files

├── ...

├── N    

│   ├── 28 jpg files

│   └── 28 dng files

---

### 📁 Additional Files

1. **`Shifting_Map_Generation.ipynb`** (located in the `Windows Application` folder)
   This notebook is used to generate a high-accuracy shifting map for high-resolution (HR) image reconstruction. While the main application can also generate a shifting map, we **highly recommend** using this notebook for more accurate results.
   🔹 *Note:* Each focusing object from a different depth requires its corresponding shifting map.

2. **Focal Plane Estimation**
   The same notebook also estimates the optimal focal plane of the target object. Updating the focus setting through the GUI based on this estimation can significantly improve the accuracy and speed of the reconstruction algorithm.

3. **Modify Focal Plane Start Value**
   Update the `z_start` value in the `OpenLMlib.py` file, inside the `imageReconstruction_unknownZ_loop` function.
   This value corresponds to the estimated focal plane of the low-resolution hologram and should be set based on the result from `Shifting_Map_Generation.ipynb`.

   <p align="center">
     <img src="https://github.com/user-attachments/assets/ce9cdef6-5d96-475f-9483-bc079d5ce540" width="600" alt="Focal Plane GUI">
   </p>

4. **`Post_Processing.ipynb`** (in the `Windows Application` folder)
   This notebook batch-processes all captured frames and compiles a time-lapse video.
   ⚠️ *Important:* If real-time processing is enabled, the application will continue running until all captured frames are processed. For back-to-back experiments, we recommend capturing all images first and then performing post-processing afterward using this notebook.

---

### 📚 Citation


---

   
