import React, { useState, useEffect } from 'react';
import { Card, Modal, Descriptions, Tag, Spin, Typography } from 'antd';  // Added Typography import
import api from '../utils/api';

const { Text } = Typography;  // Add destructuring for Text component

const CardDetail = ({ cardName, setName, language, version, foil, isModalVisible, onClose }) => {
  const [cardData, setCardData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchCardData = async () => {
      if (!cardName || !isModalVisible) return;
      
      setLoading(true);
      try {
        const response = await api.get('/fetch_card', {
          params: { name: cardName, set: setName, language, version }
        });
        setCardData(response.data);
      } catch (error) {
        console.error('Error fetching card details:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCardData();
  }, [cardName, setName, language, version, isModalVisible]);

  const renderSpecifications = () => (
    <Descriptions column={2}>
      {setName && <Descriptions.Item label="Set">{setName}</Descriptions.Item>}
      {language && <Descriptions.Item label="Language">{language}</Descriptions.Item>}
      {version && <Descriptions.Item label="Version">{version}</Descriptions.Item>}
      {foil !== undefined && (
        <Descriptions.Item label="Foil">
          <Tag color={foil ? 'gold' : 'default'}>
            {foil ? 'Yes' : 'No'}
          </Tag>
        </Descriptions.Item>
      )}
    </Descriptions>
  );

  return (
    <Modal
      title={cardName}
      open={isModalVisible}
      onCancel={onClose}
      footer={null}
      width={800}
    >
      {loading ? (
        <Spin />
      ) : (
        <div style={{ display: 'flex', gap: '20px' }}>
          {cardData?.scryfall?.image_uris?.normal && (
            <img
              src={cardData.scryfall.image_uris.normal}
              alt={cardName}
              style={{ width: '300px', height: 'auto' }}
            />
          )}
          <div style={{ flex: 1 }}>
            <h3>Specifications</h3>
            {renderSpecifications()}
            
            {cardData?.scryfall && (
              <>
                <h3>Card Details</h3>
                <Descriptions column={1}>
                  {cardData.scryfall.mana_cost && (
                    <Descriptions.Item label="Mana Cost">{cardData.scryfall.mana_cost}</Descriptions.Item>
                  )}
                  {cardData.scryfall.type_line && (
                    <Descriptions.Item label="Type">{cardData.scryfall.type_line}</Descriptions.Item>
                  )}
                  {cardData.scryfall.oracle_text && (
                    <Descriptions.Item label="Text">{cardData.scryfall.oracle_text}</Descriptions.Item>
                  )}
                  {cardData.scryfall.flavor_text && (
                    <Descriptions.Item label="Flavor">{cardData.scryfall.flavor_text}</Descriptions.Item>
                  )}
                  {(cardData.scryfall.power || cardData.scryfall.toughness) && (
                    <Descriptions.Item label="P/T">{`${cardData.scryfall.power || '-'}/${cardData.scryfall.toughness || '-'}`}</Descriptions.Item>
                  )}
                  {cardData.scryfall.loyalty && (
                    <Descriptions.Item label="Loyalty">{cardData.scryfall.loyalty}</Descriptions.Item>
                  )}
                  {cardData.scryfall.rarity && (
                    <Descriptions.Item label="Rarity">{cardData.scryfall.rarity}</Descriptions.Item>
                  )}
                </Descriptions>

                {cardData.scan_timestamp && (
                  <div style={{ marginTop: '16px' }}>
                    <Text type="secondary">
                      Last scanned: {new Date(cardData.scan_timestamp).toLocaleString()}
                    </Text>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
};

export default CardDetail;