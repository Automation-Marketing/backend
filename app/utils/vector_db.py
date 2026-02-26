import os
from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.config import Settings
import json
from typing import List, Dict, Optional
from google import genai
from google.genai import types


class VectorDB:
    """
    Vector database service using ChromaDB with Gemini embeddings.
    Manages storage and retrieval of social media posts.
    """
    
    def __init__(self, persist_directory: str = "./data/chroma_db"):
        """Initialize ChromaDB with persistent storage."""
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.genai_client = genai.Client(api_key=api_key)
        self.embedding_model = "gemini-embedding-001"
        
    def _generate_embedding(self, text: str, is_query: bool = False) -> List[float]:
        """
        Generate embeddings using Gemini's gemini-embedding-001 model.
        
        Args:
            text: Text to embed
            is_query: Differentiate between document embedding and query embedding
            
        Returns:
            List of embedding values
        """
        try:
            task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
            title = "Company Post" if not is_query else None
            
            response = self.genai_client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    title=title
                )
            )
            return response.embeddings[0].values
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
        collection_name = f"company_{company_name.lower().replace(' ', '_').replace('-', '_')}"
        
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

        print("Searching collection:", collection.name)
        print("Collection count:", collection.count())

        
        try:
            existing_data = collection.get(include=["documents", "metadatas"])
            existing_posts = set()
            
            if existing_data["documents"]:
                for i, doc in enumerate(existing_data["documents"]):
                    metadata = existing_data["metadatas"][i] if i < len(existing_data["metadatas"]) else {}
                    platform = metadata.get("platform", "unknown")
                    unique_id = f"{platform}:{doc[:100]}"
                    existing_posts.add(unique_id)
                
                print(f"Found {len(existing_posts)} existing posts in database")
        except Exception as e:
            print(f"Could not check for duplicates: {e}")
            existing_posts = set()
        
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
            
            print(f"  Embedding post {idx + 1}/{len(new_chunks)}...", flush=True)
            try:
                embedding = self._generate_embedding(text)
            except Exception as e:
                print(f"  ⚠ Failed to embed post {idx + 1}: {e}", flush=True)
                continue
            
            print(f"  Embedding post {idx + 1}/{len(new_chunks)}...", flush=True)
            try:
                embedding = self._generate_embedding(text)
            except Exception as e:
                print(f"  ⚠ Failed to embed post {idx + 1}: {e}", flush=True)
                continue
            
            documents.append(text)
            embeddings.append(embedding)
            metadatas.append(chunk.get("metadata", {}))
            ids.append(f"{company}_{idx}_{hash(text)}")
        
        if documents:
            try:
                collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
            except Exception as e:
                if "dimension" in str(e).lower() or "expected" in str(e).lower():
                    print(f"Dimension mismatch error detected: {e}")
                    print(f"Deleting incompatible collection for {company} and recreating it...")
                    self.delete_company(company)
                    collection = self.get_or_create_collection(company)
                    collection.add(
                        documents=documents,
                        embeddings=embeddings,
                        metadatas=metadatas,
                        ids=ids
                    )
                else:
                    raise
            print(f"Successfully added {len(new_chunks)} new posts!")
            print(f"Total posts in database: {collection.count()}")

    def add_texts(self, company: str, texts: List[str], metadatas: List[Dict]) -> None:
        """
        Add raw texts with metadata to the vector database for a company.
        Used by campaign_orchestrator to store AI agent outputs.
        """
        if not texts or len(texts) != len(metadatas):
            print("Invalid inputs to add_texts")
            return
            
        collection = self.get_or_create_collection(company)
        
        documents = []
        embeddings = []
        valid_metadatas = []
        ids = []
        
        for idx, text in enumerate(texts):
            if not text:
                continue
            try:
                embedding = self._generate_embedding(text)
                documents.append(text)
                embeddings.append(embedding)
                valid_metadatas.append(metadatas[idx])
                ids.append(f"{company}_ai_{hash(text)}")
            except Exception as e:
                print(f"Failed to embed text {idx}: {e}")
                
        if documents:
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=valid_metadatas,
                ids=ids
            )
            print(f"Successfully added {len(documents)} strategy texts!")

    def add_texts(self, company: str, texts: List[str], metadatas: List[Dict]) -> None:
        """
        Add raw texts with metadata to the vector database for a company.
        Used by campaign_orchestrator to store AI agent outputs.
        """
        if not texts or len(texts) != len(metadatas):
            print("Invalid inputs to add_texts")
            return
            
        collection = self.get_or_create_collection(company)
        
        documents = []
        embeddings = []
        valid_metadatas = []
        ids = []
        
        for idx, text in enumerate(texts):
            if not text:
                continue
            try:
                embedding = self._generate_embedding(text)
                documents.append(text)
                embeddings.append(embedding)
                valid_metadatas.append(metadatas[idx])
                ids.append(f"{company}_ai_{hash(text)}")
            except Exception as e:
                print(f"Failed to embed text {idx}: {e}")
                
        if documents:
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=valid_metadatas,
                ids=ids
            )
            print(f"Successfully added {len(documents)} strategy texts!")
    
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

        print("Searching collection:", collection.name)
        print("Collection count:", collection.count())

        
        query_embedding = self._generate_embedding(query, is_query=True)
        
        where_filter = None
        if platform_filter:
            where_filter = {"platform": platform_filter}
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter
        )
        
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
