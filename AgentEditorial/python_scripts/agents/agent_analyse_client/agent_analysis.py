"""Editorial analysis agent with multi-LLM orchestration."""

import json
import re
from typing import Any, Dict, List, Optional

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
    
    # Fix unquoted property names (e.g., { key: value } -> { "key": value })
    # This handles cases where keys are not quoted at all
    json_text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_text)
    
    # Fix escaped quotes in strings (sometimes LLMs double-escape)
    # But be careful not to break valid escaped quotes
    # Only fix if we see \\" which suggests double-escaping
    json_text = re.sub(r'\\\\"', '\\"', json_text)
    
    # Remove comments (JSON doesn't support comments)
    json_text = re.sub(r'//.*?$', '', json_text, flags=re.MULTILINE)
    json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
    
    # Fix trailing commas in objects and arrays (more comprehensive)
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)

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
        llama3_result: Optional[Dict[str, Any]],
        mistral_result: Optional[Dict[str, Any]],
        phi3_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Synthesize multiple LLM analyses into unified profile.
        Now handles None results gracefully.

        Args:
            llama3_result: Llama3 analysis results (can be None)
            mistral_result: Mistral analysis results (can be None)
            phi3_result: Phi3 analysis results (can be None)

        Returns:
            Synthesized editorial profile

        Raises:
            LLMError: If synthesis fails and no valid results available
        """
        # Filter out None results
        valid_results = []
        if llama3_result:
            valid_results.append(("llama3", llama3_result))
        if mistral_result:
            valid_results.append(("mistral", mistral_result))
        if phi3_result:
            valid_results.append(("phi3", phi3_result))
        
        if not valid_results:
            raise ValueError("No valid LLM results to synthesize")
        
        # If only one result, return it directly (no need for synthesis)
        if len(valid_results) == 1:
            logger.warning(
                "Only one LLM result available, using it directly",
                model=valid_results[0][0],
            )
            return valid_results[0][1]
        
        try:
            # Use Llama3 for synthesis (best for complex reasoning)
            llm = get_llama3_llm(temperature=0.5)  # Lower temperature for more consistent synthesis

            # Format prompt with available results
            prompt = EDITORIAL_SYNTHESIS_PROMPT.format(
                llama3_analysis=json.dumps(llama3_result, indent=2) if llama3_result else "{}",
                mistral_analysis=json.dumps(mistral_result, indent=2) if mistral_result else "{}",
                phi3_analysis=json.dumps(phi3_result, indent=2) if phi3_result else "{}",
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
        llama3_result: Optional[Dict[str, Any]],
        mistral_result: Optional[Dict[str, Any]],
        phi3_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Manually merge LLM results as fallback.
        Now handles None results gracefully.

        Args:
            llama3_result: Llama3 analysis results (can be None)
            mistral_result: Mistral analysis results (can be None)
            phi3_result: Phi3 analysis results (contains detailed activity_domains, can be None)

        Returns:
            Merged editorial profile
        """
        # Use phi3's activity_domains as they are more detailed
        activity_domains = phi3_result.get("activity_domains", {}) if phi3_result else {}
        # Fallback to llama3 if phi3 doesn't have activity_domains
        if not activity_domains and llama3_result:
            activity_domains = llama3_result.get("activity_domains", {})
        
        return {
            "language_level": (llama3_result or {}).get("language_level", "intermediate"),
            "editorial_tone": (llama3_result or {}).get("editorial_tone", "professional"),
            "target_audience": (llama3_result or {}).get("target_audience", {}),
            "activity_domains": activity_domains,  # Use phi3's detailed domains
            "content_structure": (mistral_result or {}).get("content_structure", {}),
            "keywords": (phi3_result or {}).get("keywords", {}),
            "style_features": (llama3_result or {}).get("style_features", {}),
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
            input_data: Input data containing 'content' (combined text from pages) - required
            **kwargs: Additional arguments (reserved for future use)

        Returns:
            Complete editorial profile as dictionary
        """
        content = input_data.get("content", "")
        if not content:
            raise ValueError("Content is required for editorial analysis")

        self.log_step("analysis_start", "running", "Starting multi-LLM analysis")

        # Run analyses with error tolerance - continue even if one fails
        results = {}
        errors = {}
        
        # Analyze with Llama3
        try:
            llama3_result = await self.analyze_with_llm(
                content,
                "llama3:8b",
                EDITORIAL_ANALYSIS_PROMPT_LLAMA3,
            )
            results["llama3:8b"] = llama3_result
        except Exception as e:
            logger.warning(
                "Llama3 analysis failed, continuing with other models",
                error=str(e),
                execution_id=str(execution_id),
            )
            errors["llama3:8b"] = str(e)
            results["llama3:8b"] = None

        # Analyze with Mistral
        try:
            mistral_result = await self.analyze_with_llm(
                content,
                "mistral:7b",
                EDITORIAL_ANALYSIS_PROMPT_MISTRAL,
            )
            results["mistral:7b"] = mistral_result
        except Exception as e:
            logger.warning(
                "Mistral analysis failed, continuing with other models",
                error=str(e),
                execution_id=str(execution_id),
            )
            errors["mistral:7b"] = str(e)
            results["mistral:7b"] = None

        # Analyze with Phi3
        try:
            phi3_result = await self.analyze_with_llm(
                content,
                "phi3:medium",
                EDITORIAL_ANALYSIS_PROMPT_PHI3,
            )
            results["phi3:medium"] = phi3_result
        except Exception as e:
            logger.warning(
                "Phi3 analysis failed, continuing with other models",
                error=str(e),
                execution_id=str(execution_id),
            )
            errors["phi3:medium"] = str(e)
            results["phi3:medium"] = None

        # Check if we have at least one successful result
        successful_results = {k: v for k, v in results.items() if v is not None}
        if not successful_results:
            error_msg = "All LLM analyses failed. No results available."
            logger.error(error_msg, errors=errors, execution_id=str(execution_id))
            self.log_step("analysis_failed", "failed", error_msg)
            raise LLMError(error_msg)

        # Synthesize results (handle missing models)
        synthesized = await self.synthesize_analyses(
            results.get("llama3:8b"),
            results.get("mistral:7b"),
            results.get("phi3:medium"),
        )

        # Add metadata
        synthesized["llm_models_used"] = {
            "llama3:8b": results.get("llama3:8b") is not None,
            "mistral:7b": results.get("mistral:7b") is not None,
            "phi3:medium": results.get("phi3:medium") is not None,
        }
        
        # Only include successful analyses in individual_analyses
        individual_analyses = {}
        if results.get("llama3:8b"):
            individual_analyses["llama3"] = results["llama3:8b"]
        if results.get("mistral:7b"):
            individual_analyses["mistral"] = results["mistral:7b"]
        if results.get("phi3:medium"):
            individual_analyses["phi3"] = results["phi3:medium"]
        synthesized["individual_analyses"] = individual_analyses
        
        # Add error information if any
        if errors:
            synthesized["llm_errors"] = errors
            synthesized["partial_analysis"] = True
            logger.warning(
                "Partial analysis completed",
                successful_models=list(successful_results.keys()),
                failed_models=list(errors.keys()),
                execution_id=str(execution_id),
            )

        self.log_step("analysis_complete", "completed", "Multi-LLM analysis complete")
        return synthesized




