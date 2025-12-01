"""LLM factory for creating Ollama LLM instances."""

from typing import Optional

from langchain_ollama import OllamaLLM

from python_scripts.config.settings import settings
from python_scripts.utils.exceptions import LLMError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def create_llm(
    model_name: str,
    temperature: float = 0.7,
    timeout: int = 300,
) -> OllamaLLM:
    """
    Create an Ollama LLM instance.

    Args:
        model_name: Name of the model (e.g., "llama3:8b")
        temperature: Temperature for generation
        timeout: Request timeout in seconds

    Returns:
        OllamaLLM instance
    """
    try:
        llm = OllamaLLM(
            model=model_name,
            base_url=settings.ollama_base_url,
            temperature=temperature,
            timeout=timeout,
        )
        logger.info("LLM created", model=model_name, base_url=settings.ollama_base_url)
        return llm
    except Exception as e:
        logger.error("Failed to create LLM", model=model_name, error=str(e))
        raise LLMError(f"Failed to create LLM {model_name}: {e}") from e


def get_llama3_llm(temperature: float = 0.7) -> OllamaLLM:
    """Get llama3:8b LLM instance."""
    return create_llm("llama3:8b", temperature=temperature)


def get_mistral_llm(temperature: float = 0.7) -> OllamaLLM:
    """Get mistral:7b LLM instance."""
    return create_llm("mistral:7b", temperature=temperature)


def get_phi3_llm(temperature: float = 0.7) -> OllamaLLM:
    """Get phi3:medium LLM instance."""
    return create_llm("phi3:medium", temperature=temperature)

