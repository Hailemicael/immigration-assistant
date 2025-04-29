from typing import Optional, Any, Dict

import asyncio
from googletrans import Translator  # Assuming async version
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END

from ..orchestration.state import AgentState
from ..relevance.agent import RelevanceAgent


class TranslatorAgent(Runnable):
    node = "TranslatorAgent"

    def __init__(self, default_lang: str = 'en', verbose: bool = False):
        """
        Initialize a translation agent with a specified default language.
        """
        self.default_lang = default_lang
        self.verbose = verbose
        self._last_action = None  # Tracks: "question_translated" or "response_translated"

    def _log(self, message: str):
        """
        Internal logging function that prints messages with a 🌍 emoji.
        """
        if self.verbose:
            print(f"[🌍 TranslatorAgent] {message}")

    async def _detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.
        """
        async with Translator() as translator:
            detection = await translator.detect(text)
            return detection.lang

    async def _translate(self, text: str, dest_lang: str) -> str:
        """
        Translate the input text into the destination language.
        """
        async with Translator() as translator:
            result = await translator.translate(text, dest=dest_lang)
            return result.text

    async def _invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        """
        Internal async method to handle translation logic.
        """
        question = state.get("question", "")
        initial_response = state.get("initial_response", "")
        verbose = state.get("verbose", self.verbose)

        # Reset last action
        self._last_action = None

        if not question:
            self._log("⚠️ No question found in state. Skipping translation.")
            return {}

        # Step 1: Detect language
        detected_lang = await self._detect_language(question)
        self._log(f"🧠 Detected language: {detected_lang}")

        history = state.get("history", [])

        # Step 2: Decide what needs translation
        if detected_lang != self.default_lang and not initial_response:
            # Translate the question
            self._log(f"🔤 Translating question from {detected_lang} to {self.default_lang}...")
            translated_question = await self._translate(question, self.default_lang)
            self._last_action = "question_translated"
            self._log(f"✅ Question translated: {translated_question}")

            history.append({
                "agent": TranslatorAgent.node,
                "action": "translate_question",
                "from_lang": detected_lang,
                "to_lang": self.default_lang,
                "original_question": question,
                "translated_question": translated_question
            })

            return {
                "detected_language": detected_lang,
                "question_translated": translated_question,
                "history": history
            }

        elif initial_response and detected_lang != self.default_lang:
            # Translate the initial response
            self._log(f"🔁 Translating initial response from {self.default_lang} to {detected_lang}...")
            translated_response = await self._translate(initial_response, detected_lang)
            self._last_action = "response_translated"
            self._log(f"✅ Final response translated: {translated_response}")

            history.append({
                "agent": TranslatorAgent.node,
                "action": "translate_response",
                "from_lang": self.default_lang,
                "to_lang": detected_lang,
                "original_response": initial_response,
                "translated_response": translated_response
            })

            return {
                "detected_language": detected_lang,
                "final_response": translated_response,
                "generation_stage": "final",
                "history": history
            }

        else:
            self._log("📝 No translation needed.")
            return {"detected_language": detected_lang}  # Always set detected language even if nothing is translated

    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        """
        Synchronously invoke the translation agent using asyncio.run().
        """
        return asyncio.run(self._invoke(state, config, **kwargs))

    def check_translation_needed(self, state: AgentState) -> str:
        if state.get('final_response') is not None or state.get('generation_stage') is 'final':
            self._log("🔁 Routing to END after translating response.")
            return END
        self._log("🔁 Routing to RelevanceAgent after translating question.")
        return RelevanceAgent.node
