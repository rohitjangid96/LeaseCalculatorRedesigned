"""
Date utilities for lease accounting
Ports Excel date functions to Python
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Optional


def eomonth(d: date, months: int = 0) -> date:
    """
    Calculate end of month - ports Excel EOMONTH()
    Args:
        d: Starting date
        months: Number of months to add/subtract
    Returns:
        Last day of the month, adjusted by months
    """
    target_month = d + relativedelta(months=months)
    
    # Get last day of target month
    if target_month.month == 12:
        last_day = date(target_month.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(target_month.year, target_month.month + 1, 1) - timedelta(days=1)
    
    return last_day


def calculate_payment_dates(
    start_date: date,
    end_date: date,
    frequency_months: int,
    day_of_month: int,
    include_last: bool = False
) -> List[date]:
    """
    Generate payment dates for lease schedule
    Ports VBA date generation logic
    
    Args:
        start_date: Lease start date
        end_date: Lease end date
        frequency_months: Payment frequency (1, 3, 6, 12)
        day_of_month: Day of month for payments
        include_last: Whether "Last" was selected
    Returns:
        List of payment dates
    """
    dates = []
    current_date = start_date
    
    while current_date <= end_date:
        if include_last or day_of_month == 0:
            # Last day of month
            payment_date = eomonth(current_date, 0)
        else:
            # Specific day of month
            try:
                payment_date = date(
                    current_date.year,
                    current_date.month,
                    day_of_month
                )
            except ValueError:
                # Invalid day (e.g., Feb 30), use last day
                payment_date = eomonth(current_date, 0)
        
        if payment_date <= end_date and payment_date >= start_date:
            dates.append(payment_date)
        
        # Move to next payment period
        current_date += relativedelta(months=frequency_months)
    
    return sorted(set(dates))


def interpolate_date_value(date_list: List[date], value_list: List[float], target_date: date) -> float:
    """
    Interpolate a value for a specific date from a series
    Used for finding rental amounts, ARO values, etc.
    
    Args:
        date_list: List of dates
        value_list: List of values corresponding to dates
        target_date: Date to interpolate for
    Returns:
        Interpolated value
    """
    # Find closest date
    if not date_list or not value_list:
        return 0.0
    
    # Exact match
    if target_date in date_list:
        idx = date_list.index(target_date)
        return value_list[idx]
    
    # Find surrounding dates
    before_date = None
    after_date = None
    
    for i, d in enumerate(date_list):
        if d <= target_date:
            before_date = (d, value_list[i])
        elif d > target_date:
            after_date = (d, value_list[i])
            break
    
    # Use nearest value
    if before_date and after_date:
        # Linear interpolation would go here
        # For now, use before_date value
        return before_date[1]
    elif before_date:
        return before_date[1]
    elif after_date:
        return after_date[1]
    else:
        return 0.0


def calculate_remaining_life(asset_life_date: Optional[date], end_date: Optional[date], current_date: date) -> float:
    """
    Calculate remaining useful life of ROU asset
    Returns years as float
    """
    if not asset_life_date or not end_date:
        return 0.0
    
    # Use earlier of asset life or lease end
    final_date = min(asset_life_date, end_date)
    
    if final_date <= current_date:
        return 0.0
    
    # Calculate remaining years
    delta = final_date - current_date
    remaining_years = delta.days / 365.25
    
    return max(0.0, remaining_years)


def is_business_day(d: date) -> bool:
    """
    Check if date is a business day (Monday-Friday)
    """
    return d.weekday() < 5


def add_months(d: date, months: int) -> date:
    """
    Add months to a date - similar to EDATE in Excel
    Excel EDATE preserves the day of month when possible
    """
    return d + relativedelta(months=months)


def edate(d: date, months: int) -> date:
    """
    Excel EDATE function - adds months to a date
    Preserves the day of month, adjusting for shorter months if needed
    
    Args:
        d: Starting date
        months: Number of months to add (can be negative)
    Returns:
        Date with months added
    """
    result = d + relativedelta(months=months)
    # If day is out of range for the target month, adjust to last day of that month
    if result.day != d.day:
        # month overflow/underflow - adjust to last day of month
        if result.month == 12:
            result = date(result.year + 1, 1, 1) - timedelta(days=1)
        elif result.month == 1:
            result = date(result.year - 1, 12, 31)
        else:
            # Last day of target month
            last_day = eomonth(result, 0)
            result = last_day
    return result


def days_between(start_date: date, end_date: date) -> int:
    """
    Calculate days between two dates
    """
    return (end_date - start_date).days


def year_fraction(start_date: date, end_date: date) -> float:
    """
    Calculate year fraction between two dates
    Used for interest calculations
    """
    delta = end_date - start_date
    return delta.days / 365.25


def get_quarter_end(d: date) -> date:
    """
    Get quarter end date for a given date
    """
    quarter_month = ((d.month - 1) // 3 + 1) * 3
    return eomonth(date(d.year, quarter_month, 1), 0)


def get_fiscal_year_end(d: date, fiscal_year_end: int = 12) -> date:
    """
    Get fiscal year end date
    """
    if d.month < fiscal_year_end:
        return eomonth(date(d.year - 1, fiscal_year_end, 1), 0)
    else:
        return eomonth(date(d.year, fiscal_year_end, 1), 0)

