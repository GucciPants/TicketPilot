"""Base agent class for the TicketPilot multi-agent system."""
import os
from langchain.chat_models import ChatOpenAI
from app.metrics import token_usage_counter

class BaseAgent:
    """Abstract base class for all agents in the pipeline."""

    def __init__(self, model: str = None, temperature: float = 0.3):
        self.model_name = model or os.getenv("TRIAGE_MODEL", "google/gemini-2.0-flash-001")
        self.temperature = temperature
        self._llm = None

    @property
    def llm(self):
        """Lazy-initialized LLM instance with timeout."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model_name,
                openai_api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
                temperature=self.temperature,
                request_timeout=20
            )
        return self._llm

    def run(self, state: dict) -> dict:
        """Execute the agent's task and return updated state.
        
        Args:
            state: Shared pipeline state dictionary
        
        Returns:
            Updated state dictionary
        """
        raise NotImplementedError("Subclasses must implement run()")

    def track_tokens(self, response, model_name: str = None):
        """Track token usage in Prometheus metrics."""
        if hasattr(response, 'usage_metadata'):
            tokens = response.usage_metadata
            total = tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)
            token_usage_counter.labels(model=model_name or self.model_name).inc(total)
