
"""Local Ollama-based retrieval-augmented generation for PrepBuddy."""

import hashlib
import logging
import math
import threading
import time
import re
import requests
from django.conf import settings

from protocols.models import PrepProtocol

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"
OLLAMA_CHAT_MODEL = "qwen2.5:1.5b"

EMBED_TIMEOUT = 30
CHAT_TIMEOUT = 90
CACHE_TTL_SECONDS = 300
MIN_SIMILARITY = 0.25
MAX_CONTEXT_STEPS = 3

SAFE_FALLBACK = (
    "I couldn't confidently find an answer in the stored preparation "
    "instructions. Please check your official instructions or contact "
    "your clinical team."
)

# In-memory cache: useful for the current single-machine development setup.
# Each process maintains its own cache; no database schema changes are needed.
_embedding_cache = {}
_cache_lock = threading.Lock()

CLINICAL_ESCALATION_TERMS = {
    "medication", "medicine", "medicines", "tablet", "tablets",
    "pill", "pills", "insulin", "blood thinner",
    "allergy", "allergic", "side effect",
    "symptom", "symptoms", "pain", "bleeding", "vomiting",
    "pregnant", "pregnancy",
}

EXCEPTION_PHRASES = (
    "accidentally ate",
    "already ate",
    "accidentally drank",
    "already drank",
    "broke my fast",
    "missed a dose",
    "missed my instruction",
    "what if i",
    "what happens if",
    "is it safe for me",
)

def safety_response(question):
    """Return a safe response for questions requiring clinical review."""
    normalized = question.lower()

    if any(term in normalized for term in CLINICAL_ESCALATION_TERMS):
        return {
            "answer": (
                "I can't safely advise on medication changes or clinical "
                "symptoms. Please contact your procedure's clinical team "
                "for instructions specific to you."
            ),
            "sources": [],
            "needs_clinical_team": True,
        }

    if any(phrase in normalized for phrase in EXCEPTION_PHRASES):
        return {
            "answer": (
                "Your situation may need individual guidance. Please contact "
                "your clinical team before changing or continuing your "
                "preparation instructions."
            ),
            "sources": [],
            "needs_clinical_team": True,
        }

    return None

def _ollama_url(path):
    """Allow the local Ollama URL to be overridden through Django settings."""
    base_url = getattr(settings, "OLLAMA_BASE_URL", OLLAMA_BASE_URL)
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

def _embed_texts(texts):
    """Generate embeddings for one or more strings through Ollama."""
    if not texts:
        return []

    response = requests.post(
        _ollama_url("/api/embed"),
        json={"model": OLLAMA_EMBED_MODEL, "input": texts},
        timeout=EMBED_TIMEOUT,
    )
    response.raise_for_status()

    embeddings = response.json().get("embeddings", [])
    if len(embeddings) != len(texts):
        raise ValueError("Ollama returned an unexpected number of embeddings.")

    if any(not vector or not all(math.isfinite(x) for x in vector)
           for vector in embeddings):
        raise ValueError("Ollama returned an invalid embedding.")

    return embeddings

def _cosine_similarity(left, right):
    """Calculate cosine similarity without requiring NumPy."""
    if len(left) != len(right):
        return 0.0

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if not left_norm or not right_norm:
        return 0.0

    return sum(a * b for a, b in zip(left, right)) / (
        left_norm * right_norm
    )

def _load_knowledge():
    """Load usable steps and reuse embeddings until the source changes."""
    protocols = (
        PrepProtocol.objects
        .filter(is_active=True)
        .prefetch_related("steps")
        .order_by("name")
    )

    documents = []

    for protocol in protocols:
        for step in protocol.steps.all():
            instruction = (step.instruction or "").strip()

            if instruction.lower() in {"", ".", "-", "n/a"}:
                continue

            content = (
                f"Protocol ID: {protocol.pk}\n"
                f"Procedure: {protocol.name}\n"
                f"Protocol description: {protocol.description}\n"
                f"Step: {step.title}\n"
                f"Instruction: {instruction}"
            )

            documents.append({
                "protocol_id": protocol.pk,
                "content": content,
                "protocol": protocol.name,
                "step": step.title,
                "instruction": instruction,
                "minutes_before_procedure": step.minutes_before_procedure,
                "is_critical": step.is_critical,
            })

    fingerprint_source = "\n".join(
        document["content"] for document in documents
    )
    fingerprint = hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()

    now = time.monotonic()

    with _cache_lock:
        cached = _embedding_cache.get(fingerprint)

        if cached and now - cached["created_at"] < CACHE_TTL_SECONDS:
            return cached["documents"]

    if not documents:
        return []

    vectors = _embed_texts([document["content"] for document in documents])

    for document, vector in zip(documents, vectors):
        document["embedding"] = vector

    with _cache_lock:
        _embedding_cache.clear()
        _embedding_cache[fingerprint] = {
            "created_at": now,
            "documents": documents,
        }

    return documents

STOP_WORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were",
    "do", "does", "did", "can", "could", "would", "should",
    "i", "me", "my", "we", "you", "your", "it", "this",
    "that", "what", "when", "where", "how", "why",
    "to", "of", "for", "in", "on", "at", "before", "after",
    "about", "and", "or", "with", "from", "please",
    "tell", "explain", "stored", "instruction", "instructions",
    "procedure", "preparation", "prep",
}


def _has_keyword_overlap(question, document):
    """Check for meaningful shared word stems between question and step."""

    def keywords(text):
        words = re.findall(r"[a-z]+", text.lower())
        return {
            (
             word[:-3] if len(word) > 5 and word.endswith("ing")
             else word[:-1] if len(word) > 4 and word.endswith("s")
             else word
            )
            for word in words
            if word not in STOP_WORDS and len(word) > 2
        }

    question_words = keywords(question)
    document_words = keywords(
        f"{document.get('step', '')} "
        f"{document.get('instruction', '')}"
    )

    return len(question_words & document_words) >= 2

def _has_single_keyword_overlap(question, document):
    """Check whether at least one meaningful topic stem matches."""

    def keywords(text):
        words = re.findall(r"[a-z]+", text.lower())
        return {
            (
             word[:-3] if len(word) > 5 and word.endswith("ing")
             else word[:-1] if len(word) > 4 and word.endswith("s")
             else word
        )
            for word in words
            if word not in STOP_WORDS and len(word) > 2
        }

    question_words = keywords(question)
    document_words = keywords(
        f"{document.get('step', '')} "
        f"{document.get('instruction', '')}"
    )

    return bool(question_words & document_words)

def retrieve_steps(
    question,
    limit=MAX_CONTEXT_STEPS,
    protocol_id=None,
):
    """Retrieve relevant steps, optionally restricted to one protocol."""
    question = question.strip()
    if not question:
        return []

    # A contextual follow-up includes the earlier patient question.
    followup_match = re.search(
        r"Earlier patient question:\s*(.*?)\s*"
        r"Current patient follow-up:",
        question,
        flags=re.IGNORECASE | re.DOTALL,
    )

    documents = _load_knowledge()

    if protocol_id is not None:
        documents = [
            document
            for document in documents
            if document["protocol_id"] == protocol_id
        ]

    if not documents:
        return []

    question_embedding = _embed_texts([question])[0]
    ranked = []

    for document in documents:
        score = _cosine_similarity(
            question_embedding,
            document["embedding"],
        )

        if score < MIN_SIMILARITY:
            continue

        if followup_match:
            earlier_question = followup_match.group(1).strip()

            relevant = _has_keyword_overlap(earlier_question, document)

            if not relevant:
                words = re.findall(r"[a-z]+", earlier_question.lower())
                meaningful_words = [
                    word for word in words
                    if word not in STOP_WORDS and len(word) > 2
                ]

                relevant = (
                    len(meaningful_words) == 1
                    and _has_single_keyword_overlap(earlier_question, document)
                )
        else:
            relevant = _has_keyword_overlap(question, document)

        if relevant:
            ranked.append((score, document))

    ranked.sort(key=lambda item: item[0], reverse=True)

    return [
        {
            "protocol_id": document["protocol_id"],
            "protocol": document["protocol"],
            "step": document["step"],
            "instruction": document["instruction"],
            "minutes_before_procedure": (
                document["minutes_before_procedure"]
            ),
            "is_critical": document["is_critical"],
            "similarity": round(score, 4),
        }
        for score, document in ranked[:limit]
    ]

def answer_with_rag(question, protocol_id=None):
    """
    Retrieve relevant preparation steps and return their stored text.

    Deliberately avoids free-form LLM generation because unsupported
    medical details must not be added to the stored instructions.
    """
    escalation = safety_response(question)
    if escalation is not None:
        return escalation

    normalized = " ".join(question.lower().strip().split())

    general_help_phrases = {
        "hi",
        "hello",
        "hey",
        "hi prepbuddy",
        "hello prepbuddy",
        "hey prepbuddy",
        "what can you help me with",
        "what can you help me with?",
        "what can you do",
        "what do you do",
        "help",
        "help me",
    }

    if (
        normalized in general_help_phrases
        or "what can you help me with" in normalized
        or "what can you do" in normalized
        or "what do you do" in normalized
    ):
        return {
            "answer": (
                "Hello! I'm PrepBuddy, your preparation-instructions "
                "assistant. I can help you understand the preparation "
                "steps stored for your procedure and answer questions "
                "when those instructions contain a reliable answer. "
                "For medication questions, symptoms, or situations "
                "not covered by your instructions, please contact "
                "your clinical team."
            ),
            "sources": [],
            "needs_clinical_team": False,
        }

    try:
        sources = retrieve_steps(
            question,
            protocol_id=protocol_id,
        )

        if not sources:
            return {
                "answer": SAFE_FALLBACK,
                "sources": [],
                "needs_clinical_team": True,
            }

        # Return only the highest-ranked source. Do not let an LLM
        # invent timings, doses, or consequences.
        source = sources[0]

        answer = (
            f"Stored instruction ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â {source['step']}: "
            f"{source['instruction']}"
        )

        public_source = {
            "protocol": source["protocol"],
            "step": source["step"],
            "minutes_before_procedure": (
                source["minutes_before_procedure"]
            ),
            "is_critical": source["is_critical"],
        }

        return {
            "answer": answer,
            "sources": [public_source],
            "needs_clinical_team": False,
        }

    except (
        requests.RequestException,
        ConnectionError,
        ValueError,
        KeyError,
        TypeError,
    ):
        logger.exception("Local RAG retrieval failed.")
        return {
            "answer": SAFE_FALLBACK,
            "sources": [],
            "needs_clinical_team": True,
        }
