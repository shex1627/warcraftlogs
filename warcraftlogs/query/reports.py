from warcraftlogs.client import WarcraftLogsClient
from typing import List, Dict

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