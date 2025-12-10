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


def extract_balanced_json(json_str: str, start_char: str) -> str:
    """
    Extract balanced JSON structure from a string.
    
    Args:
        json_str: JSON string (may be incomplete)
        start_char: Starting character ('[' for array, '{' for object)
        
    Returns:
        Balanced JSON string, or original if cannot balance
    """
    json_str = json_str.strip()
    
    open_char = start_char
    close_char = "]" if start_char == "[" else "}"
    
    count = 0
    in_string = False
    escape_next = False
    result = []
    
    for char in json_str:
        result.append(char)
        
        if escape_next:
            escape_next = False
            continue
        
        if char == "\\":
            escape_next = True
            continue
        
        if char == '"':
            in_string = not in_string
            continue
        
        if not in_string:
            if char == open_char:
                count += 1
            elif char == close_char:
                count -= 1
                if count == 0:
                    return "".join(result)
    
    # If not balanced, return as-is
    return json_str


def extract_partial_json(json_text: str, model_name: str) -> Dict[str, Any]:
    """
    Extract valid JSON parts even if full JSON is invalid.
    Now properly handles nested objects and arrays.

    Args:
        json_text: Invalid JSON string
        model_name: Name of the model (for logging)

    Returns:
        Dictionary with extracted valid parts

    Raises:
        LLMError: If no valid parts can be extracted
    """
    result = {}

    # Find all top-level key-value pairs with proper nesting handling
    i = 0
    while i < len(json_text):
        # Find a key (quoted string followed by :)
        key_match = re.search(r'"([^"]+)"\s*:', json_text[i:])
        if not key_match:
            break
        
        key = key_match.group(1)
        value_start = i + key_match.end()
        
        # Skip whitespace
        while value_start < len(json_text) and json_text[value_start] in ' \t\n\r':
            value_start += 1
        
        if value_start >= len(json_text):
            break
        
        value_char = json_text[value_start]
        
        # Handle different value types
        if value_char == '{':
            # Extract balanced object
            balanced = extract_balanced_json(json_text[value_start:], '{')
            try:
                result[key] = json.loads(balanced)
            except json.JSONDecodeError:
                # Try to fix common issues
                fixed = fix_json_common_issues(balanced)
                try:
                    result[key] = json.loads(fixed)
                except json.JSONDecodeError:
                    logger.warning("Could not parse JSON object value", key=key, value_preview=balanced[:50])
            i = value_start + len(balanced)
            
        elif value_char == '[':
            # Extract balanced array
            balanced = extract_balanced_json(json_text[value_start:], '[')
            try:
                result[key] = json.loads(balanced)
            except json.JSONDecodeError:
                fixed = fix_json_common_issues(balanced)
                try:
                    result[key] = json.loads(fixed)
                except json.JSONDecodeError:
                    logger.warning("Could not parse JSON array value", key=key, value_preview=balanced[:50])
            i = value_start + len(balanced)
            
        elif value_char == '"':
            # Extract string value
            string_end = value_start + 1
            escape_next = False
            while string_end < len(json_text):
                if escape_next:
                    escape_next = False
                    string_end += 1
                    continue
                if json_text[string_end] == '\\':
                    escape_next = True
                    string_end += 1
                    continue
                if json_text[string_end] == '"':
                    string_end += 1
                    break
                string_end += 1
            
            try:
                result[key] = json.loads(json_text[value_start:string_end])
            except json.JSONDecodeError:
                result[key] = json_text[value_start+1:string_end-1]
            i = string_end
            
        else:
            # Primitive value (number, boolean, null)
            value_end = value_start
            while value_end < len(json_text) and json_text[value_end] not in ',}]\n':
                value_end += 1
            
            value = json_text[value_start:value_end].strip()
            
            if value.lower() == 'true':
                result[key] = True
            elif value.lower() == 'false':
                result[key] = False
            elif value.lower() == 'null':
                result[key] = None
            else:
                try:
                    if '.' in value:
                        result[key] = float(value)
                    else:
                        result[key] = int(value)
                except ValueError:
                    result[key] = value
            
            i = value_end
        
        # Move past any separator
        while i < len(json_text) and json_text[i] in ',\n\r\t ':
            i += 1

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


def normalize_json_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and validate JSON data from LLM responses.
    
    Ensures that:
    - String values that are JSON are parsed
    - Expected dict/list structures are properly formatted
    - Invalid data is cleaned or removed
    
    Args:
        data: Raw data dictionary from LLM
        
    Returns:
        Normalized data dictionary
    """
    normalized = {}
    
    for key, value in data.items():
        if value is None:
            normalized[key] = None
        elif isinstance(value, str):
            # Try to parse if it looks like JSON
            value_stripped = value.strip()
            if value_stripped.startswith(("{", "[")):
                try:
                    parsed = json.loads(value_stripped)
                    normalized[key] = normalize_json_data(parsed) if isinstance(parsed, dict) else parsed
                except (json.JSONDecodeError, ValueError):
                    # If parsing fails, keep as string but log warning
                    logger.warning(
                        "Could not parse JSON string value",
                        key=key,
                        value_preview=value[:100],
                    )
                    normalized[key] = value
            else:
                normalized[key] = value
        elif isinstance(value, dict):
            # Recursively normalize nested dicts
            normalized[key] = normalize_json_data(value)
        elif isinstance(value, list):
            # Normalize list items
            normalized[key] = [
                normalize_json_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            normalized[key] = value
    
    return normalized


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
                # Normalize the result to ensure proper JSON structure
                result = normalize_json_data(result)
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
                # Normalize the synthesized result to ensure proper JSON structure
                synthesized = normalize_json_data(synthesized)
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
            phi3_result: Phi3 analysis results (contains detailed activity_domains)

        Returns:
            Merged editorial profile
        """
        # Use phi3's activity_domains as they are more detailed
        activity_domains = phi3_result.get("activity_domains", {})
        # Fallback to llama3 if phi3 doesn't have activity_domains
        if not activity_domains:
            activity_domains = llama3_result.get("activity_domains", {})
        
        return {
            "language_level": llama3_result.get("language_level", "intermediate"),
            "editorial_tone": llama3_result.get("editorial_tone", "professional"),
            "target_audience": llama3_result.get("target_audience", {}),
            "activity_domains": activity_domains,  # Use phi3's detailed domains
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




