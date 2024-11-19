import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Image, List, Space, Divider, Tag, Typography } from 'antd';
import { LinkOutlined } from '@ant-design/icons';

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
const ScryfallCard = ({ data, onPrintingSelect }) => {
  const [selectedPrinting, setSelectedPrinting] = useState(null); // Track selected printing
  const [hoveredPrinting, setHoveredPrinting] = useState(null); // Track hovered printing
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 });

  // Initialize the selected printing when data changes
  useEffect(() => {
    if (data && data.all_printings) {
      setSelectedPrinting(data.all_printings[0]); // Default to the first printing
    }
  }, [data]);

  if (!data) return <div>No card data available</div>;

  const allPrintings = data.all_printings || [];
  
  const handleMouseEnter = (item, e) => {
    setHoveredPrinting(item);
    setHoverPosition({ x: e.clientX + 20, y: e.clientY + 20 }); // Slight offset to avoid overlapping with the cursor
  };

  const handleMouseLeave = () => {
    setHoveredPrinting(null);
  };

  const handleMouseMove = (e) => {
    if (hoveredPrinting) {
      setHoverPosition({ x: e.clientX + 20, y: e.clientY + 20 });
    }
  };

  const handlePrintingSelect = (printing) => {
    setSelectedPrinting(printing);
    if (onPrintingSelect) {
      onPrintingSelect(printing); // Call parent handler if provided
    }
  };

  return (
    <Card className="scryfall-card">
      <Row gutter={16}>
        <Col span={8}>
          {/* Display the card image, either hovered printing or the default image */}
          {hoveredPrinting?.image_uris?.normal ? (
            <Image src={hoveredPrinting.image_uris.normal} alt={hoveredPrinting.name} />
          ) : selectedPrinting?.image_uris?.normal ? (
            <Image src={selectedPrinting.image_uris.normal} alt={selectedPrinting.name} />
          ) : data.image_uris?.normal ? (
            <Image src={data.image_uris.normal} alt={data.name} />
          ) : (
            <div>No image available</div>
          )}
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
          <Divider />
          <Title level={5}>All Printings</Title>
          <List
            dataSource={allPrintings}
            renderItem={(item) => (
              <List.Item
                onMouseEnter={(e) => handleMouseEnter(item, e)}
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
                onClick={() => {
                  if (typeof onPrintingSelect === 'function') {
                    console.log('onPrintingSelect called with:', item); // Log only when the function exists and is called
                    onPrintingSelect(item); // Call only if defined
                  } else if (!onPrintingSelect && process.env.NODE_ENV === 'development') {
                    console.warn('onPrintingSelect is not defined'); // Log warning only in development mode
                  }
                }}
              >
                <SetSymbol setCode={item.set} rarity={item.rarity} />
                {item.set_code} {formatSetCode(item.set)} - ${item.prices?.usd || 'N/A'}
              </List.Item>
            )}
          />
          {/* Hover Image Preview */}
          {hoveredPrinting && hoveredPrinting.image_uris && (
            <div
              style={{
                position: 'fixed',
                top: hoverPosition.y,
                left: hoverPosition.x,
                zIndex: 1000,
                backgroundColor: 'white',
                border: '1px solid #ccc',
                padding: '5px',
              }}
            >
              <Image
                src={hoveredPrinting.image_uris.normal}
                alt={hoveredPrinting.name}
                width={150}
              />
            </div>
          )}
          <Divider />
          <Space direction="vertical">
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
          <Text strong>{data.set_name ? `${data.set_name} (${data.set?.toUpperCase()})` : 'N/A'}</Text>
          <Divider />
          <Text>{data.type_line || 'N/A'}</Text>
          {data.oracle_text && formatOracleText(data.oracle_text)}
          {data.flavor_text && <Text italic>{data.flavor_text}</Text>}
          <Text>{data.power && data.toughness ? `${data.power}/${data.toughness}` : ''}</Text>
          <Divider />
          <Row gutter={[8, 8]}>
            {data.legalities && Object.entries(data.legalities).map(([format, legality]) => (
              <Col key={format}>
                <LegalityTag format={format} legality={legality} />
              </Col>
            ))}
          </Row>
        </Col>
      </Row>
    </Card>
  );
};

export default ScryfallCard;
