import argparse
import os
import requests
from string import Template

from ghapi.all import GhApi

ISSUE_TEMPLATE = Template("""
- Read the project specification (`docs/SPECS.md`) to understand what you're building
- Check the recent history log: `git log --oneline -5`
- Ensure all tests are passing before starting your work
- When your work is done, the commit message MUST include for following magic words: "Closes #$number"

Your task today: $title
$body
""")

def add_comment_to_issue(repo_owner, repo_name, issue_number, comment_body):
    """
    Adds a comment to a GitHub issue.
    """
    try:
        api = GhApi(owner=repo_owner, repo=repo_name, token=os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"))
        api.issues.create_comment(owner=repo_owner, repo=repo_name, issue_number=issue_number, body=comment_body)
        print(f"Comment added to issue #{issue_number}.")
    except Exception as e:
        print(f"Error adding comment to GitHub issue: {e}")

def get_open_issues(repo_owner, repo_name):
    """
    Retrieves open issues with the "status: ready" label from a GitHub repository, sorted by priority.

    Args:
        repo_owner: The owner of the repository.
        repo_name: The name of the repository.

    Returns:
        A list of open issue objects, or None if no open issues are found.
    """
    try:
        api = GhApi(owner=repo_owner, repo=repo_name, token=os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"))
        issues = api.issues.list_for_repo(state='open', labels='status: ready')
        if issues:
            filtered_issues = [
                issue
                for issue in issues
                if "pull_request" not in issue
            ]

            priority_order = {
                "priority: critical": 4,
                "priority: high": 3,
                "priority: medium": 2,
                "priority: low": 1,
            }

            def get_priority(issue):
                labels = {l.name for l in issue.labels}
                for label, priority in priority_order.items():
                    if label in labels:
                        return priority
                return 0  # Lowest priority

            sorted_issues = sorted(filtered_issues, key=get_priority, reverse=True)
            return sorted_issues
        else:
            return None
    except Exception as e:
        print(f"Error retrieving issues from GitHub: {e}")
        return None

def get_active_jules_sessions():
    """
    Retrieves all active Jules sessions.

    Returns:
        A list of active Jules sessions, or None if an error occurs.
    """
    jules_api_key = os.getenv("JULES_API_KEY")
    if not jules_api_key:
        print("Error: JULES_API_KEY environment variable not set.")
        return None

    headers = {
        "x-goog-api-key": jules_api_key,
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(
            "https://jules.googleapis.com/v1alpha/sessions",
            headers=headers,
        )
        response.raise_for_status()
        sessions = response.json().get("sessions", [])
        active_states = {"QUEUED", "PLANNING", "IN_PROGRESS", "AWAITING_PLAN_APPROVAL", "AWAITING_USER_FEEDBACK"}
        active_sessions = [
            session for session in sessions if session.get("state") in active_states
        ]
        return active_sessions
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving Jules sessions: {e}")
        return None

def create_jules_session(title, prompt, repo_full_name, starting_branch, require_plan_approval, automation_mode):
    """
    Creates a new Jules session.

    Args:
        prompt: The prompt for the Jules session.
        repo_full_name: The full name of the repository (e.g., "owner/repo").
        starting_branch: The starting branch for the session.
        require_plan_approval: If the plan should be approved by a human.
        automation_mode: The automation mode.

    Returns:
        The JSON response from the Jules API, or None if an error occurs.
    """
    jules_api_key = os.getenv("JULES_API_KEY")
    if not jules_api_key:
        print("Error: JULES_API_KEY environment variable not set.")
        return None

    headers = {
        "x-goog-api-key": jules_api_key,
        "Content-Type": "application/json",
    }

    source_name = f"sources/github/{repo_full_name}"

    data = {
        "title": title,
        "prompt": prompt,
        "sourceContext": {
            "source": source_name,
            "githubRepoContext": {
                "startingBranch": starting_branch
            }
        },
        "requirePlanApproval": require_plan_approval
    }

    if automation_mode:
        data["automationMode"] = automation_mode

    try:
        response = requests.post(
            "https://jules.googleapis.com/v1alpha/sessions",
            headers=headers,
            json=data,
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        body = response.json()
        return f"https://jules.google.com/session/{body['id']}"
    except requests.exceptions.RequestException as e:
        print(f"Error creating Jules session: {e}")
        return None

def main():
    """
    Main function to run the script.
    """
    parser = argparse.ArgumentParser(description="Create a Jules session from a GitHub issue.")
    parser.add_argument("repository", help="The GitHub repository in 'owner/repo' format.")
    parser.add_argument("--branch", default="master", help="The starting branch for the Jules session.")
    parser.add_argument("--count", type=int, default=1, help="Number of issues to send to Jules for processing.")
    parser.add_argument("--no-pr", action="store_true", help="Do not create a pull request.")
    parser.set_defaults(require_plan_approval=True)
    parser.add_argument("--no-plan-approval", dest="require_plan_approval", action="store_false",
                        help="Do not require plan approval.")
    args = parser.parse_args()

    repo_full_name = args.repository
    try:
        repo_owner, repo_name = repo_full_name.split('/')
    except ValueError:
        print("Error: Invalid repository format. Please use 'owner/repo'.")
        return

    print(f"Retrieving open issues from {repo_full_name}...")
    issues = get_open_issues(repo_owner, repo_name)

    if not issues:
        print("No open issues with 'status: ready' label found.")
        return

    print("Checking for active Jules sessions...")
    active_sessions = get_active_jules_sessions()
    active_titles = {session.get("title") for session in active_sessions} if active_sessions else set()

    automation_mode = "AUTO_CREATE_PR" if not args.no_pr else None

    issues_processed = 0
    for issue in issues:
        if issues_processed >= args.count:
            print(f"Processed {args.count} issues, stopping.")
            break

        title = f"{repo_full_name}#{issue.number}"
        if title in active_titles:
            print(f"Jules is already working on issue #{issue.number}.")
            continue

        print(f"Found issue to work on: #{issue.number}")
        prompt = ISSUE_TEMPLATE.substitute(**issue)

        print("Creating a new Jules session...")
        session_url = create_jules_session(title, prompt, repo_full_name, args.branch, args.require_plan_approval,
                                             automation_mode)
        if session_url:
            print(f"Jules session created successfully: {session_url}")
            add_comment_to_issue(repo_owner, repo_name, issue.number, f"Jules session created: {session_url}")
            issues_processed += 1


    print("All open issues are already being worked on by Jules.")

if __name__ == "__main__":
    main()