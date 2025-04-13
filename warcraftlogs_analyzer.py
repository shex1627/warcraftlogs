import streamlit as st
import re
import pandas as pd
from tqdm import tqdm
import json
from datetime import datetime
from pathlib import Path
import uuid
import os
from collections import defaultdict

from warcraftlogs import WarcraftLogsClient
from warcraftlogs.constants import TOKEN_DIR
from warcraftlogs.ability_data_manager import AbilityDataManager
from warcraftlogs.query.player_analysis import get_player_details, get_fight_info
from warcraftlogs.query.ranking import generate_ranking_query_from_player_and_fight
from warcraftlogs.query.tables import get_table_data
from warcraftlogs.query.events import get_buff_info_df, get_damage_info_df, get_cast_info_df
from warcraftlogs.analytics.compare import compare_damage_info, compare_buff_uptime, compare_cast_info

# Constants
SIMILAR_PLAYERS_COUNT = 10
ANALYSIS_PLAYERS_COUNT = 5
DPS_DIFF_THRESHOLD = 10000
CAST_PER_MINUTE_DIFF_THRESHOLD = 1
BUFF_UPTIME_DIFF_THRESHOLD = 0.1
MIN_DATAPOINTS = 2
ANALYSIS_LOG_FILE = "analysis_logs.jsonl"

class AnalysisLogger:
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
    def log_analysis(self, session_id: str, url: str, player: str, timestamp: str):
        log_entry = {
            "session_id": session_id,
            "url": url,
            "player": player,
            "timestamp": timestamp
        }
        
        with self.log_file.open('a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def get_recent_analyses(self, n: int = 5) -> list:
        if not self.log_file.exists():
            return []
        
        with self.log_file.open('r') as f:
            logs = [json.loads(line) for line in f]
        
        return sorted(logs, key=lambda x: x['timestamp'], reverse=True)[:n]
    
# Initialize WarcraftLogs client
@st.cache_resource
def get_client():
    return WarcraftLogsClient(token_dir=TOKEN_DIR)

@st.cache_resource
def get_ability_data_manager(_client):
    return AbilityDataManager(client=_client, cache_file="../data/ability_data_cache.json")

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

def generate_insights_prompt(cast_analyzer_df, damage_analyzer_df, buff_analyzer_df, ability_data_manager):
    """Generate prompt for LLM insights"""
    all_abilities = set(damage_analyzer_df['guid'].tolist() + 
                       buff_analyzer_df['guid'].tolist() + 
                       cast_analyzer_df['guid'].tolist())
    # Remove melee which is 1
    all_abilities = [ability for ability in all_abilities if ability != 1]
    all_abilities_df = ability_data_manager.get_abilities(all_abilities)
    all_ability_dict = all_abilities_df[['id','description']].to_dict('records')

    # Convert dataframes to markdown for LLM
    cast_analyzer_df_markdown = cast_analyzer_df.to_markdown()
    damage_analyzer_df_markdown = damage_analyzer_df.to_markdown()
    buff_analyzer_df_markdown = buff_analyzer_df.to_markdown()

    prompt = f"""
    You are a world class warcraft logs analyst. You are given the following dataframes based on a warcraft logs report,
    comparing the player's performance with other top ranks players. The dataframes are:
    {cast_analyzer_df_markdown}
    {damage_analyzer_df_markdown}
    {buff_analyzer_df_markdown}

    1 / base usually means the current player, 2 / compare means the top players.
    diff means current player - top players.

    Related abilities with their descriptions:
    {all_ability_dict}
    Please provide insights on the dataframes and the abilities. 
    #### insight format:
    combine and synthesize the dataframes from different sources and provide insights on the current player's performance.
    1.compare to the top players, what is the current player's issue(s)?
    2.actionable insights how to address the issue(s).
    3.do not repeat similar insights/information.
    """
    return prompt


def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    
    if 'current_url' not in st.session_state:
        st.session_state.current_url = ""
    
    if 'current_player' not in st.session_state:
        st.session_state.current_player = None
    
    if 'player_details_df' not in st.session_state:
        st.session_state.player_details_df = None

def perform_analysis(client, ability_data_manager, url, selected_player, source_id):
    """
    Perform analysis by comparing player performance with top players
    
    Args:
        client: WarcraftLogs client
        ability_data_manager: AbilityDataManager instance
        url: WarcraftLogs URL
        selected_player: Selected player name with spec
        source_id: Player source ID
    
    Returns:
        dict: Analysis results containing dataframes and timestamp
    """
    uploaded_report_code, uploaded_fight_id, _ = extract_report_info(url)
    
    # Get player details and fight info
    player = get_player_details(client, report_code=uploaded_report_code, fight_id=uploaded_fight_id, source_id=source_id)
    fight = get_fight_info(client, report_code=uploaded_report_code, fight_id=uploaded_fight_id)
    print(f"analyzing player {player}")
    
    # Get similar player rankings
    query, variables = generate_ranking_query_from_player_and_fight(player, fight['fights'][0])
    ranking_resp = client.query_public_api(query, variables)
    similar_player_rankings = ranking_resp['data']['worldData']['encounter']['characterRankings']['rankings']
    print(f"Found {len(similar_player_rankings)} similar players")
    
    # Get similar player report info
    similar_player_report_info = []
    for ranking in similar_player_rankings[:SIMILAR_PLAYERS_COUNT]:
        report_code = ranking['report']['code']
        fight_id = ranking['report']['fightID']
        ranking_player_details = get_player_details(client, report_code=report_code, fight_id=fight_id)
        player_source_id = find_player_id_from_name(ranking_player_details, ranking['name'])
        similar_player_report_info.append({
            'report_code': report_code,
            'fight_id': fight_id,
            'player_source_id': player_source_id
        })

    print(f"Found {len(similar_player_report_info)} similar player report info")
    print(f"example similar player report info: {similar_player_report_info[0]}")
    
    # Get player data
    buff_table_data_query = get_table_data(uploaded_report_code, uploaded_fight_id, source_id, data_type="Buffs", viewOptions=16)
    buff_table_data_resp = client.query_public_api(buff_table_data_query)
    player_buff_info_df = get_buff_info_df(buff_table_data_resp['data']['reportData']['report']['table']['data'])
    #print(f"{player_buff_info_df.to_markdown()}")
    
    damage_done_table_data_query = get_table_data(uploaded_report_code, uploaded_fight_id, source_id, data_type="DamageDone")
    damage_done_table_data_resp = client.query_public_api(damage_done_table_data_query)
    player_damage_info_df = get_damage_info_df(damage_done_table_data_resp['data']['reportData']['report']['table']['data'])
    #print(f"{player_damage_info_df.to_markdown()}")
    
    cast_data_query = get_table_data(uploaded_report_code, uploaded_fight_id, source_id, data_type="Casts")
    cast_data_resp = client.query_public_api(cast_data_query)
    player_cast_info_df = get_cast_info_df(cast_data_resp['data']['reportData']['report']['table']['data'])
    #print(f"{player_cast_info_df.to_markdown()}")

    print(f"player_cast_info_df: {player_cast_info_df.shape}")
    print(f"player_damage_info_df: {player_damage_info_df.shape}")
    print(f"player_buff_info_df: {player_buff_info_df.shape}")    

    # Get top player data
    top_player_buff_info_lst = []
    top_player_dmg_info_lst = []
    top_player_cast_info_lst = []
    
    for report_info in similar_player_report_info[:ANALYSIS_PLAYERS_COUNT]:
        # Get buff data
        buff_table_data_query = get_table_data(report_info['report_code'], report_info['fight_id'], 
                                             report_info['player_source_id'], data_type="Buffs", viewOptions=16)
        buff_table_data_resp = client.query_public_api(buff_table_data_query)
        top_player_buff_info_lst.append(buff_table_data_resp['data']['reportData']['report']['table']['data'])
        
        # Get damage data
        damage_done_table_data_query = get_table_data(report_info['report_code'], report_info['fight_id'], 
                                                    report_info['player_source_id'], data_type="DamageDone")
        damage_done_table_data_resp = client.query_public_api(damage_done_table_data_query)
        top_player_dmg_info_lst.append(damage_done_table_data_resp['data']['reportData']['report']['table']['data'])
        
        # Get cast data
        cast_data_query = get_table_data(report_info['report_code'], report_info['fight_id'], 
                                       report_info['player_source_id'], data_type="Casts")
        cast_data_resp = client.query_public_api(cast_data_query)
        top_player_cast_info_lst.append(cast_data_resp['data']['reportData']['report']['table']['data'])
    
    # Process data
    top_player_buff_info_lst_clean = list(map(get_buff_info_df, top_player_buff_info_lst))
    top_player_damage_info_lst_clean = list(map(get_damage_info_df, top_player_dmg_info_lst))
    top_player_cast_info_lst_clean = list(map(get_cast_info_df, top_player_cast_info_lst))
    
    # Remove empty dataframes
    top_player_buff_info_lst_clean = [df for df in top_player_buff_info_lst_clean if not df.empty]
    top_player_damage_info_lst_clean = [df for df in top_player_damage_info_lst_clean if not df.empty]
    top_player_cast_info_lst_clean = [df for df in top_player_cast_info_lst_clean if not df.empty]

    print(f"top_player_cast_info_lst_clean: {len(top_player_cast_info_lst_clean)}")
    print(f"top_player_damage_info_lst_clean: {len(top_player_damage_info_lst_clean)}") 
    print(f"top_player_buff_info_lst_clean: {len(top_player_buff_info_lst_clean)}")
    
    # Analyze cast differences
    cast_per_minute_diff_dict = defaultdict(list)
    for i in range(len(top_player_cast_info_lst_clean)):
        compare_df = compare_cast_info(player_cast_info_df, top_player_cast_info_lst_clean[i])
        compare_df = compare_df.query(f"abs_cast_per_minute_diff > {CAST_PER_MINUTE_DIFF_THRESHOLD}")
        for index, row in compare_df.iterrows():
            key = (row['name'], row['guid']) 
            cast_per_minute_diff_dict[key].append(row)
    
    cast_analyzer_df_records = []
    for ability in cast_per_minute_diff_dict.keys():
        ability_df = pd.DataFrame(cast_per_minute_diff_dict[ability])
        name, guid = ability
        cast_analyzer_df_records.append({
            'name': name,
            'guid': guid,
            'base_player_cast_per_minute': round(ability_df['cast_per_minute_1'].mean(), 1),
            'compare_player_cast_per_minute': round(ability_df['cast_per_minute_2'].mean(), 1),
            'cast_per_minute_diff': round(ability_df['cast_per_minute_diff'].mean(), 1),
            'datapoints': len(ability_df)
        })
    
    cast_analyzer_df = pd.DataFrame(cast_analyzer_df_records)
    
    # Analyze buff differences
    buff_uptime_diff_dict = defaultdict(list)
    for i in range(len(top_player_buff_info_lst_clean)):
        compare_df = compare_buff_uptime(player_buff_info_df, top_player_buff_info_lst_clean[i])
        compare_df = compare_df.query(f"abs_up_time_pct_diff > {BUFF_UPTIME_DIFF_THRESHOLD}")
        for index, row in compare_df.iterrows():
            key = (row['name'], row['guid']) 
            buff_uptime_diff_dict[key].append(row)
    
    buff_analyzer_df_records = []
    for ability in buff_uptime_diff_dict.keys():
        ability_df = pd.DataFrame(buff_uptime_diff_dict[ability])
        name, guid = ability
        buff_analyzer_df_records.append({
            'name': name,
            'guid': guid,
            'base_player_buff_uptime': round(ability_df['up_time_pct_1'].mean(), 1),
            'compare_player_buff_uptime': round(ability_df['up_time_pct_2'].mean(), 1),
            'buff_uptime_diff': round(ability_df['up_time_pct_diff'].mean(), 1),
            'datapoints': len(ability_df)
        })
    
    buff_analyzer_df = pd.DataFrame(buff_analyzer_df_records).query(f"datapoints > {MIN_DATAPOINTS}")
    
    # Analyze damage differences
    damage_done_diff_dict = defaultdict(list)
    for i in range(len(top_player_damage_info_lst_clean)):
        compare_df = compare_damage_info(player_damage_info_df, top_player_damage_info_lst_clean[i])
        compare_df = compare_df.query(f"abs_dps_diff > {DPS_DIFF_THRESHOLD}")
        for index, row in compare_df.iterrows():
            key = (row['name'], row['guid']) 
            damage_done_diff_dict[key].append(row)
    
    damage_analyzer_df_records = []
    for ability in damage_done_diff_dict.keys():
        ability_df = pd.DataFrame(damage_done_diff_dict[ability])
        name, guid = ability
        damage_analyzer_df_records.append({
            'name': name,
            'guid': guid,
            'base_player_dps': round(ability_df['dps_1'].mean(), 1),
            'compare_player_dps': round(ability_df['dps_2'].mean(), 1),
            'base_player_hit_per_minute': round(ability_df['hit_per_minute_1'].mean(), 1),
            'compare_player_hit_per_minute': round(ability_df['hit_per_minute_2'].mean(), 1),
            'dps_diff': round(ability_df['dps_diff'].mean(), 1),
            'hit_per_minute_diff': round(ability_df['hit_per_minute_diff'].mean(), 1),
            'datapoints': len(ability_df)
        })
    
    damage_analyzer_df = pd.DataFrame(damage_analyzer_df_records).query(f"datapoints > {MIN_DATAPOINTS}").sort_values('dps_diff', ascending=True)
    
    return {
        'damage_analyzer_df': damage_analyzer_df,
        'cast_analyzer_df': cast_analyzer_df,
        'buff_analyzer_df': buff_analyzer_df,
        'timestamp': datetime.now().isoformat(),
        'similar_player_report_info': similar_player_report_info
    }

def display_analysis_results(results):
    """Display the analysis results"""
    if not results:
        return
    
    st.subheader("Analysis Results")
    
    # Reorder columns for damage analysis
    damage_cols = ['name', 'dps_diff', 'hit_per_minute_diff'] + [
        col for col in results['damage_analyzer_df'].columns 
        if col not in ['name', 'dps_diff', 'hit_per_minute_diff']
    ]
    #remove guid column
    damage_cols = [col for col in damage_cols if col != 'guid']
    st.write("### Damage Analysis")
    st.dataframe(
        results['damage_analyzer_df'][damage_cols].style.background_gradient(
            cmap='autumn', subset=['dps_diff','hit_per_minute_diff']
        ),
        use_container_width=True,
        hide_index=True
    )
    
    # Reorder columns for cast analysis
    cast_cols = ['name', 'cast_per_minute_diff'] + [
        col for col in results['cast_analyzer_df'].columns 
        if col not in ['name', 'cast_per_minute_diff']
    ]
    #remove guid column
    cast_cols = [col for col in cast_cols if col != 'guid']
    st.write("### Cast Analysis")
    st.dataframe(
        results['cast_analyzer_df'][cast_cols].round(1).style.background_gradient(
            cmap='autumn', subset=['cast_per_minute_diff']
        ),
        use_container_width=True,
        hide_index=True
    )
    
    # Reorder columns for buff analysis
    buff_cols = ['name', 'buff_uptime_diff'] + [
        col for col in results['buff_analyzer_df'].columns 
        if col not in ['name', 'buff_uptime_diff']
    ]
    #remove guid column
    buff_cols = [col for col in buff_cols if col != 'guid']
    st.write("### Buff Uptime Analysis")
    st.dataframe(
        results['buff_analyzer_df'][buff_cols].sort_values('buff_uptime_diff', ascending=True)
            .style.background_gradient(cmap='autumn', subset=['buff_uptime_diff']),
        use_container_width=True,
        hide_index=True
    )

def main():
    st.title("WarcraftLogs Player Analyzer")
    
    # Initialize session state
    initialize_session_state()
    
    # Initialize client and ability data manager
    client = get_client()
    ability_data_manager = get_ability_data_manager(client)
    
    # Initialize logger
    logger = AnalysisLogger(ANALYSIS_LOG_FILE)
    
    # Display recent analyses
    # recent_analyses = logger.get_recent_analyses()
    # if recent_analyses:
    #     with st.expander("Recent Analyses"):
    #         for analysis in recent_analyses:
    #             st.write(f"Player: {analysis['player']} - {analysis['timestamp']}")
    #             if st.button(f"Load {analysis['player']}'s analysis", key=analysis['timestamp']):
    #                 st.session_state.current_url = analysis['url']
                    
    # URL input
    url = st.text_input(
        "Enter WarcraftLogs URL (with fight ID):",
        value=st.session_state.current_url
    )
    
    if url != st.session_state.current_url:
        st.session_state.current_url = url
        st.session_state.player_details_df = None
        st.session_state.current_player = None
        st.session_state.analysis_results = None
    
    report_code, fight_id, _ = extract_report_info(url)
    if fight_id == "last":
        from warcraftlogs.query.reports import get_last_fight_id
        fight_id = get_last_fight_id(client, report_code=report_code)

    if not url:
        st.text("Please enter a WarcraftLogs raid URL with fight ID.")
        return 


    if not report_code or not fight_id:
        st.error("Invalid URL. Please enter a valid WarcraftLogs URL with a fight ID.")
        return
    
    try:
        # Get player details if not already in session state
        if st.session_state.player_details_df is None:
            with st.spinner("Loading player details..."):
                player_details = get_player_details(client, report_code=report_code, fight_id=fight_id)
                
                # Flatten player details for selection
                player_details_lst = []
                for role, role_player_details in player_details.items():
                    player_details_lst.extend(role_player_details)
                
                player_details_df = pd.DataFrame(player_details_lst)
                player_details_df['player_spec'] = player_details_df['specs'].apply(lambda x: x[0]['spec'])
                player_details_df['player_tooltip'] = player_details_df['name'] + '-' + player_details_df['player_spec'] + ' ' + player_details_df['type']
                
                st.session_state.player_details_df = player_details_df
        
        if st.session_state.player_details_df is not None:
            player_options = st.session_state.player_details_df['player_tooltip'].tolist()
            selected_player = st.selectbox(
                "Select player to analyze:",
                player_options,
                index=player_options.index(st.session_state.current_player) if st.session_state.current_player in player_options else 0
            )
            
            if selected_player != st.session_state.current_player:
                st.session_state.current_player = selected_player
            
            selected_player_name = selected_player.split('-')[0]
            source_id = st.session_state.player_details_df[
                st.session_state.player_details_df['name'] == selected_player_name
            ]['id'].values[0]
            
            # Only analyze when button is clicked
            if st.button("Analyze Player"):
                with st.spinner("Analyzing player performance..."):
                    results = perform_analysis(client, ability_data_manager, url, selected_player, source_id)
                    logger.log_analysis(
                        st.session_state.session_id,
                        url,
                        selected_player,
                        results['timestamp']
                    )
                    st.session_state.analysis_results = results
        
            # Display results if they exist
            if st.session_state.analysis_results:
                display_analysis_results(st.session_state.analysis_results)

                # LLM Insights
                if st.button("Generate Insights"):
                    api_key = os.environ.get("OPENAI_API_KEY")
                    
                    if api_key:
                        try:
                            from askharrison.llm.openai_llm_client import OpenAIClient
                            openai_client = OpenAIClient(api_key=api_key)
                            
                            with st.spinner("Generating insights..."):
                                insights_prompt = generate_insights_prompt(
                                    st.session_state.analysis_results['cast_analyzer_df'],
                                    st.session_state.analysis_results['damage_analyzer_df'],
                                    st.session_state.analysis_results['buff_analyzer_df'],
                                    ability_data_manager
                                )
                                insights = openai_client.generate(insights_prompt)
                                
                                st.write("### AI Insights")
                                st.markdown(insights)
                        except Exception as e:
                            st.error(f"Error generating insights: {str(e)}")
                    else:
                        st.warning("Please enter an OpenAI API key to generate insights.")


                # top player references as hyperlinks
                st.write("### Top Player References")
                # generate warcraftlogs url for top players, 
                # like https://www.warcraftlogs.com/reports/6Qy7Tp91KaCJWMFB?fight=15&type=damage-done&source=110
                top_player_urls = []
                for report_info in st.session_state.analysis_results['similar_player_report_info'][:ANALYSIS_PLAYERS_COUNT]:
                    top_player_urls.append(f"https://www.warcraftlogs.com/reports/{report_info['report_code']}?fight={report_info['fight_id']}&type=damage-done&source={report_info['player_source_id']}")
                for url in top_player_urls:
                    st.write(f"[{url}]({url})")
            
    except Exception as e:
        trace_info = st.expander("Traceback", expanded=False)
        with trace_info:
            st.write(e)
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main() 