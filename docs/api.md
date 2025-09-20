# API Documentation

## Base URL
```
http://localhost:8001
```

## Authentication
Currently no authentication is required. All endpoints are publicly accessible.

## Endpoints

### Health Check
```http
GET /status
```

**Response:**
```json
{
  "message": "API SERVICE RUNNING"
}
```

### File Upload

#### Single File Upload
```http
POST /uploadfile/
Content-Type: multipart/form-data
```

**Parameters:**
- `data_file`: The file to upload
- `metadata_file`: YAML metadata file

**Example:**
```bash
curl -X POST "http://localhost:8001/uploadfile/" \
  -F "data_file=@data.csv" \
  -F "metadata_file=@metadata.yaml"
```

**Response:**
```json
{
  "status": "success",
  "original_filename": "data.csv",
  "final_object_name": "ProjectName/data.csv",
  "file_id": "uuid-here",
  "message": "Metadata stored successfully."
}
```

#### Folder Upload
```http
POST /upload_folder/
Content-Type: multipart/form-data
```

**Parameters:**
- `zip_file`: ZIP file containing the folder
- `metadata_file`: YAML metadata file
- `name`: Optional folder name override

**Example:**
```bash
curl -X POST "http://localhost:8001/upload_folder/" \
  -F "zip_file=@experiment.zip" \
  -F "metadata_file=@metadata.yaml" \
  -F "name=Experiment_2025_01_19"
```

### Search

#### Search Folders
```http
GET /search
```

**Query Parameters:**
- `project`: Research project ID (partial match)
- `author`: Author name (partial match)
- `experiment_type`: Experiment type (partial match)
- `tags_contain`: Search within tags
- `date_after`: Filter by date (YYYY-MM-DD)
- `date_before`: Filter by date (YYYY-MM-DD)
- `limit`: Number of results (default: 50)
- `offset`: Pagination offset (default: 0)

**Example:**
```bash
curl "http://localhost:8001/search?author=researcher&limit=10"
```

#### Search Files
```http
GET /search_files
```

**Query Parameters:**
- `file_id`: Exact file ID (UUID)
- `research_project_id`: Project ID (partial match)
- `author`: Author name (partial match)
- `file_type`: File extension (e.g., 'pdf', 'csv')
- `experiment_type`: Experiment type (partial match)
- `tags_contain`: Search within tags
- `date_after`: Filter by date (YYYY-MM-DD)
- `date_before`: Filter by date (YYYY-MM-DD)
- `limit`: Number of results (default: 100)
- `offset`: Pagination offset (default: 0)

### Download

#### Download File
```http
GET /download/{file_id}
```

**Example:**
```bash
curl -O "http://localhost:8001/download/uuid-here"
```

#### List Folder Files
```http
GET /folders/{folder_id}/files
```

**Response:**
```json
{
  "folder_id": "uuid-here",
  "files": [
    {
      "file_id": "uuid-here",
      "relative_path": "data/file1.csv",
      "stored_filename": "file1.csv",
      "original_filename": "file1.csv",
      "extension": "CSV",
      "size_bytes": 1024,
      "content_type": "text/csv",
      "created_at": "2025-01-19T10:00:00Z"
    }
  ]
}
```

#### Download Folder as ZIP
```http
GET /folders/{folder_id}/download_zip
```

**Query Parameters:**
- `subpath`: Optional subfolder path to download

**Example:**
```bash
curl -O "http://localhost:8001/folders/uuid-here/download_zip"
```

## Metadata Schema

### Required Fields
- `research_project_id`: Project identifier
- `author`: Researcher name

### Optional Fields
- `experiment_type`: Type of experiment
- `date_conducted`: Date of experiment (YYYY-MM-DD)
- `custom_tags`: Comma-separated tags
- `notes`: Additional notes

### Example Metadata File
```yaml
research_project_id: "Frequency_Sweep_Study"
author: "researcher_name"
experiment_type: "Calibration"
date_conducted: "2025-01-19"
custom_tags: "calibration, 1.5MHz, NHP"
notes: "Baseline calibration run"
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid metadata YAML file: missing required field 'author'"
}
```

### 404 Not Found
```json
{
  "detail": "File with ID uuid-here not found."
}
```

### 500 Internal Server Error
```json
{
  "detail": "An unexpected error occurred: database connection failed"
}
```

## Rate Limiting

Currently no rate limiting is implemented. For production deployment, consider implementing rate limiting based on your requirements.

## CORS

CORS is enabled for all origins. For production, configure appropriate CORS settings.
