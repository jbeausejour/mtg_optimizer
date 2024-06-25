import React, { useState } from 'react';
import { Card, Input, Button } from 'antd';

const CardForm = () => {
  const [cardName, setCardName] = useState('');
  const [cardData, setCardData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.get(`/fetch_card?name=${cardName}`);
      setCardData(response.data);
    } catch (error) {
      console.error('Error fetching card data:', error);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <Input 
          type="text" 
          value={cardName} 
          onChange={(e) => setCardName(e.target.value)} 
          placeholder="Enter card name" 
        />
        <Button type="primary" htmlType="submit">Search</Button>
      </form>
      {cardData && (
        <div>
          <Card title="Scryfall Data">
            <pre>{JSON.stringify(cardData.scryfall, null, 2)}</pre>
          </Card>
          <Card title="MTGStocks Data">
            <pre>{JSON.stringify(cardData.mtgstocks, null, 2)}</pre>
          </Card>
          {cardData.previous_scan && (
            <Card title="Previous Scan Data">
              <pre>{JSON.stringify(cardData.previous_scan, null, 2)}</pre>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};

export default CardForm;