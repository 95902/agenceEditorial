"""Initialize Qdrant collection for client articles."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.config.settings import settings
from python_scripts.utils.logging import setup_logging, get_logger
from python_scripts.vectorstore.qdrant_client import qdrant_client, get_client_collection_name

VECTOR_SIZE = 1024  # mxbai-embed-large-v1 dimension


def main() -> None:
    """Initialize Qdrant collection for client articles."""
    setup_logging()
    logger = get_logger(__name__)

    # Get domain from command line argument
    if len(sys.argv) < 2:
        print("Usage: python init_qdrant_client.py <domain>")
        print("Example: python init_qdrant_client.py example.com")
        sys.exit(1)

    domain = sys.argv[1]
    collection_name = get_client_collection_name(domain)

    try:
        if qdrant_client.collection_exists(collection_name):
            logger.info("Collection already exists", collection=collection_name, domain=domain)
            print(f"Collection '{collection_name}' already exists for domain '{domain}'.")
        else:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vector_size=VECTOR_SIZE,
            )
            logger.info("Collection created successfully", collection=collection_name, domain=domain)
            print(f"Collection '{collection_name}' created successfully for domain '{domain}'.")
    except Exception as e:
        logger.error("Failed to initialize collection", error=str(e), domain=domain)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

