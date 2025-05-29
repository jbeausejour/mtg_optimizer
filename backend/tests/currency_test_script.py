#!/usr/bin/env python3
"""
Test script for currency conversion functionality.

This script tests the currency conversion system to ensure it's working correctly
across different currencies and scenarios.

Usage:
    python test_currency_conversion.py
"""

import sys
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

# Assuming these imports work in your environment
try:
    from app.constants.currency import (
        CurrencyConverter, 
        apply_currency_conversion_to_listings,
        CURRENCY_TO_CAD_RATES,
        SUPPORTED_CURRENCIES
    )
except ImportError:
    print("❌ Error: Could not import currency modules.")
    print("Make sure you're running this from the correct directory and the app is properly set up.")
    sys.exit(1)


class CurrencyTester:
    """Test suite for currency conversion functionality"""
    
    def __init__(self):
        self.converter = CurrencyConverter()
        self.test_results = []
        
    def log_test(self, test_name, passed, message=""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")
        self.test_results.append((test_name, passed, message))
        
    def test_basic_conversions(self):
        """Test basic currency conversions"""
        print("\n🧪 Testing Basic Currency Conversions")
        print("-" * 50)
        
        test_cases = [
            ("CAD", 100.0, 100.0),  # CAD to CAD should be 1:1
            ("USD", 100.0, 135.0),  # USD to CAD
            ("EUR", 100.0, 159.0),  # EUR to CAD  
            ("GBP", 100.0, 169.0),  # GBP to CAD
            ("JPY", 1000.0, 9.0),   # JPY to CAD
        ]
        
        for currency, amount, expected_cad in test_cases:
            try:
                result = self.converter.convert_to_cad(amount, currency)
                expected = float(expected_cad)
                passed = abs(result - expected) < 0.01  # Allow small floating point differences
                
                self.log_test(
                    f"Convert {amount} {currency} to CAD",
                    passed,
                    f"Expected ~C${expected:.2f}, got C${result:.2f}"
                )
            except Exception as e:
                self.log_test(
                    f"Convert {amount} {currency} to CAD", 
                    False, 
                    f"Exception: {str(e)}"
                )
    
    def test_unsupported_currency(self):
        """Test handling of unsupported currencies"""
        print("\n🧪 Testing Unsupported Currency Handling")
        print("-" * 50)
        
        try:
            # Test unsupported currency - should return original amount with warning
            result = self.converter.convert_to_cad(100.0, "XYZ")
            passed = result == 100.0  # Should default to original amount
            
            self.log_test(
                "Handle unsupported currency (XYZ)",
                passed,
                f"Expected 100.0 (fallback), got {result}"
            )
        except Exception as e:
            self.log_test(
                "Handle unsupported currency (XYZ)",
                False,
                f"Exception: {str(e)}"
            )
    
    def test_reverse_conversion(self):
        """Test CAD to other currencies"""
        print("\n🧪 Testing Reverse Conversions (CAD to others)")
        print("-" * 50)
        
        test_cases = [
            ("USD", 135.0, 100.0),  # C$135 CAD should be ~$100 USD
            ("EUR", 159.0, 100.0),  # C$159 CAD should be ~€100 EUR
            ("GBP", 169.0, 100.0),  # C$169 CAD should be ~£100 GBP
        ]
        
        for currency, cad_amount, expected_foreign in test_cases:
            try:
                result = self.converter.convert_from_cad(cad_amount, currency)
                expected = float(expected_foreign)
                passed = abs(result - expected) < 1.0  # Allow for rounding differences
                
                self.log_test(
                    f"Convert C${cad_amount} CAD to {currency}",
                    passed,
                    f"Expected ~{expected:.2f} {currency}, got {result:.2f} {currency}"
                )
            except Exception as e:
                self.log_test(
                    f"Convert C${cad_amount} CAD to {currency}",
                    False,
                    f"Exception: {str(e)}"
                )
    
    def test_dataframe_conversion(self):
        """Test currency conversion on a DataFrame (as used in optimization)"""
        print("\n🧪 Testing DataFrame Currency Conversion")
        print("-" * 50)
        
        try:
            # Create sample data
            sample_data = pd.DataFrame([
                {"site_id": 1, "name": "Lightning Bolt", "price": 2.50, "quantity": 4},
                {"site_id": 2, "name": "Lightning Bolt", "price": 3.25, "quantity": 2}, 
                {"site_id": 3, "name": "Counterspell", "price": 1.85, "quantity": 3},
                {"site_id": 1, "name": "Counterspell", "price": 2.10, "quantity": 1},
            ])
            
            # Site currency mapping
            site_currency_map = {
                1: "CAD",  # Site 1 uses CAD (default)
                2: "USD",  # Site 2 uses USD
                3: "EUR",  # Site 3 uses EUR
            }
            
            # Apply currency conversion
            converted_df = apply_currency_conversion_to_listings(sample_data, site_currency_map)
            
            # Check that conversion was applied
            required_columns = ['original_currency', 'original_price', 'price']
            has_required_cols = all(col in converted_df.columns for col in required_columns)
            
            self.log_test(
                "DataFrame conversion adds required columns",
                has_required_cols,
                f"Required: {required_columns}, Found: {list(converted_df.columns)}"
            )
            
            if has_required_cols:
                # Check specific conversions
                cad_rows = converted_df[converted_df['original_currency'] == 'CAD']
                usd_rows = converted_df[converted_df['original_currency'] == 'USD'] 
                eur_rows = converted_df[converted_df['original_currency'] == 'EUR']
                
                # USD prices should be converted to higher CAD values
                if not usd_rows.empty:
                    usd_converted = all(
                        row['price'] > row['original_price']
                        for _, row in usd_rows.iterrows()
                    )
                    self.log_test("USD prices converted to higher CAD values", usd_converted)
                
                # CAD prices should be unchanged after conversion to CAD
                cad_unchanged = all(
                    abs(row['price'] - row['original_price']) < 0.01 
                    for _, row in cad_rows.iterrows()
                )
                self.log_test("CAD prices unchanged after conversion", cad_unchanged)
                
                # EUR prices should be converted to higher CAD values (multiplied by ~1.59)
                if not eur_rows.empty:
                    eur_converted = all(
                        row['price'] > row['original_price']
                        for _, row in eur_rows.iterrows()
                    )
                    self.log_test("EUR prices converted to higher CAD values", eur_converted)
                
                # Print sample of converted data
                print("\n📊 Sample Conversion Results:")
                for _, row in converted_df.iterrows():
                    symbol = self.converter.get_currency_symbol(row['original_currency'])
                    print(f"   {row['name']}: {symbol}{row['original_price']:.2f} {row['original_currency']} → C${row['price']:.2f} CAD")
                    
        except Exception as e:
            self.log_test(
                "DataFrame currency conversion",
                False,
                f"Exception: {str(e)}"
            )
    
    def test_currency_symbols(self):
        """Test currency symbol retrieval"""
        print("\n🧪 Testing Currency Symbols")
        print("-" * 50)
        
        expected_symbols = {
            'CAD': 'C
        
        for currency, expected_symbol in expected_symbols.items():
            try:
                result = self.converter.get_currency_symbol(currency)
                passed = result == expected_symbol
                
                self.log_test(
                    f"Get symbol for {currency}",
                    passed,
                    f"Expected '{expected_symbol}', got '{result}'"
                )
            except Exception as e:
                self.log_test(
                    f"Get symbol for {currency}",
                    False,
                    f"Exception: {str(e)}"
                )
    
    def test_supported_currencies(self):
        """Test supported currency validation"""
        print("\n🧪 Testing Supported Currency Validation")
        print("-" * 50)
        
        # Test supported currencies
        supported_tests = ['CAD', 'USD', 'EUR', 'GBP', 'JPY']
        for currency in supported_tests:
            try:
                is_supported = self.converter.is_supported_currency(currency)
                self.log_test(f"{currency} is supported", is_supported)
            except Exception as e:
                self.log_test(f"{currency} is supported", False, f"Exception: {str(e)}")
        
        # Test unsupported currencies
        unsupported_tests = ['XYZ', 'ABC', 'INVALID']
        for currency in unsupported_tests:
            try:
                is_supported = self.converter.is_supported_currency(currency)
                self.log_test(f"{currency} is unsupported", not is_supported)
            except Exception as e:
                self.log_test(f"{currency} is unsupported", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all currency conversion tests"""
        print("🚀 Starting Currency Conversion Tests")
        print("=" * 60)
        
        self.test_basic_conversions()
        self.test_unsupported_currency()
        self.test_reverse_conversion()
        self.test_dataframe_conversion()
        self.test_currency_symbols()
        self.test_supported_currencies()
        
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for test_name, passed, message in self.test_results:
                if not passed:
                    print(f"   • {test_name}: {message}")
        
        print("\n" + "=" * 60)
        return failed_tests == 0


def main():
    """Main test runner"""
    print("💰 MTG Optimization Currency Conversion Test Suite")
    print("🔧 Testing currency conversion functionality (CAD-based)...")
    print()
    
    tester = CurrencyTester()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All tests passed! Currency conversion is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the currency conversion implementation.")
        sys.exit(1)


if __name__ == "__main__":
    main(),
            'USD': '
        
        for currency, expected_symbol in expected_symbols.items():
            try:
                result = self.converter.get_currency_symbol(currency)
                passed = result == expected_symbol
                
                self.log_test(
                    f"Get symbol for {currency}",
                    passed,
                    f"Expected '{expected_symbol}', got '{result}'"
                )
            except Exception as e:
                self.log_test(
                    f"Get symbol for {currency}",
                    False,
                    f"Exception: {str(e)}"
                )
    
    def test_supported_currencies(self):
        """Test supported currency validation"""
        print("\n🧪 Testing Supported Currency Validation")
        print("-" * 50)
        
        # Test supported currencies
        supported_tests = ['USD', 'CAD', 'EUR', 'GBP', 'JPY']
        for currency in supported_tests:
            try:
                is_supported = self.converter.is_supported_currency(currency)
                self.log_test(f"{currency} is supported", is_supported)
            except Exception as e:
                self.log_test(f"{currency} is supported", False, f"Exception: {str(e)}")
        
        # Test unsupported currencies
        unsupported_tests = ['XYZ', 'ABC', 'INVALID']
        for currency in unsupported_tests:
            try:
                is_supported = self.converter.is_supported_currency(currency)
                self.log_test(f"{currency} is unsupported", not is_supported)
            except Exception as e:
                self.log_test(f"{currency} is unsupported", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all currency conversion tests"""
        print("🚀 Starting Currency Conversion Tests")
        print("=" * 60)
        
        self.test_basic_conversions()
        self.test_unsupported_currency()
        self.test_reverse_conversion()
        self.test_dataframe_conversion()
        self.test_currency_symbols()
        self.test_supported_currencies()
        
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for test_name, passed, message in self.test_results:
                if not passed:
                    print(f"   • {test_name}: {message}")
        
        print("\n" + "=" * 60)
        return failed_tests == 0


def main():
    """Main test runner"""
    print("💰 MTG Optimization Currency Conversion Test Suite")
    print("🔧 Testing currency conversion functionality...")
    print()
    
    tester = CurrencyTester()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All tests passed! Currency conversion is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the currency conversion implementation.")
        sys.exit(1)


if __name__ == "__main__":
    main(), 
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
        }
        
        for currency, expected_symbol in expected_symbols.items():
            try:
                result = self.converter.get_currency_symbol(currency)
                passed = result == expected_symbol
                
                self.log_test(
                    f"Get symbol for {currency}",
                    passed,
                    f"Expected '{expected_symbol}', got '{result}'"
                )
            except Exception as e:
                self.log_test(
                    f"Get symbol for {currency}",
                    False,
                    f"Exception: {str(e)}"
                )
    
    def test_supported_currencies(self):
        """Test supported currency validation"""
        print("\n🧪 Testing Supported Currency Validation")
        print("-" * 50)
        
        # Test supported currencies
        supported_tests = ['USD', 'CAD', 'EUR', 'GBP', 'JPY']
        for currency in supported_tests:
            try:
                is_supported = self.converter.is_supported_currency(currency)
                self.log_test(f"{currency} is supported", is_supported)
            except Exception as e:
                self.log_test(f"{currency} is supported", False, f"Exception: {str(e)}")
        
        # Test unsupported currencies
        unsupported_tests = ['XYZ', 'ABC', 'INVALID']
        for currency in unsupported_tests:
            try:
                is_supported = self.converter.is_supported_currency(currency)
                self.log_test(f"{currency} is unsupported", not is_supported)
            except Exception as e:
                self.log_test(f"{currency} is unsupported", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all currency conversion tests"""
        print("🚀 Starting Currency Conversion Tests")
        print("=" * 60)
        
        self.test_basic_conversions()
        self.test_unsupported_currency()
        self.test_reverse_conversion()
        self.test_dataframe_conversion()
        self.test_currency_symbols()
        self.test_supported_currencies()
        
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for test_name, passed, message in self.test_results:
                if not passed:
                    print(f"   • {test_name}: {message}")
        
        print("\n" + "=" * 60)
        return failed_tests == 0


def main():
    """Main test runner"""
    print("💰 MTG Optimization Currency Conversion Test Suite")
    print("🔧 Testing currency conversion functionality...")
    print()
    
    tester = CurrencyTester()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All tests passed! Currency conversion is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the currency conversion implementation.")
        sys.exit(1)


if __name__ == "__main__":
    main()