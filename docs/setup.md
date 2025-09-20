# Setup Guide

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd UEIL-Data-Store
   ```

2. **Configure environment**
   ```bash
   cp env.template .env
   # Edit .env with your settings
   ```

3. **Start the system**
   ```bash
   docker-compose up --build
   ```

4. **Access the services**
   - Web Interface: http://localhost:8501
   - API Documentation: http://localhost:8001/docs
   - MinIO Console: http://localhost:9001

## Development Setup

### Using Dev Containers (Recommended)

1. Open the project in VS Code
2. Install the "Dev Containers" extension
3. Open the project in a dev container
4. All services will be available in the container environment

### Local Development

1. **Start infrastructure services**
   ```bash
   docker-compose up postgres-metadata-db minio-server
   ```

2. **Run backend locally**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. **Run frontend locally**
   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run app.py
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin123` |
| `PG_USER` | PostgreSQL username | `postgres` |
| `PG_PASSWORD` | PostgreSQL password | `postgres123` |
| `PG_DATABASE` | Database name | `metadata_db` |

### Database Setup

The database schema is automatically created on first startup. The system creates:

- `public.folders` - Folder metadata
- `public.file_index` - File metadata and search index

### MinIO Setup

MinIO automatically creates the default bucket (`raw-data`) on first startup.

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 8001, 8501, 9000, 9001, 5432 are available
2. **Database connection**: Check PostgreSQL container logs
3. **File uploads**: Verify MinIO container is running
4. **Permission issues**: Ensure Docker has proper permissions

### Debug Commands

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs backend
docker-compose logs postgres-metadata-db
docker-compose logs minio-server

# Test API
curl http://localhost:8001/status

# Connect to database
docker-compose exec postgres-metadata-db psql -U your_username -d metadata_db
```
