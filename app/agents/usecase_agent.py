import json
import re
from langchain_core.prompts import ChatPromptTemplate

class UsecaseAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, company: str, product: str, desc: str, context: str, comp_context: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert Product Marketing Manager. Define specific use cases for the product being launched considering the competitive landscape. Return strictly valid JSON."),
            ("human", """Company: {company}
Product: {product}
Description: {desc}
Competition Context: {comp_context}

Scraped Context:
{context}

Return JSON with exactly:
{{"use_cases": [{{"title": "...", "description": "..."}}]}}""")
        ])
        
        chain = prompt | self.llm
        try:
            result = chain.invoke({"company": company, "product": product, "desc": desc, "context": context, "comp_context": comp_context})
            return self._parse(result.content)
        except Exception as e:
            print(f"[UsecaseAgent] Error: {e}")
            return {"use_cases": []}

    def _parse(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try: return json.loads(match.group())
                except: pass
            return {"use_cases": []}
