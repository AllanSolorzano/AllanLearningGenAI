# Session 04: Tool Calling (Function Calling)

Make LLMs reliably call functions so they can fetch live data, trigger actions, and work as practical agents.

## DevOps Analogy

| Tool Calling Concept            | DevOps Equivalent |
|--------------------------------|-------------------|
| Tool schema                     | API contract / OpenAPI spec |
| Model emits tool call           | Service decides to call downstream API |
| Your code executes the tool     | API gateway + backend handler |
| Tool result fed back to model   | Downstream response returned to orchestrator |
| Final assistant response        | Aggregated response to end user |

## What You'll Learn

- Define robust tool schemas with clear input contracts
- Build the canonical tool-calling loop (model -> tool -> model)
- Orchestrate multiple tool calls in one response cycle
- Validate/guard tool arguments and handle failures safely
- Run the same function-calling flow across:
  - OpenAI hosted models
  - Other OpenAI-compatible hosted models
  - Local models with Ollama OpenAI-compatible `/v1` API

## Prerequisites

```bash
# Install dependencies
pip install -r ../../requirements.txt

# Optional for local execution path
# https://ollama.com/download
ollama pull llama3.2
```

Environment setup:

```bash
cp ../../.env.example ../../.env
# then fill keys/models as needed
```

## Session Structure

```
04_tool_calling_function_calling/
├── concepts/
│   ├── 01_what_is_tool_calling.md
│   ├── 02_tool_schema_design.md
│   ├── 03_tool_loop_orchestration.md
│   ├── 04_provider_compatibility.md
│   └── 05_safety_validation_observability.md
├── labs/
│   ├── lab01_tool_schema_basics/
│   ├── lab02_single_tool_loop/
│   ├── lab03_multi_tool_orchestration/
│   └── lab04_provider_agnostic_loop/
└── demos/
    ├── demo_basic_function_call.py
    ├── demo_multi_tool_incident_agent.py
    └── demo_provider_switch.py
```

## Labs

| Lab | Topic | Key Concepts |
|-----|-------|-------------|
| lab01_tool_schema_basics | Write function schemas + local dispatcher | JSON schema, argument validation |
| lab02_single_tool_loop | One complete tool loop | tool choice auto, tool message round-trip |
| lab03_multi_tool_orchestration | Multiple calls + fallback handling | chained tool calls, error-aware prompting |
| lab04_provider_agnostic_loop | Same loop for OpenAI/compatible/Ollama | base URL switching, model portability |

## Demos

| Demo | What it shows |
|------|---------------|
| `demo_basic_function_call.py` | Minimal function call with one tool |
| `demo_multi_tool_incident_agent.py` | Incident assistant that combines two tools |
| `demo_provider_switch.py` | Run exact same code path against different providers |

## Quick Start

```bash
cd sessions/04_tool_calling_function_calling

# Read concepts first
cat concepts/01_what_is_tool_calling.md

# Run labs
python labs/lab01_tool_schema_basics/lab.py
python labs/lab02_single_tool_loop/lab.py
python labs/lab03_multi_tool_orchestration/lab.py
python labs/lab04_provider_agnostic_loop/lab.py

# Run demos
python demos/demo_basic_function_call.py
python demos/demo_multi_tool_incident_agent.py
python demos/demo_provider_switch.py
```

## Estimated Time

| Activity | Time |
|----------|------|
| Concepts | 35 min |
| 4 labs | 100 min |
| Demos | 20 min |
| **Total** | **~2.5 hours** |

