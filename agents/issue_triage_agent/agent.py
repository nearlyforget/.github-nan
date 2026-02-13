# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any

from google.adk.agents.llm_agent import Agent
from issue_triage_agent.settings import GITHUB_BASE_URL
from issue_triage_agent.settings import IS_INTERACTIVE
from issue_triage_agent.settings import OWNER
from issue_triage_agent.settings import REPO
from issue_triage_agent.team_members import TEAM_MEMBERS
from issue_triage_agent.utils import error_response
from issue_triage_agent.utils import get_request
from issue_triage_agent.utils import patch_request
from issue_triage_agent.utils import post_request
import requests


CATEGORY_TO_OWNER = {
    "core-protocol": "technical-committee",
    "governance": "governance-committee",
    "capability": "maintainers",
    "documentation": "maintainers",
    "infrastructure": "devops-maintainers",
    "maintenance": "devops-maintainers",
    "sdk": "devops-maintainers",
    "samples-conformance": "maintainers",
}

CATEGORIES = list(CATEGORY_TO_OWNER.keys())

CATEGORY_GUIDELINES = """
      Category rubric and disambiguation rules:
      - "core-protocol": Issues related to base communication layer, global context, breaking changes or major refactors.
      - "governance": Issues related to project governance, contribution guidelines, licensing.
      - "capability": Issues suggesting new schemas (Discovery, Cart, etc.) or extensions, or bugs in existing ones.
      - "documentation": Issues about documentation (README, guides).
      - "infrastructure": Issues about CI/CD, linters, build scripts, repo setup.
      - "maintenance": Issues about version bumps, lockfile updates, minor bug fixes, dependency updates.
      - "sdk": Issues related to language specific SDKs.
      - "samples-conformance": Issues about samples or conformance suite.

      When unsure between categories, prefer the most specific match. If a category
      cannot be assigned confidently, do not call the labeling tool.
"""

APPROVAL_INSTRUCTION = (
    "Do not ask for user approval for labeling! If you can't find appropriate"
    " category for the issue, do not label it."
)
if IS_INTERACTIVE:
    APPROVAL_INSTRUCTION = "Only label them when the user approves the labeling!"


def list_untriaged_issues(issue_count: int) -> dict[str, Any]:
    """List open issues that need triaging.

    Returns issues that are missing a category label, or have no assignees.

    Args:
      issue_count: number of issues to return

    Returns:
      The status of this request, with a list of issues when successful.
      Each issue includes flags indicating what actions are needed.
    """
    url = f"{GITHUB_BASE_URL}/search/issues"
    query = f"repo:{OWNER}/{REPO} is:open is:issue"
    params = {
        "q": query,
        "sort": "created",
        "order": "desc",
        "per_page": 100,  # Fetch more to filter
        "page": 1,
    }

    try:
        response = get_request(url, params)
    except requests.exceptions.RequestException as e:
        return error_response(f"Error: {e}")
    issues = response.get("items", [])

    category_labels = set(CATEGORY_TO_OWNER.keys())
    untriaged_issues = []
    for issue in issues:
        issue_labels = {label["name"] for label in issue.get("labels", [])}
        assignees = issue.get("assignees", [])

        existing_category_labels = issue_labels & category_labels
        has_category = bool(existing_category_labels)

        # Determine what actions are needed
        needs_category_label = not has_category
        needs_owner = not assignees

        # Include issue if it needs any action
        if needs_category_label or needs_owner:
            issue["needs_category_label"] = needs_category_label
            issue["needs_owner"] = needs_owner
            issue["existing_category_label"] = (
                list(existing_category_labels)[0] if existing_category_labels else None
            )
            untriaged_issues.append(issue)
            if len(untriaged_issues) >= issue_count:
                break
    return {"status": "success", "issues": untriaged_issues}


def add_label_to_issue(issue_number: int, label: str) -> dict[str, Any]:
    """Add the specified category label to the given issue number.

    Args:
      issue_number: issue number of the GitHub issue.
      label: label to assign

    Returns:
      The status of this request, with the applied label when successful.
    """
    print(f"Attempting to add label '{label}' to issue #{issue_number}")
    if label not in CATEGORY_TO_OWNER:
        return error_response(
            f"Error: Label '{label}' is not an allowed category label. Will not apply."
        )

    label_url = f"{GITHUB_BASE_URL}/repos/{OWNER}/{REPO}/issues/{issue_number}/labels"
    label_payload = [label]

    try:
        response = post_request(label_url, label_payload)
    except requests.exceptions.RequestException as e:
        return error_response(f"Error: {e}")

    return {
        "status": "success",
        "message": response,
        "applied_label": label,
    }


def add_owner_to_issue(issue_number: int, label: str) -> dict[str, Any]:
    """Assign an owner to the issue based on the category label.

    Args:
      issue_number: issue number of the GitHub issue.
      label: category label that determines the owner to assign

    Returns:
      The status of this request, with the assigned owner when successful.
    """
    print(f"Attempting to assign owner for label '{label}' to issue #{issue_number}")
    if label not in CATEGORY_TO_OWNER:
        return error_response(f"Error: Label '{label}' is not a valid category label.")

    team = CATEGORY_TO_OWNER.get(label)
    if not team:
        return {
            "status": "warning",
            "message": (
                f"Label '{label}' does not have an owner team. Will not assign."
            ),
        }

    members = TEAM_MEMBERS.get(team)
    if not members or not members[0]:
        return {
            "status": "warning",
            "message": (
                f"Team '{team}' for label '{label}' has no members defined in"
                " team_members.py. Will not assign."
            ),
        }

    owner = members[0]  # Assign the first user in the list
    print(f"Assigning default user '{owner}' from team '{team}'")

    assignee_url = (
        f"{GITHUB_BASE_URL}/repos/{OWNER}/{REPO}/issues/{issue_number}/assignees"
    )
    assignee_payload = {"assignees": [owner]}

    try:
        response = post_request(assignee_url, assignee_payload)
    except requests.exceptions.RequestException as e:
        return error_response(f"Error: {e}")

    return {
        "status": "success",
        "message": response,
        "assigned_owner": owner,
    }


def change_issue_type(issue_number: int, issue_type: str) -> dict[str, Any]:
    """Change the issue type of the given issue number.

    Args:
      issue_number: issue number of the GitHub issue, in string format.
      issue_type: issue type to assign

    Returns:
      The the status of this request, with the applied issue type when successful.
    """
    print(f"Attempting to change issue type '{issue_type}' to issue #{issue_number}")
    url = f"{GITHUB_BASE_URL}/repos/{OWNER}/{REPO}/issues/{issue_number}"
    payload = {"type": issue_type}

    try:
        response = patch_request(url, payload)
    except requests.exceptions.RequestException as e:
        return error_response(f"Error: {e}")

    return {"status": "success", "message": response, "issue_type": issue_type}


root_agent = Agent(
    model="gemini-2.0-flash",
    name="issue_triage_assistant",
    description="Triage GitHub issues with category labels.",
    instruction=f"""
      You are a triaging bot for the GitHub {REPO} repo with the owner {OWNER}.
      Your goal is to triage new issues by assigning a category label and setting issue type.
      IMPORTANT: {APPROVAL_INSTRUCTION}

      {CATEGORY_GUIDELINES}

      ## Triaging Workflow

      Each issue will have flags indicating what actions are needed:
      - `needs_category_label`: true if the issue needs a category label.
      - `needs_owner`: true if the issue needs an owner assigned.

      For each issue, perform ONLY the required actions based on the flags:

      1. **If `needs_category_label` is true**:
         - Use `add_label_to_issue` to add ONE appropriate category label from the list: {", ".join(CATEGORY_TO_OWNER.keys())}.
         - Use `change_issue_type` to set the issue type:
           - If it's a bug report → "Bug"
           - If it's a feature request → "Feature"
           - Otherwise → do not change the issue type

      2. **If `needs_owner` is true**:
         - Use `add_owner_to_issue` to assign an owner based on the category label.
         - Note: If the issue already has a category label (`existing_category_label`), use that existing label to determine the owner. If you just added a category label, use that label to determine the owner.

      Do NOT add a category label if `needs_category_label` is false.
      Do NOT assign an owner if `needs_owner` is false.

      Response quality requirements:
      - Summarize the issue in your own words without leaving template
        placeholders (never output text like "[fill in later]").
      - Justify the chosen category label with a short explanation referencing the issue
        details.
      - If no label is applied, clearly state why.

      Present the following in an easy to read format highlighting issue number and your label.
      - the issue summary in a few sentence
      - your category label recommendation and justification
    """,
    tools=[
        list_untriaged_issues,
        add_label_to_issue,
        add_owner_to_issue,
        change_issue_type,
    ],
)
