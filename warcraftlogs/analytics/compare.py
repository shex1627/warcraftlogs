import numpy as np
import pandas as pd
from dataclasses import dataclass

def compare_damage_info(base_df, compare_df):
    """
    Compare damage information between two players/specs
    
    Args:
        base_df (DataFrame): Base player's damage data
        compare_df (DataFrame): Comparison player's damage data
        
    Returns:
        DataFrame: Comparison metrics with absolute and relative differences
    """
    
    # Get common abilities between both players
    common_abilities = set(base_df['name']) & set(compare_df['name'])
    
    # Filter both dataframes to only include common abilities
    base_df = base_df[base_df['name'].isin(common_abilities)].sort_values('name').reset_index(drop=True)
    compare_df = compare_df[compare_df['name'].isin(common_abilities)].sort_values('name').reset_index(drop=True)
    
    # Create comparison dataframe
    comparison = pd.DataFrame()
    comparison['ability'] = base_df['name']
    
    # Calculate absolute differences
    metrics = ['dps', 'hit_per_minute'] #, 'critHitCount', 'crit_pct', 'uses',  'hitCount'
    for metric in metrics:
        comparison[f'{metric}_base'] = base_df[metric]
        comparison[f'{metric}_compare'] = compare_df[metric]
        comparison[f'{metric}_diff'] = compare_df[metric] - base_df[metric]
        
        # Calculate percentage difference
        comparison[f'{metric}_diff_pct'] = np.where(
            base_df[metric].notna() & (base_df[metric] != 0),
            ((compare_df[metric] - base_df[metric]) / base_df[metric] * 100),
            np.nan
        )
    
    # Format percentage columns
    pct_columns = [col for col in comparison.columns if 'pct' in col]
    for col in pct_columns:
        comparison[col] = comparison[col].round(1)
        
    # Format numeric columns
    numeric_columns = [col for col in comparison.columns if col not in ['ability'] + pct_columns]
    for col in numeric_columns:
        comparison[col] = comparison[col].round(1)
    
    return comparison

def compare_damage_info(damage_info_df1: pd.DataFrame, damage_info_df2: pd.DataFrame):
    damage_info_df1 = damage_info_df1[['name', 'dps', 'hit_per_minute', 'guid']]
    damage_info_df2 = damage_info_df2[['name', 'dps', 'hit_per_minute', 'guid']]
    merged_df = damage_info_df1.merge(damage_info_df2, on=['name', 'guid'], suffixes=('_1', '_2'), how=
                               'inner')
    merged_df['dps_diff'] = merged_df['dps_1'] - merged_df['dps_2']
    merged_df['hit_per_minute_diff'] = merged_df['hit_per_minute_1'] - merged_df['hit_per_minute_2']
    merged_df['abs_dps_diff'] = merged_df['dps_diff'].abs()
    merged_df['abs_hit_per_minute_diff'] = merged_df['hit_per_minute_diff'].abs()
    return merged_df

def compare_buff_uptime(buff_info_df1: pd.DataFrame, buff_info_df2: pd.DataFrame):
    buff_info_df1 = buff_info_df1[['name', 'up_time_pct', 'totalUses', 'type', 'guid']]
    buff_info_df2 = buff_info_df2[['name', 'up_time_pct', 'totalUses', 'type', 'guid']]
    merged_df = buff_info_df1.merge(buff_info_df2, on=['name', 'guid'], suffixes=('_1', '_2'), how=
                               'inner')
    merged_df['up_time_pct_diff'] = merged_df['up_time_pct_1'] - merged_df['up_time_pct_2']
    merged_df['total_uses_diff'] = merged_df['totalUses_1'] - merged_df['totalUses_2']
    merged_df['abs_up_time_pct_diff'] = merged_df['up_time_pct_diff'].abs()
    return merged_df

def compare_cast_info(cast_info_df1: pd.DataFrame, cast_info_df2: pd.DataFrame):
    cast_info_df1 = cast_info_df1[['name', 'cast_per_minute', 'total_time', 'guid']]
    cast_info_df2 = cast_info_df2[['name', 'cast_per_minute', 'total_time', 'guid']]
    merged_df = cast_info_df1.merge(cast_info_df2, on=['name', 'guid'], suffixes=('_1', '_2'), how=
                               'inner')
    merged_df['cast_per_minute_diff'] = merged_df['cast_per_minute_1'] - merged_df['cast_per_minute_2']
    merged_df['abs_cast_per_minute_diff'] = merged_df['cast_per_minute_diff'].abs()
    return merged_df

