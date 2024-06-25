export const fetchMTGStockData = async (cardName) => {
    // Replace with the actual MTG Stocks API endpoint
    const response = await fetch(`https://api.mtgstocks.com/v1/cards?name=${cardName}`);
    if (!response.ok) {
      throw new Error('Failed to fetch MTG Stocks data');
    }
    const data = await response.json();
    return data;
  };
  
  export const fetchScryfallData = async (cardName) => {
    const response = await fetch(`https://api.scryfall.com/cards/named?exact=${cardName}`);
    if (!response.ok) {
      throw new Error('Failed to fetch Scryfall data');
    }
    const data = await response.json();
    return data;
  };
  