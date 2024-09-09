import React, { useState } from 'react';
import { Card, Input, Button } from 'antd';

const CardForm = () => {
  const [cardName, setCardName] = useState('');
  const [cardData, setCardData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/fetch_card?name=${cardName}`);
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
        <h2>{cardData.name}</h2>
        <h3>Sets:</h3>
        <ul>
          {cardData.sets.map((set, index) => (
            <li key={index}>{set.name} ({set.code})</li>
          ))}
        </ul>
        <h3>Languages:</h3>
        <ul>
          {cardData.languages.map((lang, index) => (
            <li key={index}>{lang}</li>
          ))}
        </ul>
        <h3>Versions:</h3>
        <ul>
          {cardData.versions.map((version, index) => (
            <li key={index}>{version}</li>
          ))}
        </ul>
      </div>
      )}
    </div>
  );
};

export default CardForm;