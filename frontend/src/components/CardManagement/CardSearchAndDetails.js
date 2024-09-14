import React, { useState } from 'react';
import { Card, Input, Button, message } from 'antd';
import api from '../../utils/api';  // Make sure this path is correct

const CardForm = () => {
  const [cardName, setCardName] = useState('');
  const [cardData, setCardData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await api.get(`/fetch_card?name=${encodeURIComponent(cardName)}`);
      setCardData(response.data);
    } catch (error) {
      console.error('Error fetching card data:', error);
      message.error('Failed to fetch card data. Please try again.');
    } finally {
      setLoading(false);
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
        <Button type="primary" htmlType="submit" loading={loading}>Search</Button>
      </form>
      {cardData && (
        <Card title={cardData.name}>
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
        </Card>
      )}
    </div>
  );
};

export default CardForm;