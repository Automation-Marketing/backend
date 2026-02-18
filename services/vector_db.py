import chromadb
from chromadb.config import Settings
import requests
import json
from typing import List, Dict, Optional


class VectorDB:
    """
    Vector database service using ChromaDB with Ollama embeddings.
    Manages storage and retrieval of social media posts.
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize ChromaDB with persistent storage."""
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.ollama_url = "http://localhost:11434/api/embeddings"
        self.embedding_model = "nomic-embed-text"
        
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embeddings using Ollama's nomic-embed-text model.
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding values
        """
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.embedding_model,
                    "prompt": text
                }
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    def get_or_create_collection(self, company_name: str):
        """
        Get or create a collection for a specific company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            ChromaDB collection
        """
        # Sanitize collection name (ChromaDB requirements)
        collection_name = f"company_{company_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # ChromaDB will create if doesn't exist
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"company": company_name}
        )
        
        return collection
    
    def add_posts(self, company: str, chunks: List[Dict]) -> None:
        """
        Add posts to the vector database for a company.
        Automatically appends new posts and skips duplicates.
        
        Args:
            company: Company name
            chunks: List of chunks with 'text' and 'metadata'
        """
        if not chunks:
            print("No chunks to add")
            return
        
        collection = self.get_or_create_collection(company)
        
        # Get existing posts to check for duplicates
        try:
            existing_data = collection.get(include=["documents", "metadatas"])
            existing_posts = set()
            
            if existing_data["documents"]:
                # Create unique identifiers for existing posts (text + platform)
                for i, doc in enumerate(existing_data["documents"]):
                    metadata = existing_data["metadatas"][i] if i < len(existing_data["metadatas"]) else {}
                    platform = metadata.get("platform", "unknown")
                    # Use first 100 chars of text + platform as unique identifier
                    unique_id = f"{platform}:{doc[:100]}"
                    existing_posts.add(unique_id)
                
                print(f"Found {len(existing_posts)} existing posts in database")
        except Exception as e:
            print(f"Could not check for duplicates: {e}")
            existing_posts = set()
        
        # Filter out duplicates
        new_chunks = []
        duplicate_count = 0
        
        for chunk in chunks:
            text = chunk["text"]
            platform = chunk["metadata"].get("platform", "unknown")
            unique_id = f"{platform}:{text[:100]}"
            
            if unique_id in existing_posts:
                duplicate_count += 1
                print(f"Skipping duplicate post from {platform}")
            else:
                new_chunks.append(chunk)
                existing_posts.add(unique_id) 
        
        if duplicate_count > 0:
            print(f"Skipped {duplicate_count} duplicate posts")
        
        if not new_chunks:
            print("No new posts to add (all were duplicates)")
            return
        
        print(f"Adding {len(new_chunks)} new posts to vector database...")
        
        documents = []
        embeddings = []
        metadatas = []
        ids = []
        
        for idx, chunk in enumerate(new_chunks):
            text = chunk.get("text", "")
            if not text:
                continue
                
            embedding = self._generate_embedding(text)
            
            documents.append(text)
            embeddings.append(embedding)
            metadatas.append(chunk.get("metadata", {}))
            ids.append(f"{company}_{idx}_{hash(text)}")
        
        if documents:
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Successfully added {len(new_chunks)} new posts!")
            print(f"Total posts in database: {collection.count()}")
    
    def search(
        self, 
        company_name: str, 
        query: str, 
        top_k: int = 5,
        platform_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for similar posts using semantic search.
        
        Args:
            company_name: Name of the company
            query: Search query
            top_k: Number of results to return
            platform_filter: Optional platform filter (instagram, linkedin, twitter)
            
        Returns:
            List of matching posts with metadata
        """
        collection = self.get_or_create_collection(company_name)
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Build filter
        where_filter = None
        if platform_filter:
            where_filter = {"platform": platform_filter}
        
        # Search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter
        )
        
        # Format results
        formatted_results = []
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })
        
        return formatted_results
    
    def delete_company(self, company_name: str):
        """
        Delete all data for a specific company.
        
        Args:
            company_name: Name of the company
        """
        collection_name = f"company_{company_name.lower().replace(' ', '_').replace('-', '_')}"
        try:
            self.client.delete_collection(name=collection_name)
            print(f"Deleted collection for {company_name}")
        except Exception as e:
            print(f"Error deleting collection: {e}")
    
    def get_company_stats(self, company_name: str) -> Dict:
        """
        Get statistics about stored data for a company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Dictionary with statistics
        """
        collection = self.get_or_create_collection(company_name)
        count = collection.count()
        
        return {
            "company": company_name,
            "total_posts": count,
            "collection_name": collection.name
        }


if __name__ == "__main__":
    db = VectorDB()
    
    test_posts = [
        {
            "text": "Excited to announce our new AI product launch!",
            "metadata": {
                "platform": "twitter",
                "company": "TestCo",
                "post_date": "2026-02-17",
                "hashtags": ["#AI", "#ProductLaunch"]
            }
        },
        {
            "text": "Join us for our annual tech conference next month",
            "metadata": {
                "platform": "linkedin",
                "company": "TestCo",
                "post_date": "2026-02-16"
            }
        }
    ]
    
    print("Adding test posts...")
    db.add_posts("TestCo", test_posts)
    
    print("\nSearching for 'artificial intelligence'...")
    results = db.search("TestCo", "artificial intelligence", top_k=2)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['text']}")
        print(f"   Platform: {result['metadata'].get('platform')}")
        print(f"   Distance: {result.get('distance')}")
    
    print("\n" + "="*50)
    stats = db.get_company_stats("TestCo")
    print(f"Stats: {stats}")
