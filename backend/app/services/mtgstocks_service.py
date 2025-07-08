import asyncio
import aiohttp
import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any
from urllib.parse import quote
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MTGStocksService:
    """Service for interacting with MTGStocks API and scraping price data"""

    BASE_URL = "https://api.mtgstocks.com"
    SITE_URL = "https://www.mtgstocks.com"

    def __init__(self):
        self.session = None
        self._rate_limit_delay = 2  # seconds between requests
        self._last_request_time = 0

    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-CH-UA": '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        }
        self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        """Ensure we don't make requests too quickly"""
        import time

        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)

        self._last_request_time = time.time()

    async def search_cards(self, card_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for cards using MTGStocks autocomplete API

        Args:
            card_name: Name of the card to search for
            limit: Maximum number of results to return

        Returns:
            List of card dictionaries with id, name, slug, type
        """
        try:
            await self._rate_limit()

            encoded_name = quote(card_name)
            url = f"{self.BASE_URL}/search/autocomplete/{encoded_name}"

            logger.info(f"Searching MTGStocks for: {card_name} -> {url}")

            async with self.session.get(url) as response:
                logger.info(f"MTGStocks response status: {response.status}")
                if response.status == 200:
                    # Check content type - might be HTML or JSON
                    content_type = response.headers.get("content-type", "")

                    if "application/json" in content_type:
                        data = await response.json()
                        # Filter to only print types and limit results
                        cards = [card for card in data if card.get("type") == "print"][:limit]
                        logger.info(f"Found {len(cards)} cards for search: {card_name}")
                        return cards
                    else:
                        # If we get HTML, try to parse it
                        html = await response.text()
                        logger.warning(f"Got HTML response instead of JSON for: {card_name}")
                        return await self._parse_search_html(html, card_name)

                elif response.status == 403:
                    response_text = await response.text()
                    logger.error(f"403 Forbidden for {card_name}: {response_text[:200]}")
                    return []

                elif response.status == 429:
                    logger.warning(f"Rate limited searching for: {card_name}")
                    await asyncio.sleep(5)  # Wait longer for rate limits
                    return []

                else:
                    response_text = await response.text()
                    logger.warning(f"Search failed with status {response.status} for: {card_name}")
                    logger.warning(f"Response: {response_text[:200]}")
                    return []

        except Exception as e:
            logger.error(f"Error searching for card '{card_name}': {str(e)}")
            return []

    async def _parse_search_html(self, html: str, card_name: str) -> List[Dict[str, Any]]:
        """Parse HTML search results if JSON is not returned"""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Look for links or elements that might contain card information
            # This is a fallback for when the API returns HTML instead of JSON
            cards = []

            # Try to find card links or data
            card_links = soup.find_all("a", href=re.compile(r"/prints/\d+"))

            for link in card_links[:10]:  # Limit to 10 results
                href = link.get("href", "")
                card_id_match = re.search(r"/prints/(\d+)", href)

                if card_id_match:
                    card_id = int(card_id_match.group(1))
                    card_text = link.get_text(strip=True)

                    cards.append({"id": card_id, "name": card_text, "slug": f"print-{card_id}", "type": "print"})

            logger.info(f"Parsed {len(cards)} cards from HTML for: {card_name}")
            return cards

        except Exception as e:
            logger.error(f"Error parsing search HTML: {str(e)}")
            return []

    async def get_card_details(self, mtgstocks_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed card information including pricing

        Args:
            mtgstocks_id: The MTGStocks print ID

        Returns:
            Dictionary with card details and pricing info
        """
        try:
            await self._rate_limit()

            # Try API endpoint first (if available)
            api_url = f"{self.BASE_URL}/prints/{mtgstocks_id}"

            async with self.session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_api_response(data)
                elif response.status == 404:
                    logger.warning(f"Card {mtgstocks_id} not found")
                    return None

            # Fallback to scraping the webpage
            return await self._scrape_card_page(mtgstocks_id)

        except Exception as e:
            logger.error(f"Error getting card details for ID {mtgstocks_id}: {str(e)}")
            return None

    def _parse_api_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse API response into standardized format"""
        try:
            results = {
                "id": data.get("id"),
                "name": data.get("name"),
                "set": data.get("set", {}).get("name"),
                "set_code": data.get("set", {}).get("code"),
                "market_price": self._extract_price(data.get("prices", {}).get("market")),
                "avg_price": self._extract_price(data.get("prices", {}).get("average")),
                "low_price": self._extract_price(data.get("prices", {}).get("low")),
                "high_price": self._extract_price(data.get("prices", {}).get("high")),
                "url": f"{self.SITE_URL}/prints/{data.get('id')}",
                "last_updated": data.get("updated_at"),
                "foil_only": data.get("foil_only", False),
            }
            logger.info(f"Parsed API response: {results}")
            return results
        except Exception as e:
            logger.error(f"Error parsing API response: {str(e)}")
            return None

    async def _scrape_card_page(self, mtgstocks_id: int) -> Optional[Dict[str, Any]]:
        """
        Scrape card page for pricing information when API is unavailable

        Args:
            mtgstocks_id: The MTGStocks print ID

        Returns:
            Dictionary with scraped card data
        """
        try:
            await self._rate_limit()

            url = f"{self.SITE_URL}/prints/{mtgstocks_id}"

            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to scrape page for ID {mtgstocks_id}, status: {response.status}")
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                return self._parse_scraped_page(soup, mtgstocks_id)

        except Exception as e:
            logger.error(f"Error scraping card page for ID {mtgstocks_id}: {str(e)}")
            return None

    def _parse_scraped_page(self, soup: BeautifulSoup, mtgstocks_id: int) -> Optional[Dict[str, Any]]:
        """Parse scraped HTML page for card information"""
        try:
            # First, try to extract from meta description (most reliable)
            card_data = self._parse_meta_description(soup)
            if card_data:
                card_data["id"] = mtgstocks_id
                card_data["url"] = f"{self.SITE_URL}/prints/{mtgstocks_id}"
                logger.info(f"Successfully parsed meta description for ID {mtgstocks_id}")
                return card_data

            # Fallback: Look for custom MTG elements
            card_data = self._parse_mtg_custom_elements(soup, mtgstocks_id)
            if card_data and card_data.get("name"):
                logger.info(f"Successfully parsed custom elements for ID {mtgstocks_id}")
                return card_data

            # Final fallback: Original parsing method
            card_data = self._parse_fallback_method(soup, mtgstocks_id)
            if card_data:
                logger.info(f"Successfully parsed with fallback method for ID {mtgstocks_id}")
                return card_data

            logger.warning(f"Failed to parse any data for ID {mtgstocks_id}")
            return None

        except Exception as e:
            logger.error(f"Error parsing scraped page: {str(e)}")
            return None

    def _parse_meta_description(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract card data from meta description - most reliable method"""
        try:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if not meta_desc:
                return None

            content = meta_desc.get("content", "")
            logger.debug(f"Meta description content: {content}")

            # Parse format: "Card Name (SET) #Number • Low: $X, Average: $Y, Market: $Z, Foil: $A • Set Name • Magic: The Gathering, MTG"

            # Split by bullet points
            main_parts = content.split(" • ")
            if len(main_parts) < 2:
                return None

            # Parse card name, set code, and number
            name_set_part = main_parts[0]
            name_match = re.match(r"(.+?)\s*\(([^)]+)\)\s*#?(\d+)?", name_set_part)

            if not name_match:
                return None

            card_name = name_match.group(1).strip()
            set_code = name_match.group(2).strip()

            # Parse prices from the price part
            price_part = main_parts[1] if len(main_parts) > 1 else ""
            prices = self._extract_prices_from_description(price_part)

            # Extract set name (3rd part)
            set_name = main_parts[2].strip() if len(main_parts) > 2 else None

            return {
                "name": card_name,
                "set": set_name,
                "set_code": set_code,
                "market_price": prices.get("market"),
                "avg_price": prices.get("average"),
                "low_price": prices.get("low"),
                "foil_price": prices.get("foil"),
                "market_foil_price": prices.get("market_foil"),
                "last_updated": None,
                "foil_only": False,
            }

        except Exception as e:
            logger.error(f"Error parsing meta description: {str(e)}")
            return None

    def _extract_prices_from_description(self, price_text: str) -> Dict[str, Decimal]:
        """Extract all price types from meta description price text"""
        prices = {}

        # Patterns for different price types
        patterns = {
            "low": r"Low:\s*\$(\d+\.\d{2})",
            "average": r"Average:\s*\$(\d+\.\d{2})",
            "market": r"Market:\s*\$(\d+\.\d{2})",
            "foil": r"Foil:\s*\$(\d+\.\d{2})",
            "market_foil": r"Market foil:\s*\$(\d+\.\d{2})",
        }

        for price_type, pattern in patterns.items():
            match = re.search(pattern, price_text)
            if match:
                try:
                    prices[price_type] = Decimal(match.group(1))
                except (ValueError, TypeError):
                    continue

        return prices

    def _parse_mtg_custom_elements(self, soup: BeautifulSoup, mtgstocks_id: int) -> Optional[Dict[str, Any]]:
        """Parse custom MTG elements like mtg-card-box"""
        try:
            card_data = {
                "id": mtgstocks_id,
                "url": f"{self.SITE_URL}/prints/{mtgstocks_id}",
            }

            # Look for mtg-card-box elements
            price_boxes = soup.find_all("mtg-card-box")

            for box in price_boxes:
                title = box.get("title", "")

                if "price" in title.lower():
                    # Extract prices from this box
                    price_data = self._extract_prices_from_element(box)
                    card_data.update(price_data)

            # Look for card name in title or heading
            title_elem = soup.find("title") or soup.find("h1")
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                # Extract card name from title like "Card Name • Set Name (SET)"
                name_match = re.match(r"(.+?)\s*•", title_text)
                if name_match:
                    card_data["name"] = name_match.group(1).strip()

            # Look for purchase buttons to identify supported stores
            purchase_buttons = soup.find_all("mtg-purchase-button")
            stores = []
            for button in purchase_buttons:
                store_name = button.get("storename")
                if store_name:
                    stores.append(store_name)

            if stores:
                card_data["available_stores"] = stores

            return card_data if card_data.get("name") else None

        except Exception as e:
            logger.error(f"Error parsing MTG custom elements: {str(e)}")
            return None

    def _extract_prices_from_element(self, element) -> Dict[str, Any]:
        """Extract price information from a custom element"""
        prices = {}

        # Look for price text patterns within the element
        element_text = element.get_text() if hasattr(element, "get_text") else str(element)

        # Common price patterns
        price_patterns = {
            "market_price": r"Market[:\s]*\$(\d+\.\d{2})",
            "avg_price": r"Average[:\s]*\$(\d+\.\d{2})",
            "low_price": r"Low[:\s]*\$(\d+\.\d{2})",
            "high_price": r"High[:\s]*\$(\d+\.\d{2})",
            "foil_price": r"Foil[:\s]*\$(\d+\.\d{2})",
        }

        for price_type, pattern in price_patterns.items():
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                try:
                    prices[price_type] = Decimal(match.group(1))
                except (ValueError, TypeError):
                    continue

        return prices

    def _parse_fallback_method(self, soup: BeautifulSoup, mtgstocks_id: int) -> Optional[Dict[str, Any]]:
        """Original fallback parsing method"""
        try:
            # Extract card name
            card_name = None
            name_elem = soup.find("h1") or soup.find("h2")
            if name_elem:
                card_name = name_elem.get_text(strip=True)

            # Extract set information
            set_name = None
            set_code = None
            set_elem = soup.find("span", class_="set-name") or soup.find("div", class_="set-info")
            if set_elem:
                set_text = set_elem.get_text(strip=True)
                # Try to extract set code in parentheses
                set_match = re.search(r"\(([^)]+)\)", set_text)
                if set_match:
                    set_code = set_match.group(1)
                    set_name = set_text.replace(f"({set_code})", "").strip()
                else:
                    set_name = set_text

            # Extract pricing information
            prices = {}

            # Look for price elements with various selectors
            price_selectors = [
                ".price-box .price",
                ".market-price",
                ".avg-price",
                ".price-current",
                "[data-price]",
                ".price",
            ]

            for selector in price_selectors:
                price_elems = soup.select(selector)
                for elem in price_elems:
                    price_text = elem.get_text(strip=True)
                    price_value = self._extract_price_from_text(price_text)
                    if price_value:
                        # Try to determine price type from context
                        price_type = self._determine_price_type(elem, price_text)
                        prices[price_type] = price_value

            # If no prices found, try to find any dollar amounts
            if not prices:
                dollar_pattern = r"\$(\d+(?:\.\d{2})?)"
                dollar_matches = re.findall(dollar_pattern, str(soup))
                if dollar_matches:
                    # Use the first reasonable price found
                    for match in dollar_matches:
                        price = Decimal(match)
                        if 0.01 <= price <= 10000:  # Reasonable price range
                            prices["market"] = price
                            break

            return {
                "id": mtgstocks_id,
                "name": card_name,
                "set": set_name,
                "set_code": set_code,
                "market_price": prices.get("market"),
                "avg_price": prices.get("average", prices.get("avg")),
                "low_price": prices.get("low"),
                "high_price": prices.get("high"),
                "url": f"{self.SITE_URL}/prints/{mtgstocks_id}",
                "last_updated": None,
                "foil_only": "foil" in str(soup).lower(),
            }

        except Exception as e:
            logger.error(f"Error in fallback parsing method: {str(e)}")
            return None

    def _determine_price_type(self, elem, price_text: str) -> str:
        """Determine the type of price based on element context"""
        elem_str = str(elem).lower()
        text_lower = price_text.lower()

        if "market" in elem_str or "market" in text_lower:
            return "market"
        elif "avg" in elem_str or "average" in text_lower:
            return "average"
        elif "low" in elem_str or "low" in text_lower:
            return "low"
        elif "high" in elem_str or "high" in text_lower:
            return "high"
        else:
            return "market"  # Default to market price

    def _extract_price_from_text(self, text: str) -> Optional[Decimal]:
        """Extract price value from text"""
        try:
            # Remove currency symbols and extract numeric value
            price_match = re.search(r"\$?(\d+(?:\.\d{2})?)", text.replace(",", ""))
            if price_match:
                return Decimal(price_match.group(1))
        except (ValueError, TypeError):
            pass
        return None

    def _extract_price(self, price_data) -> Optional[Decimal]:
        """Extract price from various price data formats"""
        if price_data is None:
            return None

        try:
            if isinstance(price_data, (int, float)):
                return Decimal(str(price_data))
            elif isinstance(price_data, str):
                return self._extract_price_from_text(price_data)
            elif isinstance(price_data, dict):
                # Handle nested price objects
                return self._extract_price(price_data.get("value") or price_data.get("amount"))
        except (ValueError, TypeError):
            pass

        return None

    async def get_market_price(self, mtgstocks_id: int) -> Optional[Decimal]:
        """
        Get just the market price for a card (optimized for watchlist checking)

        Args:
            mtgstocks_id: The MTGStocks print ID

        Returns:
            Market price as Decimal or None
        """
        try:
            card_details = await self.get_card_details(mtgstocks_id)
            if card_details:
                return card_details.get("market_price") or card_details.get("avg_price")
            return None
        except Exception as e:
            logger.error(f"Error getting market price for ID {mtgstocks_id}: {str(e)}")
            return None

    async def search_and_get_best_match(
        self, card_name: str, set_code: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a card and return the best match with pricing

        Args:
            card_name: Name of the card
            set_code: Optional set code to help with matching

        Returns:
            Best matching card with pricing information
        """
        try:
            # Search for the card
            search_results = await self.search_cards(card_name)

            if not search_results:
                return None

            # Find best match
            best_match = None

            # If we have a set code, try to find exact match
            if set_code:
                for card in search_results:
                    # Get detailed info to check set
                    details = await self.get_card_details(card["id"])
                    if details and details.get("set_code", "").lower() == set_code.lower():
                        best_match = details
                        break

            # If no set match found, use first result (closest name match)
            if not best_match and search_results:
                best_match = await self.get_card_details(search_results[0]["id"])

            return best_match

        except Exception as e:
            logger.error(f"Error in search_and_get_best_match for '{card_name}': {str(e)}")
            return None


# Convenience function for one-off requests
async def get_mtgstocks_price(mtgstocks_id: int) -> Optional[Decimal]:
    """
    Get market price for a card (standalone function)

    Args:
        mtgstocks_id: The MTGStocks print ID

    Returns:
        Market price as Decimal or None
    """
    try:
        async with MTGStocksService() as service:
            return await service.get_market_price(mtgstocks_id)
    except Exception as e:
        logger.error(f"Error getting MTGStocks price for ID {mtgstocks_id}: {str(e)}")
        return None


# Convenience function for searching cards
async def search_mtgstocks_cards(card_name: str, set_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Search for a card and return best match with pricing

    Args:
        card_name: Name of the card to search for
        set_code: Optional set code for better matching

    Returns:
        Best matching card data with pricing
    """
    try:
        async with MTGStocksService() as service:
            return await service.search_and_get_best_match(card_name, set_code)
    except Exception as e:
        logger.error(f"Error searching MTGStocks for '{card_name}': {str(e)}")
        return None
