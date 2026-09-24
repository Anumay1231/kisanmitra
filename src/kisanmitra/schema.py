from typing import List, Literal

from pydantic import BaseModel, Field


class AdviceCard(BaseModel):
    """Structured summary of an agent answer, used by the UI and the evaluation harness."""
    recommendation: str = Field(description="The main advice, at most 60 words")
    key_figures: List[str] = Field(default_factory=list,
                                   description="Exact figures used, e.g. 'EMI Rs 8,611/month', 'price Rs 8,50,000'")
    tools_used: List[str] = Field(default_factory=list, description="Names of the tools that produced those figures")
    data_gaps: str = Field(default="", description="Anything unavailable (failed tool, missing key), else empty")
    confidence: Literal["high", "medium", "low"] = Field(description="high if every figure came from a tool")
