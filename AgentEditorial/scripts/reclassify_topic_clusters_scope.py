#!/usr/bin/env python3
"""
Reclassification des topic_clusters existants avec le champ `scope`.

Ce script:
- Parcourt tous les TopicCluster existants,
- Recalcule le scope à partir du label via classify_topic_label,
- Met à jour le champ `scope` (et laisse `is_valid` tel quel).

Usage:
    python scripts/reclassify_topic_clusters_scope.py
"""

import asyncio

from sqlalchemy import select

from python_scripts.analysis.article_enrichment.topic_filters import (
    classify_topic_label,
)
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import TopicCluster
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def reclassify_scopes() -> None:
    """Reclassify all TopicCluster rows with a computed scope."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TopicCluster))
        clusters = list(result.scalars().all())

        logger.info("Reclassifying topic cluster scopes", count=len(clusters))

        updated = 0
        for cluster in clusters:
            label = cluster.label or ""
            new_scope = classify_topic_label(label)

            if getattr(cluster, "scope", None) != new_scope:
                cluster.scope = new_scope
                updated += 1

        if updated:
            await session.commit()

        logger.info("Reclassification complete", updated=updated, total=len(clusters))


def main() -> None:
    asyncio.run(reclassify_scopes())


if __name__ == "__main__":
    main()





