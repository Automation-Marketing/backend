import json
import re
from langchain_core.prompts import ChatPromptTemplate

class ObjectivesAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, company: str, product: str, desc: str, comp_context: str, usecase_context: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Campaign Strategist. Define the SMART objectives for this campaign based on the use cases and competition. Return strictly valid JSON."),
            ("human", """Company: {company}
Product: {product}
Description: {desc}
Competition: {comp_context}
Use cases: {usecase_context}

Return JSON with exactly:
{{"objectives": ["Objective 1", "Objective 2", "Objective 3"]}}""")
        ])
        
        chain = prompt | self.llm
        try:
            result = chain.invoke({"company": company, "product": product, "desc": desc, "comp_context": comp_context, "usecase_context": usecase_context})
            return self._parse(result.content)
        except Exception as e:
            print(f"[ObjectivesAgent] Error: {e}")
            return {"objectives": []}

    def _parse(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try: return json.loads(match.group())
                except: pass
            return {"objectives": []}
