import logging

from minio import Minio

logger = logging.getLogger(__name__)


def get_minio_client(
    endpoint: str, username: str, password: str, default_bucket: str, secure: bool
):
    """
    Initialize and return a MinIO client instance.
    """

    logger.info(f"MinIO Client Secure Flag is: {str(secure)} (Type: {secure})")

    client = None
    # Ensure all required MinIO settings are present
    if endpoint and username and password:
        try:
            logger.info(f"Initializing MinIO client for endpoint: {endpoint}")
            # Create MinIO client instance
            client = Minio(
                endpoint,
                username,
                password,
                secure=secure,
            )
        except Exception as e:
            logger.error(f"Minio client initialization failed: {e}", exc_info=True)
    else:
        logger.warning(
            "MinIO credentials not properly set in environment. MinIO client NOT initialized."
        )
    # Ensure the default bucket exists
    if not client.bucket_exists(default_bucket):
        client.make_bucket(default_bucket)
        logger.info(f"Bucket '{default_bucket}' created in MinIO.")
    else:
        logger.info(f"Bucket '{default_bucket}' already exists in MinIO.")
    return client
