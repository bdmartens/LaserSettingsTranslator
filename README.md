# Laser Settings Translator

A premium settings, profile management, and universal translation tool for **LightBurn** and **K40 Whisperer** laser control software. 

This application bridges the gap between different laser cutters (varying tube ages, optical paths, nominal wattages, and focus lenses) by using physical and thermodynamic models to mathematically translate laser settings from one machine to another.

---

## 📖 Table of Contents
- [Key Features](#-key-features)
- [Mathematical Framework](#-mathematical-framework)
- [System Requirements & Dependencies](#-system-requirements--dependencies)
- [Installation & Running](#-installation--running)
- [How to Accomplish Key Tasks](#-how-to-accomplish-key-tasks)
  - [1. Calibrating Your Machine Factor (κ-Factor)](#1-calibrating-your-machine-factor-κ-factor)
  - [2. Translating a LightBurn Material Library](#2-translating-a-lightburn-material-library)
  - [3. Generating K40 Whisperer Cheat Sheets](#3-generating-k40-whisperer-cheat-sheets)
- [Project Directory Structure](#-project-directory-structure)
- [Verification & Quality Assurance](#-verification--quality-assurance)

---

## 🌟 Key Features

*   **Machine Efficiency Calibration Engine ($\kappa$-Factor Regression):** Solves for your laser's specific physical cutting ($\kappa_{cut}$) and engraving ($\kappa_{eng}$) efficiency constants using linear least-squares regression against reference material benchmarks.
*   **Thermodynamic & Optical Scaling:** 
    *   *Optical Beam Divergence:* Scales focus spot sizes based on wattage (e.g., `0.08 mm` at 40W, scaling non-linearly using the square root of wattage ratios for higher power tubes).
    *   *Focal Lens Scaling:* Automatically scales cutting kerf width and linear energy density ($E_l$) based on the lens focal length (e.g., standard 2.0" lenses vs 1.5" lenses).
    *   *Specific Energy Density ($E_v$):* Matches the required energy density per unit volume ($J/mm^3$) to yield uniform results across different machines.
*   **Universal Library Porting:** Easily import an existing LightBurn `.clb` or `.clib` library, translate all speeds, powers, and passes to match another machine's characteristics, and export a fresh, ready-to-import LightBurn library.
*   **K40 Whisperer Compatibility:** Convert complex LightBurn material libraries into clean, categorized text cheat sheets mapped directly to K40 Whisperer’s color-coded vector cut (Red) and raster engrave (Blue/Black) workflow.
*   **Premium GUI:** Built with a modern, fully-responsive dark-mode user interface using `CustomTkinter`.

---

## 🧮 Mathematical Framework

The application relies on physical modeling rather than generic percentage scaling:

1.  **Spot Size Power Density Scaling:**
    $$w_{spot} = 0.08 \times \sqrt{\frac{\text{Wattage}_{\text{user}}}{40.0}}$$
    *(High-power CO2 tubes physically yield larger spot sizes, reducing peak power density).*

2.  **Cutting Resistance Constant ($c_{mat}$):**
    $$c_{mat} = \frac{\text{Power}_{\text{watts}} \times \text{Passes}}{\text{Speed} \times \text{Thickness}}$$
    *(Determines how many Joules per square millimeter a specific material absorbs to shear).*

3.  **Machine Efficiency Solver (Least-Squares Regression for $\kappa_{cut}$):**
    $$v_{\text{model}} = \frac{P_{\text{watts}} \times N_{\text{passes}} \times \text{Spot Ratio}}{d \times c_{mat}}$$
    The engine fits the user's actual cut speeds ($v_{\text{user}}$) to the physical model ($v_{\text{model}}$) using the slope $\kappa_{cut}$ minimizing the sum of squared errors:
    $$\kappa_{cut} = \frac{\sum (v_{\text{model}} \times v_{\text{user}})}{\sum v_{\text{model}}^2}$$

4.  **Gantry & Power Clamping Safeguards:**
    If scaled speed exceeds the physical limits of your laser gantry ($V_{max}$), the engine dynamically reduces the cutting/engraving power to maintain the exact specific energy target at $V_{max}$.

---

## 📦 System Requirements & Dependencies

The project is built on **Python 3.8+** and requires minimal external packages.

### Core Dependencies:
*   **Python:** `3.8`, `3.9`, `3.10`, `3.11`, or `3.12`
*   **CustomTkinter:** `sqlite3` and `tkinter` (normally bundled with Python installations)
*   **Libraries (`requirements.txt`):**
    *   `customtkinter>=5.2.0` (Modern graphical components and styles)

---

## 🚀 Installation & Running

### 1. Clone & Setup Environment
Open your terminal/command prompt, navigate to the folder, and create a virtual environment:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (macOS/Linux)
source .venv/bin/activate
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Run the GUI Application
```powershell
python main.py
```

---

## 🛠️ How to Accomplish Key Tasks

### 1. Calibrating Your Machine Factor (κ-Factor)
Every individual laser has a unique efficiency profile depending on mirrors alignment, age of the tube, and chiller efficiency.
1. Run a few test cuts on standard materials (e.g., Birch Plywood, Acrylic) and note down the **thickness**, **speed**, **power**, and **passes** where the laser achieved a clean, minimal-power cut.
2. Launch the application (`python main.py`).
3. Under the **Calibration** panel, input your test cut values.
4. Select the matching material from the reference database.
5. Click **Solve & Calibrate**. The math engine will compute your machine's exact $\kappa_{cut}$ efficiency coefficient. A factor of `1.0` is standard; values `< 1.0` indicate a slightly less efficient system (common with older tubes), and `> 1.0` indicates high efficiency.

### 2. Translating a LightBurn Material Library
Have a library dialed in for a 40W K40 but just upgraded to an 80W or 130W cabinet?
1. Open the application.
2. In the **Machine Profiles** section, select or input your current target machine profile (e.g., 80W CO2, 60mm/s Max Gantry Speed, focal length 1.5").
3. Click **Import LightBurn Library (.clb/.clib)** and select your source file.
4. Set the **Source Wattage** (e.g., 40W).
5. Input your calibrated $\kappa_{cut}$ / $\kappa_{eng}$ factors (or leave as `1.0` for default scaling).
6. Click **Translate & Export**. The application scales every material entry based on your target wattage, focal spot adjustments, and speed/power safety bounds, writing a brand new `.clb` library file.
7. Open LightBurn, go to **Material Library -> Load**, and choose your new file.

### 3. Generating K40 Whisperer Cheat Sheets
Since K40 Whisperer runs on color layers (Red for Vector Cut, Blue for Vector Engrave, Black for Raster) instead of library formats:
1. Load a LightBurn library or generate a custom profile library in the app.
2. Click **Export K40 Whisperer Cheat Sheet**.
3. Select where you want to save the `.txt` file.
4. This produces a clear, categorized, human-readable text reference detailing exactly what analog pot current percentages/digital power settings and speeds to input manually for every material.

---

## 📂 Project Directory Structure

```filepath
K40-Settings/
│
├── main.py                     # Main application entry point
├── requirements.txt            # Project python dependencies
├── GEMINI.md                   # Lead Systems Architect constraints & guidelines
├── README.md                   # This instruction and user manual
│
├── data/
│   ├── default_materials.json  # Reference physical cutting/engraving benchmarks
│   └── machine_profiles.json   # Pre-configured machine profiles (40W, 80W, 130W, etc.)
│
├── src/
│   ├── gui/
│   │   ├── __init__.py         # Package initialization
│   │   └── main_window.py      # CustomTkinter GUI layout & user-event triggers
│   │
│   ├── math_engine.py          # Physics, optics, and statistical regression solvers
│   └── parser.py               # LightBurn CLB XML parser & K40 text exporter
│
└── tests/
    └── test_math.py            # Complete test suite validating scaling and safeguards
```

---

## 🧪 Verification & Quality Assurance

To verify that the translation equations, spot size conversions, focal length kerfs, regression solvers, and safety clamping algorithms are performing flawlessly, run the automated test suite:

```powershell
python tests/test_math.py
```

This runs 8 extensive validation tests verifying spot size scaling, linear regression precision, gantry speed safeguards, thermodynamic calculations, and metric/imperial unit conversions.
