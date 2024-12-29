import React, { useState } from 'react';
import { Row, Col, Card, Table, Collapse, Typography, Tag, Space, Button, message } from 'antd';
import { WarningOutlined, ShoppingCartOutlined } from '@ant-design/icons';
import { getStandardTableColumns } from '../utils/tableConfig';
import PurchaseUrls from './PurchaseUrls';
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
            <div className="flex justify-between items-center">
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
          className="mb-4"
        >
          <Row gutter={[16, 16]}>
            {storeData.map(({ name, count }, index) => (
              <Col span={8} key={index}>
                <Card size="small" bordered={false} className="bg-gray-50">
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
          <PurchaseUrls 
            purchaseData={purchaseData}
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
          />
        )}
      </>
    );
  };

  return (
    <div className="w-full space-y-4">
      <Card>
        <Space direction="vertical" className="w-full">
          <Space>
            <Title level={4} className="m-0">Optimization Results</Title>
            <Tag color="blue">{`${result.sites_scraped} Sites`}</Tag>
            <Tag color="purple">{`${result.cards_scraped} Cards`}</Tag>
          </Space>
          
          {result.message && (
            <Text type="secondary">{result.message}</Text>
          )}
        </Space>
      </Card>

      {Object.values(errors).some(arr => arr?.length > 0) && (
        <Card 
          title={
            <Space>
              <WarningOutlined className="text-yellow-500" />
              <span>Issues Found</span>
            </Space>
          } 
          className="bg-yellow-50"
        >
          {errors.unreachable_stores?.length > 0 && (
            <div className="mb-4">
              <Text strong className="text-red-600">Unreachable Stores:</Text>
              <div className="mt-1">
                {errors.unreachable_stores.map(store => (
                  <Tag key={store} color="red">{store}</Tag>
                ))}
              </div>
            </div>
          )}
          {errors.unknown_languages?.length > 0 && (
            <div className="mb-4">
              <Text strong className="text-orange-600">Unknown Languages:</Text>
              <div className="mt-1">
                {errors.unknown_languages.map(lang => (
                  <Tag key={lang} color="orange">{lang}</Tag>
                ))}
              </div>
            </div>
          )}
          {errors.unknown_qualities?.length > 0 && (
            <div className="mb-4">
              <Text strong className="text-orange-600">Unknown Qualities:</Text>
              <div className="mt-1">
                {errors.unknown_qualities.map(quality => (
                  <Tag key={quality} color="orange">{quality}</Tag>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {bestSolution && (
        <Collapse
          defaultActiveKey={['best-solution']}
          className="bg-white"
        >
          <Panel
            key="best-solution"
            header={
              <div className="flex justify-between items-center w-full">
                <Space>
                  <Text strong>{`${bestSolution.number_store} Stores`}</Text>
                  <Tag color="green">Best Solution</Tag>
                  <Tag color={bestSolution.nbr_card_in_solution === bestSolution.total_qty ? 'blue' : 'orange'}>
                    {bestSolution.missing_cards_count === 0
                      ? 'Complete'
                      : `${((1 -(bestSolution.missing_cards_count / bestSolution.total_qty)) * 100).toFixed(1)}% Complete`}
                  </Tag>
                  <Text>${bestSolution.total_price.toFixed(2)}</Text>
                </Space>
                <Space>
                  {bestSolution.missing_cards_count > 0 && (
                    <Tag color="red" icon={<WarningOutlined />}>
                      {bestSolution.missing_cards_count} Missing Cards
                    </Tag>
                  )}
                  <Text type="secondary">
                    {`${bestSolution.nbr_card_in_solution-bestSolution.missing_cards_count}/${bestSolution.total_qty} Cards Found`}
                  </Text>
                </Space>
              </div>
            }
          >
            <StoreDistribution solution={bestSolution} />
            {bestSolution.missing_cards?.length > 0 && (
              <Card title="Missing Cards" size="small" className="mb-4">
                <Space wrap>
                  {bestSolution.missing_cards.map(card => (
                    <Tag
                      key={card}
                      color="red"
                      className="cursor-pointer"
                      onClick={() => onCardClick({ name: card })}
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
        <Collapse className="bg-white">
          {otherSolutions.map((solution, index) => {
            const completeness = solution.nbr_card_in_solution === solution.total_qty;
            const percentage = ((solution.nbr_card_in_solution / solution.total_qty) * 100).toFixed(1);
            
            return (
              <Panel
                key={index}
                header={
                  <div className="flex justify-between items-center w-full">
                    <Space>
                      <Text strong>{`${solution.number_store} Stores`}</Text>
                      <Tag color={completeness ? 'blue' : 'orange'}>
                        {completeness ? 'Complete' : `${percentage}% Complete`}
                      </Tag>
                      <Text>${solution.total_price.toFixed(2)}</Text>
                    </Space>
                    <Space>
                      {solution.missing_cards_count > 0 && (
                        <Tag color="red" icon={<WarningOutlined />}>
                          {solution.missing_cards_count} Missing Cards
                        </Tag>
                      )}
                      <Text type="secondary">
                        {`${solution.nbr_card_in_solution}/${bestSolution.nbr_card_in_solution} Cards Found`}
                      </Text>
                    </Space>
                  </div>
                }
              >
                <StoreDistribution solution={solution} />
                {solution.missing_cards?.length > 0 && (
                  <Card title="Missing Cards" size="small" className="mb-4">
                    <Space wrap>
                      {solution.missing_cards.map(card => (
                        <Tag 
                          key={card} 
                          color="red"
                          className="cursor-pointer"
                          onClick={() => onCardClick({ name: card })}
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
    </div>
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
          {record.foil && <Tag color="blue">Foil</Tag>}
          {record.language !== 'English' && (
            <Tag color="orange">{record.language}</Tag>
          )}
          {record.version !== 'Normal' && (
            <Tag color="purple">{record.version}</Tag>
          )}
        </Space>
      ),
    }
  ];

  return (
    <Table
      dataSource={dataSource}
      columns={columns}
      pagination={false}
      scroll={{ y: 400 }}
      size="small"
    />
  );
};

export default OptimizationSummary;