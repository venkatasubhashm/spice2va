import os
import time
from pydantic import BaseModel, Field
from google import genai
from .provider import LLMProvider

class VerilogAModelOutput(BaseModel):
    circuit_summary: str = Field(description="A brief summary of the circuit's purpose.")
    topology: str = Field(description="A description of the circuit topology.")
    equations: str = Field(description="The mathematical equations governing the behavior.")
    assumptions: str = Field(description="Any assumptions made during the translation.")
    verilog_a_code: str = Field(description="The complete, raw Verilog-A module code.")
    validation_plan: str = Field(description="How to validate the generated code.")
    expected_behavior: str = Field(description="The expected physical behavior of the model.")

class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str = "gemini-3.6-flash"):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        max_retries = 3
        backoff = 2
        
        for attempt in range(1, max_retries + 2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': schema,
                    },
                )
                return schema.model_validate_json(response.text)
            except Exception as e:
                error_str = str(e).upper()
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    # Do not retry quota issues
                    raise e
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    if attempt <= max_retries:
                        print(f"  -> Gemini temporarily unavailable; retrying ({attempt}/{max_retries})...")
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        raise e
                else:
                    raise e
