"""
Projection Calculator
Calculates future period projections for lease accounting

VBA Source: VB script/Code, compu() Sub (Lines 510-568)
VBA Projection Loop:
  - Lines 512-513: projectionmode increment and baldatep = EoMonth(baldatep, A4.Value)
  - Lines 526-533: Find closing balances at projection date (pfindclosing)
  - Lines 537-546: Calculate period activity (pfindPL): depreciation, interest, rent
  - Lines 548-550: Store in AD4, AC4, AE4, AF4, AG4 columns
"""

from datetime import date
from typing import List, Dict, Optional
from dateutil.relativedelta import relativedelta
import logging
from lease_accounting.core.models import LeaseData, PaymentScheduleRow
from lease_accounting.utils.date_utils import eomonth

logger = logging.getLogger(__name__)


class ProjectionCalculator:
    """
    Calculates projection periods showing future balances and activity
    VBA Source: Lines 510-568 (Projections loop)
    """
    
    def __init__(self, schedule: List[PaymentScheduleRow], lease_data: LeaseData):
        self.schedule = schedule
        self.lease_data = lease_data
        
    def calculate_projections(
        self, 
        balance_date: date,
        projection_periods: int = 3,
        period_months: int = 3,
        enable_projections: bool = True
    ) -> List[Dict[str, any]]:
        """
        Calculate projection periods
        VBA: Projections loop (Lines 510-568)
        
        Args:
            balance_date: Current balance date (to_date)
            projection_periods: Number of periods to calculate (max 6, like VBA)
            period_months: Months per period (from A4 in VBA)
            enable_projections: Whether projections are enabled (A3 in VBA)
        
        Returns:
            List of projection dicts, each containing:
            - projection_mode: 1-6
            - projection_date: Future date
            - closing_liability: Liability at projection date
            - closing_rou_asset: ROU Asset at projection date
            - depreciation: Sum of depreciation in period
            - interest: Sum of interest in period
            - rent_paid: Sum of rent paid in period
        """
        if not enable_projections or projection_periods <= 0:
            return []
        
        projections = []
        baldatep = balance_date  # VBA: baldatep = baldate
        projectionmode = 0
        max_projections = min(projection_periods, 6)  # VBA: projectionmode < 6
        
        # Sublease multiplier (VBA Line 362)
        subl = -1 if self.lease_data.sublease == "Yes" else 1
        
        # VBA Line 386: forceenddate = Max(date_modified, termination_date)
        # VBA Line 511: If forceenddate <= baldate And forceenddate <> 0 Then GoTo skip_projections
        # This means: if lease was terminated/modified on or before balance_date, skip projections
        # However, VBA logic allows projections when schedule extends beyond termination_date
        # We should only skip if schedule data doesn't extend beyond termination_date
        forceenddate = None
        if self.lease_data.date_modified and self.lease_data.termination_date:
            forceenddate = max(self.lease_data.date_modified, self.lease_data.termination_date)
        elif self.lease_data.date_modified:
            forceenddate = self.lease_data.date_modified
        elif self.lease_data.termination_date:
            forceenddate = self.lease_data.termination_date
        
        # VBA Line 511: If forceenddate <= baldate And forceenddate <> 0 Then GoTo skip_projections
        # However, if schedule data exists beyond termination_date AND beyond balance_date, allow projections
        # This handles cases where lease was modified but schedule continues
        if forceenddate:
            # Find max schedule date
            max_schedule_check = None
            for row in self.schedule:
                row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
                if row_date:
                    if max_schedule_check is None or row_date > max_schedule_check:
                        max_schedule_check = row_date
            
            # VBA Line 511: If forceenddate <= balance_date, skip projections
            # BUT: If schedule extends beyond balance_date, we can still project forward
            if forceenddate <= balance_date:
                # Only skip if max schedule date is at or before balance_date (no future to project)
                if not max_schedule_check or max_schedule_check <= balance_date:
                    return []
        
        # If forceenddate is after balance_date (future modification), can't project into that period
        if forceenddate and forceenddate > balance_date:
            # Can't project into a future modification - return empty
            return []
        
        # Check if there's any schedule data after balance_date for projections
        # If balance_date is beyond all schedule dates, we can't project forward
        max_schedule_date = None
        for row in self.schedule:
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if row_date:
                if max_schedule_date is None or row_date > max_schedule_date:
                    max_schedule_date = row_date
        
        # If balance_date is beyond max_schedule_date, start from max_schedule_date
        # This ensures we can still calculate projections even when to_date extends beyond lease end
        if max_schedule_date and balance_date > max_schedule_date:
            balance_date = max_schedule_date
        
        # If balance_date equals lease end exactly, find the last date before lease end to project from
        if self.lease_data.end_date and balance_date == self.lease_data.end_date:
            dates_before_end = [row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None) 
                               for row in self.schedule 
                               if (row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)) 
                               and (row.date if hasattr(row, 'date') else row.payment_date) < self.lease_data.end_date]
            if dates_before_end:
                balance_date = max(dates_before_end)
        
        baldatep = balance_date
        
        while projectionmode < max_projections:
            projectionmode += 1  # VBA Line 513
            
            # Reset period activity counters
            deprp = 0.0  # VBA Line 514
            inttp = 0.0  # VBA Line 515
            RentPaidp = 0.0  # VBA Line 516
            
            opendatep = baldatep  # VBA Line 521
            # VBA Line 522: baldatep = EoMonth(baldatep, A4.Value)
            # Note: VBA EoMonth adds months and returns end of month
            baldatep = self._eomonth_add(baldatep, period_months)
            
            # VBA Line 525: If End_date < baldatep Then GoTo pfindPL
            if self.lease_data.end_date and self.lease_data.end_date < baldatep:
                # Calculate period activity up to end_date instead
                baldatep = self.lease_data.end_date
            
            # If projection date hasn't advanced past opening date, we've reached the end
            if baldatep <= opendatep:
                break
            
            # VBA Lines 526-533: pfindclosing - Find closing balances at baldatep
            closing_liability_p, closing_rou_p = self._find_closing_at_date(baldatep)
            
            # VBA Lines 537-546: pfindPL - Calculate period activity
            # Sum depreciation, interest, rent between opendatep and baldatep
            deprp, inttp, RentPaidp = self._calculate_period_activity(
                opendatep, baldatep
            )
            
            # VBA Lines 548-550: Store results
            # AD4 = closing_liability, AC4 = closing_rou
            # AE4 = depreciation, AF4 = interest, AG4 = rent
            projection = {
                'projection_mode': projectionmode,
                'projection_date': baldatep.isoformat(),
                'closing_liability': closing_liability_p * subl,
                'closing_rou_asset': closing_rou_p * subl,
                'depreciation': deprp * subl,
                'interest': inttp * subl,
                'rent_paid': RentPaidp * subl,
            }
            
            projections.append(projection)
            
            # VBA Line 536: If End_date < opendatep Then GoTo Projections
            # Continue if we've reached lease end (allows showing final balances)
            # Only stop if we're trying to project beyond lease end and already showed lease end
            if self.lease_data.end_date and self.lease_data.end_date < opendatep:
                break
            # If we just projected to lease end, stop further projections
            if self.lease_data.end_date and baldatep >= self.lease_data.end_date and projectionmode > 1:
                break
            
            # Update baldatep for next iteration
            if projectionmode < max_projections:
                baldatep = self._eomonth_add(baldatep, period_months)
        
        return projections
    
    def _eomonth_add(self, date_val: date, months: int) -> date:
        """
        VBA: WorksheetFunction.EoMonth(baldatep, months)
        Adds months and returns end of month
        """
        # Use the date_utils.eomonth function which correctly ports Excel EOMONTH
        return eomonth(date_val, months)
    
    def _find_closing_at_date(self, target_date: date) -> tuple:
        """
        Find closing liability and ROU asset at projection date
        VBA Lines 526-533: pfindclosing
        VBA: For Each cell In Range("C9:C" & endrow)
             If cell.Value = baldatep Then
                 AD4 = cell.Offset(0, 4).Value (liability)
                 AC4 = cell.Offset(0, 6).Value (ROU)
        Returns: (liability, rou_asset)
        """
        closing_liability = 0.0
        closing_rou = 0.0
        
        # Try exact date match first
        for row in self.schedule:
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if not row_date:
                continue
            
            if row_date == target_date:
                closing_liability = row.lease_liability or 0.0
                closing_rou = row.rou_asset or 0.0
                return (closing_liability, closing_rou)
            
            # Track last row up to target_date
            if row_date <= target_date:
                closing_liability = row.lease_liability or 0.0
                closing_rou = row.rou_asset or 0.0
            elif row_date > target_date:
                # Interpolate - use previous row's values (VBA copies from previous row)
                break
        
        return (closing_liability, closing_rou)
    
    def _calculate_period_activity(
        self, 
        from_date: date, 
        to_date: date
    ) -> tuple:
        """
        Calculate period activity between from_date and to_date
        VBA Lines 537-546: pfindPL
        VBA: For cell.Value > opendatep And cell.Value <= baldatep
             deprp = deprp + cell.Offset(0, 7).Value (depreciation)
             inttp = inttp + cell.Offset(0, 3).Value (interest)
             RentPaidp = RentPaidp + cell.Offset(0, 1).Value (rental)
        
        Returns: (depreciation, interest, rent_paid)
        """
        deprp = 0.0
        inttp = 0.0
        RentPaidp = 0.0
        
        # Handle case where from_date and to_date are same (no period to calculate)
        if from_date >= to_date:
            return (0.0, 0.0, 0.0)
        
        for row in self.schedule:
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if not row_date:
                continue
            
            # VBA: cell.Value > opendatep And cell.Value <= baldatep
            if row_date > from_date and row_date <= to_date:
                deprp += row.depreciation or 0.0  # Column J (offset 7 from C)
                inttp += row.interest or 0.0  # Column F (offset 3 from C)
                RentPaidp += row.rental_amount or 0.0  # Column D (offset 1 from C)
            
            # VBA Line 545: If cell.Value > baldatep Then Exit For
            if row_date > to_date:
                break
        
        return (deprp, inttp, RentPaidp)

