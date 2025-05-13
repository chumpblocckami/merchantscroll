from src.drawer import display_deck

if __name__ == "__main__":

    mock_deck = {
        "main": {"Yotian Soldier": 60},
        "side": {
            "Yotian Soldier": 15,
        },
        "player": "chumpblocckami",
        "tournament": "LPTAA tournament",
        "date": "2023-10-01",
    }

    fig = display_deck(deck=mock_deck)
    fig.savefig("./tests/test_decklist.png", dpi=100, bbox_inches="tight")
