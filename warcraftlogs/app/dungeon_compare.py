import streamlit as st
import pandas as pd
import os
from pathlib import Path
from warcraftlogs import WarcraftLogsClient
from warcraftlogs.constants import TOKEN_DIR
from warcraftlogs.query.reports import extract_report_info, get_encounter_info, get_player_dps_and_ilvl
from warcraftlogs.query.player_analysis import get_player_details
from warcraftlogs.query.dungeon.get_dungeon_runs import get_mythic_plus_runs
from warcraftlogs.query.dungeon.run_manager import MythicPlusRunManager
from warcraftlogs.gear.get_item_level import get_char_average_item_level, get_item_level_bracket
from warcraftlogs.query.fight import get_damage_breakdown, get_cast_breakdown
from warcraftlogs.analytics.compare import compare_damage, compare_casts
from warcraftlogs.utils import format_number
from warcraftlogs.constants import DUNGEON_RUN_LOCATION

def apply_gradient_styling(df, column_name):
    styled = df.style.format(precision=2).applymap(
        lambda x: (
            f'background-color: rgba(255, {int(255 * (1 - abs(x) / abs(df[column_name].min())))}, {int(255 * (1 - abs(x) / abs(df[column_name].min())))}, 0.7)'
            if x < 0 and df[column_name].min() < 0
            else f'background-color: rgba({int(255 * (1 - x / df[column_name].max()))}, 255, {int(255 * (1 - x / df[column_name].max()))}, 0.7)'
            if x > 0 and df[column_name].max() > 0
            else 'background-color: white'
        ),
        subset=[column_name]
    )
    return styled

def main():
    # use wide layout
    st.set_page_config(layout="wide")
    st.title("Warcraft Logs Dungeon Run DPS Analyzer")
    # show a description of wha this app do
    st.markdown("""
Compare your Mythic+ dungeon performance with top players using the same keystone level and similar gear.

Note: DPS differences may also be due to different dungeon routes.

Copy and paste a Warcraft Logs dungeon report URL to get started.
""")
    if os.environ.get('HIDE_MENU', 'true') == 'true':
        st.markdown("""
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """, unsafe_allow_html=True)

    # Initialize session state variables
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'confirmed_selection' not in st.session_state:
        st.session_state.confirmed_selection = False
    if 'comparison_ready' not in st.session_state:
        st.session_state.comparison_ready = False

    # Step 1: User input
    if not st.session_state.confirmed_selection:
        url = st.text_input("Paste a Warcraft Logs report URL:")
        find_similar = True #st.checkbox("Find similar item level players by looking at more pages. Takes few min", value=True)

        if 'client' not in st.session_state:
            st.session_state.client = WarcraftLogsClient(token_dir=TOKEN_DIR)
        client = st.session_state.client

        if url:
            # Step 2: Extract info from URL
            try:
                report_code, fight_id, _ = extract_report_info(url)
                st.session_state['report_code'] = report_code
                st.session_state['fight_id'] = fight_id
            except Exception as e:
                st.error(f"Could not parse URL: {e}")
                return

            if fight_id == "last":
                from warcraftlogs.query.reports import get_last_fight_id
                fight_id = get_last_fight_id(client, report_code=report_code)

            # Step 3: Get player info
            players_info = get_player_details(client, report_code, fight_id)
            player_details_lst = []
            for role, role_player_details in players_info.items():
                player_details_lst.extend(role_player_details)
            # Let user select player
            player_names = [f"{p['name']}--({p['type']}, {p['specs'][0]['spec']})" for p in player_details_lst]
            #player_names = [p['name'] for p in player_details_lst]
            selected_player_name = st.selectbox("Select player to analyze", player_names)
            selected_player_name = selected_player_name.split('--')[0]
            selected_player = next(p for p in player_details_lst if p['name'] == selected_player_name)
            st.session_state['selected_player'] = selected_player

            # make a button to confirm selection
            if st.button("Confirm Selection"):
                fight_info = get_encounter_info(client.query_public_api, report_code, fight_id)
                st.session_state['fight_info'] = fight_info
                
                # Store all necessary data in session state
                st.session_state['report_code'] = report_code
                st.session_state['fight_id'] = fight_id
                st.session_state['selected_player_name'] = selected_player_name
                st.session_state['selected_player'] = selected_player
                st.session_state['find_similar'] = find_similar

                # Step 5: Find similar runs
                player_class = selected_player['type']
                player_spec = selected_player['specs'][0]['spec']
                keystone_level = fight_info['keystone_level']
                dungeon_name = fight_info['encounter_name']

                if find_similar:
                    pages = [1, 3, 6, 8, 10]
                    max_reports = 10
                else:
                    pages = [1]
                    max_reports = 20

                run_manager = MythicPlusRunManager()
                dungeon_runs_paths = list(Path(DUNGEON_RUN_LOCATION).glob("*.pkl"))

                use_cached_runs = False
                for dungeon_run_path in dungeon_runs_paths:
                    stats = run_manager.add_from_file(str(dungeon_run_path))
                try:
                    temp_df = pd.DataFrame(sorted(
                        run_manager.get_runs(dungeon_name, keystone_level, player_class, player_spec),
                        key=lambda x: x['player']['raw_dps'], reverse=True
                    ))
                    compare_df = pd.concat([temp_df, pd.DataFrame(temp_df['player'].tolist())], axis=1)
                    compare_df = compare_df.sort_values(by=['item_level_bracket', 'raw_dps'], ascending=False)
                    if compare_df.shape[0] > 5:
                        print(f"Found {compare_df.shape[0]} cached runs for {dungeon_name} at level {keystone_level} for {player_class} {player_spec}.")
                        use_cached_runs = True
                        #st.warning("Using cached runs for faster comparison. You can change this in the settings.")
                except Exception as e:
                    st.error(f"Error loading existing runs: {e}")
                    compare_df = pd.DataFrame()

                print(f"Using cached runs: {use_cached_runs}")
                if not use_cached_runs:
                    runs_info = []
                    with st.spinner("Fetching top logs..."):
                        # show progress bar from 
                        progress_bar = st.progress(0, text="Fetching runs from Warcraft Logs pages...")
                        for page_index in range(len(pages)):
                            page = pages[page_index]
                            runs = get_mythic_plus_runs(
                                client=client,
                                dungeon_name=dungeon_name,
                                keystone_level=keystone_level,
                                page=page,
                                max_reports=max_reports,
                                class_filter=player_class,
                                spec_filter=player_spec,
                            )
                            runs_info.extend(runs)
                            progress_bar.progress(page_index / len(pages))
                    
                    run_manager.add_runs(runs_info)
                    file_path = os.path.join(DUNGEON_RUN_LOCATION, f"{dungeon_name}_{keystone_level}_{player_class}_{player_spec}.pkl")
                    run_manager.save_to_file(file_path)

                    # Step 6: Build DataFrame for selection
                    temp_df = pd.DataFrame(sorted(
                        run_manager.get_runs(dungeon_name, keystone_level, player_class, player_spec),
                        key=lambda x: x['player']['raw_dps'], reverse=True
                    ))
                    compare_df = pd.concat([temp_df, pd.DataFrame(temp_df['player'].tolist())], axis=1)
                    compare_df = compare_df.sort_values(by=['item_level_bracket', 'raw_dps'], ascending=False)

                # Step 7: Filter by item level if needed
                dungeon_info = get_player_dps_and_ilvl(report_code=report_code,fight_id=fight_id, query_graphql_func=client.query_public_api)
                try:
                    players_information = dungeon_info.get('players')
                    for player_info in players_information:
                        if player_info.get('name') == selected_player_name:
                            reference_ivl = player_info.get('item_level')
                            break
                except Exception as e:
                    print(f"Error extracting player info: {e}")
                    reference_ivl = get_char_average_item_level(
                        report_id=report_code,
                        fight_id=fight_id,
                        character_name=selected_player_name,
                        client=client
                    )
                if find_similar:
                    compare_record = compare_df.query(
                        f"item_level_bracket <= {get_item_level_bracket(reference_ivl)}"
                    ).copy()
                else:
                    compare_record = compare_df.head(10).copy()
                compare_record['player_name'] = compare_record['player'].apply(lambda x: x.get("character_name"))

                display_cols = ['player_name', 'report_id', 'fight_id', 'item_level_bracket', 'dps', 'hps', 'spec']
                log_options = compare_record[display_cols].head(10).to_dict(orient='records')
                log_labels = [f"{r['player_name']} | {r['report_id']} | {r['dps']} DPS" for r in log_options]
                # Store comparison data
                st.session_state['compare_record'] = compare_record
                st.session_state['log_options'] = log_options
                st.session_state['log_labels'] = log_labels
                
                # Mark as confirmed
                st.session_state.confirmed_selection = True
                st.rerun()  # Force rerun to show next step

                # # Step 8: Let user select a log to compare
                # st.subheader("Select a log to compare")
                # display_cols = ['player_name', 'report_id', 'fight_id', 'item_level_bracket', 'dps', 'hps', 'spec']
                # st.dataframe(compare_record[display_cols].head(10), use_container_width=True)
                # log_options = compare_record[display_cols].head(10).to_dict(orient='records')
                # log_labels = [f"{r['player_name']} | {r['report_id']} | {r['dps']} DPS" for r in log_options]
                # selected_log_idx = st.selectbox("Choose a log to compare", range(len(log_labels)), format_func=lambda i: log_labels[i])
                # chosen_record = log_options[selected_log_idx]
                # st.session_state['chosen_record'] = chosen_record

    # Step 8: Log selection (only show if confirmed but not compared yet)
    if st.session_state.confirmed_selection and not st.session_state.comparison_ready:
        st.subheader("Select a log to compare")
        
        # Use data from session state
        compare_record = st.session_state['compare_record']
        log_options = st.session_state['log_options']
        log_labels = st.session_state['log_labels']
        
        display_cols = ['player_name', 'report_id', 'fight_id', 'avg_item_level', 'dps', 'hps', 'spec']
        st.dataframe(compare_record[display_cols].head(10), use_container_width=True)
        
        selected_log_idx = st.selectbox("Choose a log to compare", range(len(log_labels)), format_func=lambda i: log_labels[i])
        chosen_record = log_options[selected_log_idx]
        st.session_state['chosen_record'] = chosen_record
        
        if st.button("Compare!"):
            st.session_state.comparison_ready = True
            st.rerun()  # Force rerun to show comparison
                
    # Step 9: Show comparison (only show if ready to compare)
    if st.session_state.comparison_ready:
        client = st.session_state.client
        # Show a back button to allow going back to log selection
        if st.button("← Back to Log Selection"):
            st.session_state.comparison_ready = False
            st.rerun()
        
        # Show reset button to start over
        if st.button("🔄 Start Over"):
            # Clear all session state
            for key in list(st.session_state.keys()):
                if key.startswith(('step', 'confirmed', 'comparison', 'report_', 'fight_', 'selected_', 'find_', 'compare_', 'log_', 'chosen_')):
                    del st.session_state[key]
            st.rerun()

        # show both logs urls
        st.markdown(f"""Your log: [Warcraft Logs Report](https://www.warcraftlogs.com/reports/{st.session_state['report_code']})""")
        st.markdown(f"""Comparison log: [Warcraft Logs Report](https://www.warcraftlogs.com/reports/{st.session_state['chosen_record']['report_id']})""")
        
        # Your existing comparison logic using session state data...
        reference_report_info = {
            'REPORT_ID': st.session_state['report_code'],
            'FIGHT_ID': st.session_state['fight_id'],
            'PLAYER_NAME': st.session_state['selected_player_name']
        }
        compare_report_info = {
            'REPORT_ID': st.session_state['chosen_record']['report_id'],
            'FIGHT_ID': st.session_state['chosen_record']['fight_id'],
            'PLAYER_NAME': st.session_state['chosen_record']['player_name']
        }

        # Damage breakdown
        reference_char_dmg_breakdown = get_damage_breakdown(
            report_code=reference_report_info['REPORT_ID'],
            fight_id=reference_report_info['FIGHT_ID'],
            player_name=reference_report_info['PLAYER_NAME'],
            client=client
        )
        compare_char_dmg_breakdown = get_damage_breakdown(
            report_code=compare_report_info['REPORT_ID'],
            fight_id=compare_report_info['FIGHT_ID'],
            player_name=compare_report_info['PLAYER_NAME'],
            client=client
        )
        damage_breakdown_compare = compare_damage(
            reference_char_dmg_breakdown,
            compare_char_dmg_breakdown,
        )
        st.subheader("Damage Breakdown Comparison")
        # apply_gradient_styling(damage_breakdown_compare\
        #                .head(10), 
        #                'dps_diff')

        dmg_selected_columns = ['ability_name', 'dps_Player 1','dps_diff', 'avg_damage_diff', 'damage_percent_Player 1','damage_percent_diff']
        st.dataframe(apply_gradient_styling(damage_breakdown_compare[dmg_selected_columns].head(10), 
            'dps_diff'), use_container_width=True)

        # Cast breakdown
        reference_char_cast_breakdown = get_cast_breakdown(
            report_code=reference_report_info['REPORT_ID'],
            fight_id=reference_report_info['FIGHT_ID'],
            player_name=reference_report_info['PLAYER_NAME'],
            query_graphql_func=client.query_public_api
        )
        compare_char_cast_breakdown = get_cast_breakdown(
            report_code=compare_report_info['REPORT_ID'],
            fight_id=compare_report_info['FIGHT_ID'],
            player_name=compare_report_info['PLAYER_NAME'],
            query_graphql_func=client.query_public_api
        )
        cast_breakdown_compare = compare_casts(
            reference_char_cast_breakdown,
            compare_char_cast_breakdown,
        )
        st.subheader("Cast Breakdown Comparison")
        cast_selected_columns = ['ability_name', 'cpm_diff', 'casts_per_minute_Player 1','casts_per_minute_Player 2',
        'total_casts_diff','total_casts_Player 2',  'total_casts_Player 1',]
        st.dataframe(apply_gradient_styling(cast_breakdown_compare[cast_selected_columns].head(10).round(2)
                                            , 'cpm_diff'), use_container_width=True)

if __name__ == "__main__":
    main()
