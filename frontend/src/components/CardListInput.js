import React, { useState } from 'react';
import { Input, Button, List } from 'antd';

const CardListInput = ({ onSubmit }) => {
  const [cardName, setCardName] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [cardList, setCardList] = useState([]);

  const handleAddCard = () => {
    if (cardName) {
      setCardList([...cardList, { name: cardName, quantity }]);
      setCardName('');
      setQuantity(1);
    }
  };

  const handleSubmit = () => {
    onSubmit(cardList);
    setCardList([]);
  };

  return (
    <div>
      <Input 
        value={cardName} 
        onChange={(e) => setCardName(e.target.value)} 
        placeholder="Card Name" 
      />
      <Input 
        type="number" 
        value={quantity} 
        onChange={(e) => setQuantity(parseInt(e.target.value))} 
        min={1} 
      />
      <Button onClick={handleAddCard}>Add Card</Button>
      <List
        dataSource={cardList}
        renderItem={item => (
          <List.Item>
            {item.name} x{item.quantity}
          </List.Item>
        )}
      />
      <Button onClick={handleSubmit}>Submit Card List</Button>
    </div>
  );
};

export default CardListInput;