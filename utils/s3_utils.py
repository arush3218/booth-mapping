import os
import boto3
import tempfile
import geopandas as gpd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class S3Manager:
    def __init__(self):
        # Try to load from environment variables first
        self.bucket_name = os.getenv("AWS_BUCKET_NAME")
        aws_access_key = os.getenv("AWS_ACCESS_KEY")
        aws_secret_key = os.getenv("AWS_SECRET_KEY")
        
        # If not found, try to load from credintials.json
        if not all([self.bucket_name, aws_access_key, aws_secret_key]):
            cred_file = Path("credintials.json")
            if cred_file.exists():
                with open(cred_file, 'r') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"')
                            if key == 'bucket_name':
                                self.bucket_name = value
                            elif key == 'aws_access_key':
                                aws_access_key = value
                            elif key == 'aws_secret_key':
                                aws_secret_key = value
        
        if not all([self.bucket_name, aws_access_key, aws_secret_key]):
            raise ValueError("Missing AWS credentials")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        self.base_prefix = "shp_files_state_wise/"
        self.temp_dir = tempfile.mkdtemp()
    
    def list_states(self):
        states = set()
        paginator = self.s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.base_prefix, Delimiter='/'):
            for prefix in page.get('CommonPrefixes', []):
                state_folder = prefix['Prefix'].replace(self.base_prefix, '').rstrip('/')
                if state_folder:
                    states.add(state_folder)
        return sorted(list(states))
    
    def download_shapefile(self, state, file_type):
        state_prefix = f"{self.base_prefix}{state}/"
        response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=state_prefix)
        
        if 'Contents' not in response:
            raise FileNotFoundError(f"No files found for state: {state}")
        
        files = [obj['Key'] for obj in response['Contents']]
        
        shapefile_base = None
        for file_key in files:
            filename = file_key.split('/')[-1].lower()
            if file_type.lower() in filename and filename.endswith('.shp'):
                shapefile_base = file_key.rsplit('.', 1)[0]
                break
        
        if not shapefile_base:
            available_files = [f.split('/')[-1] for f in files if f.endswith('.shp')]
            raise FileNotFoundError(f"No {file_type} shapefile found for {state}. Available shapefiles: {available_files}")
        
        extensions = ['.shp', '.shx', '.dbf', '.prj']
        local_paths = {}
        
        for ext in extensions:
            s3_key = f"{shapefile_base}{ext}"
            local_filename = f"{state}_{file_type}{ext}"
            local_path = os.path.join(self.temp_dir, local_filename)
            
            try:
                self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                local_paths[ext] = local_path
            except Exception as e:
                if ext == '.prj':
                    continue
                else:
                    raise
        
        return local_paths.get('.shp')
    
    def load_shapefile(self, state, file_type):
        shp_path = self.download_shapefile(state, file_type)
        return gpd.read_file(shp_path)
    
    def cleanup(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)