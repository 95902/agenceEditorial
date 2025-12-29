import pytest

from python_scripts.agents.article_generation.crew import PlanningCrew


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planning_crew_runs() -> None:
    crew = PlanningCrew()
    result = await crew.run(topic="Sujet de test pour article", keywords=["test", "article"])
    assert "raw_outline" in result











