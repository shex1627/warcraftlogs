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
    