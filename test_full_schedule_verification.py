#!/usr/bin/env python3
"""
Test script to verify full schedule matches expected
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add lease_application to path
sys.path.insert(0, str(Path(__file__).parent / 'lease_application'))

from app import create_app

# Create app
app = create_app()
app.config['TESTING'] = True

# Payload
payload = {
    "auto_id": 3,
    "description": "Untitled Lease",
    "asset_class": "Building",
    "asset_id_code": "",
    "accrual_day": 1,
    "agreement_date": None,
    "aro": 0,
    "aro_table": 0,
    "bargain_purchase": "No",
    "borrowing_rate": 10,
    "compound_months": 3,
    "cost_centre": "",
    "counterparty": "QWE",
    "currency": "INR",
    "date_modified": None,
    "day_of_month": "5",
    "end_date": "2033-12-31",
    "esc_freq_months": None,
    "escalation_percent": 0,
    "escalation_start_date": None,
    "finance_lease": "No",
    "first_payment_date": "2024-03-01",
    "frequency_months": 3,
    "from_date": "2024-01-01",
    "fv_of_rou": 0,
    "index_rate_table": "",
    "initial_direct_expenditure": 0,
    "lease_incentive": 0,
    "lease_start_date": "2024-01-01",
    "manual_adj": "No",
    "practical_expedient": "No",
    "purchase_option_price": 0,
    "rental_1": 0,
    "rental_2": 0,
    "rental_schedule": [
        {"amount": 50000, "end_date": "2026-12-31", "rental_count": 36, "rental_number": 1, "start_date": "2024-01-01"},
        {"amount": 60000, "end_date": "2029-12-31", "rental_count": 36, "rental_number": 2, "start_date": "2027-01-01"},
        {"amount": 70000, "end_date": "2033-12-31", "rental_count": 48, "rental_number": 3, "start_date": "2030-01-01"}
    ],
    "security_deposit": 0,
    "security_discount": 0,
    "short_term_ifrs": "No",
    "sublease": "No",
    "sublease_rou": 0,
    "tenure": 120,
    "termination_date": None,
    "termination_penalty": 0,
    "title_transfer": "No",
    "to_date": "2026-12-31",
    "transition_date": None,
    "transition_option": "",
    "useful_life_end_date": None
}

# Expected key dates and amounts from the expected schedule
expected_checkpoints = [
    ("2024-03-01", 50000),  # First payment (Entry 0)
    ("2026-12-05", 50000),  # Last payment of Entry 0
    ("2027-03-05", 60000),  # First payment of Entry 1 (should NOT be Jan 5)
    ("2029-12-05", 60000),  # Last payment of Entry 1
    ("2030-03-05", 70000),  # First payment of Entry 2 (continues pattern from Dec 5, 2029 + 3 months)
    ("2033-12-05", 70000),  # Last payment (should be Dec 5, 2033, not Oct 5)
]

def test_full_schedule():
    """Test full schedule matches expected"""
    with app.test_client() as client:
        # Create a test user session
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'test_user'
        
        # Call calculate API
        response = client.post('/api/calculate_lease', json=payload, content_type='application/json')
        
        if response.status_code != 200:
            print(f"Error: {response.data.decode('utf-8')}")
            return False
        
        result = response.get_json()
        schedule = result.get('schedule', [])
        
        print("=" * 80)
        print("VERIFICATION OF KEY DATES")
        print("=" * 80)
        
        all_passed = True
        
        # Build a lookup map by date
        schedule_map = {}
        for row in schedule:
            date_str = str(row.get('date', ''))[:10]
            if date_str:
                schedule_map[date_str] = row
        
        # Check each expected checkpoint
        for expected_date, expected_amount in expected_checkpoints:
            if expected_date in schedule_map:
                actual_row = schedule_map[expected_date]
                actual_amount = actual_row.get('rental_amount', 0)
                
                if abs(actual_amount - expected_amount) < 0.01:
                    print(f"✅ {expected_date}: Expected {expected_amount:,.2f}, Got {actual_amount:,.2f}")
                else:
                    print(f"❌ {expected_date}: Expected {expected_amount:,.2f}, Got {actual_amount:,.2f}")
                    all_passed = False
            else:
                print(f"❌ {expected_date}: DATE NOT FOUND in schedule")
                all_passed = False
        
        # Check that Jan 5, 2027 does NOT exist
        if "2027-01-05" in schedule_map:
            jan5_row = schedule_map["2027-01-05"]
            if jan5_row.get('rental_amount', 0) > 0:
                print(f"❌ 2027-01-05: Should NOT exist, but found with rental: {jan5_row.get('rental_amount', 0):,.2f}")
                all_passed = False
            else:
                print(f"✅ 2027-01-05: Exists but has no rental (OK - might be a non-payment row)")
        else:
            print(f"✅ 2027-01-05: Does NOT exist (correct)")
        
        print("\n" + "=" * 80)
        print("PAYMENT SEQUENCE VERIFICATION")
        print("=" * 80)
        
        # Get all payment dates (with rental > 0) sorted by date
        payment_dates = []
        for row in schedule:
            if row.get('rental_amount', 0) > 0:
                date_str = str(row.get('date', ''))[:10]
                rental = row.get('rental_amount', 0)
                payment_dates.append((date_str, rental))
        
        payment_dates.sort()
        
        # Check transitions between rental entries
        print("\nTransition checks:")
        
        # Entry 0 -> Entry 1 transition (should be Dec 5, 2026 -> Mar 5, 2027)
        dec_5_2026 = next((d, a) for d, a in payment_dates if d == "2026-12-05")
        mar_5_2027 = next((d, a) for d, a in payment_dates if d == "2027-03-05")
        
        if dec_5_2026 and mar_5_2027:
            print(f"✅ Entry 0->1: {dec_5_2026[0]} ({dec_5_2026[1]:,.0f}) -> {mar_5_2027[0]} ({mar_5_2027[1]:,.0f})")
        else:
            print(f"❌ Entry 0->1 transition missing")
            all_passed = False
        
        # Check for payments in 2027 - should be quarterly starting from Mar 5
        payments_2027 = [(d, a) for d, a in payment_dates if d[:4] == "2027"]
        print(f"\nPayments in 2027 (should be quarterly starting Mar 5):")
        for d, a in payments_2027:
            print(f"  {d}: {a:,.2f}")
        
        if len(payments_2027) == 4 and all(d.endswith("-05") for d, _ in payments_2027):
            print("✅ All 2027 payments are on the 5th and quarterly")
        else:
            print("❌ 2027 payment pattern incorrect")
            all_passed = False
        
        # Check last payment
        last_date, last_amount = payment_dates[-1]
        print(f"\nLast payment: {last_date}, Amount: {last_amount:,.2f}")
        print(f"Expected: 2033-12-05, Amount: 70,000.00")
        
        if last_date == "2033-12-05" and abs(last_amount - 70000) < 0.01:
            print("✅ Last payment matches expected")
        else:
            print("❌ Last payment does NOT match expected")
            all_passed = False
        
        print("\n" + "=" * 80)
        if all_passed:
            print("✅ ALL CHECKS PASSED")
        else:
            print("❌ SOME CHECKS FAILED")
        print("=" * 80)
        
        return all_passed

if __name__ == '__main__':
    test_full_schedule()

