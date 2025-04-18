from typing import Dict, Optional

from langchain_core.runnables import Runnable, RunnableConfig


class TimelineAgent(Runnable):
    def __init__(self, llm, verbose_setting):
        self.llm = llm
        self.verbose_setting = verbose_setting

    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        verbose = state.get("verbose", self.verbose_setting)
        if verbose:
            print(f"\n[DEBUG - TimelineAgent] Processing forms: {state.get('forms', [])}")

        if not state.get("forms"):
            if verbose:
                print(f"[DEBUG - TimelineAgent] No forms found, skipping")
            return {}

        timeline_info = [f"{form}: 3–6 months processing" for form in state.get("forms", [])]

        if verbose:
            print(f"[DEBUG - TimelineAgent] Generated timeline info: {timeline_info}")

        # Update history
        history = state.get("history", [])
        history.append({
            "agent": "TimelineAgent",
            "generated_timelines": len(timeline_info)
        })

        return {
            "timeline": timeline_info,
            "history": history
        }

    def route_after_timeline(self, state: Dict) -> str:
        if state.get("verbose", self.verbose):
            print(f"[📆 Timeline Routing] → Generation Stage: {state.get('generation_stage')}")
        return "ReasoningAgent" if state.get("generation_stage") == "initial" else END