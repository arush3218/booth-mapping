import os
import streamlit as st
import pandas as pd
import geopandas as gpd
from utils.data_utils import (
    get_available_states, 
    prepare_booth_data, 
    get_ac_pc_list,
    validate_booths_in_polygon
)
from utils.clustering_utils import process_ac_pc_clustering
from utils.map_utils import create_and_save_map
from utils.s3_utils import S3Manager
import zipfile
from io import BytesIO


st.set_page_config(
    page_title="Booth Mapping Tool",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Booth Mapping and Clustering Tool")
st.markdown("---")


def initialize_session_state():
    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'summary_data' not in st.session_state:
        st.session_state.summary_data = None
    if 'selected_booths_data' not in st.session_state:
        st.session_state.selected_booths_data = None
    if 's3_manager' not in st.session_state:
        st.session_state.s3_manager = None
    if 'use_s3' not in st.session_state:
        st.session_state.use_s3 = False


def get_column_name(gdf, patterns):
    for pattern in patterns:
        if pattern in gdf.columns:
            return pattern
    return None


def extract_booth_info(row, state, ac_pc_code, ac_pc_name):
    booth_patterns = ['booth', 'booth_no', 'BOOTH_NO', 'BOOTH']
    booth_col = get_column_name(pd.DataFrame([row]), booth_patterns)
    booth = row[booth_col] if booth_col else ''
    
    booth_name_patterns = ['booth_name', 'BOOTH_NAME', 'name', 'NAME']
    booth_name_col = get_column_name(pd.DataFrame([row]), booth_name_patterns)
    booth_name = row[booth_name_col] if booth_name_col else ''
    
    district_patterns = ['district', 'DISTRICT', 'dist', 'DIST']
    district_col = get_column_name(pd.DataFrame([row]), district_patterns)
    district = row[district_col] if district_col else ''
    
    district_n_patterns = ['district_n', 'DISTRICT_N', 'dist_name', 'DIST_NAME']
    district_n_col = get_column_name(pd.DataFrame([row]), district_n_patterns)
    district_n = row[district_n_col] if district_n_col else ''
    
    pc_patterns = ['pc', 'PC', 'pc_no', 'PC_NO']
    pc_col = get_column_name(pd.DataFrame([row]), pc_patterns)
    pc = row[pc_col] if pc_col else ''
    
    pc_name_patterns = ['pc_name', 'PC_NAME']
    pc_name_col = get_column_name(pd.DataFrame([row]), pc_name_patterns)
    pc_name = row[pc_name_col] if pc_name_col else ''
    
    ac_patterns = ['ac', 'AC', 'ac_no', 'AC_NO']
    ac_col = get_column_name(pd.DataFrame([row]), ac_patterns)
    ac = row[ac_col] if ac_col else ''
    
    ac_name_patterns = ['ac_name', 'AC_NAME']
    ac_name_col = get_column_name(pd.DataFrame([row]), ac_name_patterns)
    ac_name = row[ac_name_col] if ac_name_col else ''
    
    return {
        'state': state,
        'district': district,
        'district_n': district_n,
        'pc': pc,
        'pc_name': pc_name,
        'ac': ac,
        'ac_name': ac_name,
        'booth': booth,
        'booth_name': booth_name,
        'cluster': row.get('cluster', ''),
        'latitude': row.get('latitude', ''),
        'longitude': row.get('longitude', '')
    }


initialize_session_state()

st.sidebar.header("Configuration")

# Initialize S3 manager
if st.session_state.s3_manager is None:
    try:
        with st.spinner("Connecting to S3..."):
            st.session_state.s3_manager = S3Manager()
            st.session_state.use_s3 = True
        st.sidebar.success("✅ Connected to S3")
    except Exception as e:
        st.sidebar.error(f"Failed to connect to S3: {e}")
        st.sidebar.info("Please check your credentials in credintials.json")
        st.stop()

states = get_available_states(s3_manager=st.session_state.s3_manager)
if not states:
    st.error("No state data found in the Data/ directory. Please add state shapefiles.")
    st.stop()

selected_state = st.sidebar.selectbox("Select State", [""] + states)

selection_type = st.sidebar.radio("Selection Type", ["AC wise", "PC wise"])

if selected_state and selected_state != "":
    ac_pc_gdf, booths_gdf = prepare_booth_data(
        selected_state, 
        selection_type,
        s3_manager=st.session_state.s3_manager
    )
    
    if ac_pc_gdf is None or booths_gdf is None:
        st.error(f"Could not load shapefiles for {selected_state}. Please check the data files.")
        st.stop()
    
    ac_pc_list = get_ac_pc_list(ac_pc_gdf)
    
    if not ac_pc_list:
        st.error(f"Could not parse AC/PC data for {selected_state}.")
        st.stop()
    
    samples_per_ac = st.sidebar.number_input(
        "Samples per AC/PC (determines clusters)",
        min_value=25,
        max_value=5000,
        value=300,
        step=25,
        help="25 samples = 1 cluster. Each cluster will have 2 booths selected."
    )
    
    clusters_per_ac = round(samples_per_ac / 25)
    booths_per_ac = clusters_per_ac * 2
    
    st.sidebar.info(f"""
    **Configuration:**
    - {len(ac_pc_list)} {'ACs' if selection_type == 'AC wise' else 'PCs'} in {selected_state}
    - {clusters_per_ac} clusters per AC/PC
    - 2 booths per cluster
    - ~{booths_per_ac} booths selected per AC/PC
    """)
    
    if st.sidebar.button("Generate Results for All", type="primary"):
        if selection_type == "AC wise":
            code_patterns = ['ac_no', 'ac', 'AC_NO', 'AC']
        else:
            code_patterns = ['pc_no', 'pc', 'PC_NO', 'PC']
        
        ac_pc_column = get_column_name(ac_pc_gdf, code_patterns)
        
        if not ac_pc_column:
            st.error("Could not determine AC/PC column in shapefile.")
            st.stop()
        
        all_summary_rows = []
        all_selected_booths = []
        all_results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, (ac_pc_code, ac_pc_name) in enumerate(ac_pc_list):
            status_text.text(f"Processing {ac_pc_name} ({ac_pc_code})... {idx + 1}/{len(ac_pc_list)}")
            progress_bar.progress((idx + 1) / len(ac_pc_list))
            
            valid_booths = validate_booths_in_polygon(
                booths_gdf, ac_pc_gdf, ac_pc_code, ac_pc_column
            )
            
            if valid_booths.empty:
                summary_row = {
                    'AC' if selection_type == 'AC wise' else 'PC': ac_pc_code,
                    ('AC_Name' if selection_type == 'AC wise' else 'PC_Name'): ac_pc_name,
                    'Total_Booths': 0,
                    'Selected_Booths': 0,
                    'Status': 'Not completed',
                    'Reason': 'No booths found within boundary',
                    'Samples_Requested': samples_per_ac
                }
                all_summary_rows.append(summary_row)
                continue
            
            result = process_ac_pc_clustering(valid_booths, samples_per_ac)
            
            all_results.append({
                'ac_pc_code': ac_pc_code,
                'ac_pc_name': ac_pc_name,
                'state': selected_state,
                'selection_type': selection_type,
                **result
            })
            
            summary_row = {
                'AC' if selection_type == 'AC wise' else 'PC': ac_pc_code,
                ('AC_Name' if selection_type == 'AC wise' else 'PC_Name'): ac_pc_name,
                'Total_Booths': result['total_booths'],
                'Selected_Booths': len(result['selected_booths']),
                'Status': 'Completed' if result['is_complete'] else 'Not completed',
                'Reason': result['reason'],
                'Samples_Requested': samples_per_ac
            }
            all_summary_rows.append(summary_row)
            
            if not result['selected_booths'].empty:
                for _, row in result['selected_booths'].iterrows():
                    booth_info = extract_booth_info(
                        row, selected_state, ac_pc_code, ac_pc_name
                    )
                    all_selected_booths.append(booth_info)
                
                create_and_save_map(
                    result['clustered_booths'],
                    result['selected_booths'],
                    result['cluster_centers'],
                    ac_pc_name,
                    ac_pc_code,
                    output_dir="output/maps"
                )
        
        st.session_state.results = all_results
        st.session_state.summary_data = pd.DataFrame(all_summary_rows)
        st.session_state.selected_booths_data = pd.DataFrame(all_selected_booths)
        
        progress_bar.empty()
        status_text.empty()
        st.success(f"Processing complete! Processed {len(ac_pc_list)} {'ACs' if selection_type == 'AC wise' else 'PCs'}")

if st.session_state.results:
    results = st.session_state.results
    
    st.header("Processing Results")
    
    if isinstance(results, list):
        total_acs = len(results)
        completed = sum(1 for r in results if r['is_complete'])
        total_booths = sum(r['total_booths'] for r in results)
        total_selected = sum(len(r['selected_booths']) for r in results)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total ACs/PCs", total_acs)
        with col2:
            st.metric("Completed", f"{completed}/{total_acs}")
        with col3:
            st.metric("Total Booths", total_booths)
        with col4:
            st.metric("Total Selected", total_selected)
    
    tab1, tab2, tab3 = st.tabs(["📊 Summary", "📋 Selected Booths", "🗺️ Maps"])
    
    with tab1:
        st.subheader("Summary")
        if st.session_state.summary_data is not None:
            st.dataframe(st.session_state.summary_data, use_container_width=True)
            
            csv = st.session_state.summary_data.to_csv(index=False)
            st.download_button(
                label="Download Summary CSV",
                data=csv,
                file_name="summary.csv",
                mime="text/csv"
            )
    
    with tab2:
        st.subheader("Selected Booths")
        if st.session_state.selected_booths_data is not None and not st.session_state.selected_booths_data.empty:
            st.dataframe(st.session_state.selected_booths_data, use_container_width=True)
            
            csv = st.session_state.selected_booths_data.to_csv(index=False)
            st.download_button(
                label="Download Selected Booths CSV",
                data=csv,
                file_name="selected_booths.csv",
                mime="text/csv"
            )
        else:
            st.info("No booths selected.")
    
    with tab3:
        st.subheader("Interactive Maps")
        
        if isinstance(results, list):
            map_files = []
            for result in results:
                safe_name = result['ac_pc_name'].replace(' ', '_').replace('/', '_')
                map_filename = f"{result['ac_pc_code']}_{safe_name}_map.html"
                map_path = os.path.join("output/maps", map_filename)
                if os.path.exists(map_path):
                    map_files.append((map_path, map_filename))
            
            if map_files:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for map_path, map_filename in map_files:
                        zip_file.write(map_path, map_filename)
                
                zip_buffer.seek(0)
                st.download_button(
                    label=f"Download All Maps (ZIP - {len(map_files)} files)",
                    data=zip_buffer,
                    file_name=f"{selected_state}_maps.zip",
                    mime="application/zip"
                )
            
            ac_pc_options = [f"{r['ac_pc_code']} - {r['ac_pc_name']}" for r in results if not r['selected_booths'].empty]
            
            if ac_pc_options:
                selected_view = st.selectbox("Select AC/PC to view map", ac_pc_options)
                selected_code = selected_view.split(' - ')[0]
                
                view_result = next((r for r in results if r['ac_pc_code'] == selected_code), None)
                
                if view_result:
                    safe_name = view_result['ac_pc_name'].replace(' ', '_').replace('/', '_')
                    map_filename = f"{view_result['ac_pc_code']}_{safe_name}_map.html"
                    map_path = os.path.join("output/maps", map_filename)
                    
                    if os.path.exists(map_path):
                        with open(map_path, 'r', encoding='utf-8') as f:
                            map_html = f.read()
                        st.components.v1.html(map_html, height=600, scrolling=True)
            else:
                st.info("No maps available.")
        else:
            st.info("No results to display.")

else:
    st.info("👈 Please configure settings in the sidebar and click 'Generate Results' to begin.")
    
    st.markdown("""
    ### How to use this tool:
    
    1. **Select State**: Choose a state from the dropdown
    2. **Selection Type**: Choose AC wise or PC wise analysis
    3. **Samples per AC/PC**: This determines how many clusters each AC/PC will be divided into (clusters = samples/25)
    4. **Generate Results**: Click to process ALL ACs or PCs in the selected state
    
    ### Features:
    
    - **Automated Clustering**: Uses KMeans clustering to intelligently select booths
    - **Interactive Maps**: View all booths color-coded by cluster with selected booths highlighted
    - **CSV Export**: Download summary and selected booths data
    - **Validation**: Ensures all booths fall within their respective AC/PC boundaries
    
    ### Output Files:
    
    - `summary.csv`: Overview of processing results
    - `selected_booths.csv`: Detailed list of selected booth locations
    - HTML maps: Interactive maps for each AC/PC
    """)

st.markdown("---")
st.markdown("Built with Streamlit ")
