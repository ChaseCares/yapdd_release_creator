#!/usr/bin/env python3
"""
Compares the latest Git tag between two GitHub repositories.

If the target repository has a newer tag, this script creates a new release
in the local repository to match that tag. It can optionally send notifications
to a Discord webhook.
"""

import argparse
import logging
import re
import sys
from typing import Dict, Optional

import requests

# --- Constants ---
GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
# Regex for YYYY.MM[.patch] style tags
TAG_VERSION_PATTERN = re.compile(r"^\d{4}\.\d{2}(\.\d+)?$")
# Regex for 'owner/repo' format
OWNER_REPO_PATTERN = re.compile(r"^[\w.-]+/[\w.-]+$")
# Regex for GitHub Personal Access Tokens (classic and fine-grained)
# https://gist.github.com/magnetikonline/073afe7909ffdd6f10ef06a00bc3bc88
TOKEN_PATTERN = re.compile(r"^(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})$")


class GitHubAPI:
    """A wrapper for interacting with the GitHub API."""

    def __init__(self, auth_token: str):
        if not TOKEN_PATTERN.match(auth_token):
            raise ValueError("Invalid GitHub authentication token format.")
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {auth_token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    def get_latest_tag(self, owner_repo: str) -> str:
        """
        Fetches the latest tag for a given repository.

        Args:
            owner_repo: The repository in 'owner/name' format.

        Returns:
            The name of the latest tag.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
            ValueError: If the repository has no tags.
        """
        if not OWNER_REPO_PATTERN.match(owner_repo):
            raise ValueError(f"Invalid repository format: '{owner_repo}'")

        url = f"{GITHUB_API_URL}/repos/{owner_repo}/git/matching-refs/tags"
        response = requests.get(url, headers=self._headers)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        tags = response.json()

        if not tags:
            raise ValueError(f"No tags found for repository '{owner_repo}'.")

        # The API returns tags sorted chronologically, so the last one is the newest.
        latest_tag_ref = tags[-1].get("ref", "")
        return latest_tag_ref.split("/")[-1]

    def create_release(
        self, owner_repo: str, tag_name: str, body: str, target_commitish: str = "main"
    ) -> requests.Response:
        """
        Creates a new release in a GitHub repository.

        Args:
            owner_repo: The repository in 'owner/name' format.
            tag_name: The name for the tag and release.
            body: The text description of the release.
            target_commitish: The commitish value that the tag is created from.

        Returns:
            The requests.Response object from the API call.
        """
        url = f"{GITHUB_API_URL}/repos/{owner_repo}/releases"
        data = {
            "tag_name": tag_name,
            "name": tag_name,  # Release name is same as tag
            "body": body,
            "target_commitish": target_commitish,
        }
        response = requests.post(url, headers=self._headers, json=data)
        response.raise_for_status()
        return response


def send_discord_notification(message: str, webhook_url: str) -> None:
    """Sends a notification message to a Discord webhook."""
    if not webhook_url:
        return
    try:
        response = requests.post(webhook_url, json={"content": message})
        response.raise_for_status()
        logging.info("Successfully sent Discord notification.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Discord notification: {e}")


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare latest tags of two GitHub repos and create a new release if needed."
    )
    parser.add_argument(
        "--auth",
        type=str,
        help="GitHub personal access token for authentication.",
        required=True,
    )
    parser.add_argument(
        "--target-repo",
        type=str,
        help="The target (source) repository in 'owner/repo' format.",
        required=True,
    )
    parser.add_argument(
        "--local-repo",
        type=str,
        help="The local (destination) repository to update, in 'owner/repo' format.",
        required=True,
    )
    parser.add_argument(
        "--discord-webhook",
        type=str,
        help="Optional Discord webhook URL for notifications.",
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    """Main execution function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    args = parse_arguments()

    try:
        api = GitHubAPI(args.auth)

        # Fetch and validate tags
        logging.info(f"Fetching latest tag from target repo: {args.target_repo}")
        target_tag = api.get_latest_tag(args.target_repo)
        if not TAG_VERSION_PATTERN.match(target_tag):
            raise ValueError(f"Target tag '{target_tag}' does not match expected format.")
        logging.info(f"Found target tag: {target_tag}")

        logging.info(f"Fetching latest tag from local repo: {args.local_repo}")
        local_tag = api.get_latest_tag(args.local_repo)
        if not TAG_VERSION_PATTERN.match(local_tag):
            raise ValueError(f"Local tag '{local_tag}' does not match expected format.")
        logging.info(f"Found local tag: {local_tag}")

        # Compare tags and act
        if target_tag == local_tag:
            logging.info("Tags are identical. No update needed.")
            return

        message = (
            f"Update needed for '{args.local_repo}'. "
            f"Newest tag from '{args.target_repo}' is {target_tag}."
        )
        logging.warning(message)
        send_discord_notification(message, args.discord_webhook)

        release_body = (
            "This release was automatically generated.\n"
            f"It mirrors the upstream changes from "
            f"https://github.com/{args.target_repo}/releases/tag/{target_tag}"
        )

        logging.info(f"Creating release '{target_tag}' in '{args.local_repo}'...")
        api.create_release(args.local_repo, target_tag, release_body)

        success_message = f"Successfully created release '{target_tag}' in '{args.local_repo}'."
        logging.info(success_message)
        send_discord_notification(success_message, args.discord_webhook)

    except (ValueError, requests.exceptions.RequestException) as e:
        error_message = f"Operation failed: {e}"
        logging.error(error_message, exc_info=False) # set exc_info=True for full traceback
        send_discord_notification(f"ERROR: {error_message}", args.discord_webhook)
        sys.exit(1)


if __name__ == "__main__":
    main()
