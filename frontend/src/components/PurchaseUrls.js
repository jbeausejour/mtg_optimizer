import React, { useState } from 'react';
import api from '../utils/api';
import { Modal, Button, Space, Alert, Typography, Divider } from 'antd';
import { ShoppingCartOutlined, ExportOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
// const fillCartInPopup = (store) => {
//   try {
//     console.log(`Opening popup for cart fill on ${store.site_name}`);

//     const popup = window.open(store.generated_url.replace('/checkout/cart', ''), '_blank');

//     popup.onload = async () => {
//       try {
//         console.log(`Popup loaded for ${store.site_name}, injecting cart fill script.`);

//         popup.fetch(store.purchase_url, {
//           method: 'POST',
//           headers: { 'Content-Type': 'application/json' },
//           body: JSON.stringify(store.payload),
//           credentials: 'include'
//         })
//         .then(response => response.json())
//         .then(data => {
//           console.log(`Cart fill response in popup:`, data);

//           if (data.carts && data.carts.length > 0) {
//             popup.location.href = store.generated_url;
//           } else {
//             console.error(`Cart fill failed in popup for ${store.site_name}`);
//             popup.close();
//           }
//         })
//         .catch(err => {
//           console.error(`Error posting cart items in popup:`, err);
//           popup.close();
//         });

//       } catch (error) {
//         console.error('Error injecting cart fill script:', error);
//         popup.close();
//       }
//     };

//   } catch (err) {
//     console.error(`Popup automation failed for ${store.site_name}:`, err);
//   }
// };

// const fillCartInPopupWithForm = (store) => {
//   try {
//     console.log(`Opening popup for cart fill on ${store.site_name}`);

//     const popup = window.open(
//       store.generated_search_url || store.generated_cart_url.replace('/checkout/cart', ''),
//       '_blank',
//       'width=900,height=700,toolbar=0,location=0,menubar=0,scrollbars=1,resizable=1'
//     );

//     if (!popup) {
//       alert('Please enable popups for this site to proceed.');
//       return;
//     }

//     popup.onload = async () => {
//       try {
//         console.log(`Popup loaded for ${store.site_name}, injecting form cart fill.`);

//         popup.addToCartViaForm = (items) => {
//           items.forEach(item => {
//             const form = popup.document.createElement('form');
//             form.method = 'POST';
//             form.action = '/cart/add';

//             const idInput = popup.document.createElement('input');
//             idInput.name = 'id';
//             idInput.value = item.id;
//             form.appendChild(idInput);

//             const qtyInput = popup.document.createElement('input');
//             qtyInput.name = 'quantity';
//             qtyInput.value = item.quantity || 1;
//             form.appendChild(qtyInput);

//             popup.document.body.appendChild(form);
//             form.submit();
//           });

//           setTimeout(() => {
//             popup.location.href = store.generated_cart_url;
//           }, 1500);
//         };

//         // Trigger the add-to-cart form injection from the popup
//         popup.addToCartViaForm(store.payload.items);

//       } catch (error) {
//         console.error('Error injecting cart fill form:', error);
//         popup.close();
//       }
//     };

//   } catch (err) {
//     console.error(`Popup automation failed for ${store.site_name}:`, err);
//   }
// };

// const handleBuyAllSearchPages = async () => {
//   setError(null);
//   setIsSubmitting(true);

//   try {
//     await Promise.all(
//       purchaseData?.map(store => handleOpenSearchPage(store)) || []
//     );
//   } catch (err) {
//     setError('Failed to open all search pages. Please check your popup blocker settings.');
//   } finally {
//     setIsSubmitting(false);
//   }
// };

// export const handleOpenSearchPage = async (store) => {
//   try {
//     const response = await api.post("/purchase_order_search", {
//       purchase_data: [store],
//     });

//     const generatedStore = response.data[0];

//     if (!generatedStore) {
//       console.error(`No generated payload for ${store.site_name}`);
//       return;
//     }

//     if (generatedStore.method === "crystal" && generatedStore.payload) {
//       // POST form for crystal
//       const form = document.createElement("form");
//       form.method = "POST";
//       form.action = generatedStore.generated_search_url;
//       form.target = "_blank";

//       Object.entries(generatedStore.payload).forEach(([key, value]) => {
//         const input = document.createElement("input");
//         input.type = "hidden";
//         input.name = key;
//         input.value = value;
//         form.appendChild(input);
//       });

//       document.body.appendChild(form);
//       form.requestSubmit(); // this avoids the shadowing issue
//       document.body.removeChild(form);
//     } else if (generatedStore.method === "f2f" && generatedStore.payload) {
//       // POST form for f2f API (to their endpoint)
//       const form = document.createElement("form");
//       form.method = "POST";
//       form.action = generatedStore.generated_search_url;
//       form.target = "_blank";

//       const input = document.createElement("input");
//       input.type = "hidden";
//       input.name = "filters";
//       input.value = JSON.stringify(generatedStore.payload.filters);
//       form.appendChild(input);

//       document.body.appendChild(form);
//       form.submit();
//       document.body.removeChild(form);
//     } else if (generatedStore.method === "shopify") {
//       // Simply open the URL
//       window.open(generatedStore.generated_search_url, "_blank");
//     } else {
//       console.error(`Unknown method for ${store.site_name}`);
//     }
//   } catch (err) {
//     console.error(`Error generating search form for ${store.site_name}:`, err);
//   }
// };

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
      } else if (store.method === 'f2f') {
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


  // const submitStoreForm_proxy = async (store) => {
  //   try {
  //     console.log(`Attempting to submit for ${store.site_name} with method ${store.method}`);
  //     console.log("Request URL:", store.purchase_url);
  //     console.log("Full store data:", store);

  //     console.log("Sending JSON payload to /proxy");

  //     const response = await api.post('/proxy', {
  //       method: 'POST',
  //       headers: { 'Content-Type': 'application/json' },
  //       credentials: 'include', 
  //       body: JSON.stringify({
  //         purchase_url: store.purchase_url,
  //         payload: store.payload
  //       }),
  //     });

  //     if (store.method === 'crystal') {
  //       window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/checkout/cart')}`, '_blank');
  //     }
  //     if (store.method === 'shopify') {
  //       window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/cart')}`, '_blank');
  //     }
  //     if (store.method === 'f2f') {
  //       window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/cart')}`, '_blank');
  //     }

  //     // console.log(`Response from ${store.site_name}:`, response.data);
  //     // const cartLink = response.data?.carts?.[0]?.links?.cart;
  //     // if (cartLink) {
  //     //   window.open(`${store.purchase_url.split('/api/')[0]}${cartLink}`, '_blank');
  //     // } else {
  //     //   if (store.method === 'crystal') {
  //     //     window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/cart')}`, '_blank');
  //     //   }
  //     //   if (store.method === 'shopify') {
  //     //     window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/cart')}`, '_blank');
  //     //   }
  //     //   if (store.method === 'f2f') {
  //     //     window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/cart')}`, '_blank');
  //     //   }
  //     //   // fallback (in case)
  //     //   window.open(`${store.purchase_url.replace('/api/v1/cart/line_items', '/cart')}`, '_blank');
  //     // }

  //     return true;
  //   } catch (err) {
  //     console.error(`Error submitting form for ${store.site_name}:`, err);
  //     console.error("Stack trace:", err.stack);
  //     return false;
  //   }
  // };

  // const submitStoreForm_purchase_order = async (store) => {
  //   try {
  //     console.log(`Generating purchase link and cart payload for ${store.site_name}`);
  
  //     // Get the purchase_url and payload from your backend
  //     const response = await api.post('/purchase_order', {
  //       purchase_data: [store]
  //     });
  
  //     const generatedStore = response.data[0];
  //     console.info(`Response returned for ${store.site_name}:`, generatedStore);
  
  //     if (generatedStore?.purchase_url && generatedStore?.payload) {
  //       // Option 1: Post directly from frontend
  //       const cartWindow = window.open('', '_blank');  // Open window early to avoid popup blockers
  //       const postResponse = await fetch(generatedStore.purchase_url, {
  //         method: 'POST',
  //         headers: { 'Content-Type': 'application/json' },
  //         body: JSON.stringify(generatedStore.payload),
  //         credentials: 'include'
  //       });
  
  //       console.log(`POST response status: ${postResponse.status}`);
  //       console.log(await postResponse.text());
  //       if (postResponse.ok) {
  //         // After successful post, redirect the opened window to cart
  //         const cartUrl = generatedStore.generated_cart_url || 
  //                         generatedStore.purchase_url.replace('/api/v1/cart/line_items', '/checkout/cart');
  //         cartWindow.location.href = cartUrl;
  //         return true;
  //       } else {
  //         cartWindow.close();
  //         console.error(`Cart POST failed for ${store.site_name}:`, await postResponse.text());
  //         return false;
  //       }
  //     } else {
  //       console.error(`No purchase_url or payload returned for ${store.site_name}`);
  //       return false;
  //     }
  
  //   } catch (err) {
  //     console.error(`Error generating purchase and posting cart for ${store.site_name}:`, err);
  //     return false;
  //   }
  // };
  
  // const submitStoreForm_headless_cart_fill = async (store) => {
  //   try {
  //     console.log(`Generating purchase link and cart payload for ${store.site_name}`);

  //     const response = await api.post('/purchase_order', {
  //       purchase_data: [store]
  //     });

  //     const generatedStore = response.data[0];
  //     console.info(`Response returned for ${store.site_name}:`, generatedStore);

  //     if (generatedStore?.purchase_url && generatedStore?.payload && generatedStore?.generated_url) {
  //       const cartWindow = window.open('', '_blank');

  //       // Call backend headless browser automation
  //       const headlessResponse = await api.post('/headless_cart_fill', {
  //         purchase_url: generatedStore.purchase_url,
  //         payload: generatedStore.payload,
  //         base_url: generatedStore.generated_url.replace('/checkout/cart', '')
  //       });

  //       if (headlessResponse.data?.cart_url) {
  //         cartWindow.location.href = headlessResponse.data.cart_url;
  //         return true;
  //       } else {
  //         cartWindow.close();
  //         console.error(`Headless fill failed for ${store.site_name}`);
  //         return false;
  //       }

  //     } else {
  //       console.error(`No purchase_url, payload, or generated_cart_url returned for ${store.site_name}`);
  //       return false;
  //     }

  //   } catch (err) {
  //     console.error(`Error generating purchase and posting cart for ${store.site_name}:`, err);
  //     return false;
  //   }
  // };

  const handleBuyFromStore = async (store) => {
    setError(null);
    setIsSubmitting(true);

    try {
      const success = await submitStoreForm(store);
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
        purchaseData?.map(store => submitStoreForm(store)) || []
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
              //onClick={() => handleOpenSearchPage(store)}
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
