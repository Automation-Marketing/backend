import json
from pathlib import Path
from typing import Dict, Optional


# Absolute path to company_mappings.json, relative to this file's location
_DEFAULT_DB_PATH = Path(__file__).parent / "company_mappings.json"


class CompanyResolver:
    """
    Resolve company names to social media handles.
    Uses a local JSON database with manual mappings.
    """
    
    def __init__(self, db_path: Path = _DEFAULT_DB_PATH):
        """Initialize with path to company mappings database."""
        self.db_path = Path(db_path)
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict:
        """Load company mappings from JSON file."""
        if self.db_path.exists():
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_mappings(self):
        """Save company mappings to JSON file."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.mappings, f, indent=2, ensure_ascii=False)
    
    def resolve(
        self,
        company_name: str,
        instagram: Optional[str] = None,
        linkedin: Optional[str] = None,
        twitter: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Resolve company name to social media handles.
        
        Args:
            company_name: Name of the company
            instagram: Optional Instagram handle override
            linkedin: Optional LinkedIn URL override
            twitter: Optional Twitter handle override
            
        Returns:
            Dictionary with social media handles
        """
        company_key = company_name.lower().strip()
        
        # Check if company exists in database
        if company_key in self.mappings:
            handles = self.mappings[company_key].copy()
            
            # Override with provided values
            if instagram:
                handles["instagram"] = instagram
            if linkedin:
                handles["linkedin"] = linkedin
            if twitter:
                handles["twitter"] = twitter
                
            return handles
        
        # If not in database, use provided values or return empty
        handles = {
            "instagram": instagram or "",
            "linkedin": linkedin or "",
            "twitter": twitter or ""
        }
        
        # Save to database for future use
        if any(handles.values()):
            self.add_company(company_name, handles)
        
        return handles
    
    def add_company(
        self,
        company_name: str,
        handles: Dict[str, str]
    ):
        """
        Add or update company in the database.
        
        Args:
            company_name: Name of the company
            handles: Dictionary with social media handles
        """
        company_key = company_name.lower().strip()
        self.mappings[company_key] = {
            "company_name": company_name,
            "instagram": handles.get("instagram", ""),
            "linkedin": handles.get("linkedin", ""),
            "twitter": handles.get("twitter", "")
        }
        self._save_mappings()
        print(f"Added {company_name} to company database")
    
    def get_company(self, company_name: str) -> Optional[Dict]:
        """Get company handles from database."""
        company_key = company_name.lower().strip()
        return self.mappings.get(company_key)
    
    def list_companies(self) -> list:
        """List all companies in database."""
        return [v["company_name"] for v in self.mappings.values()]


# Test the company resolver
if __name__ == "__main__":
    resolver = CompanyResolver()
    
    # Add test companies
    print("Adding test companies...")
    
    resolver.add_company("Tesla", {
        "instagram": "teslamotors",
        "linkedin": "https://www.linkedin.com/company/tesla-motors/",
        "twitter": "tesla"
    })
    
    resolver.add_company("Odoo", {
        "instagram": "odoo",
        "linkedin": "https://www.linkedin.com/company/odoo/",
        "twitter": "odoo"
    })
    
    # Resolve
    print("\nResolving Tesla...")
    handles = resolver.resolve("Tesla")
    print(json.dumps(handles, indent=2))
    
    # List all
    print("\nAll companies in database:")
    print(resolver.list_companies())
