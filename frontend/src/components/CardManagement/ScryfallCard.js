import React from 'react';
import { Card, Row, Col, Image, Typography, Divider, Space, Tag } from 'antd';
import { LinkOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const formatCardName = (name) => {
  if (!name) return '';
  const part = name.split(' // ')[0];
  const noApostrophes = part.replace(/'/g, '');
  const formatted = noApostrophes.replace(/\s+/g, '-').toLowerCase();
  return formatted;
};

const formatSetCode = (setCode) => {
  let formattedSetCode = setCode;
  if (formattedSetCode.length > 3 && (formattedSetCode.startsWith('p') || formattedSetCode.startsWith('t'))) {
    formattedSetCode = formattedSetCode.slice(1);
  }
  return formattedSetCode.toLowerCase();
};

const ManaSymbol = ({ symbol }) => {
  const cleanSymbol = symbol.replace(/[{/}]/g, '');
  const symbolUrl = `https://svgs.scryfall.io/card-symbols/${cleanSymbol}.svg`;
  return (
    <img 
      src={symbolUrl} 
      alt={cleanSymbol} 
      className="mana-symbol" 
      style={{width: '16px', height: '16px', margin: '0 1px', verticalAlign: 'text-bottom'}} 
    />
  );
};

const SetSymbol = ({ setCode, rarity }) => {
  const formattedSetCode = formatSetCode(setCode);
  const symbolUrl = `https://svgs.scryfall.io/sets/${formattedSetCode}.svg`;
  const rarityColor = {
    common: 'black',
    uncommon: 'silver',
    rare: 'gold',
    mythic: '#D37E2A'
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
        filter: `brightness(0) saturate(100%) ${rarityColor[rarity]}`
      }} 
    />
  );
};

const LegalityTag = ({ format, legality }) => {
  const color = {
    legal: 'green',
    not_legal: 'default',
    banned: 'red',
    restricted: 'blue'
  };
  return (
    <Tag color={color[legality]}>
      {format}
    </Tag>
  );
};

const ScryfallCard = ({ data }) => {
  if (!data) return <div>No card data available</div>;

  return (
    <Card className="scryfall-card">
      <Row gutter={16}>
        <Col span={8}>
          {data.image_uris && data.image_uris.normal ? (
            <Image src={data.image_uris.normal} alt={data.name} />
          ) : (
            <div>No image available</div>
          )}
          <Divider />
          <Space direction="vertical" size="small">
            <Text><strong>Mana Value:</strong> {data.cmc}</Text>
            <Text><strong>Types:</strong> {data.type_line}</Text>
            <Text><strong>Rarity:</strong> {data.rarity}</Text>
            <Text>
              <strong>Expansion:</strong> <SetSymbol setCode={data.set} rarity={data.rarity} /> {data.set_name}
            </Text>
            <Text><strong>Card Number:</strong> {data.collector_number}</Text>
            <Text><strong>Artist:</strong> {data.artist}</Text>
          </Space>
          <Divider />
          <Space direction="vertical">
            <a href={`https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=${data.multiverse_ids[0]}`} target="_blank" rel="noopener noreferrer">
              <LinkOutlined /> View on Gatherer
            </a>
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
          <Text strong>{data.set_name} ({data.set.toUpperCase()})</Text>
          <Divider />
          <Text>{data.type_line}</Text>
          <Paragraph>{data.oracle_text}</Paragraph>
          {data.flavor_text && <Text italic>{data.flavor_text}</Text>}
          <Text>{data.power && data.toughness ? `${data.power}/${data.toughness}` : ''}</Text>
          <Divider />
          <Row gutter={[8, 8]}>
            {Object.entries(data.legalities).map(([format, legality]) => (
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