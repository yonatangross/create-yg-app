"""Unit tests for agent memory mapping functionality."""

import pytest

from app.db.models.memory import MemoryType
from app.shared.services.memory.agent_memory_mapping import (
    AGENT_MEMORY_MAP,
    get_memory_types_for_agent,
    should_include_memory_type,
)


class TestAgentMemoryMapping:
    """Tests for agent memory type filtering."""

    def test_agent_memory_map_structure(self):
        """Test that AGENT_MEMORY_MAP is properly structured."""
        assert isinstance(AGENT_MEMORY_MAP, dict)
        assert len(AGENT_MEMORY_MAP) > 0

        # Check all mappings are valid
        for agent_type, memory_types in AGENT_MEMORY_MAP.items():
            assert isinstance(agent_type, str)
            assert isinstance(memory_types, list)
            assert len(memory_types) > 0
            for mt in memory_types:
                assert isinstance(mt, MemoryType)

    def test_get_memory_types_for_chat_agent(self):
        """Test chat agent gets USER_PREFERENCE and LEARNED_FACT."""
        result = get_memory_types_for_agent("chat")

        assert result is not None
        assert MemoryType.USER_PREFERENCE in result
        assert MemoryType.LEARNED_FACT in result
        assert MemoryType.KEY_INSIGHT not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_code_review_agent(self):
        """Test code_review agent gets KEY_INSIGHT and LEARNED_FACT."""
        result = get_memory_types_for_agent("code_review")

        assert result is not None
        assert MemoryType.KEY_INSIGHT in result
        assert MemoryType.LEARNED_FACT in result
        assert MemoryType.USER_PREFERENCE not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_analysis_agent(self):
        """Test analysis agent gets CONVERSATION_SUMMARY and KEY_INSIGHT."""
        result = get_memory_types_for_agent("analysis")

        assert result is not None
        assert MemoryType.CONVERSATION_SUMMARY in result
        assert MemoryType.KEY_INSIGHT in result
        assert MemoryType.USER_PREFERENCE not in result
        assert MemoryType.LEARNED_FACT not in result

    def test_get_memory_types_for_tutor_agent(self):
        """Test tutor agent gets USER_PREFERENCE and LEARNED_FACT."""
        result = get_memory_types_for_agent("tutor")

        assert result is not None
        assert MemoryType.USER_PREFERENCE in result
        assert MemoryType.LEARNED_FACT in result
        assert MemoryType.KEY_INSIGHT not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_backend_system_architect(self):
        """Test backend-system-architect gets KEY_INSIGHT and LEARNED_FACT."""
        result = get_memory_types_for_agent("backend-system-architect")

        assert result is not None
        assert MemoryType.KEY_INSIGHT in result
        assert MemoryType.LEARNED_FACT in result
        assert MemoryType.USER_PREFERENCE not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_frontend_ui_developer(self):
        """Test frontend-ui-developer gets USER_PREFERENCE and KEY_INSIGHT."""
        result = get_memory_types_for_agent("frontend-ui-developer")

        assert result is not None
        assert MemoryType.USER_PREFERENCE in result
        assert MemoryType.KEY_INSIGHT in result
        assert MemoryType.LEARNED_FACT not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_ai_ml_engineer(self):
        """Test ai-ml-engineer gets KEY_INSIGHT and LEARNED_FACT."""
        result = get_memory_types_for_agent("ai-ml-engineer")

        assert result is not None
        assert MemoryType.KEY_INSIGHT in result
        assert MemoryType.LEARNED_FACT in result
        assert MemoryType.USER_PREFERENCE not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_code_quality_reviewer(self):
        """Test code-quality-reviewer gets KEY_INSIGHT and LEARNED_FACT."""
        result = get_memory_types_for_agent("code-quality-reviewer")

        assert result is not None
        assert MemoryType.KEY_INSIGHT in result
        assert MemoryType.LEARNED_FACT in result
        assert MemoryType.USER_PREFERENCE not in result
        assert MemoryType.CONVERSATION_SUMMARY not in result

    def test_get_memory_types_for_product_manager(self):
        """Test product-manager gets USER_PREFERENCE and CONVERSATION_SUMMARY."""
        result = get_memory_types_for_agent("product-manager")

        assert result is not None
        assert MemoryType.USER_PREFERENCE in result
        assert MemoryType.CONVERSATION_SUMMARY in result
        assert MemoryType.KEY_INSIGHT not in result
        assert MemoryType.LEARNED_FACT not in result

    def test_get_memory_types_for_unknown_agent_returns_none(self):
        """Test unknown agent returns None (uses all types)."""
        result = get_memory_types_for_agent("unknown_agent_xyz")

        assert result is None

    def test_should_include_memory_type_chat_agent(self):
        """Test should_include_memory_type for chat agent."""
        assert should_include_memory_type("chat", MemoryType.USER_PREFERENCE) is True
        assert should_include_memory_type("chat", MemoryType.LEARNED_FACT) is True
        assert should_include_memory_type("chat", MemoryType.KEY_INSIGHT) is False
        assert should_include_memory_type("chat", MemoryType.CONVERSATION_SUMMARY) is False

    def test_should_include_memory_type_code_review_agent(self):
        """Test should_include_memory_type for code_review agent."""
        assert should_include_memory_type("code_review", MemoryType.KEY_INSIGHT) is True
        assert should_include_memory_type("code_review", MemoryType.LEARNED_FACT) is True
        assert should_include_memory_type("code_review", MemoryType.USER_PREFERENCE) is False
        assert should_include_memory_type("code_review", MemoryType.CONVERSATION_SUMMARY) is False

    def test_should_include_memory_type_unknown_agent_allows_all(self):
        """Test unknown agent allows all memory types."""
        assert should_include_memory_type("unknown_agent", MemoryType.USER_PREFERENCE) is True
        assert should_include_memory_type("unknown_agent", MemoryType.LEARNED_FACT) is True
        assert should_include_memory_type("unknown_agent", MemoryType.KEY_INSIGHT) is True
        assert should_include_memory_type("unknown_agent", MemoryType.CONVERSATION_SUMMARY) is True

    def test_all_memory_types_used_somewhere(self):
        """Test that all MemoryType enum values are used in at least one mapping."""
        all_types_in_mappings = set()
        for memory_types in AGENT_MEMORY_MAP.values():
            all_types_in_mappings.update(memory_types)

        all_enum_types = set(MemoryType)

        # All enum values should be used in at least one mapping
        assert all_types_in_mappings == all_enum_types

    @pytest.mark.parametrize(
        "agent_type,expected_count",
        [
            ("chat", 2),
            ("code_review", 2),
            ("analysis", 2),
            ("tutor", 2),
            ("backend-system-architect", 2),
            ("frontend-ui-developer", 2),
            ("ai-ml-engineer", 2),
            ("code-quality-reviewer", 2),
            ("product-manager", 2),
        ],
    )
    def test_agent_memory_counts(self, agent_type, expected_count):
        """Test that each agent has expected number of memory types."""
        result = get_memory_types_for_agent(agent_type)
        assert len(result) == expected_count
