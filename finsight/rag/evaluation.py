"""
RAGAS evaluation for FinSight RAG pipeline.
Uses Ollama (DeepSeek-R1:14b) as judge LLM — fully local, no API key needed.

Metrics:
  faithfulness      — does the answer contradict the context? (anti-hallucination)
  answer_relevancy  — does the answer address the question?
  context_precision — is the retrieved context on-topic?
"""
from finsight.config import OLLAMA_BASE_URL, OLLAMA_MODEL_PRIMARY


def run_ragas_evaluation(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str] | None = None,
    ollama_model: str | None = None,
) -> dict:
    """
    Run RAGAS evaluation on a set of Q&A pairs.

    Args:
        questions:      List of user questions.
        answers:        List of RAG-generated answers.
        contexts:       List of context lists (one list of strings per question).
        ground_truths:  Optional list of reference answers (improves recall metric).
        ollama_model:   Ollama model to use as judge (default: deepseek-r1:14b).

    Returns:
        {
            "faithfulness": float,
            "answer_relevancy": float,
            "context_precision": float,
            "per_question": [...],
            "error": str | None,
        }
    """
    model_name = ollama_model or OLLAMA_MODEL_PRIMARY

    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_community.llms import Ollama
        from langchain_community.embeddings import OllamaEmbeddings
        from datasets import Dataset
    except ImportError as e:
        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "per_question": [],
            "error": f"Missing dependency: {e}. Run: pip install ragas langchain-community datasets",
        }

    try:
        # Set up judge LLM (Ollama, local)
        llm = LangchainLLMWrapper(
            Ollama(model=model_name, base_url=OLLAMA_BASE_URL, temperature=0)
        )
        # Set up embeddings for answer_relevancy metric
        embeddings = LangchainEmbeddingsWrapper(
            OllamaEmbeddings(model=model_name, base_url=OLLAMA_BASE_URL)
        )

        data: dict = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        if ground_truths:
            data["ground_truth"] = ground_truths

        dataset = Dataset.from_dict(data)
        metrics = [faithfulness, answer_relevancy, context_precision]

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings,
            raise_exceptions=False,
        )

        df = result.to_pandas()
        per_question = df.to_dict(orient="records")

        return {
            "faithfulness": round(float(result["faithfulness"]), 4),
            "answer_relevancy": round(float(result["answer_relevancy"]), 4),
            "context_precision": round(float(result["context_precision"]), 4),
            "per_question": per_question,
            "error": None,
        }

    except Exception as e:
        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "per_question": [],
            "error": str(e)[:500],
        }
