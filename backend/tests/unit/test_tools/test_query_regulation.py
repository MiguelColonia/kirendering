"""Tests del tool query_regulation (stub normativo)."""

import pytest

from cimiento.llm.tools.query_regulation import RegulationQueryResult, query_regulation


@pytest.mark.parametrize(
    "topic",
    ["height", "coverage", "far", "habitability", "parking", "accessibility"],
)
@pytest.mark.asyncio
async def test_query_regulation_known_topics_return_items(topic: str) -> None:
    result = await query_regulation(topic)
    assert isinstance(result, RegulationQueryResult)
    assert result.topic == topic
    assert result.is_mock is True
    assert len(result.items) > 0


@pytest.mark.asyncio
async def test_query_regulation_unknown_topic_returns_all_items() -> None:
    result = await query_regulation("solar_orientation")
    assert isinstance(result, RegulationQueryResult)
    assert len(result.items) > 0


@pytest.mark.asyncio
async def test_query_regulation_disclaimer_present() -> None:
    result = await query_regulation("height")
    assert len(result.disclaimer) > 20


@pytest.mark.asyncio
async def test_query_regulation_items_have_required_fields() -> None:
    result = await query_regulation("habitability")
    for item in result.items:
        assert item.code
        assert item.description
        assert item.value
        assert item.source
