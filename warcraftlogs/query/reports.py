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

def get_player_dps_and_ilvl(report_code: str, fight_id: int, query_graphql_func) -> dict:
    """
    Get DPS and item level information for all players in a specific fight
    
    Args:
        report_code: Warcraft Logs report code (e.g., "dnwvbGp2A9ZmXFy7")
        fight_id: Fight ID number (e.g., 1)
        query_graphql_func: Function that takes (query, variables) and returns GraphQL response
        
    Returns:
        Dictionary with fight info and player data:
        {
            'fight_id': int,
            'name': str,
            'duration_minutes': float,
            'encounter_id': int,
            'difficulty': int,
            'keystone_level': int or None,
            'players': [
                {
                    'name': str,
                    'class_spec': str,
                    'item_level': int,
                    'total_damage': int,
                    'dps': float,
                    'active_time_minutes': float,
                    'top_abilities': [{'name': str, 'total': int, 'type': int}, ...]
                }, ...
            ]
        }
    """
    
    query = """
    query GetPlayerDPSAndItemLevel($code: String!, $fightID: Int!) {
      reportData {
        report(code: $code) {
          fights(fightIDs: [$fightID]) {
            id
            name
            startTime
            endTime
            encounterID
            difficulty
            keystoneLevel
          }
          
          table(
            fightIDs: [$fightID]
            dataType: DamageDone
            viewBy: Source
            hostilityType: Friendlies
          )
        }
      }
    }
    """
    
    variables = {
        "code": report_code,
        "fightID": fight_id
    }
    
    # Execute the query using the provided function
    result = query_graphql_func(query, variables)
    
    # Parse the response
    report_data = result['data']['reportData']['report']
    fight_data = report_data['fights'][0]
    table_data = report_data['table']['data']['entries']
    
    # Calculate fight duration
    duration_ms = fight_data['endTime'] - fight_data['startTime']
    duration_seconds = duration_ms / 1000
    duration_minutes = duration_seconds / 60
    
    # Process player data
    players = []
    
    for player in table_data:
        # Extract class and spec from icon field
        icon = player.get('icon', '')
        class_spec = icon.replace('-', ' ') if icon else f"{player['type']} (Unknown Spec)"
        
        # Calculate DPS
        total_damage = player['total']
        dps = total_damage / duration_seconds if duration_seconds > 0 else 0
        
        # Calculate active time in minutes
        active_time_ms = player.get('activeTime', 0)
        active_time_minutes = active_time_ms / (1000 * 60)
        
        # Get top 5 abilities
        top_abilities = player.get('abilities', [])#[:top_abilities_ct]
        
        player_dict = {
            'name': player['name'],
            'class_spec': class_spec,
            'item_level': player.get('itemLevel', 0),
            'total_damage': total_damage,
            'dps': round(dps, 0),
            'active_time_minutes': round(active_time_minutes, 1),
            'top_abilities': top_abilities
        }
        
        players.append(player_dict)
    
    # Sort players by DPS (descending)
    players.sort(key=lambda p: p['dps'], reverse=True)
    
    # Create fight info dictionary
    fight_info = {
        'fight_id': fight_data['id'],
        'name': fight_data['name'],
        'duration_minutes': round(duration_minutes, 1),
        'encounter_id': fight_data['encounterID'],
        'difficulty': fight_data.get('difficulty', 0),
        'keystone_level': fight_data.get('keystoneLevel'),
        'players': players
    }
    
    return fight_info
