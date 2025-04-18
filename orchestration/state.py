from typing import TypedDict, Literal, Optional, List, Dict


class AgentState(TypedDict):
    """Definition of the state shared between agents."""
    question: str
    relevance: Literal["relevant", "irrelevant", "unknown"]
    generation_stage: Literal["initial", "final"]
    initial_response: Optional[str]
    legislation: Optional[List[str]]
    forms: Optional[List[str]]
    timeline: Optional[List[str]]
    final_response: Optional[str]
    verbose: bool
    history: List[Dict]  # Session history for memory