import sys
import os

# Put src in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.math_engine import LaserMathEngine
from src.parser import LightBurnParser

def run_tests():
    print("=" * 60)
    print("        RUNNING LASER SETTINGS ENGINE VERIFICATION TESTS")
    print("=" * 60)
    
    engine = LaserMathEngine()
    parser = LightBurnParser()
    
    # 1. Test Spot Size calculation
    print("[TEST 1] Testing Spot Size Calibration...")
    spot_40 = engine.calculate_spot_size(40.0, "CO2")
    spot_80 = engine.calculate_spot_size(80.0, "CO2")
    spot_130 = engine.calculate_spot_size(130.0, "CO2")
    print(f"  * 40W Spot Size: {spot_40:.3f} mm")
    print(f"  * 80W Spot Size: {spot_80:.3f} mm (Expected: ~0.113 mm)")
    print(f"  * 130W Spot Size: {spot_130:.3f} mm (Expected: ~0.144 mm)")
    assert spot_40 == 0.08, "Baseline 40W spot size incorrect"
    assert spot_80 > spot_40, "80W spot size should be larger than 40W spot size due to tube thickness"
    print("  => SUCCESS!")

    # 2. Test regression for cutting (solving for machine constant kappa)
    print("\n[TEST 2] Testing Linear Least-Squares Cut Calibration...")
    
    # Mock reference material database
    ref_db = {
        "Birch Plywood": {
            "cutting": [
                {"thickness_mm": 3.0, "ref_speed": 10.0, "ref_power": 60.0, "ref_passes": 1}
            ]
        }
    }
    
    # User cuts 3mm Birch Plywood at Speed 8 instead of reference 10, meaning their machine is slightly less efficient (kappa ~ 0.8)
    test_cuts = [{
        "material_name": "Birch Plywood",
        "thickness_mm": 3.0,
        "speed": 8.0,
        "power": 60.0,
        "passes": 1,
        "wattage": 40.0
    }]
    
    kappa_solved = engine.calibrate_machine_cut_factor(test_cuts, ref_db)
    print(f"  * Solved Cut Constant (kappa_cut): {kappa_solved:.2f}x (Expected: 0.80)")
    assert abs(kappa_solved - 0.80) < 0.01, "Cut calibration regression failed to converge correctly"
    print("  => SUCCESS!")

    # 3. Test engraving predictions
    print("\n[TEST 3] Testing Engraving Vector Scaling and Speed Safeguards...")
    ref_db_eng = {
        "Acrylic (Clear/Cast)": {
            "engraving": [
                {"mode": "Frosted Engrave", "ref_speed": 150.0, "ref_power": 12.0, "interval_mm": 0.08}
            ]
        }
    }
    
    # Predict settings for a stronger 80W laser cutting acrylic (more power means we can run faster)
    pred_eng = engine.predict_engraving_settings(
        material_name="Acrylic (Clear/Cast)",
        mode="Frosted Engrave",
        target_power=20.0,
        target_interval=0.08,
        user_wattage=80.0,
        kappa_eng=1.0,
        reference_materials=ref_db_eng
    )
    print(f"  * 80W predicted engrave settings: {pred_eng}")
    assert pred_eng["speed"] > 150.0, "80W laser should engrave faster than 40W reference"
    print("  => SUCCESS!")

    # 4. Test Parser mapping and parsing consistency
    print("\n[TEST 4] Testing Material Name Mapping...")
    assert parser._map_to_standard_material("monport acrylic sheet") == "Acrylic (Clear/Cast)"
    assert parser._map_to_standard_material("Birch Ply 3mm") == "Birch Plywood"
    assert parser._map_to_standard_material("Premium MDF Board") == "MDF"
    print("  => SUCCESS!")

    # 5. Test Multi-Test statistics calculations
    print("\n[TEST 5] Testing Multi-Test Calibration Statistical Solver...")
    multi_test_cuts = [
        {
            "material_name": "Birch Plywood",
            "thickness_mm": 3.0,
            "speed": 8.0,      # Yields kappa = 0.8
            "power": 60.0,
            "passes": 1,
            "wattage": 40.0
        },
        {
            "material_name": "Birch Plywood",
            "thickness_mm": 3.0,
            "speed": 12.0,     # Yields kappa = 1.2
            "power": 60.0,
            "passes": 1,
            "wattage": 40.0
        }
    ]
    
    stats = engine.analyze_cut_tests(multi_test_cuts, ref_db)
    print(f"  * Multi-cut Solved Stats: {stats}")
    assert stats["count"] == 2, "Test count should be 2"
    assert abs(stats["average"] - 1.00) < 0.01, "Average calibration should be 1.00"
    assert abs(stats["min"] - 0.80) < 0.01, "Min calibration should be 0.80"
    assert abs(stats["max"] - 1.20) < 0.01, "Max calibration should be 1.20"
    assert abs(stats["std_dev"] - 0.20) < 0.01, "Standard deviation should be 0.20"
    print("  => SUCCESS!")

    # 6. Test Thermodynamic Energy and Kerf Focal Length Scaling
    print("\n[TEST 6] Testing Thermodynamic Energy & Focal Kerf Scaling...")
    # Base kerf = 0.15mm
    # With no focal length supplied, should use default base kerf (approximation ratio = 1.0)
    w_unsupplied = engine.scale_kerf_width(0.15, None)
    print(f"  * Unsupplied Focal Length Kerf: {w_unsupplied:.3f} mm (Expected: 0.150 mm)")
    assert abs(w_unsupplied - 0.15) < 0.001, "Kerf should not be scaled when focal length is unsupplied"

    # With focal length = 1.5" lens (38.1 mm), scaled kerf = 0.15 * (38.1 / 50.8) = 0.1125 mm
    w_scaled = engine.scale_kerf_width(0.15, 38.1)
    print(f"  * 1.5\" Focal Length Kerf: {w_scaled:.4f} mm (Expected: 0.1125 mm)")
    assert abs(w_scaled - 0.1125) < 0.0001, "Kerf focal length scaling formula is incorrect"

    # Ev = P / (v * w * t)
    # Power = 40W * 50% = 20W. Speed = 10 mm/s. Kerf = 0.15mm. Thickness = 3.0mm.
    # Unscaled kerf (ratio = 1.0)
    # Ev = 20 / (10 * 0.15 * 3.0) = 20 / 4.5 = 4.444 J/mm^3
    ev_val = engine.calculate_specific_energy_cut(
        speed=10.0,
        power=50.0,
        thickness=3.0,
        kerf=0.15,
        wattage=40.0,
        focal_length=None
    )
    print(f"  * Specific Energy Ev (unscaled): {ev_val:.3f} J/mm^3 (Expected: 4.444 J/mm^3)")
    assert abs(ev_val - 4.444) < 0.01, "Specific energy calculation is incorrect"

    # El = P / v
    # Power = 40W * 50% = 20W. Speed = 10 mm/s.
    # El = 20 / 10 = 2.0 J/mm
    el_val = engine.calculate_linear_energy_density(
        speed=10.0,
        power=50.0,
        wattage=40.0
    )
    print(f"  * Linear Energy Density El: {el_val:.2f} J/mm (Expected: 2.00 J/mm)")
    assert abs(el_val - 2.0) < 0.01, "Linear energy density calculation is incorrect"
    print("  => SUCCESS!")

    # 7. Test safety bounds & clamping constraints in predictions
    print("\n[TEST 7] Testing Safety Bounds & Clamp Constraints in Cut Predictions...")
    ref_db_cut = {
        "Birch Plywood": {
            "cutting": [
                {"thickness_mm": 3.0, "ref_speed": 10.0, "ref_power": 60.0, "ref_passes": 1}
            ]
        }
    }
    # Predict settings with high target power of 95% but max power clamp = 80%
    # The system should clamp the power to 80% and scale the speed down to maintain same specific energy!
    # c_mat = (40 * 0.6) / (10 * 3) = 24 / 30 = 0.8 J/mm^2
    # At wattage 40W, kappa = 1.0, and target passes = 1, ref_spot/user_spot = 1.0:
    # predicted speed before constraints at target power 95%:
    # speed = 1.0 * (40 * 0.95) / (3 * 0.8) = 38 / 2.4 = 15.83 mm/s
    # Max Power constraint is 80%, so power clamps to 80%.
    # predicted speed at clamped power 80%:
    # speed = 1.0 * (40 * 0.8) / (3 * 0.8) = 32 / 2.4 = 13.33 mm/s
    pred_clamped = engine.predict_cutting_settings(
        thickness=3.0,
        material_name="Birch Plywood",
        target_power=95.0,
        target_passes=1,
        user_wattage=40.0,
        kappa_cut=1.0,
        reference_materials=ref_db_cut,
        laser_type="CO2",
        v_max=80.0,
        p_min=10.0,
        p_max=80.0
    )
    print(f"  * Power-clamped Cut Settings: {pred_clamped} (Expected power: 80.0%, speed: 13.3 mm/s)")
    assert pred_clamped["power"] == 80.0, "Power did not clamp to max_power constraint"
    assert abs(pred_clamped["speed"] - 13.3) < 0.1, "Speed not correctly predicted at clamped power"

    # Now let's test a case where predicted speed is faster than v_max (e.g. v_max = 5.0 mm/s)
    # The system should clamp the speed to 5.0 mm/s, and scale power down to maintain energy density!
    # At target power 50%:
    # Base predicted speed = (40 * 0.5) / 2.4 = 20 / 2.4 = 8.33 mm/s
    # v_max is 5.0 mm/s. Since predicted speed 8.33 > 5.0, speed is clamped to 5.0.
    # Scaled power = (v_max * t * c_mat) / kappa = (5.0 * 3.0 * 0.8) = 12.0 Watts.
    # Scaled power % = (12.0 / 40.0) * 100 = 30.0%
    pred_speed_clamped = engine.predict_cutting_settings(
        thickness=3.0,
        material_name="Birch Plywood",
        target_power=50.0,
        target_passes=1,
        user_wattage=40.0,
        kappa_cut=1.0,
        reference_materials=ref_db_cut,
        laser_type="CO2",
        v_max=5.0,
        p_min=10.0,
        p_max=90.0
    )
    print(f"  * Speed-clamped Cut Settings: {pred_speed_clamped} (Expected speed: 5.0 mm/s, power: 30.0%)")
    assert pred_speed_clamped["speed"] == 5.0, "Speed did not clamp to max_speed constraint"
    assert abs(pred_speed_clamped["power"] - 30.0) < 0.1, "Power did not scale down to maintain specific energy"
    # 8. Test Imperial Specific Energy and Focal Kerf Scaling
    print("\n[TEST 8] Testing Imperial Energy Density & Focal Kerf Scaling...")
    # Base kerf = 0.0059 in (approx 0.15mm)
    # Unsupplied focal length, ratio = 1.0
    w_unsupplied_imp = engine.scale_kerf_width(0.0059, None, "imperial")
    print(f"  * Unsupplied Focal Length Kerf (Imp): {w_unsupplied_imp:.5f} in (Expected: 0.00590 in)")
    assert abs(w_unsupplied_imp - 0.0059) < 0.0001, "Imperial kerf should not be scaled when focal length is unsupplied"

    # Scaled focal length = 1.5" lens, scaled kerf = 0.0059 * (1.5 / 2.0) = 0.004425 in
    w_scaled_imp = engine.scale_kerf_width(0.0059, 1.5, "imperial")
    print(f"  * 1.5\" Focal Length Kerf (Imp): {w_scaled_imp:.6f} in (Expected: 0.004425 in)")
    assert abs(w_scaled_imp - 0.004425) < 0.00001, "Imperial kerf focal length scaling formula is incorrect"

    # Imperial Ev = P / (v * w * t)
    # Power = 40W * 50% = 20W. Speed = 0.3937 in/s. Kerf = 0.0059 in. Thickness = 0.1181 in.
    # Ev = 20 / (0.3937 * 0.0059 * 0.1181) = 20 / 0.00027429 = 72915 J/in^3
    ev_val_imp = engine.calculate_specific_energy_cut(
        speed=0.3937,
        power=50.0,
        thickness=0.1181,
        kerf=0.0059,
        wattage=40.0,
        focal_length=None,
        units="imperial"
    )
    print(f"  * Specific Energy Ev (Imperial): {ev_val_imp:.1f} J/in^3 (Expected: ~72915 J/in^3)")
    assert abs(ev_val_imp - 72915) < 100, "Imperial specific energy calculation is incorrect"

    # Imperial El = P / v
    # Power = 40W * 50% = 20W. Speed = 0.3937 in/s.
    # El = 20 / 0.3937 = 50.80 J/in
    el_val_imp = engine.calculate_linear_energy_density(
        speed=0.3937,
        power=50.0,
        wattage=40.0
    )
    print(f"  * Linear Energy Density El (Imperial): {el_val_imp:.2f} J/in (Expected: 50.80 J/in)")
    assert abs(el_val_imp - 50.80) < 0.1, "Imperial linear energy density calculation is incorrect"
    # 9. Test High Power Normalization
    print("\n[TEST 9] Testing High Power Normalization...")
    # Base predicted speed at 95% is 15.83 mm/s.
    # Normalizing with cap = 80% should yield speed = 13.3 mm/s and power = 80.0%
    pred_normalized = engine.predict_cutting_settings(
        thickness=3.0,
        material_name="Birch Plywood",
        target_power=95.0,
        target_passes=1,
        user_wattage=40.0,
        kappa_cut=1.0,
        reference_materials=ref_db_cut,
        laser_type="CO2",
        v_max=80.0,
        p_min=10.0,
        p_max=90.0,
        power_normalize_cap=80.0
    )
    print(f"  * Normalized Cut Settings: {pred_normalized} (Expected power: 80.0%, speed: 13.3 mm/s)")
    assert pred_normalized["power"] == 80.0, "Normalization did not cap power at 80%"
    assert abs(pred_normalized["speed"] - 13.3) < 0.1, "Normalization did not scale speed correctly to preserve energy density"

    # Explicit utility call testing: speed 10.0 mm/s @ 95% power normalized to 80% cap
    # 10.0 * 80 / 95 = 8.42 mm/s
    norm_res = engine.normalize_to_power_cap(speed=10.0, power=95.0, power_cap=80.0)
    print(f"  * Direct Utility Normalization: {norm_res} (Expected speed: 8.42 mm/s, power: 80.0%)")
    assert norm_res["power"] == 80.0, "Utility did not cap power at 80%"
    assert abs(norm_res["speed"] - 8.42) < 0.01, "Utility did not scale speed correctly"
    assert norm_res["normalized"] is True, "Normalization flag should be True"
    print("  => SUCCESS!")


    print("\n" + "=" * 60)
    print("              ALL CALIBRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

