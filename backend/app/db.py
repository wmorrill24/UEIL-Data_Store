# db.py (drop-in)
import datetime
import logging
import uuid
import json
from typing import Optional, Iterable, Dict, Any, List

import psycopg2

from config import settings

logger = logging.getLogger(__name__)

# ---- Connection config (unchanged) ----
PG_HOST = settings.PG_HOST
PG_DATABASE = settings.PG_DATABASE
PG_USER = settings.PG_USER
PG_PASSWORD = settings.PG_PASSWORD
PG_PORT = settings.PG_PORT


class DatabaseConnectionError(Exception):
    """Custom exception for database connection errors."""

    pass


def get_pg_connection():
    """
    Establish and return a connection to the PostgreSQL database.
    Raises DatabaseConnectionError if configuration is missing or connection fails.
    """
    if not all([PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD]):
        logger.error(
            "PostgreSQL connection details (PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD) are not fully configured."
        )
        raise DatabaseConnectionError(
            "Configuration details not set for PostgreSQL connection."
        )
    try:
        conn_string = (
            f"host='{PG_HOST}' port='{PG_PORT}' dbname='{PG_DATABASE}' "
            f"user='{PG_USER}' password='{PG_PASSWORD}'"
        )
        return psycopg2.connect(conn_string)
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}", exc_info=True)
        raise DatabaseConnectionError(f"Failed to connect to database: {e}")
    except Exception as e:
        logger.error(f"Unexpected error connecting to PostgreSQL: {e}", exc_info=True)
        raise DatabaseConnectionError(f"Unexpected error: {e}")


# =============================================================================
# Folder-centric helpers (ADDITIVE)
# =============================================================================


def create_folder(
    conn,
    *,
    name: str,
    key_prefix: str,
    project: str,
    author: str,
    experiment_type: Optional[str] = None,
    date_conducted: Optional[datetime.date] = None,
    tags: Optional[Iterable[str]] = None,
    notes: Optional[str] = None,
    immutable: bool = True,
) -> Dict[str, Any]:
    """
    Insert a new folder row into public.folders and return the full row.
    """
    payload = {
        "name": name,
        "key_prefix": key_prefix,
        "project": project,
        "author": author,
        "experiment_type": experiment_type,
        "date_conducted": date_conducted,
        "tags": json.dumps(list(tags or [])),
        "notes": notes,
        "immutable": immutable,
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.folders (
                id, name, key_prefix, project, author, experiment_type, date_conducted,
                tags, notes, immutable, file_count, total_size, created_at, updated_at
            ) VALUES (
                uuid_generate_v4(), %(name)s, %(key_prefix)s, %(project)s, %(author)s,
                %(experiment_type)s, %(date_conducted)s,
                %(tags)s::jsonb, %(notes)s, %(immutable)s, 0, 0, NOW(), NOW()
            )
            RETURNING id, name, key_prefix, project, author, experiment_type, date_conducted,
                      tags, notes, immutable, file_count, total_size, created_at, updated_at
            """,
            payload,
        )
        row = cur.fetchone()
        cols = [d[0] for d in cur.description]
        conn.commit()
        return dict(zip(cols, row))


def folder_name_exists(conn, *, project: str, name: str) -> bool:
    """
    True if a folder with (project, name) already exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM public.folders WHERE project=%s AND name=%s LIMIT 1",
            (project, name),
        )
        return cur.fetchone() is not None


def list_files_for_folder(conn, folder_id: uuid.UUID) -> List[Dict[str, Any]]:
    """
    Return files for a folder ordered by relative_path.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT file_id, relative_path, stored_filename, original_filename,
                   extension, size_bytes, content_type, created_at, bucket, object_name
            FROM public.file_index
            WHERE folder_id=%s
            ORDER BY relative_path ASC
            """,
            (str(folder_id),),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def file_relpath_exists(conn, *, folder_id: uuid.UUID, relative_path: str) -> bool:
    """
    True if (folder_id, relative_path) already exists in public.file_index.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM public.file_index
             WHERE folder_id=%s AND relative_path=%s
             LIMIT 1
            """,
            (str(folder_id), relative_path),
        )
        return cur.fetchone() is not None


def insert_file_row(
    conn,
    *,
    file_id: uuid.UUID,
    folder_id: uuid.UUID,
    bucket: str,
    object_name: str,
    relative_path: str,
    original_filename: str,
    stored_filename: str,
    extension: Optional[str],
    content_type: Optional[str],
    size_bytes: int,
    checksum_etag: Optional[str],
    project: str,
    author: str,
    experiment_type: Optional[str],
    date_conducted: Optional[datetime.date],
    tags: Iterable[str],
) -> str:
    """
    Insert a file row into public.file_index (denormalized with folder metadata).
    Returns the file_id as string.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.file_index (
                file_id, folder_id, bucket, object_name, relative_path,
                original_filename, stored_filename, extension, content_type,
                size_bytes, checksum_etag, created_at,
                project, author, experiment_type, date_conducted, tags
            ) VALUES (
                %(file_id)s, %(folder_id)s, %(bucket)s, %(object_name)s, %(relative_path)s,
                %(original_filename)s, %(stored_filename)s, %(extension)s, %(content_type)s,
                %(size_bytes)s, %(checksum_etag)s, NOW(),
                %(project)s, %(author)s, %(experiment_type)s, %(date_conducted)s, %(tags)s::jsonb
            )
            RETURNING file_id
            """,
            {
                "file_id": str(file_id),
                "folder_id": str(folder_id),
                "bucket": bucket,
                "object_name": object_name,
                "relative_path": relative_path,
                "original_filename": original_filename,
                "stored_filename": stored_filename,
                "extension": extension,
                "content_type": content_type,
                "size_bytes": int(size_bytes),
                "checksum_etag": checksum_etag,
                "project": project,
                "author": author,
                "experiment_type": experiment_type,
                "date_conducted": date_conducted,
                "tags": json.dumps(list(tags or [])),
            },
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return str(new_id)


def search_folders(
    conn,
    *,
    project: Optional[str] = None,
    author: Optional[str] = None,
    experiment_type: Optional[str] = None,
    date_after: Optional[datetime.date] = None,
    date_before: Optional[datetime.date] = None,
    tags_contain: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at_desc",
) -> Dict[str, Any]:
    """
    Search public.folders with case-insensitive partials and return paginated results.
    """
    wh, params = [], {}
    if project:
        wh.append("project ILIKE %(project)s")
        params["project"] = f"%{project}%"
    if author:
        wh.append("author ILIKE %(author)s")
        params["author"] = f"%{author}%"
    if experiment_type:
        wh.append("experiment_type ILIKE %(experiment_type)s")
        params["experiment_type"] = f"%{experiment_type}%"
    if date_after:
        wh.append("date_conducted >= %(date_after)s")
        params["date_after"] = date_after
    if date_before:
        wh.append("date_conducted <= %(date_before)s")
        params["date_before"] = date_before
    if tags_contain:
        wh.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text(tags) t WHERE t ILIKE %(tagq)s)"
        )
        params["tagq"] = f"%{tags_contain}%".lower()

    where_sql = f"WHERE {' AND '.join(wh)}" if wh else ""
    order_sql = (
        "ORDER BY created_at DESC"
        if sort == "created_at_desc"
        else "ORDER BY created_at ASC"
    )

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM public.folders {where_sql}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT id, name, key_prefix, project, author, experiment_type,
                   date_conducted, tags, notes, immutable,
                   file_count, total_size, created_at, updated_at
            FROM public.folders
            {where_sql}
            {order_sql}
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**params, "limit": int(limit), "offset": int(offset)},
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    return {"results": rows, "total": total, "limit": int(limit), "offset": int(offset)}


# =============================================================================
# Updated legacy endpoints to point at new schema (REPLACEMENTS)
# =============================================================================


async def store_file_metadata_in_db(
    file_id: uuid.UUID,
    original_file_name: str,
    file_type_extension: str,
    content_type: str,
    size_bytes: int,
    minio_bucket_name: str,
    minio_object_path: str,
    upload_timestamp: datetime.datetime,
    research_project_id: str = None,
    experiment_type: str = None,
    author: str = None,
    date_conducted: datetime.date = None,
    custom_tags: str = None,
    # New optional fields to align with folder-aware design:
    folder_id: Optional[uuid.UUID] = None,
    relative_path: Optional[str] = None,
    stored_filename: Optional[str] = None,
    checksum_etag: Optional[str] = None,
) -> dict:
    """
    Backward-compatible insert for single-file flows.
    Writes to public.file_index, mapping legacy param names:
      - research_project_id -> project
      - file_type_extension -> extension
      - custom_tags (comma string) -> tags (JSONB, lowercased & deduped)
    """
    # Normalize tags: TEXT -> JSONB lowercased list
    tags_list: List[str] = []
    if custom_tags:
        tags_list = [t.strip().lower() for t in custom_tags.split(",") if t.strip()]

    conn = None
    try:
        conn = get_pg_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.file_index (
                    file_id, folder_id, bucket, object_name, relative_path,
                    original_filename, stored_filename, extension, content_type,
                    size_bytes, checksum_etag, created_at,
                    project, author, experiment_type, date_conducted, tags
                ) VALUES (
                    %(file_id)s, %(folder_id)s, %(bucket)s, %(object_name)s, %(relative_path)s,
                    %(original_filename)s, %(stored_filename)s, %(extension)s, %(content_type)s,
                    %(size_bytes)s, %(checksum_etag)s, %(created_at)s,
                    %(project)s, %(author)s, %(experiment_type)s, %(date_conducted)s, %(tags)s::jsonb
                )
                """,
                {
                    "file_id": str(file_id),
                    "folder_id": str(folder_id) if folder_id else None,
                    "bucket": minio_bucket_name,
                    "object_name": minio_object_path,
                    "relative_path": relative_path,
                    "original_filename": original_file_name,
                    "stored_filename": stored_filename or original_file_name,
                    "extension": file_type_extension,
                    "content_type": content_type,
                    "size_bytes": int(size_bytes),
                    "checksum_etag": checksum_etag,
                    "created_at": upload_timestamp,
                    "project": research_project_id,
                    "author": author,
                    "experiment_type": experiment_type,
                    "date_conducted": date_conducted,
                    "tags": json.dumps(tags_list),
                },
            )
            conn.commit()

        return {
            "status": "success",
            "file_id": str(file_id),
            "inserted_metadata_summary": {
                "original_file_name": original_file_name,
                "minio_object_path": minio_object_path,
                "project": research_project_id,
            },
            "message": "Metadata stored successfully.",
        }
    except (DatabaseConnectionError, psycopg2.Error) as e:
        if conn:
            conn.rollback()
        logger.error(f"DB error storing metadata: {e}", exc_info=True)
        return {"status": "error", "message": f"Database error: {str(e)}"}
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error storing metadata: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to store metadata: {str(e)}"}
    finally:
        if conn:
            conn.close()


async def search_files_in_db(
    file_id: uuid.UUID | None = None,
    research_project_id: str | None = None,  # maps to public.file_index.project
    author: str | None = None,
    file_type: str | None = None,  # maps to public.file_index.extension
    experiment_type: str | None = None,
    tags_contain: str | None = None,  # case-insensitive substring over JSONB tags
    date_before: datetime.date | None = None,  # filters date_conducted
    date_after: datetime.date | None = None,  # filters date_conducted
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """
    Search public.file_index with case-insensitive partial matches.
    """
    logger.info(
        "Searching for files in PostgreSQL (public.file_index) with provided filters."
    )
    conn = None
    results: List[dict] = []

    try:
        conn = get_pg_connection()
        with conn.cursor() as cursor:
            base_query = """
            SELECT
                file_id, folder_id, bucket, object_name, relative_path,
                original_filename, stored_filename, extension, content_type,
                size_bytes, checksum_etag, created_at,
                project, author, experiment_type, date_conducted, tags
            FROM public.file_index
            """

            where_clauses: List[str] = []
            params: Dict[str, object] = {}

            if file_id:
                where_clauses.append("file_id = %(file_id)s")
                params["file_id"] = str(file_id)

            if research_project_id:
                where_clauses.append("project ILIKE %(project)s")
                params["project"] = f"%{research_project_id}%"

            if author:
                where_clauses.append("author ILIKE %(author)s")
                params["author"] = f"%{author}%"

            if file_type:
                where_clauses.append("extension ILIKE %(extension)s")
                params["extension"] = f"%{file_type}%"

            if experiment_type:
                where_clauses.append("experiment_type ILIKE %(experiment_type)s")
                params["experiment_type"] = f"%{experiment_type}%"

            if date_after:
                where_clauses.append("date_conducted >= %(date_after)s")
                params["date_after"] = date_after

            if date_before:
                where_clauses.append("date_conducted <= %(date_before)s")
                params["date_before"] = date_before

            if tags_contain:
                where_clauses.append(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements_text(tags) t WHERE t ILIKE %(tagq)s)"
                )
                params["tagq"] = f"%{tags_contain}%".lower()

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            order_sql = "ORDER BY created_at DESC"
            limit_sql = "LIMIT %(limit)s OFFSET %(offset)s"
            params["limit"] = int(limit)
            params["offset"] = int(offset)

            final_query = f"{base_query} {where_sql} {order_sql} {limit_sql};"
            logger.info(f"Executing search query: {final_query} with params: {params}")

            cursor.execute(final_query, params)
            colnames = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(colnames, row)))

        return results

    except (DatabaseConnectionError, psycopg2.Error) as e:
        logger.error(f"Database error during metadata search: {e}", exc_info=True)
        raise e
    finally:
        if conn:
            conn.close()


async def get_file_minio_details(file_id: uuid.UUID) -> dict | None:
    """
    Retrieves the MinIO bucket and object path, file name, and content_type for a given file_id.
    """
    logger.info(f"Retrieving MinIO details for file ID: {file_id}")

    conn = None
    try:
        conn = get_pg_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT bucket, object_name, original_filename, content_type
                FROM public.file_index
                WHERE file_id = %s
                """,
                (str(file_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None

            bucket_name, object_path, filename, content_type = row
            return {
                "bucket": bucket_name,
                "path": object_path,
                "filename": filename,
                "content_type": content_type,
            }
    except (DatabaseConnectionError, psycopg2.Error) as e:
        logger.error(f"Database error retrieving MinIO details: {e}", exc_info=True)
        raise e
    finally:
        if conn:
            conn.close()
