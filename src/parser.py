import xml.etree.ElementTree as ET
import json
import os

class LightBurnParser:
    def __init__(self):
        pass

    def parse_clb(self, file_path):
        """
        Parse a LightBurn .clb or .clib XML file into a structured dictionary.
        Returns:
            dict: {
                "materials": [
                    {
                        "name": "Acrylic",
                        "entries": [
                            {
                                "thickness": 3.0,
                                "desc": "Cut",
                                "type": "Cut",
                                "speed": 3.0,
                                "power": 81.0,
                                "passes": 1,
                                "interval": 0.08,
                                "xml_node": Element  # We keep a copy of the XML node for structural re-export
                            }
                        ]
                    }
                ]
            }
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Material library file not found: {file_path}")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML file: {e}")

        library_data = {"materials": []}

        for mat_node in root.findall("Material"):
            mat_name = mat_node.get("name", "Unknown Material")
            material_entry = {"name": mat_name, "entries": []}

            for entry_node in mat_node.findall("Entry"):
                thickness = float(entry_node.get("Thickness", "-1.0"))
                desc = entry_node.get("Desc", "")
                no_thick_title = entry_node.get("NoThickTitle", "")

                cut_setting = entry_node.find("CutSetting")
                if cut_setting is None:
                    continue

                setting_type = cut_setting.get("type", "Cut")
                
                # Fetch sub-properties
                speed = 10.0
                speed_node = cut_setting.find("speed")
                if speed_node is not None:
                    speed = float(speed_node.get("Value", "10.0"))

                power = 50.0
                max_power_node = cut_setting.find("maxPower")
                if max_power_node is not None:
                    power = float(max_power_node.get("Value", "50.0"))

                passes = 1
                passes_node = cut_setting.find("numPasses")
                if passes_node is not None:
                    passes = int(passes_node.get("Value", "1"))

                interval = 0.08
                interval_node = cut_setting.find("interval")
                if interval_node is not None:
                    interval = float(interval_node.get("Value", "0.08"))

                material_entry["entries"].append({
                    "thickness": thickness,
                    "desc": desc,
                    "no_thick_title": no_thick_title,
                    "type": setting_type,
                    "speed": speed,
                    "power": power,
                    "passes": passes,
                    "interval": interval,
                    "entry_node": entry_node  # Preserve the exact XML reference
                })

            library_data["materials"].append(material_entry)

        return library_data

    def scale_and_export_clb(self, input_file_path, output_file_path, engine, source_wattage, target_wattage, kappa_cut, kappa_eng, reference_db, laser_type="CO2", v_max=80.0, v_max_eng=400.0, p_min=10.0, p_max=90.0, power_normalize_cap=None):
        """
        Parse an existing .clb file, scale all values using the math engine, 
        and write a fully compliant LightBurn XML library.
        Supports power_normalize_cap to limit power while scaling speed to preserve identical energy delivery.
        """
        tree = ET.parse(input_file_path)
        root = tree.getroot()

        for mat_node in root.findall("Material"):
            mat_name = mat_node.get("name")
            
            # Map material names to our standard database if possible (e.g. "Ply" -> "Birch Plywood")
            standard_mat_name = self._map_to_standard_material(mat_name)
            in_ref_db = standard_mat_name in reference_db

            for entry_node in mat_node.findall("Entry"):
                thickness = float(entry_node.get("Thickness", "-1.0"))
                cut_setting = entry_node.find("CutSetting")
                if cut_setting is None:
                    continue

                setting_type = cut_setting.get("type", "Cut")

                speed_node = cut_setting.find("speed")
                max_power_node = cut_setting.find("maxPower")
                min_power_node = cut_setting.find("minPower")
                passes_node = cut_setting.find("numPasses")
                interval_node = cut_setting.find("interval")

                current_speed = float(speed_node.get("Value", "10")) if speed_node is not None else 10.0
                current_power = float(max_power_node.get("Value", "50")) if max_power_node is not None else 50.0
                current_passes = int(passes_node.get("Value", "1")) if passes_node is not None else 1
                current_interval = float(interval_node.get("Value", "0.08")) if interval_node is not None else 0.08

                if setting_type == "Cut":
                    # Scale cutting speed
                    c_mat_override = None
                    if not in_ref_db:
                        c_mat_override = engine.calculate_material_cut_constant(
                            thickness=max(0.1, thickness),
                            speed=current_speed,
                            power=current_power,
                            passes=current_passes,
                            wattage=40.0
                        )
                    pred_cut = engine.predict_cutting_settings(
                        thickness=max(0.5, thickness),
                        material_name=standard_mat_name,
                        target_power=current_power,
                        target_passes=current_passes,
                        user_wattage=target_wattage,
                        kappa_cut=kappa_cut,
                        reference_materials=reference_db,
                        laser_type=laser_type,
                        v_max=v_max,
                        p_min=p_min,
                        p_max=p_max,
                        c_mat_override=c_mat_override,
                        power_normalize_cap=power_normalize_cap
                    )
                    if pred_cut is not None:
                        if speed_node is not None:
                            speed_node.set("Value", str(pred_cut["speed"]))
                        if max_power_node is not None:
                            max_power_node.set("Value", str(pred_cut["power"]))
                        if min_power_node is not None:
                            min_power_node.set("Value", str(pred_cut["power"]))
                        if passes_node is not None:
                            passes_node.set("Value", str(pred_cut["passes"]))
                        
                elif setting_type == "Scan":
                    # Scale engraving speed / power
                    mode = "Light Engrave" if current_power < 20 else "Deep Engrave"
                    e_ref_override = None
                    if not in_ref_db:
                        e_ref_override = engine.calculate_material_engrave_constant(
                            speed=current_speed,
                            power=current_power,
                            interval=current_interval,
                            wattage=40.0
                        )
                    pred_eng = engine.predict_engraving_settings(
                        material_name=standard_mat_name,
                        mode=mode,
                        target_power=current_power,
                        target_interval=current_interval,
                        user_wattage=target_wattage,
                        kappa_eng=kappa_eng,
                        reference_materials=reference_db,
                        laser_type=laser_type,
                        v_max=v_max_eng,
                        p_min=p_min,
                        p_max=p_max,
                        e_ref_override=e_ref_override,
                        power_normalize_cap=power_normalize_cap
                    )
                    if pred_eng is not None:
                        if speed_node is not None:
                            speed_node.set("Value", str(pred_eng["speed"]))
                        if max_power_node is not None:
                            max_power_node.set("Value", str(pred_eng["power"]))
                        # Match minPower to maxPower for CO2, or keep at 0
                        if min_power_node is not None:
                            min_power_node.set("Value", str(pred_eng["power"]))

        # Write out the modified XML
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        tree.write(output_file_path, encoding="UTF-8", xml_declaration=True)


    def export_k40_whisperer_txt(self, library_data, output_txt_path):
        """
        Generate a human-readable materials cheat sheet specifically optimized 
        for K40 Whisperer users (categorized by SVG color coding: Red = Cut, Blue = Engrave).
        """
        os.makedirs(os.path.dirname(output_txt_path), exist_ok=True)

        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("      K40 WHISPERER MATERIALS REFERENCE CHEAT SHEET\n")
            f.write("=" * 60 + "\n")
            f.write("Map SVG layers to these speeds and manual analog pot / digital settings.\n\n")

            for mat in library_data["materials"]:
                f.write(f"=== MATERIAL: {mat['name']} ===\n")
                cuts = [e for e in mat["entries"] if e["type"] == "Cut"]
                engraves = [e for e in mat["entries"] if e["type"] == "Scan"]

                if cuts:
                    f.write("  [RED LAYER - VECTOR CUTTING]\n")
                    for c in cuts:
                        f.write(f"    * {c['thickness']}mm Thick ({c['desc']}):\n")
                        f.write(f"      - Speed: {c['speed']} mm/s\n")
                        f.write(f"      - Recommended Power Setting: {c['power']}%\n")
                        if c['passes'] > 1:
                            f.write(f"      - Passes Required: {c['passes']}\n")
                        f.write("\n")

                if engraves:
                    f.write("  [BLUE/BLACK LAYER - RASTER ENGRAVING]\n")
                    for e in engraves:
                        title = e['no_thick_title'] or e['desc'] or "Standard Engrave"
                        f.write(f"    * {title}:\n")
                        f.write(f"      - Speed: {e['speed']} mm/s\n")
                        f.write(f"      - Recommended Power Setting: {e['power']}%\n")
                        f.write(f"      - Line Interval/DPI: {e['interval']}mm (~{round(25.4/e['interval'])} DPI)\n")
                        f.write("\n")

                f.write("-" * 60 + "\n\n")

    def _map_to_standard_material(self, name):
        """
        Clean and map library material names to our standard internal JSON keys.
        """
        name_lower = name.lower()
        if "ply" in name_lower or "birch" in name_lower or "wood" in name_lower:
            return "Birch Plywood"
        elif "acrylic" in name_lower or "plexiglass" in name_lower:
            return "Acrylic (Clear/Cast)"
        elif "mdf" in name_lower:
            return "MDF"
        elif "cardboard" in name_lower:
            return "Cardboard"
        elif "leather" in name_lower:
            return "Leather (Veg-Tanned)"
        return "Birch Plywood" # Fallback

    def export_custom_clb(self, entries, output_file_path):
        """
        Build a compliant LightBurn XML library from scratch for custom merged entries.
        """
        root = ET.Element("LightBurnLibraryVersion")
        
        # Group entries by material name
        materials_map = {}
        for entry in entries:
            name = entry["material_name"]
            if name not in materials_map:
                materials_map[name] = []
            materials_map[name].append(entry)
            
        for mat_name, mat_entries in materials_map.items():
            mat_node = ET.SubElement(root, "Material", name=mat_name)
            for entry in mat_entries:
                thickness_str = f"{entry.get('thickness', -1.0):.3f}"
                desc_str = entry.get('desc', 'Setting')
                # If engraving mode title is empty, fallback
                if entry["type"] == "Scan" and not desc_str:
                    desc_str = "Standard Engrave"
                entry_node = ET.SubElement(mat_node, "Entry", Thickness=thickness_str, Desc=desc_str)
                
                setting_type = entry["type"]
                # Convert "Scan" or "Cut" setting type to LightBurn format
                cut_setting = ET.SubElement(entry_node, "CutSetting", type=setting_type)
                
                # Speed
                ET.SubElement(cut_setting, "speed", Value=str(entry["speed"]))
                # Powers
                ET.SubElement(cut_setting, "maxPower", Value=str(entry["power"]))
                ET.SubElement(cut_setting, "minPower", Value=str(entry["power"]))
                
                if setting_type == "Cut":
                    # Passes
                    ET.SubElement(cut_setting, "numPasses", Value=str(int(entry.get("passes", 1))))
                elif setting_type == "Scan":
                    # Interval
                    ET.SubElement(cut_setting, "interval", Value=str(entry.get("interval", 0.08)))
                    
        # Write out
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        tree = ET.ElementTree(root)
        tree.write(output_file_path, encoding="UTF-8", xml_declaration=True)
