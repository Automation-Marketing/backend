import json
import re
from langchain_core.prompts import ChatPromptTemplate

class CompetitionAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, company: str, product: str, desc: str, context: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert Competitive Intelligence Analyst. Identify the market competition, alternatives, and advantages for the specific product being launched based on the context. Return strictly valid JSON."),
            ("human", """Company: {company}
Product/Service: {product}
Campaign Description: {desc}

Scraped Context:
{context}

Return JSON with exactly these keys:
{{"competitors": ["Comp 1", "Comp 2"], "alternative_product": "What alternatives exist in the market?", "advantages": "How is this product better than alternatives?"}}""")
        ])
        
        chain = prompt | self.llm
        try:
            result = chain.invoke({"company": company, "product": product, "desc": desc, "context": context})
            return self._parse(result.content)
        except Exception as e:
            print(f"[CompetitionAgent] Error: {e}")
            return {"competitors": [], "alternative_product": "", "advantages": ""}

    def _parse(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try: return json.loads(match.group())
                except: pass
            return {"competitors": [], "alternative_product": "", "advantages": ""}
