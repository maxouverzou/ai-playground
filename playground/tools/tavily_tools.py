import os
from typing import Literal, List, Optional

from langchain.tools import tool
from pydantic import BaseModel, Field
from tavily import TavilyClient

# step 3: create the tool
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

class TavilyCrawlInput(BaseModel):
    """Input for tavily crawl"""
    url: str = Field(description="The root URL to begin the crawl")
    instructions: str = Field(description="Natural language instructions for the crawler")
    max_depth: Optional[int] = Field(
        description="Max depth of the crawl. Defines how far from the base URL the crawler can explore", default=1)
    max_breadth: Optional[int] = Field(
        description="Max number of links to follow per level of the tree (i.e., per page)",
        default=20)
    limit: Optional[int] = Field(description="Total number of links the crawler will process before stopping",
                                 default=50)
    select_paths: Optional[List[str]] = Field(
        description="Regex patterns to select only URLs with specific path patterns.", default=None)
    select_domains: Optional[List[str]] = Field(
        description="Regex patterns to select crawling to specific domains or subdomains", default=None)
    exclude_paths: Optional[List[str]] = Field(
        description="Regex patterns to exclude URLs with specific path patterns.")
    exclude_domains: Optional[List[str]] = Field(
        description="Regex patterns to exclude specific domains or subdomains from crawling.")
    allow_external: Optional[bool] = Field(
        description="Whether to include external domain links in the final results list.", default=True)
    include_images: Optional[bool] = Field(description="Whether to include images in the crawl results.", default=False)
    extract_depth: Optional[Literal["basic", "advanced"]] = Field(
        description="Advanced extraction retrieves more data, including tables and embedded content, with higher success but may increase latency.",
        default="basic")


@tool(args_schema=TavilyCrawlInput)
def tavily_crawl(
        url: str,
        instruction: Optional[str],
        max_depth=1,
        max_breadth=20,
        limit=50,
        select_paths: List[str] = None,
        select_domains: List[str] = None,
        exclude_paths: List[str] = None,
        exclude_domains: List[str] = None,
        allow_external: bool = True,
        include_images: bool = False,
        extract_depth: Literal["basic", "advanced"] = "basic",
):
    """
    Graph-based website traversal with built-in extraction and intelligent discovery.

    Use this to discover new content on high-value websites.
    """
    return tavily_client.crawl(url, instruction=instruction, max_depth=max_depth, max_breadth=max_breadth, limit=limit,
                               select_paths=select_paths, select_domains=select_domains, exclude_paths=exclude_paths,
                               exclude_domains=exclude_domains, allow_external=allow_external,
                               include_images=include_images, extract_depth=extract_depth)


class TavilyExtractInput(BaseModel):
    """Input for tavily extract"""
    urls: List[str] = Field(description="The URL(s) to extract content from.")
    extract_depth: Optional[Literal["basic", "advanced"]] = Field(
        description="Advanced extraction retrieves more data, including tables and embedded content, with higher success but may increase latency.",
        default="basic")


@tool(args_schema=TavilyExtractInput)
def tavily_extract(
        urls: List[str],
        extract_depth: Literal["basic", "advanced"] = "basic",
):
    """
    Extract web page(s) content.

    Use this to get the content of high-value pages.
    """
    return tavily_client.extract(urls, extract_depth=extract_depth)


class TavilySearchInput(BaseModel):
    query: str = Field(description="The search query to execute")
    max_results: Optional[int] = Field(
        description="The maximum number of search results to return.",
        default=5)
    topic: Optional[Literal["general", "news", "finance"]] = Field(
        description="The category of the search. 'news' is useful for retrieving real-time updates, particularly about politics, sports, and major current events covered by mainstream media sources. 'general' is for broader, more general-purpose searches that may include a wide range of sources.",
        default="general")
    include_raw_content: Optional[bool] = Field(
        description="Include the cleaned and parsed HTML content of each search result.", default=False)


@tool(args_schema=TavilySearchInput)
def tavily_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = False,
):
    """
    Run a web search.

    Use this to explore a topic, find relevant URLs, or answer specific factual questions.
    """
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
