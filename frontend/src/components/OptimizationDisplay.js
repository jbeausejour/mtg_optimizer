import React, { useState } from 'react';
import { Row, Col, Card, Collapse, Typography, Tag, Space, Button, message, Alert } from 'antd';
import { WarningOutlined, ShoppingCartOutlined } from '@ant-design/icons';
import { getStandardTableColumns } from '../utils/tableConfig';
import EnhancedTable from './EnhancedTable';
import PurchaseHandler from './PurchaseUrls';
import api from '../utils/api';

const { Title, Text } = Typography;
const { Panel } = Collapse;


export const OptimizationSummary = ({ result, onCardClick }) => {
  const solutions = result?.solutions || [];
  const errors = result?.errors || {};
  
  const sortedSolutions = [...solutions].sort((a, b) => {
    if (a.is_best_solution) return -1;
    if (b.is_best_solution) return 1;
    if (a.missing_cards_count !== b.missing_cards_count) {
      return a.missing_cards_count - b.missing_cards_count;
    }
    if (a.total_price !== b.total_price) {
      return a.total_price - b.total_price;
    }
    return a.number_store - b.number_store;
  });

  const bestSolution = sortedSolutions.find(s => s.is_best_solution);
  const otherSolutions = sortedSolutions.filter(s => !s.is_best_solution);

  const StoreDistribution = ({ solution }) => {
    const [purchaseData, setPurchaseData] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    
    
    const handlePurchase = async () => {
      try {

        const response = await api.post('/purchase_order', { 
          purchase_data: solution.stores,
        });
        
        setPurchaseData(response.data);
        setIsModalOpen(true);
        
      } catch (error) {
        console.error('Error submitting purchase order:', error);
        message.error('Failed to submit purchase order. Please try again.');
      }
    };
  
    const storeData = solution.list_stores.split(', ')
      .map(store => {
        const [name, count] = store.split(': ');
        return { name, count: parseInt(count) };
      })
      .filter(store => store.count > 0);
    
    return (
      <>
        <Card 
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Store Distribution</span>
              <Button 
                type="primary"
                icon={<ShoppingCartOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handlePurchase();
                }}
              >
                Buy It Now
              </Button>
            </div>
          } 
          size="small" 
          style={{ marginBottom: 16 }}
        >
          <Row gutter={[16, 16]}>
            {storeData.map(({ name, count }, index) => (
              <Col span={8} key={index}>
                <Card size="small">
                  <Text strong>{name}</Text>
                  <div>
                    <Text type="secondary">{count} cards</Text>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
        
        {purchaseData && (
          <PurchaseHandler 
            purchaseData={purchaseData}
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
          />
        )}
      </>
    );
  };
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Title level={4} style={{ margin: 0 }}>Optimization Results</Title>
            <Tag className="sites-tag">{`${result.sites_scraped} Sites`}</Tag>
            <Tag className="cards-tag">{`${result.cards_scraped} Cards`}</Tag>
          </Space>
          
          {result.message && (
            <Text type="secondary">{result.message}</Text>
          )}
        </Space>
      </Card>

      {Object.values(errors).some(arr => arr?.length > 0) && (
        <Alert
          message={
            <Space>
              <WarningOutlined />
              <span>Issues Found</span>
            </Space>
          }
          description={
            <Space direction="vertical" style={{ width: '100%' }}>
              {errors.unreachable_stores?.length > 0 && (
                <div>
                  <Text strong className="error-text">Unreachable Stores:</Text>
                  <div style={{ marginTop: 4 }}>
                    <Space wrap>
                      {errors.unreachable_stores.map(store => (
                        <Tag key={store} className="error-tag">{store}</Tag>
                      ))}
                    </Space>
                  </div>
                </div>
              )}
              {errors.unknown_languages?.length > 0 && (
                <div>
                  <Text strong className="warning-text">Unknown Languages:</Text>
                  <div style={{ marginTop: 4 }}>
                    <Space wrap>
                      {errors.unknown_languages.map(lang => (
                        <Tag key={lang} className="warning-tag">{lang}</Tag>
                      ))}
                    </Space>
                  </div>
                </div>
              )}
              {errors.unknown_qualities?.length > 0 && (
                <div>
                  <Text strong className="warning-text">Unknown Qualities:</Text>
                  <div style={{ marginTop: 4 }}>
                    <Space wrap>
                      {errors.unknown_qualities.map(quality => (
                        <Tag key={quality} className="warning-tag">{quality}</Tag>
                      ))}
                    </Space>
                  </div>
                </div>
              )}
            </Space>
          }
          type="warning"
          showIcon
        />
      )}

      {bestSolution && (
        <Collapse defaultActiveKey={['best-solution']}>
          <Panel
            key="best-solution"
            header={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <Space>
                  <Text strong>{`${bestSolution.number_store} Stores`}</Text>
                  <Tag className="success-tag">Best Solution</Tag>
                  <Tag className={bestSolution.nbr_card_in_solution === bestSolution.total_qty ? 'complete-tag' : 'partial-tag'}>
                    {bestSolution.missing_cards_count === 0
                      ? 'Complete'
                      : `${((1 -(bestSolution.missing_cards_count / bestSolution.total_qty)) * 100).toFixed(1)}% Complete`}
                  </Tag>
                  <Tag className="price-tag">${bestSolution.total_price.toFixed(2)}</Tag>
                </Space>
                <Space>
                  {bestSolution.missing_cards_count > 0 && (
                    <Tag className="missing-tag" icon={<WarningOutlined />}>
                      {bestSolution.missing_cards_count} Missing Cards
                    </Tag>
                  )}
                  <Tag>
                    {`${bestSolution.nbr_card_in_solution-bestSolution.missing_cards_count}/${bestSolution.total_qty} Cards Found`}
                  </Tag>
                </Space>
              </div>
            }
          >
            <StoreDistribution solution={bestSolution} />
            {bestSolution.missing_cards?.length > 0 && (
              <Card title="Missing Cards" size="small" style={{ marginBottom: 16 }}>
                <Space wrap>
                  {bestSolution.missing_cards.map(card => (
                    <Tag
                      key={card}
                      className="missing-card-tag cursor-pointer"
                      onClick={() => onCardClick(card)}
                    >
                      {card}
                    </Tag>
                  ))}
                </Space>
              </Card>
            )}
            <SolutionDetails solution={bestSolution} onCardClick={onCardClick} />
          </Panel>
        </Collapse>
      )}

      {otherSolutions.length > 0 ? (
        <Collapse>
          {otherSolutions.map((solution, index) => {
            const completeness = solution.nbr_card_in_solution === solution.total_qty;
            const percentage = ((solution.nbr_card_in_solution / solution.total_qty) * 100).toFixed(1);
            
            return (
              <Panel
                key={index}
                header={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <Space>
                      <Text strong>{`${solution.number_store} Stores`}</Text>
                      <Tag className={completeness ? 'complete-tag' : 'partial-tag'}>
                        {completeness ? 'Complete' : `${percentage}% Complete`}
                      </Tag>
                      <Tag className="price-tag">${solution.total_price.toFixed(2)}</Tag>
                    </Space>
                    <Space>
                      {solution.missing_cards_count > 0 && (
                        <Tag className="missing-tag" icon={<WarningOutlined />}>
                          {solution.missing_cards_count} Missing Cards
                        </Tag>
                      )}
                      <Tag>
                        {`${solution.nbr_card_in_solution}/${bestSolution.nbr_card_in_solution} Cards Found`}
                      </Tag>
                    </Space>
                  </div>
                }
              >
                <StoreDistribution solution={solution} />
                {solution.missing_cards?.length > 0 && (
                  <Card title="Missing Cards" size="small" style={{ marginBottom: 16 }}>
                    <Space wrap>
                      {solution.missing_cards.map(card => (
                        <Tag 
                          key={card} 
                          className="missing-card-tag cursor-pointer"
                          onClick={() => onCardClick(card)}
                        >
                          {card}
                        </Tag>
                      ))}
                    </Space>
                  </Card>
                )}
                <SolutionDetails solution={solution} onCardClick={onCardClick} />
              </Panel>
            );
          })}
        </Collapse>
      ) : (
        <Card>
          <Text type="warning">No optimization solutions available</Text>
        </Card>
      )}
    </Space>
  );
};

const SolutionDetails = ({ solution, onCardClick }) => {
  const dataSource = solution.stores.flatMap(store => 
    store.cards.map(card => ({
      key: `${card.name}-${store.site_name}`,
      site_name: store.site_name,
      site_id: store.site_id,
      ...card
    }))
  );

  const columns = [
    ...getStandardTableColumns(onCardClick),
    {
      title: 'Store',
      dataIndex: 'site_name',
      key: 'site_name',
      sorter: (a, b) => a.site_name.localeCompare(b.site_name),
    },
    {
      title: 'Details',
      key: 'details',
      render: (_, record) => (
        <Space>
          {record.foil && <Tag className="foil-tag">Foil</Tag>}
          {record.language !== 'English' && (
            <Tag className="language-tag">{record.language}</Tag>
          )}
          {record.version !== 'Normal' && (
            <Tag className="version-tag">{record.version}</Tag>
          )}
        </Space>
      ),
    }
  ];

  return (
    <EnhancedTable
      dataSource={dataSource}
      columns={columns}
      exportFilename={`optimization_solution_${solution.id || 'export'}`}
      persistKey={`optimization_solution_${solution.id || 'default'}`}
      scroll={{ y: 400 }}
      pagination={false}
      size="small"
      onRow={(record) => ({
        onClick: () => {
          onCardClick?.(record);
        }
      })}
    />
  );
};

export default OptimizationSummary;