"""Tests for the multi-agent pipeline."""
import json
from unittest.mock import MagicMock, patch, PropertyMock

from app.agents.router_agent import RouterAgent
from app.agents.context_agent import ContextAgent
from app.agents.quality_agent import QualityAgent

BILLING = '{"category": "billing", "priority": "medium", "requires_rag": true, "reason": ""}'
ACCESS = '{"category": "access", "priority": "high", "requires_rag": true, "reason": ""}'
GOOD_QA = '{"reason": "OK", "hallucination_risk": "low", "actionable": true, "professional_tone": true}'


class TestRouterAgent:
    def test_classifies_login(self, mock_llm, agent_state):
        mock_llm(ACCESS)
        state = RouterAgent().run(agent_state)
        assert state['category'] == 'access'

    def test_classifies_billing(self, mock_llm, agent_state):
        mock_llm(BILLING)
        agent_state['description'] = 'My bill is wrong'
        state = RouterAgent().run(agent_state)
        assert state['category'] == 'billing'

    def test_fallback_on_bad_json(self, mock_llm, agent_state):
        mock_llm('not json')
        state = RouterAgent().run(agent_state)
        assert state['category'] == 'general'


class TestContextAgent:
    def test_retrieves(self, mock_qdrant, agent_state):
        state = ContextAgent().run(agent_state)
        assert len(state['context_docs']) == 3

    def test_empty(self, mock_qdrant, agent_state):
        mock_qdrant.return_value = []
        state = ContextAgent().run(agent_state)
        assert state['context_docs'] == []


class TestQualityAgent:
    def test_empty_resolution(self, mock_llm, agent_state):
        agent_state['resolution'] = ''
        state = QualityAgent().run(agent_state)
        assert state['quality_check']['passed'] is False

    def test_error_resolution(self, mock_llm, agent_state):
        agent_state['resolution'] = 'Error: something'
        state = QualityAgent().run(agent_state)
        assert state['quality_check']['passed'] is False

    def test_works_with_context(self, mock_llm, agent_state):
        mock_llm(GOOD_QA)
        agent_state['resolution'] = 'Reset your password.'
        agent_state['context_docs'] = [{'text': 'reset password info', 'score': 0.9}]
        state = QualityAgent().run(agent_state)
        assert 'quality_check' in state
        assert state['quality_check']['confidence'] > 0

    def test_llm_fallback_does_not_crash(self, mock_llm, agent_state):
        mock_llm('bad json')
        agent_state['resolution'] = 'Reset your password.'
        agent_state['context_docs'] = [{'text': 'info', 'score': 0.5}]
        state = QualityAgent().run(agent_state)
        assert 'quality_check' in state
        assert state['quality_check']['passed'] is False