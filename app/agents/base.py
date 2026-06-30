"""Base agent class for the TicketPilot multi-agent system."""
import os
import logging
from langchain.chat_models import ChatOpenAI

logger = logging.getLogger(__name__)
from app.metrics import token_usage_counter
from app.utils.retry import sync_retry
from langchain.schema import HumanMessage

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
                base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
                temperature=self.temperature,
                request_timeout=int(os.getenv("LLM_TIMEOUT", "120"))
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

    def invoke_with_retry(self, prompt: str) -> str:
        """Invoke the LLM with retry logic and return the response content.

        Args:
            prompt: The prompt string to send to the LLM.

        Returns:
            The response content as a string.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        @sync_retry(max_retries=3, base_delay=1.0, backoff=2.0,
                    exceptions=(Exception,))
        def _invoke():
            return self.llm.invoke([HumanMessage(content=prompt)])

        try:
            response = _invoke()
            self.track_tokens(response)
            return response.content.strip()
        except Exception as e:
            logger.error("LLM call failed after retries: %s", e)
            raise RuntimeError(f"LLM invocation failed: {e}") from e

    def track_tokens(self, response, model_name: str = None):
        """Track token usage in Prometheus metrics."""
        if hasattr(response, 'usage_metadata'):
            tokens = response.usage_metadata
            total = tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)
            token_usage_counter.labels(model=model_name or self.model_name).inc(total)
