import json
from typing import Dict, Any, List

from langchain.agents import AgentExecutor, create_react_agent
from langchain.agents import Tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools.render import render_text_description

from llm.bedrock import get_llm
from llm.code_exec import run_python_code
from llm.vector_store import retrieve_project_chunks


def run_agent_pipeline(project_id: int, goal: str) -> Dict[str, Any]:
    """
    ReAct-style agent with tools:
    - retrieve: fetch relevant chunks from pgvector via LangChain retriever
    - run_code: execute Python (simple sandbox) and return stdout/stderr
    Final output: a natural language answer. If code was run, include code and exec output.
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
            description=(
                "Use to run small Python experiments. Input must be Python code you just generated, "
                "as a single string. Do not call this unless code meaningfully improves the answer. "
                "Returns stdout/stderr."
            ),
        ),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a research agent. Always retrieve context first. "
                "Answer the user's goal concisely. Use code only if it materially improves the answer, "
                "and only after you have generated the exact Python you will run. "
                "If you run code, keep it small/self-contained and in your final answer briefly explain: "
                "the intent, the code (high level), and the results (stdout/stderr). Do not fabricate.",
            ),
            (
                "system",
                "TOOLS AVAILABLE:\n{tools}\n"
                "When invoking a tool, use its exact name from: {tool_names}.",
            ),
            ("user", "Goal:\n{input}"),
            MessagesPlaceholder("agent_scratchpad", optional=True),
        ]
    ).partial(
        tools=render_text_description(tools),
        tool_names=", ".join([t.name for t in tools]),
    )

    llm = get_llm()
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
    )

    result = executor.invoke({"input": goal, "agent_scratchpad": []})
    
    output_text = result.get("output", "")

    last_run = runs[-1] if runs else None

    return {
        "answer": output_text,
        "code": last_run["code"] if last_run else None,
        "exec": {"stdout": last_run["stdout"], "stderr": last_run["stderr"]} if last_run else None,
    }


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None

