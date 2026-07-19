"""RAGAS evaluation suite for the AthleteCare RAG pipeline.

Uses only local models (Llama.cpp + HuggingFace embeddings) – no OpenAI.

Run:
    pytest tests/test_ragas_eval.py -v -s

The test is automatically skipped when the GGUF model file is not present.
"""

from __future__ import annotations

import pytest
from datasets import Dataset
from langchain_community.llms import LlamaCpp
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import answer_relevancy, faithfulness

from app.config import (
    EMBED_MODEL_NAME,
    LLAMA_CHAT_FORMAT,
    LLAMA_MAX_TOKENS,
    LLAMA_N_CTX,
    LLAMA_N_GPU_LAYERS,
    LLAMA_N_THREADS,
    LLAMA_TEMPERATURE,
    LLAMA_VERBOSE,
    MODEL_PATH,
)

# ---------------------------------------------------------------------------
# Synthetic evaluation dataset
# ---------------------------------------------------------------------------
SYNTHETIC_DATASET = {
    "question": [
        "What is the recommended return-to-play timeline for a Grade II hamstring strain?",
        "How should a lateral ankle sprain be managed in the first 72 hours?",
    ],
    "ground_truth": [
        "Grade II hamstring strains typically require 18-28 days return-to-play with early eccentric loading and phased progression.",
        "Initial management includes RICE protocol, early protected mobilisation from day 3, and proprioceptive exercises.",
    ],
    "contexts": [
        [
            "Grade II hamstring strain: partial tear with moderate pain. "
            "Return-to-play criteria include full ROM, isokinetic strength ≥ 90%, "
            "and pain-free sprinting. Club average: 18-28 days with early eccentric loading."
        ],
        [
            "Lateral ankle sprain Grade II ATFL partial tear. "
            "Day 0: RICE, ankle brace. Day 3: early mobilisation and proprioception. "
            "Club average return-to-play: 28 days vs 35 days for standard care."
        ],
    ],
    "answer": [
        "Based on club protocols, Grade II hamstring strains average 18-28 days return-to-play "
        "when early eccentric loading (Nordic exercises) is initiated in the sub-acute phase.",
        "For a lateral ankle sprain, apply RICE in the first 72 hours, then begin early "
        "protected mobilisation and proprioceptive training from day 3 to accelerate recovery.",
    ],
}


def _build_local_llm() -> LangchainLLMWrapper:
    """Wrap the local LlamaCpp model for RAGAS evaluation."""
    llm = LlamaCpp(
        model_path=str(MODEL_PATH),
        chat_format=LLAMA_CHAT_FORMAT,
        n_ctx=LLAMA_N_CTX,
        n_threads=LLAMA_N_THREADS,
        n_gpu_layers=LLAMA_N_GPU_LAYERS,
        temperature=LLAMA_TEMPERATURE,
        max_tokens=LLAMA_MAX_TOKENS,
        verbose=LLAMA_VERBOSE,
        stop=["<|eot_id|>", "<|end_of_text|>"],
    )
    return LangchainLLMWrapper(llm)


def _build_local_embeddings() -> LangchainEmbeddingsWrapper:
    """Wrap HuggingFace embeddings for RAGAS evaluation."""
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )
    return LangchainEmbeddingsWrapper(embeddings)


@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason=f"Local GGUF model not found at {MODEL_PATH}. See models/README.md.",
)
def test_ragas_faithfulness_and_answer_relevancy():
    """
    Evaluate the RAG pipeline using RAGAS faithfulness and answer_relevancy metrics.

    Thresholds are set conservatively for local model quality; adjust as needed
    once a production-grade GGUF is in place.
    """
    dataset = Dataset.from_dict(SYNTHETIC_DATASET)
    llm = _build_local_llm()
    embeddings = _build_local_embeddings()

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )

    scores = result.to_pandas()

    print("\n--- RAGAS Evaluation Results ---")
    print(scores.to_string(index=False))
    print("--------------------------------")

    avg_faithfulness = scores["faithfulness"].mean()
    avg_relevancy = scores["answer_relevancy"].mean()

    assert avg_faithfulness >= 0.3, (
        f"Average faithfulness {avg_faithfulness:.3f} below threshold 0.3"
    )
    assert avg_relevancy >= 0.3, (
        f"Average answer_relevancy {avg_relevancy:.3f} below threshold 0.3"
    )


def test_synthetic_dataset_structure():
    """Sanity check: synthetic dataset has aligned columns."""
    n = len(SYNTHETIC_DATASET["question"])
    assert len(SYNTHETIC_DATASET["ground_truth"]) == n
    assert len(SYNTHETIC_DATASET["contexts"]) == n
    assert len(SYNTHETIC_DATASET["answer"]) == n
    assert all(len(ctx) > 0 for ctx in SYNTHETIC_DATASET["contexts"])
