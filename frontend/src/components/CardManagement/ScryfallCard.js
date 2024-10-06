import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Image, Typography, Divider, Space, Tag, message } from 'antd';
import { LinkOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const SCRYFALL_API_BASE = "https://api.scryfall.com";

const ScryfallCard = ({ card, onSetClick }) => {
  const [cardData, setCardData] = useState(card);
  const [availablePrints, setAvailablePrints] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const cardName = cardData?.name;
  const initialSetCode = cardData?.set;

  // Fetch all available prints for this card when it loads
  useEffect(() => {
    const fetchAvailablePrints = async () => {
      try {
        const response = await fetch(cardData.prints_search_uri);
        const result = await response.json();
        setAvailablePrints(result.data.filter(print => !print.digital && print.purchase_uris)); // Filter out digital-only versions
      } catch (error) {
        message.error('Failed to load available prints');
      }
    };

    fetchAvailablePrints();
  }, [cardData.prints_search_uri]);

  const handleSetChange = async (setCode) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${SCRYFALL_API_BASE}/cards/named?exact=${cardName}&set=${setCode}`);
      const updatedCardData = await response.json();
      setCardData(updatedCardData);  // Update the card details based on the selected set
      onSetClick(setCode);  // Trigger callback to notify parent of the set selection
    } catch (error) {
      message.error('Failed to fetch card details for the selected set');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle hover effect for card image
  const handleHover = (e) => {
    const cardImage = e.target;
    cardImage.style.transform = 'scale(1.1)';
    cardImage.style.transition = 'transform 0.3s ease';
  };

  const handleMouseOut = (e) => {
    const cardImage = e.target;
    cardImage.style.transform = 'scale(1)';
  };

  if (!cardData) return <div>No card data available</div>;

  return (
    <Card className="scryfall-card" style={{ background: "#f7f7f7", borderRadius: '8px' }}>
      <Row gutter={16}>
        <Col span={8}>
          {isLoading ? (
            <div>Loading...</div>
          ) : (
            <>
              {cardData.image_uris && cardData.image_uris.normal ? (
                <Image 
                  src={cardData.image_uris.normal} 
                  alt={cardData.name} 
                  onMouseEnter={handleHover} 
                  onMouseLeave={handleMouseOut} 
                  style={{ transition: "transform 0.3s", borderRadius: "8px" }} 
                />
              ) : (
                <div>No image available</div>
              )}
              <Divider />
              <Space direction="vertical" size="small">
                <Text><strong>Mana Value:</strong> {cardData.cmc}</Text>
                <Text><strong>Types:</strong> {cardData.type_line}</Text>
                <Text><strong>Rarity:</strong> {cardData.rarity}</Text>
                <Text>
                  <strong>Expansion:</strong> {cardData.set_name}
                </Text>
                <Text><strong>Card Number:</strong> {cardData.collector_number}</Text>
                <Text><strong>Artist:</strong> {cardData.artist}</Text>
              </Space>
              <Divider />
              <Space direction="vertical">
                <a href={`https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=${cardData.multiverse_ids[0]}`} target="_blank" rel="noopener noreferrer">
                  <LinkOutlined /> View on Gatherer
                </a>
                <a href={`https://edhrec.com/cards/${cardData.name.replace(/\s+/g, '-').toLowerCase()}`} target="_blank" rel="noopener noreferrer">
                  <LinkOutlined /> Card analysis on EDHREC
                </a> 
              </Space>
            </>
          )}
        </Col>
        <Col span={16}>
          <Title level={3}>
            {cardData.name}
            <span className="mana-cost">
              {cardData.mana_cost && cardData.mana_cost.split('').map((char, index) => 
                char === '{' || char === '}' ? null : <img key={index} src={`https://svgs.scryfall.io/card-symbols/${char.replace(/[{}]/g, '')}.svg`} alt={char} style={{ width: '16px', height: '16px', margin: '0 1px', verticalAlign: 'text-bottom' }} />
              )}
            </span>
          </Title>
          <Text strong>{cardData.set_name} ({cardData.set.toUpperCase()})</Text>
          <Divider />
          <Text>{cardData.type_line}</Text>
          <Paragraph>{cardData.oracle_text}</Paragraph>
          {cardData.flavor_text && <Text italic>{cardData.flavor_text}</Text>}
          <Text>{cardData.power && cardData.toughness ? `${cardData.power}/${cardData.toughness}` : ''}</Text>
          <Divider />
          
          <Title level={4}>Available Sets and Prices</Title>
          {availablePrints.map(print => (
            <Row key={print.id} style={{ marginBottom: '8px' }}>
              <Col span={16}>
                <a onClick={() => handleSetChange(print.set)} style={{ cursor: 'pointer', color: '#1890ff' }}>
                  {print.set_name} ({print.set.toUpperCase()})
                </a>
              </Col>
              <Col span={8}>
                <Space>
                  {print.prices.usd && <Text strong>USD: ${print.prices.usd}</Text>}
                </Space>
              </Col>
            </Row>
          ))}
          
        </Col>
      </Row>
    </Card>
  );
};

export default ScryfallCard;
