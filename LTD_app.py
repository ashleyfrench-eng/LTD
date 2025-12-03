import streamlit as st
import os
import json
import pandas as pd
import io
import matplotlib.pyplot as plt
import tempfile
import zipfile
from LTD_scatter import generate_scatter_plots
from columns_json2 import generate_columns_json
from filled_regions2 import generate_filled_regions_json
from LTD_foundation2 import generate_foundation_json
from wall2 import generate_wall_json
from LTD_floor4 import generate_merged_floor_json
from visual_check2 import generate_floor_plot_data
from vornoi5 import generate_voronoi_floor_plots
from LTD_summary import group_columns_by_alignment
from LTD_summary import plot_columns_by_floor
# -------------------------------
# STREAMLIT APP UI
# -------------------------------
st.set_page_config(page_title="Automated Load Take Down", layout="wide")

@st.cache_data(show_spinner=False)
def cached_voronoi(folder_path, save_plots=False):
    from vornoi5 import generate_voronoi_floor_plots
    return generate_voronoi_floor_plots(folder_path, save_plots=save_plots, show_plots=True)


# Background colour toggle
bg_choice = st.radio(
    "Choose background colour:",
    ["Yellow", "Dark", "Pink"],
    index=0,
    horizontal=True
)

bg_colors = {"Yellow": "#FAE41D", "Dark": "#1E1E1E", "Pink": "#FF008A"}
selected_color = bg_colors[bg_choice]
st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {selected_color};
            color: {'white' if bg_choice != 'Yellow' else 'black'};
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# App title
st.title("Automated Load Take Down")
st.write("by Ashley French — Version: 2025-11-09")

st.header("How to Use")
st.write("First open and run the Dynamo Script LoadTakedown within Revit and this will export the neccessary data into a folder of your choice. Next, enter the folder path below and click the buttons to generate the various JSON files and visual outputs. Make sure all required CSV files are present in the 'Revit_Data' subfolder.Visual and data outputs are created that can be inspected throughout. The Voronoi plots show the trubutary areas for the colums, wallls and foundations. The results are put into a LTD table in both excel and here to look at.")



st.header("Step 1: Upload LTD Folder (ZIP)")

uploaded_zip = st.file_uploader("Upload your LTD folder (as a ZIP)", type=["zip"])

if uploaded_zip:
    # Create a temporary directory for this user session
    tmpdir = tempfile.mkdtemp()

    # Extract uploaded ZIP into the directory
    with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
        zip_ref.extractall(tmpdir)

    # Save to session_state so other parts of your app can access it
    st.session_state["folder_path"] = tmpdir


    st.success(f"✅ Extracted files to: {tmpdir}")

def find_file(root, filename):
    for dirpath, dirnames, filenames in os.walk(root):
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None


# After zip_ref.extractall(tmpdir)
st.write("Extracted folder structure:")
for root, dirs, files in os.walk(tmpdir):
    level = root.replace(tmpdir, "").count(os.sep)
    indent = " " * 4 * level
    st.write(f"{indent}{os.path.basename(root)}/")
    subindent = " " * 4 * (level + 1)
    for f in files:
        st.write(f"{subindent}{f}")

st.header("Step 2: Assign Load Types Values")
st.write(" Please Include SW of slab in permanent loads if applicable. In the future this will be automated.")

# --- Step 1: Load JSON file ---
folder_path = st.session_state.get("folder_path", "")
json_path = os.path.join(folder_path, "filled_regions_structured.json")

if not os.path.exists(json_path):
    st.warning("⚠️ filled_regions_structured.json not found in the selected folder.")
else:
    with open(json_path, "r") as f:
        data = json.load(f)

    # --- Step 2: Extract all unique RegionTypes ---
    region_types = set()
    for floor_data in data.values():
        for load_category, regions in floor_data.items():
            for region in regions:
                region_type = region.get("RegionType", "").strip().upper()
                if region_type:
                    region_types.add(region_type)

    # --- Step 3: Split into Permanent (G) and Imposed (Q) ---
    g_types = sorted([r for r in region_types if r.startswith("G")])
    q_types = sorted([r for r in region_types if r.startswith("Q")])

    st.success(f"✅ Found {len(g_types)} Permanent Loads and {len(q_types)} Imposed Loads.")

    # --- Step 4: Create editable tables ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏗️ Permanent (G) Load Types")
        g_df = pd.DataFrame({"RegionType": g_types, "Assigned Value": [1.0]*len(g_types)})
        g_edited = st.data_editor(
            g_df,
            num_rows="fixed",
            key="g_table",
            width="stretch"
        )

    with col2:
        st.subheader("🏢 Imposed (Q) Load Types")
        q_df = pd.DataFrame({"RegionType": q_types, "Assigned Value": [0.8]*len(q_types)})
        q_edited = st.data_editor(
            q_df,
            num_rows="fixed",
            key="q_table",
            width="stretch"
        )

        # --- Step 5: Update original JSON with assigned UnitLoad values ---
        if st.button("💾 Save Assigned Values to Data File"):
            # Combine both edited tables into one dictionary
            combined_values = {
                **dict(zip(g_edited["RegionType"], g_edited["Assigned Value"])),
                **dict(zip(q_edited["RegionType"], q_edited["Assigned Value"]))
            }

            # Make a backup before overwriting
            backup_path = json_path.replace(".json", "_backup.json")
            if not os.path.exists(backup_path):
                import shutil
                shutil.copy(json_path, backup_path)
                st.info(f"📂 Backup created: {backup_path}")

            # Load the original JSON again
            with open(json_path, "r") as f:
                data = json.load(f)

            # Loop through all regions and add "UnitLoad" based on RegionType
            for floor_key, floor_data in data.items():
                for load_type, regions in floor_data.items():
                    for region in regions:
                        region_type = region.get("RegionType", "").strip().upper()
                        if region_type in combined_values:
                            region["UnitLoad"] = combined_values[region_type]

            # Save back to the same JSON file
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2)

            st.success(f"✅ UnitLoad values added and saved to: {json_path}")
            # st.json(combined_values)

# --- Generate column JSON ---
st.header("Step 3: Generate Cleaned Data and Visual Output Check files")
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("🧱 Generate Cleaned Column Data"):
        try:
            with st.spinner("Generating column JSON..."):
                json_path = generate_columns_json(folder_path)
            st.success(f"✅ JSON file created: {json_path}")
            
            # Optionally display the JSON
            # with open(json_path, "r") as f:
            #     st.json(json.load(f))
                
        except Exception as e:
            st.error(f"❌ Error: {e}")

with open(json_path, "rb") as f:
    st.download_button(
        label="⬇️ Download columns_cleaned.json",
        data=f,
        file_name="columns_cleaned.json",
        mime="application/json"
    )

if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("🗺️ Generate Cleaned Area Loads"):
        try:
            with st.spinner("Processing area loads..."):
                json_path = generate_filled_regions_json(folder_path)
            st.success(f"✅ JSON file created: {json_path}")

            # Display preview of JSON
            #with open(json_path, "r") as f:
            #    preview = json.load(f)
            #st.json(preview)

        except Exception as e:
            st.error(f"❌ Error: {e}")

# Generate foundation visuals and JSON
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("🏗️ Generate Foundation  Visuals and Clean Data"):
        try:
            with st.spinner("Processing foundation geometries..."):
                json_path, plot_folder = generate_foundation_json(folder_path)
            st.success(f"✅ Foundation JSON created: {json_path}")
            st.info(f"📁 Plots saved in: {plot_folder}")

            # Display JSON preview
            #with open(json_path, "r") as f:
            #    st.json(json.load(f))

        except Exception as e:
            st.error(f"❌ Error: {e}")

# Generate wall JSON
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("🏗️ Generate Cleaned Wall Data"):
        try:
            with st.spinner("Processing wall data..."):
                json_path, wall_count = generate_wall_json(folder_path)
            st.success(f"✅ Wall JSON created: {json_path}")
            st.info(f"📊 Walls exported: {wall_count}")

            # Preview JSON
            #with open(json_path, "r") as f:
            #    st.json(json.load(f))

        except Exception as e:
            st.error(f"❌ Error: {e}")

# Generate merged floor JSON
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("🟦 Generate Cleaned Floor Boundary Data"):
        try:
            with st.spinner("Making floor boundaries..."):
                json_path, floor_count = generate_merged_floor_json(folder_path)
            st.success(f"✅ JSON created: {json_path}")
            st.info(f"📊 Floors processed: {floor_count}")

            # Preview JSON
            #with open(json_path, "r") as f:
            #    st.json(json.load(f))

        except Exception as e:
            st.error(f"❌ Error: {e}")

# Generate floor + columns + walls JSON + Visuals
st.header("Step 4: Generate Combined Data and Visuals of Elements")
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("🟦 Generate Visual Plots and Combine Data"):
        with st.spinner("Processing floors..."):
            json_path, floor_count = generate_floor_plot_data(folder_path)
        st.success(f"✅ JSON created: {json_path}")
        st.info(f"📊 Floors processed: {floor_count}")

        #with open(json_path, "r") as f:
        #    st.json(json.load(f))

# Generate Voronoi floor plots + JSON
st.header("Step 5: Generate Trib areas for  Load Take Down and show visuals and collect data")
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("Generate Load Take Down Plots and Ouput Data"):
        with st.spinner("Generating Voronoi plots..."):
            json_path, floor_count = cached_voronoi(folder_path, save_plots=True)
        st.success(f"✅ Voronoi JSON saved at: {json_path}")
        st.info(f"📊 Floors processed: {floor_count}")
        #with open(json_path, "r") as f:
        #    st.json(json.load(f))

st.header("Step 6: Generate LoadTakedown Summary Table")

@st.cache_data(show_spinner=False)
def cached_load_summary(folder_path):
    """Cache the processed DataFrame so it doesn’t recompute each time."""
    voronoi_json_path = os.path.join(folder_path, "LTD_plots_data", "LTD_results.json")
    df = group_columns_by_alignment(voronoi_json_path, match_radius=0.5)
    return df

if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    # Generate and cache summary when button pressed
    if st.button("📊 Generate Load Takedown Summary"):
        try:
            with st.spinner("Processing Voronoi JSON and grouping column alignments..."):
                df = cached_load_summary(folder_path)

            # Save to Excel
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            st.success("✅ Load takedown summary generated successfully!")
            st.dataframe(df, width="stretch")

            st.download_button(
                label="💾 Download Load Takedown Summary (Excel)",
                data=excel_buffer,
                file_name="column_load_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Store df in session state for later
            st.session_state["load_summary_df"] = df

        except Exception as e:
            st.error(f"❌ Error generating summary: {e}")

# ---------------------------------------
# Plot section (runs independently)
# ---------------------------------------
if "load_summary_df" in st.session_state:
    df = st.session_state["load_summary_df"]

    st.subheader("🟦 Column Scatter Plot by Floor")

    # Dropdown to select floor
    selected_floor = st.selectbox(
        "Select floor to display:",
        sorted(df["Floor"].unique(), reverse=True)
    )

    # Filter and plot
    floor_df = df[df["Floor"] == selected_floor]
    fig = plot_columns_by_floor(floor_df)
    st.plotly_chart(fig, use_container_width=True)




# Generate scatter plots
st.header("Extra: Scatter Plots")
if "folder_path" in st.session_state:
    folder_path = st.session_state["folder_path"]

    if st.button("📊 Generate Foundation Scatter Plots"):
        try:
            with st.spinner("Generating scatter plots..."):
                plot_paths = generate_scatter_plots(folder_path)
            st.success(f"✅ {len(plot_paths)} foundation scatter plots generated successfully!")

            # Display images directly in Streamlit
            # for p in plot_paths:
            #     st.image(p, caption=os.path.basename(p), use_container_width=True)

        except Exception as e:
            st.error(f"❌ Error: {e}")











