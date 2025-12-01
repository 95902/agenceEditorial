"""Editorial analysis agent with multi-LLM orchestration."""

import json
import re
from typing import Any, Dict, List

from python_scripts.agents.base_agent import BaseAgent
from python_scripts.agents.prompts import (
    EDITORIAL_ANALYSIS_PROMPT_LLAMA3,
    EDITORIAL_ANALYSIS_PROMPT_MISTRAL,
    EDITORIAL_ANALYSIS_PROMPT_PHI3,
    EDITORIAL_SYNTHESIS_PROMPT,
)
from python_scripts.agents.utils.llm_factory import (
    get_llama3_llm,
    get_mistral_llm,
    get_phi3_llm,
)
from python_scripts.utils.exceptions import LLMError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def extract_and_parse_json(response_text: str, model_name: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response with multiple fallback strategies.

    Args:
        response_text: Raw response from LLM
        model_name: Name of the model (for logging)

    Returns:
        Parsed JSON as dictionary

    Raises:
        LLMError: If all parsing strategies fail
    """
    # Strategy 1: Try to find JSON block between ```json and ```
    json_block_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: Try to find JSON block between ``` and ```
    code_block_match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first { and last } and extract
    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        json_text = response_text[json_start:json_end]

        # Try direct parse
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            # Strategy 4: Try to fix common JSON issues
            fixed_json = fix_json_common_issues(json_text)
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                # Strategy 5: Try to extract valid JSON parts
                return extract_partial_json(json_text, model_name)

    # Strategy 6: Try parsing entire response
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        raise LLMError(
            f"Failed to parse {model_name} response: Could not extract valid JSON"
        )


def fix_json_common_issues(json_text: str) -> str:
    """
    Fix common JSON issues in LLM responses.

    Args:
        json_text: JSON string with potential issues

    Returns:
        Fixed JSON string
    """
    # Remove trailing commas before } or ]
    json_text = re.sub(r",\s*}", "}", json_text)
    json_text = re.sub(r",\s*]", "]", json_text)

    # Fix missing quotes around keys (only if key doesn't have quotes)
    # Match: key: (where key is a word without quotes)
    json_text = re.sub(r'(\w+):', r'"\1":', json_text)

    # Fix single quotes to double quotes (basic, be careful)
    # Only replace single quotes that are clearly string delimiters
    json_text = re.sub(r"'([^']*)':", r'"\1":', json_text)

    return json_text


def extract_partial_json(json_text: str, model_name: str) -> Dict[str, Any]:
    """
    Extract valid JSON parts even if full JSON is invalid.

    Args:
        json_text: Invalid JSON string
        model_name: Name of the model (for logging)

    Returns:
        Dictionary with extracted valid parts

    Raises:
        LLMError: If no valid parts can be extracted
    """
    result = {}

    # Try to extract key-value pairs
    # Match: "key": value (where value can be string, number, boolean, null, object, array)
    # More sophisticated pattern
    pattern = r'"([^"]+)":\s*([^,}\]]+?)(?=\s*[,}\]])'
    matches = re.findall(pattern, json_text)

    for key, value in matches:
        value = value.strip()
        # Remove trailing commas
        value = value.rstrip(",").strip()

        # Try to parse value as JSON
        try:
            # Try as JSON first
            result[key] = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            # If not valid JSON, try to infer type
            if value.lower() in ("true", "false"):
                result[key] = value.lower() == "true"
            elif value.lower() == "null":
                result[key] = None
            elif value.isdigit():
                result[key] = int(value)
            elif re.match(r"^-?\d+\.\d+$", value):
                result[key] = float(value)
            else:
                # Remove quotes if present
                value = value.strip('"').strip("'")
                result[key] = value

    if not result:
        logger.warning("Could not extract any valid JSON parts", model=model_name)
        raise LLMError(
            f"Failed to parse {model_name} response: No valid JSON could be extracted"
        )

    logger.warning(
        "Partial JSON extraction used",
        model=model_name,
        extracted_keys=list(result.keys()),
    )
    return result


class EditorialAnalysisAgent(BaseAgent):
    """Agent for analyzing editorial style using multiple LLMs."""

    def __init__(self) -> None:
        """Initialize the editorial analysis agent."""
        super().__init__("editorial_analysis")

    async def analyze_with_llm(
        self,
        content: str,
        model_name: str,
        prompt_template: str,
    ) -> Dict[str, Any]:
        """
        Analyze content with a specific LLM.

        Args:
            content: Website content to analyze
            model_name: Name of the model
            prompt_template: Prompt template to use

        Returns:
            Analysis results as dictionary

        Raises:
            LLMError: If analysis fails
        """
        try:
            # Get appropriate LLM
            if model_name == "llama3:8b":
                llm = get_llama3_llm(temperature=0.7)
            elif model_name == "mistral:7b":
                llm = get_mistral_llm(temperature=0.7)
            elif model_name == "phi3:medium":
                llm = get_phi3_llm(temperature=0.7)
            else:
                raise LLMError(f"Unknown model: {model_name}")

            # Format prompt
            prompt = prompt_template.format(content=content)

            # Invoke LLM (OllamaLLM supports async via __call__ or invoke)
            self.log_step("llm_invoke", "running", f"Invoking {model_name}")
            # Use invoke for async compatibility
            if hasattr(llm, "ainvoke"):
                response = await llm.ainvoke(prompt)
            elif hasattr(llm, "invoke"):
                response = llm.invoke(prompt)
            else:
                response = await llm(prompt)

            # Parse JSON response with robust extraction
            response_text = response if isinstance(response, str) else str(response)

            # Log raw response for debugging (truncated)
            logger.debug(
                "LLM raw response",
                model=model_name,
                response_length=len(response_text),
                response_preview=response_text[:500] if len(response_text) > 500 else response_text,
            )

            try:
                result = extract_and_parse_json(response_text, model_name)
            except LLMError as e:
                # Log full response for debugging (truncated to 2000 chars)
                logger.error(
                    "JSON parsing failed",
                    model=model_name,
                    error=str(e),
                    response_preview=response_text[:2000] if len(response_text) > 2000 else response_text,
                )
                raise

            self.log_step("llm_invoke", "completed", f"{model_name} analysis complete")
            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response", model=model_name, error=str(e))
            raise LLMError(f"Failed to parse {model_name} response: {e}") from e
        except Exception as e:
            logger.error("LLM analysis failed", model=model_name, error=str(e))
            raise LLMError(f"{model_name} analysis failed: {e}") from e

    async def synthesize_analyses(
        self,
        llama3_result: Dict[str, Any],
        mistral_result: Dict[str, Any],
        phi3_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Synthesize multiple LLM analyses into unified profile.

        Args:
            llama3_result: Llama3 analysis results
            mistral_result: Mistral analysis results
            phi3_result: Phi3 analysis results

        Returns:
            Synthesized editorial profile

        Raises:
            LLMError: If synthesis fails
        """
        try:
            # Use Llama3 for synthesis (best for complex reasoning)
            llm = get_llama3_llm(temperature=0.5)  # Lower temperature for more consistent synthesis

            # Format prompt
            prompt = EDITORIAL_SYNTHESIS_PROMPT.format(
                llama3_analysis=json.dumps(llama3_result, indent=2),
                mistral_analysis=json.dumps(mistral_result, indent=2),
                phi3_analysis=json.dumps(phi3_result, indent=2),
            )

            # Invoke LLM
            self.log_step("synthesis", "running", "Synthesizing analyses")
            # Use invoke for async compatibility
            if hasattr(llm, "ainvoke"):
                response = await llm.ainvoke(prompt)
            elif hasattr(llm, "invoke"):
                response = llm.invoke(prompt)
            else:
                response = await llm(prompt)

            # Parse JSON response with robust extraction
            response_text = response if isinstance(response, str) else str(response)

            # Log raw response for debugging (truncated)
            logger.debug(
                "LLM synthesis raw response",
                response_length=len(response_text),
                response_preview=response_text[:500] if len(response_text) > 500 else response_text,
            )

            try:
                synthesized = extract_and_parse_json(response_text, "llama3:8b (synthesis)")
            except LLMError as e:
                # Log full response for debugging
                logger.error(
                    "Synthesis JSON parsing failed",
                    error=str(e),
                    response_preview=response_text[:2000] if len(response_text) > 2000 else response_text,
                )
                # Fallback to manual merge
                logger.warning("Falling back to manual merge due to JSON parsing failure")
                return self._manual_merge(llama3_result, mistral_result, phi3_result)

            self.log_step("synthesis", "completed", "Synthesis complete")
            return synthesized

        except json.JSONDecodeError as e:
            logger.error("Failed to parse synthesis JSON response", error=str(e))
            # Fallback: manually merge results
            return self._manual_merge(llama3_result, mistral_result, phi3_result)
        except Exception as e:
            logger.error("Synthesis failed", error=str(e))
            # Fallback: manually merge results
            return self._manual_merge(llama3_result, mistral_result, phi3_result)

    def _manual_merge(
        self,
        llama3_result: Dict[str, Any],
        mistral_result: Dict[str, Any],
        phi3_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Manually merge LLM results as fallback.

        Args:
            llama3_result: Llama3 analysis results
            mistral_result: Mistral analysis results
            phi3_result: Phi3 analysis results

        Returns:
            Merged editorial profile
        """
        return {
            "language_level": llama3_result.get("language_level", "intermediate"),
            "editorial_tone": llama3_result.get("editorial_tone", "professional"),
            "target_audience": llama3_result.get("target_audience", {}),
            "activity_domains": llama3_result.get("activity_domains", {}),
            "content_structure": mistral_result.get("content_structure", {}),
            "keywords": phi3_result.get("keywords", {}),
            "style_features": llama3_result.get("style_features", {}),
        }

    async def execute(
        self,
        execution_id: Any,
        input_data: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute editorial analysis workflow.

        Args:
            execution_id: Execution ID (UUID)
            input_data: Input data containing 'content' (combined text from pages)
            **kwargs: Additional arguments

        Returns:
            Complete editorial profile
        """
        content = input_data.get("content", "")
        if not content:
            raise ValueError("Content is required for editorial analysis")

        self.log_step("analysis_start", "running", "Starting multi-LLM analysis")

        # Run analyses in parallel (if possible) or sequentially
        try:
            # Analyze with Llama3
            llama3_result = await self.analyze_with_llm(
                content,
                "llama3:8b",
                EDITORIAL_ANALYSIS_PROMPT_LLAMA3,
            )

            # Analyze with Mistral
            mistral_result = await self.analyze_with_llm(
                content,
                "mistral:7b",
                EDITORIAL_ANALYSIS_PROMPT_MISTRAL,
            )

            # Analyze with Phi3
            phi3_result = await self.analyze_with_llm(
                content,
                "phi3:medium",
                EDITORIAL_ANALYSIS_PROMPT_PHI3,
            )

            # Synthesize results
            synthesized = await self.synthesize_analyses(llama3_result, mistral_result, phi3_result)

            # Add metadata
            synthesized["llm_models_used"] = {
                "llama3:8b": True,
                "mistral:7b": True,
                "phi3:medium": True,
            }
            synthesized["individual_analyses"] = {
                "llama3": llama3_result,
                "mistral": mistral_result,
                "phi3": phi3_result,
            }

            self.log_step("analysis_complete", "completed", "Multi-LLM analysis complete")
            return synthesized

        except Exception as e:
            self.log_step("analysis_failed", "failed", f"Analysis failed: {e}")
            raise

