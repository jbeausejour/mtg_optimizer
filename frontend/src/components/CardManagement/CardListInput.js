import React, { useState, useEffect } from 'react';
import { Input, Button, List, Select, Space } from 'antd';
import axios from 'axios';

const { Option } = Select;

const CardListInput = ({ onSubmit }) => {
  const [cardName, setCardName] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [cardList, setCardList] = useState([]);
  const [sets, setSets] = useState([]);
  const [selectedSet, setSelectedSet] = useState('');

  useEffect(() => {
    // Fetch the list of sets when the component mounts
    fetchSets();
  }, []);

  const fetchSets = async () => {
    try {
      const response = await axios.get('/api/v1/sets');
      setSets(response.data);
    } catch (error) {
      console.error('Error fetching sets:', error);
    }
  };

  const handleAddCard = () => {
    if (cardName && selectedSet) {
      setCardList([...cardList, { name: cardName, quantity, set: selectedSet }]);
      setCardName('');
      setQuantity(1);
      setSelectedSet('');
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
        />
        <Input 
          type="number" 
          value={quantity} 
          onChange={(e) => setQuantity(parseInt(e.target.value))} 
          min={1} 
        />
        <Select
          style={{ width: '100%' }}
          placeholder="Select a set"
          value={selectedSet}
          onChange={setSelectedSet}
        >
          {sets.map(set => (
            <Option key={set.set_code} value={set.set_code}>{set.set_name}</Option>
          ))}
        </Select>
        <Button onClick={handleAddCard}>Add Card</Button>
        <List
          dataSource={cardList}
          renderItem={item => (
            <List.Item>
              {item.name} x{item.quantity} ({item.set})
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