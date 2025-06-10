from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import json 
import warcraftlogs
from warcraftlogs.constants import TOKEN_DIR, SCHEMA_LOCATION
import logging
from warcraftlogs import WarcraftLogsClient
import json

EXPERIENCE_PATH = "/Users/shadowclone/Desktop/Code/warcraftlogs/warcraftlogs/data/experience.json"
GENERAL_EXPERIENCE_PATH = "/Users/shadowclone/Desktop/Code/warcraftlogs/warcraftlogs/data/general_experience.json"

logger = logging.getLogger(__name__)

client = WarcraftLogsClient(token_dir=TOKEN_DIR)

# Initialize FastMCP server
mcp = FastMCP("warcraftlogs")

@mcp.tool()
def get_schema() -> str:
    """get the schema of the warcraftlogs graphql api"""
    with open(SCHEMA_LOCATION, 'r') as f:
        schema = json.load(f)
    return str(schema)

@mcp.tool()
def query_warcraflogs_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None, 
                              trunct=3000) -> Dict[str, Any]:
    """
    Execute a query against the public API.
    Automatically handles token management.
    
    Args:
        query: GraphQL query string
        variables: Optional variables for the query
        trunct: Length of the response to truncate to (default 3000) to avoid long responses
        
    Returns:
        Dict containing the GraphQL response
    """
    try:
        response = client.query_public_api(query, variables)
        # Check if the response is too long
        response_str = str(response)
        if len(response_str) > trunct:
            logger.warning("Response is too long, truncating...")
            response_text = response_str[:trunct]
        else:
            response_text = response_str
        return response_text
    except Exception as e:
        logger.error(f"Error querying WarcraftLogs API: {e}")
        return {"error": str(e)}
    
@mcp.tool()
def record_experience(self, user_question: str, method: str) -> None:
    """
    Record the method to a user question in the experience file. Make sure to include all the important details
    so you don't make the same mistake again.

    Args:
        user_question: The user's question
        method: The method used to answer the question
    """
    try:
        # load the experience file, create file if it doesn't exist
        try:
            with open(EXPERIENCE_PATH, 'r') as f:
                experience = json.load(f)
        except FileNotFoundError:
            experience = {}
        # create the experience entry
        experience_entry = {
            "user_question": user_question,
            "method": method
        }
        # add the experience entry to the experience file
        if user_question not in experience:
            experience[user_question] = []
        experience[user_question].append(experience_entry)
        # write the experience file
        with open(EXPERIENCE_PATH, 'w') as f:
            json.dump(experience, f, indent=4)
    except Exception as e:
        logger.error(f"Error recording experience: {e}")
        raise e
    
@mcp.tool()
def record_general_experience(self, general_experiences: list[str]) -> None:
    """
    Record good information/experience/tips to know about the warcraftlogs api. This is useful for making accurate
    queries.
    It should be general information.
    Example:
        zone 43 is mythic+ dungeon
        bracket is key stone level
        You can query page number to get runs from an older date
    Not example:
        Blistering Spite (472220) and Galvanized Spite (472223) are opening mechanics. (specific to a fight and no context of what the fight is and who use those abilities)

    Args:
        general_experience: good information to know about the warcraftlogs api
    """
    try:
        # load the experience file, create file if it doesn't exist
        try:
            with open(GENERAL_EXPERIENCE_PATH, 'r') as f:
                experience = json.load(f)
        except FileNotFoundError:
            experience = {}
        # create the experience entry
        experience.extend(general_experiences)
        with open(GENERAL_EXPERIENCE_PATH, 'w') as f:
            json.dump(experience, f, indent=4)
    except Exception as e:
        logger.error(f"Error recording general experience: {e}")
        raise e
    
@mcp.tool()
def get_general_experience(self) -> Optional[Dict[str, Any]]:
    """
    Get records of good information to know about the warcraftlogs api. Read this to before making a plan
    to answer a question.

    Returns:
        a list of good information to know about the warcraftlogs api
    """
    try:
        # load the experience file
        with open(GENERAL_EXPERIENCE_PATH, 'r') as f:
            experience = json.load(f)
        # return the experience
        return experience
    except Exception as e:
        logger.error(f"Error getting general experience: {e}")
        raise e

@mcp.tool()
def get_experience(self) -> Optional[Dict[str, Any]]:
    """
    Get records of how AI answered pass user questions to help answer current user questions.

    Returns:
        Dict containing the experience for the user question
    """
    try:
        # load the experience file
        with open(EXPERIENCE_PATH, 'r') as f:
            experience = json.load(f)
        # return the experience
        return experience
    except Exception as e:
        logger.error(f"Error getting experience: {e}")
        raise e

if __name__ == "__main__":
    # Initialize and run the server
    logger = logging.getLogger("mcp")
    print("Starting MCP server...")
    logger.info("Starting MCP server...")
    mcp.run(transport='stdio')
