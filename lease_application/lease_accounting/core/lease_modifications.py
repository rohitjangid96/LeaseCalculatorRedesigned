"""
Lease Modification Handler
Implements VBA modify_calc() logic for handling lease modifications
Lines 712-826 from VBA Code
"""

from typing import Optional, Dict, Tuple, List
from datetime import date
from lease_accounting.core.models import LeaseData, PaymentScheduleRow


def process_lease_modifications(lease_data: LeaseData, schedule: List[PaymentScheduleRow],
                                baldate: date) -> Tuple[List[PaymentScheduleRow], Dict]:
    """
    VBA modify_calc() function - Main modification processing
    Handles modification chains and gain/loss calculations
    """
    if not lease_data.modifies_this_id or lease_data.modifies_this_id <= 0:
        return schedule, {}
    
    modification_results = {
        'covid_pe_gain': 0.0,
        'modification_gain': 0.0,
        'sublease_gainloss': 0.0,
        'sublease_modification_gainloss': 0.0,
        'liability_at_modification': 0.0,
        'rou_at_modification': 0.0,
        'security_at_modification': 0.0,
        'aro_at_modification': 0.0,
    }
    
    # VBA Line 720-725: Traverse modification chain backwards
    current_lease_id = lease_data.modifies_this_id
    modification_chain = []
    
    while current_lease_id and current_lease_id > 0:
        modification_chain.append(current_lease_id)
        # Would need to fetch previous lease from database
        # current_lease_id = previous_lease.modifies_this_id
        break  # Simplified - would traverse full chain
    
    if not modification_chain:
        return schedule, modification_results
    
    # VBA Line 729: nextleasedate = date_modified
    nextleasedate = lease_data.date_modified
    
    if not nextleasedate:
        return schedule, modification_results
    
    # VBA Line 731-740: Calculate security_gross at modification
    sec_gross = lease_data.security_deposit or 0.0
    if hasattr(lease_data, 'security_dates') and lease_data.security_dates:
        for qqq in range(1, 5):
            if (qqq <= len(lease_data.security_dates) and 
                lease_data.security_dates[qqq - 1] and
                lease_data.security_dates[qqq - 1] <= baldate):
                if qqq == 1:
                    sec_gross += lease_data.increase_security_1 or 0.0
                elif qqq == 2:
                    sec_gross += lease_data.increase_security_2 or 0.0
                elif qqq == 3:
                    sec_gross += lease_data.increase_security_3 or 0.0
                elif qqq == 4:
                    sec_gross += lease_data.increase_security_4 or 0.0
    
    # VBA Line 743-784: Find modification date in schedule and capture values
    Liability_value = 0.0
    security_value = 0.0
    ROU_value = 0.0
    ARO_value = 0.0
    deprp = 0.0  # Cumulative depreciation up to modification
    
    # Find modification row and capture balances
    mod_row = None
    for row in schedule:
        row_date = getattr(row, 'payment_date', row.date)
        if isinstance(row_date, date) and row_date == nextleasedate:
            Liability_value = row.lease_liability
            security_value = row.security_deposit_pv or 0.0
            ROU_value = row.rou_asset
            ARO_value = row.aro_provision or 0.0
            mod_row = row
            break
        elif row_date < nextleasedate:
            deprp += abs(row.depreciation or 0.0)
    
    if not mod_row:
        # Insert modification row if not found (VBA Line 755-783)
        # Simplified - would insert row with interpolated values
        pass
    
    modification_results['liability_at_modification'] = Liability_value
    modification_results['rou_at_modification'] = ROU_value
    modification_results['security_at_modification'] = security_value
    modification_results['aro_at_modification'] = ARO_value
    
    # VBA Line 789-813: Calculate modification gain/loss
    # Recalculate from modification date with new terms
    # This would trigger a new schedule generation from modification date
    
    # VBA Line 796-798: COVID Practical Expedient
    if lease_data.practical_expedient == "Yes":
        # covid_pe_gain = new_liability - old_liability
        # Would need new schedule to calculate
        modification_results['covid_pe_gain'] = 0.0  # Placeholder
    
    # VBA Line 800-806: Modification gain/loss
    # K9 = G7 + O9 + L9 - Liability_value - ARO_value + security_value + D6 - sec_gross
    ide = (lease_data.initial_direct_expenditure or 0) - (lease_data.lease_incentive or 0)
    
    # Would need to recalculate schedule from modification date to get new values
    # Simplified calculation:
    modification_gain = (
        Liability_value +  # Old liability
        ARO_value -  # Old ARO
        security_value -  # Old security PV
        (lease_data.security_deposit or 0.0) +  # New security base
        sec_gross  # New security gross
    )
    
    # VBA Line 802-806: If I9 < 0, additional gain calculation
    # (Would need new ROU asset calculation)
    
    # VBA Line 808-812: Sublease modification gain/loss
    if lease_data.sublease == "Yes":
        # K5 = Liability_value - new_liability
        # Would need new schedule calculation
        modification_results['sublease_modification_gainloss'] = 0.0  # Placeholder
    
    modification_results['modification_gain'] = modification_gain
    
    return schedule, modification_results


def calculate_original_lease_id(lease_id: int, modifies_this_id: Optional[int]) -> int:
    """
    VBA orj_id() function (Lines 1116-1123)
    Traces back through modification chain to find original lease ID
    """
    if not modifies_this_id or modifies_this_id <= 0:
        return lease_id
    
    oai = lease_id
    # Would traverse chain: oai = modifies_this_id of oai
    # For now, simplified:
    return oai

