import json
from typing import Literal, Optional, Union

def get_table_data(
    report_code: str,
    fight_id: Union[int, list[int]],
    source_id: Optional[int] = None,
    player_name: Optional[str] = None,
    data_type: Literal["Buffs", "DamageDone"] = "DamageDone",
    **kwargs
) -> str:
    """
    Generate a GraphQL query to get table data from WarcraftLogs.
    
    Args:
        report_code: The unique report code
        fight_id: Single fight ID or list of fight IDs to query
        source_id: Optional actor ID to filter by
        player_name: Optional player name to filter by (alternative to source_id)
        data_type: Type of data to query - "Buffs" or "DamageDone"
        **kwargs: Additional filter arguments to pass to the table query
        
    Returns:
        GraphQL query string
    """
    # Convert single fight ID to list
    if isinstance(fight_id, int):
        fight_id = [fight_id]
        
    # Build the filter arguments
    filter_args = []
    
    if source_id:
        filter_args.append(f"sourceID: {source_id}")
    
    # Add any additional filter arguments
    for key, value in kwargs.items():
        if isinstance(value, str):
            filter_args.append(f'{key}: "{value}"')
        else:
            filter_args.append(f'{key}: {value}')
            
    # Join all filter arguments
    filter_str = ", ".join([
        f'fightIDs: {fight_id}',
        f'dataType: {data_type}',
        *filter_args
    ])

    # Build the complete query
    query = f"""
    query {{
        reportData {{
            report(code: "{report_code}") {{
                table(
                {filter_str}
                )
            }}
        }}
    }}
    """
    
    return query

def example_usage():
    # Example 1: Get damage done for a specific player by source ID
    damage_query = get_table_data(
        report_code="abcd1234",
        fight_id=1,
        source_id=42,
        data_type="DamageDone"
    )
    print("Damage Query:")
    print(damage_query)
    
    # Example 2: Get buffs for multiple fights with additional filters
    buff_query = get_table_data(
        report_code="abcd1234",
        fight_id=[1, 2, 3],
        player_name="PlayerName",
        data_type="Buffs",
        hostilityType="Friendlies",
        killType="Kills"
    )
    print("\nBuff Query:")
    print(buff_query)

if __name__ == "__main__":
    example_usage() 