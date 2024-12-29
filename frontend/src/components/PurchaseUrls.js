import React, { useState } from 'react';
import { Modal, Button, Space, Alert, Typography, Card, Divider } from 'antd';
import { ShoppingCartOutlined, ExportOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const PurchaseHandler = ({ purchaseData, isOpen, onClose }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
    
  const submitStoreForm = (store) => {
    try {
      // Create a form element
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = store.purchase_url;
      form.target = '_blank';
      
      // Handle different store methods
      if (store.method === 'crystal' || store.method === 'scrapper') {
        // Add authenticity token
        const tokenInput = document.createElement('input');
        tokenInput.type = 'hidden';
        tokenInput.name = 'authenticity_token';
        tokenInput.value = store.payload.authenticity_token;
        form.appendChild(tokenInput);
        
        // Add query with card names
        const queryInput = document.createElement('input');
        queryInput.type = 'hidden';
        queryInput.name = 'query';
        queryInput.value = store.payload.query;
        form.appendChild(queryInput);
        
        // Add submit button
        const submitInput = document.createElement('input');
        submitInput.type = 'hidden';
        submitInput.name = 'submitBtn';  // Changed from 'submit' to 'submitBtn'
        submitInput.value = store.payload.submit;
        form.appendChild(submitInput);
      } else if (store.method === 'shopify') {
        // For Shopify stores, handle the JSON payload
        const queryInput = document.createElement('input');
        queryInput.type = 'hidden';
        queryInput.name = 'payload';
        queryInput.value = store.payload; // Already JSON stringified
        form.appendChild(queryInput);
      }
    
      // Submit the form
      document.body.appendChild(form);
      form.submit();
      document.body.removeChild(form);
      
      return true;
    } catch (err) {
      console.error(`Error submitting form for ${store.site_name}:`, err);
      return false;
    }
  };

  const handleBuyFromStore = async (store) => {
    setError(null);
    setIsSubmitting(true);
    
    try {
      const success = submitStoreForm(store);
      if (!success) {
        setError(`Failed to open ${store.site_name}. Please check your popup blocker.`);
      }
    } catch (err) {
      setError(`Error processing purchase for ${store.site_name}: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBuyAll = async () => {
    setError(null);
    setIsSubmitting(true);

    try {
      const results = await Promise.all(
        purchaseData?.map(store => {
          try {
            return submitStoreForm(store);
          } catch (err) {
            console.error(`Error submitting form for ${store.site_name}:`, err);
            return false;
          }
        }) || []
      );
      
      if (results.some(result => !result)) {
        setError('Some store tabs failed to open. Please try opening stores individually.');
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
              onClick={() => handleBuyFromStore(store)}
              disabled={isSubmitting}
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

export default PurchaseHandler;