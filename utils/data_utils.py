import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from typing import List, Tuple, Optional


def get_available_states(data_dir: str = "Data", s3_manager=None) -> List[str]:
    if s3_manager is not None:
        return s3_manager.list_states()
    
    if not os.path.exists(data_dir):
        return []
    
    states = [
        folder for folder in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, folder)) and not folder.startswith('.')
    ]
    return sorted(states)


def load_shapefile(filepath: str) -> Optional[gpd.GeoDataFrame]:
    if not os.path.exists(filepath):
        return None
    
    try:
        gdf = gpd.read_file(filepath)
        return gdf
    except Exception as e:
        print(f"Error loading shapefile {filepath}: {e}")
        return None


def get_ac_pc_list(gdf: gpd.GeoDataFrame, name_column: str = None, code_column: str = None) -> List[Tuple[str, str]]:
    if gdf is None or gdf.empty:
        return []
    
    if name_column is None:
        name_patterns = ['ac_name', 'pc_name', 'name', 'AC_NAME', 'PC_NAME', 'NAME']
        for pattern in name_patterns:
            if pattern in gdf.columns:
                name_column = pattern
                break
    
    if code_column is None:
        code_patterns = ['ac_no', 'pc_no', 'ac', 'pc', 'AC_NO', 'PC_NO', 'AC', 'PC']
        for pattern in code_patterns:
            if pattern in gdf.columns:
                code_column = pattern
                break
    
    if name_column and code_column:
        result = []
        for _, row in gdf.iterrows():
            code = str(row[code_column])
            name = str(row[name_column])
            result.append((code, name))
        return sorted(result, key=lambda x: x[0])
    
    return []


def validate_booths_in_polygon(booths_gdf: gpd.GeoDataFrame, polygon_gdf: gpd.GeoDataFrame, 
                                ac_pc_code: str, ac_pc_column: str = None) -> gpd.GeoDataFrame:
    if booths_gdf is None or polygon_gdf is None:
        return gpd.GeoDataFrame()
    
    if booths_gdf.crs != polygon_gdf.crs:
        booths_gdf = booths_gdf.to_crs(polygon_gdf.crs)
    
    if ac_pc_column is None:
        code_patterns = ['ac_no', 'pc_no', 'ac', 'pc', 'AC_NO', 'PC_NO', 'AC', 'PC']
        for pattern in code_patterns:
            if pattern in polygon_gdf.columns:
                ac_pc_column = pattern
                break
    
    if ac_pc_column is None:
        return gpd.GeoDataFrame()
    
    polygon_row = polygon_gdf[polygon_gdf[ac_pc_column].astype(str) == str(ac_pc_code)]
    
    if polygon_row.empty:
        return gpd.GeoDataFrame()
    
    polygon = polygon_row.iloc[0].geometry
    
    valid_booths = booths_gdf[booths_gdf.geometry.within(polygon)].copy()
    
    return valid_booths


def extract_lat_lon(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf
    
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    gdf['longitude'] = gdf.geometry.x
    gdf['latitude'] = gdf.geometry.y
    
    return gdf


def prepare_booth_data(state: str, selection_type: str, data_dir: str = "Data", s3_manager=None) -> Tuple[Optional[gpd.GeoDataFrame], Optional[gpd.GeoDataFrame]]:
    if s3_manager is not None:
        file_type = "assembly" if selection_type == "AC wise" else "parliamentary"
        ac_pc_gdf = s3_manager.load_shapefile(state, file_type)
        booths_gdf = s3_manager.load_shapefile(state, "booth")
    else:
        state_dir = os.path.join(data_dir, state)
        
        if selection_type == "AC wise":
            ac_pc_file = os.path.join(state_dir, f"{state}.assembly.shp")
        else:
            ac_pc_file = os.path.join(state_dir, f"{state}.parliamentary.shp")
        
        booths_file = os.path.join(state_dir, f"{state}.booth.shp")
        
        ac_pc_gdf = load_shapefile(ac_pc_file)
        booths_gdf = load_shapefile(booths_file)
    
    if booths_gdf is not None:
        booths_gdf = extract_lat_lon(booths_gdf)
    
    return ac_pc_gdf, booths_gdf
