import pandas as pd
from tqdm import tqdm
from typing import Dict, List
import traceback
import json
from warcraftlogs.client import WarcraftLogsClient
from warcraftlogs.ability_data_manager import AbilityDataManager

def fetch_events(client, report_code: str, fight_id: int, data_type: str, 
                start_time: int = None, end_time: int = None, 
                limit: int = 1000, max_pages: int = 30, **kwargs) -> pd.DataFrame:
    """
    Fetch events from WarcraftLogs API with automatic pagination
    
    Parameters:
    -----------
    client : WarcraftLogsClient
        Client instance for querying the API
    report_code : str
        The report code to query
    fight_id : int
        The fight ID to query
    data_type : str
        Event data type (e.g., 'Casts', 'Buffs', 'Damage', etc.)
    start_time : int, optional
        Start time in milliseconds (relative to report start)
    end_time : int, optional
        End time in milliseconds (relative to report start)
    limit : int, optional
        Number of events per page (default 1000, max 10000)
    max_pages : int, optional
        Maximum number of pages to fetch (default 30)
    **kwargs : dict
        Additional query parameters (e.g., sourceID, targetID, etc.)
    
    Returns:
    --------
    pd.DataFrame
        DataFrame containing all events
    """
    def generate_query(page_start_time=None):
        # Build filter string from kwargs and optional parameters
        filters = []
        if page_start_time is not None:
            filters.append(f"startTime: {page_start_time}")
        if end_time is not None:
            filters.append(f"endTime: {end_time}")
        for key, value in kwargs.items():
            filters.append(f"{key}: {value}")
        
        filter_string = "\n".join(filters)
        
        return """
        {
          reportData {
            report(code: "%s") {
              events(
                fightIDs: [%d]
                dataType: %s
                limit: %d
                %s
              ) {
                data
                nextPageTimestamp
              }
            }
          }
        }
        """ % (report_code, fight_id, data_type, limit, filter_string)

    # Initialize variables for pagination
    all_events = []
    page_counter = 0
    next_timestamp = start_time

    # Fetch initial fight info to get end time if not provided
    if end_time is None:
        fight_query = """
        {
          reportData {
            report(code: "%s") {
              fights(fightIDs: [%d]) {
                startTime
                endTime
              }
            }
          }
        }
        """ % (report_code, fight_id)
        fight_info = client.query_public_api(fight_query)
        start_time = fight_info['data']['reportData']['report']['fights'][0]['startTime']
        end_time = fight_info['data']['reportData']['report']['fights'][0]['endTime']

    with tqdm(total=max_pages, desc=f"Fetching {data_type} events") as pbar:
        while True:
            # Break if we've hit the page limit
            if page_counter >= max_pages:
                print(f"Reached maximum page limit of {max_pages}")
                break

            # Query current page
            response = client.query_public_api(generate_query(next_timestamp))
            events_data = response['data']['reportData']['report']['events']
            
            # Add events to our collection
            current_events = events_data['data']
            all_events.extend(current_events)
            
            # Update pagination info
            next_timestamp = events_data['nextPageTimestamp']
            page_counter += 1
            pbar.update(1)
            
            # Break if we've reached the end
            if next_timestamp is None or next_timestamp >= end_time:
                break

    # Convert to DataFrame
    if all_events:
        df = pd.json_normalize(all_events)
        # Convert timestamp to relative time in seconds
        #cast_info_df['timestamp_seconds'] = (cast_info_df['timestamp'] - startTime) / 1000.0
        #cast_info_df['timestamp_readable'] = pd.to_datetime(cast_info_df['timestamp_seconds'], unit='s').dt.strftime('%H:%M:%S')


        if 'timestamp' in df.columns:
            df['timestamp_seconds'] = (df['timestamp'] - start_time) / 1000.0
            df['timestamp_readable'] = pd.to_datetime(df['timestamp_seconds'], unit='s').dt.strftime('%H:%M:%S')
        return df
    else:
        return pd.DataFrame()

def augment_events_df(cast_info_df: pd.DataFrame, id_to_name_dict: Dict={}, 
                    ability_data_manager: AbilityDataManager=None, ability_id_to_name_dict: Dict={}) -> pd.DataFrame:
    """AbilityDataManager
    """
    # add sourceName and targetName
    if id_to_name_dict:
        cast_info_df['sourceName'] = cast_info_df['sourceID'].apply(lambda x: id_to_name_dict.get(x, f"{x}_Unknown"))
        cast_info_df['targetName'] = cast_info_df['targetID'].apply(lambda x: id_to_name_dict.get(x, f"{x}_Unknown"))

    # for cast events, add abilityName
    if ability_data_manager:
        ability_ids = cast_info_df['abilityGameID'].unique().tolist()
        ability_mapping_df = ability_data_manager.get_abilities(ability_ids)
        ability_id_to_name_dict = dict(zip(ability_mapping_df['id'], ability_mapping_df['name']))

    # for cast events, add abilityName
    if ability_id_to_name_dict:
        cast_info_df['abilityName'] = cast_info_df['abilityGameID'].apply(lambda x: ability_id_to_name_dict.get(x, f"{x}_Unknown"))

    # prefix targetName if targetInstanceID is not null to indicate the target is an instance of an actor (e.g. a pet or a totem)
    if 'targetInstance' in cast_info_df.columns:
        cast_info_df['targetName'] = cast_info_df.apply(
            lambda row: f"{row['targetName']}_{int(row['targetInstance'])}" if pd.notna(row['targetInstance']) and row['targetInstance'] != 0 
            else row['targetName'], axis=1
        )
    
    if 'sourceInstance' in cast_info_df.columns:
        # prefix sourceName if sourceInstanceID is not null to indicate the source is an instance of an actor (e.g. a pet or a totem)
        cast_info_df['sourceName'] = cast_info_df.apply(
            lambda row: f"{row['sourceName']}_{int(row['sourceInstance'])}" if pd.notna(row['sourceInstance']) and row['sourceInstance'] != 0 
            else row['sourceName'], axis=1
        )

    return cast_info_df

def get_buff_info_df(buff_info: list):
    try:
        total_time = buff_info['totalTime']    
        buff_info_df = pd.DataFrame(buff_info['auras'])
        buff_info_df['total_time'] = total_time
        buff_info_df['up_time_pct'] = buff_info_df['totalUptime'] / total_time
        # round up_time_pct to 2 decimal places
        buff_info_df['up_time_pct'] = buff_info_df['up_time_pct'].round(2)
        # put ['name', 'up_time_pct'] in the first two columns and keep the rest of the columns in the same order
        buff_info_df = buff_info_df[['name', 'up_time_pct'] + [col for col in buff_info_df.columns if col not in ['name', 'up_time_pct']]]
        return buff_info_df
    except Exception as e:
        traceback.print_exc()
        print(f"Error in get_buff_info_df: {e}")
        return pd.DataFrame()

def get_damage_info_df(damage_data: dict, metric_type: str='dps'):
    try:
        damage_total_time = damage_data['totalTime']
        damage_info_df = pd.DataFrame(damage_data['entries'])
        damage_info_df[metric_type] = (damage_info_df['total']/damage_total_time*1000).round(0)
        if 'critHitCount' in damage_info_df.columns:
            damage_info_df['crit_pct'] = (damage_info_df['critHitCount']/damage_info_df['hitCount']).round(2)*100

        damage_info_df['hit_per_minute'] = (damage_info_df['hitCount']/damage_total_time*1000*60).round(2)
        return damage_info_df
    except KeyError:
        print("KeyError: 'totalTime' not found in damage_data")
        return pd.DataFrame()
    
def get_metric_info_df(damage_data: dict, metric_type: str='dps'):
    try:
        metric_total_time = damage_data['totalTime']
        metric_info_df = pd.DataFrame(damage_data['entries'])
        metric_info_df[metric_type] = (metric_info_df['total']/metric_total_time*1000).round(0)
        if 'critHitCount' in metric_info_df.columns:
            metric_info_df['crit_pct'] = (metric_info_df['critHitCount']/metric_info_df['hitCount']).round(2)*100
        metric_info_df['hit_per_minute'] = (metric_info_df['hitCount']/metric_total_time*1000*60).round(2)
        return metric_info_df
    except KeyError:
        print("KeyError: 'totalTime' not found")
        return pd.DataFrame()
    
def get_cast_info_df(cast_data_resp):
    try:
        cast_data_df = pd.DataFrame(cast_data_resp['entries'])
        total_time = cast_data_resp['totalTime']
        cast_data_df['total_time'] = total_time
        cast_data_df['cast_per_minute'] = cast_data_df['total'] / (total_time / 1000 / 60)
        return cast_data_df
    except KeyError:
        print("KeyError: 'totalTime' not found in cast_data_resp")
        return pd.DataFrame()

def get_ability_cast_events(report_id: str, fight_id: int, character_name: str, abilities: list, query_graphql_func):
    """
    Get individual cast events with timestamps for specific abilities for a character in a fight.
    
    Args:
        report_id (str): The WarcraftLogs report code (e.g., "ABC123DEF")
        fight_id (int): The specific fight ID within the report
        character_name (str): The character name to search for (case-insensitive)
        abilities (list): List of ability names (str) or ability IDs (int), or mixed list
                         Examples: ["Thrash", "Moonfire"] or [77758, 8921] or ["Thrash", 8921]
        query_graphql_func: Function that executes GraphQL queries against WarcraftLogs API.
                           Should have signature: query_graphql_func(query_string, variables_dict) -> dict
        
    Returns:
        dict: Contains cast events data with the following structure:
        {
            'fight_duration_seconds': float,
            'fight_info': {
                'id': int,
                'name': str,
                'start_time': float,
                'end_time': float
            },
            'character_info': {
                'id': int,
                'name': str,
                'type': str,  # class
                'server': str
            },
            'cast_events': [
                {
                    'time_formatted': str,  # e.g., "00:12.602"
                    'timestamp_ms': int,    # relative to fight start
                    'type': str,           # "Cast"
                    'ability_name': str,
                    'ability_id': int,
                    'source': str,         # character name
                    'target': str,         # target name (if any)
                    'icon': str
                }
            ],
            'abilities_found': list[str],
            'abilities_not_found': list[str],
            'ability_ids_used': list[int],
            'total_events': int
        }
        
    Raises:
        ValueError: If report, fight, or character not found
        Exception: If GraphQL query fails or returns unexpected data
        
    Example:
        # Using ability names
        result = get_ability_cast_events(
            report_id="Wbcf3HZxjdrTyQqJ",
            fight_id=1, 
            character_name="Shexclaw",
            abilities=["Thrash", "Moonfire"],
            query_graphql_func=your_graphql_client
        )
        
        # Using ability IDs
        result = get_ability_cast_events(
            report_id="Wbcf3HZxjdrTyQqJ",
            fight_id=1, 
            character_name="Shexclaw",
            abilities=[77758, 8921],
            query_graphql_func=your_graphql_client
        )
        
        # Mixed names and IDs
        result = get_ability_cast_events(
            report_id="Wbcf3HZxjdrTyQqJ",
            fight_id=1, 
            character_name="Shexclaw",
            abilities=["Thrash", 8921],
            query_graphql_func=your_graphql_client
        )
    """
    
    # Step 1: Get fight duration and validate fight exists
    fight_query = """
    query GetFightInfo($reportCode: String!, $fightID: Int!) {
        reportData {
            report(code: $reportCode) {
                fights(fightIDs: [$fightID]) {
                    id
                    startTime
                    endTime
                    name
                }
            }
        }
    }
    """
    
    try:
        fight_result = query_graphql_func(
            fight_query, 
            {"reportCode": report_id, "fightID": fight_id}
        )
        
        if not fight_result.get('data', {}).get('reportData', {}).get('report'):
            raise ValueError(f"Report {report_id} not found")
            
        fights = fight_result['data']['reportData']['report']['fights']
        if not fights:
            raise ValueError(f"Fight {fight_id} not found in report {report_id}")
            
        fight_info = fights[0]
        fight_duration_ms = fight_info['endTime'] - fight_info['startTime']
        fight_duration_seconds = fight_duration_ms / 1000.0
        
        # Store fight info for result
        fight_data = {
            'id': fight_info['id'],
            'name': fight_info['name'],
            'start_time': fight_info['startTime'],
            'end_time': fight_info['endTime']
        }
        
    except Exception as e:
        raise Exception(f"Failed to get fight information: {str(e)}")
    
    # Step 2: Get master data to find character ID and ability mappings
    master_data_query = """
    query GetMasterData($reportCode: String!) {
        reportData {
            report(code: $reportCode) {
                masterData {
                    actors(type: "Player") {
                        id
                        name
                        type
                        server
                    }
                    abilities {
                        gameID
                        name
                        icon
                    }
                }
            }
        }
    }
    """
    
    try:
        master_result = query_graphql_func(
            master_data_query,
            {"reportCode": report_id}
        )
        
        master_data = master_result['data']['reportData']['report']['masterData']
        actors_data = master_data['actors']
        abilities_data = master_data['abilities']
        
        # Find the character by name (case-insensitive)
        character_info = None
        player_id = None
        
        for actor in actors_data:
            if actor['name'] and actor['name'].lower() == character_name.lower():
                character_info = {
                    'id': actor['id'],
                    'name': actor['name'],
                    'type': actor.get('type', ''),
                    'server': actor.get('server', '')
                }
                player_id = actor['id']
                break
        
        if not character_info:
            available_players = [actor['name'] for actor in actors_data if actor['name']][:10]
            print(f"Character '{character_name}' not found. Available players: {available_players}")
            raise ValueError(f"Character '{character_name}' not found in report {report_id}")
        
        # Create mapping of ability names to game IDs and game IDs to info
        ability_name_to_id = {}
        ability_id_to_info = {}
        
        for ability in abilities_data:
            if ability['name']:  # Skip abilities without names
                ability_name_to_id[ability['name'].lower()] = ability['gameID']
            
            ability_id_to_info[ability['gameID']] = {
                'name': ability['name'],
                'icon': ability.get('icon', '')
            }
        
        # Process input abilities (can be names, IDs, or mixed)
        target_ability_ids = []
        abilities_found = []
        abilities_not_found = []
        
        for ability in abilities:
            if isinstance(ability, int):
                # It's an ability ID
                if ability in ability_id_to_info:
                    target_ability_ids.append(ability)
                    ability_name = ability_id_to_info[ability]['name'] or f"Ability {ability}"
                    abilities_found.append(ability_name)
                else:
                    abilities_not_found.append(f"ID:{ability}")
                    print(f"Warning: Ability ID {ability} not found in report master data")
            
            elif isinstance(ability, str):
                # It's an ability name
                name_lower = ability.lower()
                if name_lower in ability_name_to_id:
                    game_id = ability_name_to_id[name_lower]
                    target_ability_ids.append(game_id)
                    abilities_found.append(ability)
                else:
                    abilities_not_found.append(ability)
                    print(f"Warning: Ability '{ability}' not found in report master data")
            
            else:
                print(f"Warning: Invalid ability type {type(ability)}: {ability}. Must be string (name) or int (ID)")
                abilities_not_found.append(str(ability))
        
        if not target_ability_ids:
            print("No valid abilities found in master data.")
            if abilities_data:
                print("Available abilities (sample):")
                sample_abilities = [(a['gameID'], a['name']) for a in abilities_data if a['name']][:10]
                for aid, aname in sample_abilities:
                    print(f"  ID {aid}: {aname}")
            raise ValueError("None of the specified abilities were found in the report")
            
    except Exception as e:
        raise Exception(f"Failed to get master data: {str(e)}")
    
    # Step 3: Query cast events with ability filter
    if target_ability_ids:
        # Create filter expression for specific abilities
        ability_ids_str = ', '.join(map(str, target_ability_ids))
        filter_expression = f"ability.id in ({ability_ids_str})"
    else:
        filter_expression = None
    
    events_query = """
    query GetCastEvents($reportCode: String!, $fightID: Int!, $playerID: Int!, $filterExpr: String) {
        reportData {
            report(code: $reportCode) {
                events(
                    dataType: Casts
                    fightIDs: [$fightID]
                    sourceID: $playerID
                    filterExpression: $filterExpr
                    limit: 10000
                ) {
                    data
                }
            }
        }
    }
    """
    
    try:
        events_variables = {
            "reportCode": report_id,
            "fightID": fight_id,
            "playerID": player_id,
            "filterExpr": filter_expression
        }
        
        # Remove null filter expression to avoid GraphQL issues
        if filter_expression is None:
            del events_variables["filterExpr"]
            events_query = """
            query GetCastEvents($reportCode: String!, $fightID: Int!, $playerID: Int!) {
                reportData {
                    report(code: $reportCode) {
                        events(
                            dataType: Casts
                            fightIDs: [$fightID]
                            sourceID: $playerID
                            limit: 10000
                        ) {
                            data
                        }
                    }
                }
            }
            """
        
        events_result = query_graphql_func(events_query, events_variables)
        
        events_data = events_result['data']['reportData']['report']['events']
        
        if not events_data or 'data' not in events_data:
            raise ValueError(f"No cast events found for character '{character_name}' in fight {fight_id}")
            
    except Exception as e:
        raise Exception(f"Failed to get cast events: {str(e)}")
    
    # Step 4: Process the cast events
    def format_timestamp(timestamp_ms):
        """Convert milliseconds to MM:SS.mmm format"""
        total_seconds = timestamp_ms / 1000.0
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:06.3f}"
    
    def get_target_name(event, actors_data):
        """Get target name from target ID"""
        target_id = event.get('targetID')
        if target_id and target_id != -1:  # -1 means "Environment" or no specific target
            for actor in actors_data:
                if actor['id'] == target_id:
                    return actor.get('name', 'Unknown')
        return None
    
    cast_events = []
    
    # Process events
    events_list = events_data['data']
    
    for event in events_list:
        ability_id = event.get('abilityGameID')
        
        if ability_id and ability_id in ability_id_to_info:
            ability_info = ability_id_to_info[ability_id]
            timestamp_ms = event.get('timestamp', 0)
            
            # Get target name if available
            target_name = get_target_name(event, actors_data)
            
            cast_event = {
                'time_formatted': format_timestamp(timestamp_ms),
                'timestamp_ms': timestamp_ms,
                'type': 'Cast',
                'ability_name': ability_info['name'] or f"Ability {ability_id}",
                'ability_id': ability_id,
                'source': character_info['name'],
                'target': target_name,
                'icon': ability_info['icon']
            }
            
            cast_events.append(cast_event)
    
    # Sort events by timestamp
    cast_events.sort(key=lambda x: x['timestamp_ms'])
    
    # Step 5: Build result
    result = {
        'fight_duration_seconds': fight_duration_seconds,
        'fight_info': fight_data,
        'character_info': character_info,
        'cast_events': cast_events,
        'abilities_found': abilities_found,
        'abilities_not_found': abilities_not_found,
        'ability_ids_used': target_ability_ids,
        'total_events': len(cast_events)
    }
    
    return result
