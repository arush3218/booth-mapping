import os
import json
import boto3
from botocore.exceptions import ClientError
import tempfile
from typing import List, Optional
import geopandas as gpd
from dotenv import load_dotenv

load_dotenv()


class S3Manager:
    
    def __init__(self, credentials_file: str = None, base_prefix: str = None):
        if credentials_file:
            self.credentials = self._load_credentials(credentials_file)
            self.bucket_name = self.credentials['bucket_name']
            aws_access_key = self.credentials['aws_access_key']
            aws_secret_key = self.credentials['aws_secret_key']
            prefix = self.credentials.get('base_prefix', 'shp_files_state_wise/')
        else:
            self.bucket_name = os.getenv('AWS_BUCKET_NAME')
            aws_access_key = os.getenv('AWS_ACCESS_KEY')
            aws_secret_key = os.getenv('AWS_SECRET_KEY')
            prefix = os.getenv('AWS_BASE_PREFIX', 'shp_files_state_wise/')
        
        if not all([self.bucket_name, aws_access_key, aws_secret_key]):
            raise ValueError("Missing required AWS credentials. Set environment variables or provide credentials file.")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        self.base_prefix = base_prefix or prefix
        self.temp_dir = tempfile.mkdtemp()
    
    def _load_credentials(self, credentials_file: str) -> dict:
        try:
            with open(credentials_file, 'r') as f:
                lines = f.readlines()
                credentials = {}
                for line in lines:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        credentials[key] = value
                
                required_keys = ['bucket_name', 'aws_access_key', 'aws_secret_key']
                for key in required_keys:
                    if key not in credentials:
                        raise ValueError(f"Missing required credential: {key}")
                
                return credentials
        except Exception as e:
            raise ValueError(f"Error loading credentials: {e}")
    
    def list_states(self) -> List[str]:
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=self.base_prefix,
                Delimiter='/'
            )
            
            states = []
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    state = prefix['Prefix'].replace(self.base_prefix, '').rstrip('/')
                    if state:
                        states.append(state)
            
            return sorted(states)
        except ClientError as e:
            print(f"Error listing states from S3: {e}")
            return []
    
    def download_shapefile(self, state: str, file_type: str) -> Optional[str]:
        extensions = ['.shp', '.shx', '.dbf', '.prj']
        
        state_prefix = f"{self.base_prefix}{state}/"
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=state_prefix,
                MaxKeys=100
            )
            
            if 'Contents' not in response:
                print(f"No files found in {state_prefix}")
                return None
            
            shp_files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith(f'.{file_type}.shp')]
            
            if not shp_files:
                print(f"No {file_type}.shp file found in {state_prefix}")
                return None
            
            shp_key = shp_files[0]
            base_name = shp_key.split('/')[-1].replace('.shp', '')
            
        except ClientError as e:
            print(f"Error listing files in {state_prefix}: {e}")
            return None
        
        state_temp_dir = os.path.join(self.temp_dir, state)
        os.makedirs(state_temp_dir, exist_ok=True)
        
        downloaded_files = []
        
        for ext in extensions:
            s3_key = f"{state_prefix}{base_name}{ext}"
            local_path = os.path.join(state_temp_dir, f"{base_name}{ext}")
            
            try:
                self.s3_client.download_file(
                    self.bucket_name,
                    s3_key,
                    local_path
                )
                downloaded_files.append(local_path)
            except ClientError as e:
                print(f"Warning: Could not download {s3_key}: {e}")
                if ext != '.prj':
                    self._cleanup_files(downloaded_files)
                    return None
        
        shp_path = os.path.join(state_temp_dir, f"{base_name}.shp")
        return shp_path if os.path.exists(shp_path) else None
    
    def _cleanup_files(self, file_paths: List[str]):
        for filepath in file_paths:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print(f"Error cleaning up {filepath}: {e}")
    
    def load_shapefile_from_s3(self, state: str, file_type: str) -> Optional[gpd.GeoDataFrame]:
        shp_path = self.download_shapefile(state, file_type)
        
        if shp_path is None:
            return None
        
        try:
            gdf = gpd.read_file(shp_path)
            return gdf
        except Exception as e:
            print(f"Error loading shapefile {shp_path}: {e}")
            return None
    
    def cleanup(self):
        import shutil
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error cleaning up temp directory: {e}")
