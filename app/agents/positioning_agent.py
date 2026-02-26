import json
import re
from langchain_core.prompts import ChatPromptTemplate

class PositioningAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, company: str, product: str, tone: str, desc: str, comp_context: str, usecase_context: str, aud_context: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Master Brand Strategist. Synthesize all previous intelligence to generate the final product positioning statement and 3 taglines. Tone should be respected. Return strictly valid JSON."),
            ("human", """Company: {company}
Product: {product}
Tone: {tone}
Description: {desc}
Competition: {comp_context}
Use cases: {usecase_context}
Audience: {aud_context}

Return JSON with exactly:
{{"positioning": {{"statement": "One clear positioning statement", "taglines": ["...", "...", "..."]}}}}""")
        ])
        
        chain = prompt | self.llm
        try:
            result = chain.invoke({"company": company, "product": product, "tone": tone, "desc": desc, "comp_context": comp_context, "usecase_context": usecase_context, "aud_context": aud_context})
            return self._parse(result.content)
        except Exception as e:
            print(f"[PositioningAgent] Error: {e}")
            return {"positioning": {}}

    def _parse(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try: return json.loads(match.group())
                except: pass
            return {"positioning": {}}
