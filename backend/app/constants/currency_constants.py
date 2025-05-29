"""
Currency conversion constants and utilities for MTG card pricing.
All prices are converted to CAD as the base currency for optimization.
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Currency conversion rates to CAD (as of 2025)
# These should be updated periodically or fetched from an API
CURRENCY_TO_CAD_RATES: Dict[str, float] = {
    'CAD': 1.0,      # Canadian Dollar (base currency)
    'USD': 1.35,     # US Dollar (1 USD = 1.35 CAD)
    'EUR': 1.59,     # Euro (1 EUR = 1.59 CAD)
    'GBP': 1.69,     # British Pound (1 GBP = 1.69 CAD)
    'JPY': 0.009,    # Japanese Yen (1 JPY = 0.009 CAD)
    'AUD': 0.96,     # Australian Dollar (1 AUD = 0.96 CAD)
    'CHF': 1.51,     # Swiss Franc (1 CHF = 1.51 CAD)
    'SEK': 0.128,    # Swedish Krona (1 SEK = 0.128 CAD)
    'NOK': 0.126,    # Norwegian Krone (1 NOK = 0.126 CAD)
    'DKK': 0.213,    # Danish Krone (1 DKK = 0.213 CAD)
}

# Currency symbols for display
CURRENCY_SYMBOLS: Dict[str, str] = {
    'CAD': 'C$',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'AUD': 'A$',
    'CHF': 'CHF',
    'SEK': 'kr',
    'NOK': 'kr',
    'DKK': 'kr',
}

# Supported currencies with full names
SUPPORTED_CURRENCIES: Dict[str, str] = {
    'CAD': 'Canadian Dollar',
    'USD': 'US Dollar',
    'EUR': 'Euro',
    'GBP': 'British Pound',
    'JPY': 'Japanese Yen',
    'AUD': 'Australian Dollar',
    'CHF': 'Swiss Franc',
    'SEK': 'Swedish Krona',
    'NOK': 'Norwegian Krone',
    'DKK': 'Danish Krone',
}


class CurrencyConverter:
    """Utility class for currency conversion operations"""
    
    @staticmethod
    def convert_to_cad(amount: float, from_currency: str) -> float:
        """
        Convert an amount from a given currency to CAD.
        
        Args:
            amount: The amount to convert
            from_currency: The source currency code (e.g., 'USD', 'EUR')
            
        Returns:
            The amount converted to CAD
            
        Raises:
            ValueError: If the currency is not supported
        """
        if from_currency not in CURRENCY_TO_CAD_RATES:
            logger.warning(f"Unsupported currency: {from_currency}, defaulting to CAD")
            return amount
            
        conversion_rate = CURRENCY_TO_CAD_RATES[from_currency]
        converted_amount = amount * conversion_rate
        
        logger.debug(f"Converted {amount} {from_currency} to C${converted_amount:.4f} CAD (rate: {conversion_rate})")
        return converted_amount
    
    @staticmethod
    def convert_from_cad(amount: float, to_currency: str) -> float:
        """
        Convert an amount from CAD to a given currency.
        
        Args:
            amount: The amount in CAD to convert
            to_currency: The target currency code
            
        Returns:
            The amount converted to the target currency
        """
        if to_currency not in CURRENCY_TO_CAD_RATES:
            logger.warning(f"Unsupported currency: {to_currency}, returning CAD amount")
            return amount
            
        conversion_rate = CURRENCY_TO_CAD_RATES[to_currency]
        converted_amount = amount / conversion_rate
        
        logger.debug(f"Converted C${amount:.4f} CAD to {converted_amount:.4f} {to_currency} (rate: {1/conversion_rate:.4f})")
        return converted_amount
    
    @staticmethod
    def get_currency_symbol(currency_code: str) -> str:
        """Get the symbol for a currency code"""
        return CURRENCY_SYMBOLS.get(currency_code, currency_code)
    
    @staticmethod
    def get_supported_currencies() -> Dict[str, str]:
        """Get all supported currencies with their full names"""
        return SUPPORTED_CURRENCIES.copy()
    
    @staticmethod
    def is_supported_currency(currency_code: str) -> bool:
        """Check if a currency code is supported"""
        return currency_code in CURRENCY_TO_CAD_RATES
    
    @staticmethod
    def update_conversion_rates(new_rates: Dict[str, float]) -> None:
        """
        Update conversion rates (for future API integration)
        
        Args:
            new_rates: Dictionary of currency codes to CAD conversion rates
        """
        global CURRENCY_TO_CAD_RATES
        
        for currency, rate in new_rates.items():
            if currency in CURRENCY_TO_CAD_RATES:
                old_rate = CURRENCY_TO_CAD_RATES[currency]
                CURRENCY_TO_CAD_RATES[currency] = rate
                logger.info(f"Updated {currency} conversion rate: {old_rate} -> {rate}")
            else:
                logger.warning(f"Attempted to update unsupported currency: {currency}")


def apply_currency_conversion_to_listings(listings_df, site_currency_map: Dict[int, str]):
    """
    Apply currency conversion to a DataFrame of card listings.
    
    Args:
        listings_df: DataFrame with card listings (must have 'price' and 'site_id' columns)
        site_currency_map: Mapping of site_id to currency code
        
    Returns:
        DataFrame with prices converted to CAD and original currency/price preserved
    """
    import pandas as pd
    
    if listings_df.empty:
        return listings_df
    
    # Create a copy to avoid modifying the original
    df = listings_df.copy()
    
    # Add original currency and price columns
    df['original_currency'] = df['site_id'].map(site_currency_map).fillna('CAD')
    df['original_price'] = df['price']
    
    # Convert prices to CAD
    converter = CurrencyConverter()
    
    def convert_price(row):
        try:
            return converter.convert_to_cad(row['original_price'], row['original_currency'])
        except Exception as e:
            logger.warning(f"Error converting price {row['original_price']} {row['original_currency']}: {e}")
            return row['original_price']  # Fallback to original price
    
    df['price'] = df.apply(convert_price, axis=1)
    
    # Log conversion summary
    conversions = df.groupby('original_currency').agg({
        'original_price': ['count', 'mean'],
        'price': 'mean'
    }).round(4)
    
    logger.info("Currency conversion summary:")
    for currency in conversions.index:
        count = conversions.loc[currency, ('original_price', 'count')]
        orig_avg = conversions.loc[currency, ('original_price', 'mean')]
        cad_avg = conversions.loc[currency, ('price', 'mean')]
        logger.info(f"  {currency}: {count} items, avg {orig_avg:.2f} -> C${cad_avg:.2f} CAD")
    
    return df