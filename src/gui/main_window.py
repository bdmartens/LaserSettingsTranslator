import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        # Delay showing by 300ms for premium feeling
        self.id = self.widget.after(300, self._display_tip)

    def _display_tip(self):
        self.id = None
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        # Premium tooltip styling: dark background, light text, padded
        label = tk.Label(
            tw, 
            text=self.text, 
            justify="left", 
            background="#2B2B2B", 
            foreground="#FFFFFF", 
            relief="solid", 
            borderwidth=1, 
            font=("Inter", 9),
            padx=8,
            pady=4,
            wraplength=250
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# Import our custom logic
from ..math_engine import LaserMathEngine
from ..parser import LightBurnParser

class LaserSettingsApp(ctk.CTk):
    def __init__(self, workspace_dir=None):
        super().__init__()

        # Decouple workspace path
        self.workspace_dir = workspace_dir or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Initialize engine and parser
        self.engine = LaserMathEngine()
        self.parser = LightBurnParser()

        # Load reference materials
        self.reference_db = self._load_default_db()

        # Application state
        self.selected_laser_type = ctk.StringVar(value="CO2")
        self.user_wattage = ctk.DoubleVar(value=40.0)
        self.compare_wattage = ctk.DoubleVar(value=40.0)
        self.compare_kerf = ctk.DoubleVar(value=0.15)
        self.kappa_cut = ctk.DoubleVar(value=1.0)
        self.kappa_eng = ctk.DoubleVar(value=1.0)
        
        # Unit system tracking
        self.unit_system = ctk.StringVar(value="Metric (mm, mm/s)")

        # Multi-test lists
        self.added_cut_tests = []
        self.added_eng_tests = []

        # Machine bounds & safety constraints
        self.max_speed = ctk.DoubleVar(value=80.0)
        self.max_speed_eng = ctk.DoubleVar(value=400.0)
        self.min_power = ctk.DoubleVar(value=10.0)
        self.max_power = ctk.DoubleVar(value=80.0)

        # Optical parameters
        self.laser_kerf = ctk.DoubleVar(value=0.15)
        self.lens_focal = ctk.StringVar(value="50.8") # Metric default focal (2.0" = 50.8 mm)
        
        # LightBurn library state
        self.loaded_library_path = None
        self.loaded_library_data = None

        # High power normalization options
        self.normalize_high_power = ctk.BooleanVar(value=True)
        self.power_cap_percentage = ctk.DoubleVar(value=80.0)

        # Color coding state variables
        self.cut_color = "#FF6B6B"
        self.engrave_color = "#51CF66"

        # Compare & Merge state variables
        self.compare_library_path = None
        self.compare_library_data = None
        self.compare_library_data_flat = []
        self.matched_pairs = [] # List of {"left_id": str, "right_id": str}
        self.selected_left_id = None
        self.selected_right_id = None
        self.left_export_selections = {}
        self.right_export_selections = {}
        self.left_list_evaluated = None
        self.right_list_evaluated = None

        # Setup GUI Properties
        self.title("Antigravity - Laser Calibration & Settings Manager")
        self.geometry("1100x700")
        
        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Build Sidebar
        self._build_sidebar()

        # Build Main View (Tabs)
        self._build_main_view()
        
        # Populate material dropdowns dynamically
        self._update_material_dropdown_options()

        # Load the first saved machine profile on startup if available
        profiles = self._load_saved_profiles()
        if profiles:
            first_profile = list(profiles.keys())[0]
            self._load_machine_profile(first_profile, show_message=False)

    def _load_default_db(self):
        db_path = os.path.join(self.workspace_dir, "data", "default_materials.json")
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        # Fallback empty database
        return {"laser_types": {}}

    def _build_sidebar(self):
        # We make the sidebar a scrollable frame so it never overflows and remains beautifully organized
        self.sidebar = ctk.CTkScrollableFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # 1. Title / Brand
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="LASER CALIBRATE", 
            font=ctk.CTkFont(family="Inter", size=22, weight="bold")
        )
        self.logo_label.pack(padx=20, pady=(20, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar, 
            text="Profile Calibration Engine", 
            font=ctk.CTkFont(family="Inter", size=12, slant="italic")
        )
        self.subtitle_label.pack(padx=20, pady=(0, 5))

        self.active_profile_label = ctk.CTkLabel(
            self.sidebar, 
            text="Current Profile:  none", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#A9A9A9"
        )
        self.active_profile_label.pack(padx=20, pady=(0, 10))

        # Divider
        ctk.CTkFrame(self.sidebar, height=2, width=220, fg_color="gray30").pack(padx=20, pady=10)

        # 2. Hardware Setup Section
        ctk.CTkLabel(
            self.sidebar, 
            text="HARDWARE SPECIFICATIONS", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        ).pack(anchor="w", padx=20, pady=(0, 5))

        self.unit_system_label = ctk.CTkLabel(self.sidebar, text="Unit System:")
        self.unit_system_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.unit_system_option = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.unit_system,
            values=["Metric (mm, mm/s)", "Imperial (in, in/s)"],
            command=self._on_unit_system_changed
        )
        self.unit_system_option.pack(fill="x", padx=20, pady=(0, 10))

        self.laser_type_label = ctk.CTkLabel(self.sidebar, text="Laser Source Type:")
        self.laser_type_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.laser_type_option = ctk.CTkOptionMenu(
            self.sidebar, 
            variable=self.selected_laser_type,
            values=["CO2", "Diode", "Fiber"],
            command=self._on_laser_type_changed
        )
        self.laser_type_option.pack(fill="x", padx=20, pady=(0, 10))

        self.wattage_label = ctk.CTkLabel(self.sidebar, text="Tube Strength (Watts):")
        self.wattage_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.wattage_entry = ctk.CTkEntry(self.sidebar, textvariable=self.user_wattage)
        self.wattage_entry.pack(fill="x", padx=20, pady=(0, 10))
        self.wattage_entry.bind("<KeyRelease>", lambda e: self._update_explorer_grid())

        # Divider 2
        ctk.CTkFrame(self.sidebar, height=2, width=220, fg_color="gray30").pack(padx=20, pady=10)

        # 3. Machine Calibration Factors
        ctk.CTkLabel(
            self.sidebar, 
            text="CALIBRATION FACTORS", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        ).pack(anchor="w", padx=20, pady=(0, 5))

        self.k_cut_label = ctk.CTkLabel(self.sidebar, text="Vector Cut Factor (\u03ba_cut):")
        self.k_cut_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.k_cut_slider = ctk.CTkSlider(self.sidebar, from_=0.2, to=2.0, variable=self.kappa_cut, command=self._on_slider_changed)
        self.k_cut_slider.pack(fill="x", padx=20, pady=(0, 2))
        self.k_cut_val_label = ctk.CTkLabel(self.sidebar, text="1.00x (Standard Alignment)")
        self.k_cut_val_label.pack(anchor="w", padx=20, pady=(0, 10))

        self.k_eng_label = ctk.CTkLabel(self.sidebar, text="Raster Engrave Factor (\u03ba_eng):")
        self.k_eng_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.k_eng_slider = ctk.CTkSlider(self.sidebar, from_=0.2, to=2.0, variable=self.kappa_eng, command=self._on_slider_changed)
        self.k_eng_slider.pack(fill="x", padx=20, pady=(0, 2))
        self.k_eng_val_label = ctk.CTkLabel(self.sidebar, text="1.00x (Standard Focus)")
        self.k_eng_val_label.pack(anchor="w", padx=20, pady=(0, 10))

        # Divider 3
        ctk.CTkFrame(self.sidebar, height=2, width=220, fg_color="gray30").pack(padx=20, pady=10)

        # 4. Optical Specifications
        ctk.CTkLabel(
            self.sidebar, 
            text="OPTICAL PARAMETERS", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        ).pack(anchor="w", padx=20, pady=(0, 5))

        self.kerf_label = ctk.CTkLabel(self.sidebar, text="Laser Kerf Width (mm):")
        self.kerf_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.kerf_entry = ctk.CTkEntry(self.sidebar, textvariable=self.laser_kerf)
        self.kerf_entry.pack(fill="x", padx=20, pady=(0, 10))
        self.kerf_entry.bind("<KeyRelease>", lambda e: self._update_explorer_grid())

        self.focal_label = ctk.CTkLabel(self.sidebar, text="Lens Focal Length (mm):")
        self.focal_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.focal_option = ctk.CTkOptionMenu(
            self.sidebar, 
            variable=self.lens_focal,
            values=["38.1", "50.8", "63.5"],
            command=lambda e: self._update_explorer_grid()
        )
        self.focal_option.pack(fill="x", padx=20, pady=(0, 10))

        # Divider 4
        ctk.CTkFrame(self.sidebar, height=2, width=220, fg_color="gray30").pack(padx=20, pady=10)

        # 5. Machine Constraints
        ctk.CTkLabel(
            self.sidebar, 
            text="MACHINE SAFETY BOUNDS", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        ).pack(anchor="w", padx=20, pady=(0, 5))

        self.max_speed_label = ctk.CTkLabel(self.sidebar, text="Max Cut Speed (mm/s):")
        self.max_speed_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.max_speed_entry = ctk.CTkEntry(self.sidebar, textvariable=self.max_speed)
        self.max_speed_entry.pack(fill="x", padx=20, pady=(0, 10))
        self.max_speed_entry.bind("<KeyRelease>", lambda e: self._update_explorer_grid())

        self.max_speed_eng_label = ctk.CTkLabel(self.sidebar, text="Max Engrave Speed (mm/s):")
        self.max_speed_eng_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.max_speed_eng_entry = ctk.CTkEntry(self.sidebar, textvariable=self.max_speed_eng)
        self.max_speed_eng_entry.pack(fill="x", padx=20, pady=(0, 10))
        self.max_speed_eng_entry.bind("<KeyRelease>", lambda e: self._update_explorer_grid())

        self.min_power_label = ctk.CTkLabel(self.sidebar, text="Min Tube Power (%):")
        self.min_power_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.min_power_entry = ctk.CTkEntry(self.sidebar, textvariable=self.min_power)
        self.min_power_entry.pack(fill="x", padx=20, pady=(0, 10))
        self.min_power_entry.bind("<KeyRelease>", lambda e: self._update_explorer_grid())

        self.max_power_label = ctk.CTkLabel(self.sidebar, text="Max Tube Power (%):")
        self.max_power_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.max_power_entry = ctk.CTkEntry(self.sidebar, textvariable=self.max_power)
        self.max_power_entry.pack(fill="x", padx=20, pady=(0, 20))
        self.max_power_entry.bind("<KeyRelease>", lambda e: self._update_explorer_grid())

        # Divider 5
        ctk.CTkFrame(self.sidebar, height=2, width=220, fg_color="gray30").pack(padx=20, pady=10)

        # 6. Machine Profiles Manager
        ctk.CTkLabel(
            self.sidebar, 
            text="MACHINE PROFILES", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        ).pack(anchor="w", padx=20, pady=(0, 5))

        self.profile_name_label = ctk.CTkLabel(self.sidebar, text="Specify Machine Name:")
        self.profile_name_label.pack(anchor="w", padx=20, pady=(5, 2))
        self.profile_name_entry = ctk.CTkEntry(self.sidebar, placeholder_text="e.g. Omtech K40+")
        self.profile_name_entry.pack(fill="x", padx=20, pady=(0, 10))

        self.save_profile_btn = ctk.CTkButton(
            self.sidebar, 
            text="Save Current Specs", 
            fg_color="#1F6AA5",
            hover_color="#154B75",
            command=self._save_machine_profile
        )
        self.save_profile_btn.pack(fill="x", padx=20, pady=(0, 15))

        self.profiles_list_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.profiles_list_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self._update_profiles_list_display()

    def _build_main_view(self):
        # Create Tab View
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_wizard = self.tabview.add("Calibration Wizard")
        self.tab_explorer = self.tabview.add("Materials Library")
        self.tab_analytics = self.tabview.add("Specific Energy Analytics")
        self.tab_import = self.tabview.add("Import / Export Profile")
        self.tab_compare = self.tabview.add("Compare & Merge")

        self._build_dashboard_tab()
        self._build_wizard_tab()
        self._build_explorer_tab()
        self._build_analytics_tab()
        self._build_import_tab()
        self._build_compare_tab()

    # ==================== TAB 1: DASHBOARD ====================
    def _build_dashboard_tab(self):
        self.tab_dash.grid_columnconfigure((0, 1), weight=1)
        self.tab_dash.grid_rowconfigure(1, weight=1)
        self.tab_dash.grid_rowconfigure(2, weight=0)

        # Welcome text card
        self.welcome_card = ctk.CTkFrame(self.tab_dash, corner_radius=8, border_width=1, border_color="gray30")
        self.welcome_card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=15)
        
        welcome_title = ctk.CTkLabel(
            self.welcome_card, 
            text="Universal Laser settings translator", 
            font=ctk.CTkFont(family="Inter", size=18, weight="bold")
        )
        welcome_title.pack(anchor="w", padx=20, pady=(15, 5))

        welcome_desc = ctk.CTkLabel(
            self.welcome_card, 
            text="Welcome to the settings calibration workbench. Enter your hardware specs on the left. The statistical solver correlates reference libraries to your machine using your custom machine calibration factors.",
            wraplength=700, 
            justify="left"
        )
        welcome_desc.pack(anchor="w", padx=20, pady=(0, 15))

        # Efficiency Meters Card
        self.meters_card = ctk.CTkFrame(self.tab_dash, corner_radius=8, fg_color="gray15")
        self.meters_card.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)

        meters_title = ctk.CTkLabel(self.meters_card, text="Machine Health Assessment", font=ctk.CTkFont(family="Inter", size=14, weight="bold"))
        meters_title.pack(anchor="w", padx=15, pady=15)

        self.cut_health_label = ctk.CTkLabel(self.meters_card, text="Vector Cut Health: Optimal (1.0x)", justify="left")
        self.cut_health_label.pack(anchor="w", padx=20, pady=5)
        
        self.cut_health_progress = ctk.CTkProgressBar(self.meters_card, height=15)
        self.cut_health_progress.pack(fill="x", padx=20, pady=(0, 15))
        self.cut_health_progress.set(0.5) # 1.0x constant sits in middle

        self.eng_health_label = ctk.CTkLabel(self.meters_card, text="Engraving Calibration: Nominal (1.0x)", justify="left")
        self.eng_health_label.pack(anchor="w", padx=20, pady=5)
        
        self.eng_health_progress = ctk.CTkProgressBar(self.meters_card, height=15)
        self.eng_health_progress.pack(fill="x", padx=20, pady=(0, 20))
        self.eng_health_progress.set(0.5)

        # Import Starting Materials Library Card
        self.dash_import_card = ctk.CTkFrame(self.tab_dash, corner_radius=8, fg_color="gray15")
        self.dash_import_card.grid(row=1, column=1, sticky="nsew", padx=15, pady=15)

        dash_imp_title = ctk.CTkLabel(self.dash_import_card, text="Starting Materials Library", font=ctk.CTkFont(family="Inter", size=14, weight="bold"))
        dash_imp_title.pack(anchor="w", padx=15, pady=15)

        self.dash_file_path_label = ctk.CTkLabel(self.dash_import_card, text="No Library file loaded currently.", font=ctk.CTkFont(size=11, slant="italic"))
        self.dash_file_path_label.pack(anchor="w", padx=20, pady=5)

        self.dash_load_btn = ctk.CTkButton(
            self.dash_import_card, 
            text="Browse starting library (.clb/.clib)", 
            fg_color="#1F6AA5",
            hover_color="#154B75",
            command=self._browse_library
        )
        self.dash_load_btn.pack(anchor="w", padx=20, pady=15)

        # Divider for visual separation
        ctk.CTkFrame(self.dash_import_card, height=2, fg_color="gray30").pack(fill="x", padx=15, pady=10)

        color_title = ctk.CTkLabel(self.dash_import_card, text="Interface Color Customizer", font=ctk.CTkFont(family="Inter", size=13, weight="bold"))
        color_title.pack(anchor="w", padx=15, pady=(5, 5))

        # Vector Cut Color row
        cut_row = ctk.CTkFrame(self.dash_import_card, fg_color="transparent")
        cut_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(cut_row, text="Vector Cut Color:", font=ctk.CTkFont(size=11)).pack(side="left")
        
        self.cut_color_btn = ctk.CTkButton(
            cut_row,
            text=self.cut_color,
            fg_color=self.cut_color,
            hover_color=self.cut_color,
            text_color="#000000",
            width=95,
            height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._choose_cut_color
        )
        self.cut_color_btn.pack(side="right")

        # Raster Engrave Color row
        eng_row = ctk.CTkFrame(self.dash_import_card, fg_color="transparent")
        eng_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(eng_row, text="Raster Engrave Color:", font=ctk.CTkFont(size=11)).pack(side="left")
        
        self.eng_color_btn = ctk.CTkButton(
            eng_row,
            text=self.engrave_color,
            fg_color=self.engrave_color,
            hover_color=self.engrave_color,
            text_color="#000000",
            width=95,
            height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._choose_engrave_color
        )
        self.eng_color_btn.pack(side="right")

        # Quick Reference Summary Card
        self.quick_ref_card = ctk.CTkFrame(self.tab_dash, corner_radius=8, fg_color="gray15")
        self.quick_ref_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=15)

        qr_title = ctk.CTkLabel(self.quick_ref_card, text="Laser Wavelength Physics Overview", font=ctk.CTkFont(family="Inter", size=14, weight="bold"))
        qr_title.pack(anchor="w", padx=15, pady=15)

        self.physics_text = ctk.CTkLabel(
            self.quick_ref_card,
            text=(
                "**CO2 Lasers (10,600 nm):** Absorbs beautifully in wood, clear acrylic, glass, and leather. Reflected by bare metals.\n"
                "**Diode Lasers (450 nm):** Excellent for wood and dark acrylics. Wavelength completely passes through clear acrylic and glass (cannot cut).\n"
                "**Fiber Lasers (1,064 nm):** Highly concentrated absorption in metals and specialized engineering plastics."
            ),
            wraplength=700,
            justify="left"
        )
        self.physics_text.pack(anchor="w", padx=20, pady=(0, 15))

    # ==================== TAB 2: CALIBRATION WIZARD ====================
    def _build_wizard_tab(self):
        self.tab_wizard.grid_columnconfigure((0, 1), weight=1)
        self.tab_wizard.grid_rowconfigure(1, weight=1)

        # Description
        desc_label = ctk.CTkLabel(
            self.tab_wizard, 
            text="Perform one or more test cuts/engravings on your laser, add them below, and solve to compute the average coefficient, range, and standard deviation.",
            font=ctk.CTkFont(size=12, slant="italic")
        )
        desc_label.grid(row=0, column=0, columnspan=2, padx=15, pady=10, sticky="w")

        # ==================== LEFT COLUMN: CUT WIZARD ====================
        cut_card = ctk.CTkFrame(self.tab_wizard, corner_radius=8, fg_color="gray15")
        cut_card.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        cut_card.grid_columnconfigure((0, 1), weight=1)
        cut_card.grid_rowconfigure(7, weight=1)

        cc_title = ctk.CTkLabel(cut_card, text="Vector Cut Calibration Wizard", font=ctk.CTkFont(size=15, weight="bold"), text_color="#1F6AA5")
        cc_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # Materials Dropdown
        ctk.CTkLabel(cut_card, text="Calibration Material:").grid(row=1, column=0, padx=15, pady=3, sticky="e")
        self.wiz_cut_material = ctk.CTkOptionMenu(cut_card, values=["Birch Plywood", "Acrylic (Clear/Cast)", "MDF", "Cardboard", "Leather (Veg-Tanned)"])
        self.wiz_cut_material.grid(row=1, column=1, padx=15, pady=3, sticky="w")

        # Thickness
        self.wiz_cut_thick_label = ctk.CTkLabel(cut_card, text="Material Thickness (mm):")
        self.wiz_cut_thick_label.grid(row=2, column=0, padx=15, pady=3, sticky="e")
        self.wiz_cut_thick = ctk.CTkEntry(cut_card, width=100)
        self.wiz_cut_thick.insert(0, "3.0")
        self.wiz_cut_thick.grid(row=2, column=1, padx=15, pady=3, sticky="w")

        # Speed achieved
        self.wiz_cut_speed_label = ctk.CTkLabel(cut_card, text="Optimal Speed (mm/s):")
        self.wiz_cut_speed_label.grid(row=3, column=0, padx=15, pady=3, sticky="e")
        self.wiz_cut_speed = ctk.CTkEntry(cut_card, width=100)
        self.wiz_cut_speed.insert(0, "7.0")
        self.wiz_cut_speed.grid(row=3, column=1, padx=15, pady=3, sticky="w")

        # Power percentage
        ctk.CTkLabel(cut_card, text="Optimal Power Setting (%):").grid(row=4, column=0, padx=15, pady=3, sticky="e")
        self.wiz_cut_power = ctk.CTkEntry(cut_card, width=100)
        self.wiz_cut_power.insert(0, "65.0")
        self.wiz_cut_power.grid(row=4, column=1, padx=15, pady=3, sticky="w")

        # Add/Clear Buttons Row
        btn_frame_cut = ctk.CTkFrame(cut_card, fg_color="transparent")
        btn_frame_cut.grid(row=5, column=0, columnspan=2, padx=15, pady=10, sticky="ew")
        
        self.add_cut_btn = ctk.CTkButton(btn_frame_cut, text="Add Test Cut", width=120, fg_color="gray30", hover_color="gray40", command=self._add_cut_test_run)
        self.add_cut_btn.pack(side="left", padx=10)
        
        self.clear_cut_btn = ctk.CTkButton(btn_frame_cut, text="Clear All", width=100, fg_color="#A83232", hover_color="#C03939", command=self._clear_cut_test_runs)
        self.clear_cut_btn.pack(side="left", padx=10)

        # Runs display box
        ctk.CTkLabel(cut_card, text="Added Cutting Test Runs (Click 'X' to remove outliers):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=6, column=0, columnspan=2, padx=15, pady=(5, 0), sticky="w")
        self.cut_runs_frame = ctk.CTkScrollableFrame(cut_card, height=120, corner_radius=6, border_width=1, border_color="gray40")
        self.cut_runs_frame.grid(row=7, column=0, columnspan=2, padx=15, pady=(2, 10), sticky="nsew")

        # Solve & Stats Card
        stats_frame_cut = ctk.CTkFrame(cut_card, corner_radius=6, fg_color="gray20")
        stats_frame_cut.grid(row=8, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="ew")
        stats_frame_cut.grid_columnconfigure((0, 1), weight=1)

        self.solve_cut_btn = ctk.CTkButton(stats_frame_cut, text="Solve Calibrations", command=self._solve_cut_calibration)
        self.solve_cut_btn.grid(row=0, column=0, columnspan=2, padx=15, pady=10, sticky="ew")

        self.lbl_cut_avg = ctk.CTkLabel(stats_frame_cut, text="Average Factor: N/A", font=ctk.CTkFont(weight="bold"))
        self.lbl_cut_avg.grid(row=1, column=0, padx=15, pady=2, sticky="w")

        self.lbl_cut_std = ctk.CTkLabel(stats_frame_cut, text="Std. Deviation (\u03c3): N/A")
        self.lbl_cut_std.grid(row=1, column=1, padx=15, pady=2, sticky="w")

        self.lbl_cut_range = ctk.CTkLabel(stats_frame_cut, text="Overall Range: N/A")
        self.lbl_cut_range.grid(row=2, column=0, columnspan=2, padx=15, pady=(2, 10), sticky="w")

        # ==================== RIGHT COLUMN: ENGRAVE WIZARD ====================
        eng_card = ctk.CTkFrame(self.tab_wizard, corner_radius=8, fg_color="gray15")
        eng_card.grid(row=1, column=1, sticky="nsew", padx=15, pady=10)
        eng_card.grid_columnconfigure((0, 1), weight=1)
        eng_card.grid_rowconfigure(7, weight=1)

        ec_title = ctk.CTkLabel(eng_card, text="Raster Engrave Calibration Wizard", font=ctk.CTkFont(size=15, weight="bold"), text_color="#1F6AA5")
        ec_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # Materials Dropdown
        ctk.CTkLabel(eng_card, text="Calibration Material:").grid(row=1, column=0, padx=15, pady=3, sticky="e")
        self.wiz_eng_material = ctk.CTkOptionMenu(eng_card, values=["Birch Plywood", "Acrylic (Clear/Cast)", "MDF", "Cardboard", "Leather (Veg-Tanned)"])
        self.wiz_eng_material.grid(row=1, column=1, padx=15, pady=3, sticky="w")

        # Engrave Mode
        ctk.CTkLabel(eng_card, text="Engraving Depth Mode:").grid(row=2, column=0, padx=15, pady=3, sticky="e")
        self.wiz_eng_mode = ctk.CTkOptionMenu(eng_card, values=["Light Engrave", "Frosted Engrave", "Standard Engrave", "Deep Engrave"])
        self.wiz_eng_mode.grid(row=2, column=1, padx=15, pady=3, sticky="w")

        # Speed achieved
        self.wiz_eng_speed_label = ctk.CTkLabel(eng_card, text="Optimal Speed (mm/s):")
        self.wiz_eng_speed_label.grid(row=3, column=0, padx=15, pady=3, sticky="e")
        self.wiz_eng_speed = ctk.CTkEntry(eng_card, width=100)
        self.wiz_eng_speed.insert(0, "150.0")
        self.wiz_eng_speed.grid(row=3, column=1, padx=15, pady=3, sticky="w")

        # Power percentage
        ctk.CTkLabel(eng_card, text="Optimal Power Setting (%):").grid(row=4, column=0, padx=15, pady=3, sticky="e")
        self.wiz_eng_power = ctk.CTkEntry(eng_card, width=100)
        self.wiz_eng_power.insert(0, "15.0")
        self.wiz_eng_power.grid(row=4, column=1, padx=15, pady=3, sticky="w")

        # Add/Clear Buttons Row
        btn_frame_eng = ctk.CTkFrame(eng_card, fg_color="transparent")
        btn_frame_eng.grid(row=5, column=0, columnspan=2, padx=15, pady=10, sticky="ew")
        
        self.add_eng_btn = ctk.CTkButton(btn_frame_eng, text="Add Test Engrave", width=120, fg_color="gray30", hover_color="gray40", command=self._add_eng_test_run)
        self.add_eng_btn.pack(side="left", padx=10)
        
        self.clear_eng_btn = ctk.CTkButton(btn_frame_eng, text="Clear All", width=100, fg_color="#A83232", hover_color="#C03939", command=self._clear_eng_test_runs)
        self.clear_eng_btn.pack(side="left", padx=10)

        # Runs display box
        ctk.CTkLabel(eng_card, text="Added Engraving Test Runs (Click 'X' to remove outliers):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=6, column=0, columnspan=2, padx=15, pady=(5, 0), sticky="w")
        self.eng_runs_frame = ctk.CTkScrollableFrame(eng_card, height=120, corner_radius=6, border_width=1, border_color="gray40")
        self.eng_runs_frame.grid(row=7, column=0, columnspan=2, padx=15, pady=(2, 10), sticky="nsew")

        # Solve & Stats Card
        stats_frame_eng = ctk.CTkFrame(eng_card, corner_radius=6, fg_color="gray20")
        stats_frame_eng.grid(row=8, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="ew")
        stats_frame_eng.grid_columnconfigure((0, 1), weight=1)

        self.solve_eng_btn = ctk.CTkButton(stats_frame_eng, text="Solve Calibrations", command=self._solve_engrave_calibration)
        self.solve_eng_btn.grid(row=0, column=0, columnspan=2, padx=15, pady=10, sticky="ew")

        self.lbl_eng_avg = ctk.CTkLabel(stats_frame_eng, text="Average Factor: N/A", font=ctk.CTkFont(weight="bold"))
        self.lbl_eng_avg.grid(row=1, column=0, padx=15, pady=2, sticky="w")

        self.lbl_eng_std = ctk.CTkLabel(stats_frame_eng, text="Std. Deviation (\u03c3): N/A")
        self.lbl_eng_std.grid(row=1, column=1, padx=15, pady=2, sticky="w")

        self.lbl_eng_range = ctk.CTkLabel(stats_frame_eng, text="Overall Range: N/A")
        self.lbl_eng_range.grid(row=2, column=0, columnspan=2, padx=15, pady=(2, 10), sticky="w")

    # ==================== TAB 3: MATERIALS EXPLORER ====================
    def _build_explorer_tab(self):
        self.tab_explorer.grid_columnconfigure(0, weight=1)
        self.tab_explorer.grid_rowconfigure(1, weight=1)

        # Dropdowns top bar
        top_bar = ctk.CTkFrame(self.tab_explorer, corner_radius=8, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(top_bar, text="Material Name:").pack(side="left", padx=10)
        
        self.explore_material_dropdown = ctk.CTkOptionMenu(
            top_bar, 
            values=["Birch Plywood", "Acrylic (Clear/Cast)", "MDF", "Cardboard", "Leather (Veg-Tanned)"],
            command=self._update_explorer_grid
        )
        self.explore_material_dropdown.pack(side="left", padx=10)

        # Dynamic table display
        self.grid_frame = ctk.CTkScrollableFrame(self.tab_explorer, corner_radius=8, fg_color="gray15")
        self.grid_frame.grid(row=1, column=0, padx=15, pady=15, sticky="nsew")
        
        self._update_explorer_grid()

    def _update_explorer_grid(self, *args):
        # Clear previous grid items
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        material = self.explore_material_dropdown.get()
        laser_type = self.selected_laser_type.get()
        
        laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
        if not laser_data:
            ctk.CTkLabel(self.grid_frame, text=f"No default materials loaded for laser type: {laser_type}").pack(padx=20, pady=20)
            return

        is_metric = "Metric" in self.unit_system.get()
        unit_len = "mm" if is_metric else "in"
        unit_spd = "mm/s" if is_metric else "in/s"

        # Convert machine constraints to metric for the math engine
        v_max_cut_metric = self.max_speed.get() if is_metric else self.max_speed.get() * 25.4
        v_max_eng_metric = self.max_speed_eng.get() if is_metric else self.max_speed_eng.get() * 25.4
        p_min = self.min_power.get()
        p_max = self.max_power.get()

        # Header Titles
        headers = [f"Thickness ({unit_len})", "Task Type", "Power", "Passes", f"Speed ({unit_spd})", f"Interval ({unit_len})"]
        for col_idx, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.grid_frame, text=text, font=ctk.CTkFont(weight="bold"), fg_color="#1F6AA5", corner_radius=4)
            lbl.grid(row=0, column=col_idx, padx=10, pady=10, sticky="ew")
            self.grid_frame.grid_columnconfigure(col_idx, weight=1)

        row_idx = 1

        if self.loaded_library_data is not None:
            # We have a loaded library
            matching_mat = next((m for m in self.loaded_library_data["materials"] if m["name"] == material), None)
            if not matching_mat:
                # Clear headers and display warning
                for widget in self.grid_frame.winfo_children():
                    widget.destroy()
                ctk.CTkLabel(self.grid_frame, text="This material has no entries in the loaded library").pack(padx=20, pady=20)
                return
            
            standard_mat_name = self.parser._map_to_standard_material(material)
            in_ref_db = standard_mat_name in laser_data.get("materials", {})

            for entry in matching_mat.get("entries", []):
                if entry["type"] == "Cut":
                    thick = entry["thickness"]
                    pow_val = entry["power"]
                    pass_val = entry["passes"]
                    
                    c_mat_override = None
                    if not in_ref_db:
                        c_mat_override = self.engine.calculate_material_cut_constant(
                            thickness=max(0.1, thick),
                            speed=entry["speed"],
                            power=pow_val,
                            passes=pass_val,
                            wattage=40.0
                        )
                        
                    pred = self.engine.predict_cutting_settings(
                        thickness=max(0.1, thick),
                        material_name=standard_mat_name,
                        target_power=pow_val,
                        target_passes=pass_val,
                        user_wattage=self.user_wattage.get(),
                        kappa_cut=self.kappa_cut.get(),
                        reference_materials=laser_data.get("materials", {}),
                        laser_type=laser_type,
                        v_max=v_max_cut_metric,
                        p_min=p_min,
                        p_max=p_max,
                        c_mat_override=c_mat_override
                    )
                    
                    if pred is not None:
                        disp_spd = pred["speed"] if is_metric else round(pred["speed"] / 25.4, 3)
                        disp_pow = pred["power"]
                        disp_pass = pred["passes"]
                    else:
                        disp_spd, disp_pow, disp_pass = "--", "--", "--"
                    
                    thick_disp = thick if is_metric else round(thick / 25.4, 3)
                    ctk.CTkLabel(self.grid_frame, text=f"{thick_disp:.1f}{unit_len} (Cut)", text_color=self.cut_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=entry.get("desc", "Vector Cut") or "Vector Cut", text_color=self.cut_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=1, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=f"{disp_pow}%").grid(row=row_idx, column=2, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=str(disp_pass)).grid(row=row_idx, column=3, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=f"{disp_spd} {unit_spd}", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=4, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text="--").grid(row=row_idx, column=5, padx=5, pady=5)
                    row_idx += 1
                    
                elif entry["type"] == "Scan":
                    mode = entry.get("no_thick_title") or entry.get("desc") or "Standard Engrave"
                    pow_val = entry["power"]
                    interval = entry["interval"]
                    
                    e_ref_override = None
                    if not in_ref_db:
                        e_ref_override = self.engine.calculate_material_engrave_constant(
                            speed=entry["speed"],
                            power=pow_val,
                            interval=interval,
                            wattage=40.0
                        )
                        
                    pred_eng = self.engine.predict_engraving_settings(
                        material_name=standard_mat_name,
                        mode=mode,
                        target_power=pow_val,
                        target_interval=interval,
                        user_wattage=self.user_wattage.get(),
                        kappa_eng=self.kappa_eng.get(),
                        reference_materials=laser_data.get("materials", {}),
                        laser_type=laser_type,
                        v_max=v_max_eng_metric,
                        p_min=p_min,
                        p_max=p_max,
                        e_ref_override=e_ref_override
                    )
                    
                    if pred_eng is not None:
                        disp_spd = pred_eng["speed"] if is_metric else round(pred_eng["speed"] / 25.4, 3)
                        disp_pow = pred_eng["power"]
                        disp_int = pred_eng["interval_mm"] if is_metric else round(pred_eng["interval_mm"] / 25.4, 4)
                    else:
                        disp_spd, disp_pow, disp_int = "--", "--", "--"
                    
                    ctk.CTkLabel(self.grid_frame, text=f"{mode} (Engrave)", text_color=self.engrave_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=mode, text_color=self.engrave_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=1, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=f"{disp_pow}%").grid(row=row_idx, column=2, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text="--").grid(row=row_idx, column=3, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=f"{disp_spd} {unit_spd}", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=4, padx=5, pady=5)
                    ctk.CTkLabel(self.grid_frame, text=f"{disp_int} {unit_len}").grid(row=row_idx, column=5, padx=5, pady=5)
                    row_idx += 1
        else:
            # We do NOT have a loaded library; use default database
            mat_info = laser_data.get("materials", {}).get(material, {})
            if not mat_info:
                # Clear headers and display warning
                for widget in self.grid_frame.winfo_children():
                    widget.destroy()
                ctk.CTkLabel(self.grid_frame, text="This material is transparent/unsuitable for this wavelength").pack(padx=20, pady=20)
                return

            # 1. Add Cutting Values
            for cut in mat_info.get("cutting", []):
                thick = cut["thickness_mm"]
                pow_val = cut["ref_power"]
                pass_val = cut["ref_passes"]
                
                # Predict cut settings with safety bounds
                pred = self.engine.predict_cutting_settings(
                    thickness=thick,
                    material_name=material,
                    target_power=pow_val,
                    target_passes=pass_val,
                    user_wattage=self.user_wattage.get(),
                    kappa_cut=self.kappa_cut.get(),
                    reference_materials=laser_data.get("materials", {}),
                    laser_type=laser_type,
                    v_max=v_max_cut_metric,
                    p_min=p_min,
                    p_max=p_max
                )
                
                if pred is not None:
                    disp_spd = pred["speed"] if is_metric else round(pred["speed"] / 25.4, 3)
                    disp_pow = pred["power"]
                    disp_pass = pred["passes"]
                else:
                    disp_spd, disp_pow, disp_pass = "--", "--", "--"
                
                thick_disp = thick if is_metric else round(thick / 25.4, 3)
                ctk.CTkLabel(self.grid_frame, text=f"{thick_disp:.1f}{unit_len} (Cut)", text_color=self.cut_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text="Vector Cut", text_color=self.cut_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=1, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=f"{disp_pow}%").grid(row=row_idx, column=2, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=str(disp_pass)).grid(row=row_idx, column=3, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=f"{disp_spd} {unit_spd}", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=4, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text="--").grid(row=row_idx, column=5, padx=5, pady=5)
                row_idx += 1

            # 2. Add Engraving Values
            for eng in mat_info.get("engraving", []):
                mode = eng["mode"]
                pow_val = eng["ref_power"]
                interval = eng["interval_mm"]
                
                # Predict engrave settings with safety bounds
                pred_eng = self.engine.predict_engraving_settings(
                    material_name=material,
                    mode=mode,
                    target_power=pow_val,
                    target_interval=interval,
                    user_wattage=self.user_wattage.get(),
                    kappa_eng=self.kappa_eng.get(),
                    reference_materials=laser_data.get("materials", {}),
                    laser_type=laser_type,
                    v_max=v_max_eng_metric,
                    p_min=p_min,
                    p_max=p_max
                )
                
                if pred_eng is not None:
                    disp_spd = pred_eng["speed"] if is_metric else round(pred_eng["speed"] / 25.4, 3)
                    disp_pow = pred_eng["power"]
                    disp_int = pred_eng["interval_mm"] if is_metric else round(pred_eng["interval_mm"] / 25.4, 4)
                else:
                    disp_spd, disp_pow, disp_int = "--", "--", "--"
                
                ctk.CTkLabel(self.grid_frame, text=f"{mode} (Engrave)", text_color=self.engrave_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=mode, text_color=self.engrave_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=1, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=f"{disp_pow}%").grid(row=row_idx, column=2, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text="--").grid(row=row_idx, column=3, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=f"{disp_spd} {unit_spd}", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=4, padx=5, pady=5)
                ctk.CTkLabel(self.grid_frame, text=f"{disp_int} {unit_len}").grid(row=row_idx, column=5, padx=5, pady=5)
                row_idx += 1
            
        # Re-trigger Analytics tab updates in real-time
        self._update_analytics_tab()

    # ==================== TAB 3.5: SPECIFIC ENERGY ANALYTICS ====================
    def _build_analytics_tab(self):
        self.tab_analytics.grid_columnconfigure(0, weight=1)
        self.tab_analytics.grid_rowconfigure(2, weight=1)

        # Dropdowns top bar
        top_bar = ctk.CTkFrame(self.tab_analytics, corner_radius=8, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(top_bar, text="Select Analytics Material:").pack(side="left", padx=10)
        
        self.analytics_material_dropdown = ctk.CTkOptionMenu(
            top_bar, 
            values=["Birch Plywood", "Acrylic (Clear/Cast)", "MDF", "Cardboard", "Leather (Veg-Tanned)"],
            command=lambda e: self._update_analytics_tab()
        )
        self.analytics_material_dropdown.pack(side="left", padx=10)

        # Segmented toggle button for Vector Cut vs Raster Engrave analytics view
        self.analytics_toggle = ctk.CTkSegmentedButton(
            top_bar,
            values=["Vector Cut", "Raster Engrave"],
            command=lambda e: self._update_analytics_tab()
        )
        self.analytics_toggle.set("Vector Cut")
        self.analytics_toggle.pack(side="left", padx=20)

        # Thermodynamic Science Note Card
        self.science_card = ctk.CTkFrame(self.tab_analytics, corner_radius=8, fg_color="gray12", border_width=1, border_color="#1F6AA5")
        self.science_card.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        self.science_lbl = ctk.CTkLabel(
            self.science_card,
            text="",
            justify="left",
            wraplength=780,
            font=ctk.CTkFont(size=11, slant="italic")
        )
        self.science_lbl.pack(padx=15, pady=10, fill="x")

        # Grid view container
        self.analytics_frame = ctk.CTkScrollableFrame(self.tab_analytics, corner_radius=8, fg_color="gray15")
        self.analytics_frame.grid(row=2, column=0, padx=15, pady=15, sticky="nsew")

    def _update_analytics_tab(self):
        if not hasattr(self, "analytics_frame") or not self.analytics_frame.winfo_exists():
            return
            
        # Clear frame
        for widget in self.analytics_frame.winfo_children():
            widget.destroy()

        material = self.analytics_material_dropdown.get()
        laser_type = self.selected_laser_type.get()
        
        laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
        if not laser_data:
            ctk.CTkLabel(self.analytics_frame, text=f"No default materials loaded for laser type: {laser_type}").pack(padx=20, pady=20)
            return

        is_metric = "Metric" in self.unit_system.get()
        unit_len = "mm" if is_metric else "in"
        unit_spd = "mm/s" if is_metric else "in/s"
        unit_el = "J/mm" if is_metric else "J/in"

        is_cut = (self.analytics_toggle.get() == "Vector Cut")
        if is_cut:
            unit_ev = "J/mm³" if is_metric else "J/in³"
            ev_tooltip_desc = "Specific Energy (volumetric energy density): thermodynamic energy per unit volume required to vaporize the material (J/mm³ or J/in³)."
            calib_ev_tooltip_desc = "Calibrated Specific Energy: volumetric energy density evaluated on your target machine (includes focal length scaling)."
            diff_tooltip_desc = "Percentage difference in Specific Energy between target machine and reference. Positive = higher heat input; Negative = lower heat input."
        else:
            unit_ev = "J/mm²" if is_metric else "J/in²"
            ev_tooltip_desc = "Areal Energy Density: thermodynamic energy per unit area deposited on the material surface (J/mm² or J/in²)."
            calib_ev_tooltip_desc = "Calibrated Areal Energy Density: thermal energy per unit area evaluated on your target machine."
            diff_tooltip_desc = "Percentage difference in Areal Energy Density between target machine and reference. Positive = higher heat input; Negative = lower heat input."

        if is_cut:
            science_text = (
                "💡 Thermodynamic Science Note (Vector Cut mode):\n"
                "Cutting is a bulk subtractive process that vaporizes a 3D channel of material equal to [Thickness × Kerf Width × Length]. "
                "Therefore, we evaluate Volumetric Specific Energy (Ev) in Joules per cubic millimeter (J/mm³ or J/in³), which indicates "
                "the absolute energy required to sublime the bulk mass. Linear Energy (El in J/mm or J/in) is also shown, representing "
                "the thermal heat load along the cut line (critical for predicting charring)."
            )
            border_col = self.cut_color if hasattr(self, "cut_color") else "#1F6AA5"
        else:
            science_text = (
                "💡 Thermodynamic Science Note (Raster Engrave mode):\n"
                "Engraving is a surface vaporization process where depth is not mechanically constrained but is a dependent variable. "
                "Therefore, we evaluate Areal Energy Density (Ea) in Joules per square millimeter (J/mm² or J/in²), representing the energy "
                "delivered per unit surface area. Spot size (kerf) is omitted from this division as overlapping raster passes form a continuous plane. "
                "Linear Energy (El in J/mm or J/in) represents the transient energy density along the laser stroke."
            )
            border_col = self.engrave_color if hasattr(self, "engrave_color") else "#5CB85C"

        if hasattr(self, "science_lbl") and self.science_lbl.winfo_exists():
            self.science_lbl.configure(text=science_text)
        if hasattr(self, "science_card") and self.science_card.winfo_exists():
            self.science_card.configure(border_color=border_col)

        # Convert machine constraints to metric for the math engine
        v_max_cut_metric = self.max_speed.get() if is_metric else self.max_speed.get() * 25.4
        v_max_eng_metric = self.max_speed_eng.get() if is_metric else self.max_speed_eng.get() * 25.4
        p_min = self.min_power.get()
        p_max = self.max_power.get()

        # Header Titles
        headers = [
            "Thickness/Mode", "Library Settings", f"Lib Ev ({unit_ev})" if is_cut else f"Lib Ea ({unit_ev})", f"Lib El ({unit_el})", 
            "Calibrated Settings", f"Calib Ev ({unit_ev})" if is_cut else f"Calib Ea ({unit_ev})", f"Calib El ({unit_el})", "Net Heat Ratio"
        ]
        tooltips = [
            "Material thickness (for cutting) or engraving speed-power mode from the library.",
            "The original raw speed and power settings defined in the loaded reference library.",
            ev_tooltip_desc,
            "Linear Energy Density: thermal heat energy deposited per unit length of cut/engrave along the toolpath (J/mm or J/in).",
            "Speed and power values adjusted for your machine constraints, wattage scaling, and machine factors.",
            calib_ev_tooltip_desc,
            "Calibrated Linear Energy Density: thermal energy per unit length evaluated on your target machine.",
            diff_tooltip_desc
        ]
        for col_idx, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.analytics_frame, text=text, font=ctk.CTkFont(size=11, weight="bold"), fg_color="#1F6AA5", corner_radius=4)
            lbl.grid(row=0, column=col_idx, padx=5, pady=10, sticky="ew")
            self.analytics_frame.grid_columnconfigure(col_idx, weight=1)
            ToolTip(lbl, tooltips[col_idx])

        row_idx = 1
        w_base = self.laser_kerf.get()
        
        try:
            focal_val = float(self.lens_focal.get())
        except ValueError:
            focal_val = 50.8 if is_metric else 2.0

        standard_mat_name = self.parser._map_to_standard_material(material)
        in_ref_db = standard_mat_name in laser_data.get("materials", {})

        dataset = []
        if self.loaded_library_data is not None:
            # Load entries from XML library
            matching_mat = next((m for m in self.loaded_library_data["materials"] if m["name"] == material), None)
            if matching_mat:
                for entry in matching_mat.get("entries", []):
                    if self.analytics_toggle.get() == "Vector Cut" and entry["type"] == "Cut":
                        dataset.append({
                            "is_cut": True,
                            "thickness": entry["thickness"],
                            "ref_speed": entry["speed"],
                            "ref_power": entry["power"],
                            "ref_passes": entry["passes"],
                            "ref_interval": entry["interval"],
                            "desc": entry.get("desc", "Vector Cut") or "Vector Cut"
                        })
                    elif self.analytics_toggle.get() == "Raster Engrave" and entry["type"] == "Scan":
                        dataset.append({
                            "is_cut": False,
                            "thickness": entry["thickness"],
                            "ref_speed": entry["speed"],
                            "ref_power": entry["power"],
                            "ref_passes": entry["passes"],
                            "ref_interval": entry["interval"],
                            "desc": entry.get("no_thick_title") or entry.get("desc") or "Standard Engrave"
                        })
        else:
            # Load entries from database
            mat_info = laser_data.get("materials", {}).get(material, {})
            if mat_info:
                if self.analytics_toggle.get() == "Vector Cut":
                    for cut in mat_info.get("cutting", []):
                        dataset.append({
                            "is_cut": True,
                            "thickness": cut["thickness_mm"],
                            "ref_speed": cut["ref_speed"],
                            "ref_power": cut["ref_power"],
                            "ref_passes": cut["ref_passes"],
                            "ref_interval": 0.08,
                            "desc": "Vector Cut"
                        })
                else:
                    for eng in mat_info.get("engraving", []):
                        dataset.append({
                            "is_cut": False,
                            "thickness": 0.0,
                            "ref_speed": eng["ref_speed"],
                            "ref_power": eng["ref_power"],
                            "ref_passes": 1,
                            "ref_interval": eng["interval_mm"],
                            "desc": eng["mode"]
                        })

        if not dataset:
            ctk.CTkLabel(self.analytics_frame, text="No analytical entries available for current selection.").grid(row=1, column=0, columnspan=8, padx=20, pady=20)
            return

        for item in dataset:
            is_cut = item["is_cut"]
            ref_speed = item["ref_speed"]
            pow_val = item["ref_power"]
            thick = item["thickness"]
            pass_val = item["ref_passes"]
            interval = item["ref_interval"]
            desc = item["desc"]
            
            # Setup values based on unit system
            ref_speed_calc = ref_speed if is_metric else ref_speed / 25.4
            thick_calc = thick if is_metric else thick / 25.4
            interval_calc = interval if is_metric else interval / 25.4
            
            if is_cut:
                ref_ev = self.engine.calculate_specific_energy_cut(
                    speed=ref_speed_calc,
                    power=pow_val,
                    thickness=thick_calc,
                    kerf=w_base,
                    wattage=40.0,
                    focal_length=None,
                    units="metric" if is_metric else "imperial"
                )
            else:
                ref_ev = self.engine.calculate_specific_energy_engrave(
                    speed=ref_speed_calc,
                    power=pow_val,
                    interval=interval_calc,
                    kerf=w_base,
                    wattage=40.0,
                    focal_length=None,
                    units="metric" if is_metric else "imperial"
                )
                
            ref_el = self.engine.calculate_linear_energy_density(
                speed=ref_speed_calc,
                power=pow_val,
                wattage=40.0
            )
            
            # Predict settings
            if is_cut:
                c_mat_override = None
                if self.loaded_library_data is not None and not in_ref_db:
                    c_mat_override = self.engine.calculate_material_cut_constant(
                        thickness=max(0.1, thick),
                        speed=ref_speed,
                        power=pow_val,
                        passes=pass_val,
                        wattage=40.0
                    )
                pred = self.engine.predict_cutting_settings(
                    thickness=max(0.1, thick),
                    material_name=standard_mat_name,
                    target_power=pow_val,
                    target_passes=pass_val,
                    user_wattage=self.user_wattage.get(),
                    kappa_cut=self.kappa_cut.get(),
                    reference_materials=laser_data.get("materials", {}),
                    laser_type=laser_type,
                    v_max=v_max_cut_metric,
                    p_min=p_min,
                    p_max=p_max,
                    c_mat_override=c_mat_override
                )
            else:
                e_ref_override = None
                if self.loaded_library_data is not None and not in_ref_db:
                    e_ref_override = self.engine.calculate_material_engrave_constant(
                        speed=ref_speed,
                        power=pow_val,
                        interval=interval,
                        wattage=40.0
                    )
                pred = self.engine.predict_engraving_settings(
                    material_name=standard_mat_name,
                    mode=desc,
                    target_power=pow_val,
                    target_interval=interval,
                    user_wattage=self.user_wattage.get(),
                    kappa_eng=self.kappa_eng.get(),
                    reference_materials=laser_data.get("materials", {}),
                    laser_type=laser_type,
                    v_max=v_max_eng_metric,
                    p_min=p_min,
                    p_max=p_max,
                    e_ref_override=e_ref_override
                )
                
            if pred is not None:
                cal_spd_metric = pred["speed"]
                cal_pow = pred["power"]
                cal_spd_calc = cal_spd_metric if is_metric else cal_spd_metric / 25.4
                
                if is_cut:
                    cal_ev = self.engine.calculate_specific_energy_cut(
                        speed=cal_spd_calc,
                        power=cal_pow,
                        thickness=thick_calc,
                        kerf=w_base,
                        wattage=self.user_wattage.get(),
                        focal_length=focal_val,
                        units="metric" if is_metric else "imperial"
                    )
                else:
                    cal_ev = self.engine.calculate_specific_energy_engrave(
                        speed=cal_spd_calc,
                        power=cal_pow,
                        interval=interval_calc,
                        kerf=w_base,
                        wattage=self.user_wattage.get(),
                        focal_length=focal_val,
                        units="metric" if is_metric else "imperial"
                    )
                
                cal_el = self.engine.calculate_linear_energy_density(
                    speed=cal_spd_calc,
                    power=cal_pow,
                    wattage=self.user_wattage.get()
                )
                
                ratio = cal_ev / ref_ev if ref_ev > 0 else 1.0
                ratio_pct = (ratio - 1.0) * 100.0
                ratio_str = f"{ratio_pct:+.1f}%"
                ratio_color = "#D9534F" if ratio_pct > 12.0 else "#5CB85C"
                
                is_large_deviation = abs(ratio_pct) > 25.0
                if is_large_deviation:
                    ratio_str = f"⚠️ {ratio_str}"
                    ratio_color = "#FF9F43" # Amber warning alert
                
                cal_spd_disp = cal_spd_metric if is_metric else round(cal_spd_metric / 25.4, 3)
                disp_cal_settings = f"{cal_spd_disp:.2f}{unit_spd} @ {cal_pow}%"
                disp_cal_ev = f"{cal_ev:.2f}"
                disp_cal_el = f"{cal_el:.2f}"
            else:
                is_large_deviation = False
                disp_cal_settings = "--"
                disp_cal_ev = "--"
                disp_cal_el = "--"
                ratio_str = "--"
                ratio_color = "white"
                
            ref_spd_disp = ref_speed if is_metric else round(ref_speed / 25.4, 3)
            if is_cut:
                thick_disp = thick if is_metric else round(thick / 25.4, 3)
                first_col_text = f"{thick_disp:.1f}{unit_len} (Cut)"
                first_col_color = self.cut_color
            else:
                interval_disp = interval if is_metric else round(interval / 25.4, 4)
                first_col_text = f"{desc} (Engrave)"
                first_col_color = self.engrave_color
                
            ctk.CTkLabel(self.analytics_frame, text=first_col_text, text_color=first_col_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=5, pady=5)
            ctk.CTkLabel(self.analytics_frame, text=f"{ref_spd_disp:.2f}{unit_spd} @ {pow_val}%", text_color=first_col_color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=1, padx=5, pady=5)
            ctk.CTkLabel(self.analytics_frame, text=f"{ref_ev:.2f}").grid(row=row_idx, column=2, padx=5, pady=5)
            ctk.CTkLabel(self.analytics_frame, text=f"{ref_el:.2f}").grid(row=row_idx, column=3, padx=5, pady=5)
            ctk.CTkLabel(self.analytics_frame, text=disp_cal_settings).grid(row=row_idx, column=4, padx=5, pady=5)
            ctk.CTkLabel(self.analytics_frame, text=disp_cal_ev, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=5, padx=5, pady=5)
            ctk.CTkLabel(self.analytics_frame, text=disp_cal_el).grid(row=row_idx, column=6, padx=5, pady=5)
            
            lbl_ratio = ctk.CTkLabel(self.analytics_frame, text=ratio_str, text_color=ratio_color, font=ctk.CTkFont(weight="bold"))
            lbl_ratio.grid(row=row_idx, column=7, padx=5, pady=5)
            
            if is_large_deviation:
                tooltip_text = (
                    "Large thermodynamic deviation detected. The source library setting deviates "
                    "significantly from verified physical benchmarks (e.g. too fast for thickness, or delivering "
                    "insufficient cut energy). The math engine has corrected this to ensure a successful cut."
                )
                ToolTip(lbl_ratio, tooltip_text)
                
            row_idx += 1


    # ==================== TAB 4: IMPORT / EXPORT ====================
    def _build_import_tab(self):
        self.tab_import.grid_columnconfigure(0, weight=1)
        self.tab_import.grid_rowconfigure((1, 2), weight=1)

        # Top descriptive label
        lbl = ctk.CTkLabel(
            self.tab_import, 
            text="Load a public LightBurn library (.clb) from your disk. The program will adjust all of its entries to suit your machine parameters.",
            wraplength=700
        )
        lbl.grid(row=0, column=0, padx=15, pady=15, sticky="w")

        # Import File Card
        imp_card = ctk.CTkFrame(self.tab_import, corner_radius=8, fg_color="gray15")
        imp_card.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)

        imp_title = ctk.CTkLabel(imp_card, text="Step 1: Load Reference Library File", font=ctk.CTkFont(size=14, weight="bold"))
        imp_title.pack(anchor="w", padx=15, pady=15)

        self.file_path_label = ctk.CTkLabel(imp_card, text="No Library file loaded currently.", font=ctk.CTkFont(size=11, slant="italic"))
        self.file_path_label.pack(anchor="w", padx=20, pady=5)

        self.load_btn = ctk.CTkButton(imp_card, text="Browse library (.clb/.clib)", command=self._browse_library)
        self.load_btn.pack(anchor="w", padx=20, pady=10)

        # Export Options Card
        exp_card = ctk.CTkFrame(self.tab_import, corner_radius=8, fg_color="gray15")
        exp_card.grid(row=2, column=0, sticky="nsew", padx=15, pady=15)

        exp_title = ctk.CTkLabel(exp_card, text="Step 2: Generate Customized Libraries", font=ctk.CTkFont(size=14, weight="bold"))
        exp_title.pack(anchor="w", padx=15, pady=15)

        # High Power Normalization Controls Frame
        norm_frame = ctk.CTkFrame(exp_card, fg_color="transparent")
        norm_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.chk_norm = ctk.CTkCheckBox(
            norm_frame, 
            text="Enable High-Power Normalization (reduces speed to match energy under cap)", 
            variable=self.normalize_high_power,
            command=self._on_norm_toggle
        )
        self.chk_norm.pack(side="left", padx=5)

        self.lbl_norm_cap = ctk.CTkLabel(norm_frame, text="Cap Power at:")
        self.lbl_norm_cap.pack(side="left", padx=(20, 5))

        self.entry_norm_cap = ctk.CTkEntry(norm_frame, textvariable=self.power_cap_percentage, width=50)
        self.entry_norm_cap.pack(side="left", padx=5)

        ctk.CTkLabel(norm_frame, text="%").pack(side="left")

        # Export Buttons Container
        btn_container = ctk.CTkFrame(exp_card, fg_color="transparent")
        btn_container.pack(fill="x", padx=20, pady=5)

        self.export_lb_btn = ctk.CTkButton(btn_container, text="Export scaled LightBurn Library (.clb)", state="disabled", command=self._export_scaled_clb)
        self.export_lb_btn.pack(side="left", padx=5, pady=5)

        self.export_k40_btn = ctk.CTkButton(btn_container, text="Export K40 Whisperer cheat sheet (.txt)", state="disabled", command=self._export_k40_cheat_sheet)
        self.export_k40_btn.pack(side="left", padx=5, pady=5)

    # ==================== INTERACTION LOGIC ====================
    def _on_unit_system_changed(self, new_unit, convert=True):
        is_metric = "Metric" in new_unit
        
        # 1. Update sidebar labels
        if is_metric:
            self.max_speed_label.configure(text="Max Cut Speed (mm/s):")
            self.max_speed_eng_label.configure(text="Max Engrave Speed (mm/s):")
            self.kerf_label.configure(text="Laser Kerf Width (mm):")
            self.focal_label.configure(text="Lens Focal Length (mm):")
            
            # Convert values from Imperial to Metric
            if convert:
                self.max_speed.set(round(self.max_speed.get() * 25.4, 1))
                self.max_speed_eng.set(round(self.max_speed_eng.get() * 25.4, 1))
                self.laser_kerf.set(round(self.laser_kerf.get() * 25.4, 4))
            
            # Focal Length Option Menu
            old_focal = self.lens_focal.get()
            self.focal_option.configure(values=["38.1", "50.8", "63.5"])
            if convert:
                try:
                    val_mm = round(float(old_focal) * 25.4, 1)
                    self.lens_focal.set(str(val_mm))
                except ValueError:
                    self.lens_focal.set("50.8")
        else:
            self.max_speed_label.configure(text="Max Cut Speed (in/s):")
            self.max_speed_eng_label.configure(text="Max Engrave Speed (in/s):")
            self.kerf_label.configure(text="Laser Kerf Width (in):")
            self.focal_label.configure(text="Lens Focal Length (in):")
            
            # Convert values from Metric to Imperial
            if convert:
                self.max_speed.set(round(self.max_speed.get() / 25.4, 3))
                self.max_speed_eng.set(round(self.max_speed_eng.get() / 25.4, 3))
                self.laser_kerf.set(round(self.laser_kerf.get() / 25.4, 5))
            
            # Focal Length Option Menu
            old_focal = self.lens_focal.get()
            self.focal_option.configure(values=["1.5", "2.0", "2.5"])
            if convert:
                try:
                    val_in = round(float(old_focal) / 25.4, 1)
                    self.lens_focal.set(str(val_in))
                except ValueError:
                    self.lens_focal.set("2.0")
                
        # 2. Update Calibration Wizard labels
        self._update_wizard_labels(convert=convert)
        
        # 3. Refresh grids
        self._update_explorer_grid()
        self._update_analytics_tab()

    def _update_wizard_labels(self, convert=True):
        is_metric = "Metric" in self.unit_system.get()
        if not hasattr(self, "wiz_cut_thick_label"):
            return
        if is_metric:
            self.wiz_cut_thick_label.configure(text="Material Thickness (mm):")
            self.wiz_cut_speed_label.configure(text="Optimal Speed (mm/s):")
            self.wiz_eng_speed_label.configure(text="Optimal Speed (mm/s):")
            
            if convert:
                try:
                    thick = float(self.wiz_cut_thick.get())
                    self.wiz_cut_thick.delete(0, tk.END)
                    self.wiz_cut_thick.insert(0, str(round(thick * 25.4, 2)))
                except ValueError:
                    pass
                try:
                    spd = float(self.wiz_cut_speed.get())
                    self.wiz_cut_speed.delete(0, tk.END)
                    self.wiz_cut_speed.insert(0, str(round(spd * 25.4, 2)))
                except ValueError:
                    pass
                try:
                    spd_eng = float(self.wiz_eng_speed.get())
                    self.wiz_eng_speed.delete(0, tk.END)
                    self.wiz_eng_speed.insert(0, str(round(spd_eng * 25.4, 2)))
                except ValueError:
                    pass
        else:
            self.wiz_cut_thick_label.configure(text="Material Thickness (in):")
            self.wiz_cut_speed_label.configure(text="Optimal Speed (in/s):")
            self.wiz_eng_speed_label.configure(text="Optimal Speed (in/s):")
            
            if convert:
                try:
                    thick = float(self.wiz_cut_thick.get())
                    self.wiz_cut_thick.delete(0, tk.END)
                    self.wiz_cut_thick.insert(0, str(round(thick / 25.4, 3)))
                except ValueError:
                    pass
                try:
                    spd = float(self.wiz_cut_speed.get())
                    self.wiz_cut_speed.delete(0, tk.END)
                    self.wiz_cut_speed.insert(0, str(round(spd / 25.4, 3)))
                except ValueError:
                    pass
                try:
                    spd_eng = float(self.wiz_eng_speed.get())
                    self.wiz_eng_speed.delete(0, tk.END)
                    self.wiz_eng_speed.insert(0, str(round(spd_eng / 25.4, 3)))
                except ValueError:
                    pass

    def _on_laser_type_changed(self, *args):
        laser = self.selected_laser_type.get()
        if laser == "CO2":
            self.user_wattage.set(40.0)
        elif laser == "Diode":
            self.user_wattage.set(10.0)
        elif laser == "Fiber":
            self.user_wattage.set(30.0)
        self._update_material_dropdown_options()
        self._update_explorer_grid()

    def _on_slider_changed(self, *args):
        # Update text output values next to sliders
        self.k_cut_val_label.configure(text=f"{self.kappa_cut.get():.2f}x")
        self.k_eng_val_label.configure(text=f"{self.kappa_eng.get():.2f}x")
        
        # Calculate health meter estimations
        self._update_health_meters()
        self._update_explorer_grid()

    def _update_health_meters(self):
        # Cut Health gauge
        kc = self.kappa_cut.get()
        # Normal range is 0.5 to 1.5. Below 0.7 means alignment/optics issues.
        if kc < 0.7:
            status_cut = f"Optics Issues / Low Power ({kc:.2f}x)"
            self.cut_health_progress.configure(progress_color="red")
        elif kc > 1.3:
            status_cut = f"High Performance / Tube Boosted ({kc:.2f}x)"
            self.cut_health_progress.configure(progress_color="green")
        else:
            status_cut = f"Optimal Alignment ({kc:.2f}x)"
            self.cut_health_progress.configure(progress_color="blue")
            
        self.cut_health_label.configure(text=f"Vector Cut Health: {status_cut}")
        # Scale progress between 0 and 1
        self.cut_health_progress.set(min(1.0, max(0.0, (kc - 0.2) / 1.8)))

        # Engrave Health gauge
        ke = self.kappa_eng.get()
        if ke < 0.7:
            status_eng = f"Focal Blur / Weak Engrave ({ke:.2f}x)"
            self.eng_health_progress.configure(progress_color="red")
        elif ke > 1.3:
            status_eng = f"Sharp Focal Contrast ({ke:.2f}x)"
            self.eng_health_progress.configure(progress_color="green")
        else:
            status_eng = f"Nominal Engraving ({ke:.2f}x)"
            self.eng_health_progress.configure(progress_color="blue")

        self.eng_health_label.configure(text=f"Engraving Calibration: {status_eng}")
        self.eng_health_progress.set(min(1.0, max(0.0, (ke - 0.2) / 1.8)))

    # ==================== CALIBRATION ACTION HANDLERS ====================
    def _add_cut_test_run(self):
        try:
            mat = self.wiz_cut_material.get()
            d = float(self.wiz_cut_thick.get())
            v = float(self.wiz_cut_speed.get())
            p = float(self.wiz_cut_power.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric variables for thickness, speed, and power.")
            return

        is_metric = "Metric" in self.unit_system.get()
        if not is_metric:
            d = d * 25.4
            v = v * 25.4

        run_info = {
            "material_name": mat,
            "thickness_mm": d,
            "speed": v,
            "power": p,
            "passes": 1,
            "wattage": self.user_wattage.get(),
            "solved_kappa": None,
            "solved_deviation": None
        }
        self.added_cut_tests.append(run_info)
        self._update_cut_runs_display()

    def _remove_cut_run(self, index):
        if 0 <= index < len(self.added_cut_tests):
            self.added_cut_tests.pop(index)
            
            # Reset results for remaining tests since average changes
            for cut in self.added_cut_tests:
                cut["solved_kappa"] = None
                cut["solved_deviation"] = None
                
            self._update_cut_runs_display()
            
            # If runs still exist, automatically run recalibration, else reset stats
            if self.added_cut_tests:
                self._solve_cut_calibration(show_message=False)
            else:
                self.lbl_cut_avg.configure(text="Average Factor: N/A")
                self.lbl_cut_std.configure(text="Std. Deviation (\u03c3): N/A")
                self.lbl_cut_range.configure(text="Overall Range: N/A")

    def _clear_cut_test_runs(self):
        self.added_cut_tests = []
        self._update_cut_runs_display()
        
        self.lbl_cut_avg.configure(text="Average Factor: N/A")
        self.lbl_cut_std.configure(text="Std. Deviation (\u03c3): N/A")
        self.lbl_cut_range.configure(text="Overall Range: N/A")

    def _update_cut_runs_display(self):
        # Clear all child widgets
        for widget in self.cut_runs_frame.winfo_children():
            widget.destroy()

        if not self.added_cut_tests:
            empty_lbl = ctk.CTkLabel(
                self.cut_runs_frame, 
                text="(No cutting tests added yet. Enter values above and click 'Add Test Cut')", 
                font=ctk.CTkFont(slant="italic")
            )
            empty_lbl.pack(padx=10, pady=15)
            return

        is_metric = "Metric" in self.unit_system.get()
        for i, cut in enumerate(self.added_cut_tests):
            row = ctk.CTkFrame(self.cut_runs_frame, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)

            thick_disp = cut['thickness_mm']
            speed_disp = cut['speed']
            unit_len = "mm"
            unit_spd = "mm/s"
            
            if not is_metric:
                thick_disp = round(thick_disp / 25.4, 3)
                speed_disp = round(speed_disp / 25.4, 3)
                unit_len = "in"
                unit_spd = "in/s"

            # Left Details Label
            details_str = f"[{i+1}] {cut['material_name']} {thick_disp}{unit_len}: {speed_disp}{unit_spd} @ {cut['power']}%"
            lbl_details = ctk.CTkLabel(row, text=details_str, anchor="w")
            lbl_details.pack(side="left", padx=5, fill="x", expand=True)

            # Add solved factor and deviation highlight
            if cut.get("solved_kappa") is not None:
                kappa_val = cut["solved_kappa"]
                dev_val = cut["solved_deviation"]
                sign = "+" if dev_val >= 0 else ""
                stats_str = f"\u03ba={kappa_val:.2f}x ({sign}{dev_val:.2f}x)"
                
                # Outliers visual alert: color red if deviation is high (> 0.12), green if low
                lbl_color = "#D9534F" if abs(dev_val) > 0.12 else "#5CB85C"
                lbl_stats = ctk.CTkLabel(
                    row, 
                    text=stats_str, 
                    font=ctk.CTkFont(size=11, weight="bold"), 
                    text_color=lbl_color
                )
                lbl_stats.pack(side="left", padx=10)

            # Delete (X) Button
            del_btn = ctk.CTkButton(
                row, 
                text="X", 
                width=22, 
                height=22, 
                fg_color="#D9534F", 
                hover_color="#C9302C", 
                corner_radius=11, 
                font=ctk.CTkFont(size=10, weight="bold"), 
                command=lambda idx=i: self._remove_cut_run(idx)
            )
            del_btn.pack(side="right", padx=5)

    def _solve_cut_calibration(self, show_message=True):
        laser_type = self.selected_laser_type.get()
        laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
        if not laser_data:
            messagebox.showerror("Error", f"No database found for laser type: {laser_type}")
            return

        active_tests = self.added_cut_tests
        if not active_tests:
            try:
                mat = self.wiz_cut_material.get()
                d = float(self.wiz_cut_thick.get())
                v = float(self.wiz_cut_speed.get())
                p = float(self.wiz_cut_power.get())
                
                is_metric = "Metric" in self.unit_system.get()
                if not is_metric:
                    d = d * 25.4
                    v = v * 25.4
                    
                active_tests = [{
                    "material_name": mat,
                    "thickness_mm": d,
                    "speed": v,
                    "power": p,
                    "passes": 1,
                    "wattage": self.user_wattage.get(),
                    "solved_kappa": None,
                    "solved_deviation": None
                }]
            except ValueError:
                messagebox.showerror("Error", "No test cuts added. Please enter valid numeric values to solve for a single test.")
                return

        # Solve standard regression slope
        solved_k = self.engine.calibrate_machine_cut_factor(
            test_cuts=active_tests,
            reference_materials=laser_data.get("materials", {})
        )

        # Run detailed statistical analysis
        stats = self.engine.analyze_cut_tests(
            test_cuts=active_tests,
            reference_materials=laser_data.get("materials", {})
        )

        if stats["count"] > 0:
            avg_k = stats["average"]
            min_k = stats["min"]
            max_k = stats["max"]
            std_k = stats["std_dev"]
            
            # Map calculated kappas and deviations back to individual runs
            for idx, detail in enumerate(stats["details"]):
                if idx < len(active_tests):
                    active_tests[idx]["solved_kappa"] = detail["kappa"]
                    active_tests[idx]["solved_deviation"] = detail["deviation"]

            # Update stats display labels
            self.lbl_cut_avg.configure(text=f"Average Factor: {avg_k:.2f}x")
            self.lbl_cut_std.configure(text=f"Std. Deviation (\u03c3): {std_k:.2f}")
            self.lbl_cut_range.configure(text=f"Overall Range: [{min_k:.2f}x - {max_k:.2f}x] (n={stats['count']})")
            
            # We set the new Machine Constant to the Average Factor
            self.kappa_cut.set(round(avg_k, 2))
        else:
            self.kappa_cut.set(round(solved_k, 2))

        self._on_slider_changed()
        self._update_cut_runs_display()
        
        if show_message:
            msg = f"Cutting calibration solved using {stats['count']} test run(s)!\n\n"
            msg += f"  * Average Constant: {self.kappa_cut.get():.2f}x\n"
            if stats["count"] > 1:
                msg += f"  * Standard Deviation (\u03c3): {stats['std_dev']:.3f}\n"
                msg += f"  * Range: [{stats['min']:.2f}x to {stats['max']:.2f}x]\n"
                if stats["std_dev"] > 0.12:
                    msg += "\n[WARNING] High variance detected. Identify red-marked outliers and click 'X' to remove them before recalibrating."
            messagebox.showinfo("Cut Calibration Solved", msg)

    # Engrave handlers
    def _add_eng_test_run(self):
        try:
            mat = self.wiz_eng_material.get()
            mode = self.wiz_eng_mode.get()
            v = float(self.wiz_eng_speed.get())
            p = float(self.wiz_eng_power.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric variables for speed and power.")
            return

        is_metric = "Metric" in self.unit_system.get()
        if not is_metric:
            v = v * 25.4

        run_info = {
            "material_name": mat,
            "mode": mode,
            "speed": v,
            "power": p,
            "interval_mm": 0.08,
            "wattage": self.user_wattage.get(),
            "solved_kappa": None,
            "solved_deviation": None
        }
        self.added_eng_tests.append(run_info)
        self._update_eng_runs_display()

    def _remove_eng_run(self, index):
        if 0 <= index < len(self.added_eng_tests):
            self.added_eng_tests.pop(index)
            
            for eng in self.added_eng_tests:
                eng["solved_kappa"] = None
                eng["solved_deviation"] = None
                
            self._update_eng_runs_display()
            
            if self.added_eng_tests:
                self._solve_engrave_calibration(show_message=False)
            else:
                self.lbl_eng_avg.configure(text="Average Factor: N/A")
                self.lbl_eng_std.configure(text="Std. Deviation (\u03c3): N/A")
                self.lbl_eng_range.configure(text="Overall Range: N/A")

    def _clear_eng_test_runs(self):
        self.added_eng_tests = []
        self._update_eng_runs_display()
        
        self.lbl_eng_avg.configure(text="Average Factor: N/A")
        self.lbl_eng_std.configure(text="Std. Deviation (\u03c3): N/A")
        self.lbl_eng_range.configure(text="Overall Range: N/A")

    def _update_eng_runs_display(self):
        for widget in self.eng_runs_frame.winfo_children():
            widget.destroy()

        if not self.added_eng_tests:
            empty_lbl = ctk.CTkLabel(
                self.eng_runs_frame, 
                text="(No engraving tests added yet. Enter values above and click 'Add Test Engrave')", 
                font=ctk.CTkFont(slant="italic")
            )
            empty_lbl.pack(padx=10, pady=15)
            return

        is_metric = "Metric" in self.unit_system.get()
        for i, eng in enumerate(self.added_eng_tests):
            row = ctk.CTkFrame(self.eng_runs_frame, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)

            speed_disp = eng['speed']
            unit_spd = "mm/s"
            if not is_metric:
                speed_disp = round(speed_disp / 25.4, 3)
                unit_spd = "in/s"

            details_str = f"[{i+1}] {eng['material_name']} ({eng['mode']}): {speed_disp}{unit_spd} @ {eng['power']}%"
            lbl_details = ctk.CTkLabel(row, text=details_str, anchor="w")
            lbl_details.pack(side="left", padx=5, fill="x", expand=True)

            if eng.get("solved_kappa") is not None:
                kappa_val = eng["solved_kappa"]
                dev_val = eng["solved_deviation"]
                sign = "+" if dev_val >= 0 else ""
                stats_str = f"\u03ba={kappa_val:.2f}x ({sign}{dev_val:.2f}x)"
                
                lbl_color = "#D9534F" if abs(dev_val) > 0.12 else "#5CB85C"
                lbl_stats = ctk.CTkLabel(
                    row, 
                    text=stats_str, 
                    font=ctk.CTkFont(size=11, weight="bold"), 
                    text_color=lbl_color
                )
                lbl_stats.pack(side="left", padx=10)

            del_btn = ctk.CTkButton(
                row, 
                text="X", 
                width=22, 
                height=22, 
                fg_color="#D9534F", 
                hover_color="#C9302C", 
                corner_radius=11, 
                font=ctk.CTkFont(size=10, weight="bold"), 
                command=lambda idx=i: self._remove_eng_run(idx)
            )
            del_btn.pack(side="right", padx=5)

    def _solve_engrave_calibration(self, show_message=True):
        laser_type = self.selected_laser_type.get()
        laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
        if not laser_data:
            messagebox.showerror("Error", f"No database found for laser type: {laser_type}")
            return

        active_tests = self.added_eng_tests
        if not active_tests:
            try:
                mat = self.wiz_eng_material.get()
                mode = self.wiz_eng_mode.get()
                v = float(self.wiz_eng_speed.get())
                p = float(self.wiz_eng_power.get())
                
                is_metric = "Metric" in self.unit_system.get()
                if not is_metric:
                    v = v * 25.4
                    
                active_tests = [{
                    "material_name": mat,
                    "mode": mode,
                    "speed": v,
                    "power": p,
                    "interval_mm": 0.08,
                    "wattage": self.user_wattage.get(),
                    "solved_kappa": None,
                    "solved_deviation": None
                }]
            except ValueError:
                messagebox.showerror("Error", "No engraving tests added. Please enter valid numeric values to solve for a single test.")
                return

        solved_k = self.engine.calibrate_machine_engrave_factor(
            test_engraves=active_tests,
            reference_materials=laser_data.get("materials", {})
        )

        stats = self.engine.analyze_engrave_tests(
            test_engraves=active_tests,
            reference_materials=laser_data.get("materials", {})
        )

        if stats["count"] > 0:
            avg_k = stats["average"]
            min_k = stats["min"]
            max_k = stats["max"]
            std_k = stats["std_dev"]
            
            for idx, detail in enumerate(stats["details"]):
                if idx < len(active_tests):
                    active_tests[idx]["solved_kappa"] = detail["kappa"]
                    active_tests[idx]["solved_deviation"] = detail["deviation"]

            self.lbl_eng_avg.configure(text=f"Average Factor: {avg_k:.2f}x")
            self.lbl_eng_std.configure(text=f"Std. Deviation (\u03c3): {std_k:.2f}")
            self.lbl_eng_range.configure(text=f"Overall Range: [{min_k:.2f}x - {max_k:.2f}x] (n={stats['count']})")
            
            self.kappa_eng.set(round(avg_k, 2))
        else:
            self.kappa_eng.set(round(solved_k, 2))

        self._on_slider_changed()
        self._update_eng_runs_display()
        
        if show_message:
            msg = f"Engraving calibration solved using {stats['count']} test run(s)!\n\n"
            msg += f"  * Average Constant: {self.kappa_eng.get():.2f}x\n"
            if stats["count"] > 1:
                msg += f"  * Standard Deviation (\u03c3): {stats['std_dev']:.3f}\n"
                msg += f"  * Range: [{stats['min']:.2f}x to {stats['max']:.2f}x]\n"
                if stats["std_dev"] > 0.12:
                    msg += "\n[WARNING] High variance detected. Identify red-marked outliers and click 'X' to remove them before recalibrating."
            messagebox.showinfo("Engrave Calibration Solved", msg)

    # ==================== IMPORT / EXPORT METHODS ====================
    def _browse_library(self):
        file_path = filedialog.askopenfilename(
            title="Load Reference LightBurn Materials Library",
            initialdir=os.path.join(self.workspace_dir, "ExampleMaterialsFiles"),
            filetypes=[("LightBurn Libraries", "*.clb *.clib")]
        )
        if not file_path:
            return

        try:
            self.loaded_library_data = self.parser.parse_clb(file_path)
            self.loaded_library_path = file_path
            
            # Format and show filename
            base_name = os.path.basename(file_path)
            self.file_path_label.configure(text=f"Loaded library: {base_name}", text_color="green")
            if hasattr(self, "dash_file_path_label"):
                self.dash_file_path_label.configure(text=f"Loaded library: {base_name}", text_color="green")
            
            # Enable buttons
            self.export_lb_btn.configure(state="normal")
            self.export_k40_btn.configure(state="normal")
            
            messagebox.showinfo("Success", f"Successfully loaded library '{base_name}' containing {len(self.loaded_library_data['materials'])} materials!")
            # Update materials options menus
            self._update_material_dropdown_options()
            # Refresh displays
            self._update_explorer_grid()
            self._update_analytics_tab()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse XML library: {e}")

    def _export_scaled_clb(self):
        if not self.loaded_library_path:
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Calibrated LightBurn Materials Library",
            defaultextension=".clb",
            filetypes=[("LightBurn Library", "*.clb")]
        )
        if not file_path:
            return

        try:
            laser_type = self.selected_laser_type.get()
            laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
            
            norm_cap = None
            if self.normalize_high_power.get():
                try:
                    norm_cap = float(self.power_cap_percentage.get())
                except ValueError:
                    pass

            corrections = self.parser.scale_and_export_clb(
                input_file_path=self.loaded_library_path,
                output_file_path=file_path,
                engine=self.engine,
                source_wattage=40.0, # reference scale is 40W
                target_wattage=self.user_wattage.get(),
                kappa_cut=self.kappa_cut.get(),
                kappa_eng=self.kappa_eng.get(),
                reference_db=laser_data.get("materials", {}),
                laser_type=laser_type,
                v_max=self.max_speed.get(),
                v_max_eng=self.max_speed_eng.get(),
                p_min=self.min_power.get(),
                p_max=self.max_power.get(),
                power_normalize_cap=norm_cap
            )
            
            messagebox.showinfo("Success", f"Calibrated LightBurn library successfully exported to:\n{file_path}")
            
            if corrections:
                SettingAuditReportWindow(self, corrections)
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def _export_k40_cheat_sheet(self):
        if not self.loaded_library_data:
            return

        file_path = filedialog.asksaveasfilename(
            title="Save K40 Whisperer Cheat Sheet",
            defaultextension=".txt",
            filetypes=[("Text cheat sheet", "*.txt")]
        )
        if not file_path:
            return

        try:
            # We scale the parsed library data in-memory first to output correct values
            scaled_library = {"materials": []}
            laser_type = self.selected_laser_type.get()
            laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {}).get("materials", {})

            norm_cap = None
            if self.normalize_high_power.get():
                try:
                    norm_cap = float(self.power_cap_percentage.get())
                except ValueError:
                    pass

            for mat in self.loaded_library_data["materials"]:
                scaled_mat = {"name": mat["name"], "entries": []}
                standard_mat_name = self.parser._map_to_standard_material(mat["name"])
                in_ref_db = standard_mat_name in laser_data

                for entry in mat["entries"]:
                    scaled_entry = entry.copy()
                    
                    if entry["type"] == "Cut":
                        c_mat_override = None
                        if not in_ref_db:
                            c_mat_override = self.engine.calculate_material_cut_constant(
                                thickness=max(0.1, entry["thickness"]),
                                speed=entry["speed"],
                                power=entry["power"],
                                passes=entry["passes"],
                                wattage=40.0
                            )
                        pred = self.engine.predict_cutting_settings(
                            thickness=max(0.5, entry["thickness"]),
                            material_name=standard_mat_name,
                            target_power=entry["power"],
                            target_passes=entry["passes"],
                            user_wattage=self.user_wattage.get(),
                            kappa_cut=self.kappa_cut.get(),
                            reference_materials=laser_data,
                            laser_type=laser_type,
                            v_max=self.max_speed.get(),
                            p_min=self.min_power.get(),
                            p_max=self.max_power.get(),
                            c_mat_override=c_mat_override,
                            power_normalize_cap=norm_cap
                        )
                        if pred is not None:
                            scaled_entry["speed"] = pred["speed"]
                            scaled_entry["power"] = pred["power"]
                            scaled_entry["passes"] = pred["passes"]
                            
                    elif entry["type"] == "Scan":
                        mode = "Light Engrave" if entry["power"] < 20 else "Deep Engrave"
                        e_ref_override = None
                        if not in_ref_db:
                            e_ref_override = self.engine.calculate_material_engrave_constant(
                                speed=entry["speed"],
                                power=entry["power"],
                                interval=entry["interval"],
                                wattage=40.0
                            )
                        pred = self.engine.predict_engraving_settings(
                            material_name=standard_mat_name,
                            mode=mode,
                            target_power=entry["power"],
                            target_interval=entry["interval"],
                            user_wattage=self.user_wattage.get(),
                            kappa_eng=self.kappa_eng.get(),
                            reference_materials=laser_data,
                            laser_type=laser_type,
                            v_max=self.max_speed_eng.get(),
                            p_min=self.min_power.get(),
                            p_max=self.max_power.get(),
                            e_ref_override=e_ref_override,
                            power_normalize_cap=norm_cap
                        )
                        if pred is not None:
                            scaled_entry["speed"] = pred["speed"]
                            scaled_entry["power"] = pred["power"]
                            
                    scaled_mat["entries"].append(scaled_entry)
                scaled_library["materials"].append(scaled_mat)

            self.parser.export_k40_whisperer_txt(scaled_library, file_path)
            messagebox.showinfo("Success", f"K40 Whisperer cheat sheet successfully exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Cheat sheet export failed: {e}")

    def _on_norm_toggle(self):
        if self.normalize_high_power.get():
            self.entry_norm_cap.configure(state="normal")
        else:
            self.entry_norm_cap.configure(state="disabled")

    def _update_material_dropdown_options(self):
        if self.loaded_library_data is not None:
            materials = sorted(list(set(mat["name"] for mat in self.loaded_library_data["materials"])))
        else:
            laser_type = self.selected_laser_type.get()
            laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
            materials = sorted(list(laser_data.get("materials", {}).keys()))
            
        if not materials:
            materials = ["Birch Plywood", "Acrylic (Clear/Cast)", "MDF", "Cardboard", "Leather (Veg-Tanned)"]
            
        # Update dropdowns
        for dropdown in [self.explore_material_dropdown, self.analytics_material_dropdown, self.wiz_cut_material, self.wiz_eng_material]:
            if dropdown is not None:
                current_val = dropdown.get()
                dropdown.configure(values=materials)
                if current_val in materials:
                    dropdown.set(current_val)
                else:
                    dropdown.set(materials[0])

    # ==================== PERSISTENT MACHINE PROFILES ====================
    def _get_profiles_file_path(self):
        return os.path.join(self.workspace_dir, "data", "machine_profiles.json")

    def _load_saved_profiles(self):
        path = self._get_profiles_file_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _write_saved_profiles(self, profiles):
        path = self._get_profiles_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile: {e}")

    def _save_machine_profile(self):
        name = self.profile_name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please specify a Machine Name to save.")
            return
            
        profiles = self._load_saved_profiles()
        
        profiles[name] = {
            "laser_type": self.selected_laser_type.get(),
            "wattage": self.user_wattage.get(),
            "kappa_cut": self.kappa_cut.get(),
            "kappa_eng": self.kappa_eng.get(),
            "unit_system": self.unit_system.get(),
            "laser_kerf": self.laser_kerf.get(),
            "lens_focal": self.lens_focal.get(),
            "max_speed": self.max_speed.get(),
            "max_speed_eng": self.max_speed_eng.get(),
            "min_power": self.min_power.get(),
            "max_power": self.max_power.get()
        }
        
        self._write_saved_profiles(profiles)
        self.profile_name_entry.delete(0, tk.END)
        self._update_profiles_list_display()
        if hasattr(self, "active_profile_label"):
            self.active_profile_label.configure(text=f"Current Profile:  {name}", text_color="#5CB85C")
        messagebox.showinfo("Success", f"Machine profile '{name}' saved successfully!")

    def _load_machine_profile(self, name, show_message=True):
        profiles = self._load_saved_profiles()
        if name not in profiles:
            if show_message:
                messagebox.showerror("Error", f"Profile '{name}' not found.")
            return
            
        p = profiles[name]
        
        # Set all values
        self.selected_laser_type.set(p.get("laser_type", "CO2"))
        self.user_wattage.set(p.get("wattage", 40.0))
        self.kappa_cut.set(p.get("kappa_cut", 1.0))
        self.kappa_eng.set(p.get("kappa_eng", 1.0))
        self.unit_system.set(p.get("unit_system", "Metric (mm, mm/s)"))
        self.laser_kerf.set(p.get("laser_kerf", 0.15))
        self.lens_focal.set(p.get("lens_focal", "50.8"))
        self.max_speed.set(p.get("max_speed", 80.0))
        self.max_speed_eng.set(p.get("max_speed_eng", 400.0))
        self.min_power.set(p.get("min_power", 10.0))
        self.max_power.set(p.get("max_power", 80.0))
        
        # Trigger unit labels updates WITHOUT double converting
        self._on_unit_system_changed(self.unit_system.get(), convert=False)
        
        # Trigger other updates
        self._update_explorer_grid()
        self._update_analytics_tab()
        self._update_health_meters()
        
        # Prefill the name entry to show which machine is loaded active
        self.profile_name_entry.delete(0, tk.END)
        self.profile_name_entry.insert(0, name)
        
        if hasattr(self, "active_profile_label"):
            self.active_profile_label.configure(text=f"Current Profile:  {name}", text_color="#5CB85C")

        if show_message:
            messagebox.showinfo("Success", f"Machine profile '{name}' loaded successfully!")

    def _delete_machine_profile(self, name):
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete profile '{name}'?"):
            return
            
        profiles = self._load_saved_profiles()
        if name in profiles:
            profiles.pop(name)
            self._write_saved_profiles(profiles)
            self._update_profiles_list_display()
            if hasattr(self, "active_profile_label"):
                current_active = self.active_profile_label.cget("text")
                if f"Current Profile:  {name}" in current_active:
                    self.active_profile_label.configure(text="Current Profile:  none", text_color="#A9A9A9")
            messagebox.showinfo("Success", f"Machine profile '{name}' deleted successfully!")

    def _update_profiles_list_display(self):
        # Clear child widgets
        for widget in self.profiles_list_frame.winfo_children():
            widget.destroy()
            
        profiles = self._load_saved_profiles()
        if not profiles:
            lbl = ctk.CTkLabel(self.profiles_list_frame, text="No saved machines yet.", font=ctk.CTkFont(size=11, slant="italic"))
            lbl.pack(pady=5)
            return
            
        ctk.CTkLabel(self.profiles_list_frame, text="Load Saved Machine:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", pady=(5, 2))
        
        for name in profiles.keys():
            row = ctk.CTkFrame(self.profiles_list_frame, fg_color="gray20", height=32, corner_radius=4)
            row.pack(fill="x", pady=2)
            
            lbl = ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=11))
            lbl.pack(side="left", padx=5)
            
            # Load Button
            load_btn = ctk.CTkButton(
                row, 
                text="Load", 
                width=45, 
                height=22, 
                fg_color="#5CB85C", 
                hover_color="#4CAE4C",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda n=name: self._load_machine_profile(n)
            )
            load_btn.pack(side="right", padx=3)
            
            # Delete Button
            del_btn = ctk.CTkButton(
                row, 
                text="X", 
                width=22, 
                height=22, 
                fg_color="#D9534F", 
                hover_color="#C9302C",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda n=name: self._delete_machine_profile(n)
            )
            del_btn.pack(side="right", padx=3)


    # ==================== LIVE COLOR CHOICE METHODS ====================
    def _choose_cut_color(self):
        from tkinter import colorchooser
        color_code = colorchooser.askcolor(title="Choose Vector Cut Color", initialcolor=self.cut_color)
        if color_code and color_code[1]:
            self.cut_color = color_code[1]
            self.cut_color_btn.configure(fg_color=self.cut_color, hover_color=self.cut_color, text=self.cut_color)
            self._update_explorer_grid()
            self._update_analytics_tab()
            self._update_compare_grids()

    def _choose_engrave_color(self):
        from tkinter import colorchooser
        color_code = colorchooser.askcolor(title="Choose Raster Engrave Color", initialcolor=self.engrave_color)
        if color_code and color_code[1]:
            self.engrave_color = color_code[1]
            self.eng_color_btn.configure(fg_color=self.engrave_color, hover_color=self.engrave_color, text=self.engrave_color)
            self._update_explorer_grid()
            self._update_analytics_tab()
            self._update_compare_grids()


    # ==================== TAB 5: COMPARE & MERGE LIBRARIES ====================
    def _build_compare_tab(self):
        self.tab_compare.grid_columnconfigure(0, weight=1)
        self.tab_compare.grid_rowconfigure(1, weight=1)

        # Instructions card
        instructions_card = ctk.CTkFrame(self.tab_compare, corner_radius=8, fg_color="gray15", border_width=1, border_color="gray30")
        instructions_card.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        inst_lbl = ctk.CTkLabel(
            instructions_card,
            text=(
                "**Compare & Merge Instructions**:\n"
                "1. **Load Libraries**: Click the **Load Library** buttons at the top of Column 1 and Column 2 to load your settings.\n"
                "2. **Manual Match**: Click/highlight a row in Column 1 (Left) and a row in Column 2 (Right) to select them, then click **Link Selected** to link them.\n"
                "3. **Auto Match**: Click **Auto-Match Materials** to automatically pair items by type and similar names.\n"
                "4. **Recalculate & Compare**: Click **Compare and Analyze** to evaluate volumetric Specific Energy (Ev) for cuts and Areal Energy Density (Ea) for engraves, alongside Linear Energy (El).\n"
                "5. **Merge & Export**: Select checkboxes on any settings you wish to merge, then click **Next** to rename and generate a calibrated .clb file.\n"
                "  * Vector Cut profiles are highlighted with Vector Cut Color; Raster Engrave profiles are highlighted with Raster Engrave Color."
            ),
            justify="left",
            wraplength=750
        )
        inst_lbl.pack(anchor="w", padx=15, pady=10)

        # Controls Top Bar
        ctrl_bar = ctk.CTkFrame(self.tab_compare, corner_radius=8, fg_color="transparent")
        ctrl_bar.grid(row=2, column=0, sticky="ew", padx=15, pady=5)

        # Action Buttons
        self.btn_link = ctk.CTkButton(
            ctrl_bar,
            text="Link Selected",
            fg_color="gray30",
            state="disabled",
            command=self._link_selected_entries
        )
        self.btn_link.pack(side="left", padx=5)

        self.btn_auto_match = ctk.CTkButton(
            ctrl_bar,
            text="Auto-Match Materials",
            fg_color="#1F6AA5",
            hover_color="#154B75",
            state="disabled",
            command=self._auto_match_libraries
        )
        self.btn_auto_match.pack(side="left", padx=5)

        self.btn_compare_analyze = ctk.CTkButton(
            ctrl_bar,
            text="Compare and Analyze",
            fg_color="#1F6AA5",
            hover_color="#154B75",
            state="disabled",
            command=self._compare_and_analyze_libraries
        )
        self.btn_compare_analyze.pack(side="left", padx=5)

        self.btn_compare_next = ctk.CTkButton(
            ctrl_bar,
            text="Next \u2192",
            fg_color="#5CB85C",
            hover_color="#4CAE4C",
            state="disabled",
            command=self._on_compare_next
        )
        self.btn_compare_next.pack(side="right", padx=5)

        # Split Scrollable Frames Panel
        split_panel = ctk.CTkFrame(self.tab_compare, fg_color="transparent")
        split_panel.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        split_panel.grid_columnconfigure((0, 1), weight=1)
        split_panel.grid_rowconfigure(0, weight=1)

        # Column 1 Frame
        self.col1_card = ctk.CTkFrame(split_panel, fg_color="gray15", corner_radius=8)
        self.col1_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=5)
        self.col1_card.grid_columnconfigure(0, weight=1)
        self.col1_card.grid_rowconfigure(2, weight=1)

        # Top Section for Column 1 Loading
        col1_header = ctk.CTkFrame(self.col1_card, fg_color="transparent")
        col1_header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkLabel(col1_header, text="COLUMN 1: WORKING LIBRARY", font=ctk.CTkFont(family="Inter", size=12, weight="bold"), text_color="#1F6AA5").pack(side="left")
        
        self.col1_load_btn = ctk.CTkButton(
            col1_header,
            text="Load Library",
            width=90,
            height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._browse_column1_library
        )
        self.col1_load_btn.pack(side="right", padx=5)
        
        # Loaded file path label for Col 1
        curr_col1_name = os.path.basename(self.loaded_library_path) if self.loaded_library_path else "Default Database"
        self.col1_load_label = ctk.CTkLabel(
            self.col1_card, 
            text=f"Loaded: {curr_col1_name}",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="green" if self.loaded_library_path else "gray"
        )
        self.col1_load_label.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")

        self.col1_scroll = ctk.CTkScrollableFrame(self.col1_card, fg_color="transparent")
        self.col1_scroll.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        # Column 2 Frame
        self.col2_card = ctk.CTkFrame(split_panel, fg_color="gray15", corner_radius=8)
        self.col2_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=5)
        self.col2_card.grid_columnconfigure(0, weight=1)
        self.col2_card.grid_rowconfigure(2, weight=1)

        # Top Section for Column 2 Loading
        col2_header = ctk.CTkFrame(self.col2_card, fg_color="transparent")
        col2_header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkLabel(col2_header, text="COLUMN 2: COMPARISON LIBRARY", font=ctk.CTkFont(family="Inter", size=12, weight="bold"), text_color="#1F6AA5").pack(side="left")
        
        self.col2_load_btn = ctk.CTkButton(
            col2_header,
            text="Load Library",
            width=90,
            height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._browse_compare_library
        )
        self.col2_load_btn.pack(side="right", padx=5)

        self.col2_load_label = ctk.CTkLabel(
            self.col2_card, 
            text="No Column 2 file loaded.", 
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray"
        )
        self.col2_load_label.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")

        # Comparison Profile Setup Card
        self.col2_profile_frame = ctk.CTkFrame(self.col2_card, fg_color="gray18", corner_radius=6, border_width=1, border_color="gray30")
        self.col2_profile_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        # Grid layout inside the profile card
        self.col2_profile_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Title of the card
        lbl_p_title = ctk.CTkLabel(
            self.col2_profile_frame,
            text="⚡ Comparison Machine Profile:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#1F6AA5",
            anchor="w"
        )
        lbl_p_title.grid(row=0, column=0, columnspan=4, padx=8, pady=(4, 2), sticky="w")
        
        # Tube Wattage Input
        lbl_w = ctk.CTkLabel(self.col2_profile_frame, text="Wattage (W):", font=ctk.CTkFont(size=10))
        lbl_w.grid(row=1, column=0, padx=5, pady=2, sticky="e")
        
        self.entry_compare_wattage = ctk.CTkEntry(
            self.col2_profile_frame, 
            textvariable=self.compare_wattage,
            width=55,
            height=20,
            font=ctk.CTkFont(size=10)
        )
        self.entry_compare_wattage.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        # Kerf Input
        lbl_k = ctk.CTkLabel(self.col2_profile_frame, text="Kerf (mm):", font=ctk.CTkFont(size=10))
        lbl_k.grid(row=1, column=2, padx=5, pady=2, sticky="e")
        
        self.entry_compare_kerf = ctk.CTkEntry(
            self.col2_profile_frame, 
            textvariable=self.compare_kerf,
            width=55,
            height=20,
            font=ctk.CTkFont(size=10)
        )
        self.entry_compare_kerf.grid(row=1, column=3, padx=5, pady=2, sticky="w")
        
        # Helpful prompt
        self.lbl_compare_prompt = ctk.CTkLabel(
            self.col2_profile_frame,
            text="Note: Wattage & kerf are auto-detected from the loaded filename.",
            font=ctk.CTkFont(size=9, slant="italic"),
            text_color="gray",
            anchor="w"
        )
        self.lbl_compare_prompt.grid(row=2, column=0, columnspan=4, padx=8, pady=(2, 4), sticky="w")

        self.col2_scroll = ctk.CTkScrollableFrame(self.col2_card, fg_color="transparent")
        self.col2_scroll.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        self.col2_card.grid_rowconfigure(3, weight=1)

        # Initial render of Column 1
        self._update_compare_grids()

    def _browse_column1_library(self):
        file_path = filedialog.askopenfilename(
            title="Load Working Materials Library (Column 1)",
            initialdir=os.path.join(self.workspace_dir, "ExampleMaterialsFiles"),
            filetypes=[("LightBurn Libraries", "*.clb *.clib")]
        )
        if not file_path:
            return

        try:
            self.loaded_library_data = self.parser.parse_clb(file_path)
            self.loaded_library_path = file_path
            
            base_name = os.path.basename(file_path)
            self.file_path_label.configure(text=f"Loaded library: {base_name}", text_color="green")
            if hasattr(self, "dash_file_path_label"):
                self.dash_file_path_label.configure(text=f"Loaded library: {base_name}", text_color="green")
            
            self.export_lb_btn.configure(state="normal")
            self.export_k40_btn.configure(state="normal")
            
            self.col1_load_label.configure(text=f"Loaded: {base_name}", text_color="green")
            
            self.left_list_evaluated = None
            self.selected_left_id = None
            self.matched_pairs = []
            
            messagebox.showinfo("Success", f"Successfully loaded Column 1 library '{base_name}'!")
            self._update_material_dropdown_options()
            self._update_explorer_grid()
            self._update_analytics_tab()
            self._update_compare_grids()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse Column 1 library: {e}")

    def _browse_compare_library(self):
        file_path = filedialog.askopenfilename(
            title="Load Comparison LightBurn Materials Library (Column 2)",
            initialdir=os.path.join(self.workspace_dir, "ExampleMaterialsFiles"),
            filetypes=[("LightBurn Libraries", "*.clb *.clib")]
        )
        if not file_path:
            return

        try:
            self.compare_library_data = self.parser.parse_clb(file_path)
            self.compare_library_path = file_path
            self.compare_library_data_flat = self._flatten_compare_library()
            
            base_name = os.path.basename(file_path)
            self.col2_load_label.configure(text=f"Loaded: {base_name}", text_color="green")
            
            import re
            detected_wattage = 40.0
            # Extract wattage (e.g. 50W, 80W, 65W)
            match = re.search(r'(\d+)\s*[wW]', base_name)
            if match:
                detected_wattage = float(match.group(1))
            
            # Suggest kerf based on standard profiles or brand
            detected_kerf = 0.15
            profiles = self._load_saved_profiles()
            matched_profile_name = None
            
            # Check if there is an existing profile in the database
            for p_name, p_data in profiles.items():
                if abs(p_data.get("wattage", 0) - detected_wattage) < 0.1:
                    brand_match = False
                    for b in ["boss", "gweike", "monport"]:
                        if b in base_name.lower() and b in p_name.lower():
                            brand_match = True
                            break
                    if brand_match:
                        matched_profile_name = p_name
                        detected_kerf = p_data.get("laser_kerf", 0.15)
                        break
            
            # Fallback brand kerfs if no profile matches
            if matched_profile_name is None:
                if "gweike" in base_name.lower():
                    detected_kerf = 0.12
                elif "boss" in base_name.lower():
                    detected_kerf = 0.15
                elif "monport" in base_name.lower():
                    if detected_wattage == 55.0:
                        detected_kerf = 0.14
                    elif detected_wattage == 80.0:
                        detected_kerf = 0.16
                    elif detected_wattage == 100.0:
                        detected_kerf = 0.18
                    elif detected_wattage == 130.0:
                        detected_kerf = 0.20
            
            self.compare_wattage.set(detected_wattage)
            self.compare_kerf.set(detected_kerf)
            
            # Update the prompt label
            if matched_profile_name:
                self.lbl_compare_prompt.configure(
                    text=f"Matched profile: '{matched_profile_name}' ({detected_wattage}W, Kerf: {detected_kerf}mm)",
                    text_color="#5CB85C"
                )
            else:
                self.lbl_compare_prompt.configure(
                    text=f"Auto-detected: Wattage {detected_wattage}W, Kerf {detected_kerf}mm.",
                    text_color="#1F6AA5"
                )
            
            # Enable buttons
            self.btn_auto_match.configure(state="normal")
            self.btn_compare_analyze.configure(state="normal")
            self.btn_compare_next.configure(state="normal")
            
            self.matched_pairs = []
            self.selected_left_id = None
            self.selected_right_id = None
            self.left_export_selections = {}
            self.right_export_selections = {}
            self.left_list_evaluated = None
            self.right_list_evaluated = None
            
            messagebox.showinfo("Success", f"Successfully loaded comparison library '{base_name}' containing {len(self.compare_library_data_flat)} entries!")
            self._update_compare_grids()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse comparison library: {e}")

    def _flatten_compare_library(self):
        if not self.compare_library_data:
            return []
        flat_list = []
        idx = 0
        for mat in self.compare_library_data["materials"]:
            mat_name = mat["name"]
            for entry in mat["entries"]:
                flat_list.append({
                    "id": f"right_{idx}",
                    "material_name": mat_name,
                    "thickness": entry["thickness"],
                    "desc": entry.get("desc", ""),
                    "type": entry["type"],
                    "speed": entry["speed"],
                    "power": entry["power"],
                    "passes": entry.get("passes", 1),
                    "interval": entry.get("interval", 0.08),
                    "ev": None,
                    "el": None
                })
                idx += 1
        return flat_list

    def _get_active_l1_flat(self):
        flat_list = []
        is_metric = "Metric" in self.unit_system.get()
        laser_type = self.selected_laser_type.get()
        laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
        v_max_cut_metric = self.max_speed.get() if is_metric else self.max_speed.get() * 25.4
        v_max_eng_metric = self.max_speed_eng.get() if is_metric else self.max_speed_eng.get() * 25.4
        p_min = self.min_power.get()
        p_max = self.max_power.get()

        if self.loaded_library_data is not None:
            idx = 0
            for mat in self.loaded_library_data["materials"]:
                mat_name = mat["name"]
                standard_mat_name = self.parser._map_to_standard_material(mat_name)
                in_ref_db = standard_mat_name in laser_data.get("materials", {})
                for entry in mat["entries"]:
                    speed = entry["speed"]
                    power = entry["power"]
                    passes = entry.get("passes", 1)
                    interval = entry.get("interval", 0.08)
                    
                    if entry["type"] == "Cut":
                        c_mat_override = None
                        if not in_ref_db:
                            c_mat_override = self.engine.calculate_material_cut_constant(
                                thickness=max(0.1, entry["thickness"]),
                                speed=speed,
                                power=power,
                                passes=passes,
                                wattage=40.0
                            )
                        pred = self.engine.predict_cutting_settings(
                            thickness=max(0.1, entry["thickness"]),
                            material_name=standard_mat_name,
                            target_power=power,
                            target_passes=passes,
                            user_wattage=self.user_wattage.get(),
                            kappa_cut=self.kappa_cut.get(),
                            reference_materials=laser_data.get("materials", {}),
                            laser_type=laser_type,
                            v_max=v_max_cut_metric,
                            p_min=p_min,
                            p_max=p_max,
                            c_mat_override=c_mat_override
                        )
                        if pred:
                            speed = pred["speed"]
                            power = pred["power"]
                    elif entry["type"] == "Scan":
                        mode = entry.get("no_thick_title") or entry.get("desc") or "Standard Engrave"
                        e_ref_override = None
                        if not in_ref_db:
                            e_ref_override = self.engine.calculate_material_engrave_constant(
                                speed=speed,
                                power=power,
                                interval=interval,
                                wattage=40.0
                            )
                        pred = self.engine.predict_engraving_settings(
                            material_name=standard_mat_name,
                            mode=mode,
                            target_power=power,
                            target_interval=interval,
                            user_wattage=self.user_wattage.get(),
                            kappa_eng=self.kappa_eng.get(),
                            reference_materials=laser_data.get("materials", {}),
                            laser_type=laser_type,
                            v_max=v_max_eng_metric,
                            p_min=p_min,
                            p_max=p_max,
                            e_ref_override=e_ref_override
                        )
                        if pred:
                            speed = pred["speed"]
                            power = pred["power"]
                            
                    flat_list.append({
                        "id": f"left_{idx}",
                        "material_name": mat_name,
                        "thickness": entry["thickness"],
                        "desc": entry.get("desc", ""),
                        "type": entry["type"],
                        "speed": speed,
                        "power": power,
                        "passes": passes,
                        "interval": interval,
                        "ev": None,
                        "el": None
                    })
                    idx += 1
        else:
            idx = 0
            for mat_name, mat_info in laser_data.get("materials", {}).items():
                for cut in mat_info.get("cutting", []):
                    pred = self.engine.predict_cutting_settings(
                        thickness=cut["thickness_mm"],
                        material_name=mat_name,
                        target_power=cut["ref_power"],
                        target_passes=cut["ref_passes"],
                        user_wattage=self.user_wattage.get(),
                        kappa_cut=self.kappa_cut.get(),
                        reference_materials=laser_data.get("materials", {}),
                        laser_type=laser_type,
                        v_max=v_max_cut_metric,
                        p_min=p_min,
                        p_max=p_max
                    )
                    speed = pred["speed"] if pred else cut["ref_speed"]
                    power = pred["power"] if pred else cut["ref_power"]
                    flat_list.append({
                        "id": f"left_{idx}",
                        "material_name": mat_name,
                        "thickness": cut["thickness_mm"],
                        "desc": "Vector Cut",
                        "type": "Cut",
                        "speed": speed,
                        "power": power,
                        "passes": cut["ref_passes"],
                        "interval": 0.08,
                        "ev": None,
                        "el": None
                    })
                    idx += 1
                for eng in mat_info.get("engraving", []):
                    pred = self.engine.predict_engraving_settings(
                        material_name=mat_name,
                        mode=eng["mode"],
                        target_power=eng["ref_power"],
                        target_interval=eng["interval_mm"],
                        user_wattage=self.user_wattage.get(),
                        kappa_eng=self.kappa_eng.get(),
                        reference_materials=laser_data.get("materials", {}),
                        laser_type=laser_type,
                        v_max=v_max_eng_metric,
                        p_min=p_min,
                        p_max=p_max
                    )
                    speed = pred["speed"] if pred else eng["ref_speed"]
                    power = pred["power"] if pred else eng["ref_power"]
                    flat_list.append({
                        "id": f"left_{idx}",
                        "material_name": mat_name,
                        "thickness": 0.0,
                        "desc": eng["mode"],
                        "type": "Scan",
                        "speed": speed,
                        "power": power,
                        "passes": 1,
                        "interval": eng["interval_mm"],
                        "ev": None,
                        "el": None
                    })
                    idx += 1
        return flat_list

    def _on_left_row_clicked(self, entry_id):
        if self.selected_left_id == entry_id:
            self.selected_left_id = None
        else:
            self.selected_left_id = entry_id
        self._update_compare_grids()

    def _on_right_row_clicked(self, entry_id):
        if self.selected_right_id == entry_id:
            self.selected_right_id = None
        else:
            self.selected_right_id = entry_id
        self._update_compare_grids()

    def _link_selected_entries(self):
        if not self.selected_left_id or not self.selected_right_id:
            return
            
        left_list = self._get_active_l1_flat()
        right_list = self.compare_library_data_flat
        
        left_item = next((x for x in left_list if x["id"] == self.selected_left_id), None)
        right_item = next((x for x in right_list if x["id"] == self.selected_right_id), None)
        
        if not left_item or not right_item:
            return
            
        if left_item["type"] != right_item["type"]:
            messagebox.showerror("Matching Error", "Cannot link different task types. Only match Cuts to Cuts and Engraves to Engraves.")
            self.selected_left_id = None
            self.selected_right_id = None
            self._update_compare_grids()
            return
            
        if any(p["left_id"] == self.selected_left_id or p["right_id"] == self.selected_right_id for p in self.matched_pairs):
            messagebox.showerror("Matching Error", "One of the selected items is already matched.")
            return
            
        self.matched_pairs.append({
            "left_id": self.selected_left_id,
            "right_id": self.selected_right_id
        })
        
        self.selected_left_id = None
        self.selected_right_id = None
        self.btn_link.configure(state="disabled", fg_color="gray30")
        
        self._update_compare_grids()

    def _unlink_pair(self, left_id):
        self.matched_pairs = [p for p in self.matched_pairs if p["left_id"] != left_id]
        self._update_compare_grids()

    def _auto_match_libraries(self):
        left_list = self._get_active_l1_flat()
        right_list = self.compare_library_data_flat
        
        if not left_list or not right_list:
            return
            
        def clean_str(s):
            return "".join(c for c in s.lower() if c.isalnum())
            
        match_count = 0
        
        for l_item in left_list:
            if any(p["left_id"] == l_item["id"] for p in self.matched_pairs):
                continue
                
            l_name_clean = clean_str(l_item["material_name"])
            
            for r_item in right_list:
                if any(p["right_id"] == r_item["id"] for p in self.matched_pairs):
                    continue
                    
                if l_item["type"] != r_item["type"]:
                    continue
                    
                if l_item["type"] == "Cut":
                    if abs(l_item["thickness"] - r_item["thickness"]) > 0.22:
                        continue
                        
                r_name_clean = clean_str(r_item["material_name"])
                
                is_match = False
                if l_name_clean == r_name_clean:
                    is_match = True
                elif l_name_clean in r_name_clean or r_name_clean in l_name_clean:
                    is_match = True
                
                if is_match:
                    self.matched_pairs.append({
                        "left_id": l_item["id"],
                        "right_id": r_item["id"]
                    })
                    match_count += 1
                    break
                    
        messagebox.showinfo("Auto-Match Complete", f"Fuzzy auto-matching successfully linked {match_count} new setting pairs!")
        self._update_compare_grids()

    def _compare_and_analyze_libraries(self):
        left_list = self._get_active_l1_flat()
        right_list = self.compare_library_data_flat
        
        is_metric = "Metric" in self.unit_system.get()
        w_base = self.laser_kerf.get()
        
        try:
            focal_val = float(self.lens_focal.get())
        except ValueError:
            focal_val = 50.8 if is_metric else 2.0
            
        for item in left_list:
            spd = item["speed"]
            pow_val = item["power"]
            thick = item["thickness"]
            interval = item["interval"]
            
            spd_calc = spd if is_metric else spd / 25.4
            thick_calc = thick if is_metric else thick / 25.4
            interval_calc = interval if is_metric else interval / 25.4
            
            if item["type"] == "Cut":
                ev = self.engine.calculate_specific_energy_cut(
                    speed=spd_calc,
                    power=pow_val,
                    thickness=thick_calc,
                    kerf=w_base,
                    wattage=self.user_wattage.get(),
                    focal_length=focal_val,
                    units="metric" if is_metric else "imperial"
                )
            else:
                ev = self.engine.calculate_specific_energy_engrave(
                    speed=spd_calc,
                    power=pow_val,
                    interval=interval_calc,
                    kerf=w_base,
                    wattage=self.user_wattage.get(),
                    focal_length=focal_val,
                    units="metric" if is_metric else "imperial"
                )
            el = self.engine.calculate_linear_energy_density(
                speed=spd_calc,
                power=pow_val,
                wattage=self.user_wattage.get()
            )
            item["ev"] = ev
            item["el"] = el
            
        w_compare = self.compare_kerf.get()
        wattage_compare = self.compare_wattage.get()
        
        for item in right_list:
            spd = item["speed"]
            pow_val = item["power"]
            thick = item["thickness"]
            interval = item["interval"]
            
            spd_calc = spd if is_metric else spd / 25.4
            thick_calc = thick if is_metric else thick / 25.4
            interval_calc = interval if is_metric else interval / 25.4
            
            if item["type"] == "Cut":
                ev = self.engine.calculate_specific_energy_cut(
                    speed=spd_calc,
                    power=pow_val,
                    thickness=thick_calc,
                    kerf=w_compare,
                    wattage=wattage_compare,
                    focal_length=None,
                    units="metric" if is_metric else "imperial"
                )
            else:
                ev = self.engine.calculate_specific_energy_engrave(
                    speed=spd_calc,
                    power=pow_val,
                    interval=interval_calc,
                    kerf=w_compare,
                    wattage=wattage_compare,
                    focal_length=None,
                    units="metric" if is_metric else "imperial"
                )
            el = self.engine.calculate_linear_energy_density(
                speed=spd_calc,
                power=pow_val,
                wattage=wattage_compare
            )
            item["ev"] = ev
            item["el"] = el
            
        self.left_list_evaluated = left_list
        self.right_list_evaluated = right_list
        
        messagebox.showinfo("Comparison Analysis Completed", "Volumetric and Linear specific energies successfully calculated side-by-side!")
        self._update_compare_grids()

    def _update_compare_grids(self):
        for widget in self.col1_scroll.winfo_children():
            widget.destroy()
        for widget in self.col2_scroll.winfo_children():
            widget.destroy()
            
        left_list = self.left_list_evaluated if self.left_list_evaluated is not None else self._get_active_l1_flat()
        right_list = self.right_list_evaluated if self.right_list_evaluated is not None else self.compare_library_data_flat
        
        # Sort left and right lists: matched items go to the top, ordered by match sequence index;
        # unmatched items go to the bottom, sorted alphabetically by material name.
        def left_sort_key(item):
            matched_pair = next((p for p in self.matched_pairs if p["left_id"] == item["id"]), None)
            if matched_pair is not None:
                return (0, self.matched_pairs.index(matched_pair), "")
            else:
                mat_name_lower = str(item["material_name"]).lower()
                return (1, 0, (mat_name_lower, item["type"], item["thickness"], item["speed"], item["power"]))
                
        def right_sort_key(item):
            matched_pair = next((p for p in self.matched_pairs if p["right_id"] == item["id"]), None)
            if matched_pair is not None:
                return (0, self.matched_pairs.index(matched_pair), "")
            else:
                mat_name_lower = str(item["material_name"]).lower()
                return (1, 0, (mat_name_lower, item["type"], item["thickness"], item["speed"], item["power"]))
                
        left_list = sorted(left_list, key=left_sort_key)
        right_list = sorted(right_list, key=right_sort_key)
        
        is_metric = "Metric" in self.unit_system.get()
        unit_len = "mm" if is_metric else "in"
        unit_spd = "mm/s" if is_metric else "in/s"
        unit_ev = "J/mm³" if is_metric else "J/in³"
        unit_el = "J/mm" if is_metric else "J/in"
        
        if self.selected_left_id and self.selected_right_id:
            self.btn_link.configure(state="normal", fg_color="#5CB85C", hover_color="#4CAE4C")
        else:
            self.btn_link.configure(state="disabled", fg_color="gray30")
            
        # Left Grid Rows
        for item in left_list:
            left_id = item["id"]
            matched_pair = next((p for p in self.matched_pairs if p["left_id"] == left_id), None)
            is_matched = matched_pair is not None
            
            is_selected = self.selected_left_id == left_id
            bg_color = "#1F6AA5" if is_selected else ("gray25" if is_matched else "gray20")
            row_frame = ctk.CTkFrame(self.col1_scroll, fg_color=bg_color, corner_radius=6)
            row_frame.pack(fill="x", pady=4, padx=5)
            
            if not is_matched:
                row_frame.bind("<Button-1>", lambda e, lid=left_id: self._on_left_row_clicked(lid))
            
            # Export Checkbox
            var = tk.BooleanVar(value=self.left_export_selections.get(left_id, True if is_matched else False))
            self.left_export_selections[left_id] = var.get()
            chk = ctk.CTkCheckBox(
                row_frame, 
                text="", 
                variable=var, 
                width=20, 
                command=lambda lid=left_id, v=var: self._on_export_checkbox_toggled("left", lid, v.get())
            )
            chk.pack(side="left", padx=5)
            
            lbl_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            lbl_frame.pack(side="left", fill="both", expand=True, padx=5)
            if not is_matched:
                lbl_frame.bind("<Button-1>", lambda e, lid=left_id: self._on_left_row_clicked(lid))
                
            text_color = self.cut_color if item["type"] == "Cut" else self.engrave_color
                
            thick_disp = item["thickness"] if is_metric else round(item["thickness"] / 25.4, 3)
            task_type = "Cut" if item["type"] == "Cut" else "Engrave"
            first_lbl_text = f"{item['material_name']} ({thick_disp:.1f}{unit_len} {task_type})"
            
            lbl_title = ctk.CTkLabel(
                lbl_frame, 
                text=first_lbl_text, 
                font=ctk.CTkFont(size=12, weight="bold"), 
                text_color=text_color,
                anchor="w"
            )
            lbl_title.pack(anchor="w")
            if not is_matched:
                lbl_title.bind("<Button-1>", lambda e, lid=left_id: self._on_left_row_clicked(lid))
                
            settings_str = f"{item['speed']:.1f} {unit_spd} @ {item['power']}%"
            if is_matched:
                match_idx = self.matched_pairs.index(matched_pair)
                r_item = next((x for x in right_list if x["id"] == matched_pair["right_id"]), None)
                if r_item:
                    r_thick = r_item["thickness"] if is_metric else round(r_item["thickness"] / 25.4, 3)
                    r_type = "Cut" if r_item["type"] == "Cut" else "Engrave"
                    other_name = f"{r_item['material_name']} ({r_thick:.1f}{unit_len} {r_type})"
                    settings_str += f"  [{match_idx + 1}) Matched to {other_name}]"
                else:
                    settings_str += f"  [{match_idx + 1}) Matched]"
                
            lbl_settings = ctk.CTkLabel(
                lbl_frame, 
                text=settings_str, 
                font=ctk.CTkFont(size=11), 
                text_color=text_color,
                anchor="w"
            )
            lbl_settings.pack(anchor="w")
            if not is_matched:
                lbl_settings.bind("<Button-1>", lambda e, lid=left_id: self._on_left_row_clicked(lid))
                
            if item.get("ev") is not None:
                is_cut = item["type"] == "Cut"
                unit_ev_disp = unit_ev if is_cut else ("J/mm²" if is_metric else "J/in²")
                label_ev = "Ev" if is_cut else "Ea"
                stats_str = f"{label_ev}: {item['ev']:.1f} {unit_ev_disp} | El: {item['el']:.2f} {unit_el}"
                if is_matched:
                    r_item = next((x for x in right_list if x["id"] == matched_pair["right_id"]), None)
                    if r_item and r_item.get("ev"):
                        diff_pct = ((item["ev"] / r_item["ev"]) - 1.0) * 100.0
                        sign = "+" if diff_pct >= 0 else ""
                        stats_str += f" | Diff: {sign}{diff_pct:.1f}% {label_ev}"
                lbl_stats = ctk.CTkLabel(
                    lbl_frame, 
                    text=stats_str, 
                    font=ctk.CTkFont(size=10, slant="italic"), 
                    text_color="#B0B0B0",
                    anchor="w"
                )
                lbl_stats.pack(anchor="w")
                if not is_matched:
                    lbl_stats.bind("<Button-1>", lambda e, lid=left_id: self._on_left_row_clicked(lid))
                
            if is_matched:
                unlink_btn = ctk.CTkButton(
                    row_frame,
                    text="X",
                    width=22,
                    height=22,
                    fg_color="#D9534F",
                    hover_color="#C9302C",
                    corner_radius=11,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda lid=left_id: self._unlink_pair(lid)
                )
                unlink_btn.pack(side="right", padx=10)

        # Right Grid Rows
        for item in right_list:
            right_id = item["id"]
            matched_pair = next((p for p in self.matched_pairs if p["right_id"] == right_id), None)
            is_matched = matched_pair is not None
            
            is_selected = self.selected_right_id == right_id
            bg_color = "#1F6AA5" if is_selected else ("gray25" if is_matched else "gray20")
            row_frame = ctk.CTkFrame(self.col2_scroll, fg_color=bg_color, corner_radius=6)
            row_frame.pack(fill="x", pady=4, padx=5)
            
            if not is_matched:
                row_frame.bind("<Button-1>", lambda e, rid=right_id: self._on_right_row_clicked(rid))
            
            # Export Checkbox
            var = tk.BooleanVar(value=self.right_export_selections.get(right_id, False))
            self.right_export_selections[right_id] = var.get()
            chk = ctk.CTkCheckBox(
                row_frame, 
                text="", 
                variable=var, 
                width=20, 
                command=lambda rid=right_id, v=var: self._on_export_checkbox_toggled("right", rid, v.get())
            )
            chk.pack(side="left", padx=5)
            
            lbl_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            lbl_frame.pack(side="left", fill="both", expand=True, padx=5)
            if not is_matched:
                lbl_frame.bind("<Button-1>", lambda e, rid=right_id: self._on_right_row_clicked(rid))
                
            text_color = self.cut_color if item["type"] == "Cut" else self.engrave_color
                
            thick_disp = item["thickness"] if is_metric else round(item["thickness"] / 25.4, 3)
            task_type = "Cut" if item["type"] == "Cut" else "Engrave"
            first_lbl_text = f"{item['material_name']} ({thick_disp:.1f}{unit_len} {task_type})"
            
            lbl_title = ctk.CTkLabel(
                lbl_frame, 
                text=first_lbl_text, 
                font=ctk.CTkFont(size=12, weight="bold"), 
                text_color=text_color,
                anchor="w"
            )
            lbl_title.pack(anchor="w")
            if not is_matched:
                lbl_title.bind("<Button-1>", lambda e, rid=right_id: self._on_right_row_clicked(rid))
                
            settings_str = f"{item['speed']:.1f} {unit_spd} @ {item['power']}%"
            if is_matched and matched_pair:
                match_idx = self.matched_pairs.index(matched_pair)
                l_item = next((x for x in left_list if x["id"] == matched_pair["left_id"]), None)
                if l_item:
                    l_thick = l_item["thickness"] if is_metric else round(l_item["thickness"] / 25.4, 3)
                    l_type = "Cut" if l_item["type"] == "Cut" else "Engrave"
                    other_name = f"{l_item['material_name']} ({l_thick:.1f}{unit_len} {l_type})"
                    settings_str += f"  [{match_idx + 1}) Matched to {other_name}]"
                else:
                    settings_str += f"  [{match_idx + 1}) Matched]"
                
            lbl_settings = ctk.CTkLabel(
                lbl_frame, 
                text=settings_str, 
                font=ctk.CTkFont(size=11), 
                text_color=text_color,
                anchor="w"
            )
            lbl_settings.pack(anchor="w")
            if not is_matched:
                lbl_settings.bind("<Button-1>", lambda e, rid=right_id: self._on_right_row_clicked(rid))
                
            if item.get("ev") is not None:
                is_cut = item["type"] == "Cut"
                unit_ev_disp = unit_ev if is_cut else ("J/mm²" if is_metric else "J/in²")
                label_ev = "Ev" if is_cut else "Ea"
                stats_str = f"{label_ev}: {item['ev']:.1f} {unit_ev_disp} | El: {item['el']:.2f} {unit_el}"
                lbl_stats = ctk.CTkLabel(
                    lbl_frame, 
                    text=stats_str, 
                    font=ctk.CTkFont(size=10, slant="italic"), 
                    text_color="#B0B0B0",
                    anchor="w"
                )
                lbl_stats.pack(anchor="w")
                if not is_matched:
                    lbl_stats.bind("<Button-1>", lambda e, rid=right_id: self._on_right_row_clicked(rid))

    def _on_export_checkbox_toggled(self, side, flat_id, value):
        if side == "left":
            self.left_export_selections[flat_id] = value
        else:
            self.right_export_selections[flat_id] = value

    def _on_compare_next(self):
        selected_entries = []
        left_list = getattr(self, "left_list_evaluated", self._get_active_l1_flat())
        right_list = getattr(self, "right_list_evaluated", self.compare_library_data_flat)
        
        is_metric = "Metric" in self.unit_system.get()
        laser_type = self.selected_laser_type.get()
        laser_data = self.reference_db.get("laser_types", {}).get(laser_type, {})
        v_max_cut_metric = self.max_speed.get() if is_metric else self.max_speed.get() * 25.4
        v_max_eng_metric = self.max_speed_eng.get() if is_metric else self.max_speed_eng.get() * 25.4
        p_min = self.min_power.get()
        p_max = self.max_power.get()
        
        for item in left_list:
            if self.left_export_selections.get(item["id"], False):
                selected_entries.append({
                    "material_name": item["material_name"],
                    "thickness": item["thickness"],
                    "desc": item["desc"] or ("Cut" if item["type"] == "Cut" else "Engrave"),
                    "type": item["type"],
                    "speed": item["speed"],
                    "power": item["power"],
                    "passes": item.get("passes", 1),
                    "interval": item.get("interval", 0.08)
                })
                
        wattage_compare = self.compare_wattage.get()
        for item in right_list:
            if self.right_export_selections.get(item["id"], False):
                speed = item["speed"]
                power = item["power"]
                passes = item.get("passes", 1)
                interval = item.get("interval", 0.08)
                
                standard_mat_name = self.parser._map_to_standard_material(item["material_name"])
                in_ref_db = standard_mat_name in laser_data.get("materials", {})
                
                if item["type"] == "Cut":
                    c_mat_override = None
                    if not in_ref_db:
                        c_mat_override = self.engine.calculate_material_cut_constant(
                            thickness=max(0.1, item["thickness"]),
                            speed=speed,
                            power=power,
                            passes=passes,
                            wattage=wattage_compare
                        )
                    pred = self.engine.predict_cutting_settings(
                        thickness=max(0.1, item["thickness"]),
                        material_name=standard_mat_name,
                        target_power=power,
                        target_passes=passes,
                        user_wattage=self.user_wattage.get(),
                        kappa_cut=self.kappa_cut.get(),
                        reference_materials=laser_data.get("materials", {}),
                        laser_type=laser_type,
                        v_max=v_max_cut_metric,
                        p_min=p_min,
                        p_max=p_max,
                        c_mat_override=c_mat_override
                    )
                    if pred:
                        speed = pred["speed"]
                        power = pred["power"]
                elif item["type"] == "Scan":
                    mode = item["desc"] or "Standard Engrave"
                    e_ref_override = None
                    if not in_ref_db:
                        e_ref_override = self.engine.calculate_material_engrave_constant(
                            speed=speed,
                            power=power,
                            interval=interval,
                            wattage=wattage_compare
                        )
                    pred = self.engine.predict_engraving_settings(
                        material_name=standard_mat_name,
                        mode=mode,
                        target_power=power,
                        target_interval=interval,
                        user_wattage=self.user_wattage.get(),
                        kappa_eng=self.kappa_eng.get(),
                        reference_materials=laser_data.get("materials", {}),
                        laser_type=laser_type,
                        v_max=v_max_eng_metric,
                        p_min=p_min,
                        p_max=p_max,
                        e_ref_override=e_ref_override
                    )
                    if pred:
                        speed = pred["speed"]
                        power = pred["power"]
                        
                selected_entries.append({
                    "material_name": item["material_name"],
                    "thickness": item["thickness"],
                    "desc": item["desc"] or ("Cut" if item["type"] == "Cut" else "Engrave"),
                    "type": item["type"],
                    "speed": speed,
                    "power": power,
                    "passes": passes,
                    "interval": interval
                })
                
        if not selected_entries:
            messagebox.showerror("Export Error", "Please select at least one material entry to export.")
            return
            
        RenameExportWindow(self, selected_entries, self._export_merged_library_callback)

    def _export_merged_library_callback(self, final_entries):
        file_path = filedialog.asksaveasfilename(
            title="Save Merged and Calibrated LightBurn Materials Library",
            defaultextension=".clb",
            filetypes=[("LightBurn Library", "*.clb")]
        )
        if not file_path:
            return

        try:
            self.parser.export_custom_clb(final_entries, file_path)
            messagebox.showinfo("Success", f"Merged LightBurn materials library successfully exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export library file: {e}")


class RenameExportWindow(ctk.CTkToplevel):
    def __init__(self, parent, selected_entries, export_callback):
        super().__init__(parent)
        self.parent = parent
        self.selected_entries = selected_entries
        self.export_callback = export_callback
        
        self.title("Export Configuration - Rename Material Profiles")
        self.geometry("680x500")
        self.grab_set() # Make it modal
        
        # Title Label
        ctk.CTkLabel(self, text="Configure Material Names & Descriptions", font=ctk.CTkFont(family="Inter", size=16, weight="bold")).pack(pady=15)
        
        # Scrollable container for entries
        self.scroll_frame = ctk.CTkScrollableFrame(self, height=340)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Header labels
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(header_frame, text="Source Settings", font=ctk.CTkFont(weight="bold"), width=160, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Export Material Name", font=ctk.CTkFont(weight="bold"), width=200, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Export Description/Thickness", font=ctk.CTkFont(weight="bold"), width=200, anchor="w").pack(side="left", padx=5)
        
        self.entry_fields = []
        
        for idx, entry in enumerate(self.selected_entries):
            row = ctk.CTkFrame(self.scroll_frame, fg_color="gray20", height=40)
            row.pack(fill="x", pady=4, padx=2)
            
            # Source description
            source_lbl = f"{entry['type']}: {entry['speed']} mm/s @ {entry['power']}%"
            lbl = ctk.CTkLabel(row, text=source_lbl, width=160, anchor="w", font=ctk.CTkFont(size=11))
            lbl.pack(side="left", padx=5)
            
            # Material name entry
            name_var = tk.StringVar(value=entry["material_name"])
            name_entry = ctk.CTkEntry(row, textvariable=name_var, width=190)
            name_entry.pack(side="left", padx=5)
            
            # Description entry
            desc_val = f"{entry.get('thickness', 0.0):.1f}mm" if entry["type"] == "Cut" else entry.get("desc", "Engrave")
            desc_var = tk.StringVar(value=desc_val)
            desc_entry = ctk.CTkEntry(row, textvariable=desc_var, width=190)
            desc_entry.pack(side="left", padx=5)
            
            self.entry_fields.append({
                "entry": entry,
                "name_var": name_var,
                "desc_var": desc_var
            })
            
        # Action Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=15, padx=20)
        
        self.export_btn = ctk.CTkButton(btn_frame, text="Generate CLB Library File", fg_color="#5CB85C", hover_color="#4CAE4C", command=self._on_export)
        self.export_btn.pack(side="right", padx=10)
        
        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray30", hover_color="gray40", command=self.destroy)
        self.cancel_btn.pack(side="left", padx=10)
        
    def _on_export(self):
        final_entries = []
        for item in self.entry_fields:
            orig = item["entry"]
            new_name = item["name_var"].get().strip()
            new_desc = item["desc_var"].get().strip()
            
            if not new_name:
                messagebox.showerror("Error", "Material name cannot be empty.")
                return
                
            thickness = orig.get("thickness", -1.0)
            if orig["type"] == "Cut":
                try:
                    thickness_clean = new_desc.replace("mm", "").replace("in", "").strip()
                    thickness = float(thickness_clean)
                except ValueError:
                    pass
            
            final_entries.append({
                "material_name": new_name,
                "thickness": thickness,
                "desc": new_desc,
                "type": orig["type"],
                "speed": orig["speed"],
                "power": orig["power"],
                "passes": orig.get("passes", 1),
                "interval": orig.get("interval", 0.08)
            })
            
        self.export_callback(final_entries)
        self.destroy()


class SettingAuditReportWindow(ctk.CTkToplevel):
    def __init__(self, parent, corrections):
        super().__init__(parent)
        self.parent = parent
        self.corrections = corrections
        
        self.title("Thermodynamic Auditor - Calibrated Settings Correction Report")
        self.geometry("780x450")
        self.grab_set() # Modal
        
        # Header title
        ctk.CTkLabel(self, text="⚠️ Thermodynamic Setting Corrections Applied", font=ctk.CTkFont(family="Inter", size=16, weight="bold"), text_color="#FF9F43").pack(pady=15)
        
        # Subtitle
        desc = (
            "The math engine successfully scaled your library, but detected and corrected "
            "physically inconsistent source settings (outliers deviating by >25% from verified "
            "material benchmarks) to ensure safe operations and clean cuts."
        )
        ctk.CTkLabel(self, text=desc, font=ctk.CTkFont(size=11), wraplength=700, justify="center").pack(pady=(0, 10))
        
        # Scrollable container for entries
        scroll_frame = ctk.CTkScrollableFrame(self, height=280)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Headers
        header_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(header_frame, text="Material & Size", font=ctk.CTkFont(weight="bold"), width=150, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Original Stock", font=ctk.CTkFont(weight="bold"), width=120, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Calibrated Setting", font=ctk.CTkFont(weight="bold"), width=130, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Energy Diff", font=ctk.CTkFont(weight="bold"), width=100, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Correction Rationale", font=ctk.CTkFont(weight="bold"), width=220, anchor="w").pack(side="left", padx=5)
        
        for idx, item in enumerate(self.corrections):
            row = ctk.CTkFrame(scroll_frame, fg_color="gray20", height=45)
            row.pack(fill="x", pady=4, padx=2)
            
            # Material name & thickness
            mat_lbl = f"{item['material']} ({item['thickness']})"
            ctk.CTkLabel(row, text=mat_lbl, width=150, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
            
            # Original
            ctk.CTkLabel(row, text=item["orig_setting"], width=120, anchor="w", font=ctk.CTkFont(size=11), text_color="#FF6B6B").pack(side="left", padx=5)
            
            # Calibrated
            ctk.CTkLabel(row, text=item["new_setting"], width=130, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="#51CF66").pack(side="left", padx=5)
            
            # Deviation
            ctk.CTkLabel(row, text=item["deviation"], width=100, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="#FF9F43").pack(side="left", padx=5)
            
            # Reason
            ctk.CTkLabel(row, text=item["reason"], width=220, anchor="w", font=ctk.CTkFont(size=10, slant="italic"), wraplength=200, justify="left").pack(side="left", padx=5)
            
        # Close Button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=15, padx=20)
        
        ctk.CTkButton(btn_frame, text="Close Report", fg_color="#1F6AA5", hover_color="#154B75", command=self.destroy).pack(side="right")


