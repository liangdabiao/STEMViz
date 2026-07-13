from abc import ABC, abstractmethod
import requests
import logging
import time
import json
import re
from typing import Optional, Dict, Any


class BaseAgent(ABC):
    """Base class for all AI agents using Doubao (Volcano Engine) API"""

    def __init__(self, api_key: str, base_url: str, model: str, reasoning_tokens: Optional[float] = None, reasoning_effort: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.reasoning_tokens = reasoning_tokens
        self.reasoning_effort = reasoning_effort
        self.logger = logging.getLogger(self.__class__.__name__)
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 1.0,
        max_retries: int = 3,
        json_mode: bool = False,
        max_tokens: int = 8192,
        timeout: int = 600,
    ) -> str:
        """Call LLM with retry logic and error handling using HTTPS API"""

        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                if self.reasoning_tokens is not None:
                    payload["reasoning"] = {"max_tokens": int(self.reasoning_tokens), "enabled": True}
                    
                if self.reasoning_effort is not None:
                    payload["reasoning"] = {"effort": self.reasoning_effort, "enabled": True}

                if json_mode:
                    payload["response_format"] = {"type": "json_object"}

                url = f"{self.base_url}/chat/completions"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                
                response.raise_for_status()
                response_data = response.json()

                if "usage" in response_data:
                    self.prompt_tokens += response_data["usage"].get("prompt_tokens", 0)
                    self.completion_tokens += response_data["usage"].get("completion_tokens", 0)
                    self.total_tokens += response_data["usage"].get("total_tokens", 0)

                content = response_data["choices"][0]["message"]["content"]
                self.logger.info(f"LLM call successful (attempt {attempt + 1})")

                return content

            except Exception as e:
                self.logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    # Check if it's a rate limit error (429)
                    is_rate_limit = False
                    if hasattr(e, 'response') and e.response is not None:
                        if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                            is_rate_limit = True
                    
                    # Longer backoff for rate limit errors
                    if is_rate_limit:
                        wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s...
                        self.logger.warning(f"Rate limited (429). Waiting {wait_time}s before retry...")
                    else:
                        wait_time = min(2**attempt * 5, 60)  # 5s, 20s, 60s max
                    
                    time.sleep(wait_time)
                else:
                    raise Exception(
                        f"LLM call failed after {max_retries} attempts: {e}"
                    )

    def _call_llm_structured(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 1.0,
        max_retries: int = 3,
        max_tokens: int = 32768,
        timeout: int = 600,
    ) -> Dict[Any, Any]:
        """Call LLM and return parsed JSON response"""

        response = self._call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_retries=max_retries,
            json_mode=True,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        # Sanitize JSON output before parsing
        sanitized_response = self._sanitize_json_output(response)

        try:
            return json.loads(sanitized_response)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            # Try to recover truncated JSON
            recovered = self._recover_truncated_json(sanitized_response)
            if recovered is not None:
                self.logger.info("Successfully recovered truncated JSON")
                return recovered
            raise ValueError(f"Invalid JSON response from LLM: {response[:200]}...")

    def _recover_truncated_json(self, json_str: str) -> Optional[Dict[Any, Any]]:
        """Try to recover a truncated JSON by closing open structures"""
        try:
            # Count open/close braces and brackets
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            open_brackets = json_str.count('[')
            close_brackets = json_str.count(']')

            # Remove trailing incomplete strings or values
            # Find the last complete structure
            fixed = json_str.rstrip()
            
            # If ends with a comma, remove it
            fixed = fixed.rstrip(',')
            
            # Remove incomplete last item (truncated string or number)
            # Find the last quote or colon that might indicate incomplete data
            last_comma = fixed.rfind(',')
            last_newline = fixed.rfind('\n')
            
            # Try to trim to the last complete item
            if last_comma > 0 and last_comma > len(fixed) - 100:
                fixed = fixed[:last_comma]
            
            # Close open brackets and braces
            while open_brackets > close_brackets:
                fixed += ']'
                close_brackets += 1
            while open_braces > close_braces:
                fixed += '}'
                close_braces += 1

            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # Second attempt: find the last complete JSON object
            # Try to find a valid JSON prefix
            for i in range(len(json_str), 100, -100):
                candidate = json_str[:i]
                # Count braces
                ob = candidate.count('{')
                cb = candidate.count('}')
                obr = candidate.count('[')
                cbr = candidate.count(']')
                # Close them
                candidate = candidate.rstrip().rstrip(',')
                while obr > cbr:
                    candidate += ']'
                    cbr += 1
                while ob > cb:
                    candidate += '}'
                    cb += 1
                try:
                    result = json.loads(candidate)
                    self.logger.info(f"Recovered JSON from {i} chars of {len(json_str)}")
                    return result
                except json.JSONDecodeError:
                    continue

        except Exception:
            pass
        
        return None

    def get_token_usage(self) -> Dict[str, int]:
        """Return token usage statistics"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def _sanitize_json_output(self, text: str) -> str:
        """Remove ```json ``` code blocks from LLM output"""
        # Remove ```json``` blocks
        sanitized = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        sanitized = re.sub(r'```\s*$', '', sanitized)
        return sanitized.strip()

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute the agent's main task - to be implemented by subclasses"""
        pass
