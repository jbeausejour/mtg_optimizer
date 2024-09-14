import React, { useState, useEffect } from 'react';
import { Table, Button, DatePicker, message } from 'antd';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import api from '../utils/api';

const { RangePicker } = DatePicker;

const PriceTracker = () => {
  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [dateRange, setDateRange] = useState([]);

  useEffect(() => {
    fetchCards();
  }, []);

  const fetchCards = async () => {
    try {
      const response = await api.get('/cards');
      setCards(response.data);
    } catch (error) {
      message.error('Failed to fetch cards');
    }
  };

  const fetchPriceHistory = async (cardId, startDate, endDate) => {
    try {
      const response = await api.get('/price-history', {
        params: { cardId, startDate, endDate }
      });
      setPriceHistory(response.data);
    } catch (error) {
      message.error('Failed to fetch price history');
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Current Price',
      dataIndex: 'currentPrice',
      key: 'currentPrice',
      render: (price) => `$${price.toFixed(2)}`,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (text, record) => (
        <Button onClick={() => handleCardSelect(record)}>Track Prices</Button>
      ),
    },
  ];

  const handleCardSelect = (card) => {
    setSelectedCard(card);
    if (dateRange.length === 2) {
      fetchPriceHistory(card.id, dateRange[0], dateRange[1]);
    }
  };

  const handleDateRangeChange = (dates) => {
    setDateRange(dates);
    if (selectedCard && dates.length === 2) {
      fetchPriceHistory(selectedCard.id, dates[0], dates[1]);
    }
  };

  return (
    <div className="price-tracker">
      <h1>Price Tracker</h1>
      <Table dataSource={cards} columns={columns} rowKey="id" />
      {selectedCard && (
        <div>
          <h2>Price History for {selectedCard.name}</h2>
          <RangePicker onChange={handleDateRangeChange} />
          <LineChart width={600} height={300} data={priceHistory}>
            <XAxis dataKey="date" />
            <YAxis />
            <CartesianGrid strokeDasharray="3 3" />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="price" stroke="#8884d8" />
          </LineChart>
        </div>
      )}
    </div>
  );
};

export default PriceTracker;