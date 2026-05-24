import math

class LaserMathEngine:
    def __init__(self):
        # Default beam spot sizes at different nominal wattages
        # A 40W CO2 has ~0.08mm spot, whereas a 130W CO2 has ~0.20mm spot.
        self.ref_spot_size = 0.08  # mm

    def calculate_spot_size(self, wattage, laser_type="CO2"):
        """
        Estimate spot size in mm based on nominal wattage and laser type.
        High-power tubes physically produce a larger beam diameter and spot size.
        """
        if laser_type != "CO2":
            # Diodes and Fibers have much smaller spot sizes, generally more stable across power
            if laser_type == "Diode":
                return 0.05
            elif laser_type == "Fiber":
                return 0.02
            return 0.08
            
        # CO2 spot size scaling model
        if wattage <= 40.0:
            return 0.08
        else:
            # Non-linear scaling: grows roughly with the square root of wattage ratio
            return 0.08 * math.sqrt(wattage / 40.0)

    def calculate_material_cut_constant(self, thickness, speed, power, passes, wattage):
        """
        Calculate the raw cutting resistance constant of a material based on a cut.
        Higher constant = harder to cut.
        """
        if speed <= 0 or thickness <= 0 or power <= 0 or wattage <= 0:
            return 0.0
        
        # Energy density required = (Power_watts * Passes) / (Speed * Thickness)
        # Power_watts = nominal_wattage * power_percentage
        power_watts = wattage * (power / 100.0)
        return (power_watts * passes) / (speed * thickness)

    def calculate_material_engrave_constant(self, speed, power, interval, wattage):
        """
        Calculate the raw engraving energy density constant (J/mm^2) for a target finish.
        """
        if speed <= 0 or power <= 0 or interval <= 0 or wattage <= 0:
            return 0.0
            
        power_watts = wattage * (power / 100.0)
        # Energy per unit area = Power / (Speed * Line_Interval)
        return power_watts / (speed * interval)

    def calibrate_machine_cut_factor(self, test_cuts, reference_materials):
        """
        Perform a linear least-squares regression to solve for the user's Machine Efficiency Constant (kappa_cut).
        Each test cut should be a dict: {
            "material_name": str,
            "thickness_mm": float,
            "speed": float,
            "power": float,
            "passes": int,
            "wattage": float
        }
        reference_materials: dict of material_name -> reference model data.
        Returns:
            float: User's machine cutting factor (kappa_cut, where 1.0 is default).
        """
        sum_xy = 0.0
        sum_xx = 0.0
        
        for cut in test_cuts:
            mat_name = cut["material_name"]
            d = cut["thickness_mm"]
            v_user = cut["speed"]
            p_user = cut["power"]
            n_user = cut["passes"]
            w_user = cut["wattage"]
            
            if mat_name not in reference_materials:
                continue
                
            # Find the reference data point matching or closest to this thickness
            ref_cuts = reference_materials[mat_name].get("cutting", [])
            if not ref_cuts:
                continue
                
            # Find the closest reference thickness to calculate the base material constant
            closest_ref = min(ref_cuts, key=lambda x: abs(x["thickness_mm"] - d))
            
            # Base material constant from reference data (assuming ref machine factor = 1.0)
            c_mat = self.calculate_material_cut_constant(
                thickness=closest_ref["thickness_mm"],
                speed=closest_ref["ref_speed"],
                power=closest_ref["ref_power"],
                passes=closest_ref["ref_passes"],
                wattage=40.0 # Standard K40 reference wattage is 40W
            )
            
            if c_mat <= 0:
                continue
                
            # Modeled speed without the machine factor:
            # v_model = (Power_watts * Passes) / (thickness * c_mat)
            power_watts_user = w_user * (p_user / 100.0)
            v_model = (power_watts_user * n_user) / (d * c_mat)
            
            # Accumulate values for linear regression slope (y = kappa * x)
            # y = actual user speed (v_user), x = modeled speed (v_model)
            sum_xy += v_model * v_user
            sum_xx += v_model * v_model
            
        if sum_xx == 0.0:
            return 1.0 # Default factor if no regression possible
            
        return sum_xy / sum_xx

    def calibrate_machine_engrave_factor(self, test_engraves, reference_materials):
        """
        Solve for the user's Machine Engraving Constant (kappa_engrave) using least-squares regression.
        Each test_engrave: {
            "material_name": str,
            "mode": str,  # e.g., "Light Engrave", "Frosted Engrave"
            "speed": float,
            "power": float,
            "interval_mm": float,
            "wattage": float
        }
        """
        sum_xy = 0.0
        sum_xx = 0.0
        
        for eng in test_engraves:
            mat_name = eng["material_name"]
            mode = eng["mode"]
            v_user = eng["speed"]
            p_user = eng["power"]
            i_user = eng["interval_mm"]
            w_user = eng["wattage"]
            
            if mat_name not in reference_materials:
                continue
                
            ref_engs = reference_materials[mat_name].get("engraving", [])
            matching_ref = next((x for x in ref_engs if x["mode"] == mode), None)
            if not matching_ref:
                continue
                
            # Reference energy constant (using 40W ref machine)
            e_ref = self.calculate_material_engrave_constant(
                speed=matching_ref["ref_speed"],
                power=matching_ref["ref_power"],
                interval=matching_ref["interval_mm"],
                wattage=40.0
            )
            
            if e_ref <= 0:
                continue
                
            # Modeled speed for user:
            # v_model = Power_watts / (interval * e_ref)
            power_watts_user = w_user * (p_user / 100.0)
            v_model = power_watts_user / (i_user * e_ref)
            
            sum_xy += v_model * v_user
            sum_xx += v_model * v_model
            
        if sum_xx == 0.0:
            return 1.0
            
        return sum_xy / sum_xx

    def analyze_cut_tests(self, test_cuts, reference_materials):
        """
        Analyze a list of cutting tests. Compute individual kappa_cut values,
        and calculate statistics: average, range, and standard deviation.
        Keeps 1-to-1 mapping index alignment with the input tests.
        """
        kappas = []
        details = []
        
        for cut in test_cuts:
            mat_name = cut["material_name"]
            d = cut["thickness_mm"]
            v_user = cut["speed"]
            p_user = cut["power"]
            n_user = cut["passes"]
            w_user = cut["wattage"]
            
            if mat_name not in reference_materials:
                details.append({"kappa": None, "deviation": None})
                continue
            ref_cuts = reference_materials[mat_name].get("cutting", [])
            if not ref_cuts:
                details.append({"kappa": None, "deviation": None})
                continue
                
            closest_ref = min(ref_cuts, key=lambda x: abs(x["thickness_mm"] - d))
            c_mat = self.calculate_material_cut_constant(
                thickness=closest_ref["thickness_mm"],
                speed=closest_ref["ref_speed"],
                power=closest_ref["ref_power"],
                passes=closest_ref["ref_passes"],
                wattage=40.0
            )
            if c_mat <= 0:
                details.append({"kappa": None, "deviation": None})
                continue
                
            power_watts_user = w_user * (p_user / 100.0)
            v_model = (power_watts_user * n_user) / (d * c_mat)
            if v_model <= 0:
                details.append({"kappa": None, "deviation": None})
                continue
                
            kappa_i = v_user / v_model
            kappas.append(kappa_i)
            details.append({"kappa": round(kappa_i, 4), "deviation": 0.0})
            
        if not kappas:
            return {
                "average": 1.0, "min": 1.0, "max": 1.0, "std_dev": 0.0, "count": 0,
                "individual_kappas": [], "details": [{"kappa": None, "deviation": None} for _ in test_cuts]
            }
            
        avg = sum(kappas) / len(kappas)
        std_dev = math.sqrt(sum((x - avg) ** 2 for x in kappas) / len(kappas))
        
        # Populate deviations
        for item in details:
            if item["kappa"] is not None:
                item["deviation"] = round(item["kappa"] - avg, 4)
                
        return {
            "average": round(avg, 4),
            "min": round(min(kappas), 4),
            "max": round(max(kappas), 4),
            "std_dev": round(std_dev, 4),
            "count": len(kappas),
            "individual_kappas": [round(k, 4) for k in kappas],
            "details": details
        }

    def analyze_engrave_tests(self, test_engraves, reference_materials):
        """
        Analyze a list of engraving tests. Compute individual kappa_eng values,
        and calculate statistics: average, range, and standard deviation.
        Keeps 1-to-1 mapping index alignment with the input tests.
        """
        kappas = []
        details = []
        
        for eng in test_engraves:
            mat_name = eng["material_name"]
            mode = eng["mode"]
            v_user = eng["speed"]
            p_user = eng["power"]
            i_user = eng["interval_mm"]
            w_user = eng["wattage"]
            
            if mat_name not in reference_materials:
                details.append({"kappa": None, "deviation": None})
                continue
            ref_engs = reference_materials[mat_name].get("engraving", [])
            matching_ref = next((x for x in ref_engs if x["mode"] == mode), None)
            if not matching_ref:
                details.append({"kappa": None, "deviation": None})
                continue
                
            e_ref = self.calculate_material_engrave_constant(
                speed=matching_ref["ref_speed"],
                power=matching_ref["ref_power"],
                interval=matching_ref["interval_mm"],
                wattage=40.0
            )
            if e_ref <= 0:
                details.append({"kappa": None, "deviation": None})
                continue
                
            power_watts_user = w_user * (p_user / 100.0)
            v_model = power_watts_user / (i_user * e_ref)
            if v_model <= 0:
                details.append({"kappa": None, "deviation": None})
                continue
                
            kappa_i = v_user / v_model
            kappas.append(kappa_i)
            details.append({"kappa": round(kappa_i, 4), "deviation": 0.0})
            
        if not kappas:
            return {
                "average": 1.0, "min": 1.0, "max": 1.0, "std_dev": 0.0, "count": 0,
                "individual_kappas": [], "details": [{"kappa": None, "deviation": None} for _ in test_engraves]
            }
            
        avg = sum(kappas) / len(kappas)
        std_dev = math.sqrt(sum((x - avg) ** 2 for x in kappas) / len(kappas))
        
        # Populate deviations
        for item in details:
            if item["kappa"] is not None:
                item["deviation"] = round(item["kappa"] - avg, 4)
                
        return {
            "average": round(avg, 4),
            "min": round(min(kappas), 4),
            "max": round(max(kappas), 4),
            "std_dev": round(std_dev, 4),
            "count": len(kappas),
            "individual_kappas": [round(k, 4) for k in kappas],
            "details": details
        }


    def scale_kerf_width(self, base_kerf, focal_length=None, units="metric"):
        """
        Scale the laser cutting kerf based on focal length and unit system.
        Gaussian beam spot size is directly proportional to focal length (w0 = 4 * lambda * f / (pi * D)).
        Reference lens focal length is 2.0" (50.8 mm).
        """
        if focal_length is None or focal_length <= 0:
            return base_kerf
        ref_focal = 50.8 if units == "metric" else 2.0
        return base_kerf * (focal_length / ref_focal)

    def calculate_specific_energy_cut(self, speed, power, thickness, kerf, wattage, focal_length=None, units="metric"):
        """
        Compute Specific Energy (Ev) in Joules per unit volume (J/mm^3 or J/in^3).
        Ev = P / (v * w * t)
        where P is effective power (Watts or J/s), v is speed (mm/s or in/s), w is kerf (mm or in), t is thickness (mm or in).
        """
        if speed <= 0 or thickness <= 0 or power <= 0 or wattage <= 0 or kerf <= 0:
            return 0.0
        
        scaled_w = self.scale_kerf_width(kerf, focal_length, units)
        effective_power = wattage * (power / 100.0)
        volume_per_second = speed * scaled_w * thickness
        return effective_power / volume_per_second

    def calculate_specific_energy_engrave(self, speed, power, interval, kerf, wattage, focal_length=None, units="metric"):
        """
        Compute Areal Energy Density (Ea) in Joules per unit area for engraving (J/mm^2 or J/in^2).
        Ea = P / (v * i)
        where P is effective power (Watts), v is speed (mm/s or in/s), i is line interval (mm or in).
        """
        if speed <= 0 or interval <= 0 or power <= 0 or wattage <= 0:
            return 0.0
        effective_power = wattage * (power / 100.0)
        return effective_power / (speed * interval)

    def calculate_linear_energy_density(self, speed, power, wattage):
        """
        Compute Linear Energy Density (El) in Joules per unit length (J/mm or J/in).
        El = P / v
        where P is effective power (Watts) and v is speed (mm/s or in/s).
        """
        if speed <= 0 or power <= 0 or wattage <= 0:
            return 0.0
        effective_power = wattage * (power / 100.0)
        return effective_power / speed

    def predict_cutting_settings(self, thickness, material_name, target_power, target_passes, user_wattage, kappa_cut, reference_materials, laser_type="CO2", v_max=80.0, p_min=10.0, p_max=90.0, c_mat_override=None, power_normalize_cap=None):
        """
        Predict the target cutting speed and power for a given material, thickness, and target power percentage.
        Respects machine safety constraints (v_max, p_min, p_max) and scales settings to maintain target specific energy.
        Allows c_mat_override to support universal, database-independent custom material scaling.
        Supports power_normalize_cap to limit power while scaling speed to preserve identical energy delivery.
        """
        if c_mat_override is not None:
            c_mat = c_mat_override
        else:
            if material_name not in reference_materials:
                return None
                
            ref_cuts = reference_materials[material_name].get("cutting", [])
            if not ref_cuts:
                return None
                
            closest_ref = min(ref_cuts, key=lambda x: abs(x["thickness_mm"] - thickness))
            c_mat = self.calculate_material_cut_constant(
                thickness=closest_ref["thickness_mm"],
                speed=closest_ref["ref_speed"],
                power=closest_ref["ref_power"],
                passes=closest_ref["ref_passes"],
                wattage=40.0
            )
        
        if c_mat <= 0:
            return None
            
        # If a power normalization cap is specified, restrict our upper power bound
        effective_p_max = p_max
        if power_normalize_cap is not None:
            effective_p_max = min(p_max, power_normalize_cap)

        # 1. Enforce power durability limits on inputted target power
        clamped_power = max(p_min, min(effective_p_max, target_power))
        
        # 2. Predict base cutting speed at clamped power
        ref_spot = self.calculate_spot_size(40.0, "CO2")
        user_spot = self.calculate_spot_size(user_wattage, laser_type)
        spot_ratio = ref_spot / user_spot
        
        power_watts = user_wattage * (clamped_power / 100.0)
        predicted_speed = kappa_cut * (power_watts * target_passes * spot_ratio) / (thickness * c_mat)
        
        # 3. Enforce maximum gantry speed constraint
        if predicted_speed > v_max:
            # If speed is too fast for gantry, reduce the power to maintain the target energy density at v_max
            scaled_power_watts = (v_max * thickness * c_mat) / (kappa_cut * target_passes * spot_ratio)
            scaled_power_pct = (scaled_power_watts / user_wattage) * 100.0
            
            # Clamp the adjusted power within min/max thresholds
            clamped_power = max(p_min, min(effective_p_max, scaled_power_pct))
            predicted_speed = v_max
            
        elif predicted_speed < 0.5:
            # Prevent stalling and fire risk
            predicted_speed = 0.5
            
        return {
            "speed": round(predicted_speed, 1),
            "power": round(clamped_power, 1),
            "passes": target_passes
        }

    def predict_engraving_settings(self, material_name, mode, target_power, target_interval, user_wattage, kappa_eng, reference_materials, laser_type="CO2", v_max=400.0, p_min=10.0, p_max=90.0, e_ref_override=None, power_normalize_cap=None):
        """
        Predict the engraving speed and power for a given material and mode.
        Respects machine safety constraints (v_max, p_min, p_max).
        Allows e_ref_override to support universal, database-independent custom material scaling.
        Supports power_normalize_cap to limit power while scaling speed to preserve identical energy delivery.
        """
        if e_ref_override is not None:
            e_ref = e_ref_override
        else:
            if material_name not in reference_materials:
                return None
                
            ref_engs = reference_materials[material_name].get("engraving", [])
            matching_ref = next((x for x in ref_engs if x["mode"] == mode), None)
            if not matching_ref:
                return None
                
            e_ref = self.calculate_material_engrave_constant(
                speed=matching_ref["ref_speed"],
                power=matching_ref["ref_power"],
                interval=matching_ref["interval_mm"],
                wattage=40.0
            )
        
        if e_ref <= 0:
            return None
            
        # If a power normalization cap is specified, restrict our upper power bound
        effective_p_max = p_max
        if power_normalize_cap is not None:
            effective_p_max = min(p_max, power_normalize_cap)

        clamped_power = max(p_min, min(effective_p_max, target_power))
        
        ref_spot = self.calculate_spot_size(40.0, "CO2")
        user_spot = self.calculate_spot_size(user_wattage, laser_type)
        spot_ratio = ref_spot / user_spot
        
        power_watts = user_wattage * (clamped_power / 100.0)
        predicted_speed = kappa_eng * (power_watts * spot_ratio) / (target_interval * e_ref)
        
        if predicted_speed > v_max:
            # Reduce power to keep speed at v_max
            scaled_power_watts = (v_max * target_interval * e_ref) / (kappa_eng * spot_ratio)
            scaled_power_pct = (scaled_power_watts / user_wattage) * 100.0
            clamped_power = max(p_min, min(effective_p_max, scaled_power_pct))
            predicted_speed = v_max
        elif predicted_speed < 10.0:
            predicted_speed = 10.0
            
        return {
            "speed": round(predicted_speed, 0),
            "power": round(clamped_power, 1),
            "interval_mm": target_interval
        }

    def normalize_to_power_cap(self, speed, power, power_cap, min_speed=0.5):
        """
        Cap the power at a given percentage (power_cap) and scale down the speed
        proportionally to maintain the exact same energy delivery to the material.
        """
        if power <= power_cap or power <= 0:
            return {"speed": speed, "power": power, "normalized": False}
        
        ratio = power_cap / power
        new_speed = max(min_speed, round(speed * ratio, 2))
        return {"speed": new_speed, "power": power_cap, "normalized": True}

