"""
Blog Writing Agent - Project Structure Guide

Project Structure:
==================
```bash
blog-writing-agent/
├── src/                          # Main source code
│   ├── __init__.py              # Package initialization
│   ├── config.py                # Configuration & LLM setup
│   │
│   ├── schemas/                 # Data models & schemas
│   │   └── __init__.py          # All Pydantic models (Task, Plan, State, etc.)
│   │
│   ├── prompts/                 # System prompts
│   │   └── __init__.py          # ROUTER_SYSTEM, RESEARCH_SYSTEM, ORCH_SYSTEM, WORKER_SYSTEM
│   │
│   ├── tools/                   # Utilities & tools
│   │   └── __init__.py          # tavily_search() function
│   │
│   ├── nodes/                   # Workflow nodes
│   │   ├── __init__.py          # Exports all node functions
│   │   ├── router.py            # Route: decides if research needed
│   │   ├── research.py          # Research node: performs web search
│   │   ├── orchestrator.py      # Orchestrator: creates blog plan
│   │   ├── workers.py           # Workers: generates individual sections (parallel)
│   │   └── reducer.py           # Reducer: combines sections into final blog
│   │
│   └── graph/                   # Graph assembly
│       ├── __init__.py          # Exports app
│       └── workflow.py          # build_graph() - LangGraph assembly
│
├── main.py                      # Entry point - run() function
├── 1_bwa_basic.ipynb           # Original notebook (for reference)
├── .env                         # Environment variables (API keys)
├── requirements.txt             # Python dependencies
└── README.md                    # Project documentation

```
Workflow Architecture:
======================

START
  ↓
[router_node]  → Decide: is web research needed?
  ↓
  ├─→ YES → [research_node] → Search web for evidence
  │            ↓
  │     [orchestrator] → Create blog plan from evidence
  │            ↓
  │           ...
  │
  └─→ NO → [orchestrator] → Create blog plan (no research)
                ↓
         [fanout] → Distribute tasks to workers
                ↓
         [workers] → Generate sections in parallel (one per task)
                ↓
         [reducer_node] → Combine sections into final blog
                ↓
              END


Key Components:
===============

1. SCHEMAS (src/schemas/__init__.py)
   - Task: Individual section/task with goal, bullets, word count
   - Plan: Complete blog outline with all tasks
   - State: Global workflow state (TypedDict)
   - RouterDecision: Router output (needs_research, mode, queries)
   - EvidenceItem: Research result

2. PROMPTS (src/prompts/__init__.py)
   - ROUTER_SYSTEM: Decides research needs
   - RESEARCH_SYSTEM: Synthesizes web results
   - ORCH_SYSTEM: Creates blog outline
   - WORKER_SYSTEM: Writes individual sections

3. NODES (src/nodes/)
   - router_node: Determines research needs
   - research_node: Executes web search via Tavily
   - orchestrator: Generates structured Plan via LLM
   - workers: Generates Markdown sections in parallel
   - reducer_node: Combines sections & saves to file

4. GRAPH (src/graph/workflow.py)
   - StateGraph: Define nodes and edges
   - Conditional edges: Route based on decisions
   - Fan-out pattern: Parallel section generation

5. CONFIG (src/config.py)
   - LLM initialization (ChatOpenAI or ChatGroq)
   - Environment variable loading


Running the Agent:
==================

Option 1: Python script
    python main.py

Option 2: Programmatic
    from main import run
    result = run("Your blog topic here")
    print(result["final"])


File Organization Principles:
==============================

✓ Separation of Concerns
  - Each node in separate file
  - Schemas in one place
  - Prompts grouped together
  - Config centralized

✓ Clear Dependencies
  - Imports show data flow
  - Easy to trace execution

✓ Scalability
  - Easy to add new nodes
  - Easy to add new prompts
  - Easy to add new tools

✓ Testability
  - Individual functions testable
  - Nodes are independent
  - State is immutable


Notes:
======
- All original code preserved
- No code removed or reduced
- Only reorganized into proper structure
- Follows real AI agent project patterns
"""
