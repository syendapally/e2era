import json
from typing import Dict, Any, List

from langchain.agents import AgentExecutor, create_react_agent
from langchain.agents import Tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from llm.bedrock import get_llm
from llm.code_exec import run_python_code
from llm.vector_store import retrieve_project_chunks


def run_agent_pipeline(project_id: int, goal: str) -> Dict[str, Any]:
    """
    ReAct-style agent with two tools:
    - retrieve: fetch relevant chunks from pgvector via LangChain retriever
    - run_code: execute Python (simple sandbox) and return stdout/stderr
    Returns: dict with plan (parsed JSON or fallback), code (if executed), exec (stdout/stderr if executed)
    """
    runs: List[Dict[str, Any]] = []

    def retrieve_tool(query: str) -> str:
        docs = retrieve_project_chunks(project_id, query, k=8)
        return "\n\n".join([d.page_content for d in docs]) if docs else "No results."

    def run_code_tool(code: str) -> str:
        stdout, stderr = run_python_code(code)
        runs.append({"code": code, "stdout": stdout, "stderr": stderr})
        return f"stdout:\n{stdout}\n\nstderr:\n{stderr}"

    tools = [
        Tool(
            name="retrieve",
            func=retrieve_tool,
            description="Use to look up relevant context from the project's documents. Input: a query string.",
        ),
        Tool(
            name="run_code",
            func=run_code_tool,
            description="Use to run small Python experiments. Input: Python code as a string. Returns stdout/stderr.",
        ),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a research agent. Always first retrieve relevant context. "
                "Then produce a concise plan in JSON with fields: plan (array of steps), summary (string). "
                "If needed, you may run code. Keep steps short. Do not fabricate results.",
            ),
            ("user", "Goal:\n{goal}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    llm = get_llm()
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    result = executor.invoke({"input": goal})
    output_text = result.get("output", "")

    plan = _try_parse_json(output_text) or {"plan": output_text, "summary": output_text}
    last_run = runs[-1] if runs else None

    return {
        "plan": plan,
        "code": last_run["code"] if last_run else None,
        "exec": {"stdout": last_run["stdout"], "stderr": last_run["stderr"]} if last_run else None,
    }


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None

