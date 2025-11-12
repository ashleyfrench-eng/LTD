import os
import json
import numpy as np
from shapely.geometry import Polygon, LineString
import geopandas as gpd
import matplotlib.pyplot as plt

def generate_voronoi_floor_plots(folder_path, save_plots=True, show_plots=False):
    """
    Generate weighted Voronoi plots and JSON results for all floors.
    Reads combined floor/column/wall/foundation JSON and loading regions.
    Returns path to saved JSON and number of floors processed.
    """

    # -------------------------------
    # INPUT FILES
    # -------------------------------
    input_floor_json = os.path.join(folder_path, "visual_structural_plots", "floor_plot_data.json")
    input_loading_json = os.path.join(folder_path, "area_loads_cleaned.json")
    output_folder = os.path.join(folder_path, "LTD_plots_data")
    os.makedirs(output_folder, exist_ok=True)

    # -------------------------------
    # HELPER FUNCTIONS
    # -------------------------------
    def voronoi_finite_polygons_2d(vor, radius=None):
        """Reconstruct infinite Voronoi regions into finite polygons."""
        if vor.points.shape[1] != 2:
            raise ValueError("Requires 2D input")
        new_regions = []
        new_vertices = vor.vertices.tolist()
        center = vor.points.mean(axis=0)
        if radius is None:
            radius = np.ptp(vor.points, axis=0).max() * 2
        all_ridges = {}
        for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
            all_ridges.setdefault(p1, []).append((p2, v1, v2))
            all_ridges.setdefault(p2, []).append((p1, v1, v2))
        for p1, region_idx in enumerate(vor.point_region):
            vertices = vor.regions[region_idx]
            if not vertices or all(v >= 0 for v in vertices):
                new_regions.append(vertices)
                continue
            ridges = all_ridges.get(p1, [])
            new_region = [v for v in vertices if v >= 0]
            for p2, v1, v2 in ridges:
                if v2 < 0:
                    v1, v2 = v2, v1
                if v1 >= 0:
                    continue
                t = vor.points[p2] - vor.points[p1]
                t /= np.linalg.norm(t)
                n = np.array([-t[1], t[0]])
                midpoint = vor.points[[p1, p2]].mean(axis=0)
                direction = np.sign(np.dot(midpoint - center, n)) * n
                far_point = vor.vertices[v2] + direction * radius
                new_vertices.append(far_point.tolist())
                new_region.append(len(new_vertices) - 1)
            if len(new_region) < 3:
                continue
            vs = np.asarray([new_vertices[v] for v in new_region])
            c = vs.mean(axis=0)
            angles = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
            new_region = np.array(new_region)[np.argsort(angles)]
            new_regions.append(new_region.tolist())
        return new_regions, np.asarray(new_vertices)

    def compute_weighted_voronoi(boundary_coords, interior_points, weighted_zones):
        boundary_poly = Polygon(boundary_coords)
        if not interior_points or len(interior_points) < 3:
            return [], boundary_poly
        points = np.array(interior_points)
        from scipy.spatial import Voronoi
        vor = Voronoi(points)
        regions, vertices = voronoi_finite_polygons_2d(vor)
        results = []
        for i, region in enumerate(regions):
            if not region or any(v >= len(vertices) for v in region):
                continue
            poly = Polygon(vertices[region]).intersection(boundary_poly)
            if poly.is_empty:
                continue
            total_area = poly.area
            weighted_sum = 0.0
            for zone in weighted_zones:
                inter = poly.intersection(zone["polygon"])
                if not inter.is_empty:
                    weighted_sum += inter.area * zone["weight"]
            results.append({
                "index": i,
                "point": interior_points[i],
                "area_raw": total_area,
                "area_weighted": weighted_sum,
                "polygon": poly
            })
        return results, boundary_poly

    # -------------------------------
    # LOAD DATA
    # -------------------------------
    with open(input_floor_json, "r") as f:
        floor_data = json.load(f)

    with open(input_loading_json, "r") as f:
        loading_data = json.load(f)

    # -------------------------------
    # PROCESS EACH FLOOR
    # -------------------------------
    output_data = {}

    for floor_level, floor_info in floor_data.items():
        boundary = floor_info.get("floor_boundary", [])
        columns = floor_info.get("columns", [])
        walls = floor_info.get("walls", [])
        foundations = floor_info.get("foundations", [])

        if not boundary:
            print(f"⚠️ Skipping {floor_level}: Missing boundary or column data")
            continue

        boundary = [(float(x), float(y)) for x, y in boundary]
        points = [(float(c["X"]), float(c["Y"])) for c in columns]
        wall_points = [(float(w["X"]), float(w["Y"])) for w in walls]
        foundation_points = [(float(f["X"]), float(f["Y"])) for f in foundations]
        all_points = points + wall_points + foundation_points

        output_data[floor_level] = {
            "floor_boundary": boundary,
            "columns": [],
            "walls": [{"X": x, "Y": y} for x, y in wall_points],
            "foundations": [],
        }

        load_key = f"{floor_level} Lvl"
        if load_key not in loading_data:
            print(f"⚠️ {floor_level}: no loading data found")
            continue

        for load_type in ["Permanent Loading", "Imposed Loading"]:
            load_zones = loading_data[load_key].get(load_type, [])
            if not load_zones:
                continue

            weighted_zones = []
            for zone in load_zones:
                verts = zone.get("Vertices", [])
                if len(verts) >= 3:
                    unit_load = zone.get("UnitLoad")
                    if unit_load is None:
                        unit_load = 1.0 if load_type == "Permanent Loading" else 0.8
                    weighted_zones.append({
                        "polygon": Polygon(verts),
                        "weight": float(unit_load)
                    })
            if not weighted_zones:
                continue

            regions, boundary_poly = compute_weighted_voronoi(boundary, all_points, weighted_zones)

            # Plotting
            fig, ax = plt.subplots(figsize=(7,7))
            cmap = plt.get_cmap('tab10', len(weighted_zones))
            for i, zone in enumerate(weighted_zones):
                gpd.GeoSeries(zone["polygon"]).plot(ax=ax, color=cmap(i), alpha=0.25, edgecolor='white', linewidth=0.8)
            gpd.GeoSeries(boundary_poly.boundary).plot(ax=ax, color='black', linewidth=1.2)

            areas = [r["area_raw"] for r in regions if r["area_raw"] > 0]
            min_a, max_a = (min(areas), max(areas)) if areas else (0,1)

            for i, region in enumerate(regions):
                poly = region["polygon"]
                area_norm = (region["area_raw"] - min_a) / (max_a - min_a + 1e-9)
                grey_value = 0.7 - 0.65 * area_norm
                gpd.GeoSeries(poly).plot(ax=ax, color=str(grey_value), alpha=0.15, edgecolor='black', linewidth=0.8)

                px, py = region["point"]
                plt.scatter(px, py, color='red', s=8, zorder=5)
                if (px, py) not in wall_points:
                    plt.scatter(px, py, color='black', s=12, zorder=5)
                    plt.text(px+0.1, py+0.1, f"A={region['area_raw']:.2f}", fontsize=7)

                output_data[floor_level]["columns"].append({
                    "X": px,
                    "Y": py,
                    "Area": round(region["area_raw"],3),
                    "WeightedArea": round(region["area_weighted"],3),
                    "Type": "Wall" if (px, py) in wall_points else "Foundation" if (px, py) in foundation_points else "Column"
                })

            ax.set_aspect("equal", "box")
            plt.title(f"Weighted Voronoi – {floor_level} ({load_type})")
            plt.xlabel("X (m)")
            plt.ylabel("Y (m)")
            plt.grid(True, linestyle=':', linewidth=0.4)
            plt.tight_layout()

            output_path = os.path.join(output_folder, f"LTD_{floor_level}_{load_type.replace(' ','_')}.png")
            if save_plots:
                plt.savefig(output_path, dpi=300)
                
                
            plt.close(fig)
            print(f"✅ Saved: {output_path}")

    # Save combined JSON
    json_output_path = os.path.join(output_folder, "LTD_results.json")
    with open(json_output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✅ All Voronoi floor plots and JSON saved in: {output_folder}")
    return json_output_path, len(output_data)
