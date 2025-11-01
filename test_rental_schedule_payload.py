#!/usr/bin/env python3
"""
Test script to verify calculate API with rental schedule payload
"""
import json
import sys
from pathlib import Path

# Add lease_application to path
sys.path.insert(0, str(Path(__file__).parent / 'lease_application'))

from app import create_app
from flask import jsonify

# Create app
app = create_app()
app.config['TESTING'] = True

# Payload from the file
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

def test_calculate_with_rental_schedule():
    """Test calculate API with rental schedule payload"""
    with app.test_client() as client:
        # Create a test user session
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'test_user'
        
        # Call calculate API
        response = client.post('/api/calculate_lease', json=payload, content_type='application/json')
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.data.decode('utf-8')}")
            return False
        
        result = response.get_json()
        
        # Extract schedule
        schedule = result.get('schedule', [])
        
        print(f"\nTotal schedule rows: {len(schedule)}")
        print("\nFirst 20 payment dates (with rental > 0):")
        print("-" * 80)
        print(f"{'Date':<15} {'Rental':>12} {'Principal':>12} {'Interest':>12} {'Liability':>15} {'ROU Asset':>15}")
        print("-" * 80)
        
        payment_count = 0
        for row in schedule:
            if row.get('rental_amount', 0) > 0:
                payment_count += 1
                if payment_count <= 20:
                    date_str = str(row.get('date', ''))[:10]
                    rental = row.get('rental_amount', 0)
                    principal = row.get('principal', 0)
                    interest = row.get('interest', 0)
                    liability = row.get('lease_liability', 0)
                    rou = row.get('rou_asset', 0)
                    print(f"{date_str:<15} {rental:>12.2f} {principal:>12.2f} {interest:>12.2f} {liability:>15.2f} {rou:>15.2f}")
        
        print(f"\nTotal payments with rental > 0: {payment_count}")
        
        # Check for specific dates mentioned in expected
        print("\nChecking for critical dates:")
        print("-" * 80)
        
        # Check for Jan 5, 2027 (should NOT exist)
        jan_5_2027 = [r for r in schedule if str(r.get('date', '')) == '2027-01-05' and r.get('rental_amount', 0) > 0]
        if jan_5_2027:
            print("❌ FOUND Jan 5, 2027 payment (should NOT exist):")
            print(json.dumps(jan_5_2027[0], indent=2))
        else:
            print("✅ No Jan 5, 2027 payment (correct)")
        
        # Check for Mar 5, 2027 (should exist)
        mar_5_2027 = [r for r in schedule if str(r.get('date', '')) == '2027-03-05' and r.get('rental_amount', 0) > 0]
        if mar_5_2027:
            print("✅ Found Mar 5, 2027 payment (correct)")
            print(f"   Rental: {mar_5_2027[0].get('rental_amount', 0):.2f}")
        else:
            print("❌ Missing Mar 5, 2027 payment (should exist)")
        
        # Check last payment
        last_payment = None
        for row in reversed(schedule):
            if row.get('rental_amount', 0) > 0:
                last_payment = row
                break
        
        if last_payment:
            last_date = str(last_payment.get('date', ''))[:10]
            print(f"\nLast payment date: {last_date}")
            print(f"Last payment rental: {last_payment.get('rental_amount', 0):.2f}")
            print(f"Expected: 2023-12-05 (Dec 5, 2033)")
            
            if last_date == '2033-12-05':
                print("✅ Last payment date matches expected")
            else:
                print(f"⚠️  Last payment date differs from expected")
        
        # Check payment dates in 2027
        print("\nPayments in 2027:")
        print("-" * 80)
        payments_2027 = [r for r in schedule if str(r.get('date', ''))[:4] == '2027' and r.get('rental_amount', 0) > 0]
        for p in payments_2027[:10]:  # First 10
            date_str = str(p.get('date', ''))[:10]
            rental = p.get('rental_amount', 0)
            print(f"  {date_str}: {rental:,.2f}")
        
        return True

if __name__ == '__main__':
    test_calculate_with_rental_schedule()

