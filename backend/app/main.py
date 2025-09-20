import datetime
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
import mimetypes
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from minio.error import S3Error
from starlette.background import BackgroundTask

from config import settings
from db import (
    DatabaseConnectionError,
    get_file_minio_details,
    search_files_in_db,  # keep for legacy single-file search if needed elsewhere
    # NEW:
    create_folder,
    folder_name_exists,
    insert_file_row,
    file_relpath_exists,
    search_folders,
    list_files_for_folder,
    get_pg_connection,  # make sure this is exported from db.py
    store_file_metadata_in_db,
)
from minio_client import get_minio_client
from utils import (
    get_file_extension,
    sanitize_filename,
    sanitize_project_id,
    sanitize_relative_path,  # NEW
    auto_rename_collision,  # NEW
)

# Configure logging for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read MinIO Configuration from settings instance
MINIO_ENDPOINT = settings.MINIO_ENDPOINT
MINIO_ACCESS_KEY = settings.MINIO_ACCESS_KEY
MINIO_SECRET_KEY = settings.MINIO_SECRET_KEY
MINIO_DEFAULT_BUCKET = settings.MINIO_DEFAULT_BUCKET
MINIO_USE_HTTPS = settings.MINIO_USE_HTTPS

# Initialize FastAPI app
app = FastAPI(title="API Data Service")

# Initialize MinIO client
minio_client = get_minio_client(
    endpoint=MINIO_ENDPOINT,
    username=MINIO_ACCESS_KEY,
    password=MINIO_SECRET_KEY,
    default_bucket=MINIO_DEFAULT_BUCKET,
    secure=MINIO_USE_HTTPS,
)


def _parse_root_yaml(yaml_bytes: bytes) -> dict:
    try:
        data = yaml.safe_load(yaml_bytes)
        if not isinstance(data, dict):
            raise ValueError("YAML content must be a mapping")
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid metadata YAML: {e}")


def _extract_folder_meta(
    user_metadata: dict, explicit_name: Optional[str], zip_filename: str
) -> dict:
    """
    Accepts old or new keys:
      - project OR research_project_id -> project (required)
      - author (required)
      - experiment_type (optional)
      - date_conducted (YYYY-MM-DD) (optional)
      - tags: list[str] or comma string (optional, lowercased by client)
      - notes (optional)
      - name override via form field or YAML 'name', else defaults to zip base name
    """
    project = user_metadata.get("project") or user_metadata.get("research_project_id")
    if not project:
        raise HTTPException(
            status_code=400,
            detail="Metadata must include 'project' (or legacy 'research_project_id').",
        )

    author = user_metadata.get("author")
    if not author:
        raise HTTPException(status_code=400, detail="Metadata must include 'author'.")

    experiment_type = user_metadata.get("experiment_type")
    date_conducted = None
    if user_metadata.get("date_conducted"):
        try:
            date_conducted = datetime.date.fromisoformat(
                str(user_metadata["date_conducted"])
            )
        except Exception:
            raise HTTPException(
                status_code=400, detail="date_conducted must be YYYY-MM-DD."
            )

    # tags can be JSON array or comma string; lowercased in db layer or here
    raw_tags = user_metadata.get("tags")
    if isinstance(raw_tags, list):
        tags_list = [str(t).strip().lower() for t in raw_tags if str(t).strip()]
    elif isinstance(raw_tags, str):
        tags_list = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
    else:
        tags_list = []

    notes = user_metadata.get("notes")

    base_from_zip = sanitize_filename(os.path.splitext(zip_filename or "dataset")[0])
    name = explicit_name or user_metadata.get("name") or base_from_zip

    return {
        "project": project,
        "author": author,
        "experiment_type": experiment_type,
        "date_conducted": date_conducted,
        "tags": tags_list,
        "notes": notes,
        "name": sanitize_filename(name),
    }


def _make_key_prefix(project: str) -> str:
    proj = sanitize_project_id(project) or "unknown"
    # normalize: no leading/trailing slashes and collapse multiples
    proj = proj.strip().strip("/")

    return f"{proj}/"


async def process_and_store_file(
    file_data,
    original_filename: str,
    content_type: str,
    file_size: int,
    user_metadata: dict,
    minio_folder_prefix: str = "",  # optional extra path segment
) -> dict:
    """
    Upload one file to MinIO and store its metadata in public.file_index.
    Backward-compatible with legacy metadata keys, but aligned with the new schema.

    Supports:
    - project or research_project_id (project wins if both present)
    - tags (list[str]) or custom_tags (comma string)
    - auto-counter for S3 key collisions ("name(1).ext", "name(2).ext", ...)
    """
    # --- Parse metadata (accept both old and new keys) ---
    project = (
        user_metadata.get("project") or user_metadata.get("research_project_id") or ""
    )
    author = user_metadata.get("author")
    experiment_type = user_metadata.get("experiment_type")

    # date_conducted -> date
    date_conducted = None
    date_conducted_str = user_metadata.get("date_conducted")
    if date_conducted_str:
        try:
            date_conducted = datetime.datetime.strptime(
                str(date_conducted_str), "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid date format: '{date_conducted_str}'. Storing as null."
            )

    # tags/custom_tags -> send legacy string to db helper (it will normalize to JSONB)
    custom_tags = user_metadata.get("custom_tags")
    tags = user_metadata.get("tags")
    if custom_tags is None and isinstance(tags, list):
        # Convert list to comma string; db helper will lowercase & dedupe
        custom_tags = ",".join([str(t).strip() for t in tags if str(t).strip()])

    # --- Build S3 object path (project prefix + optional folder prefix) ---
    preferred_filename = sanitize_filename(original_filename)
    project_prefix = sanitize_project_id(project)  # stable, safe
    full_prefix = (
        os.path.join(project_prefix, minio_folder_prefix)
        if minio_folder_prefix
        else project_prefix
    )

    desired_object_name = os.path.join(full_prefix, preferred_filename)
    final_object_name = desired_object_name

    # --- Collision handling (S3 key) ---
    counter = 0
    base_name_for_counter, extension_for_counter = os.path.splitext(preferred_filename)
    while True:
        try:
            # if object exists, bump counter
            minio_client.stat_object(MINIO_DEFAULT_BUCKET, final_object_name)
            counter += 1
            current_try = f"{base_name_for_counter}({counter}){extension_for_counter}"
            final_object_name = os.path.join(full_prefix, current_try)
        except S3Error as stat_exc:
            if stat_exc.code == "NoSuchKey":
                break
            raise  # re-raise other S3 errors

    # --- Upload to MinIO ---
    minio_client.put_object(
        MINIO_DEFAULT_BUCKET,
        final_object_name,
        file_data,
        length=file_size,
        part_size=10 * 1024 * 1024,
        content_type=content_type or "application/octet-stream",
    )

    # --- Persist metadata to DB (public.file_index) ---
    file_type_extension = get_file_extension(original_filename)
    ingestion_time = datetime.datetime.now(datetime.timezone.utc)
    new_file_id = uuid.uuid4()

    # Note: store_file_metadata_in_db (your updated version) maps:
    #   research_project_id -> project
    #   custom_tags (comma string) -> tags JSONB (lowercased/deduped)
    metadata_storage_result = await store_file_metadata_in_db(
        file_id=new_file_id,
        original_file_name=original_filename,
        minio_bucket_name=MINIO_DEFAULT_BUCKET,
        minio_object_path=final_object_name,
        file_type_extension=file_type_extension,
        content_type=content_type or "application/octet-stream",
        upload_timestamp=ingestion_time,
        experiment_type=experiment_type,
        date_conducted=date_conducted,
        author=author,
        research_project_id=project,
        custom_tags=custom_tags,
        size_bytes=file_size,
        # Optional new fields in your db helper; we intentionally leave them None here:
        # folder_id=None, relative_path=None, stored_filename=None, checksum_etag=None
    )

    return {
        "status": metadata_storage_result.get("status"),
        "original_filename": original_filename,
        "final_object_name": final_object_name,
        "file_id": str(new_file_id),
        "message": metadata_storage_result.get("message"),
    }


@app.get("/status")
async def read_root():
    """Root endpoint for health check or welcome message."""
    logger.info("Root endpoint accessed.")
    return {"message": "API SERVICE RUNNING"}


@app.post("/uploadfile/")
async def create_upload_file(
    data_file: UploadFile = File(...),
    metadata_file: UploadFile = File(...),
):
    """Handles a single file upload along with its YAML metadata."""
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO service not available.")

    try:
        yaml_content = await metadata_file.read()
        user_metadata = yaml.safe_load(yaml_content)
        if not isinstance(user_metadata, dict):
            raise ValueError("YAML content could not be parsed into a dictionary.")
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid or malformed metadata YAML file: {e}"
        )
    finally:
        await metadata_file.close()

    try:
        result = await process_and_store_file(
            file_data=data_file.file,
            original_filename=data_file.filename,
            content_type=data_file.content_type,
            file_size=data_file.size,
            user_metadata=user_metadata,
        )
        return JSONResponse(
            status_code=200 if result["status"] == "success" else 500, content=result
        )
    except Exception as e:
        logger.error(
            f"Error processing single file upload {data_file.filename}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        await data_file.close()


@app.post("/upload_folder/")
async def create_upload_folder(
    zip_file: UploadFile = File(...),
    metadata_file: UploadFile = File(...),
    name: Optional[str] = Form(None),  # allow overriding folder display name
):
    """
    Folder upload (ZIP) with hierarchy preservation and collision auto-rename.
    Steps:
      1) Read YAML metadata (supports 'project' or legacy 'research_project_id')
      2) Create a folder row (auto-suffix name per project; generate key_prefix)
      3) Unpack ZIP, iterate files:
         - sanitize relative path, skip hidden/system files
         - auto-rename collisions within the same directory (name (1).ext)
         - upload to MinIO at key_prefix + relative_path
         - insert row into public.file_index (denormalized with folder metadata)
      4) Return folder JSON
    """
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO service not available.")

    # Parse YAML
    try:
        yaml_bytes = await metadata_file.read()
        user_metadata = _parse_root_yaml(yaml_bytes)
    finally:
        await metadata_file.close()

    # Build folder meta and resolve name
    meta = _extract_folder_meta(
        user_metadata, explicit_name=name, zip_filename=zip_file.filename
    )

    # Create folder row with auto-suffixed name inside same project
    conn = get_pg_connection()
    try:
        final_name = meta["name"]
        suffix = 1
        while folder_name_exists(conn, project=meta["project"], name=final_name):
            final_name = f"{meta['name']} ({suffix})"
            suffix += 1

        key_prefix = _make_key_prefix(meta["project"])

        folder_row = create_folder(
            conn,
            name=final_name,
            key_prefix=key_prefix,
            project=meta["project"],
            author=meta["author"],
            experiment_type=meta["experiment_type"],
            date_conducted=meta["date_conducted"],
            tags=meta["tags"],
            notes=meta["notes"],
            immutable=True,
        )
        folder_id = folder_row["id"]
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        logger.error(f"Failed creating folder row: {e}", exc_info=True)

        raise HTTPException(status_code=500, detail=f"Failed to create folder. {e} ")
    # From here on, keep conn open so we can query for collisions and insert rows

    temp_dir = tempfile.mkdtemp()
    try:
        # Persist ZIP to disk
        zip_file_path = Path(temp_dir) / (zip_file.filename or "upload.zip")
        with open(zip_file_path, "wb") as f:
            shutil.copyfileobj(zip_file.file, f)

        if not zipfile.is_zipfile(zip_file_path):
            raise HTTPException(
                status_code=400, detail="The uploaded file is not a valid ZIP archive."
            )

        # Extract to temp
        extract_root = Path(temp_dir) / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_file_path, "r") as zf:
            zf.extractall(extract_root)

        # Iterate files under extracted tree
        uploaded = 0
        skipped = 0

        def _exists(relp: str) -> bool:
            return file_relpath_exists(
                conn, folder_id=uuid.UUID(folder_id), relative_path=relp
            )

        for fp in extract_root.rglob("*"):
            if not fp.is_file():
                continue
            # Skip artifacts
            if fp.name in (".DS_Store",) or "__MACOSX" in fp.parts:
                skipped += 1
                continue

            # Compute relative path inside the ZIP and sanitize
            rel_from_root = str(fp.relative_to(extract_root).as_posix())
            try:
                relpath = sanitize_relative_path(rel_from_root)
            except ValueError:
                skipped += 1
                continue

            # Auto-rename collisions within the same directory
            final_relpath = auto_rename_collision(relpath, _exists)

            # Prepare object_name and metadata
            object_name = f"{key_prefix}{final_relpath}"
            stored_filename = os.path.basename(final_relpath)
            original_filename = fp.name
            ext = get_file_extension(stored_filename)
            ctype, _ = mimetypes.guess_type(stored_filename)
            ctype = ctype or "application/octet-stream"
            size_bytes = fp.stat().st_size

            # Upload to MinIO
            with open(fp, "rb") as f:
                minio_client.put_object(
                    bucket_name=MINIO_DEFAULT_BUCKET,
                    object_name=object_name,
                    data=f,
                    length=size_bytes,
                    part_size=10 * 1024 * 1024,
                    content_type=ctype,
                )

            # Insert file row (denormalized with folder metadata)
            insert_file_row(
                conn,
                file_id=uuid.uuid4(),
                folder_id=uuid.UUID(folder_id),
                bucket=MINIO_DEFAULT_BUCKET,
                object_name=object_name,
                relative_path=final_relpath,
                original_filename=original_filename,
                stored_filename=stored_filename,
                extension=ext,
                content_type=ctype,
                size_bytes=size_bytes,
                checksum_etag=None,  # you can capture from MinIO response if needed
                project=folder_row["project"],
                author=folder_row["author"],
                experiment_type=folder_row.get("experiment_type"),
                date_conducted=folder_row.get("date_conducted"),
                tags=folder_row.get("tags") or [],
            )

            logger.info(
                f"Inserted file row: folder_id={folder_id} rel='{final_relpath}' key='{object_name}' size={size_bytes}"
            )

            uploaded += 1

        # Re-fetch folder to reflect rollups (if you use trigger) or leave as-is
        # It’s fine to just return folder_row; keeping it simple here.
        return {
            "folder": folder_row,
            "stats": {"uploaded": uploaded, "skipped": skipped},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing folder upload {zip_file.filename}: {e}", exc_info=True
        )
        # DEV-ONLY: show the actual error to help debug
        raise HTTPException(
            status_code=500, detail=f"Failed to process folder upload: {e}"
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            await zip_file.close()
        except Exception:
            pass
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/search")
async def search_folders_endpoint(
    project: Optional[str] = Query(None, description="Case-insensitive partial match"),
    author: Optional[str] = Query(None, description="Case-insensitive partial match"),
    experiment_type: Optional[str] = Query(
        None, description="Case-insensitive partial match"
    ),
    tags_contain: Optional[str] = Query(
        None, description="Substring over tags (case-insensitive)"
    ),
    date_after: Optional[datetime.date] = Query(None, description="YYYY-MM-DD"),
    date_before: Optional[datetime.date] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_pg_connection()
    try:
        result = search_folders(
            conn,
            project=project,
            author=author,
            experiment_type=experiment_type,
            date_after=date_after,
            date_before=date_before,
            tags_contain=tags_contain,
            limit=limit,
            offset=offset,
            sort="created_at_desc",
        )
        return result
    except Exception as e:
        logger.error(f"API Error during folder search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search error.")
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/search_files")
async def search_files_endpoint(
    file_id: uuid.UUID | None = Query(
        None, description="Filter by exact file ID (UUID)."
    ),
    research_project_id: str | None = Query(
        None, description="Project (case-insensitive, partial)."
    ),
    author: str | None = Query(None, description="Author (case-insensitive, partial)."),
    file_type: str | None = Query(
        None, description="File extension, e.g., 'tif', 'mat' (partial)."
    ),
    experiment_type: str | None = Query(
        None, description="Experiment type (case-insensitive, partial)."
    ),
    tags_contain: str | None = Query(
        None, description="Substring match over tags (case-insensitive)."
    ),
    date_after: datetime.date | None = Query(
        None, description="YYYY-MM-DD (filters date_conducted >=)."
    ),
    date_before: datetime.date | None = Query(
        None, description="YYYY-MM-DD (filters date_conducted <=)."
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    File-level search against public.file_index.
    Returns rows including folder_id and relative_path for drill-down.
    """
    try:
        results = await search_files_in_db(
            file_id=file_id,
            research_project_id=research_project_id,
            author=author,
            file_type=file_type,
            experiment_type=experiment_type,
            tags_contain=tags_contain,
            date_after=date_after,
            date_before=date_before,
            limit=limit,
            offset=offset,
        )
        return {
            "results": results,
            "limit": limit,
            "offset": offset,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"API Error during file search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.get("/folders/{folder_id}/files")
async def get_folder_files(folder_id: uuid.UUID):
    conn = get_pg_connection()
    try:
        files = list_files_for_folder(conn, folder_id)
        return {"folder_id": str(folder_id), "files": files}
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/download/{file_id}")
async def download_file_by_stream(file_id: uuid.UUID):
    """
    Looks up a file by its metadata file ID, fetches it directly from MinIO,
    and streams it back to the client as a download. This acts as a secure proxy.
    """

    response_stream = None
    if not minio_client:
        logger.error("Download link generation failed: MinIO client not initialized.")
        raise HTTPException(status_code=503, detail="MinIO service not available.")

    # Fetch Object and Path for streaming
    try:
        minio_details = await get_file_minio_details(file_id)

        if not minio_details:
            logger.warning(f"No MinIO details found for file_id: {file_id}")
            raise HTTPException(
                status_code=404, detail=f"File with ID {file_id} not found."
            )

        bucket_name = minio_details.get("bucket")
        object_path = minio_details.get("path")
        original_filename = minio_details.get("filename")
        content_type = minio_details.get("content_type") or "application/octet-stream"

        logger.info(
            f"Proxying download for '{object_path}' from bucket '{bucket_name}'..."
        )

        # Use get_object for streaming
        response_stream = minio_client.get_object(bucket_name, object_path)

        def close_stream():
            logger.info(f"Closing MinIO response stream for {object_path}")
            response_stream.close()
            response_stream.release_conn()

        return StreamingResponse(
            content=response_stream.stream(amt=65536),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{original_filename}"'
            },
            background=BackgroundTask(
                close_stream
            ),  # Use BackgroundTask so stream stays open
        )

    except HTTPException as http_exc:
        raise http_exc
    except S3Error as e:
        if e.code == "NoSuchKey":
            logger.error(
                f"File with ID {file_id} found in DB but not in MinIO at path {minio_details.get('path') if 'minio_details' in locals() else 'unknown'}"
            )
            raise HTTPException(
                status_code=404,
                detail="File record found, but data does not exist in storage.",
            )
        else:
            logger.error(
                f"MinIO S3 error during download for file ID {file_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="Error retrieving file from storage."
            )
    except DatabaseConnectionError as e:
        logger.error(
            f"Download failed due to DB connection error for file_id {file_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503, detail="Could not connect to metadata database."
        )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while downloading file for ID {file_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@app.get("/folders/{folder_id}/download_zip")
def download_folder_as_zip(
    folder_id: uuid.UUID,
    subpath: Optional[str] = Query(
        None,
        description="Optional relative prefix (e.g., 'ds/sub1/' or 'ds/sub1'). Only files whose relative_path starts with this prefix are included.",
    ),
):
    """
    Build and stream a ZIP of a folder or subfolder.
    - If subpath is omitted: root inside ZIP is <folder_name>/
    - If subpath is provided (e.g., 'ds/sub1/'): root inside ZIP is basename(subpath)/ (e.g., 'sub1/')
    - Files keep their hierarchy under that root.
    """
    # Normalize subpath
    if subpath:
        p = subpath.strip().lstrip("/").replace("\\", "/")
        if p and not p.endswith("/"):
            p += "/"
        subpath = p

    # Fetch folder name and files
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, project FROM public.folders WHERE id = %s",
                (str(folder_id),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Folder not found.")
            folder_name = row[0]

        files = list_files_for_folder(conn, folder_id)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Filter by subpath if provided
    if subpath:
        files = [f for f in files if (f.get("relative_path") or "").startswith(subpath)]

    if not files:
        raise HTTPException(
            status_code=404, detail="No files found for this folder/subpath."
        )

    # Decide archive root directory name and output filename
    if subpath:
        root_label = os.path.basename(subpath.rstrip("/")) or "subfolder"
        zip_filename = f"{root_label}.zip"
    else:
        root_label = sanitize_filename(folder_name) or "folder"
        zip_filename = f"{root_label}.zip"

    # Create a temp ZIP on disk, write files streaming from MinIO
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_path = tmp.name
    tmp.close()

    try:
        with zipfile.ZipFile(
            tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as zf:
            for row in files:
                rel = (row.get("relative_path") or "").lstrip("/")
                if not rel:
                    continue
                # Choose the arcname inside ZIP
                if subpath:
                    # Strip the subpath prefix to make it the root
                    inner = rel[len(subpath) :] if rel.startswith(subpath) else rel
                    arcname = f"{root_label}/{inner}"
                else:
                    arcname = f"{root_label}/{rel}"

                bucket = row.get("bucket") or MINIO_DEFAULT_BUCKET
                object_name = row.get("object_name")
                if not object_name:
                    logger.warning(
                        f"Skipping entry without object_name for rel='{rel}'"
                    )
                    continue

                # Stream from MinIO into the zip entry
                try:
                    obj = minio_client.get_object(bucket, object_name)
                except S3Error as e:
                    logger.error(
                        f"Skipping missing/unreadable object '{object_name}': {e}"
                    )
                    continue

                try:
                    with zf.open(arcname, mode="w") as zf_fp:
                        shutil.copyfileobj(obj, zf_fp, length=64 * 1024)
                finally:
                    try:
                        obj.close()
                        obj.release_conn()
                    except Exception:
                        pass

        # Stream ZIP to client, delete temp file afterward
        def _cleanup(path: str):
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to remove temp zip {path}: {e}")

        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename=zip_filename,
            background=BackgroundTask(_cleanup, tmp_path),
        )

    except HTTPException:
        # re-raise API errors
        raise
    except Exception as e:
        logger.error(
            f"Error building ZIP for folder {folder_id} subpath={subpath}: {e}",
            exc_info=True,
        )
        # Best effort cleanup
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to build ZIP.")
