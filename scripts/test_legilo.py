"""
Test the Legilo fetcher for a single dataset ID.

Usage:
    uv run scripts/test_legilo.py <dataset-id>

Example:
    uv run scripts/test_legilo.py 12345678-abcd-efgh-ijkl-123456789012
"""

import argparse
import json
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger("test_legilo")

LEGILO_URL = "https://legilo.eds-infra.ceh.ac.uk/{id}/documents"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Legilo for a single dataset ID")
    parser.add_argument("id", help="EIDC dataset identifier (UUID)")
    args = parser.parse_args()

    username = os.getenv("LEGILO_USERNAME")
    password = os.getenv("LEGILO_PASSWORD")
    url = LEGILO_URL.format(id=args.id)

    logger.info("URL:      %s", url)
    logger.info("Username: %s", username or "(not set)")
    logger.info("Password: %s", "***" if password else "(not set)")

    res = requests.get(url, auth=(username, password))
    logger.info("Status:   %d", res.status_code)

    if res.status_code == 401:
        logger.error("Authentication failed — check LEGILO_USERNAME and LEGILO_PASSWORD")
        raise SystemExit(1)

    if res.status_code == 404:
        logger.warning("404 — no supporting docs found for this ID (auth may still be fine)")
        raise SystemExit(0)

    if res.status_code != 200:
        logger.error("Unexpected status %d", res.status_code)
        logger.debug("Response body: %s", res.text[:500])
        raise SystemExit(1)

    try:
        body = res.json()
    except Exception as e:
        logger.error("Failed to parse JSON response: %s", e)
        logger.debug("Raw response: %s", res.text[:500])
        raise SystemExit(1)

    logger.debug("Response keys: %s", list(body.keys()))

    docs = body.get("success", {})
    if not docs:
        logger.warning("Response was 200 but 'success' key is empty — no docs extracted")
        logger.debug("Full body:\n%s", json.dumps(body, indent=2)[:1000])
    else:
        logger.info("Found %d supporting doc(s):", len(docs))
        for filename, content in docs.items():
            logger.info("  - %s (%d chars)", filename, len(content))
