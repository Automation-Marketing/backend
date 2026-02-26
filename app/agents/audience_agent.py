import json
import re
from langchain_core.prompts import ChatPromptTemplate

class AudienceAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, company: str, product: str, icp: str, desc: str, comp_context: str, usecase_context: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an Audience Targeting Expert. Define the primary and secondary target audience profiles based on the use cases and initial ICP hint. Return strictly valid JSON."),
            ("human", """Company: {company}
Product: {product}
Hint ICP: {icp}
Description: {desc}
Competition: {comp_context}
Use cases: {usecase_context}

Return JSON with exactly:
{{"target_users": {{"primary": {{"profile": "...", "pain_points": ["..."], "motivations": ["..."]}}, "secondary": {{"profile": "...", "pain_points": ["..."], "motivations": ["..."]}}}}}}""")
        ])
        
        chain = prompt | self.llm
        try:
            result = chain.invoke({"company": company, "product": product, "icp": icp, "desc": desc, "comp_context": comp_context, "usecase_context": usecase_context})
            return self._parse(result.content)
        except Exception as e:
            print(f"[AudienceAgent] Error: {e}")
            return {"target_users": {}}

    def _parse(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try: return json.loads(match.group())
                except: pass
            return {"target_users": {}}
