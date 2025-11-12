import csv
import json
import os
from collections import defaultdict


def normalize_level_name(raw_level):
    """
    Normalize level names so that:
    - 'LB1' → 'LB'
    - 'LB2' → 'LB'
    - Removes 'Lvl' and trims spaces
    """
    level = raw_level.strip()

    if level.startswith("LB"):
        return "LB Lvl"

    if "Lvl" not in level:
        level += " Lvl"

    return level


def generate_filled_regions_json(folder_path):
    """
    Reads a filled_region_boundaries_filtered.csv file and writes a structured JSON file.
    Returns the path to the saved JSON file.
    """
    csv_file = os.path.join(folder_path, "Revit_Data", "filled_region_boundaries_filtered.csv")
    output_file = os.path.join(folder_path, "area_loads_cleaned.json")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"❌ CSV file not found: {csv_file}")

    # Use nested defaultdicts for flexible grouping
    data = defaultdict(lambda: {"Permanent Loading": [], "Imposed Loading": []})
    region_data = {}

    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                region_id = int(row["FilledRegion_ID"])
                region_type = row["FilledRegionType"].strip()[-3:]
                view_name = row["View_Name"].strip()
                loop_index = int(row["Loop_Index"])
                x = float(row["X (m)"])
                y = float(row["Y (m)"])
            except Exception:
                print(f"⚠️ Skipping malformed row: {row}")
                continue

            # Determine load type
            if "Permanent" in view_name:
                load_type = "Permanent Loading"
            elif "Imposed" in view_name:
                load_type = "Imposed Loading"
            else:
                load_type = "Other"

            raw_level = view_name.split("-")[0].strip()
            level = normalize_level_name(raw_level)

            key = (level, load_type, region_id, region_type, loop_index)
            if key not in region_data:
                region_data[key] = {
                    "RegionID": region_id,
                    "RegionType": region_type,
                    "LoopIndex": loop_index,
                    "Vertices": []
                }

            region_data[key]["Vertices"].append([x, y])

    # Organize into final structure
    for (level, load_type, region_id, region_type, loop_index), region_info in region_data.items():
        data[level][load_type].append(region_info)

    # Save to JSON
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ JSON file saved to:\n{output_file}")
    return output_file
