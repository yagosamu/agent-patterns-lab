# Self-Healing RAG

A retrieval-augmented generation (RAG) system built with Python, ChromaDB, Groq, and LangGraph.

This project retrieves relevant document chunks from a local vector database, generates an answer with an LLM, grades whether the answer is grounded in the retrieved context, and automatically retries with a rewritten query when the answer is not reliable.

If the system still cannot find enough support after the retry limit, it returns an honest fallback response instead of hallucinating.

## Why This Project Matters

Basic RAG systems often retrieve documents and immediately pass them to an LLM, assuming the response will be correct.

This project adds a self-healing loop:
- retrieve relevant context
- generate an answer
- evaluate whether the answer is supported by the documents
- rewrite the question and retry if necessary
- give up honestly when the knowledge base does not contain the answer

This improves reliability and reduces unsupported answers.

## Project Flow

The system follows this workflow:

1. `retrieve`
Search the vector database for the most relevant document chunks based on the user question.

2. `generate`
Send the retrieved chunks and the question to the LLM to produce an answer grounded in the provided context.

3. `grade_answer`
Evaluate whether the generated answer is actually supported by the retrieved documents.

4. `rewrite_question`
If the answer fails the grading step, rewrite the question to improve retrieval on the next attempt.

5. `retry loop`
Run retrieval, generation, and grading again with the rewritten query.

6. `give_up`
If the retry limit is reached and the answer is still not grounded, return an honest fallback response.

## Architecture

This project is split into two main stages:

- `ingest.py`
Loads text documents, splits them into chunks, and stores them in ChromaDB.

- `rag_agent.py`
Runs the LangGraph workflow for retrieval, answer generation, grading, retry logic, and fallback handling.

## Core AI Engineering Concepts

This project demonstrates several important AI Engineering concepts:

- `RAG (Retrieval-Augmented Generation)`
Combining retrieval from an external knowledge base with LLM generation.

- `Chunking`
Splitting documents into smaller pieces for better retrieval quality and prompt efficiency.

- `Embeddings`
Vector representations of text used for semantic search.

- `Vector Database`
A database that stores embeddings and supports similarity-based retrieval.

- `Grounding`
Constraining the LLM to answer using retrieved documents instead of unsupported prior knowledge.

- `LLM-as-Judge`
Using an LLM to evaluate whether an answer is supported by the available evidence.

- `Query Rewriting`
Rephrasing a user question to improve retrieval performance.

- `Orchestration`
Managing a multi-step AI workflow with state, branching, and retries using LangGraph.

- `Fallback Handling`
Returning "I don't know" when the system cannot produce a reliable grounded answer.

## Tech Stack

- Python
- uv
- ChromaDB
- LangChain
- LangGraph
- Groq API
- Llama 3.3

## Example Failure Case

If the user asks a question that is not covered by the knowledge base, such as "What is the capital of France?", the system may still retrieve the closest available chunks, even if they are unrelated.

The generated answer is then graded against the retrieved context. If the answer is not supported, the system rewrites the query and retries. After the retry limit is reached, it returns an honest message indicating that it could not find a reliable answer in the available documents.

This behavior is intentional and helps prevent hallucinations.

## Future Improvements

Possible next steps for this project include:

- PDF ingestion
- source citations
- hybrid search
- reranking
- evaluation datasets
- observability and tracing
- web interface
- API deployment
