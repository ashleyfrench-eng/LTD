import pandas as pd
import matplotlib.pyplot as plt
import os
import re
from shapely.geometry import LineString, MultiLineString, Polygon, Point
from shapely.ops import unary_union, polygonize
import json

def generate_merged_floor_json(folder_path):
    """
    Reads 'floor_data.csv' in the folder_path and:
    - Merges touching/overlapping floor polygons by level
    - Plots merged floor outlines
    - Saves coordinates to JSON
    Returns JSON path and number of floors processed
    """
    csv_file = os.path.join(folder_path, "Revit_Data", "floor_data.csv")
    output_folder = os.path.join(folder_path, "floor_plots_cleaned_data")
    os.makedirs(output_folder, exist_ok=True)

    json_output_path = os.path.join(output_folder, "cleaned_floor_boundaries.json")

    # -------------------------------
    # READ CSV
    # -------------------------------
    df = pd.read_csv(csv_file, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    if "Boundary Lines (m)" not in df.columns:
        raise ValueError("❌ Column 'Boundary Lines (m)' not found in CSV.")

    # -------------------------------
    # ADD LEVEL PREFIX COLUMN
    # -------------------------------
    def extract_level_prefix(level_name):
        if not isinstance(level_name, str):
            return "Unknown"
        match = re.match(r"^([A-Za-z0-9]{1,2})", level_name.strip())
        return match.group(1) if match else level_name[:2]

    df["LevelGroup"] = df["Level"].apply(extract_level_prefix)

    # -------------------------------
    # PARSE BOUNDARY LINES
    # -------------------------------
    def parse_boundary_string(boundary_str):
        lines = []
        if not isinstance(boundary_str, str):
            return lines

        boundary_str = boundary_str.replace("\n", " ").replace("\r", " ").strip()
        segments = re.split(r"[;|]", boundary_str)

        for seg in segments:
            seg = seg.strip()
            matches = re.findall(r"\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)", seg)
            if len(matches) == 2:
                try:
                    (x1, y1), (x2, y2) = matches
                    line = ((float(x1), float(y1)), (float(x2), float(y2)))
                    if line[0] != line[1]:
                        lines.append(line)
                except Exception:
                    continue

        # Deduplicate ignoring direction
        lines = list(set(tuple(sorted(line)) for line in lines))
        return lines

    # -------------------------------
    # MERGE + PLOT + JSON EXPORT
    # -------------------------------
    merged_floor_data = {}

    for group_name, group in df.groupby("LevelGroup"):
        fig, ax = plt.subplots(figsize=(8, 8))
        all_polygons = []
        plotted = False

        for _, row in group.iterrows():
            boundary_lines = parse_boundary_string(row["Boundary Lines (m)"])
            if not boundary_lines:
                continue

            shapely_lines = [LineString(line) for line in boundary_lines]
            multi = MultiLineString(shapely_lines)
            merged = unary_union(multi)
            polygons = list(polygonize(merged))

            if not polygons:
                pts = [Point(x, y) for line in boundary_lines for (x, y) in line]
                if len(pts) >= 3:
                    hull = MultiLineString([LineString([(p.x, p.y) for p in pts])]).convex_hull
                    polygons = [hull]

            all_polygons.extend(polygons)

        # Merge all polygons into a single unified area
        if all_polygons:
            merged_area = unary_union(all_polygons)

            # Handle single or multiple polygons
            merged_polys = []
            if isinstance(merged_area, Polygon):
                merged_polys = [merged_area]
            elif hasattr(merged_area, "geoms"):
                merged_polys = list(merged_area.geoms)

            # Take largest polygon as main outline
            if merged_polys:
                main_poly = max(merged_polys, key=lambda p: p.area)
                x, y = main_poly.exterior.xy
                coords = list(zip(x, y))
                merged_floor_data[group_name] = coords  # store coordinates
                ax.fill(x, y, alpha=0.7, facecolor="lightsteelblue", edgecolor="black", linewidth=1.4)
                plotted = True

        ax.set_title(f"Combined Floor Outline – {group_name}", fontsize=12)
        ax.set_aspect("equal", "box")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.grid(True, linestyle=":", linewidth=0.4)
        plt.tight_layout()

        output_path = os.path.join(output_folder, f"{group_name}.png")
        if plotted:
            plt.savefig(output_path, dpi=300)
        plt.close(fig)

    # -------------------------------
    # SAVE JSON
    # -------------------------------
    with open(json_output_path, "w") as f:
        json.dump(merged_floor_data, f, indent=4)

    print(f"✅ Merged floor JSON saved to:\n{json_output_path}")
    print(f"📊 Floors processed: {len(merged_floor_data)}")
    return json_output_path, len(merged_floor_data)
