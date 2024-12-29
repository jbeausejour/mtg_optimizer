import React, { useState } from 'react';
import { Button, Modal, Space, Divider, Typography, Alert, Spin } from 'antd';
import { ExportOutlined, ShoppingCartOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const PurchaseUrls = ({ purchaseData, isOpen, onClose }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
    
  const submitForm = (url, payload) => {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = url;
    form.target = '_blank';
    
    // Add authenticity token
    const tokenInput = document.createElement('input');
    tokenInput.type = 'hidden';
    tokenInput.name = 'authenticity_token';
    tokenInput.value = 'Dwn7IuTOGRMC6ekxD8lNnJWrsg45BVs85YplhjuFzbM=';
    form.appendChild(tokenInput);
    
    // Add query input with card names
    const queryInput = document.createElement('input');
    queryInput.type = 'hidden';
    queryInput.name = 'query';
    // Join card names with newlines
    queryInput.value = payload.map(card => card.name).join('\n');
    form.appendChild(queryInput);
    
    // Add submit input
    const submitInput = document.createElement('input');
    submitInput.type = 'hidden';
    submitInput.name = 'submit';
    submitInput.value = 'Continue';
    form.appendChild(submitInput);
  
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  };

  const handleBuyAll = async () => {
    setIsSubmitting(true);
    setError(null);
    
    try {
      const results = await Promise.all(
        purchaseData?.map(store => {
          try {
            submitForm(store.purchase_url, store.cards); // Note: using store.cards instead of store.payload
            return true;
          } catch (err) {
            console.error(`Error submitting form for ${store.site_name}:`, err);
            return false;
          }
        }) || []
      );
      
      if (results.some(result => !result)) {
        setError('Some store tabs failed to open. Please try opening stores individually.');
      } else {
        onClose();
      }
    } catch (err) {
      setError('Failed to open store tabs. Please check your popup blocker settings.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const totalCards = purchaseData?.reduce((sum, data) => sum + data.card_count, 0) || 0;

  return (
    <Modal
      title={
        <Space>
          <Title level={4} style={{ margin: 0 }}>Purchase Cards</Title>
          <Text type="secondary">
            ({totalCards} cards across {purchaseData?.length || 0} stores)
          </Text>
        </Space>
      }
      open={isOpen}
      onCancel={onClose}
      footer={null}
      width={600}
    >
      <div style={{ padding: '16px' }}>
        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            style={{ marginBottom: '16px' }}
          />
        )}

        <Button 
          type="primary"
          icon={<ShoppingCartOutlined />}
          block
          size="large"
          onClick={handleBuyAll}
          disabled={isSubmitting || !purchaseData?.length}
          loading={isSubmitting}
        >
          Open All Store Tabs ({purchaseData?.length || 0})
        </Button>
        
        <Divider />
        
        <div style={{ marginBottom: '16px' }}>
          {purchaseData?.map((store) => (
            <Button 
              key={store.site_name}
              onClick={() => {
                try {
                  submitForm(store.purchase_url, store.payload);
                  onClose();
                } catch (err) {
                  console.error(`Error opening ${store.site_name}:`, err);
                  setError(`Failed to open ${store.site_name}. Please check your popup blocker.`);
                }
              }}
              block
              style={{ 
                marginTop: '8px', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center' 
              }}
            >
              <span>{store.site_name} ({store.card_count} cards)</span>
              <ExportOutlined />
            </Button>
          ))}
        </div>

        <Alert
          message="You may need to allow pop-ups in your browser to open multiple store tabs."
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
        />
      </div>
    </Modal>
  );
};

export default PurchaseUrls;