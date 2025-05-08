import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.card_service import CardService
from app.models.buylist import UserBuylist
from app.models.user_buylist_card import UserBuylistCard

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


@pytest.mark.asyncio
async def test_generate_purchase_links_shopify():
    fake_site = MagicMock()
    fake_site.method = "shopify"
    fake_site.api_url = "fake-api"
    fake_site.url = "https://shop.example.com"
    fake_site.name = "Shopify Test Site"

    purchase_data = [{"site_id": 1, "site_name": "Shopify Test Site", "cards": [{"name": "Lightning Bolt"}]}]

    active_sites = {1: fake_site}
    links = await CardService.generate_purchase_links(purchase_data, active_sites)

    assert len(links) == 1
    assert links[0]["purchase_url"].startswith("https://")
    assert links[0]["method"] == "shopify"


@pytest.mark.asyncio
async def test_create_buylist_returns_dict(async_session):
    buylist = await CardService.create_buylist(async_session, name="Test Buylist", user_id=1)
    assert isinstance(buylist, dict)
    assert "id" in buylist
    assert buylist["name"] == "Test Buylist"


@pytest.mark.asyncio
async def test_get_all_buylists_returns_dicts(async_session):
    # Create a buylist first
    await CardService.create_buylist(async_session, name="My Buylist", user_id=42)

    buylists = await CardService.get_all_buylists(async_session, user_id=42)
    assert isinstance(buylists, list)
    assert all(isinstance(b, dict) for b in buylists)
    assert buylists[0]["name"] == "My Buylist"


@pytest.mark.asyncio
@patch("app.services.card_service.CardService.get_redis_client")
async def test_fetch_scryfall_card_names_caches(mock_redis):
    redis_mock = AsyncMock()
    mock_redis.return_value = redis_mock

    redis_mock.set.return_value = True
    redis_mock.get.return_value = None

    names = await CardService.fetch_scryfall_card_names()
    assert isinstance(names, set)


@pytest.mark.asyncio
@patch("app.services.card_service.CardService.get_sets_data")
async def test_get_set_code_fuzzy_match(mock_sets_data):
    mock_sets_data.return_value = {
        "the brothers' war": {"code": "bro"},
        "dominaria united": {"code": "dmu"},
    }

    set_code = await CardService.get_set_code("Bro Extras")
    assert set_code == "bro"
