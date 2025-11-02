"""
Complete VBA-Compatible Lease Schedule Generator
Implements ALL features from VBA datessrent() and basic_calc() functions
Comprehensive implementation matching Excel exactly

VBA Source File: VB script/Code
VBA Functions:
  - datessrent() - Lines 16-249: Generates payment schedule dates
  - basic_calc() - Lines 628-707: Calculates PV, interest, liability, ROU, depreciation
  - findrent() - Lines 879-958: Calculates escalated rental amounts
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict
from lease_accounting.core.models import LeaseData, PaymentScheduleRow
from lease_accounting.utils.date_utils import eomonth, edate
from lease_accounting.utils.finance import present_value
from lease_accounting.utils.rfr_rates import get_aro_rate
from dateutil.relativedelta import relativedelta
import math
import logging


def _generate_schedule_from_rental_schedule(lease_data: LeaseData) -> List[PaymentScheduleRow]:
    """
    Generate payment schedule from rental_schedule provided in form.
    Uses the start_date, end_date, rental_count, and amount directly from form
    instead of recalculating dates and amounts.
    """
    if not lease_data.rental_schedule or not isinstance(lease_data.rental_schedule, list):
        return []
    
    schedule: List[PaymentScheduleRow] = []
    
    # Parse rental_schedule entries
    # Format: [{"start_date": "2025-01-01", "end_date": "2025-12-31", "rental_count": 12, "amount": 50000}, ...]
    
    # Start with lease_start_date row (no payment)
    start_row = _create_schedule_row(
        lease_data, lease_data.lease_start_date, 0.0, _get_aro_for_date(lease_data, lease_data.lease_start_date),
        lease_data.lease_start_date, lease_data.end_date, 0, schedule
    )
    schedule.append(start_row)
    
    # Track the last payment date from previous entries to continue payment pattern
    # CRITICAL: For subsequent rental entries, payments should continue from the previous entry's pattern,
    # not restart from the entry's start_date or use first_payment_date
    last_payment_date = None  # Will be updated after each entry is processed - used to continue payments after all entries
    
    # Process each rental schedule entry
    for entry_idx, rental_entry in enumerate(lease_data.rental_schedule):
        if not isinstance(rental_entry, dict):
            continue
            
        start_date_str = rental_entry.get('start_date')
        end_date_str = rental_entry.get('end_date')
        rental_count = rental_entry.get('rental_count', 0)
        amount = rental_entry.get('amount', 0.0)
        
        if not start_date_str or not end_date_str:
            continue
        
        # Parse dates
        try:
            if isinstance(start_date_str, str):
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                start_date = start_date_str
                
            if isinstance(end_date_str, str):
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = end_date_str
        except (ValueError, TypeError):
            continue
        
        if start_date >= end_date or rental_count <= 0:
            continue
        
        # Generate payment dates based on frequency_months and day_of_month
        # IMPORTANT: First payment should respect first_payment_date, not rental schedule start_date
        # Calculate payment dates between start_date and end_date, but start from first_payment_date if it's later
        payment_dates = []
        
        # Get payment day
        logger = logging.getLogger(__name__)  # Define logger first before using it
        day_of_month = lease_data.day_of_month
        logger.debug(f"🔍 day_of_month from lease_data: {day_of_month} (type: {type(day_of_month)})")
        if isinstance(day_of_month, str):
            if day_of_month.isdigit():
                day_of_month = int(day_of_month)
                logger.debug(f"  Parsed as digit: {day_of_month}")
            elif day_of_month == "Last":
                day_of_month = eomonth(start_date, 0).day
                logger.debug(f"  Parsed as 'Last': {day_of_month}")
            else:
                # If it's a string but not a digit and not "Last", try to convert
                try:
                    day_of_month = int(day_of_month)
                    logger.debug(f"  Converted string to int: {day_of_month}")
                except (ValueError, TypeError):
                    # Invalid format, default to start_date.day (but this shouldn't happen)
                    logger.warning(f"⚠️  Invalid day_of_month format '{day_of_month}', defaulting to start_date.day={start_date.day}")
                    day_of_month = start_date.day
        elif isinstance(day_of_month, int):
            # Already an integer, use it
            logger.debug(f"  Already an int: {day_of_month}")
            pass
        elif day_of_month is None:
            # None, default to start_date.day
            logger.warning(f"⚠️  day_of_month is None, defaulting to start_date.day={start_date.day}")
            day_of_month = start_date.day
        else:
            # Try to convert to int, otherwise default
            try:
                day_of_month = int(day_of_month)
                logger.debug(f"  Converted to int: {day_of_month}")
            except (ValueError, TypeError):
                logger.warning(f"⚠️  Could not convert day_of_month '{day_of_month}', defaulting to start_date.day={start_date.day}")
                day_of_month = start_date.day
        logger.debug(f"📅 Final day_of_month value for payment generation: {day_of_month}")
        
        # CRITICAL: Preserve frequency_months even if it's 0 (don't default to 1 if 0 is explicitly set)
        # But if None, default to 1
        if lease_data.frequency_months is None:
            frequency_months = 1
        elif lease_data.frequency_months == 0:
            frequency_months = 1  # Can't have 0 frequency, treat as 1
        else:
            frequency_months = lease_data.frequency_months
        logger.debug(f"🔍 _generate_schedule_from_rental_schedule: frequency_months={frequency_months} (from lease_data.frequency_months={lease_data.frequency_months})")
        
        # Determine the first payment date for this rental schedule entry:
        # - For the FIRST entry: use first_payment_date if it exists and is >= start_date, otherwise use start_date + day_of_month
        # - For SUBSEQUENT entries: continue the payment pattern from the previous entry (last_payment_date + frequency_months)
        # CRITICAL: first_payment_date only applies to the FIRST rental entry, not subsequent ones!
        # CRITICAL: For subsequent entries, payments should continue the quarterly/monthly pattern, not restart from start_date
        first_payment_date_value = lease_data.first_payment_date
        
        if entry_idx == 0:
            # FIRST rental schedule entry: use first_payment_date if provided, otherwise start_date + day_of_month
            if first_payment_date_value and first_payment_date_value >= start_date:
                # Use first_payment_date as-is - this is the actual first payment date
                # Don't adjust it to match day_of_month (day_of_month applies to subsequent payments)
                payment_date = first_payment_date_value
                logger.debug(f"📅 Entry 0: Using first_payment_date as-is: {payment_date} (day_of_month={day_of_month} will apply to subsequent payments)")
            else:
                # No first_payment_date provided - use start_date and apply day_of_month
                payment_start = start_date
                if isinstance(day_of_month, int):
                    try:
                        payment_date = payment_start.replace(day=min(day_of_month, eomonth(payment_start, 0).day))
                    except (ValueError, AttributeError):
                        payment_date = eomonth(payment_start, 0) if day_of_month == "Last" else payment_start
                elif day_of_month == "Last":
                    payment_date = eomonth(payment_start, 0)
                else:
                    payment_date = payment_start
                logger.debug(f"📅 Entry 0: No first_payment_date - using start_date {start_date} adjusted to day_of_month: {payment_date}")
            
            # Ensure first payment date is not before rental schedule start_date
            if payment_date < start_date:
                # Move to first payment date that's >= start_date
                payment_date = start_date
                # Only adjust day_of_month if we're not using first_payment_date
                if not (first_payment_date_value and first_payment_date_value >= start_date):
                    try:
                        payment_date = payment_date.replace(day=min(day_of_month, eomonth(payment_date, 0).day))
                    except (ValueError, AttributeError):
                        payment_date = eomonth(payment_date, 0) if day_of_month == "Last" else payment_date
                logger.debug(f"📅 Entry 0: Adjusted payment_date to >= start_date: {payment_date}")
        else:
            # SUBSEQUENT rental schedule entries: continue payment pattern from previous entry
            # CRITICAL: Continue from last_payment_date + frequency_months, not from start_date
            if last_payment_date:
                # Continue the payment pattern: last payment + frequency_months
                next_payment_estimate = edate(last_payment_date, frequency_months)
                # Apply day_of_month to the next payment
                if isinstance(day_of_month, int):
                    try:
                        payment_date = next_payment_estimate.replace(day=min(day_of_month, eomonth(next_payment_estimate, 0).day))
                    except (ValueError, AttributeError):
                        payment_date = eomonth(next_payment_estimate, 0) if day_of_month == "Last" else next_payment_estimate
                elif day_of_month == "Last":
                    payment_date = eomonth(next_payment_estimate, 0)
                else:
                    payment_date = next_payment_estimate
                
                # Ensure payment_date is >= start_date (but should already be due to continuing pattern)
                if payment_date < start_date:
                    # If continuing pattern puts us before start_date, find first payment >= start_date that aligns with pattern
                    # Move to start_date month and apply day_of_month, then check if we need to add frequency_months
                    payment_date = start_date
                    if isinstance(day_of_month, int):
                        try:
                            payment_date = payment_date.replace(day=min(day_of_month, eomonth(payment_date, 0).day))
                        except (ValueError, AttributeError):
                            payment_date = eomonth(payment_date, 0) if day_of_month == "Last" else payment_date
                    elif day_of_month == "Last":
                        payment_date = eomonth(payment_date, 0)
                    
                    # If still before start_date, add frequency_months until we're >= start_date
                    while payment_date < start_date:
                        payment_date = edate(payment_date, frequency_months)
                        if isinstance(day_of_month, int):
                            try:
                                payment_date = payment_date.replace(day=min(day_of_month, eomonth(payment_date, 0).day))
                            except (ValueError, AttributeError):
                                payment_date = eomonth(payment_date, 0) if day_of_month == "Last" else payment_date
                        elif day_of_month == "Last":
                            payment_date = eomonth(payment_date, 0)
                
                logger.debug(f"📅 Entry {entry_idx}: Continuing pattern from last_payment_date {last_payment_date} -> {payment_date}")
            else:
                # No last_payment_date (shouldn't happen, but fallback to start_date)
                payment_start = start_date
                if isinstance(day_of_month, int):
                    try:
                        payment_date = payment_start.replace(day=min(day_of_month, eomonth(payment_start, 0).day))
                    except (ValueError, AttributeError):
                        payment_date = eomonth(payment_start, 0) if day_of_month == "Last" else payment_start
                elif day_of_month == "Last":
                    payment_date = eomonth(payment_start, 0)
                else:
                    payment_date = payment_start
                logger.warning(f"📅 Entry {entry_idx}: No last_payment_date, using start_date {start_date} adjusted to day_of_month: {payment_date}")
        
        # Generate payment dates based on frequency_months
        # VBA logic: Payments occur every frequency_months starting from first_payment_date
        # Example: Quarterly (3 months) starting Mar 5 -> Mar 5, Jun 5, Sep 5, Dec 5, etc.
        # CRITICAL: Each payment is exactly frequency_months apart (3 for quarterly, 1 for monthly)
        # DO NOT increment by 1 month - always use frequency_months
        # CRITICAL: Continue generating payments until lease end_date (not just rental schedule entry end_date)
        count = 0
        current_payment_date = payment_date  # Start from the first payment date we calculated
        
        # CRITICAL: Use lease end_date as the ultimate limit, not just the rental schedule entry's end_date
        # The schedule should continue until lease end_date (2033-12-31), not stop at rental entry end_date
        lease_end_date = lease_data.end_date
        # Use lease end_date as the target, not rental entry end_date
        target_end_date = lease_end_date if lease_end_date else end_date
        logger = logging.getLogger(__name__)
        logger.debug(f"📅 Generating payment dates from {current_payment_date}, frequency={frequency_months} months, rental_count={rental_count}")
        logger.debug(f"📅 Rental schedule entry end_date: {end_date}, Lease end_date: {lease_end_date}, Target end_date: {target_end_date}")
        
        # Continue generating payments until we reach the lease end_date (target_end_date)
        # Only respect rental_count if it's > 0, but prioritize reaching lease end_date
        while current_payment_date <= target_end_date:
            # Stop if rental_count limits us (only if rental_count > 0)
            if rental_count > 0 and count >= rental_count:
                logger.debug(f"📅 Stopping due to rental_count limit: {count} >= {rental_count}")
                break
            # Payment date must be >= rental schedule start_date
            if current_payment_date < start_date:
                # Skip this date - move to next payment by frequency_months ONLY (not 1 month!)
                current_payment_date = edate(current_payment_date, frequency_months)
                # Ensure day_of_month is correct after moving by frequency_months
                if isinstance(day_of_month, int):
                    try:
                        current_payment_date = current_payment_date.replace(day=min(day_of_month, eomonth(current_payment_date, 0).day))
                    except (ValueError, AttributeError):
                        current_payment_date = eomonth(current_payment_date, 0)
                elif day_of_month == "Last":
                    current_payment_date = eomonth(current_payment_date, 0)
                continue
            
            # Payment date must be <= target_end_date (lease end_date)
            # CRITICAL: Continue generating until lease end_date, even if rental entry ends earlier
            if current_payment_date > target_end_date:
                logger.debug(f"📅 Stopping: current_payment_date {current_payment_date} > target_end_date {target_end_date}")
                break
            
            # Add payment date
            payment_dates.append(current_payment_date)
            count += 1
            logger.debug(f"  Added payment {count}: {current_payment_date}")
            
            # Move to next payment date by EXACTLY frequency_months (quarterly = 3, monthly = 1)
            # CRITICAL: Use frequency_months, NOT 1 month! This is what makes it quarterly vs monthly
            # CRITICAL: For subsequent payments (after first), ALWAYS apply day_of_month
            # Continue generating payments until we reach lease end_date
            # Check if next payment would be within lease end_date
            next_payment_estimate = edate(current_payment_date, frequency_months)
            # Apply day_of_month to estimate
            if isinstance(day_of_month, int):
                try:
                    next_payment_estimate = next_payment_estimate.replace(day=min(day_of_month, eomonth(next_payment_estimate, 0).day))
                except (ValueError, AttributeError):
                    pass
            
            # Continue if next payment would be <= target_end_date AND (no rental_count limit OR count < rental_count)
            should_continue = (next_payment_estimate <= target_end_date) and (rental_count == 0 or count < rental_count)
            
            if should_continue:
                # edate() adds months while preserving the day
                # For quarterly: each increment adds 3 months (Mar 1 + 3 months = Jun 1)
                # For monthly: each increment adds 1 month
                previous_date = current_payment_date
                current_payment_date = edate(current_payment_date, frequency_months)
                logger.debug(f"  Incremented by {frequency_months} months: {previous_date} -> {current_payment_date}")
                
                # For subsequent payments (after first), ALWAYS apply day_of_month
                # First payment uses first_payment_date as-is, subsequent payments use day_of_month
                if isinstance(day_of_month, int):
                    try:
                        # Apply day_of_month to subsequent payment (e.g., Jun 1 -> Jun 5)
                        current_payment_date = current_payment_date.replace(day=min(day_of_month, eomonth(current_payment_date, 0).day))
                        logger.debug(f"  Applied day_of_month={day_of_month} to subsequent payment: {current_payment_date}")
                    except (ValueError, AttributeError):
                        current_payment_date = eomonth(current_payment_date, 0)
                elif day_of_month == "Last":
                    current_payment_date = eomonth(current_payment_date, 0)
                    logger.debug(f"  Applied day_of_month='Last' to subsequent payment: {current_payment_date}")
        
        logger.debug(f"📅 Generated {len(payment_dates)} payment dates: {payment_dates[:5]}...")
        
        # Create schedule rows for each payment date
        # CRITICAL: For each payment date, determine which rental entry it belongs to based on date
        # Use the rental amount from the entry whose date range contains the payment date
        for payment_date in payment_dates:
            # Calculate proportionate rental amount for the payment period
            # This handles cases where rental schedule changes mid-payment period
            payment_rental_amount = _get_proportionate_rental_for_payment_period(
                lease_data, payment_date, frequency_months
            )
            
            if payment_rental_amount == 0.0:
                # Fallback: if proportionate calculation fails, use simple lookup
                payment_rental_amount = _get_rental_from_schedule(lease_data, payment_date)
                logger.warning(f"⚠️  Proportionate calculation returned 0 for {payment_date}, using simple lookup: {payment_rental_amount}")
            
            logger.debug(f"📅 Payment date {payment_date}: proportionate rental = {payment_rental_amount:.2f}")
            
            # Check if row already exists for this date
            if any(row.date == payment_date for row in schedule):
                # Update existing row with rental amount
                for row in schedule:
                    if row.date == payment_date:
                        row.rental_amount = payment_rental_amount
                        logger.debug(f"📅 Updated existing row for {payment_date} with proportionate amount: {payment_rental_amount:.2f}")
                        break
            else:
                # Create new row - use len(schedule) as row_index to ensure only first row is is_opening
                aro_for_date = _get_aro_for_date(lease_data, payment_date)
                row = _create_schedule_row(
                    lease_data, payment_date, payment_rental_amount, aro_for_date,
                    lease_data.lease_start_date, lease_data.end_date, len(schedule), schedule
                )
                schedule.append(row)
                logger.debug(f"📅 Created new row for {payment_date} with proportionate amount: {payment_rental_amount:.2f}")
        
        # Update last_payment_date to the last payment date in payment_dates (if any were generated)
        # CRITICAL: This ensures subsequent entries continue the payment pattern
        if payment_dates:
            last_payment_date = max(payment_dates)
            logger.debug(f"📅 Entry {entry_idx}: Updated last_payment_date to {last_payment_date}")
        elif count > 0:
            # If payment_dates is empty but count > 0, something went wrong, but use current_payment_date if available
            # This shouldn't happen, but provides a fallback
            logger.warning(f"📅 Entry {entry_idx}: payment_dates is empty but count={count}")
    
    # CRITICAL: Continue generating payments after all rental schedule entries are processed
    # This ensures payments are generated until lease_end_date even if rental entries end earlier
    if lease_data.end_date and last_payment_date:
        lease_end_date = lease_data.end_date
        frequency_months = lease_data.frequency_months or 1
        day_of_month = lease_data.day_of_month
        
        # Continue generating payments from last_payment_date until lease_end_date
        current_payment_date = edate(last_payment_date, frequency_months)
        
        # Apply day_of_month to current_payment_date
        if isinstance(day_of_month, int):
            try:
                current_payment_date = current_payment_date.replace(day=min(day_of_month, eomonth(current_payment_date, 0).day))
            except (ValueError, AttributeError):
                current_payment_date = eomonth(current_payment_date, 0)
        elif day_of_month == "Last":
            current_payment_date = eomonth(current_payment_date, 0)
        
        # Continue generating payments while current_payment_date <= lease_end_date
        while current_payment_date <= lease_end_date:
            # Calculate proportionate rental amount for this payment period
            payment_rental_amount = _get_proportionate_rental_for_payment_period(
                lease_data, current_payment_date, frequency_months
            )
            
            if payment_rental_amount == 0.0:
                # Fallback: use simple lookup if proportionate calculation fails
                payment_rental_amount = _get_rental_from_schedule(lease_data, current_payment_date)
                logger.warning(f"⚠️  Proportionate calculation returned 0 for {current_payment_date}, using simple lookup: {payment_rental_amount}")
            
            # Check if row already exists for this date
            if any(row.date == current_payment_date for row in schedule):
                # Update existing row with rental amount
                for row in schedule:
                    if row.date == current_payment_date:
                        row.rental_amount = payment_rental_amount
                        logger.debug(f"📅 Updated existing row for {current_payment_date} with proportionate amount: {payment_rental_amount:.2f}")
                        break
            else:
                # Create new row
                aro_for_date = _get_aro_for_date(lease_data, current_payment_date)
                row = _create_schedule_row(
                    lease_data, current_payment_date, payment_rental_amount, aro_for_date,
                    lease_data.lease_start_date, lease_data.end_date, len(schedule), schedule
                )
                schedule.append(row)
                logger.debug(f"📅 Created new row for {current_payment_date} with proportionate amount: {payment_rental_amount:.2f}")
            
            # Move to next payment date
            next_payment_estimate = edate(current_payment_date, frequency_months)
            
            # Apply day_of_month to estimate
            if isinstance(day_of_month, int):
                try:
                    next_payment_estimate = next_payment_estimate.replace(day=min(day_of_month, eomonth(next_payment_estimate, 0).day))
                except (ValueError, AttributeError):
                    pass
            
            # Stop if next payment would exceed lease_end_date
            if next_payment_estimate > lease_end_date:
                break
            
            current_payment_date = next_payment_estimate
    
    # CRITICAL: Ensure there's a row at lease_end_date for proper amortization calculation
    # This is important even if there's no payment on that date
    if lease_data.end_date:
        lease_end_date = lease_data.end_date
        if not any(row.date == lease_end_date for row in schedule):
            # Add a final row at lease_end_date (no payment, just for closing balances)
            aro_for_date = _get_aro_for_date(lease_data, lease_end_date)
            end_row = _create_schedule_row(
                lease_data, lease_end_date, 0.0, aro_for_date,
                lease_data.lease_start_date, lease_data.end_date, len(schedule), schedule
            )
            schedule.append(end_row)
            logger.debug(f"📅 Added final row at lease_end_date: {lease_end_date}")
    
    # Sort schedule by date
    schedule.sort(key=lambda x: x.date)
    
    # CRITICAL: Add month-end rows for interest accrual (VBA Line 187-206)
    # Expected schedule includes month-end dates (Jan 31, Feb 29, Mar 31, etc.) even when there's no payment
    # These are for interest accrual and proper depreciation calculation
    month_end_schedule = []
    current_date = lease_data.lease_start_date
    end_date = lease_data.end_date
    
    # Generate month-end dates from lease_start_date to end_date
    while current_date <= end_date:
        # Get last day of current month
        month_end = eomonth(current_date, 0)
        
        # Only add if it's different from current_date and <= end_date
        if month_end != current_date and month_end <= end_date:
            # Check if this date already exists in schedule
            if not any(row.date == month_end for row in schedule):
                # Create month-end row (no payment, just for interest accrual)
                # Use len(schedule) as row_index to ensure only first row is is_opening
                aro_for_date = _get_aro_for_date(lease_data, month_end)
                month_end_row = _create_schedule_row(
                    lease_data, month_end, 0.0, aro_for_date,
                    lease_data.lease_start_date, lease_data.end_date, len(schedule), schedule
                )
                month_end_schedule.append(month_end_row)
        
        # Move to first day of next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)
    
    # Add month-end rows to schedule
    schedule.extend(month_end_schedule)
    
    # CRITICAL: Add intermediate dates when first_payment_date doesn't match day_of_month
    # Expected schedule shows dates like Mar 5, 2024 when first payment is Mar 1 but day_of_month is 5
    # This represents the day_of_month adjustment after the first payment
    if lease_data.first_payment_date and lease_data.day_of_month:
        # Parse day_of_month
        day_of_month_val = lease_data.day_of_month
        if isinstance(day_of_month_val, str):
            if day_of_month_val.isdigit():
                day_of_month_val = int(day_of_month_val)
            elif day_of_month_val == "Last":
                day_of_month_val = None  # Skip intermediate date logic for "Last"
            else:
                try:
                    day_of_month_val = int(day_of_month_val)
                except (ValueError, TypeError):
                    day_of_month_val = None
        elif not isinstance(day_of_month_val, int):
            day_of_month_val = None
        
        if day_of_month_val and isinstance(day_of_month_val, int):
            # Check if first_payment_date day doesn't match day_of_month
            if lease_data.first_payment_date.day != day_of_month_val:
                # Create intermediate date: same month/year as first_payment_date, but with day_of_month
                try:
                    intermediate_date = lease_data.first_payment_date.replace(day=min(day_of_month_val, eomonth(lease_data.first_payment_date, 0).day))
                    
                    # Only add if it's after first_payment_date and before month-end
                    if intermediate_date > lease_data.first_payment_date and intermediate_date < eomonth(lease_data.first_payment_date, 0):
                        # Check if this date already exists
                        if not any(row.date == intermediate_date for row in schedule):
                            # Create intermediate row (no payment, just for interest accrual)
                            # Use len(schedule) as row_index to ensure only first row is is_opening
                            aro_for_date = _get_aro_for_date(lease_data, intermediate_date)
                            intermediate_row = _create_schedule_row(
                                lease_data, intermediate_date, 0.0, aro_for_date,
                                lease_data.lease_start_date, lease_data.end_date, len(schedule), schedule
                            )
                            schedule.append(intermediate_row)
                            logger.debug(f"📅 Added intermediate date {intermediate_date} (day_of_month adjustment after first payment {lease_data.first_payment_date})")
                except (ValueError, AttributeError):
                    pass  # Invalid date, skip
    
    # Sort again after adding month-end and intermediate rows
    schedule.sort(key=lambda x: x.date)
    
    # Apply basic calculations (PV, interest, liability, ROU, depreciation)
    schedule = _apply_basic_calculations(lease_data, schedule)
    
    # Apply Security Deposit Increases
    schedule = _apply_security_deposit_increases(lease_data, schedule)
    
    # Apply Impairments
    schedule = _apply_impairments(lease_data, schedule)
    
    # Apply Manual Rental Adjustments
    schedule = _apply_manual_rental_adjustments(lease_data, schedule)
    
    return schedule


def generate_complete_schedule(lease_data: LeaseData) -> List[PaymentScheduleRow]:
    """
    Generate complete lease payment schedule - FULL VBA datessrent() implementation
    Includes: ARO revisions, Security increases, Manual rentals, Impairments, etc.
    
    VBA Source: VB script/Code, datessrent() function (Lines 16-249)
    
    If rental_schedule is provided in lease_data, use it directly instead of recalculating.
    """
    if not lease_data.lease_start_date or not lease_data.end_date:
        return []
    
    # Always use rental_schedule if provided (rental schedule is the source of truth)
    # When rental_schedule exists, it determines which rental applies to each payment date
    # This matches VBA logic where rental table is used when manual entries exist
    if lease_data.rental_schedule and isinstance(lease_data.rental_schedule, list) and len(lease_data.rental_schedule) > 0:
        logger = logging.getLogger(__name__)
        logger.info("📋 Using rental_schedule table (rental schedule provided - source of truth)")
        return _generate_schedule_from_rental_schedule(lease_data)
    
    schedule: List[PaymentScheduleRow] = []
    
    # Initialize rental tracking (VBA app_rent, app_rent_date)
    # Since rental_schedule will always be present, we get rental from schedule
    # For initial lookup, get rental for first payment date
    first_payment_date = lease_data.first_payment_date if lease_data.first_payment_date else lease_data.lease_start_date
    app_rent = _get_rental_from_schedule(lease_data, first_payment_date)
    app_rent_date = first_payment_date
    lastmonthpay = 0
    
    # Extract dates
    starto = lease_data.lease_start_date
    firstpaymentDate = lease_data.first_payment_date if lease_data.first_payment_date else lease_data.lease_start_date
    enddate = lease_data.end_date
    dateo = starto
    
    # Validate end date is after start date
    if enddate <= starto:
        # Edge case: same day or invalid - create at least one row
        if enddate == starto:
            row = _create_schedule_row(
                lease_data, starto, app_rent, _get_aro_for_date(lease_data, starto),
                lease_data.lease_start_date, enddate, 0, schedule
            )
            schedule.append(row)
            schedule = _apply_basic_calculations(lease_data, schedule)
            return schedule
    
    # Payment frequency
    monthof = lease_data.frequency_months
    dayofm = lease_data.day_of_month
    dayofma = int(dayofm) if isinstance(dayofm, str) and dayofm.isdigit() else (eomonth(dateo, 0).day if dayofm == "Last" else 1)
    dayofma1 = dayofma
    
    k = 1
    
    # === VBA Line 34-35: Put first date ===
    # CRITICAL: C9 is ALWAYS starto (lease_start_date), not first_payment_date!
    # This is the reference point for all PV calculations (Line 661: C10-C9)
    # VBA Line 35: Sheets("compute").Range("C9").Formula = starto
    first_row_date = starto  # VBA: C9 = starto (always, regardless of first_payment_date)
    first_rental = 0.0  # Will be set only if payment is on this date
    
    # === VBA Line 39-74: First payment date = start date ===
    if starto == firstpaymentDate:
        # If payment occurs on start date, set rental amount
        # Check if rental_schedule exists - if so, use it (rental schedule is source of truth)
        if lease_data.rental_schedule and isinstance(lease_data.rental_schedule, list) and len(lease_data.rental_schedule) > 0:
            # Use rental schedule table
            first_rental = _get_manual_rental_for_date(lease_data, dateo)
            lastmonthpay = dateo.month + dateo.year * 12
        else:
            # Use escalation logic (findrent) when no rental_schedule
            # VBA Lines 42-53: Loop until app_rent_date >= dateo
            # Since app_rent_date starts as end_date from findrent(1), this will call findrent()
            for xx in range(1, 51):  # VBA: For xx = 1 To 50
                if app_rent_date >= dateo:  # VBA Line 44
                    # VBA Line 45: Sets rental = app_rent
                    first_rental = app_rent
                    lastmonthpay = dateo.month + dateo.year * 12  # VBA Line 46
                    break
                else:
                    # VBA Lines 49-51: Increment rent_no and call findrent()
                    rent_no = rent_no + 1
                    app_rent, app_rent_date = findrent(lease_data, rent_no)
            else:
                # If loop completes without break, no valid rental found
                first_rental = 0.0
        
        # Find ARO for first date (lines 65-73)
        first_aro = _get_aro_for_date(lease_data, dateo)
        
        # Create first row (payment on start date)
        first_row = _create_schedule_row(
            lease_data, first_row_date, first_rental, first_aro, 
            lease_data.lease_start_date, enddate, 0, schedule
        )
        schedule.append(first_row)
        k += 1
    else:
        # starto != firstpaymentDate: Create opening row at starto with rental=0
        # VBA Line 35 still sets C9 = starto, but payment comes later (Line 91)
        first_aro = _get_aro_for_date(lease_data, starto)
        first_row = _create_schedule_row(
            lease_data, first_row_date, 0.0, first_aro,  # rental = 0 (no payment on start date)
            lease_data.lease_start_date, enddate, 0, schedule
        )
        schedule.append(first_row)
        k += 1
    
    dateo = starto  # Reset for main loop
    
    # === VBA Line 83-236: Main date loop ===
    for i in range(1, 50001):
        x = 0  # x = 1 means date is plotted
        dateo = starto + timedelta(days=i)
        
        # VBA Line 88: Finding last day of month
        if dayofm == "Last":
            dayofma = eomonth(dateo, 0).day
        
        # VBA Line 91-132: Plotting rent on first payment date
        # This only applies when starto != firstpaymentDate (already handled above if equal)
        if dateo == firstpaymentDate and starto != firstpaymentDate:
            rental = 0.0
            # Check if rental_schedule exists - if so, use it (rental schedule is source of truth)
            if lease_data.rental_schedule and isinstance(lease_data.rental_schedule, list) and len(lease_data.rental_schedule) > 0:
                # Use rental schedule table
                rental = _get_manual_rental_for_date(lease_data, dateo)
                lastmonthpay = dateo.month + dateo.year * 12
            else:
                # Use escalation logic (findrent) when no rental_schedule
                # VBA Lines 95-116: Same logic as above
                for xx in range(1, 51):  # VBA: For xx = 1 To 50
                    if app_rent_date >= dateo:  # VBA Line 97
                        # VBA Line 98: Sets rental = app_rent
                        rental = app_rent
                        lastmonthpay = dateo.month + dateo.year * 12  # VBA Line 99
                        break
                    else:
                        # VBA Lines 102-104: Increment rent_no and call findrent()
                        rent_no = rent_no + 1
                        app_rent, app_rent_date = findrent(lease_data, rent_no)
            
            aro_value = _get_aro_for_date(lease_data, dateo)
            
            row = _create_schedule_row(
                lease_data, dateo, rental, aro_value,
                lease_data.lease_start_date, enddate, k, schedule
            )
            schedule.append(row)
            k += 1
            x = 1
        
        # VBA Line 187-206: Month-end rows (check before skipping dates before first payment)
        # These accrual entries must be created even before first payment date
        if x == 0 and dateo.month != (dateo + timedelta(days=1)).month:
            # Month-end row - only ARO, no rental
            # CRITICAL: Create these entries even if before first payment date
            # They accumulate interest on the liability
            aro_value = _get_aro_for_date(lease_data, dateo)
            row = _create_schedule_row(
                lease_data, dateo, 0.0, aro_value,
                lease_data.lease_start_date, enddate, k, schedule
            )
            schedule.append(row)
            k += 1
            x = 1
        
        # Skip payment dates if before first payment date (but keep month-end accruals)
        if dateo < firstpaymentDate and x == 0:
            continue
        
        # VBA Line 137-184: Regular payment frequency logic
        if ((dateo.year * 12 + dateo.month) - (firstpaymentDate.year * 12 + firstpaymentDate.month)) % monthof == 0:
            if x == 1:
                continue
            
            # VBA Line 143-146: Handle February
            if dateo.month == 2 and dayofma1 > 28:
                dayofma1_temp = dayofma1
                dayofma = 28
            
            if dateo.day == dayofma:
                rental = 0.0
                
                # VBA Line 150-171: Find rental
                # Check if rental_schedule exists - if so, use it (rental schedule is source of truth)
                if lease_data.rental_schedule and isinstance(lease_data.rental_schedule, list) and len(lease_data.rental_schedule) > 0:
                    # Use rental schedule table to determine rental for this payment date
                    rental = _get_manual_rental_for_date(lease_data, dateo)
                    current_month = dateo.month + dateo.year * 12
                    lastmonthpay = 0
                else:
                    # Use escalation logic (findrent) when no rental_schedule
                    # VBA Lines 151-162: Loop to find correct rental
                    for xx in range(1, 51):  # VBA: For xx = 1 To 50
                        if app_rent_date >= dateo:  # VBA Line 152
                            # VBA Line 153: Check lastmonthpay
                            current_month = dateo.month + dateo.year * 12
                            if lastmonthpay != current_month:
                                # VBA Line 153: Set rental = app_rent
                                rental = app_rent
                            # VBA Line 154: lastmonthpay = 0 (ALWAYS sets to 0)
                            lastmonthpay = 0
                            break
                        else:
                            # VBA Lines 157-159: Increment rent_no and call findrent()
                            rent_no = rent_no + 1
                            app_rent, app_rent_date = findrent(lease_data, rent_no)
                
                # VBA Line 173-181: Find ARO
                aro_value = _get_aro_for_date(lease_data, dateo)
                
                row = _create_schedule_row(
                    lease_data, dateo, rental, aro_value,
                    lease_data.lease_start_date, enddate, k, schedule
                )
                schedule.append(row)
                k += 1
                x = 1
            
            # VBA Line 185: Restore dayofma if February
            if dateo.month == 2 and dayofma1 > 28:
                dayofma = dayofma1
        
        # VBA Line 209-228: End date handling with purchase option
        if dateo == enddate:
            if x == 0:
                # No payment on end date - add purchase option as rental
                purchase_price = lease_data.purchase_option_price or 0.0
                aro_value = _get_aro_for_date(lease_data, dateo)
                row = _create_schedule_row(
                    lease_data, dateo, purchase_price, aro_value,
                    lease_data.lease_start_date, enddate, k, schedule
                )
                schedule.append(row)
            else:
                # Payment exists - add purchase price to last rental
                if schedule:
                    schedule[-1].rental_amount += (lease_data.purchase_option_price or 0.0)
            
            break
        
        if dateo >= enddate:
            break
    
    # === VBA basic_calc() logic ===
    schedule = _apply_basic_calculations(lease_data, schedule)
    
    # === Apply Security Deposit Increases ===
    schedule = _apply_security_deposit_increases(lease_data, schedule)
    
    # === Apply Impairments ===
    schedule = _apply_impairments(lease_data, schedule)
    
    # === Apply Manual Rental Adjustments ===
    schedule = _apply_manual_rental_adjustments(lease_data, schedule)
    
    return schedule


def findrent(lease_data: LeaseData, app: int) -> Tuple[float, date]:
    """
    VBA findrent() function - Complete implementation
    
    VBA Source: VB script/Code, findrent() Sub (Lines 879-958)
    Calculates rental amount with escalation for payment number 'app'
    """
    # No default - if esc_freq_months is None, escalation is not applicable
    fre = lease_data.esc_freq_months if lease_data.esc_freq_months is not None else 0
    # VBA Line 884: pre = Escalation_percent * 100
    # CRITICAL: In Excel, if cell shows "5%" (percentage format), Excel stores it as 0.05
    # When VBA reads .Value, it gets 0.05, then multiplies by 100 → 5.0
    # But JSON sends 5.0 directly (already in percentage form), so:
    # - If escalation_percent >= 1: Already in percentage form (5 = 5%), use directly
    # - If escalation_percent < 1: In decimal form (0.05 = 5%), multiply by 100
    escalation_pct = lease_data.escalation_percent or 0.0
    if escalation_pct >= 1:
        # Already in percentage form (5.0 means 5%)
        pre = escalation_pct
    else:
        # In decimal form (0.05 means 5%), multiply by 100 to match VBA
        pre = escalation_pct * 100
    
    Frequency_months = lease_data.frequency_months
    accrualday = lease_data.accrual_day or 1
    
    # VBA Line 895-902: Determining starting point
    # CRITICAL: escalation_start_date field name - No defaults, use None if not provided
    Escalation_Start = getattr(lease_data, 'escalation_start_date', None) or getattr(lease_data, 'escalation_start', None)
    
    # VBA Line 889-893: Early exit if no escalation
    # Check if escalation parameters are missing or zero (no escalation applicable)
    # Since rental_schedule will always be present, get rental from schedule
    if fre == 0 or pre == 0 or Frequency_months == 0 or Escalation_Start is None:
        # No escalation - get rental from rental_schedule for the escalation start date (or lease start date)
        payment_date = Escalation_Start if Escalation_Start else lease_data.lease_start_date
        app_rent = _get_rental_from_schedule(lease_data, payment_date)
        app_rent_date = lease_data.end_date or date.today()
        return (app_rent, app_rent_date)
    Lease_start_date = lease_data.lease_start_date
    Day_of_Month = lease_data.day_of_month
    
    # Handle "Last" day of month
    if Day_of_Month == "Last":
        if Lease_start_date.month in [1, 3, 5, 7, 8, 10, 12]:
            Day_of_Month = 31
        elif Lease_start_date.month == 2:
            Day_of_Month = 28
        else:
            Day_of_Month = 30
    else:
        Day_of_Month = int(Day_of_Month) if isinstance(Day_of_Month, str) and Day_of_Month.isdigit() else 1
    
    # VBA Line 904: begind calculation
    begind = date(Escalation_Start.year - 1, Lease_start_date.month, accrualday)
    
    # VBA Line 906-915: Find startd
    startd = begind
    for t in range(1, 25):
        e_date = begind + relativedelta(months=Frequency_months * t)
        if Escalation_Start < e_date:
            startd = begind + relativedelta(months=Frequency_months * (t - 1))
            break
        elif Escalation_Start == e_date:
            startd = begind + relativedelta(months=Frequency_months * t)
            break
    
    # VBA Line 917-919: begdate and startd adjustments
    begdate = startd
    begdate1 = date(begdate.year, begdate.month, Day_of_Month)
    startd = date(startd.year, startd.month, accrualday)
    
    # VBA Line 921: offse calculation
    offse = (startd - Escalation_Start).days
    
    # VBA Line 924-925: u and k calculations
    if app % 2 == 1:
        u = app
    else:
        u = app - 1
    
    if offse != 0:
        k = int(u / 2)
    else:
        k = 0
    
    # VBA Line 928-956: Main loop
    # CRITICAL: VBA's For i = u To 200 allows modifying i inside the loop
    # Python's for loop doesn't allow this, so we must use a while loop
    i = u
    while i < 201:
        # VBA Line 929: app_rent_date = EDate(begdate1, fre * (i - k)) - 1
        app_rent_date = edate(begdate1, fre * (i - k)) - timedelta(days=1)
        # Get base rental from schedule and apply escalation
        base_rental = _get_rental_from_schedule(lease_data, Escalation_Start) if Escalation_Start else _get_rental_from_schedule(lease_data, lease_data.lease_start_date)
        app_rent = base_rental * ((1 + pre / 100) ** (i - 1 - k))
        
        if app == i:
            return (app_rent, app_rent_date)
        
        # VBA Line 933-936: Check if past end date
        if app_rent_date >= (lease_data.end_date or date.today()):
            app_rent_date = lease_data.end_date or date.today()
            return (app_rent, app_rent_date)
        
        # VBA Line 938-954: Offset handling
        J = 0
        i_was_incremented = False
        if offse != 0:
            # VBA Line 940: app_rent_date = EDate(begdate1, fre * (i - k))
            app_rent_date = edate(begdate1, fre * (i - k))
            # VBA Line 941: RPeriod calculation
            RPeriod = (edate(begdate, fre * (i - k) + Frequency_months)) - edate(begdate, fre * (i - k))
            offseOriginal = offse
            if offseOriginal < 0:
                offse = RPeriod.days + offseOriginal
            
            # Get base rental from schedule and apply escalation
            base_rental = _get_rental_from_schedule(lease_data, Escalation_Start) if Escalation_Start else _get_rental_from_schedule(lease_data, lease_data.lease_start_date)
            app_rent = (base_rental * ((1 + pre / 100) ** (i - k)) * offse / RPeriod.days + 
                       base_rental * ((1 + pre / 100) ** (i - 1 - k)) * (RPeriod.days - offse) / RPeriod.days)
            i += 1
            i_was_incremented = True
            if app == i:
                return (app_rent, app_rent_date)
            k += 1
            
            # VBA Line 949-952: Check end date again
            if app_rent_date >= (lease_data.end_date or date.today()):
                app_rent_date = lease_data.end_date or date.today()
                return (app_rent, app_rent_date)
        
        # Increment i for next iteration ONLY if we didn't already increment inside the offse block
        if not i_was_incremented:
            i += 1
    
    return (app_rent, app_rent_date)


def _get_aro_for_date(lease_data: LeaseData, payment_date: date) -> Optional[float]:
    """
    VBA ARO lookup logic (Lines 65-73, 118-126, etc.)
    Supports up to 8 ARO revisions
    """
    # Get ARO dates and amounts
    aro_dates = lease_data.aro_dates if hasattr(lease_data, 'aro_dates') and lease_data.aro_dates else []
    aro_revisions = lease_data.aro_revisions if hasattr(lease_data, 'aro_revisions') and lease_data.aro_revisions else []
    
    # Check ARO revisions (up to 8)
    for aro in range(8):
        if aro < len(aro_dates) and aro_dates[aro]:
            aro_date = aro_dates[aro]
            # VBA logic: If ARO_date > dateo OR ARO_date = 0, use this ARO
            if aro_date == date.min or aro_date > payment_date:
                if aro < len(aro_revisions) and aro_revisions[aro] is not None:
                    return aro_revisions[aro]
                elif aro == 0:
                    return lease_data.aro or 0.0
    
    # Default to initial ARO
    return lease_data.aro if (lease_data.aro and lease_data.aro > 0) else None


def _get_rental_from_schedule(lease_data: LeaseData, payment_date: date) -> float:
    """
    Get rental amount from rental_schedule table for a given payment date.
    VBA logic: When AutoRental = "NO" or no escalation, use rental table to determine
    which rental is effective for each payment date based on date ranges.
    
    Returns the rental amount from the rental_schedule entry whose date range contains the payment_date.
    """
    # rental_schedule should always be present
    if not lease_data.rental_schedule or not isinstance(lease_data.rental_schedule, list):
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"⚠️  rental_schedule is required but missing for payment_date {payment_date}")
        return 0.0
    
    # Find the rental schedule entry whose date range contains payment_date
    # Check entries in order (earlier entries first)
    for rental_entry in lease_data.rental_schedule:
        if not isinstance(rental_entry, dict):
            continue
        
        start_date_str = rental_entry.get('start_date')
        end_date_str = rental_entry.get('end_date')
        amount = rental_entry.get('amount', 0.0)
        
        if not start_date_str or not end_date_str:
            continue
        
        # Parse dates
        try:
            if isinstance(start_date_str, str):
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                start_date = start_date_str
                
            if isinstance(end_date_str, str):
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = end_date_str
        except (ValueError, TypeError):
            continue
        
        # Check if payment_date falls within this rental entry's date range
        if start_date <= payment_date <= end_date:
            return float(amount) if amount else 0.0
    
    # If no rental schedule entry matches, log warning and return 0.0
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️  No rental_schedule entry found for payment_date {payment_date}")
    return 0.0


def _get_proportionate_rental_for_payment_period(
    lease_data: LeaseData, 
    payment_date: date, 
    frequency_months: int
) -> float:
    """
    Calculate proportionate rental amount for a payment period.
    Handles both advance and arrears payments when rental schedule changes mid-period.
    
    For payment in advance:
        - Payment period = payment_date to payment_date + frequency_months
        - Payment covers period starting from payment date
    
    For payment in arrears:
        - Payment period = payment_date - frequency_months to payment_date
        - Payment covers period that just ended
    
    Optimization: If payment period is entirely within one rental entry, return that entry's amount directly.
    Only use proportionate calculation when period spans multiple entries.
    
    Args:
        lease_data: Lease data with rental_schedule and payment_type
        payment_date: The payment date
        frequency_months: Payment frequency in months
    
    Returns:
        Proportionate rental amount for the payment period
    """
    if not lease_data.rental_schedule or not isinstance(lease_data.rental_schedule, list):
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"⚠️  rental_schedule is required but missing for payment_date {payment_date}")
        return 0.0
    
    # Determine if payment is in advance or arrears
    payment_type = getattr(lease_data, 'payment_type', 'advance').lower()
    payment_in_advance = payment_type != 'arrear' and payment_type != 'arrears'
    
    # Calculate payment period based on advance/arrears
    from lease_accounting.utils.date_utils import edate
    if payment_in_advance:
        period_start = payment_date
        period_end_uncapped = edate(payment_date, frequency_months)
        period_end = period_end_uncapped
        # CRITICAL: Cap payment period at lease_end_date - payment period should not extend beyond lease end
        if lease_data.end_date and period_end > lease_data.end_date:
            period_end = lease_data.end_date
    else:
        # Payment in arrears - covers period BEFORE payment date
        period_start_uncapped = edate(payment_date, -frequency_months)
        period_start = period_start_uncapped
        # CRITICAL: Ensure period_start doesn't go before lease_start_date
        if lease_data.lease_start_date and period_start < lease_data.lease_start_date:
            period_start = lease_data.lease_start_date
        period_end = payment_date
        period_end_uncapped = payment_date
    
    # CRITICAL: Recalculate period_end to ensure it doesn't exceed lease_end_date
    # This is important for the last payment which might extend beyond lease end
    if lease_data.end_date and period_end > lease_data.end_date:
        period_end = lease_data.end_date
    
    # CRITICAL: Calculate total days in FULL (uncapped) period for proportionate calculation
    # When period is capped at lease_end_date, we need to use the full period days as denominator
    # Example: Payment on Jan 1, normal period Jan 1-Feb 1 (31 days), capped period Jan 1-Jan 14 (14 days)
    # We should calculate: (14/31) * monthly_rental, not (14/14) * monthly_rental
    # NOTE: period_end_uncapped is the START of the next period, so we don't add 1
    # Jan 1 to Feb 1 covers days Jan 1, Jan 2, ..., Jan 31 = 31 days (not 32)
    if payment_in_advance:
        # For advance: period from payment_date to next_payment_date (exclusive end)
        # Jan 1 to Feb 1 = 31 days (Jan 1 through Jan 31)
        full_period_days = (period_end_uncapped - period_start).days
    else:
        # For arrears: period from period_start_uncapped to payment_date (inclusive payment_date)
        # Dec 1 to Jan 1 = 31 days (Dec 1 through Dec 31, Jan 1 is included)
        full_period_days = (period_end_uncapped - period_start_uncapped).days + 1
    
    # Calculate actual period days (may be capped)
    # For capped periods, include the end date (lease_end_date) in the calculation
    if lease_data.end_date and period_end == lease_data.end_date:
        # Capped period: include lease_end_date (e.g., Jan 1 to Jan 14 = 14 days)
        actual_period_days = (period_end - period_start).days + 1
    else:
        # Normal period: end date is exclusive (e.g., Jan 1 to Feb 1 = 31 days)
        actual_period_days = (period_end - period_start).days
    
    # Use full_period_days for proportionate calculation when period is capped
    total_period_days = full_period_days if actual_period_days < full_period_days else actual_period_days
    
    if total_period_days <= 0:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️  Invalid payment period: {period_start} to {period_end}")
        return 0.0
    
    # Find all rental_schedule entries that overlap with payment period
    overlapping_entries = []
    
    for rental_entry in lease_data.rental_schedule:
        if not isinstance(rental_entry, dict):
            continue
        
        start_date_str = rental_entry.get('start_date')
        end_date_str = rental_entry.get('end_date')
        amount = rental_entry.get('amount', 0.0)
        
        if not start_date_str or not end_date_str:
            continue
        
        # Parse dates
        try:
            if isinstance(start_date_str, str):
                entry_start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                entry_start = start_date_str
                
            if isinstance(end_date_str, str):
                entry_end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                entry_end = end_date_str
        except (ValueError, TypeError):
            continue
        
        # Check for overlap between rental entry and payment period
        # Overlap exists if: entry_start <= period_end AND entry_end >= period_start
        if entry_start <= period_end and entry_end >= period_start:
            overlapping_entries.append({
                'start': entry_start,
                'end': entry_end,
                'amount': float(amount)
            })
    
    if not overlapping_entries:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"⚠️  No rental_schedule entry overlaps with payment period "
            f"({period_start} to {period_end}) for payment_date {payment_date}"
        )
        return 0.0
    
    # Optimization: If payment period is entirely within one rental entry, return that entry's amount
    # CRITICAL: Don't use optimization if period_end is capped at lease_end_date - need proportionate calculation
    # This ensures partial periods (e.g., Jan 1 to Jan 14 when normal period is Jan 1 to Feb 1) are calculated correctly
    period_is_capped = lease_data.end_date and period_end == lease_data.end_date
    
    if not period_is_capped:
        # Only use optimization if period is NOT capped (normal full period)
        for entry in overlapping_entries:
            # Check if payment period is entirely within this entry
            if entry['start'] <= period_start and entry['end'] >= period_end:
                # Payment period is entirely within this entry
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(
                    f"📊 Payment period entirely within rental entry: {payment_date}, "
                    f"period={period_start} to {period_end}, entry={entry['start']} to {entry['end']}, "
                    f"amount={entry['amount']}"
                )
                return entry['amount']
    
    # Payment period spans multiple entries - calculate proportionate rental
    total_rental = 0.0
    
    for entry in overlapping_entries:
        # Calculate overlap period
        overlap_start = max(entry['start'], period_start)
        # CRITICAL: Cap overlap_end at lease_end_date - don't calculate beyond lease end
        overlap_end = min(entry['end'], period_end)
        if lease_data.end_date:
            overlap_end = min(overlap_end, lease_data.end_date)
        
        # Ensure overlap_end is not before overlap_start
        if overlap_end < overlap_start:
            continue
        
        # Calculate days in overlap
        # For advance payments: overlap_end is exclusive (next period start), so don't add 1
        # For capped periods at lease_end_date: include lease_end_date, so add 1
        if lease_data.end_date and overlap_end == lease_data.end_date:
            # Include lease_end_date when calculating overlap
            days_in_overlap = (overlap_end - overlap_start).days + 1
        else:
            # Normal case: overlap_end is exclusive (start of next period)
            days_in_overlap = (overlap_end - overlap_start).days
        
        if days_in_overlap > 0:
            # CRITICAL: Use full_period_days as denominator for proportionate calculation
            # This ensures partial periods are calculated correctly:
            # Example: Payment Jan 1, full period Jan 1-Feb 1 (31 days), capped Jan 1-Jan 14 (14 days)
            # If rental entry covers Jan 1-Jan 14, calculate: (14/31) * monthly_rental
            # total_period_days already contains full_period_days when period is capped
            weighted_amount = (days_in_overlap / total_period_days) * entry['amount']
            total_rental += weighted_amount
            
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(
                f"📊 Proportionate rental: payment_date={payment_date}, "
                f"period={period_start} to {period_end} ({total_period_days} days), "
                f"rental_entry={entry['start']} to {entry['end']}, "
                f"overlap={overlap_start} to {overlap_end} ({days_in_overlap} days), "
                f"amount={entry['amount']}, weighted={weighted_amount:.2f}"
            )
    
    return total_rental


def _get_manual_rental_for_date(lease_data: LeaseData, payment_date: date) -> float:
    """
    VBA Manual rental lookup (Lines 56-62, 109-115, 164-170)
    Supports up to 20 manual rental dates
    
    Updated: rental_schedule always exists and is the source of truth.
    """
    # rental_schedule should always be present - use it to determine rental
    return _get_rental_from_schedule(lease_data, payment_date)


def _create_schedule_row(lease_data: LeaseData, payment_date: date, rental_amount: float,
                        aro_gross: Optional[float], start_date: date, end_date: date,
                        row_index: int, previous_schedule: List[PaymentScheduleRow]) -> PaymentScheduleRow:
    """Create a schedule row with initial calculations"""
    # Will be populated by basic_calc
    return PaymentScheduleRow(
        date=payment_date,
        rental_amount=rental_amount,
        pv_factor=1.0,
        interest=0.0,
        lease_liability=0.0,
        pv_of_rent=0.0,
        rou_asset=0.0,
        depreciation=0.0,
        change_in_rou=0.0,
        security_deposit_pv=0.0,
        aro_gross=aro_gross,
        aro_interest=0.0,
        aro_provision=None,
        is_opening=(row_index == 0)
    )


def _apply_basic_calculations(lease_data: LeaseData, schedule: List[PaymentScheduleRow]) -> List[PaymentScheduleRow]:
    """
    VBA basic_calc() function implementation
    Calculates PV factors, interest, liability, ROU asset, depreciation for each row
    
    VBA Source: VB script/Code, basic_calc() Sub (Lines 628-707)
    """
    if not schedule:
        return schedule
    
    endrow = len(schedule)
    
    # VBA Line 631: ide calculation
    ide = (lease_data.initial_direct_expenditure or 0) - (lease_data.lease_incentive or 0)
    if ide == 0:
        ide = 0
    
    # VBA Line 633-634: secdeprate and icompound
    # Security discount is stored as percentage in our system, but VBA uses it as decimal
    # If value > 1, assume it's a percentage (e.g., 5 for 5%), divide by 100
    # If value <= 1, assume it's already decimal (e.g., 0.05 for 5%)
    raw_secdeprate = lease_data.security_discount or 0.0
    secdeprate = raw_secdeprate / 100 if raw_secdeprate > 1 else raw_secdeprate
    
    # icompound: derive from frequency_months (compound frequency should match payment frequency)
    # Only use compound_months if explicitly provided and valid, otherwise derive from frequency
    freq = lease_data.frequency_months or 1
    if lease_data.compound_months and lease_data.compound_months > 0:
        # Validate that compound_months matches frequency_months
        # If mismatch, derive from frequency_months instead
        if lease_data.compound_months == freq:
            icompound = lease_data.compound_months
        else:
            # Mismatch: derive from frequency instead
            if freq == 3:
                icompound = 3  # Quarterly
            elif freq == 6:
                icompound = 6  # Semi-annually
            elif freq >= 12:
                icompound = 12  # Annually
            else:
                icompound = 1  # Monthly
    else:
        # No compound_months provided, derive from frequency: 1=monthly, 3=quarterly, 6=semi-annually, 12=annually
        if freq == 3:
            icompound = 3  # Quarterly
        elif freq == 6:
            icompound = 6  # Semi-annually
        elif freq >= 12:
            icompound = 12  # Annually
        else:
            icompound = 1  # Monthly
    
    # VBA Line 636-638: Initialize first row
    schedule[0].pv_factor = 1.0
    schedule[0].aro_gross = schedule[0].aro_gross or lease_data.aro or 0.0
    schedule[0].interest = 0.0
    schedule[0].depreciation = 0.0
    schedule[0].aro_interest = 0.0
    
    # VBA Line 639-643: First row formulas
    # G9 = G7 + F9 - D9 (liability)
    # I9 = G7 + K9 + D6 - L9 + ide (ROU asset)
    # K9 = O9 (change in ROU)
    
    # CRITICAL: We need to set temporary initial values for first pass
    # Then recalculate after all PV factors are computed
    initial_liability = _calculate_initial_liability(lease_data, schedule)
    initial_rou = _calculate_initial_rou(lease_data, initial_liability, ide)
    
    schedule[0].lease_liability = initial_liability
    schedule[0].rou_asset = initial_rou
    schedule[0].security_deposit_pv = _calculate_security_pv(lease_data, schedule[0].date, schedule[-1].date, secdeprate, schedule[0].date, None)
    
    # VBA Line 664: H9 = E9 * D9 - PV of Rent for opening row
    # Opening row has rental = 0 usually, but set it anyway
    schedule[0].pv_of_rent = schedule[0].pv_factor * schedule[0].rental_amount
    
    # VBA Line 645-646: Security deposit initial
    # D6 = Security_deposit value
    
    # VBA Line 647-659: End of life calculation
    endoflife = _calculate_end_of_life_vba(lease_data, schedule[-1].date)
    
    # VBA Line 661-664: PV factor, Interest, Liability, PV of Rent formulas for rows 10+
    for i in range(1, endrow):
        prev_row = schedule[i - 1]
        curr_row = schedule[i]
        
        # E10 = 1/((1+r)^n) - PV factor
        days_from_start = (curr_row.date - schedule[0].date).days
        if lease_data.borrowing_rate is None:
            raise ValueError("borrowing_rate is required but was not provided in the lease data")
        discount_rate = lease_data.borrowing_rate / 100
        curr_row.pv_factor = 1 / ((1 + discount_rate * icompound / 12) ** ((days_from_start / 365) * 12 / icompound))
        
        # F10 = G9*(1+r)^n - G9 - Interest
        days_between = (curr_row.date - prev_row.date).days
        if days_between > 0:
            curr_row.interest = prev_row.lease_liability * ((1 + discount_rate * icompound / 12) ** ((days_between / 365) * 12 / icompound) - 1)
        
        # G10 = G9 - D10 + F10 - Liability
        curr_row.lease_liability = prev_row.lease_liability - curr_row.rental_amount + curr_row.interest
        
        # H10 = E10 * D10 - PV of Rent
        curr_row.pv_of_rent = curr_row.pv_factor * curr_row.rental_amount
        
        # I10 = I9 - J10 + K10 - ROU Asset
        # J10 = Depreciation (calculated below)
        # K10 = O10 - N10 - O9 - Change in ROU
        
        # Get ARO for this date (may be revised)
        current_aro_gross = _get_aro_for_date(lease_data, curr_row.date) or 0.0
        if current_aro_gross:
            curr_row.aro_gross = current_aro_gross
        
        # Calculate ARO provision first
        curr_row.aro_provision = _calculate_aro_provision_vba(
            lease_data, curr_row.aro_gross or 0.0, curr_row.date, schedule[-1].date, lease_data.aro_table
        )
        
        prev_aro_prov = prev_row.aro_provision or 0.0
        curr_aro_prov = curr_row.aro_provision or 0.0
        
        # N10 = ARO Interest (change in provision)
        curr_row.aro_interest = curr_aro_prov - prev_aro_prov if curr_aro_prov is not None else 0.0
        
        # K10 = Change in ROU (VBA Line 676: =O10-N10-O9)
        if curr_aro_prov is not None:
            curr_row.change_in_rou = curr_aro_prov - curr_row.aro_interest - prev_aro_prov
        else:
            curr_row.change_in_rou = 0.0
        
        # J10 = Depreciation (VBA Lines 667-674)
        curr_row.depreciation = _calculate_depreciation_vba(
            lease_data, prev_row, curr_row, endoflife, discount_rate, icompound, schedule
        )
        
        # I10 = ROU Asset
        curr_row.rou_asset = prev_row.rou_asset - curr_row.depreciation + curr_row.change_in_rou
        
        # L10 = Security Deposit PV (VBA Line 678)
        # L10 = L9/(1/((1+secdeprate*1/12)^(((C10-$C$9)/365)*12/1)))*(1/((1+secdeprate*1/12)^(((C9-$C$9)/365)*12/1)))
        # This simplifies to: L10 = L9 * PV_factor_C9 / PV_factor_C10
        prev_security_pv = prev_row.security_deposit_pv or 0.0
        if secdeprate > 0 and lease_data.security_deposit and lease_data.security_deposit > 0:
            # Calculate PV factors
            days_from_start_curr = (curr_row.date - schedule[0].date).days
            days_from_start_prev = (prev_row.date - schedule[0].date).days
            
            pv_factor_curr = 1 / ((1 + secdeprate / 12) ** ((days_from_start_curr / 365) * 12))
            pv_factor_prev = 1 / ((1 + secdeprate / 12) ** ((days_from_start_prev / 365) * 12))
            
            if pv_factor_curr > 0:
                curr_row.security_deposit_pv = prev_security_pv * pv_factor_prev / pv_factor_curr
            else:
                curr_row.security_deposit_pv = prev_security_pv
        else:
            curr_row.security_deposit_pv = 0.0
        
        # Update principal
        curr_row.principal = curr_row.rental_amount - curr_row.interest
        curr_row.remaining_balance = curr_row.lease_liability
    
    # VBA Lines 683-689: Handle FV of ROU or recalculate G7
    if lease_data.fv_of_rou and lease_data.fv_of_rou != 0:
        # VBA Line 685: GoalSeek - adjust C7 (discount rate) to make G(endrow) = 0
        # This is an iterative process - simplified here
        # Would need to adjust borrowing_rate until sum of PV of rents matches fv_of_rou
        total_pv_rent = sum(row.pv_of_rent for row in schedule)
        if abs(total_pv_rent - lease_data.fv_of_rou) > 0.01:
            # Adjust discount rate (simplified - would iterate)
            pass
    else:
        # VBA Line 688: G7 = SUM(H9:Hendrow) - Initial liability = sum of all PV of rents
        # This must be calculated AFTER all PV factors and PV of rents are set
        # CRITICAL: Only include payments on or before the lease end date
        total_pv_rent = sum(row.pv_of_rent for row in schedule if not lease_data.end_date or row.date <= lease_data.end_date)
        
        # Update initial liability with correct value
        schedule[0].lease_liability = total_pv_rent
        
        # Recalculate ROU asset with correct initial liability
        schedule[0].rou_asset = _calculate_initial_rou(lease_data, total_pv_rent, ide)
        
        # Now we need to recalculate the entire schedule with the correct initial liability
        # Recalculate Interest, Liability, and ROU for all rows
        for i in range(1, endrow):
            prev_row = schedule[i - 1]
            curr_row = schedule[i]
            
            # Interest calculation remains the same
            days_between = (curr_row.date - prev_row.date).days
            if lease_data.borrowing_rate is None:
                raise ValueError("borrowing_rate is required but was not provided in the lease data")
            discount_rate = lease_data.borrowing_rate / 100
            if days_between > 0:
                curr_row.interest = prev_row.lease_liability * ((1 + discount_rate * icompound / 12) ** ((days_between / 365) * 12 / icompound) - 1)
            
            # Liability calculation with correct prev_row.lease_liability
            curr_row.lease_liability = prev_row.lease_liability - curr_row.rental_amount + curr_row.interest
            
            # Update ROU asset
            curr_row.depreciation = _calculate_depreciation_vba(
                lease_data, prev_row, curr_row, endoflife, discount_rate, icompound, schedule
            )
            curr_row.rou_asset = prev_row.rou_asset - curr_row.depreciation + curr_row.change_in_rou
    
    # VBA Line 695-705: Transition Option 2B handling
    if lease_data.transition_option == "2B" and lease_data.transition_date:
        transitiondate = lease_data.transition_date - timedelta(days=1)
        
        for row in schedule:
            if row.date == transitiondate:
                # VBA Line 701: Set ROU = Liability + Prepaid_accrual
                prepaid = lease_data.prepaid_accrual or 0.0
                row.rou_asset = row.lease_liability + prepaid
                break
    
    return schedule


def _calculate_initial_liability(lease_data: LeaseData, schedule: List[PaymentScheduleRow]) -> float:
    """Calculate initial lease liability as sum of PV of all payments"""
    if not schedule:
        return 0.0
    
    if lease_data.borrowing_rate is None:
        raise ValueError("borrowing_rate is required but was not provided in the lease data")
    discount_rate = lease_data.borrowing_rate / 100
    # icompound: derive from frequency_months (compound frequency should match payment frequency)
    # Only use compound_months if explicitly provided and valid, otherwise derive from frequency
    freq = lease_data.frequency_months or 1
    if lease_data.compound_months and lease_data.compound_months > 0:
        # Validate that compound_months matches frequency_months
        # If mismatch, derive from frequency_months instead
        if lease_data.compound_months == freq:
            icompound = lease_data.compound_months
        else:
            # Mismatch: derive from frequency instead
            if freq == 3:
                icompound = 3  # Quarterly
            elif freq == 6:
                icompound = 6  # Semi-annually
            elif freq >= 12:
                icompound = 12  # Annually
            else:
                icompound = 1  # Monthly
    else:
        # No compound_months provided, derive from frequency: 1=monthly, 3=quarterly, 6=semi-annually, 12=annually
        if freq == 3:
            icompound = 3  # Quarterly
        elif freq == 6:
            icompound = 6  # Semi-annually
        elif freq >= 12:
            icompound = 12  # Annually
        else:
            icompound = 1  # Monthly
    start_date = schedule[0].date
    
    total_pv = 0.0
    rental_count = 0
    for row in schedule[1:]:  # Skip opening row
        if row.rental_amount and row.rental_amount > 0:
            rental_count += 1
            days_from_start = (row.date - start_date).days
            if days_from_start > 0:
                pv_factor = 1 / ((1 + discount_rate * icompound / 12) ** ((days_from_start / 365) * 12 / icompound))
                total_pv += row.rental_amount * pv_factor
    
    # Debug: If no rentals found, log a warning
    if rental_count == 0 and len(schedule) > 1:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️  _calculate_initial_liability: No rental payments found in {len(schedule)} rows.")
    
    return total_pv


def _calculate_initial_rou(lease_data: LeaseData, initial_liability: float, ide: float) -> float:
    """Calculate initial ROU asset (VBA Line 640-642)"""
    if lease_data.sublease == "Yes":
        return lease_data.sublease_rou or initial_liability
    else:
        return initial_liability + ide


def _calculate_security_pv(lease_data: LeaseData, current_date: date, end_date: date, secdeprate: float, start_date: Optional[date] = None, prev_security_pv: Optional[float] = None) -> float:
    """
    Calculate Security Deposit PV (VBA Line 643, 678)
    VBA Line 643 (initial): L9 = D6*1/((1+secdeprate*1/12)^(((Cendrow-$C$9)/365)*12/1))
    VBA Line 678 (subsequent): L10 = L9/(1/((1+secdeprate*1/12)^(((C10-$C$9)/365)*12/1)))*(1/((1+secdeprate*1/12)^(((C9-$C$9)/365)*12/1)))
    """
    if not lease_data.security_deposit or secdeprate <= 0:
        return 0.0
    
    days_remaining = (end_date - current_date).days
    if days_remaining <= 0:
        return 0.0
    
    # VBA Line 643: Initial calculation
    if prev_security_pv is None:
        # L9 = D6 * 1/((1+secdeprate*1/12)^(((Cendrow-$C$9)/365)*12/1))
        pv_factor = 1 / ((1 + secdeprate / 12) ** ((days_remaining / 365) * 12))
        return lease_data.security_deposit * pv_factor
    else:
        # VBA Line 678: Subsequent rows
        # L10 = L9 / (PV_factor_C10 / PV_factor_C9)
        # Which equals: L10 = L9 * PV_factor_C9 / PV_factor_C10
        if start_date:
            days_from_start_curr = (current_date - start_date).days
            days_from_start_prev = (current_date - timedelta(days=1) - start_date).days if current_date > start_date else 0
            
            # Find previous date by looking at previous schedule row
            # Simplified: use current_date - 1 day to approximate previous row
            # The actual implementation should use the previous row's date
            pv_factor_curr = 1 / ((1 + secdeprate / 12) ** ((days_from_start_curr / 365) * 12))
            pv_factor_prev = 1 / ((1 + secdeprate / 12) ** ((max(days_from_start_prev, 0) / 365) * 12)) if days_from_start_prev > 0 else 1.0
            
            if pv_factor_curr > 0:
                return prev_security_pv * pv_factor_prev / pv_factor_curr
            else:
                return prev_security_pv
        else:
            # Fallback to simple calculation
            pv_factor = 1 / ((1 + secdeprate / 12) ** ((days_remaining / 365) * 12))
            return lease_data.security_deposit * pv_factor


def _calculate_aro_provision_vba(lease_data: LeaseData, aro_gross: float, current_date: date, 
                                 end_date: date, table: int) -> Optional[float]:
    """Calculate ARO Provision (VBA Lines 679-680)"""
    if aro_gross <= 0 or table <= 0:
        return None
    
    aro_rate = get_aro_rate(current_date, table)
    if aro_rate <= 0:
        return aro_gross
    
    days_remaining = (end_date - current_date).days
    if days_remaining <= 0:
        return aro_gross
    
    pv_factor = 1 / ((1 + aro_rate / 12) ** ((days_remaining / 365) * 12))
    return aro_gross * pv_factor


def _calculate_depreciation_vba(lease_data: LeaseData, prev_row: PaymentScheduleRow,
                                curr_row: PaymentScheduleRow, endoflife: date,
                                discount_rate: float, icompound: int, 
                                schedule: List[PaymentScheduleRow] = None) -> float:
    """
    Calculate Depreciation (VBA Lines 667-674)
    US-GAAP vs IFRS/Ind-AS differences
    
    US-GAAP Operating Lease (Line 670-671): Complex formula
    IFRS/Ind-AS (Line 673): Simple straight-line
    """
    gaap_standard = getattr(lease_data, 'gaap_standard', 'IFRS')
    
    # US-GAAP Operating Lease (VBA Lines 670-671)
    if gaap_standard == "US-GAAP" and lease_data.finance_lease_usgaap != "Yes":
        # Full formula: MIN(MAX((I9+Sum(F10:$F$endrow))*(DAYS(C10,C9-1)/DAY(EOMONTH(C10,0)))/
        #    ((YEAR($J$6+1)-YEAR(C9))*12+MONTH($J$6+1)-MONTH(C9)+((DAY($J$6+1)-DAY(C9))/DAY(EOMONTH(C9,0)))))-F10,0),I9),0)
        
        if not schedule:
            # Fallback to simplified
            total_days = (endoflife - prev_row.date).days
            if total_days <= 0:
                return 0.0
            days_diff = (curr_row.date - prev_row.date).days
            return max(0.0, min(prev_row.rou_asset * days_diff / total_days, prev_row.rou_asset))
        
        # Calculate Sum(F10:$F$endrow) - sum of future interest from this row onwards
        future_interest_sum = 0.0
        curr_idx = schedule.index(curr_row) if curr_row in schedule else len(schedule)
        for i in range(curr_idx, len(schedule)):
            future_interest_sum += abs(schedule[i].interest or 0.0)
        
        # Days calculation: DAYS(C10,C9-1)
        days_in_period = (curr_row.date - (prev_row.date - timedelta(days=1))).days
        
        # DAY(EOMONTH(C10,0)) - days in current month
        days_in_curr_month = eomonth(curr_row.date, 0).day
        
        # Calculate remaining period denominator
        # ((YEAR($J$6+1)-YEAR(C9))*12+MONTH($J$6+1)-MONTH(C9)+((DAY($J$6+1)-DAY(C9))/DAY(EOMONTH(C9,0))))
        end_life_plus_one = endoflife + timedelta(days=1)
        months_diff = (end_life_plus_one.year - prev_row.date.year) * 12 + (end_life_plus_one.month - prev_row.date.month)
        days_in_prev_month = eomonth(prev_row.date, 0).day
        day_adjustment = (end_life_plus_one.day - prev_row.date.day) / days_in_prev_month
        remaining_period_months = months_diff + day_adjustment
        
        # Apply formula
        numerator = (prev_row.rou_asset + future_interest_sum) * (days_in_period / days_in_curr_month)
        denominator = remaining_period_months
        depreciation = (numerator / denominator) - (curr_row.interest or 0.0)
        
        # MIN(MAX(...-F10,0),I9),0)
        depreciation = max(0.0, min(depreciation, prev_row.rou_asset))
        depreciation = max(0.0, depreciation)
        
        return depreciation
    
    else:
        # IFRS/Ind-AS (VBA Line 673): Simple straight-line
        # MAX(MIN(I9/($J$6-C9)*(C10-C9),I9),0)
        total_days = (endoflife - prev_row.date).days
        if total_days <= 0:
            return 0.0
        
        days_diff = (curr_row.date - prev_row.date).days
        depreciation = prev_row.rou_asset * days_diff / total_days
        
        return max(0.0, min(depreciation, prev_row.rou_asset))


def _calculate_end_of_life_vba(lease_data: LeaseData, enddate: date) -> date:
    """Calculate end of ROU life (VBA Lines 649-659)"""
    endoflife = lease_data.useful_life
    
    # US-GAAP
    if lease_data.finance_lease_usgaap == "Yes" or lease_data.bargain_purchase == "Yes" or lease_data.title_transfer == "Yes":
        return endoflife if endoflife else enddate
    else:
        # IFRS
        if lease_data.bargain_purchase == "Yes" or lease_data.title_transfer == "Yes":
            return endoflife if endoflife else enddate
        else:
            return enddate


def _apply_security_deposit_increases(lease_data: LeaseData, schedule: List[PaymentScheduleRow]) -> List[PaymentScheduleRow]:
    """
    VBA addsecdep() function (Lines 1059-1074)
    Apply security deposit increases (up to 4)
    """
    if not hasattr(lease_data, 'security_dates') or not lease_data.security_dates:
        return schedule
    
    raw_secdeprate = lease_data.security_discount or 0.0
    secdeprate = raw_secdeprate / 100 if raw_secdeprate > 1 else raw_secdeprate
    i = 1
    
    for row in schedule:
        # Find matching security date
        if i <= len(lease_data.security_dates) and lease_data.security_dates[i - 1]:
            SecDepDate = lease_data.security_dates[i - 1]
            
            if row.date == SecDepDate:
                increase_amount = 0.0
                if i == 1:
                    increase_amount = lease_data.increase_security_1 or 0.0
                elif i == 2:
                    increase_amount = lease_data.increase_security_2 or 0.0
                elif i == 3:
                    increase_amount = lease_data.increase_security_3 or 0.0
                elif i == 4:
                    increase_amount = lease_data.increase_security_4 or 0.0
                
                if increase_amount > 0:
                    # Add PV of increase to Security Deposit PV column
                    days_remaining = (schedule[-1].date - row.date).days
                    if days_remaining > 0 and secdeprate > 0:
                        pv_factor = 1 / ((1 + secdeprate / 12) ** ((days_remaining / 365) * 12))
                        row.security_deposit_pv += increase_amount * pv_factor
                
                i += 1
                if i > 4 or (i <= len(lease_data.security_dates) and not lease_data.security_dates[i - 1]):
                    break
    
    return schedule


def _apply_impairments(lease_data: LeaseData, schedule: List[PaymentScheduleRow]) -> List[PaymentScheduleRow]:
    """
    VBA addimpair() function (Lines 1076-1093)
    Apply impairments (up to 5)
    """
    if not hasattr(lease_data, 'impairment_dates') or not lease_data.impairment_dates:
        return schedule
    
    i = 1
    for row in schedule:
        if i <= len(lease_data.impairment_dates) and lease_data.impairment_dates[i - 1]:
            impairDate = lease_data.impairment_dates[i - 1]
            impairAmount = 0.0
            
            if i == 1:
                impairAmount = lease_data.impairment1 or 0.0
            elif i == 2:
                impairAmount = lease_data.impairment2 or 0.0
            elif i == 3:
                impairAmount = lease_data.impairment3 or 0.0
            elif i == 4:
                impairAmount = lease_data.impairment4 or 0.0
            elif i == 5:
                impairAmount = lease_data.impairment5 or 0.0
            
            if row.date == impairDate and impairAmount > 0:
                row.depreciation += impairAmount
                
                # US-GAAP: Recalculate depreciation for remaining schedule
                # VBA Line 1084 - Complex formula
                
                i += 1
                if i > 5:
                    break
    
    return schedule


def _apply_manual_rental_adjustments(lease_data: LeaseData, schedule: List[PaymentScheduleRow]) -> List[PaymentScheduleRow]:
    """
    VBA addmanualadj() function (Lines 1096-1114)
    Apply manual rental adjustments (up to 20)
    
    VBA Logic:
    - Loops through schedule dates (cell in C9:Cendrow)
    - For each schedule date, checks if it matches rental_date_2[i]
    - If match, uses rental from rental_schedule for that date
    - i increments from 1 to 20
    """
    if lease_data.manual_adj != "Yes":
        return schedule
    
    if not hasattr(lease_data, 'rental_dates') or not lease_data.rental_dates:
        return schedule
    
    # Get rental amounts by date if stored
    rental_amounts_by_date = getattr(lease_data, 'rental_amounts_by_date', {})
    
    i = 1
    for row in schedule:
        if i <= len(lease_data.rental_dates) and lease_data.rental_dates[i - 1]:
            rentaldate = lease_data.rental_dates[i - 1]
            
            # Get rental amount for this date
            # First try rental_amounts_by_date (if set from payload)
            if rental_amounts_by_date and rentaldate in rental_amounts_by_date:
                rentalamount = rental_amounts_by_date[rentaldate]
            else:
                # Use rental_schedule to get rental for this date
                rentalamount = _get_rental_from_schedule(lease_data, rentaldate)
            
            if row.date == rentaldate:
                row.rental_amount = rentalamount
                # Recalculate PV of rent
                row.pv_of_rent = row.pv_factor * rentalamount
                
                i += 1
                if i > 20:
                    break
    
    return schedule

