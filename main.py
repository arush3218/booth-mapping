import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
from typing import Dict, Any

# Global state storage (in production, use Redis or database)
app_state = {
    "s3_manager": None,
    "results": None,
    "summary_data": None,
    "selected_booths_data": None,
    "use_s3": False
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize S3 manager on startup"""
    try:
        app_state["s3_manager"] = S3Manager()
        app_state["use_s3"] = True
        print("✅ Connected to S3")
    except Exception as e:
        print(f"❌ Failed to connect to S3: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to S3: {e}")
    yield
    # Cleanup on shutdown (if needed)
    pass


app = FastAPI(title="Booth Mapping Tool", lifespan=lifespan)

# Mount static files directory
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("output/maps", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_column_name(gdf, patterns):
    """Helper function to find column name matching patterns"""
    for pattern in patterns:
        if pattern in gdf.columns:
            return pattern
    return None


def extract_booth_info(row, state, ac_pc_code, ac_pc_name):
    """Extract booth information from a row - EXACT COPY from app.py"""
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


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Render landing page"""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/instructions", response_class=HTMLResponse)
async def instructions_page(request: Request):
    """Render instructions page"""
    return templates.TemplateResponse("instructions.html", {"request": request})


@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    """Render main application page"""
    states = get_available_states(s3_manager=app_state["s3_manager"])
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "states": states
    })


@app.get("/api/states")
async def get_states():
    """Get list of available states"""
    states = get_available_states(s3_manager=app_state["s3_manager"])
    return {"states": states}


@app.get("/api/ac_pc_list/{state}/{selection_type}")
async def get_ac_pc_list_api(state: str, selection_type: str):
    """Get AC/PC list for a state"""
    try:
        ac_pc_gdf, booths_gdf = prepare_booth_data(
            state, 
            selection_type,
            s3_manager=app_state["s3_manager"]
        )
        
        if ac_pc_gdf is None:
            raise HTTPException(status_code=404, detail="State data not found")
        
        ac_pc_list = get_ac_pc_list(ac_pc_gdf)
        return {
            "ac_pc_list": ac_pc_list,
            "count": len(ac_pc_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process")
async def process_data(request: Request):
    """Process booth mapping and clustering - EXACT LOGIC from app.py"""
    try:
        data = await request.json()
        selected_state = data.get("state")
        selection_type = data.get("selection_type")
        samples_per_ac = int(data.get("samples_per_ac", 300))
        
        if not selected_state or not selection_type:
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        # Prepare data
        ac_pc_gdf, booths_gdf = prepare_booth_data(
            selected_state, 
            selection_type,
            s3_manager=app_state["s3_manager"]
        )
        
        if ac_pc_gdf is None or booths_gdf is None:
            raise HTTPException(status_code=404, detail=f"Could not load shapefiles for {selected_state}")
        
        ac_pc_list = get_ac_pc_list(ac_pc_gdf)
        
        if not ac_pc_list:
            raise HTTPException(status_code=404, detail=f"Could not parse AC/PC data for {selected_state}")
        
        # Determine column patterns
        if selection_type == "AC wise":
            code_patterns = ['ac_no', 'ac', 'AC_NO', 'AC']
        else:
            code_patterns = ['pc_no', 'pc', 'PC_NO', 'PC']
        
        ac_pc_column = get_column_name(ac_pc_gdf, code_patterns)
        
        if not ac_pc_column:
            raise HTTPException(status_code=500, detail="Could not determine AC/PC column in shapefile")
        
        # Process all AC/PCs - EXACT LOGIC from app.py
        all_summary_rows = []
        all_selected_booths = []
        all_results = []
        
        for idx, (ac_pc_code, ac_pc_name) in enumerate(ac_pc_list):
            # Validate booths
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
            
            # Process clustering - EXACT LOGIC
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
            
            # Extract booth information - EXACT LOGIC
            if not result['selected_booths'].empty:
                for _, row in result['selected_booths'].iterrows():
                    booth_info = extract_booth_info(
                        row, selected_state, ac_pc_code, ac_pc_name
                    )
                    all_selected_booths.append(booth_info)
                
                # Create and save map - EXACT LOGIC
                create_and_save_map(
                    result['clustered_booths'],
                    result['selected_booths'],
                    result['cluster_centers'],
                    ac_pc_name,
                    ac_pc_code,
                    output_dir="output/maps"
                )
        
        # Store results in app state
        app_state["results"] = all_results
        app_state["summary_data"] = pd.DataFrame(all_summary_rows)
        app_state["selected_booths_data"] = pd.DataFrame(all_selected_booths)
        
        # Calculate statistics
        total_acs = len(all_results)
        completed = sum(1 for r in all_results if r['is_complete'])
        total_booths = sum(r['total_booths'] for r in all_results)
        total_selected = sum(len(r['selected_booths']) for r in all_results)
        
        return {
            "status": "success",
            "total_acs": total_acs,
            "completed": completed,
            "total_booths": total_booths,
            "total_selected": total_selected,
            "message": f"Processing complete! Processed {len(ac_pc_list)} {'ACs' if selection_type == 'AC wise' else 'PCs'}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results/summary")
async def get_summary():
    """Get summary data"""
    if app_state["summary_data"] is None:
        raise HTTPException(status_code=404, detail="No results available")
    
    return {
        "data": app_state["summary_data"].to_dict(orient="records")
    }


@app.get("/api/results/selected_booths")
async def get_selected_booths():
    """Get selected booths data"""
    if app_state["selected_booths_data"] is None:
        raise HTTPException(status_code=404, detail="No results available")
    
    return {
        "data": app_state["selected_booths_data"].to_dict(orient="records")
    }


@app.get("/api/results/maps")
async def get_available_maps():
    """Get list of available maps"""
    if app_state["results"] is None:
        raise HTTPException(status_code=404, detail="No results available")
    
    map_files = []
    for result in app_state["results"]:
        if not result['selected_booths'].empty:
            safe_name = result['ac_pc_name'].replace(' ', '_').replace('/', '_')
            map_filename = f"{result['ac_pc_code']}_{safe_name}_map.html"
            map_path = os.path.join("output/maps", map_filename)
            if os.path.exists(map_path):
                map_files.append({
                    "code": result['ac_pc_code'],
                    "name": result['ac_pc_name'],
                    "filename": map_filename
                })
    
    return {"maps": map_files}


@app.get("/api/map/{filename}")
async def get_map(filename: str):
    """Get specific map file"""
    map_path = os.path.join("output/maps", filename)
    if not os.path.exists(map_path):
        raise HTTPException(status_code=404, detail="Map not found")
    
    return FileResponse(map_path, media_type="text/html")


@app.get("/api/download/summary")
async def download_summary():
    """Download summary CSV"""
    if app_state["summary_data"] is None:
        raise HTTPException(status_code=404, detail="No results available")
    
    csv = app_state["summary_data"].to_csv(index=False)
    return StreamingResponse(
        iter([csv]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=summary.csv"}
    )


@app.get("/api/download/selected_booths")
async def download_selected_booths():
    """Download selected booths CSV"""
    if app_state["selected_booths_data"] is None:
        raise HTTPException(status_code=404, detail="No results available")
    
    csv = app_state["selected_booths_data"].to_csv(index=False)
    return StreamingResponse(
        iter([csv]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=selected_booths.csv"}
    )


@app.get("/api/download/maps")
async def download_all_maps():
    """Download all maps as ZIP"""
    if app_state["results"] is None:
        raise HTTPException(status_code=404, detail="No results available")
    
    map_files = []
    for result in app_state["results"]:
        if not result['selected_booths'].empty:
            safe_name = result['ac_pc_name'].replace(' ', '_').replace('/', '_')
            map_filename = f"{result['ac_pc_code']}_{safe_name}_map.html"
            map_path = os.path.join("output/maps", map_filename)
            if os.path.exists(map_path):
                map_files.append((map_path, map_filename))
    
    if not map_files:
        raise HTTPException(status_code=404, detail="No maps available")
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for map_path, map_filename in map_files:
            zip_file.write(map_path, map_filename)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=maps.zip"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
