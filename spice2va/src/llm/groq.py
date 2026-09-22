import os
import time
import json
from pydantic import BaseModel
from groq import Groq, APIStatusError, APIConnectionError, RateLimitError, BadRequestError, AuthenticationError
from .provider import LLMProvider

class GroqProvider(LLMProvider):
    def __init__(self, model_name: str = "openai/gpt-oss-120b"):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")
        self.client = Groq(api_key=api_key)
        self.model_name = model_name

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        max_retries = 3
        backoff = 2
        
        # Append schema requirements to prompt for standard json_object mode
        schema_json = schema.model_json_schema()
        full_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: You MUST return ONLY valid JSON that perfectly adheres to the following JSON Schema.\n"
            f"Schema:\n{json.dumps(schema_json, indent=2)}\n"
        )
        
        for attempt in range(1, max_retries + 2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that always returns perfectly formatted JSON."},
                        {"role": "user", "content": full_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                
                content = response.choices[0].message.content
                return schema.model_validate_json(content)
                
            except RateLimitError as e:
                # 429 Rate Limit
                raise Exception(f"Groq Quota/Rate-limit exhausted (429): {e}")
            except AuthenticationError as e:
                # 401/403 Auth
                raise Exception(f"Groq Authentication error (401/403): {e}")
            except BadRequestError as e:
                # 400 Bad Request
                raise Exception(f"Groq Bad Request (400): {e}")
            except (APIStatusError, APIConnectionError) as e:
                # 5xx or connection issues
                if isinstance(e, APIStatusError) and not (500 <= e.status_code < 600):
                    # If it's an APIStatusError but not a 5xx, raise it
                    raise e
                    
                if attempt <= max_retries:
                    print(f"  -> Groq temporarily unavailable (5xx); retrying ({attempt}/{max_retries})...")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise e
            except Exception as e:
                raise e
