import React, { useState, useEffect } from 'react';
import { Input, Button, List, Select, Space, AutoComplete } from 'antd';
import debounce from 'lodash/debounce';
import api from '../../utils/api';

const { Option } = Select;

const CardListInput = ({ onSubmit }) => {
  const [cardName, setCardName] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [cardList, setCardList] = useState([]);
  const [sets, setSets] = useState([]);
  const [selectedSet, setSelectedSet] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [cardVersions, setCardVersions] = useState(null);

  const fetchSuggestions = async (query) => {
    if (query.length > 2) {
      try {
        const response = await api.get(`/card_suggestions?query=${query}`);
        console.log('Suggestions received:', response.data);
        setSuggestions(response.data.map(name => ({ value: name })));
      } catch (error) {
        console.error('Error fetching suggestions:', error);
        setSuggestions([]);
      }
    } else {
      setSuggestions([]);
    }
  };

  const debouncedFetchSuggestions = debounce(fetchSuggestions, 300);

  const fetchCardVersions = async (cardName) => {
    try {
      const response = await api.get(`/card_versions?name=${encodeURIComponent(cardName)}`);
      console.log('Card versions received:', response.data);
      setCardVersions(response.data);
      setSets(response.data.sets);
    } catch (error) {
      console.error('Error fetching card versions:', error);
      setCardVersions(null);
      setSets([]);
    }
  };


  const handleCardSelect = (value) => {
    setCardName(value);
    setSelectedSet('');  // Reset selected set when a new card is chosen
    fetchCardVersions(value);
  };

  const handleAddCard = () => {
    if (cardName && selectedSet && quantity > 0) {
      setCardList([...cardList, { name: cardName, quantity, set: selectedSet }]);
      setCardName('');
      setQuantity(1);
      setSelectedSet('');
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
        <AutoComplete
          value={cardName}
          options={suggestions}
          onSearch={(text) => {
            setCardName(text);
            debouncedFetchSuggestions(text);
          }}
          onSelect={handleCardSelect}
          placeholder="Card Name"
          style={{ width: '100%' }}
          className="card-name-autocomplete"
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
          </>
        )}
        <Button onClick={handleAddCard} disabled={!cardName || !selectedSet || quantity < 1}>Add Card</Button>
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