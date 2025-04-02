import React, { useState } from 'react';
import { Modal, Button, Space, Alert, Typography, Divider } from 'antd';
import { ShoppingCartOutlined, ExportOutlined, InfoCircleOutlined, CaretRightOutlined, CaretDownOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const persistConsoleLogs = () => {
  const oldLog = console.log;
  console.log = (...args) => {
    oldLog(...args);
    const logs = JSON.parse(localStorage.getItem("consoleLogs") || "[]");
    logs.push(args.join(" "));
    localStorage.setItem("consoleLogs", JSON.stringify(logs));
  };

  window.addEventListener("load", () => {
    const logs = JSON.parse(localStorage.getItem("consoleLogs") || "[]");
    logs.forEach((log) => oldLog(log));
    localStorage.removeItem("consoleLogs");
  });
};

persistConsoleLogs();

const generateBookmarkletCode = (cards) => {
  return `javascript:(function(){
    const cards = ${JSON.stringify(cards)};
    function waitForElement(selector, timeout = 10000) {
      return new Promise((resolve, reject) => {
        const interval = setInterval(() => {
          const el = document.querySelector(selector);
          if(el){ clearInterval(interval); resolve(el); }
        }, 100);
        setTimeout(() => { clearInterval(interval); reject("Timeout waiting for " + selector); }, timeout);
      });
    }
    async function addCard(card) {
      document.querySelectorAll("form.add-to-cart-form").forEach(form => {
        if(form.getAttribute("data-vid") !== card.variant_id){
          form.style.display = "none";
        }
      });
      try {
        const btn = await waitForElement(
          'form.add-to-cart-form[data-vid="' + card.variant_id + '"] input[type="submit"], ' +
          'form.add-to-cart-form[data-vid="' + card.variant_id + '"] button[type="submit"]'
        );
        console.log("Clicking add-to-cart for", card.name, "with variant", card.variant_id);
        btn.click();
        await new Promise(resolve => setTimeout(resolve, 2000));
      } catch(err) {
        console.error("Error adding", card.name, ":", err);
        throw err;
      }
    }
    async function addAllCards() {
      for(let i = 0; i < cards.length; i++){
        await addCard(cards[i]);
      }
    }
    addAllCards()
      .then(() => waitForElement("a.checkout-link", 10000))
      .then(link => {
        console.log("Clicking checkout link...");
        link.click();
      })
      .catch(err => console.error("Error in bookmarklet:", err));
  })();`;
};

const BookmarkletGenerator = ({ cards, siteName, onSearch }) => {
  const [expanded, setExpanded] = useState(false);
  const bookmarkletCode = generateBookmarkletCode(cards);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(bookmarkletCode);
      message.success("Booklet code copied to clipboard!");
    } catch (err) {
      message.error("Failed to copy booklet code.");
    }
  };

  return (
    <div style={{ padding: '16px', backgroundColor: '#fafafa', border: '1px solid #ddd', borderRadius: '4px', marginTop: '16px' }}>
      <Title level={5}>{siteName} – Auto Add-to-Cart Booklet</Title>
      <Space style={{ marginBottom: '8px' }}>
        <Button type="default" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Hide Card Details' : 'Show Card Details'}
        </Button>
      </Space>
      
      {expanded && cards.map(card => (
        <div key={card.variant_id} style={{ marginBottom: '8px' }}>
          <Text>{card.name} ${card.price} (Variant ID: {card.variant_id})</Text>
        </div>
      ))}
      <p style={{ marginTop: '8px' }}>
        Click the button below to open the search results page for {siteName}'s cards.
      </p>
      <Space>
        <Button type="default" onClick={onSearch}>
          Search for Cards
        </Button>
      </Space>
      <Divider />
      <p style={{ marginTop: '8px' }}>
        After reviewing the search results, use the booklet below to add cards to your cart.
      </p>
      <p style={{ marginTop: '8px' }}>
        Drag this link to your bookmarks bar:
      </p>
      <a
        draggable="true"
        href={bookmarkletCode}
        onClick={(e) => e.stopPropagation()}
        style={{ fontWeight: 'bold', color: '#1890ff', textDecoration: 'none', cursor: 'pointer' }}
        title="Drag to your bookmarks bar"
      >
        {siteName} Booklet
      </a>
      <p style={{ marginTop: '8px' }}>
        Or click below to copy the booklet code:
      </p>
      <Space>
        <Button type="primary" onClick={handleCopy}>
          Copy Code
        </Button>
      </Space>
    </div>
  );
};


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
  // Handle non-Shopify stores with traditional form submission
  const submitStoreForm = async (store) => {
    try {
      // Create a form element
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = store.purchase_url;
      form.target = '_blank';
      
      console.info(`Submitting form for ${store.site_name} with method ${store.method}`);
      
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
        submitInput.name = 'submitBtn';
        submitInput.value = store.payload.submit;
        form.appendChild(submitInput);
      } else if (store.method === 'f2f') {
        const queryInput = document.createElement('input');
        queryInput.type = 'hidden';
        queryInput.name = 'payload';
        queryInput.value = store.payload;
        form.appendChild(queryInput);
      }
    
      // Submit the form
      document.body.appendChild(form);
      form.submit();
      document.body.removeChild(form);
      
      await new Promise(resolve => setTimeout(resolve, 2000));
      return true;
    } catch (err) {
      console.error(`Error submitting form for ${store.site_name}:`, err);
      return false;
    }
  };
  
  // URL-based approach for Shopify cart
  const handleShopifyCart = async (store) => {
    try {
      setStoreStatus(prev => ({...prev, [store.site_name]: 'processing'}));
      console.log(`🛒 Processing Shopify cart for: ${store.site_name}`);
      
      // Extract base URL
      const parsedUrl = new URL(store.purchase_url);
      const baseUrl = `${parsedUrl.protocol}//${parsedUrl.hostname}`;
      console.log(`🔗 Base URL: ${baseUrl}`);
      
      // Create the cart URL with all items
      let cartUrl = `${baseUrl}/cart/`;
      
      // Add each variant ID to the URL
      store.cards.forEach((card, index) => {
        // Format: {variant_id}:{quantity}
        const quantity = card.quantity || 1;
        cartUrl += `${index === 0 ? '' : ','}${card.variant_id}:${quantity}`;
      });
      
      console.log(`🔗 Generated cart URL: ${cartUrl}`);
      
      // Show a notification
      const notification = document.createElement('div');
      notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background-color: #52c41a; color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 10000; font-family: Arial, sans-serif;';
      notification.textContent = `Opening ${store.site_name} cart with ${store.cards.length} items...`;
      document.body.appendChild(notification);
      
      // // Open the cart URL in a new tab
      window.open(cartUrl, '_blank');
      
      // Remove notification after 3 seconds
      setTimeout(() => {
        if (document.body.contains(notification)) {
          document.body.removeChild(notification);
        }
      }, 3000);
      
      setStoreStatus(prev => ({...prev, [store.site_name]: 'success'}));
      return true;
    } catch (err) {
      console.error(`💥 Shopify cart error for ${store.site_name}:`, err);
      setStoreStatus(prev => ({...prev, [store.site_name]: 'error'}));
      setError(`Error adding items to ${store.site_name}: ${err.message}`);
      return false;
    }
  };

  // URL-based approach for Shopify cart
  const handleF2FCart = async (store) => {
    try {
      setStoreStatus(prev => ({...prev, [store.site_name]: 'processing'}));
      console.log(`🛒 Processing F2F cart for: ${store.site_name}`);
      
      // Extract base URL
      const parsedUrl = new URL(store.purchase_url);
      const baseUrl = `${parsedUrl.protocol}//${parsedUrl.hostname}`;
      console.log(`🔗 Base URL: ${baseUrl}`);
      
      // Create the cart URL with all items
      let cartUrl = `${baseUrl}/cart/`;
      
      // Add each variant ID to the URL
      store.cards.forEach((card, index) => {
        // Format: {variant_id}:{quantity}
        const quantity = card.quantity || 1;
        cartUrl += `${index === 0 ? '' : ','}${card.variant_id}:${quantity}`;
      });
      
      console.log(`🔗 Generated cart URL: ${cartUrl}`);
      
      // Show a notification
      const notification = document.createElement('div');
      notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background-color: #52c41a; color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 10000; font-family: Arial, sans-serif;';
      notification.textContent = `Opening ${store.site_name} cart with ${store.cards.length} items...`;
      document.body.appendChild(notification);
      
      // // Open the cart URL in a new tab
      window.open(cartUrl, '_blank');
      
      // Remove notification after 3 seconds
      setTimeout(() => {
        if (document.body.contains(notification)) {
          document.body.removeChild(notification);
        }
      }, 3000);
      
      setStoreStatus(prev => ({...prev, [store.site_name]: 'success'}));
      return true;
    } catch (err) {
      console.error(`💥 F2F cart error for ${store.site_name}:`, err);
      setStoreStatus(prev => ({...prev, [store.site_name]: 'error'}));
      setError(`Error adding items to ${store.site_name}: ${err.message}`);
      return false;
    }
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

  const enhanceShopifyStore = (store) => {
    if (store.method === "shopify") {
      try {
        const baseUrl = new URL(store.purchase_url);
        const shopUrl = `${baseUrl.protocol}//${baseUrl.hostname}`;
        
        return {
          ...store,
          cart_update_url: `${shopUrl}/cart/update.js`,
          cart_redirect_url: `${shopUrl}/cart`,
          shop_url: shopUrl
        };
      } catch (error) {
        console.error(`Failed to enhance Shopify store: ${error.message}`);
        return store;
      }
    }
    return store;
  };

  const getStatusColor = (store) => {
    const status = storeStatus[store.site_name];
    if (status === 'success') return '#52c41a';
    if (status === 'error') return '#f5222d';
    if (status === 'processing') return '#faad14';
    return undefined; // Default button color
  };

  const enhancedPurchaseData = purchaseData.map(enhanceShopifyStore);
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
          <Alert message={error} type="error" showIcon style={{ marginBottom: '16px' }} />
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
          {enhancedPurchaseData?.map((store) => {
            const currentStatus = storeStatus[store.site_name];
            const totalPrice = getTotalPrice(store).toFixed(2);
            const isCrystal = store.method === 'crystal' || store.method === 'scrapper';
            // For crystal stores, generate the bookmarklet code for the draggable link.
            const bookmarkletCode = isCrystal ? generateBookmarkletCode(store.cards) : null;
  
            return (
              <div
                key={store.site_name}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  marginBottom: '12px'
                }}
              >
                {/* Header Section */}
                <div
                  onClick={() => toggleStoreExpansion(store.site_name)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    padding: '8px',
                    background: getStatusColor(store),
                    borderRadius: '4px 4px 0 0',
                    color: (currentStatus === 'success' || currentStatus === 'error') ? 'white' : 'inherit'
                  }}
                >
                  {expandedStores[store.site_name] ? <CaretDownOutlined /> : <CaretRightOutlined />}
                  <span style={{ marginLeft: '4px' }}>
                    {store.site_name} ({store.card_count} cards, ${totalPrice})
                  </span>
                  {isCrystal && (
                    <a
                      draggable="true"
                      href={bookmarkletCode}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        marginLeft: 'auto',
                        fontWeight: 'bold',
                        color: '#1890ff',
                        cursor: 'pointer',
                        textDecoration: 'none'
                      }}
                      title="Drag to your bookmarks bar"
                    >
                    {store.site_name} Booklet
                    </a>
                  )}
                </div>
                {/* Expanded Details */}
                {expandedStores[store.site_name] && (
                  <div style={{ padding: '8px' }}>
                    {isCrystal ? (
                      <BookmarkletGenerator 
                        cards={store.cards}
                        siteName={store.site_name}
                        onSearch={() => submitStoreForm(store)}
                      />
                    ) : (
                      <>
                        {/* Non-crystal card breakdown */}
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
                        {currentStatus === 'success' && store.method === 'shopify' ? (
                          <Button
                            size="small"
                            onClick={() => window.open(`${store.shop_url}/cart`, '_blank')}
                            icon={<ExportOutlined />}
                          >
                            Go to Cart
                          </Button>
                        ) : currentStatus === 'success' ? (
                          <Button size="small" disabled>Processed</Button>
                        ) : (
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
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
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