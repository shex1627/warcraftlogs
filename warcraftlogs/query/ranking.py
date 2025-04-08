from typing import Dict, List, Optional
import pandas as pd
from warcraftlogs.client import WarcraftLogsClient
from warcraftlogs.ability_data_manager import AbilityDataManager
from warcraftlogs.query.player_analysis import PlayerDetails, get_item_level_bracket
from warcraftlogs.query.events import fetch_events

def generate_ranking_query(player: PlayerDetails, fight: dict):
    query = """
    query GetDungeonRankings($zoneID: Int!) {{
      worldData {{
        zone(id: $zoneID) {{
          name
          encounters(id: [3015]) {{
            id
            name
            characterRankings(
              className: "{}"
              specName: "{}"
              bracket: {}
              includeCombatantInfo: true,
              leaderboard: LogsOnly
            )
          }}
        }}
      }}
    }}
    """.format(player.class_name, player.spec_name, player.bracket)
    
    variables = {
        "zoneID": fight['zone']['id'],
        #"encounterID": fight['fights'][0]['encounterID']
    }
    return query, variables

def generate_ranking_query(**kwargs):
    source_filter_str = ""
    for key, value in kwargs.items():
        source_filter_str += f"{key}: {value},\n"
    source_filter_str = source_filter_str[:-2]  # remove last comma and newline
    query = f"""
    query GetDungeonRankings($encounterID: Int!) {{
      worldData {{
          encounter(id: $encounterID) {{
            id
            name
            characterRankings(
              includeCombatantInfo: false,
              leaderboard: LogsOnly,
              {source_filter_str}
            )
          }}
        }}
      }}
    """
    return query

def generate_ranking_query_from_player_and_fight(player: PlayerDetails, fight: dict):
    filters = {
        "bracket": player.bracket,
        "className": f'"{player.class_name}"',
        "specName": f'"{player.spec_name}"',
        "difficulty": fight['difficulty']
    }
    query_generated = generate_ranking_query(**filters)
    variables = {
        "encounterID": fight['encounterID']
    }
    return query_generated, variables