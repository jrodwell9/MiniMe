Our requirements for granular control, local execution, and a self-evolving feedback loop point toward one clear choice: **LangGraph** (within the LangChain ecosystem).

While frameworks like CrewAI are excellent for rapid role-based deployment, they often abstract away the state management and "time-travel" debugging features you need to build a system that evolves based on human feedback.

---

## 1. The Framework: LangGraph

LangGraph is a low-level orchestration framework designed for building stateful, multi-agent systems. It treats every agent interaction as a **node** in a graph, with **edges** defining the logic flow.

### Why LangGraph fits your specs:

* **Granular Traceability:** Unlike sequential "black box" frameworks, LangGraph allows us to inspect the full state at every node. By pairing it with **LangSmith** (or an open-source local alternative like **Arize Phoenix**), we can see the exact prompt, token usage, and tool output for every step.
* **Self-Evolving Prompts:** We can implement a "Meta-Agent" node. This agent's job is to read user feedback, analyze past failures in the traces, and update the "System Prompt" stored in your long-term memory.
* **Human-in-the-loop (HITL):** LangGraph has native support for **Breakpoints**. The system can pause before executing a GitHub commit or a shopping purchase, allowing you to provide feedback that is then saved to the state.

---

## 2. Local Stack & Hardware Optimization

Running this on **12-24GB RAM** requires strategic model selection. We cannot run multiple massive models simultaneously, but we can swap them or use efficient quantized versions via Ollama.

### Recommended Local Stack:

* **Model Provider:** [Ollama](https://ollama.com/) (Service mode).
* **Primary Coding Model:** `deepseek-coder-v2:16b` (fits in 24GB at 4-bit quantization) or `llama3.1:8b`.
* **Orchestrator/Admin Model:** `mistral:7b` or `phi3:medium` (highly efficient for simple logic/routing).
* **Database:** **PostgreSQL** (running locally in Docker). Use this as the "Checkpointer" for LangGraph to ensure our agents "remember" where they left off even after a reboot.

---

## 3. Implementation Strategy: Memory & Evolution

To achieve the "constantly evolving" goal, we should utilize LangGraph's dual-layer memory system:

### A. Short-Term (Session) Memory

Use a **Checkpointer** (`SqliteSaver` or `PostgresSaver`). This tracks the "Thread ID." If an agent is halfway through a complex refactor on GitHub and your power cuts out, it resumes exactly at that node with the same local variables.

### B. Long-Term (Evolutionary) Memory

Use a **Store** (e.g., `PostgresStore`). This is where we store:

1. **User Preferences:** "I prefer Python type hints in all files."
2. **Optimized Prompts:** The "best" version of the system prompt discovered so far.
3. **Few-Shot Examples:** Successful past interactions that the agent can reference to improve future performance.

### C. The Feedback Loop

Create an `optimizer` node that triggers whenever a user provides a "Correction."

The agent writes the improved prompt to our local DB, and the next session loads the versioned `system_prompt` from there.

---

## 4. GitHub & Admin Integration

LangGraph integrates natively with the **LangChain Community Toolkits**.

* **GitHub:** Use the `GitHubToolkit`. It allows agents to create issues, open PRs, read code, and comment on reviews. Since we want to automate the SDLC, we can have one agent act as the "Product Manager" (managing issues) and another as the "Developer" (writing code).
* **Everyday Admin:** For meal prep and shopping, we can use the `Playwright` tool (for web interaction) or custom Python functions to interface with your local calendar (iCal/Google API).

## Comparison to Agent Developer Kit (ADK)

Google's **Agent Development Kit (ADK)**—launched in early 2025—is a formidable competitor to the LangChain/LangGraph ecosystem. Our choice depends on whether we value **ecosystem depth (LangGraph)** or **developer experience and "rewindable" debugging (ADK)**.

Here is the breakdown of how they compare against our specific requirements.

---

### Comparison: LangGraph vs. Google ADK

| Feature | LangGraph | Google ADK |
| --- | --- | --- |
| **Philosophy** | **Graph-based.** Explicitly defines nodes and edges. Best for complex, cyclic logic. | **Code-first.** Aims to make agent development feel like traditional software engineering. |
| **Tracing & Debugging** | **LangSmith** (Cloud/Self-hosted) or Arize Phoenix. Very detailed, but can be heavy. | **Built-in Dev UI.** Includes a unique "rewind" feature to step back through decision logic. |
| **Local LLM Support** | Native via `ChatOllama` or `ChatOpenAI` (Ollama base URL). | Support via **LiteLLM** bridge (e.g., `ollama_chat/llama3`). |
| **Memory & State** | **Checkpointers** for session state; **Store** for long-term/cross-thread memory. | **Artifacts.** A built-in key-value map for memory, goals, and state tracking. |
| **GitHub Integration** | **Extensive.** Mature `GitHubToolkit` for PRs, issues, and code reading. | **Standard.** Relies on custom functions or standard Python libraries (less "pre-built"). |
| **Maturity** | Very High. Huge library of community "recipes." | High (Google-backed) but newer community ecosystem. |

---

### Deep Dive: Which one fits you best?

#### 1. Granular Traces & Human Feedback

* **Google ADK** has a superior **local developer experience**. Its browser-based Dev UI is designed for the "edit-run-debug" cycle. The "rewind" capability is excellent for your "continual human feedback" goal—it allows you to see exactly where a prompt failed and test a correction in real-time.
* **LangGraph** wins on **algorithmic granularity**. Because you define the "State" as a schema, you can inspect and modify every variable between every single node. For a system that "constantly evolves," LangGraph’s transparency into its own state-machine is harder to beat.

#### 2. Local Hardware (Ollama & 12-24GB RAM)

* Both frameworks handle this well by offloading the heavy lifting to the Ollama server.
* **ADK** is slightly more "lightweight" in terms of its own overhead, which might give you a tiny bit more breathing room for larger context windows in your local LLM.

#### 3. Software Development Lifecycle (SDLC) & GitHub

* **LangGraph** is the clear winner here today. The **LangChain GitHub Toolkit** is battle-tested. It includes pre-defined logic for searching repositories, managing branches, and handling large diffs.
* With ADK, you would likely end up writing more "glue code" to interact with the GitHub API.

---

### Final Recommendation: **LangGraph**

While Google ADK's "Rewind" debugger is world-class, **LangGraph** remains the superior choice for your specific project for three reasons:

1. **Maturity of GitHub Tools:** As a specialist looking to automate the *full lifecycle*, you need a framework that can already "speak" GitHub fluently. LangGraph’s integrations are years ahead.
2. **Stateful Evolution:** Your goal of a "constantly evolving system" requires an agent to modify its own instructions or memory. LangGraph’s `Store` and `Checkpointer` architecture is designed specifically for this type of long-term "learning."
3. **Community Recipes:** There are hundreds of open-source "Local Coding Assistant" templates for LangGraph that you can clone and adapt, saving you weeks of architectural setup.
