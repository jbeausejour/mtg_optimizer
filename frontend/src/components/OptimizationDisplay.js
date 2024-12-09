import React, { useState } from 'react';
import { Row, Col, Card, Table, Collapse, Typography, Tag, Tooltip } from 'antd';
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import CardDetail from './CardDetail';
import { getStandardTableColumns, cardNameStyle } from '../utils/tableConfig';

const { Title, Text } = Typography;
const { Panel } = Collapse;

export const OptimizationSummary = ({ result, onCardClick }) => {
  // Filter out duplicate solutions based on their properties
  const solutions = Array.isArray(result?.solutions) 
    ? result.solutions.filter((solution, index, self) =>
        index === self.findIndex((s) => (
          s.total_price === solution.total_price &&
          s.number_store === solution.number_store &&
          s.nbr_card_in_solution === solution.nbr_card_in_solution
        ))
      )
    : [];
  const errors = result?.errors || {};

  return (
    <div className="w-full space-y-4">
      <Title level={4}>Optimization Results</Title>
      
      {Object.values(errors).some(arr => arr?.length > 0) && (
        <Card title={<span><WarningOutlined /> Issues Found</span>} type="inner">
          {errors.unreachable_stores?.length > 0 && (
            <div className="mb-2">
              <Text type="danger">Unreachable Stores: </Text>
              <Text>{errors.unreachable_stores.join(', ')}</Text>
            </div>
          )}
          {errors.unknown_languages?.length > 0 && (
            <div className="mb-2">
              <Text type="warning">Unknown Languages: </Text>
              <Text>{errors.unknown_languages.join(', ')}</Text>
            </div>
          )}
          {errors.unknown_qualities?.length > 0 && (
            <div>
              <Text type="warning">Unknown Qualities: </Text>
              <Text>{errors.unknown_qualities.join(', ')}</Text>
            </div>
          )}
        </Card>
      )}

      {solutions.length > 0 ? (
        <Collapse>
          {solutions.map((solution, index) => {
            const completeness = solution.nbr_card_in_solution === (solution.total_qty || solution.nbr_card_in_solution);
            const percentage = ((solution.nbr_card_in_solution / (solution.total_qty || solution.nbr_card_in_solution)) * 100).toFixed(2);
            
            return (
              <Panel 
                key={index}
                header={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Text strong>{`${solution.number_store} Stores`}</Text>
                      <Tag color={completeness ? 'green' : 'orange'}>
                        {completeness ? 'COMPLETE' : `${percentage}%`}
                      </Tag>
                      <Text type="secondary">${solution.total_price.toFixed(2)}</Text>
                    </div>
                    {solution.missing_cards?.length > 0 && (
                      <Text type="danger">
                        Missing: {solution.missing_cards.length} cards
                      </Text>
                    )}
                  </div>
                }
              >
                <StoreDistribution solution={solution} />
                {solution.missing_cards?.length > 0 && (
                  <Card title="Missing Cards" size="small" className="mb-4">
                    <Text type="danger">
                      {solution.missing_cards.map((card, index) => (
                        <React.Fragment key={index}>
                          <span style={cardNameStyle} onClick={() => onCardClick({ name: card })}>
                            {card}
                          </span>
                          {index < solution.missing_cards.length - 1 ? ', ' : ''}
                        </React.Fragment>
                      ))}
                    </Text>
                  </Card>
                )}
                <OptimizationDetails 
                  solution={solution} 
                  onCardClick={onCardClick}
                />
              </Panel>
            );
          })}
        </Collapse>
      ) : (
        <Text type="warning">No optimization solutions available</Text>
      )}
    </div>
  );
};

const StoreDistribution = ({ solution }) => {
  const storeData = solution.list_stores.split(', ')
    .map(store => {
      const [name, count] = store.split(': ');
      return { name, count: parseInt(count) };
    })
    .filter(store => store.count > 0);

  return (
    <Card title="Store Distribution" size="small" className="mb-4">
      <Row gutter={[16, 16]}>
        {storeData.map(({ name, count }, index) => (
          <Col span={8} key={index}>
            <Card size="small">
              <Text strong>{name}</Text>
              <div>{count} cards</div>
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
  );
};

export const OptimizationDetails = ({ solution, onCardClick }) => {
  const [cardDetailVisible, setCardDetailVisible] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);

  const handleCardClick = (card) => {
    setSelectedCard(card);
    setCardDetailVisible(true);
  };

  // Transform the cards object into an array
  const dataSource = Object.values(solution.cards || {})
    .filter(card => card && card.price !== 10000)
    .map(card => ({
      key: `${card.name}-${card.site_name}`,
      name: card.name,
      store: card.site_name,
      price: card.price,
      set: card.set_name,
      quality: card.quality,
      quantity: card.quantity,
      version: card.version,
      foil: card.foil,
      language: card.language
    }));

  const columns = [
    ...getStandardTableColumns(onCardClick),
    {
      title: 'Store',
      dataIndex: 'store',
      key: 'store',
      sorter: (a, b) => a.store?.localeCompare(b.store),
    },
    {
      title: 'Details',
      key: 'details',
      render: (_, record) => (
        <div>
          {record.foil && <Tag color="blue">Foil</Tag>}
          {record.language !== 'English' && <Tag color="orange">{record.language}</Tag>}
          {record.version !== 'Standard' && <Tag color="purple">{record.version}</Tag>}
        </div>
      ),
    }
  ];

  return (
    <>
      <Table 
        dataSource={dataSource} 
        columns={columns} 
        pagination={false}
        scroll={{ y: 400 }}
        size="small"
      />
      {selectedCard && (
        <CardDetail
          cardName={selectedCard.name}
          setName={selectedCard.set_name}
          language={selectedCard.language}
          version={selectedCard.version}
          foil={selectedCard.foil}
          isModalVisible={cardDetailVisible}
          onClose={() => setCardDetailVisible(false)}
        />
      )}
    </>
  );
};

export default OptimizationSummary;