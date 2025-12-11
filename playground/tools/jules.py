import os
import requests
from typing import Optional
from langchain.tools import tool
from pydantic import BaseModel, Field

class CreateJulesSessionInput(BaseModel):
    """Input for create_jules_session"""
    prompt: str = Field(description="The task description for Jules to execute.")
    fullRepositoryName: str = Field(
        description="The full repository name in 'owner/repo' format (e.g., 'my-org/my-repo')."
    )
    repositoryBranch: str = Field(
        default="master",
        description="The starting branch for the session (default: 'master')."
    )
    title: Optional[str] = Field(
        default=None,
        description="Optional title for the session."
    )
    requirePlanApproval: bool = Field(
        default=False,
        description="If true, plans require explicit approval before execution."
    )
    automationMode: str = Field(
        default="AUTO_CREATE_PR",
        description="Automation mode (default: 'AUTO_CREATE_PR')."
    )

@tool(args_schema=CreateJulesSessionInput)
def create_jules_session(
    prompt: str,
    fullRepositoryName: str,
    repositoryBranch: str = "master",
    title: Optional[str] = None,
    requirePlanApproval: bool = False,
    automationMode: str = "AUTO_CREATE_PR"
) -> str:
    """
    Start a new session with Jules to execute a coding task.
    """
    api_key = os.environ.get("JULES_API_KEY")
    if not api_key:
        raise ValueError("JULES_API_KEY environment variable is not set.")

    # Format the repository name to the Jules API expected format
    # Expecting "owner/repo" -> "sources/github-owner-repo"
    parts = fullRepositoryName.split('/')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"fullRepositoryName must be in 'owner/repo' format. Got: {fullRepositoryName}")

    owner, repo = parts
    # The Jules API convention for GitHub sources seems to be 'sources/github-{owner}-{repo}'
    # We follow this convention based on the request.
    api_source_name = f"sources/github-{owner}-{repo}"

    url = "https://jules.googleapis.com/v1alpha/sessions"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "sourceContext": {
            "source": api_source_name,
            "githubRepoContext": {
                "startingBranch": repositoryBranch
            }
        },
        "requirePlanApproval": requirePlanApproval,
        "automationMode": automationMode
    }

    if title:
        payload["title"] = title

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["url"]
    except requests.exceptions.RequestException as e:
        # If the response has a JSON body with error details, try to include that
        error_msg = str(e)
        if e.response is not None:
            try:
                error_details = e.response.json()
                error_msg += f" Details: {error_details}"
            except ValueError:
                pass
        raise RuntimeError(f"Failed to create Jules session: {error_msg}")
