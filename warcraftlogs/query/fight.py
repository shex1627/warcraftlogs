import pandas as pd
from typing import Optional, Dict, Any
from warcraftlogs.client import WarcraftLogsClient

def get_fight_duration(client: WarcraftLogsClient, report_code, fight_id):
    """
    Get the duration of a fight in seconds.
    
    Args:
        client: Object with query_public_api method
        report_code: String - The report code
        fight_id: Integer - The fight ID
    
    Returns:
        Float - Fight duration in seconds
    """
    
    fight_query = """
    query GetFightInfo($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                fights(fightIDs: [$fightId]) {
                    id
                    startTime
                    endTime
                }
            }
        }
    }
    """
    
    variables = {"code": report_code, "fightId": fight_id}
    
    try:
        result = client.query_public_api(fight_query, variables)
        fights = result.get('data', {}).get('reportData', {}).get('report', {}).get('fights', [])
        
        if fights:
            fight = fights[0]
            start_time = fight.get('startTime', 0)
            end_time = fight.get('endTime', 0)
            
            # Convert from milliseconds to seconds
            duration_seconds = (end_time - start_time) / 1000.0
            #print(f"Fight duration: {start_time} to {end_time} = {duration_seconds} seconds")
            return duration_seconds
            
    except Exception as e:
        print(f"Error getting fight duration: {e}")
        import traceback
        traceback.print_exc()
    
    print("Returning fallback duration of 1 second")
    return 1

def get_damage_breakdown(report_code: str, fight_id: int, player_name: str, 
                        client) -> pd.DataFrame:
    """
    Get damage breakdown for a specific player in a WarcraftLogs fight.
    
    Args:
        report_code: WarcraftLogs report code (e.g., "Wbcf3HZxjdrTyQqJ")
        fight_id: Fight ID number
        player_name: Player name to analyze
        client: Function to query the WarcraftLogs API (should return JSON response)
        
    Returns:
        pandas.DataFrame with columns: ability_name, total_damage, damage_percent, dps, hit_count, 
        crit_count, crit_rate, avg_damage, avg_hit, avg_crit, uses
    """
    
    # First, get fight details and player information
    fight_query = """
    query($code: String!, $fightID: Int!) {
      reportData {
        report(code: $code) {
          fights(fightIDs: [$fightID]) {
            startTime
            endTime
            name
          }
          playerDetails(fightIDs: [$fightID])
        }
      }
    }
    """
    
    fight_variables = {"code": report_code, "fightID": fight_id}
    fight_response = client.query_public_api(fight_query, fight_variables)
    
    # Extract fight duration
    fight_data = fight_response['data']['reportData']['report']['fights'][0]
    fight_duration = (fight_data['endTime'] - fight_data['startTime']) / 1000.0
    
    # Find player ID from playerDetails
    player_details = fight_response['data']['reportData']['report']['playerDetails']['data']['playerDetails']
    player_id = None
    
    # Search through all player categories
    for category in ['tanks', 'healers', 'dps']:
        for player in player_details.get(category, []):
            if player['name'] == player_name:
                player_id = player['id']
                break
        if player_id:
            break
    
    if not player_id:
        raise ValueError(f"Player '{player_name}' not found in fight {fight_id}")
    
    # Get damage breakdown for the specific player
    damage_query = """
    query($code: String!, $fightID: Int!, $sourceID: Int!) {
      reportData {
        report(code: $code) {
          table(
            fightIDs: [$fightID]
            dataType: DamageDone
            viewBy: Ability
            sourceID: $sourceID
          )
        }
      }
    }
    """
    
    damage_variables = {"code": report_code, "fightID": fight_id, "sourceID": player_id}
    damage_response = client.query_public_api(damage_query, damage_variables)
    
    # Extract ability data
    abilities = damage_response['data']['reportData']['report']['table']['data']['entries']
    
    # Calculate total damage for percentage calculations
    total_damage_all_abilities = sum(ability['total'] for ability in abilities if ability['total'] > 0)
    
    # Process each ability into DataFrame format
    damage_data = []
    
    for ability in abilities:
        # Skip abilities with no damage
        if ability['total'] == 0:
            continue
            
        # Calculate basic stats
        total_damage = ability['total']
        damage_percent = (total_damage / total_damage_all_abilities * 100) if total_damage_all_abilities > 0 else 0
        dps = total_damage / fight_duration
        hit_count = ability['hitCount']
        crit_count = ability['critHitCount']
        uses = ability.get('uses', 0)
        
        # Calculate averages
        avg_damage = total_damage / hit_count if hit_count > 0 else 0
        crit_rate = (crit_count / hit_count * 100) if hit_count > 0 else 0
        
        # Extract hit details for average hit and crit damage
        avg_hit = 0
        avg_crit = 0
        
        for hit_detail in ability.get('hitdetails', []):
            if hit_detail['type'] == 'Hit' and hit_detail['count'] > 0:
                avg_hit = hit_detail['total'] / hit_detail['count']
            elif hit_detail['type'] == 'Critical Hit' and hit_detail['count'] > 0:
                avg_crit = hit_detail['total'] / hit_detail['count']
        
        damage_data.append({
            'ability_name': ability['name'],
            'total_damage': total_damage,
            'damage_percent': round(damage_percent, 1),
            'dps': round(dps, 0),
            'hit_count': hit_count,
            'crit_count': crit_count,
            'crit_rate': round(crit_rate, 1),
            'avg_damage': round(avg_damage, 0),
            'avg_hit': round(avg_hit, 0),
            'avg_crit': round(avg_crit, 0),
            'uses': uses
        })
    
    # Create DataFrame and sort by total damage (descending)
    df = pd.DataFrame(damage_data)
    df = df.sort_values('total_damage', ascending=False).reset_index(drop=True)
    
    return df

def get_cast_breakdown(report_code: str, fight_id: int, player_name: str, 
                      query_graphql_func) -> pd.DataFrame:
    """
    Get cast breakdown for a specific player in a WarcraftLogs fight.
    
    Args:
        report_code: WarcraftLogs report code (e.g., "Wbcf3HZxjdrTyQqJ")
        fight_id: Fight ID number
        player_name: Player name to analyze
        query_graphql_func: Function that executes GraphQL queries against WarcraftLogs API
        
    Returns:
        pandas.DataFrame with columns: ability_id, ability_name, total_casts, casts_per_minute
    """
    
    # Get fight details and player information
    fight_query = """
    query($code: String!, $fightID: Int!) {
      reportData {
        report(code: $code) {
          fights(fightIDs: [$fightID]) {
            startTime
            endTime
            name
          }
          playerDetails(fightIDs: [$fightID])
        }
      }
    }
    """
    
    fight_variables = {"code": report_code, "fightID": fight_id}
    fight_response = query_graphql_func(fight_query, fight_variables)
    
    # Extract fight duration
    fight_data = fight_response['data']['reportData']['report']['fights'][0]
    fight_duration_ms = fight_data['endTime'] - fight_data['startTime']
    fight_duration_seconds = fight_duration_ms / 1000
    fight_duration_minutes = fight_duration_ms / (1000 * 60)
    
    # Find player ID
    player_details = fight_response['data']['reportData']['report']['playerDetails']['data']['playerDetails']
    player_id = None
    
    for category in ['tanks', 'healers', 'dps']:
        for player in player_details.get(category, []):
            if player['name'] == player_name:
                player_id = player['id']
                break
        if player_id:
            break
    
    if not player_id:
        raise ValueError(f"Player '{player_name}' not found in fight {fight_id}")
    
    # Get cast data
    cast_query = """
    query($code: String!, $fightID: Int!, $sourceID: Int!) {
      reportData {
        report(code: $code) {
          table(
            fightIDs: [$fightID]
            dataType: Casts
            viewBy: Ability
            sourceID: $sourceID
          )
        }
      }
    }
    """
    
    cast_variables = {"code": report_code, "fightID": fight_id, "sourceID": player_id}
    cast_response = query_graphql_func(cast_query, cast_variables)
    
    # Process cast data
    casts = cast_response['data']['reportData']['report']['table']['data']['entries']
    cast_data = []
    
    for cast in casts:
        total_casts = cast['total']
        casts_per_minute = total_casts / fight_duration_minutes if fight_duration_minutes > 0 else 0
        
        # Extract ability ID - this is typically found in the 'guid' field for casts
        ability_id = cast.get('guid', cast.get('abilityGameID', None))
        
        cast_data.append({
            'ability_id': ability_id,
            'ability_name': cast['name'],
            'total_casts': total_casts,
            'casts_per_minute': round(casts_per_minute, 2)
        })
    
    # Create DataFrame and sort by total casts
    df = pd.DataFrame(cast_data)
    df = df.sort_values('total_casts', ascending=False).reset_index(drop=True)
    
    return df


def get_buff_uptime(report_code: str, fight_id: int, player_name: str, 
                   query_graphql_func) -> pd.DataFrame:
    """
    Get buff uptime breakdown for a specific player in a WarcraftLogs fight.
    
    Args:
        report_code: WarcraftLogs report code (e.g., "Wbcf3HZxjdrTyQqJ")
        fight_id: Fight ID number
        player_name: Player name to analyze
        query_graphql_func: Function that executes GraphQL queries against WarcraftLogs API
        
    Returns:
        pandas.DataFrame with columns: buff_name, total_uptime_seconds, uptime_percentage, 
        total_applications, avg_duration_seconds, max_stacks
    """
    
    # Get fight details and player information
    fight_query = """
    query($code: String!, $fightID: Int!) {
      reportData {
        report(code: $code) {
          fights(fightIDs: [$fightID]) {
            startTime
            endTime
            name
          }
          playerDetails(fightIDs: [$fightID])
        }
      }
    }
    """
    
    fight_variables = {"code": report_code, "fightID": fight_id}
    fight_response = query_graphql_func(fight_query, fight_variables)
    
    # Extract fight duration
    fight_data = fight_response['data']['reportData']['report']['fights'][0]
    fight_duration_ms = fight_data['endTime'] - fight_data['startTime']
    
    # Find player ID
    player_details = fight_response['data']['reportData']['report']['playerDetails']['data']['playerDetails']
    player_id = None
    
    for category in ['tanks', 'healers', 'dps']:
        for player in player_details.get(category, []):
            if player['name'] == player_name:
                player_id = player['id']
                break
        if player_id:
            break
    
    if not player_id:
        raise ValueError(f"Player '{player_name}' not found in fight {fight_id}")
    
    # Get buff data
    buff_query = """
    query($code: String!, $fightID: Int!, $sourceID: Int!) {
      reportData {
        report(code: $code) {
          table(
            fightIDs: [$fightID]
            dataType: Buffs
            viewBy: Ability
            sourceID: $sourceID
          )
        }
      }
    }
    """
    
    buff_variables = {"code": report_code, "fightID": fight_id, "sourceID": player_id}
    buff_response = query_graphql_func(buff_query, buff_variables)
    
    # Process buff data
    auras = buff_response['data']['reportData']['report']['table']['data']['auras']
    buff_data = []
    
    for aura in auras:
        total_uptime_ms = aura['totalUptime']
        total_uptime_seconds = total_uptime_ms / 1000
        uptime_percentage = (total_uptime_ms / fight_duration_ms * 100) if fight_duration_ms > 0 else 0
        total_applications = aura['totalUses']
        avg_duration_seconds = total_uptime_seconds / total_applications if total_applications > 0 else 0
        
        # Calculate max stacks if available (some buffs have stacking)
        max_stacks = 1  # Default for non-stacking buffs
        # Note: Stack information would need additional API calls if needed
        
        buff_data.append({
            'buff_name': aura['name'],
            'total_uptime_seconds': round(total_uptime_seconds, 1),
            'uptime_percentage': round(uptime_percentage, 2),
            'total_applications': total_applications,
            'avg_duration_seconds': round(avg_duration_seconds, 1),
            'max_stacks': max_stacks
        })
    
    # Create DataFrame and sort by uptime percentage
    df = pd.DataFrame(buff_data)
    df = df.sort_values('uptime_percentage', ascending=False).reset_index(drop=True)
    
    return df
