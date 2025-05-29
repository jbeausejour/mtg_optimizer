import React, { useEffect, useState } from 'react';
import { Card, Button, Space, Typography, notification } from 'antd';
import { 
  TrophyOutlined, 
  ShopOutlined, 
  DollarOutlined, 
  EyeOutlined,
  RocketOutlined,
  CheckCircleOutlined 
} from '@ant-design/icons';

const { Title, Text } = Typography;

const SuccessCelebration = ({ 
  bestSolution, 
  elapsedTime, 
  solutionsFound, 
  onViewResults 
}) => {
  const [showConfetti, setShowConfetti] = useState(false);

  useEffect(() => {
    // Show success notification
    notification.success({
      message: '🎉 Optimization Complete!',
      description: (
        <div>
          <div><strong>{bestSolution.store_count} stores</strong> found for <strong>${bestSolution.total_price?.toFixed(2)}</strong></div>
          <div style={{ marginTop: '4px', color: '#666' }}>
            {bestSolution.cards_found} cards • {elapsedTime} • {bestSolution.completeness ? 'Complete solution' : 'Partial solution'}
          </div>
        </div>
      ),
      duration: 8,
      placement: 'topRight',
      style: {
        background: 'linear-gradient(135deg, #f6ffed 0%, #fcffe6 100%)',
        border: '2px solid #52c41a',
        borderRadius: '12px'
      }
    });

    // Trigger confetti animation
    setShowConfetti(true);
    setTimeout(() => setShowConfetti(false), 3000);
  }, [bestSolution, elapsedTime, solutionsFound]);

  return (
    <>
      <Card
        style={{
          background: 'linear-gradient(135deg, #f6ffed 0%, #fcffe6 100%)',
          border: '2px solid #52c41a',
          borderRadius: '16px',
          marginBottom: '24px',
          position: 'relative',
          overflow: 'hidden',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          boxShadow: '0 8px 24px rgba(82, 196, 26, 0.12)'
        }}
        onClick={onViewResults}
        hoverable
        bodyStyle={{ padding: '24px' }}
      >
        {/* Animated background elements */}
        <div style={{
          position: 'absolute',
          top: '-50%',
          right: '-50%',
          width: '200%',
          height: '200%',
          background: 'radial-gradient(circle, rgba(82, 196, 26, 0.1) 0%, transparent 70%)',
          animation: showConfetti ? 'pulse 2s ease-in-out infinite' : 'none'
        }} />
        
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                background: '#52c41a',
                borderRadius: '50%',
                width: '48px',
                height: '48px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                animation: showConfetti ? 'bounce 1s ease-in-out' : 'none'
              }}>
                <TrophyOutlined style={{ fontSize: '24px', color: 'white' }} />
              </div>
              <div>
                <Title level={3} style={{ margin: 0, color: '#52c41a' }}>
                  Optimization Successful!
                </Title>
                <Text style={{ fontSize: '16px', color: '#666' }}>
                  Found the best solution in {elapsedTime}
                </Text>
              </div>
            </div>
            
            <Button 
              type="primary" 
              size="large"
              icon={<EyeOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onViewResults();
              }}
              style={{
                background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
                border: 'none',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(82, 196, 26, 0.3)'
              }}
            >
              View Results
            </Button>
          </div>

          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', 
            gap: '16px',
            marginBottom: '16px'
          }}>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(255, 255, 255, 0.7)', borderRadius: '8px' }}>
              <ShopOutlined style={{ fontSize: '20px', color: '#1890ff', marginBottom: '4px' }} />
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1890ff' }}>
                {bestSolution.store_count}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Stores</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(255, 255, 255, 0.7)', borderRadius: '8px' }}>
              <DollarOutlined style={{ fontSize: '20px', color: '#52c41a', marginBottom: '4px' }} />
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#52c41a' }}>
                ${bestSolution.total_price?.toFixed(2)}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Total Price</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(255, 255, 255, 0.7)', borderRadius: '8px' }}>
              <CheckCircleOutlined style={{ fontSize: '20px', color: '#722ed1', marginBottom: '4px' }} />
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#722ed1' }}>
                {bestSolution.cards_found}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Cards Found</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(255, 255, 255, 0.7)', borderRadius: '8px' }}>
              <RocketOutlined style={{ fontSize: '20px', color: '#fa8c16', marginBottom: '4px' }} />
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fa8c16' }}>
                {solutionsFound}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Solutions</div>
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <Space size="middle">
              <div style={{
                background: bestSolution.completeness ? 'rgba(82, 196, 26, 0.1)' : 'rgba(250, 140, 22, 0.1)',
                color: bestSolution.completeness ? '#52c41a' : '#fa8c16',
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '14px',
                fontWeight: 'bold'
              }}>
                {bestSolution.completeness ? '✅ Complete Solution' : '⚠️ Partial Solution'}
              </div>
              <Text style={{ color: '#666' }}>•</Text>
              <Text style={{ color: '#666' }}>Click to view detailed results</Text>
            </Space>
          </div>
        </div>
      </Card>

      {/* Add CSS animations */}
      <style>{`
        @keyframes pulse {
          0% { transform: scale(1); opacity: 0.1; }
          50% { transform: scale(1.05); opacity: 0.2; }
          100% { transform: scale(1); opacity: 0.1; }
        }
        
        @keyframes bounce {
          0%, 20%, 53%, 80%, 100% { transform: translate3d(0,0,0); }
          40%, 43% { transform: translate3d(0,-15px,0); }
          70% { transform: translate3d(0,-7px,0); }
          90% { transform: translate3d(0,-2px,0); }
        }
      `}</style>
    </>
  );
};

export default SuccessCelebration;