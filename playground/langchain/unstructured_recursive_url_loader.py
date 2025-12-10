from typing import Any, Callable, Iterator, List, Optional, Set, Union
import logging
from urllib.parse import urlparse

import requests
from langchain_community.document_loaders.url import UnstructuredURLLoader
from langchain_core.documents import Document
from langchain_core.utils.html import extract_sub_links

logger = logging.getLogger(__name__)

class UnstructuredRecursiveUrlLoader(UnstructuredURLLoader):
    """Recursively load all child links from a root URL using Unstructured.

    This loader combines the recursive crawling logic of RecursiveUrlLoader with
    the content extraction capabilities of UnstructuredURLLoader.
    """

    def __init__(
        self,
        url: str,
        max_depth: Optional[int] = 2,
        link_filter: Optional[Callable[[str], bool]] = None,
        prevent_outside: bool = True,
        timeout: Optional[int] = 10,
        check_response_status: bool = False,
        continue_on_failure: bool = True,
        headers: Optional[dict] = None,
        mode: str = "single",
        show_progress_bar: bool = False,
        base_url: Optional[str] = None,
        autoset_encoding: bool = True,
        encoding: Optional[str] = None,
        proxies: Optional[dict] = None,
        ssl: bool = True,
        **unstructured_kwargs: Any,
    ):
        """Initialize with URL to crawl and unstructured settings.

        Args:
            url: The URL to crawl.
            max_depth: The max depth of the recursive loading.
            link_filter: A function that takes a URL string and returns True if the link
                should be followed, False otherwise. This is applied after `prevent_outside`.
            prevent_outside: If ``True``, prevent loading from urls which are not children
                of the root url.
            timeout: The timeout for the requests, in the unit of seconds.
            check_response_status: If ``True``, check HTTP response status and skip
                URLs with error responses (``400-599``).
            continue_on_failure: If ``True``, continue if getting or parsing a link raises
                an exception. Otherwise, raise the exception.
            headers: Default request headers to use for all requests.
            mode: Mode for unstructured partition ("single" or "elements").
            show_progress_bar: Whether to show a progress bar (not used in lazy_load currently).
            base_url: The base url to check for outside links against.
            autoset_encoding: Whether to automatically set the encoding of the response.
            encoding: The encoding of the response.
            proxies: A dictionary mapping protocol names to the proxy URLs.
            ssl: Whether to verify SSL certificates during requests.
            **unstructured_kwargs: Arbitrary kwargs to pass to the unstructured partition function.
        """
        # Ensure headers is a dict if it is None, because UnstructuredURLLoader expects it to be dictionary-like
        # when popped from kwargs, or it pops default {}.
        if headers is None:
            headers = {}

        # Initialize parent with the root URL.
        # Note: UnstructuredURLLoader stores urls in self.urls
        super().__init__(
            urls=[url],
            continue_on_failure=continue_on_failure,
            mode=mode,
            show_progress_bar=show_progress_bar,
            headers=headers,
            **unstructured_kwargs
        )
        self.url = url
        self.max_depth = max_depth if max_depth is not None else 2
        self.link_filter = link_filter
        self.prevent_outside = prevent_outside if prevent_outside is not None else True
        self.timeout = timeout
        self.check_response_status = check_response_status
        self.base_url = base_url if base_url is not None else self._parse_base_url(url)
        self.autoset_encoding = autoset_encoding
        self.encoding = encoding
        self.proxies = proxies
        self.ssl = ssl

    def _parse_base_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}/"

    def lazy_load(self) -> Iterator[Document]:
        """Lazy load web pages recursively."""
        visited: Set[str] = set()
        yield from self._get_child_links_recursive(self.url, visited)

    def load(self) -> List[Document]:
        """Load web pages recursively."""
        return list(self.lazy_load())

    def _get_child_links_recursive(
        self, url: str, visited: Set[str], *, depth: int = 0
    ) -> Iterator[Document]:
        """Recursively get all child links starting with the path of the input URL."""
        if depth >= self.max_depth:
            return

        visited.add(url)

        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers=self.headers,
                proxies=self.proxies,
                verify=self.ssl,
            )

            if self.encoding is not None:
                response.encoding = self.encoding
            elif self.autoset_encoding:
                response.encoding = response.apparent_encoding

            if self.check_response_status and 400 <= response.status_code <= 599:
                 raise ValueError(f"Received HTTP status {response.status_code}")
        except Exception as e:
            if self.continue_on_failure:
                logger.warning(
                    f"Unable to load from {url}. Received error {e} of type "
                    f"{e.__class__.__name__}"
                )
                return
            else:
                raise e

        # Process content with Unstructured
        try:
            from unstructured.partition.html import partition_html

            # partition_html supports text argument
            elements = partition_html(
                text=response.text,
                source_url=url,
                headers=self.headers,
                **self.unstructured_kwargs
            )

            if self.mode == "single":
                text = "\n\n".join([str(el) for el in elements])
                metadata = {"source": url}
                yield Document(page_content=text, metadata=metadata)
            elif self.mode == "elements":
                for element in elements:
                    metadata = element.metadata.to_dict()
                    metadata["category"] = element.category
                    yield Document(page_content=str(element), metadata=metadata)

        except Exception as e:
             if self.continue_on_failure:
                logger.error(f"Error partitioning {url}: {e}")
             else:
                raise e

        # Extract links
        # We use extract_sub_links which takes care of finding links and converting to absolute paths
        # and checking prevent_outside.
        sub_links = extract_sub_links(
            response.text,
            url,
            base_url=self.base_url,
            prevent_outside=self.prevent_outside,
            continue_on_failure=self.continue_on_failure,
        )

        for link in sub_links:
            # Apply user filter
            if self.link_filter and not self.link_filter(link):
                continue

            if link not in visited:
                yield from self._get_child_links_recursive(
                    link, visited, depth=depth + 1
                )
