# 🗺️ Indian Electoral Booth Sampling and Spatial Analysis Tool

A modern, production-ready web application for intelligent sampling and spatial analysis of Indian electoral polling booths using FastAPI, AWS S3, geospatial analysis, and machine learning clustering algorithms.

## 🌟 Overview

This tool helps electoral analysts and researchers perform systematic sampling of polling booths from Assembly Constituencies (AC) or Parliamentary Constituencies (PC) across Indian states. It uses KMeans clustering to ensure geographically distributed samples and provides an elegant dark-themed interface with interactive visualizations for analysis.

## ✨ Key Features

- **🎨 Modern Dark UI**: Elegant dark-themed interface inspired by modern web applications
- **⚡ FastAPI Backend**: High-performance async API with RESTful endpoints
- **☁️ Cloud-Native**: Fetches shapefiles directly from AWS S3 (no local storage required)
- **🎯 Smart Clustering**: KMeans algorithm ensures geographically distributed booth selection
- **🗺️ Interactive Maps**: Folium-based HTML maps with color-coded clusters
- **📊 Batch Processing**: Process all ACs/PCs in a state simultaneously
- **✅ Spatial Validation**: Ensures booths fall within constituency boundaries
- **📥 Export Options**: Download summary, booth data as CSV, and maps as ZIP
- **🚀 Real-time Processing**: Progress tracking with live updates
- **📱 Responsive Design**: Works seamlessly on desktop, tablet, and mobile devices

## 📁 Project Structure

```
BoothMapping/
├── main.py                     # FastAPI application & API routes
├── app.py                      # Legacy Streamlit app (deprecated)
├── requirements.txt            # Python dependencies
├── credintials.json           # AWS credentials (git-ignored in private repo)
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
├── utils/                     # Backend utility modules
│   ├── __init__.py
│   ├── s3_utils.py           # AWS S3 operations
│   ├── data_utils.py         # Data loading and validation
│   ├── clustering_utils.py   # KMeans clustering logic
│   └── map_utils.py          # Folium map generation
├── templates/                 # Jinja2 HTML templates
│   ├── landing.html          # Landing page
│   ├── instructions.html     # Documentation page
│   └── index.html            # Main application page
├── static/                    # Frontend assets
│   ├── css/
│   │   ├── landing.css       # Landing page styles
│   │   ├── instructions.css  # Instructions page styles
│   │   └── app.css          # Application page styles
│   └── js/
│       └── script.js         # Frontend JavaScript
└── output/                    # Generated outputs (git-ignored)
    └── maps/                  # HTML map files
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- AWS account with S3 access
- Shapefiles uploaded to S3 bucket

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/amarr07/Indian-Electoral-BoothSampling-and-Spatial-Analysis-Tool.git
cd Indian-Electoral-BoothSampling-and-Spatial-Analysis-Tool
```

2. **Create virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure AWS credentials**:

Create `credintials.json` in the root directory:
```json
bucket_name = "your-bucket-name" 
aws_access_key = "your-access-key"
aws_secret_key = "your-secret-key"
```

Or set environment variables:
```bash
export AWS_BUCKET_NAME=your-bucket-name
export AWS_ACCESS_KEY=your-access-key
export AWS_SECRET_KEY=your-secret-key
```

5. **Run the application**:
```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

6. **Access the application**:
- Open your browser and navigate to `http://localhost:8000`
- Landing page: `http://localhost:8000/`
- Instructions: `http://localhost:8000/instructions`
- Main app: `http://localhost:8000/app`

## 📊 S3 Data Structure

Your S3 bucket should follow this structure:

```
your-bucket-name/
└── shp_files_state_wise/
    ├── andhrapradesh/
    │   ├── andhrapradesh.assembly.shp
    │   ├── andhrapradesh.assembly.shx
    │   ├── andhrapradesh.assembly.dbf
    │   ├── andhrapradesh.assembly.prj
    │   ├── andhrapradesh.parliamentary.shp
    │   ├── andhrapradesh.parliamentary.shx
    │   ├── andhrapradesh.parliamentary.dbf
    │   ├── andhrapradesh.parliamentary.prj
    │   ├── andhrapradesh.booth.shp
    │   ├── andhrapradesh.booth.shx
    │   ├── andhrapradesh.booth.dbf
    │   └── andhrapradesh.booth.prj
    ├── maharashtra/
    │   └── [similar structure]
    └── [other states...]
```

## 🎯 How to Use

### Landing Page
1. **Start Mapping**: Navigate directly to the application
2. **View Instructions**: Read comprehensive documentation

### Main Application
1. **Automatic Connection**: The app connects to your S3 bucket on startup
2. **Select State**: Choose from available states in the dropdown
3. **Choose Analysis Type**: Select AC wise or PC wise
4. **Configure Sampling**:
   - Set samples per AC/PC (default: 300)
   - Formula: `clusters = samples ÷ 25`
   - Each cluster selects 2 booths
5. **Generate Results**: Click "Generate Results for All"
6. **View Results**:
   - Summary statistics in cards
   - Detailed tables for summary and selected booths
   - Interactive maps for each constituency
7. **Download Outputs**:
   - Summary CSV (processing statistics)
   - Selected Booths CSV (detailed booth information)
   - All Maps as ZIP (interactive visualizations)

## 🔄 Processing Workflow

### 1. Data Loading
- Connects to AWS S3 bucket
- Lists available states
- Downloads required shapefiles to temporary storage

### 2. Spatial Validation
- Filters booths within selected AC/PC boundaries
- Uses GeoPandas spatial operations
- Extracts latitude/longitude coordinates (EPSG:4326)

### 3. Clustering Algorithm
```
Number of clusters = round(samples_per_ac / 25)
```
- Applies KMeans clustering to booth coordinates
- Creates geographically distributed clusters

### 4. Booth Selection Strategy
For each cluster:
- **Primary range**: 500m - 2km from centroid
- **Extended range**: up to 3km if needed
- Selects 2 nearest booths to centroid
- Marks "Not completed" if insufficient booths

### 5. Visualization
- Interactive Folium maps with:
  - All booths (color-coded by cluster)
  - Cluster centroids (marked with icons)
  - Selected booths (highlighted with stars)
- Saved as HTML files

### 6. Export
- **summary.csv**: AC/PC-wise processing results
- **selected_booths.csv**: Detailed booth information
- **HTML maps**: One per AC/PC (zipped download)

## 📋 Output Format

### Summary CSV Columns
| Column | Description |
|--------|-------------|
| AC/PC | Constituency code |
| AC_Name/PC_Name | Constituency name |
| Total_Booths | Total booths in constituency |
| Selected_Booths | Number of booths selected |
| Status | Completed / Not completed |
| Reason | Explanation if incomplete |
| Samples_Requested | Target sample size |

### Selected Booths CSV Columns
| Column | Description |
|--------|-------------|
| state | State name |
| district, district_n | District information |
| pc, pc_name | Parliamentary constituency |
| ac, ac_name | Assembly constituency |
| booth, booth_name | Booth code and name |
| cluster | Assigned cluster number |
| latitude, longitude | GPS coordinates |

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| AWS_BUCKET_NAME | S3 bucket name | `electoral-shapefiles` |
| AWS_ACCESS_KEY | AWS access key ID | `AKIA...` |
| AWS_SECRET_KEY | AWS secret access key | `wJalrXU...` |
| AWS_BASE_PREFIX | Base folder in S3 | `shp_files_state_wise/` |

### Shapefile Requirements

**AC/PC Shapefiles** (Polygon):
- `AC_NO`/`PC_NO` or `AC`/`PC` - Constituency code
- `AC_NAME`/`PC_NAME` - Constituency name
- Polygon geometry

**Booth Shapefiles** (Point):
- `BOOTH_NO` or `BOOTH` - Booth code
- `BOOTH_NAME` - Booth name
- `AC_NO`/`PC_NO` - Constituency reference
- `DISTRICT`, `DISTRICT_N` - District info
- Point geometry

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI 0.104+ (High-performance async API)
- **Server**: Uvicorn (ASGI server)
- **Geospatial**: GeoPandas, Shapely
- **ML**: scikit-learn (KMeans)
- **Cloud**: AWS S3 (boto3)
- **Data Processing**: Pandas, NumPy
- **Mapping**: Folium

### Frontend
- **Templating**: Jinja2
- **Styling**: Custom CSS (Dark theme)
- **JavaScript**: Vanilla JS (No framework dependencies)
- **Design**: Responsive, mobile-first approach

## 📦 Dependencies

See [requirements.txt](requirements.txt) for full list:
- **fastapi** - Modern web framework
- **uvicorn** - ASGI server
- **jinja2** - Template engine
- **python-multipart** - Form data parsing
- **python-dotenv** - Environment variable management
- **geopandas** - Geospatial data processing
- **boto3** - AWS S3 integration
- **scikit-learn** - Machine learning (KMeans)
- **folium** - Interactive maps
- **pandas** - Data manipulation
- **numpy** - Numerical computing
- **shapely** - Geometric operations
- **geopy** - Distance calculations

## 🔒 Security Best Practices

1. **Credentials**: This is a private repo - `credintials.json` is included but keep repo private
2. **Use IAM roles**: Prefer IAM roles over access keys in production
3. **Rotate keys**: Regularly rotate AWS access keys
4. **Least privilege**: Grant minimum required S3 permissions
5. **Use HTTPS**: S3 client uses encrypted connections by default
6. **Production**: Use environment variables instead of credentials file

### Required S3 Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

## 🐛 Troubleshooting

**No states showing?**
- Verify S3 bucket name and credentials
- Check bucket structure matches expected format
- Ensure IAM permissions are correct

**Connection errors?**
- Validate AWS credentials in `.env`
- Check network connectivity
- Verify S3 bucket region

**Shapefile loading errors?**
- Ensure all components present (.shp, .shx, .dbf, .prj)
- Verify file naming conventions
- Check CRS (coordinate reference system)

**Incomplete selections?**
- Reduce `samples_per_ac` value
- Check booth distribution in constituency
- Review cluster configuration

## 📈 Performance Tips

- **Caching**: Streamlit caches S3 connections
- **Batch processing**: Process multiple ACs/PCs at once
- **Network**: Ensure stable internet for S3 access
- **Memory**: Large states may require more RAM

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make changes with clear commit messages
4. Submit a pull request

## 🚀 API Endpoints

### Web Routes
- `GET /` - Landing page
- `GET /instructions` - Documentation page
- `GET /app` - Main application interface

### API Routes
- `GET /api/states` - List available states
- `GET /api/ac_pc_list/{state}/{selection_type}` - Get AC/PC list for state
- `POST /api/process` - Process booth mapping for all constituencies
- `GET /api/results/summary` - Get summary data
- `GET /api/results/selected_booths` - Get selected booths data
- `GET /api/results/maps` - Get list of available maps
- `GET /api/map/{filename}` - View specific map
- `GET /api/download/summary` - Download summary CSV
- `GET /api/download/selected_booths` - Download selected booths CSV
- `GET /api/download/maps` - Download all maps as ZIP

## 📄 License

This project is provided as-is for electoral analysis and research purposes.

## 🙏 Acknowledgments

- **Data Source**: Election Commission of India
- **Built with**: FastAPI, GeoPandas, Folium, scikit-learn
- **Cloud Platform**: AWS S3
- **Design Inspiration**: Modern web applications with dark themes

## 📧 Contact

For issues or questions, please open an issue on GitHub.

---

**⚠️ Important**: This tool is for research and analysis purposes. Ensure compliance with data usage policies and electoral regulations in your jurisdiction.
