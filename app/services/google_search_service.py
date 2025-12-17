import asyncio
from typing import List
from pydantic import BaseModel
from langchain_google_community import GoogleSearchAPIWrapper


class SearchResult(BaseModel):
    """Single search result"""
    title: str
    url: str
    snippet: str


class GoogleSearchService:
    """Wrapper around Google Custom Search API via LangChain"""

    def __init__(self, api_key: str, engine_id: str, max_results: int = 10):
        if not api_key or not engine_id:
            raise ValueError(
                "Google Search API credentials not configured. "
                "Please set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in .env file"
            )
        self.api_key = api_key
        self.engine_id = engine_id
        self.max_results = max_results
        self.wrapper = GoogleSearchAPIWrapper(
            google_api_key=api_key,
            google_cse_id=engine_id
        )

    async def search(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """
        Async search using Google Custom Search API.
            query: Search query string
            num_results: Number of results to return (default 5, max 10)
            Returns List of SearchResult objects with title, url, snippet
        """
        try:
            num_results = min(num_results, self.max_results)

            # Run sync wrapper in thread pool
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self.wrapper.results,
                query,
                num_results
            )

            search_results = []
            for result in results:
                search_results.append(SearchResult(
                    title=result.get("title", "No title"),
                    url=result.get("link", ""),
                    snippet=result.get("snippet", "")
                ))

            return search_results

        except Exception as e:
            raise ValueError(f"Google Search API error: {str(e)}")
