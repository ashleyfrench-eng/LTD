import json
import os
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString

def generate_floor_plot_data(folder_path):
    """
    Combines merged floor boundaries, columns, walls, and foundations into JSON and plots.
    Returns path to saved JSON and the number of floors processed.
    """
    # -------------------------------
    # INPUT FILES
    # -------------------------------
    floors_json_path = os.path.join(folder_path, "floor_plots_cleaned_data", "cleaned_floor_boundaries.json")
    columns_json_path = os.path.join(folder_path, "columns_cleaned.json")
    walls_json_path = os.path.join(folder_path, "wall_cleaned.json")
    foundation_json_path = os.path.join(folder_path, "foundation_plots_cleaned_data", "foundation_points.json")  

    # Output folder
    output_folder = os.path.join(folder_path, "visual_structural_plots")
    os.makedirs(output_folder, exist_ok=True)

    # -------------------------------
    # LOAD JSON DATA
    # -------------------------------
    with open(floors_json_path, "r") as f:
        floor_data = json.load(f)

    with open(columns_json_path, "r") as c:
        column_data = json.load(c)

    with open(walls_json_path, "r") as w:
        wall_data = json.load(w)

    with open(foundation_json_path, "r") as fo:
        foundation_data = json.load(fo)

    # -------------------------------
    # PARSE JSON STRUCTURE
    # -------------------------------
    if isinstance(column_data, dict) and "Columns" in column_data:
        columns_list = column_data["Columns"]
    elif isinstance(column_data, list):
        columns_list = column_data
    else:
        raise ValueError("❌ Could not find valid column list in JSON file.")

    if isinstance(wall_data, dict) and "Walls" in wall_data:
        walls_list = wall_data["Walls"]
    elif isinstance(wall_data, list):
        walls_list = wall_data
    else:
        raise ValueError("❌ Could not find valid wall list in JSON file.")

    if isinstance(foundation_data, dict) and "Foundations" in foundation_data:
        foundations_list = foundation_data["Foundations"]
    elif isinstance(foundation_data, list):
        foundations_list = foundation_data
    else:
        raise ValueError("❌ Could not find valid foundation list in JSON file.")

    # -------------------------------
    # HELPER: Convert level to number
    # -------------------------------
    def level_to_number(level_name):
        if not isinstance(level_name, str):
            return None
        level_name = level_name.strip()[:2].upper()
        if level_name.startswith("RF"):
            return 999
        if level_name.startswith("LB"):
            return -1
        if level_name.startswith("B"):
            try:
                return -int(level_name[1])
            except:
                return None
        try:
            return int(level_name)
        except:
            return None

    # -------------------------------
    # GROUP COLUMNS BY LEVEL
    # -------------------------------
    columns_by_level = {}
    for col_info in columns_list:
        top_level = col_info.get("TopLevel") or col_info.get("Top Level")
        base_level = col_info.get("BaseLevel") or col_info.get("Base Level")

        top_num = level_to_number(top_level)
        base_num = level_to_number(base_level)

        if "Top" in col_info and isinstance(col_info["Top"], dict):
            x = col_info["Top"].get("X")
            y = col_info["Top"].get("Y")
        else:
            x = col_info.get("Top X (m)")
            y = col_info.get("Top Y (m)")

        if x is None or y is None or top_num is None or base_num is None:
            continue

        low, high = sorted([base_num+1, top_num])
        for lvl in range(low, high + 1):
            level_key = f"{lvl:02d}" if lvl >= 0 else f"B{abs(lvl)}"
            columns_by_level.setdefault(level_key, []).append((float(x), float(y)))

        if top_level and top_level.strip().upper().startswith("RF"):
            columns_by_level.setdefault("RF", []).append((float(x), float(y)))

    # -------------------------------
    # GROUP FOUNDATIONS BY LEVEL
    # -------------------------------
    foundations_by_level = {}
    for foundation_info in foundations_list:
        level = foundation_info.get("Level")
        if not level:
            continue
        x = foundation_info.get("X")
        y = foundation_info.get("Y")
        if x is None or y is None:
            continue
        foundations_by_level.setdefault(level, []).append({"X": x, "Y": y})

    # -------------------------------
    # GROUP WALLS BY LEVEL
    # -------------------------------
    walls_by_level = {}
    for wall_info in walls_list:
        top_level = wall_info.get("TopLevel") or wall_info.get("Top Level")
        base_level = wall_info.get("BaseLevel") or wall_info.get("Base Level")

        top_num = level_to_number(top_level)
        base_num = level_to_number(base_level)

        start_top = wall_info.get("Start Top", {})
        end_top = wall_info.get("End Top", {})

        start_x = start_top.get("X")
        start_y = start_top.get("Y")
        end_x = end_top.get("X")
        end_y = end_top.get("Y")

        if None in [start_x, start_y, end_x, end_y, top_num, base_num]:
            continue

        low, high = sorted([base_num + 1, top_num])
        for lvl in range(low, high + 1):
            level_key = f"{lvl:02d}" if lvl >= 0 else f"B{abs(lvl)}"
            walls_by_level.setdefault(level_key, []).append({
                "start": (float(start_x), float(start_y)),
                "end": (float(end_x), float(end_y))
            })

        if top_level and top_level.strip().upper().startswith("RF"):
            walls_by_level.setdefault("RF", []).append({
                "start": (float(start_x), float(start_y)),
                "end": (float(end_x), float(end_y))
            })
        if base_level and base_level.strip().upper().startswith("LB"):
            walls_by_level.setdefault("LB", []).append({
                "start": (float(start_x), float(start_y)),
                "end": (float(end_x), float(end_y))
            })

    # -------------------------------
    # PLOT + EXPORT JSON
    # -------------------------------
    output_data = {}
    for floor_level, coords in floor_data.items():
        if not coords:
            continue

        fig, ax = plt.subplots(figsize=(8, 8))
        polygon = Polygon(coords)
        x, y = polygon.exterior.xy
        ax.fill(x, y, alpha=0.5, facecolor="lightblue", edgecolor="black", linewidth=1.2, label="Floor boundary")

        # Columns
        col_points = columns_by_level.get(floor_level, [])
        if col_points:
            col_x, col_y = zip(*col_points)
            ax.scatter(col_x, col_y, c="red", s=30, label="Columns")

        # Foundations
        foundation_points = foundations_by_level.get(floor_level, [])
        if foundation_points:
            fx = [pt["X"] for pt in foundation_points]
            fy = [pt["Y"] for pt in foundation_points]
            ax.scatter(fx, fy, c="black", s=30, label="Foundations")

        # Walls
        wall_segments = walls_by_level.get(floor_level, [])
        for seg in wall_segments:
            (x1, y1), (x2, y2) = seg["start"], seg["end"]
            ax.plot([x1, x2], [y1, y2], c="green", linewidth=2.0, label="_nolegend_")
        if wall_segments:
            ax.plot([], [], c="green", linewidth=2.0, label="Walls")  # legend

        ax.set_title(f"Floor {floor_level} – Merged Boundary + Columns + Walls", fontsize=12)
        ax.set_aspect("equal", "box")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.grid(True, linestyle=":", linewidth=0.4)
        ax.legend()
        plt.tight_layout()

        # Save figure
        output_path = os.path.join(output_folder, f"floor_{floor_level}.png")
        plt.savefig(output_path, dpi=300)
        plt.close(fig)

        # Store JSON data
        sampled_wall_points = []
        for seg in wall_segments:
            line = LineString([seg["start"], seg["end"]])
            distances = np.linspace(0, line.length, 5)
            for d in distances:
                x, y = line.interpolate(d).coords[0]
                sampled_wall_points.append({"X": round(x,3), "Y": round(y,3)})

        output_data[floor_level] = {
            "floor_boundary": coords,
            "columns": [{"X": x, "Y": y} for x, y in col_points],
            "foundations": foundation_points,
            "walls": sampled_wall_points
        }

    # Save combined JSON
    json_output_path = os.path.join(output_folder, "floor_plot_data.json")
    with open(json_output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✅ Floor plots and JSON saved in: {output_folder}")
    return json_output_path, len(output_data)
