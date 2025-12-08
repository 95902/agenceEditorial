"""Initialize Qdrant collection for client articles."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.config.settings import settings
from python_scripts.utils.logging import setup_logging, get_logger
from python_scripts.vectorstore.qdrant_client import qdrant_client, CLIENT_COLLECTION_NAME

VECTOR_SIZE = 1024  # mxbai-embed-large-v1 dimension


def main() -> None:
    """Initialize Qdrant collection for client articles."""
    setup_logging()
    logger = get_logger(__name__)

    try:
        if qdrant_client.collection_exists(CLIENT_COLLECTION_NAME):
            logger.info("Collection already exists", collection=CLIENT_COLLECTION_NAME)
            print(f"Collection '{CLIENT_COLLECTION_NAME}' already exists.")
        else:
            qdrant_client.create_collection(
                collection_name=CLIENT_COLLECTION_NAME,
                vector_size=VECTOR_SIZE,
            )
            logger.info("Collection created successfully", collection=CLIENT_COLLECTION_NAME)
            print(f"Collection '{CLIENT_COLLECTION_NAME}' created successfully.")
    except Exception as e:
        logger.error("Failed to initialize collection", error=str(e))
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

