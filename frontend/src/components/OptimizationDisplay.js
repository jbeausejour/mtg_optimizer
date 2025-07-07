import React, { useState } from 'react';
import { Row, Col, Card, Collapse, Typography, Tag, Space, Button, message, Alert } from 'antd';
import { WarningOutlined, ShoppingCartOutlined, CheckCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { getStandardTableColumns } from '../utils/tableConfig';
import EnhancedTable from './EnhancedTable';
import PurchaseHandler from './PurchaseUrls';
import api from '../utils/api';

const { Title, Text } = Typography;
const { Panel } = Collapse;

// Helper functions for backward compatibility with new field names
const getSolutionMetrics = (solution) => {
  // Use new fields if available, fallback to legacy fields
  const cardsRequiredTotal = solution.cards_required_total ?? solution.cards_required_total ?? 0;
  const cardsRequiredUnique = solution.cards_required_unique ?? (solution.missing_cards ? cardsRequiredTotal - solution.missing_cards.length : 0);
  const cardsFoundTotal = solution.cards_found_total ?? solution.nbr_card_in_solution ?? solution.total_card_found ?? 0;
  const cardsFoundUnique = solution.cards_found_unique ?? (cardsRequiredUnique - (solution.missing_cards_count ?? 0));
  
  // Use new completeness fields if available, calculate if not
  const completenessByQuantity = solution.completeness_by_quantity ?? 
    (cardsRequiredTotal > 0 ? cardsFoundTotal / cardsRequiredTotal : 0);
  const completenessByUnique = solution.completeness_by_unique ?? 
    (cardsRequiredUnique > 0 ? cardsFoundUnique / cardsRequiredUnique : 0);
  
  const isComplete = solution.is_complete ?? (solution.missing_cards_count === 0);
  const missingCardsCount = solution.missing_cards_count ?? 0;
  
  return {
    cardsRequiredTotal,
    cardsRequiredUnique,
    cardsFoundTotal,
    cardsFoundUnique,
    completenessByQuantity,
    completenessByUnique,
    isComplete,
    missingCardsCount,
    totalPrice: solution.total_price ?? 0,
    numberStore: solution.number_store ?? 0,
    missingCards: solution.missing_cards ?? []
  };
};

export const OptimizationSummary = ({ result, onCardClick }) => {
  const solutions = result?.solutions || [];
  const errors = result?.errors || {};
  
  const sortedSolutions = [...solutions].sort((a, b) => {
    if (a.is_best_solution) return -1;
    if (b.is_best_solution) return 1;
    
    const metricsA = getSolutionMetrics(a);
    const metricsB = getSolutionMetrics(b);
    
    if (metricsA.missingCardsCount !== metricsB.missingCardsCount) {
      return metricsA.missingCardsCount - metricsB.missingCardsCount;
    }
    if (metricsA.totalPrice !== metricsB.totalPrice) {
      return metricsA.totalPrice - metricsB.totalPrice;
    }
    return metricsA.numberStore - metricsB.numberStore;
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

  // Solution Details component
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
      <Card title="Solution Details" size="small" style={{ marginTop: 16 }}>
        <EnhancedTable
          dataSource={dataSource}
          columns={columns}
          exportFilename={`optimization_solution_${solution.id || 'export'}`}
          persistKey={`optimization_solution_${solution.id || 'default'}`}
          scroll={{ y: 400 }}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          size="small"
          onRow={(record) => ({
            onClick: () => {
              onCardClick?.(record);
            }
          })}
        />
      </Card>
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
            {result.algorithm_used && (
              <Tag color="blue" icon={<InfoCircleOutlined />}>
                {result.algorithm_used.toUpperCase()}
              </Tag>
            )}
            {result.execution_time && (
              <Tag color="purple">
                {result.execution_time.toFixed(1)}s
              </Tag>
            )}
          </Space>
          
          {result.message && (
            <Text type="secondary">{result.message}</Text>
          )}

          {/* algorithm information */}
          {result.algorithm_used && (
            <Alert
              message={`Optimization completed using ${result.algorithm_used.toUpperCase()} algorithm`}
              description={
                <Space direction="vertical">
                  {result.execution_time && (
                    <Text>Execution time: {result.execution_time.toFixed(2)} seconds</Text>
                  )}
                  {result.iterations && (
                    <Text>Iterations: {result.iterations}</Text>
                  )}
                  {result.convergence_metric != null && (
                    <Text>Convergence metric: {safeToFixed(result.convergence_metric, 4)}</Text>
                  )}
                </Space>
              }
              type="info"
              showIcon
              style={{ marginTop: 8 }}
            />
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
                  <Text strong>{`${getSolutionMetrics(bestSolution).numberStore} Stores`}</Text>
                  <Tag className="success-tag">Best Solution</Tag>
                  <Tag className={getSolutionMetrics(bestSolution).isComplete ? 'complete-tag' : 'partial-tag'}>
                    {getSolutionMetrics(bestSolution).isComplete ? 'Complete' : `${(getSolutionMetrics(bestSolution).completenessByQuantity * 100).toFixed(1)}% Complete`}
                  </Tag>
                  <Tag className="price-tag">${getSolutionMetrics(bestSolution).totalPrice.toFixed(2)}</Tag>
                </Space>
                <Space>
                  {getSolutionMetrics(bestSolution).missingCardsCount > 0 && (
                    <Tag className="missing-tag" icon={<WarningOutlined />}>
                      {getSolutionMetrics(bestSolution).missingCardsCount} Missing Cards
                    </Tag>
                  )}
                  <Tag>
                    {`${getSolutionMetrics(bestSolution).cardsFoundTotal}/${getSolutionMetrics(bestSolution).cardsRequiredTotal} Cards Found`}
                  </Tag>
                  {/* Show metrics if available */}
                  {bestSolution.completeness_by_unique !== undefined && (
                    <Tag color="blue">
                      {`${getSolutionMetrics(bestSolution).cardsFoundUnique}/${getSolutionMetrics(bestSolution).cardsRequiredUnique} Types`}
                    </Tag>
                  )}
                </Space>
              </div>
            }
          >
            <StoreDistribution solution={bestSolution} />
            
            {/* completeness information */}
            {(bestSolution.completeness_by_quantity !== undefined || bestSolution.completeness_by_unique !== undefined) && (
              <Card title="Solution Quality" size="small" style={{ marginBottom: 16 }}>
                <Row gutter={16}>
                  <Col span={12}>
                    <div style={{ textAlign: 'center' }}>
                      <Text strong>Card Quantity</Text>
                      <div style={{ fontSize: '24px', color: getSolutionMetrics(bestSolution).completenessByQuantity >= 1.0 ? '#52c41a' : '#faad14' }}>
                        {(getSolutionMetrics(bestSolution).completenessByQuantity * 100).toFixed(1)}%
                      </div>
                      <Text type="secondary">{getSolutionMetrics(bestSolution).cardsFoundTotal} of {getSolutionMetrics(bestSolution).cardsRequiredTotal} cards</Text>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div style={{ textAlign: 'center' }}>
                      <Text strong>Card Types</Text>
                      <div style={{ fontSize: '24px', color: getSolutionMetrics(bestSolution).completenessByUnique >= 1.0 ? '#52c41a' : '#faad14' }}>
                        {(getSolutionMetrics(bestSolution).completenessByUnique * 100).toFixed(1)}%
                      </div>
                      <Text type="secondary">{getSolutionMetrics(bestSolution).cardsFoundUnique} of {getSolutionMetrics(bestSolution).cardsRequiredUnique} types</Text>
                    </div>
                  </Col>
                </Row>
              </Card>
            )}
            
            {getSolutionMetrics(bestSolution).missingCards.length > 0 && (
              <Card title="Missing Cards" size="small" style={{ marginBottom: 16 }}>
                <Space wrap>
                  {getSolutionMetrics(bestSolution).missingCards.map(card => (
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
            
            {/* DETAILED PANEL - This is the key addition */}
            <SolutionDetails solution={bestSolution} onCardClick={onCardClick} />
          </Panel>
        </Collapse>
      )}

      {otherSolutions.length > 0 ? (
        <Collapse>
          {otherSolutions.map((solution, index) => {
            const metrics = getSolutionMetrics(solution);
            const completenessPercentage = (metrics.completenessByQuantity * 100).toFixed(1);
            
            return (
              <Panel
                key={`solution-${solution.id || index}`}
                header={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <Space>
                      <Text strong>{`${metrics.numberStore} Stores`}</Text>
                      <Tag className={metrics.isComplete ? 'complete-tag' : 'partial-tag'}>
                        {metrics.isComplete ? 'Complete' : `${completenessPercentage}% Complete`}
                      </Tag>
                      <Tag className="price-tag">${metrics.totalPrice.toFixed(2)}</Tag>
                    </Space>
                    <Space>
                      {metrics.missingCardsCount > 0 && (
                        <Tag className="missing-tag" icon={<WarningOutlined />}>
                          {metrics.missingCardsCount} Missing Cards
                        </Tag>
                      )}
                      <Tag>
                        {`${metrics.cardsFoundTotal}/${metrics.cardsRequiredTotal} Cards Found`}
                      </Tag>
                      {/* Show metrics if available */}
                      {solution.completeness_by_unique !== undefined && (
                        <Tag color="blue">
                          {`${metrics.cardsFoundUnique}/${metrics.cardsRequiredUnique} Types`}
                        </Tag>
                      )}
                    </Space>
                  </div>
                }
              >
                <StoreDistribution solution={solution} />
                
                {/* completeness information */}
                {(solution.completeness_by_quantity !== undefined || solution.completeness_by_unique !== undefined) && (
                  <Card title="Solution Quality" size="small" style={{ marginBottom: 16 }}>
                    <Row gutter={16}>
                      <Col span={12}>
                        <div style={{ textAlign: 'center' }}>
                          <Text strong>Card Quantity</Text>
                          <div style={{ fontSize: '24px', color: metrics.completenessByQuantity >= 1.0 ? '#52c41a' : '#faad14' }}>
                            {(metrics.completenessByQuantity * 100).toFixed(1)}%
                          </div>
                          <Text type="secondary">{metrics.cardsFoundTotal} of {metrics.cardsRequiredTotal} cards</Text>
                        </div>
                      </Col>
                      <Col span={12}>
                        <div style={{ textAlign: 'center' }}>
                          <Text strong>Card Types</Text>
                          <div style={{ fontSize: '24px', color: metrics.completenessByUnique >= 1.0 ? '#52c41a' : '#faad14' }}>
                            {(metrics.completenessByUnique * 100).toFixed(1)}%
                          </div>
                          <Text type="secondary">{metrics.cardsFoundUnique} of {metrics.cardsRequiredUnique} types</Text>
                        </div>
                      </Col>
                    </Row>
                  </Card>
                )}
                
                {metrics.missingCards.length > 0 && (
                  <Card title="Missing Cards" size="small" style={{ marginBottom: 16 }}>
                    <Space wrap>
                      {metrics.missingCards.map(card => (
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
                
                {/* DETAILED PANEL - This is the key addition for other solutions too */}
                <SolutionDetails solution={solution} onCardClick={onCardClick} />
              </Panel>
            );
          })}
        </Collapse>
      ) : (
        !bestSolution && (
          <Card>
            <Text type="warning">No optimization solutions available</Text>
          </Card>
        )
      )}
    </Space>
  );
};

export default OptimizationSummary;