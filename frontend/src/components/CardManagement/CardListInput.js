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
  const [quality, setQuality] = useState('NM');  // Add quality state

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

  const fetchCardVersions = async (cardName) => { //to review
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
      setCardList([...cardList, { 
        name: cardName,     // Changed from 'Name'
        quantity,           // Changed from 'Quantity'
        set_name: selectedSet,  // Changed from 'Edition' or 'set'
        quality  // Include quality
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