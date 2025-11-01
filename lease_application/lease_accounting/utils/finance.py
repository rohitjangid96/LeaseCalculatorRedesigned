"""
Financial calculation utilities
Ports Excel financial functions to Python for lease calculations
"""

import math
from typing import Optional


def present_value(rate: float, nper: int, pmt: float, fv: float = 0.0, due: bool = False) -> float:
    """
    Calculate present value
    Ports Excel PV() function
    
    Args:
        rate: Interest rate per period
        nper: Number of periods
        pmt: Payment per period
        fv: Future value (residual)
        due: True if payments at beginning of period
    Returns:
        Present value
    """
    if rate == 0:
        return -(pmt * nper + fv)
    
    if due:
        factor = (1 + rate) * ((1 - (1 + rate) ** -nper) / rate)
    else:
        factor = (1 - (1 + rate) ** -nper) / rate
    
    return -(pmt * factor + fv / ((1 + rate) ** nper))


def future_value(rate: float, nper: int, pmt: float, pv: float = 0.0, due: bool = False) -> float:
    """
    Calculate future value
    Ports Excel FV() function
    
    Args:
        rate: Interest rate per period
        nper: Number of periods
        pmt: Payment per period
        pv: Present value
        due: True if payments at beginning of period
    Returns:
        Future value
    """
    if rate == 0:
        return -(pmt * nper + pv)
    
    factor = (1 + rate) ** nper
    if due:
        return -(pmt * (1 + rate) * (factor - 1) / rate + pv * factor)
    else:
        return -(pmt * (factor - 1) / rate + pv * factor)


def payment(rate: float, nper: int, pv: float, fv: float = 0.0, due: bool = False) -> float:
    """
    Calculate payment amount
    Ports Excel PMT() function
    
    Args:
        rate: Interest rate per period
        nper: Number of periods
        pv: Present value
        fv: Future value (residual)
        due: True if payments at beginning of period
    Returns:
        Payment amount
    """
    if rate == 0:
        return -(pv + fv) / nper
    
    pv_factor = 1 / ((1 + rate) ** nper) if rate != 0 else 1
    if due:
        return -(pv + fv * pv_factor) * rate / ((1 + rate) * (1 - pv_factor))
    else:
        return -(pv + fv * pv_factor) * rate / (1 - pv_factor)


def interest_payment(rate: float, per: int, nper: int, pv: float, fv: float = 0.0, due: bool = False) -> float:
    """
    Calculate interest portion of payment
    Ports Excel IPMT() function
    
    Args:
        rate: Interest rate per period
        per: Period number
        nper: Total number of periods
        pv: Present value
        fv: Future value
        due: True if payments at beginning of period
    Returns:
        Interest payment for period
    """
    ipmt = (pv * rate * (1 + rate) ** (per - 1 - (1 if due else 0)) + 
            (fv if per == nper else 0) + 
            payment(rate, nper - (per - 1), pv * (1 + rate) ** (per - 1), fv, due) * (per - 1))
    
    return -ipmt


def principal_payment(rate: float, per: int, nper: int, pv: float, fv: float = 0.0, due: bool = False) -> float:
    """
    Calculate principal portion of payment
    Ports Excel PPMT() function
    
    Args:
        rate: Interest rate per period
        per: Period number
        nper: Total number of periods
        pv: Present value
        fv: Future value
        due: True if payments at beginning of period
    Returns:
        Principal payment for period
    """
    pmt_val = payment(rate, nper, pv, fv, due)
    ipmt_val = interest_payment(rate, per, nper, pv, fv, due)
    
    return pmt_val - ipmt_val


def net_present_value(rate: float, values: list) -> float:
    """
    Calculate net present value
    Ports Excel NPV() function
    
    Args:
        rate: Discount rate per period
        values: List of cash flows
    Returns:
        Net present value
    """
    if not values:
        return 0.0
    
    npv = 0.0
    for i, value in enumerate(values):
        npv += value / ((1 + rate) ** (i + 1))
    
    return npv


def internal_rate_of_return(values: list, guess: float = 0.1) -> Optional[float]:
    """
    Calculate internal rate of return
    Ports Excel IRR() function
    
    Args:
        values: List of cash flows (first should be negative)
        guess: Initial guess for rate
    Returns:
        Internal rate of return or None if not found
    """
    # Simplified IRR calculation using Newton-Raphson
    rate = guess
    
    for _ in range(100):  # Max 100 iterations
        npv = sum(cf / ((1 + rate) ** (i + 1)) for i, cf in enumerate(values))
        dnpv = sum(-cf * (i + 1) / ((1 + rate) ** (i + 2)) for i, cf in enumerate(values))
        
        if abs(dnpv) < 1e-10:
            break
        
        new_rate = rate - npv / dnpv
        
        if abs(new_rate - rate) < 1e-6:
            return new_rate
        
        rate = new_rate
    
    return None


def compound_rate(principal: float, future_value: float, periods: int) -> float:
    """
    Calculate compound interest rate
    """
    if principal <= 0:
        return 0.0
    
    return (future_value / principal) ** (1.0 / periods) - 1.0


def effective_annual_rate(nominal_rate: float, compounding_periods: int) -> float:
    """
    Calculate effective annual rate
    """
    return (1 + nominal_rate / compounding_periods) ** compounding_periods - 1


def calculate_lease_payment(capitalized_cost: float, residual_value: float, term_months: int, 
                           money_factor: float, sales_tax_rate: float = 0.0) -> dict:
    """
    Calculate lease payment with all components
    Standard lease formula: Payment = Depreciation + Finance Charge + Tax
    
    Args:
        capitalized_cost: Total cost
        residual_value: Expected value at end
        term_months: Lease term in months
        money_factor: Interest rate as money factor
        sales_tax_rate: Sales tax rate as decimal (0.08 for 8%)
    Returns:
        Dictionary with payment breakdown
    """
    # Convert money factor to annual rate if needed
    if money_factor < 1:  # It's a true money factor
        monthly_rate = money_factor
        annual_rate = money_factor * 2400
    else:  # It's already a rate
        monthly_rate = money_factor / 12
        annual_rate = money_factor
    
    # Monthly depreciation
    monthly_depreciation = (capitalized_cost - residual_value) / term_months
    
    # Monthly finance charge
    monthly_finance_charge = (capitalized_cost + residual_value) * money_factor
    
    # Monthly payment before tax
    monthly_payment_pre_tax = monthly_depreciation + monthly_finance_charge
    
    # Tax
    tax_amount = monthly_payment_pre_tax * sales_tax_rate
    
    # Total monthly payment
    total_monthly_payment = monthly_payment_pre_tax + tax_amount
    
    return {
        'monthly_payment': round(total_monthly_payment, 2),
        'depreciation': round(monthly_depreciation, 2),
        'finance_charge': round(monthly_finance_charge, 2),
        'tax': round(tax_amount, 2),
        'residual_value': round(residual_value, 2),
        'capitalized_cost': round(capitalized_cost, 2),
        'annual_rate': round(annual_rate, 4)
    }


def calculate_rou_asset_value(present_value_lease_liability: float, initial_direct_costs: float = 0.0,
                             prepaid_rentals: float = 0.0, lease_incentives: float = 0.0,
                             scope_reductions: float = 0.0) -> float:
    """
    Calculate Right-of-Use asset value
    ROU Asset = PV of Lease Liability + Initial Direct Costs + Prepaid Rentals 
                - Lease Incentives + Scope Reductions
    """
    return (present_value_lease_liability + initial_direct_costs + prepaid_rentals 
            - lease_incentives + scope_reductions)


def calculate_depreciation_straight_line(rou_asset_value: float, useful_life_years: float,
                                         months_elapsed: float) -> float:
    """
    Calculate straight-line depreciation
    """
    if useful_life_years <= 0:
        return 0.0
    
    annual_depreciation = rou_asset_value / useful_life_years
    return annual_depreciation * (months_elapsed / 12)


def is_finance_lease_usgaap(criteria: dict) -> bool:
    """
    Determine if lease is finance lease under US GAAP (ASC 842)
    Returns True if it meets any of 5 criteria
    """
    # 1. Title transfers
    if criteria.get('title_transfer') == 'Yes':
        return True
    
    # 2. Bargain purchase option
    if criteria.get('bargain_purchase') == 'Yes':
        return True
    
    # 3. Lease term covers major part of economic life
    lease_term_years = criteria.get('lease_term_years', 0)
    economic_life_years = criteria.get('economic_life_years', 0)
    if economic_life_years > 0 and lease_term_years / economic_life_years >= 0.75:
        return True
    
    # 4. Present value of lease payments >= fair value
    pv_lease_payments = criteria.get('pv_lease_payments', 0)
    fair_value = criteria.get('fair_value', 1)
    if fair_value > 0 and pv_lease_payments / fair_value >= 0.9:
        return True
    
    # 5. Specialized asset with no alternative use
    # This would need business logic based on asset type
    
    return False

