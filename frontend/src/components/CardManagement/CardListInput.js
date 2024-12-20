import React, { useState } from 'react';
import { Input, Button, List, Select, Space } from 'antd';

const { Option } = Select;

const CardListInput = ({ onSubmit }) => {
  const [cardName, setCardName] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [cardList, setCardList] = useState([]);
  const [sets, setSets] = useState([]);
  const [selectedSet, setSelectedSet] = useState('');
  const [cardVersions, setCardVersions] = useState(null);
  const [quality, setQuality] = useState('NM');  // Add quality state

  const handleCardSelect = (value) => {
    setCardName(value);
    setSelectedSet('');  // Reset selected set when a new card is chosen
    fetchCardVersions(value);
  };

  const handleAddCard = () => {
    if (cardName && selectedSet && quantity > 0) {
      setCardList([...cardList, { 
        name: cardName,
        quantity,
        set_name: selectedSet,
        quality
      }]);
      setCardName('');
      setQuantity(1);
      setSelectedSet('');
      setQuality('NM');  // Reset quality
      setCardVersions(null);
    }
  };

  const handleSubmit = () => {
    onSubmit(cardList);
    setCardList([]);
  };

  const handleReset = () => {
    setCardList([]);
  };

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
        <Input
          value={cardName}
          onChange={(e) => setCardName(e.target.value)}
          placeholder="Card Name"
          style={{ width: '100%' }}
        />
        {cardVersions && (
          <>
            <Select
              style={{ width: '100%' }}
              placeholder="Select a set"
              value={selectedSet}
              onChange={setSelectedSet}
            >
              {sets.map(set => (
                <Option key={set.code} value={set.code}>{set.name}</Option>
              ))}
            </Select>
            <Input 
              type="number" 
              value={quantity} 
              onChange={(e) => setQuantity(parseInt(e.target.value))} 
              min={1} 
              placeholder="Quantity"
            />
            <Select
              style={{ width: '100%' }}
              placeholder="Select Quality"
              value={quality}
              onChange={setQuality}
            >
              <Option value="NM">Near Mint (NM)</Option>
              <Option value="LP">Lightly Played (LP)</Option>
              <Option value="MP">Moderately Played (MP)</Option>
              <Option value="HP">Heavily Played (HP)</Option>
              <Option value="DMG">Damaged (DMG)</Option>
            </Select>
          </>
        )}
        <Button onClick={handleAddCard} disabled={!cardName || !selectedSet || quantity < 1}>Add Card</Button>
        <List
          dataSource={cardList}
          renderItem={item => (
            <List.Item>
              {item.name} x{item.quantity} ({item.set_name}) - {item.quality}
            </List.Item>
          )}
        />
        <Space>
          <Button onClick={handleSubmit}>Submit Card List</Button>
          <Button onClick={handleReset}>Reset List</Button>
        </Space>
      </Space>
    </div>
  );
};

export default CardListInput;