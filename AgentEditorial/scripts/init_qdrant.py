"""Initialize Qdrant collection for competitor articles."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.config.settings import settings
from python_scripts.utils.logging import setup_logging, get_logger
from python_scripts.vectorstore.qdrant_client import qdrant_client

COLLECTION_NAME = "competitor_articles"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 dimension


def main() -> None:
    """Initialize Qdrant collection."""
    setup_logging()
    logger = get_logger(__name__)

    try:
        if qdrant_client.collection_exists(COLLECTION_NAME):
            logger.info("Collection already exists", collection=COLLECTION_NAME)
            print(f"Collection '{COLLECTION_NAME}' already exists.")
        else:
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vector_size=VECTOR_SIZE,
            )
            logger.info("Collection created successfully", collection=COLLECTION_NAME)
            print(f"Collection '{COLLECTION_NAME}' created successfully.")
    except Exception as e:
        logger.error("Failed to initialize collection", error=str(e))
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

