import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Image, List, Space, Divider, Tag, Typography, message } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import api from '../../utils/api';  // Add this import

const { Title, Text, Paragraph } = Typography;

//Formats a card name to lowercase with hyphens, removing apostrophes. (Utility function)
const formatCardName = (name) => {
  if (!name) return '';
  const part = name.split(' // ')[0]; // Take the first part if split by ' // '
  const noApostrophes = part.replace(/'/g, ''); // Remove apostrophes
  const formatted = noApostrophes.replace(/\s+/g, '-').toLowerCase(); // Replace spaces with hyphens and convert to lowercase
  return formatted;
};

//Formats the set code to lowercase, handling special cases for prefixes like 'p' or 't'. (Utility function)
const formatSetCode = (setCode) => {
  if (!setCode) {
    console.error('Error: setCode is undefined or null');
    return '';
  }

  let formattedSetCode = setCode;
  if (formattedSetCode.length > 3 && (formattedSetCode.startsWith('p') || formattedSetCode.startsWith('t'))) {
    formattedSetCode = formattedSetCode.slice(1);
  }
  return formattedSetCode.toLowerCase();
};

//Formats oracle text into paragraphs, with symbols converted to icons. (Utility function)
const formatOracleText = (text) => {
  if (!text) return null; // Return null or an appropriate fallback if text is undefined or empty
  return text.split('\n').map((paragraph, index) => (
    <Paragraph key={index}>
      {paragraph.split(/(\{[^}]+\})/).map((part, i) => (
        part.startsWith('{') ? <ManaSymbol key={i} symbol={part} /> : part
      ))}
    </Paragraph>
  ));
};

//Renders an image of the mana symbol based on the input. (Utility function)
const ManaSymbol = ({ symbol }) => {
  const cleanSymbol = symbol.replace(/[{/}]/g, '');
  const symbolUrl = `https://svgs.scryfall.io/card-symbols/${cleanSymbol}.svg`;
  return (
    <img
      src={symbolUrl}
      alt={cleanSymbol}
      className="mana-symbol"
      style={{ width: '16px', height: '16px', margin: '0 1px', verticalAlign: 'text-bottom' }}
    />
  );
};

//Renders the symbol of a card set with coloring based on rarity. (Utility function)
const SetSymbol = ({ setCode, rarity }) => {
  const formattedSetCode = formatSetCode(setCode);
  const symbolUrl = `https://svgs.scryfall.io/sets/${formattedSetCode}.svg`;
  const rarityColor = {
    common: '#000000', // Black
    uncommon: '#C0C0C0', // Silver
    rare: '#FFD700', // Gold
    special: '#FFD700', // Gold    
    mythic: '#D37E2A', // Orange
    bonus: '#FFD700' // Gold
  };

  return (
    <img
      src={symbolUrl}
      alt={formattedSetCode} 
      className="set-symbol"
      style={{
        width: '16px',
        height: '16px',
        marginRight: '4px',
        verticalAlign: 'text-bottom',
        filter: `brightness(0) saturate(100%) ${rarityColor[rarity]}`,
        fill: rarityColor[rarity]
      }}
    />
  );
};

//Displays the legality of the card in different formats. (Utility function)
const LegalityTag = ({ format, legality }) => {
  const color = {
    legal: 'green',
    not_legal: 'lightgray',
    banned: 'red',
    restricted: 'blue'
  };
  return (
    <Tag color={color[legality]}>
      {format}
    </Tag>
  );
};

//Displays detailed information of a card from Scryfall API. (Result of user clicking on a card)
const ScryfallCard = ({ data, onPrintingSelect, onSetClick, isEditable }) => {
  console.group('ScryfallCard Component');
  console.log('Component mounted with props:', { 
    hasData: Boolean(data), 
    dataKeys: data ? Object.keys(data) : [],
    name: data?.name,
    printingsCount: data?.all_printings?.length 
  });

  if (!data || !data.name) {
    console.error('Invalid card data received:', data);
    console.groupEnd();
    return <div>Error: Invalid card data received</div>;
  }

  const [availablePrints, setAvailablePrints] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPrinting, setSelectedPrinting] = useState(null);
  const [hoveredPrinting, setHoveredPrinting] = useState(null);

  // Add component state logging
  useEffect(() => {
    console.log('Component State:', {
      availablePrintsCount: availablePrints.length,
      isLoading,
      selectedPrinting: selectedPrinting?.name
    });
  }, [availablePrints, isLoading, selectedPrinting]);

  // Fetch all printings when component mounts or data changes
  useEffect(() => {
    const fetchPrints = async () => {
      console.group('Prints Fetching');
      if (!data?.name) {
        console.warn('No card name available');
        console.groupEnd();
        return;
      }
      
      try {
        // All printings should already be in the data from backend
        if (data.all_printings && Array.isArray(data.all_printings)) {
          console.log('3. Using provided printings:', data.all_printings);
          const prints = data.all_printings.filter(print => !print.digital);
          console.log('4. Filtered prints:', prints);
          setAvailablePrints(prints);
          setSelectedPrinting(prints.find(p => p.id === data.id) || prints[0]);
        } else {
          console.warn('5. No printings found in data, falling back to API');
          // Fallback to fetching from backend
          const response = await api.get('/fetch_card', {
            params: {
              name: data.name,
              include_prints: true
            }
          });
          if (response.data.scryfall?.all_printings) {
            const prints = response.data.scryfall.all_printings;
            setAvailablePrints(prints);
            setSelectedPrinting(prints.find(p => p.id === data.id) || prints[0]);
          }
        }
      } catch (error) {
        console.error('6. Error processing prints:', error);
        message.error('Failed to load card printings');
      }
      console.groupEnd();
    };

    fetchPrints();
    return () => {
      console.log('7. ScryfallCard unmounting');
    };
  }, [data]);

  // Log when prints or selection changes
  useEffect(() => {
    console.log('8. Available prints updated:', availablePrints);
    console.log('9. Selected printing:', selectedPrinting);
  }, [availablePrints, selectedPrinting]);

  const handleSetChange = async (print) => {
    setIsLoading(true);
    try {
      setSelectedPrinting(print);
      if (onSetClick) onSetClick(print.set);
      if (onPrintingSelect) onPrintingSelect(print);
    } catch (error) {
      message.error('Failed to update card printing');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle hover effect for card image
  const handleHover = (e) => {
    e.target.style.transform = 'scale(1.1)';
    e.target.style.transition = 'transform 0.3s ease';
  };

  const handleMouseOut = (e) => {
    e.target.style.transform = 'scale(1)';
  };

  // Add new styles
  const printingItemStyle = {
    display: 'inline-block',
    margin: '0 8px 8px 0',
    padding: '4px 8px',
    border: '1px solid #d9d9d9',
    borderRadius: '4px',
    cursor: isEditable ? 'pointer' : 'default',
    transition: 'all 0.3s',
    opacity: isEditable ? 1 : 0.7,
  };

  const selectedPrintingStyle = {
    ...printingItemStyle,
    backgroundColor: '#f0f0f0',
    borderColor: '#1890ff'
  };

  const handlePrintClick = (print) => {
    setSelectedPrinting(print); // Always update the selected printing
    if (isEditable) { // Only trigger save actions if in edit mode
      handleSetChange(print);
    }
  };

  if (!data) return <div>No card data available</div>;

  console.log('Rendering card display');
  return (
    <Card className="scryfall-card" style={{ background: "#f7f7f7", borderRadius: '8px' }}>
      {console.log('Card render started')}
      <Row gutter={16}>
        <Col span={8}>
          {isLoading ? (
            <div>Loading...</div>
          ) : (
            <>
              <Image 
                src={(hoveredPrinting || selectedPrinting)?.image_uris?.normal || data.image_uris?.normal} 
                alt={data.name}
                onMouseEnter={handleHover}
                onMouseLeave={handleMouseOut}
                style={{ transition: "transform 0.3s", borderRadius: "8px" }}
              />
              <Divider />
              <Space direction="vertical" size="small">
                <Text><strong>Mana Value:</strong> {data.cmc || 'N/A'}</Text>
                <Text><strong>Types:</strong> {data.type_line || 'N/A'}</Text>
                <Text><strong>Rarity:</strong> {data.rarity || 'N/A'}</Text>
                <Text>
                  <strong>Expansion:</strong>
                  {data.set ? (
                    <>
                      <SetSymbol setCode={data.set} rarity={data.rarity} /> {data.set_name || 'N/A'}
                    </>
                  ) : 'N/A'}
                </Text>
                <Text><strong>Card Number:</strong> {data.collector_number || 'N/A'}</Text>
                <Text><strong>Artist:</strong> {data.artist || 'N/A'}</Text>
              </Space>
            </>
          )}
          <Divider orientation="left">Available Printings</Divider>
          <div style={{ marginBottom: '16px' }}>
            {availablePrints.map(print => (
              <div
                key={`${print.set}-${print.collector_number}`}
                style={selectedPrinting?.id === print.id ? selectedPrintingStyle : printingItemStyle}
                onClick={() => handlePrintClick(print)}
                onMouseEnter={() => setHoveredPrinting(print)} // Allow hover in both modes
                onMouseLeave={() => setHoveredPrinting(null)} // Allow hover in both modes
              >
                <Space>
                  <SetSymbol setCode={print.set} rarity={print.rarity} />
                  <span>{print.set.toUpperCase()}</span>
                  {print.prices?.usd && <span>${print.prices.usd}</span>}
                </Space>
              </div>
            ))}
          </div>
          <Divider />
          <Space direction="vertical">
            {data.scryfall_uri && (
              <a href={data.scryfall_uri} target="_blank" rel="noopener noreferrer">
                <LinkOutlined /> View on Scryfall
              </a>
            )}
            {data.multiverse_ids?.[0] && (
              <a href={`https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=${data.multiverse_ids[0]}`} target="_blank" rel="noopener noreferrer">
                <LinkOutlined /> View on Gatherer
              </a>
            )}
            <a href={`https://edhrec.com/cards/${formatCardName(data.name)}`} target="_blank" rel="noopener noreferrer">
              <LinkOutlined /> Card analysis on EDHREC
            </a>
          </Space>
        </Col>
        <Col span={16}>
          <Title level={3}>
            {data.name}
            <span className="mana-cost">
              {data.mana_cost && data.mana_cost.split('').map((char, index) => 
                char === '{' || char === '}' ? null : <ManaSymbol key={index} symbol={`{${char}}`} />
              )}
            </span>
          </Title>
          <Text strong>
            {(selectedPrinting || data).set_name} ({(selectedPrinting || data).set?.toUpperCase() || 'N/A'})
          </Text>
          <Divider />
          <Text>{data.type_line || 'N/A'}</Text>
          {data.oracle_text && formatOracleText(data.oracle_text)}
          {data.flavor_text && <Text italic>{data.flavor_text}</Text>}
          <Text>{data.power && data.toughness ? `${data.power}/${data.toughness}` : ''}</Text>
          <Divider />
          <Title level={4}>Format Legality</Title>
          <Row gutter={[8, 8]}>
            {Object.entries(data.legalities || {}).map(([format, legality]) => (
              <Col key={format}>
                <LegalityTag format={format} legality={legality} />
              </Col>
            ))}
          </Row>
        </Col>
      </Row>
      {console.log('Card render completed')}
    </Card>
  );
};

export default React.memo(ScryfallCard); // Add memoization to prevent unnecessary rerenders
