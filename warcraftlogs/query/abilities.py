def generate_single_ability_query(ability_id):
    query = """
    query GetAbilityInfo($gameID: Int!) {
        gameData {
        ability(id: $gameID) {
            id
            icon
            name
            }
        }
    }
    """
    variables = {
        "gameID": ability_id
    }
    
    return {
        "query": query,
        "variables": variables
    }