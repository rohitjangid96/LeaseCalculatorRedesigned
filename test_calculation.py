#!/usr/bin/env python3
"""
Test script to validate lease calculations
Reads payload from file, calls calculation endpoint, and compares with expected results
"""

import sys
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add the lease_application directory to the path
sys.path.insert(0, '/Users/rohitjangid/Downloads/Lease_Redesign/lease_application')

from lease_accounting.core.models import LeaseData
from lease_accounting.schedule.generator_vba_complete import generate_complete_schedule
from lease_accounting.core.processor import LeaseProcessor, ProcessingFilters


def parse_indian_number(num_str: str) -> float:
    """Parse Indian number format: 27,76,912 = 2776912"""
    if not num_str or num_str.strip() == '-' or num_str.strip() == '':
        return 0.0
    # Remove commas and convert
    cleaned = num_str.replace(',', '').strip()
    try:
        return float(cleaned)
    except:
        return 0.0


def parse_dollar_amount(amt_str: str) -> float:
    """Parse dollar amount: $2,848,297.90 = 2848297.90"""
    if not amt_str or amt_str.strip() == '-' or amt_str.strip() == '':
        return 0.0
    cleaned = amt_str.replace('$', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except:
        return 0.0


def parse_payload_file(filepath: str) -> Tuple[Dict, List[Dict], List[Dict]]:
    """Parse the payload file to extract payload, actual, and expected responses"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    payload_dict = {}
    in_payload = False
    
    # Parse payload section - format is key\n:\nvalue\n (each on separate line)
    i = 0
    while i < len(lines):
        line_stripped = lines[i].strip()
        if 'Payload :' in line_stripped or 'Payload:' in line_stripped:
            in_payload = True
            i += 1
            # Skip the next line which is the opening brace
            if i < len(lines) and '{' in lines[i]:
                i += 1
            continue
        if in_payload:
            if line_stripped == '------':
                break
            # Format: key (line), : (next line), value (line after)
            # Check if this line looks like a key (no colon, not empty, not a value with quotes)
            if line_stripped and ':' not in line_stripped and not line_stripped.startswith('"') and line_stripped != '{':
                key = line_stripped
                # Next line should be ':'
                if i + 1 < len(lines) and lines[i + 1].strip() == ':':
                    # Line after that should be the value
                    if i + 2 < len(lines):
                        value = lines[i + 2].strip().strip('"')
                        payload_dict[key] = value
                        i += 2  # Skip the ':' and value lines
        i += 1
    
    # Extract actual response section
    actual_lines = content.split('Actual Response :')[1].split('expected Response')[0] if 'Actual Response :' in content else ""
    actual_rows = []
    
    for line in actual_lines.split('\n'):
        if line.strip() and not line.strip().startswith('📅') and '\t' in line:
            parts = line.split('\t')
            if len(parts) > 10:
                actual_rows.append(parts)
    
    # Extract expected response section
    expected_section = ""
    if 'expected Response:' in content:
        expected_section = content.split('expected Response:')[1]
    elif 'expected Response' in content:
        expected_section = content.split('expected Response')[1]
    
    expected_rows = []
    
    # Expected format is multi-line: Date on one line, then fields on subsequent lines
    # Format: Date\n(empty)\n(empty)\nPV_factor\nInterest\nLiability\nPV_of_rent\nROU\nDepreciation
    lines = expected_section.split('\n')
    i = 0
    while i < len(lines):
        line_stripped = lines[i].strip()
        # Check if this line is a date (contains month-year like Jan-25, Feb-25, etc.)
        if line_stripped and re.match(r'^\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}$', line_stripped):
            date_str = line_stripped
            # The next few lines contain the fields:
            # Line i+1: empty (Rent)
            # Line i+2: empty (Rent)
            # Line i+3: PV factor
            # Line i+4: Interest
            # Line i+5: Liability
            # Line i+6: PV of rent
            # Line i+7: ROU
            # Line i+8: Depreciation
            
            row = [date_str]
            # Try to extract fields (they might be on different lines)
            for offset in range(1, 9):
                if i + offset < len(lines):
                    field_line = lines[i + offset].strip().replace('\t', '')
                    if field_line and field_line != '-':
                        row.append(field_line)
                    else:
                        row.append('')  # Empty field
            expected_rows.append(row)
            # Skip ahead - each data row takes about 9 lines
            i += 8
        else:
            i += 1
    
    return payload_dict, actual_rows, expected_rows


def create_lease_data_from_payload(payload: Dict) -> LeaseData:
    """Create LeaseData object from payload dictionary"""
    
    def parse_date(date_str: Optional[str]):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return None
    
    return LeaseData(
        auto_id=int(payload.get('auto_id', 2)),
        description=payload.get('description', 'Untitled Lease'),
        asset_class=payload.get('asset_class', 'Land'),
        asset_id_code=payload.get('asset_id_code', ''),
        
        # Dates
        lease_start_date=parse_date(payload.get('lease_start_date')),
        first_payment_date=parse_date(payload.get('first_payment_date')),
        end_date=parse_date(payload.get('end_date')),
        agreement_date=parse_date(payload.get('agreement_date')),
        termination_date=parse_date(payload.get('termination_date')),
        
        # Financial Terms
        tenure=float(payload.get('tenure', 0) or 0),
        frequency_months=int(payload.get('frequency_months', 1) or 1),
        day_of_month=str(payload.get('day_of_month', '1')),
        
        # Payments
        auto_rentals=payload.get('auto_rentals', 'Yes'),
        manual_adj=payload.get('manual_adj', 'No'),
        rental_1=float(payload.get('rental_1', 50000) or 50000),
        rental_2=float(payload.get('rental_2', 0) or 0),
        
        # Escalation
        escalation_start=parse_date(payload.get('escalation_start_date')),
        escalation_percent=float(payload.get('escalation_percent', 10) or 10),
        esc_freq_months=int(payload.get('esc_freq_months', 12) or 12),
        accrual_day=int(payload.get('accrual_day', 1) or 1),
        index_rate_table=payload.get('index_rate_table', ''),
        
        # Rates
        borrowing_rate=float(payload.get('borrowing_rate', 8) or 8),
        compound_months=int(payload.get('compound_months', 1)) if payload.get('compound_months') else None,
        fv_of_rou=float(payload.get('fv_of_rou', 0) or 0),
        
        # Residual
        bargain_purchase=payload.get('bargain_purchase', 'No'),
        purchase_option_price=float(payload.get('purchase_option_price', 0) or 0),
        title_transfer=payload.get('title_transfer', 'No'),
        useful_life=parse_date(payload.get('useful_life_end_date')),
        
        # Entity
        currency=payload.get('currency', 'USD'),
        cost_centre=payload.get('cost_centre', ''),
        counterparty=payload.get('counterparty', 'Test'),
        
        # Security
        security_deposit=float(payload.get('security_deposit', 0) or 0),
        security_discount=float(payload.get('security_discount', 0) or 0),
        increase_security_1=0,
        increase_security_2=0,
        increase_security_3=0,
        increase_security_4=0,
        security_dates=[None, None, None, None],
        
        # ARO
        aro=float(payload.get('aro', 0) or 0),
        aro_table=int(payload.get('aro_table', 0) or 0),
        aro_revisions=[0, 0, 0, 0],
        aro_dates=[None, None, None, None],
        
        # Initial Costs
        initial_direct_expenditure=float(payload.get('initial_direct_expenditure', 0) or 0),
        lease_incentive=float(payload.get('lease_incentive', 0) or 0),
        
        # Modifications
        modifies_this_id=None,
        modified_by_this_id=None,
        date_modified=parse_date(payload.get('date_modified')),
        
        # Sublease
        sublease=payload.get('sublease', 'No'),
        sublease_rou=float(payload.get('sublease_rou', 0) or 0),
        
        # Other
        profit_center='',
        group_entity_name='',
        short_term_lease_ifrs=payload.get('short_term_ifrs', 'No'),
        short_term_lease_usgaap=payload.get('short_term_usgaap', 'No'),
        finance_lease_usgaap=payload.get('finance_lease', 'No'),
        practical_expedient=payload.get('practical_expedient', 'No'),
        prepaid_accrual=0.0,
        transition_date=parse_date(payload.get('transition_date')),
        transition_option=payload.get('transition_option', ''),
        gaap_standard='IFRS',
    )


def compare_results(actual_schedule: List, expected_rows: List[Dict], tolerance: float = 1.0):
    """Compare actual calculation results with expected values"""
    
    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)
    
    differences = []
    
    # Compare opening liability (first row)
    if actual_schedule and len(actual_schedule) > 0:
        first_row = actual_schedule[0]
        actual_opening_liab = first_row.lease_liability if hasattr(first_row, 'lease_liability') else 0.0
        actual_opening_rou = first_row.rou_asset if hasattr(first_row, 'rou_asset') else 0.0
        
        # Find expected opening row (look for 1-Jan-25 or first Jan-25 that's not 31-Jan-25)
        expected_opening = None
        for row in expected_rows:
            if len(row) > 4 and row[0]:
                date_str = row[0].strip()
                # Check if it's the opening date (1-Jan-25 or first date)
                if '1-Jan-25' in date_str or ('Jan-25' in date_str and '31' not in date_str and '28' not in date_str):
                    expected_opening = row
                    break
        
        if expected_opening:
            exp_liab_str = expected_opening[5] if len(expected_opening) > 5 else '0'  # Liability at index 5
            exp_rou_str = expected_opening[7] if len(expected_opening) > 7 else '0'  # ROU at index 7
            expected_liab = parse_indian_number(exp_liab_str)
            expected_rou = parse_indian_number(exp_rou_str)
            
            liab_diff = actual_opening_liab - expected_liab
            rou_diff = actual_opening_rou - expected_rou
            
            print(f"\nOpening Liability:")
            print(f"  Expected: {expected_liab:,.2f}")
            print(f"  Actual:   {actual_opening_liab:,.2f}")
            print(f"  Difference: {liab_diff:,.2f} ({abs(liab_diff/expected_liab*100) if expected_liab != 0 else 0:.2f}%)")
            
            if abs(liab_diff) > tolerance:
                differences.append(('Opening Liability', expected_liab, actual_opening_liab, liab_diff))
            
            print(f"\nOpening ROU Asset:")
            print(f"  Expected: {expected_rou:,.2f}")
            print(f"  Actual:   {actual_opening_rou:,.2f}")
            print(f"  Difference: {rou_diff:,.2f} ({abs(rou_diff/expected_rou*100) if expected_rou != 0 else 0:.2f}%)")
            
            if abs(rou_diff) > tolerance:
                differences.append(('Opening ROU', expected_rou, actual_opening_rou, rou_diff))
    
    # Compare a few key rows
    print("\n" + "-"*80)
    print("Key Row Comparisons (first 5 data rows):")
    print("-"*80)
    
    for i, row in enumerate(actual_schedule[:6]):
        if i == 0:
            continue  # Skip opening row
        
        if i >= len(expected_rows):
            break
        
        # Find matching expected row by date
        actual_date = row.date if hasattr(row, 'date') else None
        if not actual_date:
            continue
        
        # Try to find matching expected row
        for exp_row in expected_rows:
            if len(exp_row) > 0 and actual_date.strftime('%d-%b-%y').replace('0', '') in exp_row[0]:
                # Compare key values
                actual_interest = row.interest if hasattr(row, 'interest') else 0.0
                actual_liability = row.lease_liability if hasattr(row, 'lease_liability') else 0.0
                actual_dep = row.depreciation if hasattr(row, 'depreciation') else 0.0
                
                if len(exp_row) > 3:
                    exp_interest = parse_indian_number(exp_row[4])
                    exp_liability = parse_indian_number(exp_row[5] if len(exp_row) > 5 else '0')
                    exp_dep = parse_indian_number(exp_row[8] if len(exp_row) > 8 else '0')
                    
                    print(f"\n{actual_date.strftime('%d-%b-%Y')}:")
                    print(f"  Interest:   Expected={exp_interest:,.2f}, Actual={actual_interest:,.2f}, Diff={actual_interest-exp_interest:,.2f}")
                    print(f"  Liability:  Expected={exp_liability:,.2f}, Actual={actual_liability:,.2f}, Diff={actual_liability-exp_liability:,.2f}")
                    print(f"  Depreciation: Expected={exp_dep:,.2f}, Actual={actual_dep:,.2f}, Diff={actual_dep-exp_dep:,.2f}")
                
                break
    
    print("\n" + "="*80)
    if differences:
        print(f"❌ Found {len(differences)} significant differences (>${tolerance} tolerance)")
        return False
    else:
        print("✅ All comparisons within tolerance")
        return True


def main():
    """Main test function"""
    
    payload_file = '/Users/rohitjangid/Downloads/Lease_Redesign/lease_application/Payload :'
    
    print("="*80)
    print("LEASE CALCULATION TEST SCRIPT")
    print("="*80)
    
    # Parse payload file
    print("\n1. Parsing payload file...")
    try:
        payload, actual_rows, expected_rows = parse_payload_file(payload_file)
        print(f"   ✓ Loaded payload with {len(payload)} fields")
        print(f"   ✓ Found {len(expected_rows)} expected result rows")
    except Exception as e:
        print(f"   ❌ Error parsing payload file: {e}")
        return 1
    
    # Create LeaseData object
    print("\n2. Creating LeaseData object...")
    try:
        lease_data = create_lease_data_from_payload(payload)
        print(f"   ✓ Lease Start: {lease_data.lease_start_date}")
        print(f"   ✓ Lease End: {lease_data.end_date}")
        print(f"   ✓ First Payment: {lease_data.first_payment_date}")
        print(f"   ✓ Rental Amount: ${lease_data.rental_1:,.2f}")
        print(f"   ✓ Borrowing Rate: {lease_data.borrowing_rate}%")
        print(f"   ✓ Escalation: {lease_data.escalation_percent}%")
    except Exception as e:
        print(f"   ❌ Error creating LeaseData: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Generate schedule
    print("\n3. Generating payment schedule...")
    try:
        import pdb; pdb.set_trace()  # DEBUG: Add breakpoint here
        schedule = generate_complete_schedule(lease_data)
        print(f"   ✓ Generated {len(schedule)} schedule rows")
        
        if schedule:
            print(f"   ✓ First row date: {schedule[0].date}")
            print(f"   ✓ Last row date: {schedule[-1].date}")
            print(f"   ✓ Opening Liability: ${schedule[0].lease_liability:,.2f}")
            print(f"   ✓ Opening ROU: ${schedule[0].rou_asset:,.2f}")
    except Exception as e:
        print(f"   ❌ Error generating schedule: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Compare with expected results
    print("\n4. Comparing with expected results...")
    try:
        success = compare_results(schedule, expected_rows, tolerance=100.0)
    except Exception as e:
        print(f"   ❌ Error comparing results: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "="*80)
    if success:
        print("✅ TEST PASSED - Calculations match expected values")
        return 0
    else:
        print("❌ TEST FAILED - Calculations differ from expected values")
        return 1


if __name__ == '__main__':
    sys.exit(main())

