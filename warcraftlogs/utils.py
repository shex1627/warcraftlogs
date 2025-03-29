"""
Utility functions for the Warcraft Logs API client.
"""

import base64
import hashlib
import secrets
import string
from typing import Tuple

def generate_pkce_verifier_and_challenge() -> Tuple[str, str]:
    """
    Generate a PKCE code verifier and its corresponding challenge.
    
    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate a random code verifier (between 43-128 chars as per RFC 7636)
    allowed_chars = string.ascii_letters + string.digits + "-._~"
    code_verifier = ''.join(secrets.choice(allowed_chars) for _ in range(128))
    
    # Generate code challenge by hashing the verifier with SHA-256
    code_challenge_digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode().rstrip('=')
    
    return code_verifier, code_challenge


def generate_random_state() -> str:
    """
    Generate a random state parameter for OAuth security.
    
    Returns:
        A random hex string
    """
    return secrets.token_hex(16)

import json
from typing import Dict, List, Any, Union, Optional
from collections import Counter

def parse_json_schema(
    json_data: Union[Dict, List, Any], 
    max_list_items: int = 5, 
    current_depth: int = 0, 
    max_depth: Optional[int] = None,
    indent: str = "  "
) -> str:
    """
    Parse any nested JSON and return a human-readable schema.
    
    Args:
        json_data: The JSON data to parse (dict, list, or primitive value)
        max_list_items: Maximum number of list items to display before truncating
        current_depth: Current recursion depth (used internally)
        max_depth: Maximum recursion depth before truncating
        indent: Indentation string
        
    Returns:
        A string representation of the schema
    """
    # Handle depth limit
    if max_depth is not None and current_depth > max_depth:
        return f"{indent * current_depth}... (truncated at depth {max_depth})"
    
    # Handle different data types
    if isinstance(json_data, dict):
        if not json_data:
            return f"{indent * current_depth}{{}} (empty object)"
            
        result = f"{indent * current_depth}{{\n"
        for key, value in json_data.items():
            result += f"{indent * (current_depth + 1)}\"{key}\": "
            if isinstance(value, (dict, list)):
                result += "\n" + parse_json_schema(
                    value, max_list_items, current_depth + 1, max_depth, indent
                )
            else:
                result += f"{type(value).__name__} ({repr(value) if len(repr(value)) < 50 else repr(value)[:47] + '...'})\n"
        result += f"{indent * current_depth}}}\n"
        return result
        
    elif isinstance(json_data, list):
        if not json_data:
            return f"{indent * current_depth}[] (empty array)\n"
            
        # Analyze list to see if items share schema
        if len(json_data) > max_list_items:
            # Check if all items are of the same type
            types = [type(item) for item in json_data]
            type_counts = Counter(types)
            most_common_type, count = type_counts.most_common(1)[0]
            
            # If all items are dictionaries, check if they share keys
            if most_common_type == dict and count == len(json_data):
                # Get all unique keys
                all_keys = set()
                for item in json_data:
                    all_keys.update(item.keys())
                
                # Count occurrences of each key
                key_counts = Counter()
                for item in json_data:
                    for key in item.keys():
                        key_counts[key] += 1
                
                # Check if keys are consistent
                consistent_keys = [key for key, count in key_counts.items() 
                                  if count >= len(json_data) * 0.8]  # 80% threshold
                
                if consistent_keys:
                    # Create a template object with the consistent keys
                    template = {}
                    for key in consistent_keys:
                        # Use the first item that has this key
                        for item in json_data:
                            if key in item:
                                template[key] = item[key]
                                break
                    
                    result = f"{indent * current_depth}[/* {len(json_data)} items, showing schema only */\n"
                    result += parse_json_schema(
                        template, max_list_items, current_depth + 1, max_depth, indent
                    )
                    result += f"{indent * current_depth}]\n"
                    return result
            
            # If all items are primitive and of the same type
            elif most_common_type not in (dict, list) and count >= len(json_data) * 0.8:
                result = f"{indent * current_depth}[/* {len(json_data)} items of type {most_common_type.__name__} */\n"
                # Show a few examples
                result += f"{indent * (current_depth + 1)}Examples: "
                examples = [repr(item) for item in json_data[:3]]
                result += ", ".join(examples)
                if len(json_data) > 3:
                    result += ", ..."
                result += f"\n{indent * current_depth}]\n"
                return result
        
        # Default list handling (show up to max_list_items)
        result = f"{indent * current_depth}[\n"
        for i, item in enumerate(json_data):
            if i >= max_list_items:
                result += f"{indent * (current_depth + 1)}... ({len(json_data) - max_list_items} more items)\n"
                break
            
            if isinstance(item, (dict, list)):
                result += parse_json_schema(
                    item, max_list_items, current_depth + 1, max_depth, indent
                )
            else:
                result += f"{indent * (current_depth + 1)}{type(item).__name__} ({repr(item) if len(repr(item)) < 50 else repr(item)[:47] + '...'})\n"
        
        result += f"{indent * current_depth}]\n"
        return result
    
    else:
        # Handle primitive values
        return f"{indent * current_depth}{type(json_data).__name__} ({repr(json_data) if len(repr(json_data)) < 50 else repr(json_data)[:47] + '...'})\n"
    