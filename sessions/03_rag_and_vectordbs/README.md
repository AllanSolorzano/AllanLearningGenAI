# Session 03 — RAG & Vector Databases

> "RAG is how you give an LLM access to your runbooks, internal wikis, and incident history
> without fine-tuning — and without hallucination."

---

## Learning Objectives

By the end of this session you will be able to:

1. **Explain the RAG architecture** — why retrieval beats fine-tuning for private knowledge
2. **Chunk documents effectively** — split strategies that maximise retrieval quality
3. **Build and query a vector store** — index documents in ChromaDB and search by meaning
4. **Build a full RAG pipeline** — retrieve → augment → generate, end-to-end
5. **Evaluate retrieval quality** — measure whether you're retrieving the right content
6. **Run everything locally** — Ollama + ChromaDB + sentence-transformers, zero cloud costs

---

## Prerequisites

- Sessions 01–02 complete (understand embeddings, context window, structured output)
- Python 3.10+, `pip install -r ../../requirements.txt`

**API Key:** Optional. All labs run fully offline with Ollama.  
If you have an `ANTHROPIC_API_KEY`, the labs will use Claude for generation. If not, they fall back to Ollama automatically.

---

## Local LLM Setup (Ollama)

Session 03 can run **entirely offline** using Ollama:

```bash
# 1. Install Ollama: https://ollama.com/download
# 2. Pull a model (choose one):
ollama pull llama3.2          # 2GB — good balance of speed and quality
ollama pull mistral           # 4GB — stronger reasoning
ollama pull qwen2.5:3b        # 2GB — fast, good for RAG

# 3. Verify it's running
ollama list
curl http://localhost:11434/api/tags
```

The utility module `utils/llm.py` auto-detects which backend to use.

---

## Estimated Time

| Activity | Time |
|----------|------|
| Read all concept files | 40 min |
| Lab 01 — Chunking Strategies | 20 min |
| Lab 02 — ChromaDB Vector Store | 25 min |
| Lab 03 — Full RAG Pipeline | 35 min |
| Lab 04 — Retrieval Evaluation | 25 min |
| Demos (all 3) | 20 min |
| **Total** | **~2.5 hours** |

---

## How to Work Through This Session

### Step 1 — Read concepts (in order)

```
concepts/
├── 01_rag_architecture.md       ← Start here — the big picture
├── 02_chunking.md
├── 03_vector_stores.md
├── 04_retrieval_evaluation.md
└── 05_local_llms.md             ← Ollama, when local beats cloud
```

### Step 2 — Run the labs

```bash
# Lab 01: Chunking
cd labs/lab01_chunking && python lab.py

# Lab 02: ChromaDB
cd labs/lab02_chromadb && python lab.py

# Lab 03: Full RAG pipeline (uses Ollama or Anthropic)
cd labs/lab03_rag_pipeline && python lab.py

# Lab 04: Evaluation
cd labs/lab04_evaluation && python lab.py
```

### Step 3 — Run the demos

```bash
cd demos

# Interactive runbook Q&A bot
python demo_runbook_bot.py

# Semantic + keyword hybrid search comparison
python demo_hybrid_search.py

# Fully offline RAG — no API key, no internet after setup
python demo_local_rag.py
```

---

## The RAG Pipeline at a Glance

```
INDEXING (done once):
  Documents → Chunk → Embed → Store in ChromaDB

QUERYING (done per request):
  User question
       ↓
  [Embed question]  →  query vector
       ↓
  [ChromaDB search]  →  top-k relevant chunks
       ↓
  [Build prompt: system + chunks + question]
       ↓
  [LLM generates answer]   ← Anthropic OR Ollama
       ↓
  Answer (grounded in your documents)
```
