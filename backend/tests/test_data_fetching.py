import sys
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from bs4 import BeautifulSoup

from app.utils.data_fetcher import ExternalDataSynchronizer


class TestExternalDataSynchronizer(unittest.TestCase):

    def setUp(self):
        self.sample_html = """
        <div class="content clearfix">
            <div class="products-container browse">
                <li class="product">
                    <div class="meta">
                        <span class="category">Sample Edition</span>
                        <h4 class="name">Sample Card</h4>
                    </div>
                    <div class="variants">
                        <div class="variant-row">
                            <span class="variant-short-info variant-description">Near Mint, English</span>
                            <span class="variant-short-info variant-qty">5 in stock</span>
                            <span class="regular price">$10.00</span>
                        </div>
                    </div>
                </li>
            </div>
        </div>
        """
        self.soup = BeautifulSoup(self.sample_html, "html.parser")
        self.site = Mock(name="Sample Site")
        self.card_names = ["Sample Card"]

    @patch("app.utils.data_fetcher.parse_card_string")
    @patch("app.utils.data_fetcher.clean_card_name")
    def test_extract_info(self, mock_clean_card_name, mock_parse_card_string):
        mock_parse_card_string.return_value = {
            "name": "Sample Card",
            "version": None,
            "foil": False,
        }
        mock_clean_card_name.return_value = "Sample Card"

        result = ExternalDataSynchronizer.extract_info(
            self.soup,
            self.site,
            self.card_names,
            strategy=ExternalDataSynchronizer.STRATEGY_SCRAPPER,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["name"], "Sample Card")
        self.assertEqual(result.iloc[0]["edition"], "Sample Edition")
        self.assertEqual(result.iloc[0]["quality"], "Near Mint")
        self.assertEqual(result.iloc[0]["language"], "English")
        self.assertEqual(result.iloc[0]["quantity"], 5)
        self.assertEqual(result.iloc[0]["price"], 10.0)

    @patch("app.utils.data_fetcher.db.session")
    @patch("app.utils.data_fetcher.Scan")
    @patch("app.utils.data_fetcher.MarketplaceCard")
    @patch("app.utils.data_fetcher.ScanResult")
    def test_save_cards_to_db(
        self, mock_scan_result, mock_marketplace_card, mock_scan, mock_session
    ):
        site = Mock(name="Test Site")
        cards_df = pd.DataFrame(
            [
                {
                    "name": "Test Card",
                    "edition": "Test Edition",
                    "version": "Regular",
                    "foil": False,
                    "quality": "Near Mint",
                    "language": "English",
                    "quantity": 5,
                    "price": 10.0,
                }
            ]
        )

        ExternalDataSynchronizer.save_cards_to_db(site, cards_df)

        mock_scan.assert_called_once_with()
        mock_marketplace_card.assert_called_once_with(
            site=site.name,  # Change this line
            name="Test Card",
            edition="Test Edition",
            version="Regular",
            foil=False,
            quality="Near Mint",
            language="English",
            quantity=5,
            price=10.0,
        )
        mock_scan_result.assert_called_once()
        self.assertEqual(mock_session.add.call_count, 3)
        self.assertEqual(mock_session.commit.call_count, 2)

    @patch("app.utils.data_fetcher.parse_card_string")
    @patch("app.utils.data_fetcher.clean_card_name")
    def test_extract_info_no_matching_cards(
        self, mock_clean_card_name, mock_parse_card_string
    ):
        mock_parse_card_string.return_value = {
            "name": "Non-existent Card",
            "version": None,
            "foil": False,
        }
        mock_clean_card_name.return_value = "Non-existent Card"

        card_names = ["Some Other Card"]  # This should not match the card in the HTML
        result = ExternalDataSynchronizer.extract_info(
            self.soup,
            self.site,
            card_names,
            strategy=ExternalDataSynchronizer.STRATEGY_SCRAPPER,
        )

        self.assertTrue(result.empty, f"Expected empty DataFrame, but got: {result}")

    def test_extract_info_empty_soup(self):
        empty_soup = BeautifulSoup("", "html.parser")
        result = ExternalDataSynchronizer.extract_info(
            empty_soup,
            self.site,
            self.card_names,
            strategy=ExternalDataSynchronizer.STRATEGY_SCRAPPER,
        )
        self.assertTrue(result.empty)

    @patch("app.utils.data_fetcher.db.session")
    @patch("app.utils.data_fetcher.Scan")
    def test_save_cards_to_db_empty_dataframe(self, mock_scan, mock_session):
        site = Mock(name="Test Site")
        empty_df = pd.DataFrame()
        card_names = []

        ExternalDataSynchronizer.save_cards_to_db(site, empty_df)

        mock_scan.assert_called_once_with(card_names=card_names)
        self.assertEqual(mock_session.add.call_count, 1)
        self.assertEqual(mock_session.commit.call_count, 2)

    @patch("app.utils.data_fetcher.parse_card_string")
    @patch("app.utils.data_fetcher.clean_card_name")
    def test_process_product_item(self, mock_clean_card_name, mock_parse_card_string):
        mock_parse_card_string.return_value = {
            "name": "Sample Card",
            "version": None,
            "foil": False,
        }
        mock_clean_card_name.return_value = "Sample Card"

        site = Mock(name="Test Site")
        item = self.soup.find("li", {"class": "product"})
        card_names = ["Sample Card"]
        excluded_categories = set()

        result = ExternalDataSynchronizer.process_product_item(
            item, site, card_names, excluded_categories
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Sample Card")
        self.assertEqual(result["edition"], "Sample Edition")
        self.assertEqual(result["site"], site.name)  # Change this line

    def test_strategy_add_to_cart(self):
        card_attrs = {"name": "Sample Card", "edition": "Sample Edition", "foil": False}
        variant_html = """
        <div class="variant-row">
            <form class="add-to-cart-form" data-name="Sample Card - Regular" data-variant="Near Mint, English" data-price="$10.00" data-category="Sample Edition">
                <select class="qty" max="5"></select>
            </form>
        </div>
        """
        variant = BeautifulSoup(variant_html, "html.parser").find(
            "div", {"class": "variant-row"}
        )

        with patch(
            "app.utils.data_fetcher.ExternalDataSynchronizer.find_name_version_foil",
            return_value=("Sample Card", "Regular", "Non-Foil"),
        ):
            with patch(
                "app.utils.data_fetcher.ExternalDataSynchronizer.normalize_variant_description",
                return_value=["Near Mint", "English"],
            ):
                with patch("app.utils.data_fetcher.normalize_price", return_value=10.0):
                    result = ExternalDataSynchronizer.strategy_add_to_cart(
                        card_attrs, variant
                    )

        self.assertIsNotNone(result, "strategy_add_to_cart returned None")
        if result is not None:
            self.assertIsInstance(result, dict)
            self.assertEqual(result["name"], "Sample Card")
            self.assertEqual(result["quality"], "Near Mint")
            self.assertEqual(result["language"], "English")
            self.assertEqual(result["quantity"], 5)
            self.assertEqual(result["price"], 10.0)


def run_tests_with_output():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestExternalDataSynchronizer)
    unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)


if __name__ == "__main__":
    run_tests_with_output()
