"""
Microsoft Foundry integration service.
Handles Azure AI Foundry / Azure OpenAI for agent intelligence.
"""
import logging
import random
from datetime import datetime
from typing import Optional, List

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MOCK_AI_RESPONSES = {
    "root_cause_analysis": [
        "Based on the log analysis and metrics correlation, the root cause is an N+1 query pattern in the ORM layer. The service is generating individual SQL queries for each related entity instead of using JOIN operations, causing CPU saturation and database connection exhaustion.",
        "The evidence strongly suggests a memory leak in the event listener registration. Objects are being retained in closure scope preventing garbage collection. This is a classic Node.js EventEmitter leak pattern.",
        "Analysis indicates a missing database index on the high-cardinality user_id column combined with a sudden 3x traffic spike. The query planner is performing full table scans on a 12M+ row table.",
    ],
    "fix_suggestion": [
        "Implement eager loading with Django's select_related() and prefetch_related() to batch related queries. Add Redis caching with 5-minute TTL for frequently accessed data.",
        "Add cleanup function in useEffect hook to remove event listeners on component unmount. Use WeakRef/WeakMap for cache implementations to allow garbage collection.",
        "Create a composite index on (user_id, created_at DESC) using CONCURRENTLY to avoid table locks. Update the query to leverage the index with proper WHERE clause ordering.",
    ],
}


class FoundryService:
    """Microsoft Foundry / Azure OpenAI integration for agent intelligence."""

    def __init__(self):
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.api_key = settings.AZURE_OPENAI_KEY
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self._simulation = settings.SIMULATION_MODE

    async def analyze_root_cause(self, incident_context: dict) -> dict:
        """Use Azure OpenAI to perform root cause analysis."""
        if self._simulation:
            return {
                "root_cause": random.choice(MOCK_AI_RESPONSES["root_cause_analysis"]),
                "confidence": round(random.uniform(0.80, 0.97), 2),
                "model": f"azure/{self.deployment}",
                "tokens_used": random.randint(800, 2400),
                "latency_ms": random.randint(800, 2000),
            }

        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version="2024-02-01",
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert SRE analyzing production incidents. "
                        "Analyze the provided metrics, logs and context to identify root cause. "
                        "Return a structured analysis with root_cause, severity, affected_services, and recommended_action."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Incident Context:\n{incident_context}",
                },
            ]

            response = client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.1,
                max_tokens=1000,
            )

            return {
                "root_cause": response.choices[0].message.content,
                "model": f"azure/{self.deployment}",
                "tokens_used": response.usage.total_tokens,
            }
        except Exception as e:
            logger.error(f"Foundry: Azure OpenAI call failed: {e}")
            return {
                "root_cause": random.choice(MOCK_AI_RESPONSES["root_cause_analysis"]),
                "confidence": 0.75,
                "error": str(e),
                "fallback": True,
            }

    async def generate_code_fix(self, diagnosis: dict, code_context: str) -> dict:
        """Use Azure OpenAI to generate a code fix."""
        if self._simulation:
            return {
                "fix_description": random.choice(MOCK_AI_RESPONSES["fix_suggestion"]),
                "confidence": round(random.uniform(0.78, 0.95), 2),
                "model": f"azure/{self.deployment}",
                "tokens_used": random.randint(1200, 3500),
            }

        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version="2024-02-01",
            )

            response = client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert software engineer. Generate a minimal, focused code fix for the given diagnosis.",
                    },
                    {
                        "role": "user",
                        "content": f"Diagnosis: {diagnosis}\n\nCode Context:\n{code_context}",
                    },
                ],
                temperature=0.2,
                max_tokens=2000,
            )

            return {
                "fix_description": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
            }
        except Exception as e:
            logger.error(f"Foundry: Code generation failed: {e}")
            return {"fix_description": random.choice(MOCK_AI_RESPONSES["fix_suggestion"]), "fallback": True}
