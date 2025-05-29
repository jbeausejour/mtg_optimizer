// ==UserScript==
// @name         Crystal Commerce Auto Cart
// @namespace    http://tampermonkey.net/
// @version      1.6
// @description  Automatically add cards to cart on Crystal Commerce sites
// @match        https://*.crystalcommerce.com/*
// @match        https://*.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    console.log('🚀 Crystal Commerce Auto Cart userscript v1.6 loading...');

    // Set detection flags immediately
    window.crystalCommerceUserscript = true;
    window.userscriptVersion = '1.6';

    // Function to dispatch ready events
    function dispatchReadyEvents() {
        console.log('📡 Dispatching userscript ready events');

        try {
            window.dispatchEvent(new CustomEvent('userscriptReady', {
                detail: { version: '1.6', type: 'crystalcommerce' }
            }));
            window.dispatchEvent(new CustomEvent('crystalCommerceReady', {
                detail: { version: '1.6' }
            }));
        } catch (e) {
            console.error('Error dispatching events:', e);
        }
    }

    // Dispatch events immediately and after DOM load
    dispatchReadyEvents();

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', dispatchReadyEvents);
    }

    // Function to add cards to cart (individual approach for non-Crystal Commerce sites)
    window.addCardsToCart = function(cards) {
        console.log('🛒 Adding individual cards to cart:', cards);

        if (!Array.isArray(cards) || cards.length === 0) {
            console.error('Invalid cards data:', cards);
            return false;
        }

        const isCrystalCommerce = window.location.hostname.includes('crystalcommerce.com') ||
                                  document.querySelector('form[action*="cart"]') ||
                                  document.querySelector('.crystal-commerce') ||
                                  document.querySelector('[data-crystal]');

        if (isCrystalCommerce) {
            return addToCrystalCommerceCart(cards);
        } else {
            return addToGenericCart(cards);
        }
    };

    // Crystal Commerce specific cart addition (individual cards)
    function addToCrystalCommerceCart(cards) {
        console.log('💎 Using Crystal Commerce individual cart method');

        try {
            let cartForm = document.querySelector('form[action*="cart"]') ||
                          document.querySelector('form#cart-form') ||
                          document.querySelector('.cart-form form');

            if (!cartForm) {
                console.log('Creating new cart form...');
                cartForm = document.createElement('form');
                cartForm.method = 'POST';
                cartForm.action = '/cart/add';
                document.body.appendChild(cartForm);
            }

            let addedCount = 0;

            cards.forEach((card, index) => {
                try {
                    console.log(`Processing card ${index + 1}: ${card.name}`);

                    if (card.variant_id) {
                        const variantInput = document.createElement('input');
                        variantInput.type = 'hidden';
                        variantInput.name = `items[${index}][variant_id]`;
                        variantInput.value = card.variant_id;
                        cartForm.appendChild(variantInput);

                        const quantityInput = document.createElement('input');
                        quantityInput.type = 'hidden';
                        quantityInput.name = `items[${index}][quantity]`;
                        quantityInput.value = card.quantity || 1;
                        cartForm.appendChild(quantityInput);

                        addedCount++;
                    } else {
                        console.warn(`Card ${card.name} missing variant_id`);
                    }
                } catch (e) {
                    console.error(`Error processing card ${card.name}:`, e);
                }
            });

            if (addedCount > 0) {
                console.log(`✅ Submitting cart form with ${addedCount} items`);

                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                                 document.querySelector('input[name="authenticity_token"]')?.value;

                if (csrfToken) {
                    const tokenInput = document.createElement('input');
                    tokenInput.type = 'hidden';
                    tokenInput.name = 'authenticity_token';
                    tokenInput.value = csrfToken;
                    cartForm.appendChild(tokenInput);
                }

                cartForm.submit();
                return true;
            } else {
                console.error('No valid cards to add to cart');
                return false;
            }

        } catch (e) {
            console.error('Error in Crystal Commerce cart addition:', e);
            return false;
        }
    }

    // Generic cart addition for other sites
    function addToGenericCart(cards) {
        console.log('🛍️ Using generic cart method');

        try {
            cards.forEach((card, index) => {
                console.log(`Attempting to add: ${card.name}`);

                const addButtons = document.querySelectorAll([
                    `[data-variant-id="${card.variant_id}"]`,
                    `[data-product-id="${card.variant_id}"]`,
                    '.add-to-cart',
                    '.btn-add-cart',
                    '[onclick*="addToCart"]'
                ].join(','));

                if (addButtons.length > 0) {
                    console.log(`Found ${addButtons.length} potential add buttons`);
                    addButtons[0].click();
                } else {
                    console.warn(`No add-to-cart button found for ${card.name}`);
                }

                setTimeout(() => {}, index * 100);
            });

            return true;
        } catch (e) {
            console.error('Error in generic cart addition:', e);
            return false;
        }
    }

    // Check for automation on page load
    function checkForAutomation() {
        console.log('🔍 Checking for automation triggers...');
        console.log('📍 Current URL:', window.location.href);
        console.log('📄 Page title:', document.title);
        console.log('🌐 Hostname:', window.location.hostname);
        console.log('📂 Pathname:', window.location.pathname);

        // Check if this is a multi_search page (Crystal Commerce search results)
        const isMultiSearchPage = window.location.pathname.includes('/products/multi_search') ||
                                 window.location.pathname.includes('/multi_search');

        console.log('🔍 Is multi_search page:', isMultiSearchPage);

        // Check for automation flags in URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const hasAutoFlag = urlParams.has('auto_add_to_cart');
        const cardData = urlParams.get('card_data');

        console.log('🤖 Has auto flag:', hasAutoFlag);
        console.log('📦 Has card data:', !!cardData);

        if (isMultiSearchPage) {
            console.log('✅ On multi_search page - analyzing page content...');

            setTimeout(() => {
                // Analyze the page more thoroughly
                analyzePage();

                // Try to add cards if we detect automation
                if (hasAutoFlag || detectAutomatedSearch()) {
                    console.log('🚀 Starting automated cart addition...');
                    addAllCardsFromSearchResults();
                } else {
                    console.log('ℹ️ No automation detected - manual search');
                }
            }, 3000); // Give more time for page to load

            return; // Exit early for multi_search pages
        }

        // Check for other search results page indicators
        const isSearchResults = window.location.pathname.includes('/search') ||
                               document.querySelector('.search-results') ||
                               document.querySelector('#search-results') ||
                               document.querySelector('.product-grid') ||
                               document.querySelector('.products-grid');

        console.log('🔍 Is other search results page:', isSearchResults);

        if (isSearchResults && hasAutoFlag) {
            console.log('✅ Automated search on results page - will add cards to cart');
            setTimeout(() => {
                addAllCardsFromSearchResults();
            }, 2000);
        }

        // Check for legacy auto_cart parameter (for non-Crystal Commerce sites)
        const autoCart = urlParams.get('auto_cart');
        if (autoCart) {
            console.log('🎯 Legacy auto_cart parameter detected');
            try {
                const cards = JSON.parse(decodeURIComponent(autoCart));
                setTimeout(() => {
                    const success = window.addCardsToCart(cards);
                    showNotification(
                        success ? `✅ Added ${cards.length} cards to cart!` : `❌ Failed to add cards`,
                        success ? 'success' : 'error'
                    );
                }, 2000);
            } catch (e) {
                console.error('Error parsing auto_cart data:', e);
            }
        }
    }

    // NEW: Function to analyze the page content
    function analyzePage() {
        console.log('🔬 Analyzing page content...');

        // Look for different types of elements
        const forms = document.querySelectorAll('form');
        const addToCartForms = document.querySelectorAll('form.add-to-cart-form, form[action*="cart"]');
        const buttons = document.querySelectorAll('button, input[type="submit"]');
        const addButtons = document.querySelectorAll('[class*="add"], [value*="Add"], [onclick*="cart"]');

        console.log(`📋 Found ${forms.length} total forms`);
        console.log(`🛒 Found ${addToCartForms.length} add-to-cart forms`);
        console.log(`🔘 Found ${buttons.length} total buttons`);
        console.log(`➕ Found ${addButtons.length} add-related buttons`);

        // Log some examples
        if (addToCartForms.length > 0) {
            console.log('📝 First add-to-cart form:', addToCartForms[0]);
            console.log('📝 Form action:', addToCartForms[0].action);
            console.log('📝 Form method:', addToCartForms[0].method);
        }

        if (addButtons.length > 0) {
            console.log('📝 First add button:', addButtons[0]);
            console.log('📝 Button text:', addButtons[0].textContent || addButtons[0].value);
        }

        // Check for product containers
        const products = document.querySelectorAll([
            '.product',
            '.card',
            '.item',
            '[data-product]',
            '.product-item',
            '.search-result',
            '.listing',
            '.mtg-card'
        ].join(','));

        console.log(`📦 Found ${products.length} product containers`);
    }

    // NEW: Function to detect if this was an automated search
    function detectAutomatedSearch() {
        // Check document referrer
        const referrerHasAuto = document.referrer.includes('auto_add_to_cart');

        // Check for specific form fields that might indicate automation
        const hasAutoFields = document.querySelector('input[name="auto_add_to_cart"]') ||
                             document.querySelector('input[name="card_data"]');

        // Check URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const hasAutoParams = urlParams.has('auto_add_to_cart') || urlParams.has('card_data');

        console.log('🕵️ Automation detection:');
        console.log('- Referrer has auto:', referrerHasAuto);
        console.log('- Has auto fields:', !!hasAutoFields);
        console.log('- Has auto params:', hasAutoParams);

        return referrerHasAuto || hasAutoFields || hasAutoParams;
    }

    // NEW: Function to add all cards from search results to cart
    function addAllCardsFromSearchResults() {
        console.log('🛒 Adding all cards from search results to cart...');

        try {
            // Look for add-to-cart forms/buttons on the page
            const addToCartElements = document.querySelectorAll([
                'form.add-to-cart-form',
                '.add-to-cart-form',
                'form[action*="cart"]',
                '.add-to-cart',
                '.btn-add-cart',
                'button[onclick*="cart"]',
                'input[value*="Add to Cart"]',
                'input[type="submit"][value*="Add"]'
            ].join(','));

            console.log(`🎯 Found ${addToCartElements.length} add-to-cart elements`);

            if (addToCartElements.length === 0) {
                console.warn('⚠️ No add-to-cart elements found on search results page');
                showNotification('⚠️ No add-to-cart buttons found on results page', 'warning');
                return false;
            }

            let addedCount = 0;

            // Process each add-to-cart element
            addToCartElements.forEach((element, index) => {
                setTimeout(() => {
                    try {
                        console.log(`📦 Processing element ${index + 1}:`, element);

                        if (element.tagName === 'FORM') {
                            // Submit the form
                            element.submit();
                            console.log(`✅ Submitted form ${index + 1}`);
                        } else if (element.tagName === 'BUTTON' || element.tagName === 'INPUT') {
                            // Click the button/input
                            element.click();
                            console.log(`✅ Clicked button ${index + 1}`);
                        } else {
                            // Try clicking anyway
                            element.click();
                            console.log(`✅ Clicked element ${index + 1}`);
                        }

                        addedCount++;
                    } catch (e) {
                        console.error(`❌ Error processing element ${index + 1}:`, e);
                    }
                }, index * 500); // Stagger submissions to avoid overwhelming the server
            });

            // Show final notification
            setTimeout(() => {
                showNotification(
                    `✅ Processed ${addedCount} items from search results!`,
                    'success'
                );
            }, addToCartElements.length * 500 + 1000);

            return true;

        } catch (e) {
            console.error('❌ Error in addAllCardsFromSearchResults:', e);
            showNotification('❌ Error adding cards from search results', 'error');
            return false;
        }
    }

    // Show notification to user
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: ${type === 'success' ? '#52c41a' : type === 'error' ? '#f5222d' : '#1890ff'};
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-family: Arial, sans-serif;
            font-size: 14px;
            max-width: 300px;
            word-wrap: break-word;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            if (document.body.contains(notification)) {
                notification.style.transition = 'opacity 0.3s ease';
                notification.style.opacity = '0';
                setTimeout(() => {
                    if (document.body.contains(notification)) {
                        document.body.removeChild(notification);
                    }
                }, 300);
            }
        }, 5000);

        notification.addEventListener('click', () => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkForAutomation);
    } else {
        checkForAutomation();
    }

    // Also check after a delay in case of dynamic loading
    setTimeout(checkForAutomation, 1000);

    console.log('✅ Crystal Commerce Auto Cart userscript v1.6 loaded successfully');

})();