import unittest
from unittest.mock import patch

from app.services.card_service import CardDataManager


class TestCardDataManager(unittest.TestCase):
    @patch("app.services.card_service.requests.get")
    def test_get_scryfall_card_versions(self, mock_get):
        # Mock the API response
        mock_get.return_value.json.return_value = {
            "data": [
                {
                    "set": "lea",
                    "set_name": "Limited Edition Alpha",
                    "lang": "en",
                    "finishes": ["nonfoil"],
                },
                {
                    "set": "4ed",
                    "set_name": "Fourth Edition",
                    "lang": "en",
                    "finishes": ["nonfoil"],
                },
                {
                    "set": "clb",
                    "set_name": "Commander Legends: Battle for Baldur's Gate",
                    "lang": "en",
                    "finishes": ["foil", "nonfoil"],
                },
            ],
            "has_more": False,
        }

        result = CardDataManager.get_scryfall_card_versions("Fireball")

        self.assertEqual(result["name"], "Fireball")
        self.assertEqual(len(result["sets"]), 3)
        self.assertEqual(result["languages"], ["en"])
        self.assertEqual(set(result["versions"]), {"foil", "nonfoil"})


if __name__ == "__main__":
    unittest.main()
