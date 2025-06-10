import re
from typing import List, Dict
from warcraftlogs.client import WarcraftLogsClient


def get_last_fight_id(client: WarcraftLogsClient, report_code: str) -> int:
    """
    Query WarcraftLogs API to get the last fight ID from a report
    
    Parameters:
    -----------
    client : WarcraftLogsClient
        Initialized client for WarcraftLogs API
    report_code : str
        The report code to query
        
    Returns:
    --------
    int
        ID of the last fight in the report
    """
    query = """
    {
      reportData {
        report(code: "%s"
        ) {
          fights(
            killType: Encounters
          ){
            id
            name
            startTime
            endTime
          }
        }
      }
    }
    """ % report_code
    
    response = client.query_public_api(query)
    
    # Extract fights and sort by end time
    fights = response['data']['reportData']['report']['fights']
    sorted_fights = sorted(fights, key=lambda x: x['endTime'])
    
    # Get the ID of the last fight
    last_fight_id = sorted_fights[-1]['id']
    
    return last_fight_id

def extract_report_info(url):
    """Extract report code, fight ID, and source ID from WarcraftLogs URL
    
    Args:
        url (str): WarcraftLogs URL
        
    Returns:
        tuple: (report_code, fight_id, source_id) where:
            - report_code (str): The report code from URL
            - fight_id (int|str): Fight ID as integer, or "last" for last fight
            - source_id (int|None): Source ID if present, else None
    """
    try:
        report_code = re.search(r'/reports/(\w+)', url)
        if not report_code:
            return None, None, None
        report_code = report_code.group(1)
        
        fight_id = re.search(r'fight=(\d+|last)', url)
        if not fight_id:
            return report_code, None, None
        fight_id_value = fight_id.group(1)
        fight_id = int(fight_id_value) if fight_id_value.isdigit() else "last"
        
        source_id = re.search(r'source=(\d+)', url)
        source_id = int(source_id.group(1)) if source_id else None
        
        return report_code, fight_id, source_id
    except Exception:
        return None, None, None

def find_player_id_from_name(fight_player_details, player_name):
    """Find player ID from player name in fight details"""
    for role, player_details in fight_player_details.items():
        for player_detail in player_details:
            if player_detail['name'] == player_name:
                return player_detail['id']
    return None

def get_encounter_info(query_function, report_code, fight_id):
    """
    Get dungeon name and encounter name from a Warcraft Logs report and fight ID.
    
    Args:
        query_function: A function that can query Warcraft Logs GraphQL API
                       Should accept (query_string, variables) and return response dict
        report_code: The report code (string)
        fight_id: The fight ID (integer)
    
    Returns:
        dict: {
            'encounter_name': str,
            'dungeon_name': str,
            'zone_id': int,
            'encounter_id': int,
            'difficulty': int,
            'keystone_level': int or None,
            'fight_type': str  # 'encounter', 'trash', 'unknown'
        }
    """
    
    # GraphQL query to get fight details and zone information
    query = """
    query GetEncounterInfo($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                fights(fightIDs: [$fightId]) {
                    id
                    name
                    encounterID
                    difficulty
                    keystoneLevel
                    kill
                }
                zone {
                    id
                    name
                    encounters {
                        id
                        name
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "code": report_code,
        "fightId": fight_id
    }
    
    try:
        # Execute the query
        response = query_function(query, variables)
        
        # Extract data from response
        report = response.get('data', {}).get('reportData', {}).get('report', {})
        fights = report.get('fights', [])
        zone = report.get('zone', {})
        
        if not fights:
            return {
                'encounter_name': 'Unknown Fight',
                'dungeon_name': 'Unknown Zone',
                'zone_id': None,
                'encounter_id': None,
                'difficulty': None,
                'keystone_level': None,
                'fight_type': 'unknown'
            }
        
        fight = fights[0]  # Should only be one fight since we filtered by ID
        
        # Get basic fight info
        fight_name = fight.get('name', 'Unknown Fight')
        encounter_id = fight.get('encounterID', 0)
        difficulty = fight.get('difficulty')
        keystone_level = fight.get('keystoneLevel')
        
        # Get zone info
        zone_id = zone.get('id')
        zone_name = zone.get('name', 'Unknown Zone')
        
        # Determine if this is an encounter or trash
        if encounter_id == 0:
            fight_type = 'trash'
            encounter_name = fight_name  # For trash, use the fight name directly
        else:
            fight_type = 'encounter'
            # Try to find the encounter name from the zone's encounter list
            encounter_name = fight_name  # Default to fight name
            encounters = zone.get('encounters', [])
            for encounter in encounters:
                if encounter.get('id') == encounter_id:
                    encounter_name = encounter.get('name', fight_name)
                    break
        
        return {
            'encounter_name': encounter_name,
            'dungeon_name': zone_name,
            'zone_id': zone_id,
            'encounter_id': encounter_id,
            'difficulty': difficulty,
            'keystone_level': keystone_level,
            'fight_type': fight_type
        }
        
    except Exception as e:
        print(f"Error querying Warcraft Logs API: {e}")
        return {
            'encounter_name': 'Error',
            'dungeon_name': 'Error',
            'zone_id': None,
            'encounter_id': None,
            'difficulty': None,
            'keystone_level': None,
            'fight_type': 'unknown'
        }
    