def get_threat_query(report_code, fight_id,**kwargs):
    # If player_id is provided, filter to that specific player
    #source_filter = f"sourceID: {player_id}" if player_id is not None else ""
    # if start_time is not None:
    #     source_filter += f"startTime: {start_time}"
    source_filter = ""
    for key, value in kwargs.items():
        source_filter += f"{key}: {value}\n"
    #print(source_filter)
    query = """
      {
        reportData {
          report(code: "%s") {
            events(
              fightIDs: %d
              dataType: Threat
              limit: 1000
              %s
            ) {
              data
              nextPageTimestamp
            }
          }
        }
      }
      """ % (report_code, fight_id, source_filter)
    return query

def find_npc_ids(report_code, fight_id):
    query = """
{
  reportData {
    report(code: "%s") {
      fights {
        enemyNPCs {
          id
          gameID
        }
      }
      masterData {
        actors {
          id
          name
          gameID
          type
          subType
        }
      }
    }
  }
}
""" % report_code
    return query

def identify_pull_clusters(df, gap_threshold=30):
    """
    Identifies pull clusters based on gaps in threat activity
    
    Parameters:
    - df: DataFrame with timestamp_seconds column
    - gap_threshold: Number of seconds that defines a gap between pulls (default 30s)
    
    Returns:
    - DataFrame with pull cluster assignments
    """
    # Sort by timestamp
    df = df.sort_values('timestamp_seconds')
    
    # Calculate time differences between consecutive events
    time_diffs = df['timestamp_seconds'].diff()
    
    # Identify new clusters where gap is larger than threshold
    new_cluster = time_diffs > gap_threshold
    
    # Create cluster labels
    cluster_labels = new_cluster.cumsum()
    
    # Add cluster labels to original dataframe
    df_with_clusters = df.copy()
    df_with_clusters['pull_cluster'] = cluster_labels
    
    # Calculate cluster statistics 
    cluster_stats = df_with_clusters.groupby('pull_cluster').agg({
        'timestamp_seconds': ['min', 'max', 'count'],
        'sourceName': lambda x: len(x.unique())
    }).round(2)
    
    cluster_stats.columns = ['start_time', 'end_time', 'events_count', 'unique_targets']
    cluster_stats['duration'] = cluster_stats['end_time'] - cluster_stats['start_time']
    
    return df_with_clusters, cluster_stats
