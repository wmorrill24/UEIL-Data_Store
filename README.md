# UEIL Data Store - Biomedical Research Data Lake

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docs.docker.com/compose/)

A comprehensive data lake system designed for biomedical engineering research labs. This system provides secure, organized storage and retrieval of experimental data with metadata management, search capabilities, and multiple client interfaces.

## 🏗️ Architecture Overview

This system uses a service-oriented architecture with the following components:

### Backend Services
- **FastAPI Backend**: RESTful API for data ingestion, search, and retrieval
- **PostgreSQL Database**: Metadata storage and search indexing
- **MinIO Object Storage**: S3-compatible file storage system
- **Docker Compose**: Container orchestration for all services

### Client Libraries
- **Python Client**: Programmatic access for Python-based research workflows
- **MATLAB Client**: Integration with MATLAB analysis pipelines
- **Web Frontend**: Streamlit-based web interface for data browsing and upload

### Key Features
- **File & Folder Upload**: Support for individual files and batch folder uploads
- **Metadata Management**: Structured metadata with biomedical research fields
- **Advanced Search**: Filter by project, author, experiment type, dates, and tags
- **Version Control**: Automatic file versioning and collision handling
- **Secure Access**: Controlled access to research data
- **Multiple Interfaces**: Web UI, Python API, and MATLAB integration

## 🚀 Quick Start

### Prerequisites
- Docker Engine
- Docker Compose
- Python 3.9+ (for client libraries)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd UEIL-Data-Store
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start the System
```bash
docker-compose up --build
```

### 3. Access the Services
- **Web Frontend**: http://localhost:8501
- **API Documentation**: http://localhost:8001/docs
- **API Health Check**: http://localhost:8001/status
- **MinIO Console**: http://localhost:9001
- **Database**: localhost:5432

## 📁 Project Structure

```
UEIL-Data-Store/
├── backend/                 # FastAPI backend service
│   ├── app/                # Application code
│   ├── Dockerfile          # Backend container
│   └── requirements.txt    # Python dependencies
├── frontend/               # Streamlit web interface
│   ├── app.py             # Main Streamlit app
│   └── utils.py           # Frontend utilities
├── clients/                # Client libraries
│   ├── python/            # Python client library
│   └── matlab/            # MATLAB client library
├── docs/                   # Documentation
├── tests/                  # Test data and integration tests
└── scripts/                # Utility scripts
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file based on `.env.example`:

```bash
# MinIO Configuration
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_DEFAULT_BUCKET=raw-data

# PostgreSQL Configuration
PG_HOST=postgres-metadata-db
PG_DATABASE=metadata_db
PG_USER=your_username
PG_PASSWORD=your_password
PG_PORT=5432
```

### Database Schema
The system automatically creates the following tables:
- `public.folders`: Folder metadata and organization
- `public.file_index`: File metadata and search indexing

## 📚 Usage

### Web Interface
1. Navigate to http://localhost:8501
2. Use the upload interface to add files and folders
3. Search and browse your data using the search interface
4. Download individual files or entire folders

### Python Client
```python
from data_ingestion import upload_file, search_file, download_file

# Upload a file with metadata
result = upload_file("data.csv", "metadata.yaml")

# Search for files
results = search_file(author="researcher", experiment_type="calibration")

# Download a file
file_path = download_file("file_id_here")
```

### MATLAB Client
```matlab
% Add the client to your MATLAB path
addpath('path/to/UEIL-Data-Store/clients/matlab')

% Upload files (coming soon)
% upload_file('data.mat', 'metadata.yaml')
```

## 🔍 API Endpoints

### Core Endpoints
- `GET /status` - Health check
- `POST /uploadfile/` - Upload single file
- `POST /upload_folder/` - Upload folder (ZIP)
- `GET /search` - Search folders
- `GET /search_files` - Search individual files
- `GET /download/{file_id}` - Download file
- `GET /folders/{folder_id}/files` - List folder contents
- `GET /folders/{folder_id}/download_zip` - Download folder as ZIP

### Search Parameters
- `project`: Research project identifier
- `author`: Researcher name
- `experiment_type`: Type of experiment
- `tags_contain`: Search within tags
- `date_after` / `date_before`: Date range filtering
- `file_type`: File extension filtering

## 🧪 Testing

### Run Integration Tests
```bash
# Test API endpoints
curl http://localhost:8001/status

# Test search
curl "http://localhost:8001/search?limit=5"

# Test upload (with test files)
curl -X POST "http://localhost:8001/uploadfile/" \
  -F "data_file=@test_file.txt" \
  -F "metadata_file=@metadata.yaml"
```

### Database Testing
```bash
# Connect to database
docker-compose exec postgres-metadata-db psql -U your_username -d metadata_db

# Check tables
\dt

# View data
SELECT * FROM public.folders;
SELECT * FROM public.file_index;
```

## 🛠️ Development

### Backend Development
```bash
cd backend
# Code changes are automatically reloaded via Docker volume mounting
```

### Frontend Development
```bash
cd frontend
# Streamlit app runs with hot reload
```

### Client Library Development
```bash
cd clients/python
pip install -e .
```

## 📊 Metadata Schema

### Required Fields
- `research_project_id`: Project identifier
- `author`: Researcher name

### Optional Fields
- `experiment_type`: Type of experiment
- `date_conducted`: Date of experiment (YYYY-MM-DD)
- `custom_tags`: Comma-separated tags
- `notes`: Additional notes

### Example Metadata
```yaml
research_project_id: "Frequency_Sweep_Study"
author: "researcher_name"
experiment_type: "Calibration"
date_conducted: "2025-01-19"
custom_tags: "calibration, 1.5MHz, NHP"
notes: "Baseline calibration run"
```

## 🚀 Deployment

### Production Setup
1. Update environment variables for production
2. Configure persistent storage volumes
3. Set up backup procedures
4. Configure monitoring and logging

### Backup Strategy
- Database backups: Automated PostgreSQL dumps
- Object storage: MinIO replication
- Configuration: Version-controlled environment files

## 🤝 Contributing

### For Researchers
1. Use the web interface for data uploads
2. Follow metadata conventions
3. Use descriptive project IDs and tags

### For Developers
1. Follow the existing code structure
2. Add tests for new features
3. Update documentation for API changes

## 📞 Support

### Common Issues
- **Database connection errors**: Check PostgreSQL container status
- **File upload failures**: Verify MinIO container and permissions
- **Search not working**: Ensure database is properly initialized

### Getting Help
- Check container logs: `docker-compose logs service_name`
- Verify service status: `docker-compose ps`
- Test API connectivity: `curl http://localhost:8001/status`

## 📄 License

This project is designed for internal research use at UEIL. Please ensure compliance with your institution's data handling policies.

---

**Built for Biomedical Research** | **UEIL Data Management Platform**
