import asyncio
import json
import logging
from aiohttp import ClientSession, ClientTimeout
import urllib

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

list_of_urls = [
 'https://www.atlascollectables.com/products/multi_search',
 'https://www.topdeckhero.com/products/multi_search',
 'https://tome2boutique.crystalcommerce.com/products/multi_search',
 'https://levalet.crystalcommerce.com/products/multi_search',
 'https://comichunter.crystalcommerce.com/products/multi_search',
 'https://www.gamekeeperonline.com/products/multi_search',
 'https://lesecretdeskorrigans.crystalcommerce.com/products/multi_search',
 'https://godsarena.crystalcommerce.com/products/multi_search',
 'https://jeux3dragons.crystalcommerce.com/products/multi_search',
 'https://cartamagica.crystalcommerce.com/products/multi_search',
 'https://kanatacg.crystalcommerce.com/products/multi_search',
 'https://acgamesonline.crystalcommerce.com/products/multi_search',
 'https://collect-edition.crystalcommerce.com/products/multi_search',
 'https://www.expeditionjeux.com/products/multi_search',
 'https://magiccave.crystalcommerce.com/products/multi_search',
 'https://orchardcitygames.crystalcommerce.com/products/multi_search',
 'https://jjcards.crystalcommerce.com/products/multi_search',
 'https://dragontcg.crystalcommerce.com/products/multi_search',
 'https://firstplayer.crystalcommerce.com/products/multi_search',
 'https://mtgnorth.crystalcommerce.com/products/multi_search',
 'https://jittedivision.crystalcommerce.com/products/multi_search',
 'https://gamersden.crystalcommerce.com/products/multi_search',
 'https://gauntletgamesvictoria.crystalcommerce.com/products/multi_search',
 'https://sequencecomics.crystalcommerce.com/products/multi_search',
 'https://tradingpost.roundtabletavern.com/products/multi_search',
 'https://mtg.collect-edition.com/products/multi_search',
 'https://www.mozmagic.com/products/multi_search',
 'https://a2ztcg.crystalcommerce.com/products/multi_search',
 'https://thebeardeddragongames.crystalcommerce.com/products/multi_search',
 'https://brainstormgamespdx.crystalcommerce.com/products/multi_search',
 'https://www.thetoytrove.com/products/multi_search',
 'https://www.noblecards.ca/products/multi_search',
 'https://www.cbagames.com/products/multi_search',
 'https://www.bruteforcemtg.com/products/multi_search'
]
list_of_shopify_urls = [
    'https://obsidiangames.ca/pages/mtg-deck-builder',
    'https://houseofcards.ca/pages/deck-builder'
]
list_api_urls = [
    'obsidiangamesvernon.myshopify.com',
    'house-of-cards-mtg.myshopify.com'
]
headers2 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
}


headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "DNT": "1",
    "Origin": "https://orchardcitygames.crystalcommerce.com",
    "Referer": "https://orchardcitygames.crystalcommerce.com/products/multi_search",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Sec-GPC": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
card_list = [
    "Lifetime Pass Holder", "Academy Manufactor", "Akroma's Will", "Ancient Brass Dragon",
    "Ancient Copper Dragon", "Ancient Den", "Ancient Gold Dragon", "Arcane Signet",
    "Attempted Murder", "Bag of Devouring", "Barbarian Class", "Battlefield Forge",
    "Berserker's Frenzy", "Big Score", "Black Market Connections",
    "Brightclimb Pathway // Grimclimb Pathway", "Caesar, Legion's Emperor",
    "Cavern-Hoard Dragon", "Caves of Koilos", "Chaos Channeler", "Chaos Dragon",
    "Circuits Act", "Clifftop Retreat", "Clown Car", "Clowning Around",
    "Comet, Stellar Pup", "Command Tower", "Component Pouch", "Corrupted Conviction",
    "Cyberman Patrol", "Danse Macabre", "Deadly Dispute", "Delina, Wild Mage",
    "Diamond Pick-Axe", "Dragonskull Summit", "Ebony Fly", "Exotic Orchard",
    "Fetid Heath", "Goldspan Dragon", "Graven Cairns", "Great Furnace",
    "Hoarding Ogre", "Isolated Chapel", "Jan Jansen, Chaos Crafter", "Lightfoot Rogue",
    "Luxury Suite", "Maddening Hex", "Mines of Moria", "Mondrak, Glory Dominus",
    "Monologue Tax", "Myrkul's Edict", "Needleverge Pathway // Pillarverge Pathway",
    "Night Shift of the Living Dead", "Ojer Taq, Deepest Foundation // Temple of Civilization",
    "Prosperous Partnership", "Rain of Riches", "Reckless Endeavor", "Recruitment Drive",
    "Revel in Riches", "Revivify", "Rugged Prairie", "Ruinous Ultimatum", "Six-Sided Die",
    "Slight Malfunction", "Smothering Tithe", "Sol Ring", "Spectator Seating",
    "Strength-Testing Hammer", "Sword of Hours", "The Deck of Many Things",
    "The Reaver Cleaver", "Thousand Moons Smithy // Barracks of the Thousand", "Thunderwave",
    "Tocasia's Welcome", "Treasure Chest", "Unwinding Clock", "Valiant Endeavor",
    "Vault of Champions", "Vault of Whispers", "Vexing Puzzlebox", "Wand of Wonder",
    "Wyll, Blade of Frontiers", "Wyll's Reversal", "Xenosquirrels"
]

async def test_site(url):
    relevant_headers = headers
    async with ClientSession() as session:
        try:
            # Step 1: Perform GET Request
            async with session.get(url) as get_response:
                if get_response.status != 200:
                    logger.error(f"GET failed with status {get_response.status} for {url}")
                    return

                # Extract cookies
                cookies = "; ".join([f"{key}={value.value}" for key, value in get_response.cookies.items()])
                logger.info(f"Cookies extracted: {cookies}")

                # Filter relevant headers for POST
                relevant_headers.update({
                    key: value
                    for key, value in get_response.headers.items()
                    if key.lower() in ['cache-control', 'content-type', 'accept-language', 'accept-encoding']
                })

                relevant_headers.update({
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Cookie": cookies,
                })

                # Log the formed headers
                #logger.info(f"Formed POST headers: {relevant_headers}")

                query_string = "\r\n".join(card_list)
                encoded_query = urllib.parse.quote_plus(query_string)

                # Step 2: Prepare Payload
                payload = {
                    "authenticity_token": "22RG7%2Bkevd0Y2er8Jp4di9EA1mV3xrAGksVetPkPIgg%3D",
                    #"query": "\r\n".join(card_list),
                    #"query": "Forest%0D%0AMox%20Emerald%0D%0ABirds%20of%20Paradise%0D%0AWrath%20of%20God%0D%0AFact%20or%20Fiction",
                    "query": encoded_query,
                    "submit": "Continue",
                }

                # Step 3: Perform POST Request
                async with session.post(url, data=payload, headers=relevant_headers) as post_response:
                    if post_response.status == 200:
                        response_text = await post_response.text()
                        logger.info(f"POST succeeded. Response length: {len(response_text)} ")
                        if "your search" in response_text.lower():
                            index = response_text.lower().index("your search")
                            start = max(index - 100, 0)
                            end = min(index + 100, len(response_text))
                            snippet = response_text[start:end]
                            logger.info(f"POST succeeded but no results found. Context: {snippet}")
                    else:
                        logger.error(f"POST failed with status {post_response.status}")
                        error_detail = await post_response.text()
                        logger.error(f"Error details: {error_detail[:500]}")

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")

async def test_shopify_site(url, api):
    relevant_headers = headers
    async with ClientSession() as session:
        try:
            async with session.get(url) as get_response:
                if get_response.status != 200:
                    logger.error(f"GET failed with status {get_response.status} for {url}")
                    return

                # Extract cookies
                cookies = "; ".join([f"{key}={value.value}" for key, value in get_response.cookies.items()])
                logger.info(f"Cookies extracted: {cookies}")

                # Filter relevant headers for POST
                relevant_headers = {
                    key: value
                    for key, value in get_response.headers.items()
                    if key.lower() in ['cache-control', 'content-type', 'accept-language', 'accept-encoding']
                }
                relevant_headers.update({
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Cookie": cookies,
                })

            # Log the formed headers
            logger.info(f"Formed POST headers: {relevant_headers}")
                    
            # Format the payload
            payload = [{"card": name, "quantity": 1} for name in card_list]
            
            # Construct API URL
            api_url = f"https://api.binderpos.com/external/shopify/decklist?storeUrl={api}&type=mtg"
            

            # Make the request
            json_payload = json.dumps(payload)  # Convert list to JSON string
            async with session.post(api_url, data=json_payload, headers=relevant_headers) as post_response:
                if post_response.status == 200:
                    response_text = await post_response.text()
                    logger.info(f"POST succeeded. Response length: {len(response_text)}")
                else:
                    logger.error(f"POST failed with status {post_response.status}")
                    error_detail = await post_response.text()
                    logger.error(f"Error details: {error_detail[:500]}")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")

async def main():
    """
    Test multiple sites from the provided list.
    """
    tasks = [test_site(url) for url in list_of_urls]
    await asyncio.gather(*tasks)

    tasks = [test_shopify_site(url, api) for url, api in zip(list_of_shopify_urls, list_api_urls)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
