import React, { useState, useEffect } from 'react';
import { Modal, Button, Space, Alert, Typography, Divider, message } from 'antd';
import { ShoppingCartOutlined, ExportOutlined, InfoCircleOutlined, CaretRightOutlined, CaretDownOutlined, PlayCircleOutlined, SettingOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;


const generateAutomationURL = (cards, store) => {
  console.log('🔍 Generating automation URL for store:', store.site_name);
  
  // For Crystal Commerce sites, we use form submission (not URL generation)
  if (['crystal', 'scrapper'].includes(store.method?.toLowerCase())) {
    console.log('💎 Crystal Commerce - will use form submission (not URL)');
    return store.purchase_url; // Just return the endpoint for display purposes
  } 
  // For other sites, use individual cart approach
  else {
    console.log('🛍️ Non-Crystal Commerce - using auto_cart URL');
    
    const baseUrl = store.purchase_url || store.url;
    const cartData = encodeURIComponent(JSON.stringify(cards));
    const finalUrl = `${baseUrl}?auto_cart=${cartData}`;
    
    console.log('🔗 Generated URL:', finalUrl);
    return finalUrl;
  }
};

const UserscriptBasedAutomation = ({ cards, store, onSearch }) => {
  const [expanded, setExpanded] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [userscriptInstalled, setUserscriptInstalled] = useState(false);
  const [debugInfo, setDebugInfo] = useState('');
  const [manualOverride, setManualOverride] = useState(false);

  // Add comprehensive safety checks for store object
  if (!store) {
    console.error('❌ UserscriptBasedAutomation: No store object provided');
    return (
      <Alert
        message="Error: Store data not available"
        description="The store information is missing. Please try again."
        type="error"
        showIcon
      />
    );
  }

  // Log the actual store structure for debugging
  console.log('📦 UserscriptBasedAutomation received store:', store);

  const storeName = store.site_name || store.name || 'Unknown Store';
  const storeMethod = store.method || 'unknown';

  // Only proceed with userscript automation for Crystal Commerce sites
  if (!['crystal', 'scrapper'].includes(storeMethod.toLowerCase())) {
    return (
      <Alert
        message="Userscript automation not available"
        description={`This store (${storeName}) uses ${storeMethod} method. Userscript automation is only available for Crystal Commerce sites.`}
        type="info"
        showIcon
        style={{ margin: '16px' }}
      />
    );
  }

  // Try to generate automation URL with error handling
  let automationURL;
  try {
    automationURL = generateAutomationURL(cards, store);
  } catch (error) {
    console.error('❌ Failed to generate automation URL:', error);
    return (
      <Alert
        message="URL Generation Error"
        description={`Failed to generate automation URL for ${storeName}. Error: ${error.message}`}
        type="error"
        showIcon
        style={{ margin: '16px' }}
      />
    );
  }

  // Enhanced userscript detection with multiple methods
  useEffect(() => {
    const checkUserscript = () => {
      const checks = {
        crystalCommerceUserscript: !!window.crystalCommerceUserscript,
        tampermonkey: !!window.tampermonkey,
        violentmonkey: !!window.violentmonkey,
        greasemonkey: !!window.greasemonkey,
        // Check for common userscript managers
        userScriptManager: !!(window.tampermonkey || window.violentmonkey || window.greasemonkey),
        // Check for our specific script function
        autoCartFunction: typeof window.addCardsToCart === 'function',
        // Check for userscript-specific objects
        GM_info: typeof GM_info !== 'undefined',
        // Check if any userscript globals exist
        hasUserscriptGlobals: typeof GM !== 'undefined' || typeof GM_getValue !== 'undefined'
      };
      
      const detectedUserscript = checks.crystalCommerceUserscript || 
                                checks.autoCartFunction ||
                                (checks.userScriptManager && checks.hasUserscriptGlobals);
      
      setUserscriptInstalled(detectedUserscript || manualOverride);
      
      // Update debug info
      const debugDetails = Object.entries(checks)
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');
      setDebugInfo(debugDetails);
      
      console.log('🔍 Userscript detection results:', checks);
      console.log('✅ Userscript detected:', detectedUserscript);
    };
    
    // Check immediately
    checkUserscript();
    
    // Check again after delays to catch late-loading userscripts
    const timeouts = [500, 1000, 2000, 5000];
    const timeoutIds = timeouts.map(delay => 
      setTimeout(checkUserscript, delay)
    );
    
    // Listen for custom events from userscript
    const handleUserscriptReady = () => {
      console.log('🎯 Userscript ready event received');
      checkUserscript();
    };
    
    window.addEventListener('userscriptReady', handleUserscriptReady);
    window.addEventListener('crystalCommerceReady', handleUserscriptReady);
    
    return () => {
      timeoutIds.forEach(clearTimeout);
      window.removeEventListener('userscriptReady', handleUserscriptReady);
      window.removeEventListener('crystalCommerceReady', handleUserscriptReady);
    };
  }, [manualOverride]);

  const handleUserscriptInstall = () => {
    const userscriptCode = `
// ==UserScript==
// @name         Crystal Commerce Auto Cart
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Automatically add cards to cart on Crystal Commerce sites
// @match        https://*.crystalcommerce.com/*
// @match        https://*.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    // Set detection flag immediately
    window.crystalCommerceUserscript = true;
    
    // Dispatch ready event
    window.dispatchEvent(new CustomEvent('crystalCommerceReady'));
    
    // Function to add cards to cart
    window.addCardsToCart = function(cards) {
        console.log('Adding cards to cart:', cards);
        // Your cart addition logic here
        cards.forEach(card => {
            console.log(\`Adding \${card.name} (ID: \${card.variant_id}) x\${card.quantity}\`);
        });
    };
    
    // Check for auto_cart parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    const autoCart = urlParams.get('auto_cart');
    
    if (autoCart) {
        try {
            const cards = JSON.parse(decodeURIComponent(autoCart));
            setTimeout(() => addCardsToCart(cards), 1000);
        } catch (e) {
            console.error('Error parsing auto cart data:', e);
        }
    }
})();`;

    // Copy to clipboard
    navigator.clipboard.writeText(userscriptCode).then(() => {
      message.success('Userscript code copied to clipboard!');
    }).catch(() => {
      message.info('Please copy the userscript code manually from the browser console');
      console.log('Userscript code:', userscriptCode);
    });
    
    // Open Tampermonkey
    window.open('https://tampermonkey.net/', '_blank');
  };
  
  const handleDirectAutomation = async () => {
    setIsProcessing(true);
    
    try {
      // For Crystal Commerce, submit form with variant IDs included
      if (['crystal', 'scrapper'].includes(store.method?.toLowerCase())) {
        console.log('💎 Submitting Crystal Commerce form with variant IDs');
        console.log('🎯 Store payload:', store.payload);
        
        // Extract variant IDs from cards
        const variantIds = cards.map(card => card.variant_id).filter(Boolean);
        console.log('🎯 Variant IDs to include:', variantIds);
        
        if (variantIds.length === 0) {
          message.error('No variant IDs found in cards');
          return;
        }
        
        // MODIFIED: Add variant IDs to the URL as a parameter
        const baseUrl = store.purchase_url;
        const urlWithParams = new URL(baseUrl);
        urlWithParams.searchParams.set('auto_variant_ids', JSON.stringify(variantIds));
        
        // Create and submit form with the backend payload
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = urlWithParams.toString(); // Use URL with parameters
        form.target = '_blank';
        
        // Add authenticity token (from backend)
        const tokenInput = document.createElement('input');
        tokenInput.type = 'hidden';
        tokenInput.name = 'authenticity_token';
        tokenInput.value = store.payload.authenticity_token;
        form.appendChild(tokenInput);
        
        // Add query with card names (from backend)
        const queryInput = document.createElement('input');
        queryInput.type = 'hidden';
        queryInput.name = 'query';
        queryInput.value = store.payload.query;
        form.appendChild(queryInput);
        
        // Add submit button (from backend) - using 'submitBtn' to avoid name conflict
        const submitInput = document.createElement('input');
        submitInput.type = 'hidden';
        submitInput.name = 'submitBtn'; // Changed from 'submit' to avoid overriding form.submit()
        submitInput.value = store.payload.submit;
        form.appendChild(submitInput);
        
        console.log('📤 Submitting form with:');
        console.log('- URL with auto_variant_ids:', urlWithParams.toString());
        console.log('- authenticity_token:', store.payload.authenticity_token ? 'present' : 'missing');
        console.log('- query:', store.payload.query ? store.payload.query.substring(0, 50) + '...' : 'missing');
        console.log('- submitBtn:', store.payload.submit);
        
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
        
        message.success(`Form submitted to ${storeName}! Userscript will add ${variantIds.length} specific cards automatically.`);
      } 
      // For other sites, use existing logic
      else {
        const cartData = encodeURIComponent(JSON.stringify(cards));
        const url = `${store.purchase_url}?auto_cart=${cartData}`;
        window.open(url, '_blank');
        message.success(`Automation URL opened for ${storeName}!`);
      }
    } catch (error) {
      console.error('Error in handleDirectAutomation:', error);
      message.error(`Failed to start automation: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCopyURL = async () => {
    try {
      await navigator.clipboard.writeText(automationURL);
      message.success("Automation URL copied! Open this URL on the target site.");
    } catch (err) {
      message.error("Failed to copy automation URL.");
    }
  };

  const handleManualSearch = () => {
    try {
      onSearch();
    } catch (error) {
      console.error('Error in manual search:', error);
      message.error('Failed to open search page.');
    }
  };

  const toggleManualOverride = () => {
    setManualOverride(!manualOverride);
    message.info(manualOverride ? 'Manual override disabled' : 'Manual override enabled - button will be clickable');
  };

  return (
    <div style={{ 
      padding: '16px', 
      backgroundColor: '#f0f8ff', 
      border: '1px solid #1890ff', 
      borderRadius: '6px', 
      marginTop: '16px' 
    }}>
      <Title level={5}>
        <PlayCircleOutlined style={{ color: '#1890ff', marginRight: '8px' }} />
        {storeName} – Userscript Automation (No Console!)
      </Title>
      
      {/* Debug Information */}
      <Alert
        message={`Detection Status: ${userscriptInstalled ? '✅ Ready' : '❌ Not Detected'}`}
        description={
          <div>
            <div>Debug info: {debugInfo}</div>
            <Button 
              size="small" 
              icon={<SettingOutlined />}
              onClick={toggleManualOverride}
              style={{ marginTop: '8px' }}
            >
              {manualOverride ? 'Disable Manual Override' : 'Enable Manual Override'}
            </Button>
          </div>
        }
        type={userscriptInstalled ? 'success' : 'warning'}
        showIcon
        style={{ marginBottom: '16px' }}
      />
      
      {!userscriptInstalled && !manualOverride ? (
        <Alert
          message="Userscript Required (One-time Setup)"
          description="Install Tampermonkey userscript to enable automatic cart addition without dev console."
          type="warning"
          showIcon
          action={
            <Button size="small" onClick={handleUserscriptInstall}>
              Get Userscript Code
            </Button>
          }
          style={{ marginBottom: '16px' }}
        />
      ) : (
        <Alert
          message={userscriptInstalled ? "✅ Userscript Detected!" : "⚠️ Manual Override Active"}
          description={userscriptInstalled ? 
            "Automation will work automatically when you click the button below." :
            "Manual override is enabled. The automation button is now clickable for testing."
          }
          type={userscriptInstalled ? "success" : "info"}
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Space style={{ marginBottom: '12px' }}>
        <Button type="default" onClick={() => setExpanded(!expanded)}>
          {expanded ? <CaretDownOutlined /> : <CaretRightOutlined />}
          {expanded ? 'Hide' : 'Show'} Card Details ({cards.length} items)
        </Button>
      </Space>
      
      {expanded && (
        <div style={{ 
          marginBottom: '16px', 
          padding: '12px', 
          backgroundColor: '#fafafa', 
          borderRadius: '4px',
          maxHeight: '150px',
          overflowY: 'auto'
        }}>
          {cards.map((card, index) => (
            <div key={index} style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              marginBottom: '4px',
              fontSize: '13px'
            }}>
              <Text>{card.name}</Text>
              <Text type="secondary">
                ${card.price} × {card.quantity || 1} (ID: {card.variant_id})
              </Text>
            </div>
          ))}
        </div>
      )}

      <Space direction="vertical" style={{ width: '100%' }}>
        <div>
          <Text strong style={{ color: (userscriptInstalled || manualOverride) ? '#52c41a' : '#fa8c16' }}>
            Method 1: Automatic (No Console Required)
          </Text>
          <div style={{ marginTop: '8px' }}>
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />}
              block 
              onClick={handleDirectAutomation}
              loading={isProcessing}
              size="large"
              disabled={!userscriptInstalled && !manualOverride}
            >
              🚀 Open Site & Auto-Run Cart Addition
            </Button>
          </div>
          {!userscriptInstalled && !manualOverride && (
            <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}>
              Install userscript first or enable manual override to test
            </Text>
          )}
        </div>
        
        <Divider style={{ margin: '12px 0' }}>OR</Divider>
        
        <div>
          <Text strong>Method 2: Manual URL Approach</Text>
          <div style={{ marginTop: '8px' }}>
            <Space style={{ width: '100%' }}>
              <Button 
                onClick={handleManualSearch}
                icon={<ExportOutlined />}
              >
                🔍 Open Site Normally
              </Button>
              <Button 
                onClick={handleCopyURL}
                type="default"
              >
                📋 Copy Auto URL
              </Button>
            </Space>
          </div>
        </div>
      </Space>
      
      <Divider style={{ margin: '12px 0' }} />
      
      <div style={{ fontSize: '12px', color: '#666' }}>
        <Text strong>Store Info:</Text>
        <div style={{ marginTop: '4px', fontSize: '10px', fontFamily: 'monospace' }}>
          <div>Method: {storeMethod}</div>
          <div>Site ID: {store.site_id}</div>
          {store.purchase_url && <div>URL: {store.purchase_url}</div>}
          {store.url && <div>Fallback URL: {store.url}</div>}
        </div>
        
        <Text strong style={{ marginTop: '8px', display: 'block' }}>How it works:</Text>
        <ul style={{ margin: '4px 0 0 0', paddingLeft: '16px' }}>
          <li><strong>One-time setup:</strong> Install browser userscript (Tampermonkey)</li>
          <li><strong>Automatic:</strong> Click button → opens special URL → automation runs</li>
          <li><strong>No dev console:</strong> Everything happens automatically</li>
          <li><strong>Works on Crystal Commerce sites:</strong> {storeName}</li>
        </ul>
        
        {isProcessing && (
          <Alert 
            message="Opening automation URL..." 
            description="If userscript is installed, cart addition will start automatically"
            type="info" 
            size="small"
            style={{ marginTop: '8px' }}
          />
        )}
      </div>
    </div>
  );
};

// Updated PurchaseHandler component with userscript-based automation
const PurchaseHandler = ({ purchaseData, isOpen, onClose }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [storeStatus, setStoreStatus] = useState({});
  const [expandedStores, setExpandedStores] = useState({});

  const toggleStoreExpansion = (siteName) => {
    setExpandedStores(prev => ({
      ...prev,
      [siteName]: !prev[siteName]
    }));
  };
  
  // Form-based store submission for Crystal Commerce
  const submitStoreForm = async (store) => {
    try {
      console.info(`Submitting form for ${store.site_name} with method ${store.method}`);
      
      if (store.method === 'crystal' || store.method === 'scrapper') {
        // Extract variant IDs from cards (ONLY for Crystal Commerce)
        const variantIds = store.cards.map(card => card.variant_id).filter(Boolean);
        console.log('🎯 Variant IDs to include for', store.site_name, ':', variantIds);
        
        if (variantIds.length === 0) {
          console.error('No variant IDs found in cards for', store.site_name);
          return false;
        }
        
        // Add variant IDs to the URL as a parameter
        const baseUrl = store.purchase_url; // FIXED: was undefined
        const urlWithParams = new URL(baseUrl);
        urlWithParams.searchParams.set('auto_variant_ids', JSON.stringify(variantIds));
        
        // Create and submit form with the backend payload
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = urlWithParams.toString(); // Use URL with parameters
        form.target = '_blank';
        
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
        submitInput.name = 'submitBtn';
        submitInput.value = store.payload.submit;
        form.appendChild(submitInput);
        
        console.log('📤 Bulk: URL with auto_variant_ids:', urlWithParams.toString());
        
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
        
      } else if (store.method === 'f2f') {
        // F2F stores don't need variant IDs
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = store.purchase_url; // No variant IDs for F2F
        form.target = '_blank';
        
        const queryInput = document.createElement('input');
        queryInput.type = 'hidden';
        queryInput.name = 'payload';
        queryInput.value = store.payload;
        form.appendChild(queryInput);
        
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
      }
    
      await new Promise(resolve => setTimeout(resolve, 2000));
      return true;
    } catch (err) {
      console.error(`Error submitting form for ${store.site_name}:`, err);
      return false;
    }
  };

  // Handle Shopify and F2F carts (unchanged)
  const handleShopifyCart = async (store) => {
    try {
      setStoreStatus(prev => ({...prev, [store.site_name]: 'processing'}));
      
      const parsedUrl = new URL(store.purchase_url);
      const baseUrl = `${parsedUrl.protocol}//${parsedUrl.hostname}`;
      
      let cartUrl = `${baseUrl}/cart/`;
      
      store.cards.forEach((card, index) => {
        const quantity = card.quantity || 1;
        cartUrl += `${index === 0 ? '' : ','}${card.variant_id}:${quantity}`;
      });
      
      const notification = document.createElement('div');
      notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background-color: #52c41a; color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 10000; font-family: Arial, sans-serif;';
      notification.textContent = `Opening ${store.site_name} cart with ${store.cards.length} items...`;
      document.body.appendChild(notification);
      
      window.open(cartUrl, '_blank');
      
      setTimeout(() => {
        if (document.body.contains(notification)) {
          document.body.removeChild(notification);
        }
      }, 3000);
      
      setStoreStatus(prev => ({...prev, [store.site_name]: 'success'}));
      return true;
    } catch (err) {
      console.error(`Shopify cart error for ${store.site_name}:`, err);
      setStoreStatus(prev => ({...prev, [store.site_name]: 'error'}));
      setError(`Error adding items to ${store.site_name}: ${err.message}`);
      return false;
    }
  };

  const handleF2FCart = async (store) => {
    // Similar implementation to handleShopifyCart
    return handleShopifyCart(store); // Placeholder - use your existing implementation
  };

  const handleBuyAll = async () => {
    setError(null);
    setIsSubmitting(true);
  
    try {
      const results = await Promise.all(
        purchaseData.map(store => {
          if (store.method === "shopify") {
            return handleShopifyCart(store);
          } else if (store.method === "f2f") {
            return handleF2FCart(store);
          } else {
            return submitStoreForm(store);
          }
        })
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

  const getTotalPrice = (store) => {
    if (!store.cards || store.cards.length === 0) return 0;
    return store.cards.reduce((sum, card) => sum + (card.price * (card.quantity || 1)), 0);
  };

  const getStatusColor = (store) => {
    const status = storeStatus[store.site_name];
    if (status === 'success') return '#52c41a';
    if (status === 'error') return '#f5222d';
    if (status === 'processing') return '#faad14';
    return undefined;
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
      width={700}
    >
      <div style={{ padding: '16px' }}>
        {error && (
          <Alert message={error} type="error" showIcon style={{ marginBottom: '16px' }} />
        )}
        
        <Alert
          message="SOLUTION: Browser Userscript (No Console!)"
          description="Install a one-time userscript to enable automatic cart addition without using developer console."
          type="success"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        
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
          {purchaseData?.map((store) => {
            const currentStatus = storeStatus[store.site_name];
            const totalPrice = getTotalPrice(store).toFixed(2);
            const isCrystal = store.method === 'crystal' || store.method === 'scrapper';

            return (
              <div
                key={store.site_name}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  marginBottom: '12px'
                }}
              >
                <div
                  onClick={() => toggleStoreExpansion(store.site_name)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    padding: '12px',
                    background: getStatusColor(store),
                    borderRadius: '4px 4px 0 0',
                    color: (currentStatus === 'success' || currentStatus === 'error') ? 'white' : 'inherit'
                  }}
                >
                  {expandedStores[store.site_name] ? <CaretDownOutlined /> : <CaretRightOutlined />}
                  <span style={{ marginLeft: '8px', fontWeight: 'bold' }}>
                    {store.site_name}
                  </span>
                  <span style={{ marginLeft: 'auto' }}>
                    {store.card_count} cards • ${totalPrice}
                  </span>
                </div>

                {expandedStores[store.site_name] && (
                  <div style={{ padding: '0' }}>
                    {isCrystal ? (
                      <UserscriptBasedAutomation 
                        cards={store.cards}
                        store={store}
                        onSearch={() => submitStoreForm(store)}
                      />
                    ) : (
                      <div style={{ padding: '16px' }}>
                        {/* Your existing non-crystal store handling */}
                        <div style={{ marginBottom: '12px' }}>
                          {store.cards.map((card) => (
                            <div key={card.variant_id} style={{ padding: '4px 0', borderBottom: '1px solid #eee' }}>
                              <span style={{ fontWeight: 'bold' }}>{card.name}</span>
                              <span style={{ marginLeft: '8px' }}>Qty: {card.quantity || 1}</span>
                              <span style={{ marginLeft: '8px' }}>Price: ${card.price.toFixed(2)}</span>
                              <span style={{ marginLeft: '8px' }}>Variant: {card.variant_id}</span>
                            </div>
                          ))}
                        </div>
                        
                        <Button
                          size="small"
                          onClick={() => {
                            if (store.method === "shopify") {
                              handleShopifyCart(store);
                            } else if (store.method === "f2f") {
                              handleF2FCart(store);
                            } else {
                              submitStoreForm(store);
                            }
                          }}
                          disabled={currentStatus === 'processing'}
                          loading={currentStatus === 'processing'}
                        >
                          Process {currentStatus !== 'processing' && <ExportOutlined style={{ marginLeft: '4px' }} />}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        
        <Alert
          message="Userscript automation: One-time setup enables automatic cart addition without developer console."
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
        />
      </div>
    </Modal>
  );
};

export default PurchaseHandler;