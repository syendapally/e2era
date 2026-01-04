from typing import List

from langchain.prompts import ChatPromptTemplate

from core.models import Project
from llm.bedrock import get_llm


def build_plan(project: Project, goal: str, evidence_chunks: List[str]) -> dict:
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a research planner. Given the user's research goal and evidence snippets, "
                "return a concise, actionable plan as JSON with fields: plan (array of steps) and summary (string). "
                "Steps should be short, numbered actions.",
            ),
            (
                "user",
                "Goal:\n{goal}\n\nEvidence:\n{evidence}",
            ),
        ]
    )

    chain = prompt | llm
    result = chain.invoke({"goal": goal, "evidence": "\n\n".join(evidence_chunks[:20])})
    text = result if isinstance(result, str) else str(result)
    try:
        import json
        return json.loads(text)
    except Exception:
        return {"plan": text, "summary": text}

