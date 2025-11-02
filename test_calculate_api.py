#!/usr/bin/env python3
"""
Test suite for the calculate_lease API endpoint
Tests with the provided payload and validates the expected response structure
"""

import sys
import os
import json
from pathlib import Path

# Add lease_application to path
sys.path.insert(0, str(Path(__file__).parent / 'lease_application'))

from lease_application.app import create_app
import lease_application.database as database


class TestCalculateAPI:
    """Test suite for calculate_lease endpoint"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        # Create test app with default config
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['SECRET_KEY'] = 'test-secret-key'
        cls.client = cls.app.test_client()
        
        # Initialize test database
        database.init_database()
        
        # Create a test user and login
        cls.test_username = 'test_user'
        cls.test_password = 'test_password'
        
        # Create test user
        try:
            # Check if user exists and create if needed
            with database.get_db_connection() as conn:
                cursor = conn.execute('SELECT user_id FROM users WHERE username = ?', (cls.test_username,))
                user = cursor.fetchone()
                
                if not user:
                    # Create user using database function
                    cls.user_id = database.create_user(cls.test_username, cls.test_password)
                else:
                    cls.user_id = user[0]
        except Exception as e:
            # If user already exists, get the user_id
            try:
                with database.get_db_connection() as conn:
                    cursor = conn.execute('SELECT user_id FROM users WHERE username = ?', (cls.test_username,))
                    user = cursor.fetchone()
                    cls.user_id = user[0] if user else database.create_user(cls.test_username, cls.test_password)
            except:
                cls.user_id = 1  # Fallback
        
        # Login to get session
        with cls.client.session_transaction() as sess:
            sess['user_id'] = cls.user_id
            sess['username'] = cls.test_username
    
    def get_test_payload(self):
        """Return the test payload"""
        return {
            "auto_id": 2,
            "description": "Untitled Lease",
            "asset_class": "Land",
            "asset_id_code": "",
            "accrual_day": 1,
            "agreement_date": "2025-11-01",
            "aro": 0,
            "aro_table": 0,
            "auto_rentals": "Yes",
            "bargain_purchase": "No",
            "borrowing_rate": 9,
            "compound_months": 1,
            "cost_centre": "",
            "counterparty": "Test",
            "currency": "USD",
            "date_modified": "2025-11-01",
            "day_of_month": "1",
            "end_date": "2029-12-31",
            "esc_freq_months": 12,
            "escalation_percent": 10,
            "escalation_start_date": "2025-03-01",
            "finance_lease": "No",
            "first_payment_date": "2025-03-01",
            "frequency_months": 1,
            "from_date": "2025-01-01",
            "fv_of_rou": 0,
            "index_rate_table": "",
            "initial_direct_expenditure": 0,
            "lease_incentive": 0,
            "lease_start_date": "2025-01-01",
            "manual_adj": "No",
            "practical_expedient": "No",
            "purchase_option_price": 0,
            "rental_1": 50000,
            "rental_2": 0,
            "security_deposit": 0,
            "security_discount": 0,
            "short_term_ifrs": "No",
            "sublease": "No",
            "sublease_rou": 0,
            "tenure": 0,
            "termination_date": "2025-11-01",
            "termination_penalty": 0,
            "title_transfer": "No",
            "to_date": "2025-12-31",
            "transition_date": "2025-11-01",
            "transition_option": "",
            "useful_life_end_date": "2025-11-01"
        }
    
    def get_expected_response_keys(self):
        """Return expected top-level keys in response"""
        return ['date_range', 'journal_entries', 'lease_result', 'schedule']
    
    def test_calculate_lease_endpoint_exists(self):
        """Test that the endpoint exists and is accessible"""
        payload = self.get_test_payload()
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404, "Endpoint /api/calculate_lease does not exist"
    
    def test_calculate_lease_response_structure(self):
        """Test that the response has the expected structure"""
        payload = self.get_test_payload()
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data.decode()}"
        
        data = json.loads(response.data)
        
        # Check top-level keys
        expected_keys = self.get_expected_response_keys()
        for key in expected_keys:
            assert key in data, f"Missing key '{key}' in response"
        
        # Check date_range structure
        assert 'date_range' in data
        assert 'filtered' in data['date_range']
        assert 'from_date' in data['date_range']
        assert 'to_date' in data['date_range']
        
        # Check journal_entries is a list
        assert isinstance(data['journal_entries'], list), "journal_entries should be a list"
        
        # Check lease_result structure
        assert 'lease_result' in data
        lease_result = data['lease_result']
        assert 'borrowing_rate' in lease_result
        assert 'opening_lease_liability' in lease_result or 'opening_liability' in lease_result or 'opening_lease_liability' in lease_result
        
        # Check schedule is a list
        assert isinstance(data['schedule'], list), "schedule should be a list"
        assert len(data['schedule']) > 0, "schedule should not be empty"
    
    def test_calculate_lease_borrowing_rate(self):
        """Test that borrowing_rate is correctly extracted from payload"""
        payload = self.get_test_payload()
        expected_rate = 9.0
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        
        # Verify borrowing_rate in lease_result
        assert 'lease_result' in data
        assert 'borrowing_rate' in data['lease_result']
        assert data['lease_result']['borrowing_rate'] == expected_rate, \
            f"Expected borrowing_rate to be {expected_rate}, got {data['lease_result']['borrowing_rate']}"
    
    def test_calculate_lease_date_range(self):
        """Test that date_range matches payload dates"""
        payload = self.get_test_payload()
        expected_from = "2025-01-01"
        expected_to = "2025-12-31"
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        
        # Verify date_range
        assert data['date_range']['from_date'] == expected_from
        assert data['date_range']['to_date'] == expected_to
        assert data['date_range']['filtered'] is True
    
    def test_calculate_lease_journal_entries_structure(self):
        """Test that journal_entries have the expected structure"""
        payload = self.get_test_payload()
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        journal_entries = data['journal_entries']
        
        # Should have at least some journal entries
        assert len(journal_entries) > 0, "Should have journal entries"
        
        # Check structure of first journal entry
        if len(journal_entries) > 0:
            entry = journal_entries[0]
            expected_entry_keys = [
                'account_code', 'account_name', 'bs_pl', 'ifrs_adjustment',
                'incremental_adjustment', 'opening_balance', 'previous_period',
                'result_period', 'usgaap_entry'
            ]
            for key in expected_entry_keys:
                assert key in entry, f"Journal entry missing key '{key}'"
    
    def test_calculate_lease_schedule_structure(self):
        """Test that schedule entries have the expected structure"""
        payload = self.get_test_payload()
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        schedule = data['schedule']
        
        assert len(schedule) > 0, "Schedule should not be empty"
        
        # Check structure of first schedule entry
        if len(schedule) > 0:
            entry = schedule[0]
            expected_schedule_keys = [
                'date', 'rental_amount', 'pv_factor', 'interest',
                'lease_liability', 'pv_of_rent', 'rou_asset', 'depreciation'
            ]
            for key in expected_schedule_keys:
                assert key in entry, f"Schedule entry missing key '{key}'"
            
            # Check opening row (first entry)
            assert 'lease_liability' in entry
            assert 'rou_asset' in entry
            # Opening liability and ROU should be equal (initial calculation)
            assert entry['lease_liability'] == entry['rou_asset'], \
                "Opening lease liability should equal opening ROU asset"
    
    def test_calculate_lease_expected_values(self):
        """Test that key expected values match the provided expected response"""
        payload = self.get_test_payload()
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        
        # Check specific expected values from the provided response
        lease_result = data['lease_result']
        
        # Verify borrowing_rate is 9 (not defaulting to 8)
        assert lease_result['borrowing_rate'] == 9.0, \
            f"Expected borrowing_rate to be 9.0, got {lease_result.get('borrowing_rate')}"
        
        # Verify opening liability and ROU are approximately correct
        # (based on expected response: ~2776911.787866688)
        opening_liability = lease_result.get('opening_lease_liability') or \
                           lease_result.get('opening_liability') or \
                           (data['schedule'][0]['lease_liability'] if data['schedule'] else None)
        
        assert opening_liability is not None, "Opening liability should be present"
        assert abs(opening_liability - 2776911.787866688) < 100, \
            f"Opening liability should be approximately 2776911.79, got {opening_liability}"
        
        # Verify opening ROU asset
        opening_rou = lease_result.get('opening_rou_asset') or \
                      (data['schedule'][0]['rou_asset'] if data['schedule'] else None)
        
        assert opening_rou is not None, "Opening ROU asset should be present"
        assert abs(opening_rou - 2776911.787866688) < 100, \
            f"Opening ROU should be approximately 2776911.79, got {opening_rou}"
        
        # Verify closing values exist
        assert 'closing_lease_liability_current' in lease_result
        assert 'closing_lease_liability_non_current' in lease_result
        assert 'closing_rou_asset' in lease_result
        
        # Verify closing ROU asset (expected: ~2223354.3449403597)
        closing_rou = lease_result['closing_rou_asset']
        assert abs(closing_rou - 2223354.3449403597) < 100, \
            f"Closing ROU should be approximately 2223354.34, got {closing_rou}"
    
    def test_calculate_lease_missing_borrowing_rate_raises_error(self):
        """Test that missing borrowing_rate raises an error (not defaulting to 8)"""
        payload = self.get_test_payload()
        # Remove borrowing_rate
        del payload['borrowing_rate']
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        # Should return an error (not 200)
        assert response.status_code != 200, \
            "Missing borrowing_rate should raise an error, not default to 8"
        
        # Should have error message
        data = json.loads(response.data)
        assert 'error' in data, "Error response should contain 'error' key"
        assert 'borrowing_rate' in data['error'].lower(), \
            "Error message should mention borrowing_rate"
    
    def test_calculate_lease_with_ibr_field(self):
        """Test that borrowing_rate can be provided as 'ibr' field"""
        payload = self.get_test_payload()
        # Remove borrowing_rate and add ibr
        del payload['borrowing_rate']
        payload['ibr'] = 9
        
        response = self.client.post(
            '/api/calculate_lease',
            json=payload,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['lease_result']['borrowing_rate'] == 9.0, \
            "Should extract borrowing_rate from 'ibr' field"


def run_tests():
    """Run all tests"""
    import pytest
    pytest.main([__file__, '-v', '--tb=short'])


if __name__ == '__main__':
    # Run tests directly if pytest not available
    try:
        import pytest
        pytest.main([__file__, '-v', '--tb=short'])
    except ImportError:
        print("pytest not available. Running tests manually...")
        test_suite = TestCalculateAPI()
        test_suite.setup_class()
        
        print("\n" + "="*80)
        print("Running Calculate API Tests")
        print("="*80)
        
        test_methods = [method for method in dir(test_suite) 
                        if method.startswith('test_') 
                        and callable(getattr(test_suite, method))]
        
        passed = 0
        failed = 0
        
        for method_name in test_methods:
            try:
                print(f"\nRunning {method_name}...")
                method = getattr(test_suite, method_name)
                method()
                print(f"✓ {method_name} PASSED")
                passed += 1
            except AssertionError as e:
                print(f"✗ {method_name} FAILED: {e}")
                failed += 1
            except Exception as e:
                print(f"✗ {method_name} ERROR: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        print("\n" + "="*80)
        print(f"Tests: {passed} passed, {failed} failed")
        print("="*80)
        
        sys.exit(0 if failed == 0 else 1)

