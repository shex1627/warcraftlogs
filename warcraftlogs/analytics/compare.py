import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Tuple

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

def compare_metric_info(metric_info_df1: pd.DataFrame, metric_info_df2: pd.DataFrame, metric_type: str='dps'):
    metric_info_df1 = metric_info_df1[['name', metric_type, 'hit_per_minute', 'guid']]
    metric_info_df2 = metric_info_df2[['name', metric_type, 'hit_per_minute', 'guid']]
    merged_df = metric_info_df1.merge(metric_info_df2, on=['name', 'guid'], suffixes=('_1', '_2'), how=
                               'inner')
    merged_df[f'{metric_type}_diff'] = merged_df[f'{metric_type}_1'] - merged_df[f'{metric_type}_2']
    merged_df['hit_per_minute_diff'] = merged_df['hit_per_minute_1'] - merged_df['hit_per_minute_2']
    merged_df[f'abs_{metric_type}_diff'] = merged_df[f'{metric_type}_diff'].abs()
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

def compare_casts(player1_df: pd.DataFrame, player2_df: pd.DataFrame,
                 player1_name: str = "Player 1", player2_name: str = "Player 2") -> pd.DataFrame:
    """
    Compare cast breakdown between two players.
    
    Args:
        player1_df: Cast DataFrame for first player
        player2_df: Cast DataFrame for second player
        player1_name: Name for first player (for column labels)
        player2_name: Name for second player (for column labels)
        
    Returns:
        DataFrame with cast comparison metrics sorted by absolute CPM difference
    """
    
    # Merge dataframes on ability_name
    merged = pd.merge(
        player1_df[['ability_name', 'total_casts', 'casts_per_minute']],
        player2_df[['ability_name', 'total_casts', 'casts_per_minute']],
        on='ability_name',
        how='outer',
        suffixes=(f'_{player1_name}', f'_{player2_name}')
    ).fillna(0)
    
    # Calculate differences and ratios
    merged['total_casts_diff'] = merged[f'total_casts_{player1_name}'] - merged[f'total_casts_{player2_name}']
    
    merged['cpm_diff'] = merged[f'casts_per_minute_{player1_name}'] - merged[f'casts_per_minute_{player2_name}']
    
    # Calculate ratio (Player1 / Player2)
    merged['cpm_ratio'] = np.where(
        merged[f'casts_per_minute_{player2_name}'] != 0,
        merged[f'casts_per_minute_{player1_name}'] / merged[f'casts_per_minute_{player2_name}'],
        np.inf
    )
    
    # Sort by absolute CPM difference
    merged['abs_cpm_diff'] = abs(merged['cpm_diff'])
    merged = merged.sort_values('abs_cpm_diff', ascending=False).drop('abs_cpm_diff', axis=1)
    
    # Round numeric columns for readability
    numeric_cols = ['cpm_diff', 'cpm_ratio']
    merged[numeric_cols] = merged[numeric_cols].round(2)
    
    return merged.reset_index(drop=True)

def compare_damage(player1_df: pd.DataFrame, player2_df: pd.DataFrame, 
                  player1_name: str = "Player 1", player2_name: str = "Player 2") -> pd.DataFrame:
    """
    Compare damage breakdown between two players.
    
    Args:
        player1_df: Damage DataFrame for first player
        player2_df: Damage DataFrame for second player
        player1_name: Name for first player (for column labels)
        player2_name: Name for second player (for column labels)
        
    Returns:
        DataFrame with damage comparison metrics sorted by absolute DPS difference
    """
    
    # Merge dataframes on ability_name
    merged = pd.merge(
        player1_df[['ability_name', 'total_damage', 'damage_percent', 'dps', 'avg_damage']],
        player2_df[['ability_name', 'total_damage', 'damage_percent', 'dps', 'avg_damage']],
        on='ability_name',
        how='outer',
        suffixes=(f'_{player1_name}', f'_{player2_name}')
    ).fillna(0)
    
    # Calculate differences and percentages
    merged['total_damage_diff'] = merged[f'total_damage_{player1_name}'] - merged[f'total_damage_{player2_name}']
    merged['total_damage_diff_pct'] = np.where(
        merged[f'total_damage_{player2_name}'] != 0,
        (merged['total_damage_diff'] / merged[f'total_damage_{player2_name}']) * 100,
        np.inf
    )
    
    merged['damage_percent_diff'] = merged[f'damage_percent_{player1_name}'] - merged[f'damage_percent_{player2_name}']
    
    merged['dps_diff'] = merged[f'dps_{player1_name}'] - merged[f'dps_{player2_name}']
    merged['dps_diff_pct'] = np.where(
        merged[f'dps_{player2_name}'] != 0,
        (merged['dps_diff'] / merged[f'dps_{player2_name}']) * 100,
        np.inf
    )
    
    merged['avg_damage_diff'] = merged[f'avg_damage_{player1_name}'] - merged[f'avg_damage_{player2_name}']
    merged['avg_damage_diff_pct'] = np.where(
        merged[f'avg_damage_{player2_name}'] != 0,
        (merged['avg_damage_diff'] / merged[f'avg_damage_{player2_name}']) * 100,
        np.inf
    )
    
    # Sort by absolute DPS difference
    merged['abs_dps_diff'] = abs(merged['dps_diff'])
    merged = merged.sort_values('abs_dps_diff', ascending=False).drop('abs_dps_diff', axis=1)
    
    # Round numeric columns for readability
    numeric_cols = ['total_damage_diff_pct', 'damage_percent_diff', 'dps_diff', 'dps_diff_pct', 'avg_damage_diff', 'avg_damage_diff_pct']
    merged[numeric_cols] = merged[numeric_cols].round(2)
    
    return merged.reset_index(drop=True)


def compare_buffs(player1_df: pd.DataFrame, player2_df: pd.DataFrame,
                 player1_name: str = "Player 1", player2_name: str = "Player 2") -> pd.DataFrame:
    """
    Compare buff uptime between two players (intersection only).
    
    Args:
        player1_df: Buff DataFrame for first player
        player2_df: Buff DataFrame for second player
        player1_name: Name for first player (for column labels)
        player2_name: Name for second player (for column labels)
        
    Returns:
        DataFrame with buff comparison metrics for shared buffs only, 
        sorted by absolute uptime percentage difference
    """
    
    # Get intersection of buffs (inner join)
    merged = pd.merge(
        player1_df[['buff_name', 'total_uptime_seconds', 'uptime_percentage', 'total_applications', 'avg_duration_seconds']],
        player2_df[['buff_name', 'total_uptime_seconds', 'uptime_percentage', 'total_applications', 'avg_duration_seconds']],
        on='buff_name',
        how='inner',  # Only shared buffs
        suffixes=(f'_{player1_name}', f'_{player2_name}')
    )
    
    # Calculate differences
    merged['uptime_seconds_diff'] = merged[f'total_uptime_seconds_{player1_name}'] - merged[f'total_uptime_seconds_{player2_name}']
    merged['uptime_pct_diff'] = merged[f'uptime_percentage_{player1_name}'] - merged[f'uptime_percentage_{player2_name}']
    merged['applications_diff'] = merged[f'total_applications_{player1_name}'] - merged[f'total_applications_{player2_name}']
    merged['avg_duration_diff'] = merged[f'avg_duration_seconds_{player1_name}'] - merged[f'avg_duration_seconds_{player2_name}']
    
    # Calculate percentage differences
    merged['uptime_pct_diff_relative'] = np.where(
        merged[f'uptime_percentage_{player2_name}'] != 0,
        (merged['uptime_pct_diff'] / merged[f'uptime_percentage_{player2_name}']) * 100,
        np.inf
    )
    
    # Sort by absolute uptime percentage difference
    merged['abs_uptime_pct_diff'] = abs(merged['uptime_pct_diff'])
    merged = merged.sort_values('abs_uptime_pct_diff', ascending=False).drop('abs_uptime_pct_diff', axis=1)
    
    # Round numeric columns for readability
    numeric_cols = ['uptime_seconds_diff', 'uptime_pct_diff', 'avg_duration_diff', 'uptime_pct_diff_relative']
    merged[numeric_cols] = merged[numeric_cols].round(2)
    
    return merged.reset_index(drop=True)
