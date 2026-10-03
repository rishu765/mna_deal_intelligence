"""Grounded RAG orchestration over retrieval, context, and generation."""

from __future__ import annotations

from ma_company_intelligence.domain import RAGAnswer, RetrievalFilters
from ma_company_intelligence.generation import GenerationRequest, Generator
from ma_company_intelligence.rag.context import ContextBuilder
from ma_company_intelligence.rag.errors import InvalidQuestionError
from ma_company_intelligence.rag.prompts import GROUNDING_INSTRUCTIONS, build_generation_input
from ma_company_intelligence.retrieval import Retriever

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I could not find sufficient evidence in the provided documents to answer this reliably."
)


class GroundedRAGService:
    """Retrieve evidence, construct bounded context, and generate one grounded answer."""

    def __init__(
        self,
        retriever: Retriever,
        context_builder: ContextBuilder,
        generator: Generator,
        *,
        max_output_tokens: int = 800,
    ) -> None:
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self._retriever = retriever
        self._context_builder = context_builder
        self._generator = generator
        self._max_output_tokens = max_output_tokens

    def answer(
        self,
        question: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RAGAnswer:
        """Return an answer constrained to the retrieved evidence prefix."""

        if not question.strip():
            raise InvalidQuestionError("question must contain non-whitespace text")
        if top_k <= 0:
            raise InvalidQuestionError("top_k must be positive")

        results = self._retriever.retrieve(question, top_k=top_k, filters=filters)
        if not results:
            return self._insufficient_answer(
                question,
                warning="Retrieval returned no evidence, so generation was skipped.",
            )

        context = self._context_builder.build(results)
        if not context.included_results:
            return self._insufficient_answer(
                question,
                warning=(
                    "No complete evidence chunk fit the configured context budget, "
                    "so generation was skipped."
                ),
            )

        warnings: list[str] = []
        if context.omitted_result_count:
            warnings.append(
                f"{context.omitted_result_count} retrieved result(s) were omitted by the "
                "context limits."
            )
        generated = self._generator.generate(
            GenerationRequest(
                instructions=GROUNDING_INSTRUCTIONS,
                input_text=build_generation_input(
                    question=question,
                    context=context.text,
                ),
                max_output_tokens=self._max_output_tokens,
            )
        )
        answer_text = generated.answer
        if generated.insufficient_evidence:
            answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
            warnings.append("The generator classified the supplied evidence as insufficient.")

        return RAGAnswer(
            question=question,
            answer=answer_text,
            supporting_results=context.included_results,
            insufficient_evidence=generated.insufficient_evidence,
            generator_provider=self._generator.provider_name,
            generator_model=self._generator.model_name,
            warnings=tuple(warnings),
        )

    def _insufficient_answer(self, question: str, *, warning: str) -> RAGAnswer:
        return RAGAnswer(
            question=question,
            answer=INSUFFICIENT_EVIDENCE_MESSAGE,
            supporting_results=(),
            insufficient_evidence=True,
            generator_provider=self._generator.provider_name,
            generator_model=self._generator.model_name,
            warnings=(warning,),
        )
