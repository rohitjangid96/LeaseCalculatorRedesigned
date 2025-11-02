"""
Main Lease Processor
Ports compu() VBA function to Python
Handles multi-lease processing with filtering and results generation

VBA Source File: VB script/Code
VBA Function: compu() Sub (Lines 251-624)
  - Main loop: For ai = G2 To G3 (Lines 316-605)
  - Opening balances: Lines 364-381
  - Closing balances: Lines 384-427
  - Period activity: Lines 429-477 (findPL section)
  - Current/Non-current split: Lines 553-566
"""

from datetime import date, datetime, timedelta
from typing import List, Optional
from dateutil.relativedelta import relativedelta
import logging
from lease_accounting.core.models import LeaseData, LeaseResult, ProcessingFilters, PaymentScheduleRow
from lease_accounting.schedule.generator_vba_complete import generate_complete_schedule

logger = logging.getLogger(__name__)


class LeaseProcessor:
    """
    Main lease accounting processor
    Ports Excel compu() function logic
    """
    
    def __init__(self, filters: ProcessingFilters):
        self.filters = filters
        self.lease_results = []
    
    def process_all_leases(self, lease_data_list: List[LeaseData]) -> List[LeaseResult]:
        """
        Process multiple leases
        Main loop equivalent to For ai = G2 To G3 in VBA
        """
        results = []
        
        for lease_data in lease_data_list:
            # Check filters
            if not self.should_process_lease(lease_data):
                continue
            
            # Skip short-term leases
            if self.is_short_term_lease(lease_data):
                continue
            
            # Process single lease
            result = self.process_single_lease(lease_data)
            if result:
                results.append(result)
        
        return results
    
    def should_process_lease(self, lease_data: LeaseData) -> bool:
        """Check if lease passes all filters"""
        
        # Cost center filter
        if self.filters.cost_center_filter and \
           lease_data.cost_centre != self.filters.cost_center_filter:
            return False
        
        # Entity filter
        if self.filters.entity_filter and \
           lease_data.group_entity_name != self.filters.entity_filter:
            return False
        
        # Asset class filter
        if self.filters.asset_class_filter and \
           lease_data.asset_class != self.filters.asset_class_filter:
            return False
        
        # Date filters
        if self.filters.end_date and lease_data.end_date and \
           lease_data.end_date < self.filters.end_date:
            return False
        
        if self.filters.start_date and lease_data.lease_start_date and \
           lease_data.lease_start_date > self.filters.start_date:
            return False
        
        return True
    
    def is_short_term_lease(self, lease_data: LeaseData) -> bool:
        """Check if lease is short-term (to be excluded)"""
        
        if self.filters.gaap_standard == "US-GAAP":
            return lease_data.short_term_lease_usgaap == "Yes"
        else:
            return lease_data.short_term_lease_ifrs == "Yes"
    
    def process_single_lease(self, lease_data: LeaseData) -> Optional[LeaseResult]:
        """
        Process a single lease - equivalent to main loop in compu()
        
        VBA Source: VB script/Code, compu() Sub (Lines 251-624)
        Main processing flow:
          1. Generate schedule (via generate_complete_schedule - VBA datessrent/basic_calc)
          2. Get opening balances (VBA Lines 367-381)
          3. Calculate period activity (VBA Lines 429-477)
          4. Get closing balances (VBA Lines 404-419)
          5. Split current/non-current liability (VBA Lines 553-566)
          6. Create LeaseResult object (VBA Results sheet)
        """
        if not self.filters.start_date or not self.filters.end_date:
            return None
        
        # Generate payment schedule
        schedule = generate_complete_schedule(lease_data)
        
        if not schedule:
            return None
        
        # VBA Line 361: Process lease modifications if applicable
        if lease_data.modifies_this_id and lease_data.modifies_this_id > 0:
            from lease_accounting.core.lease_modifications import process_lease_modifications
            schedule, mod_results = process_lease_modifications(
                lease_data, schedule, self.filters.end_date
            )
            # Store modification results in lease_data for use in results
            lease_data.calculated_fields.update(mod_results)
        
        # Calculate opening balances
        opening_liability, opening_rou, opening_aro, opening_security = self.get_opening_balances(
            schedule, self.filters.start_date
        )
        
        # Calculate period activity (depreciation, interest, rent paid)
        # Pass date_modified if available in lease_data
        date_modified = getattr(lease_data, 'date_modified', None)
        period_activity = self.calculate_period_activity(
            schedule, self.filters.start_date, self.filters.end_date, date_modified
        )
        
        # Calculate closing balances (VBA: baldate = D3)
        closing_liability, closing_rou, closing_aro, closing_security = self.get_closing_balances(
            schedule, self.filters.end_date
        )
        
        # Calculate Current vs Non-Current Liability
        # VBA Source: VB script/Code, compu() Sub (Lines 553-566)
        # 
        # Two methods (controlled by Sheets("A").Range("A5").Value):
        #   Method 0 (A5=0): Sum PV of payments due in next 12 months (Line 543, 560-561)
        #   Method 1 (A5<>0): Max(Total Liability - Projected Liability 12m ahead, 0) (Line 563)
        #
        # CURRENT IMPLEMENTATION: Method 0 (Projection-based calculation)
        # Formula: liacurrent = liacurrent + cell.Offset(0, 1).Value * cell.Offset(0, 2).Value / baldatepv
        # Where:
        #   cell.Offset(0, 1) = Rental amount (column D)
        #   cell.Offset(0, 2) = PV Factor at payment date (column E)
        #   baldatepv = PV factor at balance date (to_date) - VBA Line 410
        
        closing_liability_total = abs(closing_liability) if closing_liability > 0 else 0
        
        # Get PV factor at balance date (baldatepv) - VBA Line 410
        baldatepv = self._get_pv_factor_at_date(
            schedule, self.filters.end_date, lease_data
        )
        
        # Calculate current liability = sum of PV of payments due in next 12 months
        # VBA Line 543: For each payment between balance date and balance date + 12 months
        # VBA: If projectionmode = 1 And Sheets("A").Range("A5").Value = 0 Then
        #      liacurrent = liacurrent + cell.Offset(0, 1).Value * cell.Offset(0, 2).Value / baldatepv
        twelve_months_later = self.filters.end_date + relativedelta(months=12)
        
        liacurrent = 0.0
        for row in schedule:
            # Get row date - PaymentScheduleRow uses 'date' attribute
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if not row_date:
                continue
                
            # Check if payment is in next 12 months after balance date
            # VBA: cell.Value > opendatep And cell.Value <= baldatep (for projection period 1, 12 months)
            if (row_date > self.filters.end_date and 
                row_date <= twelve_months_later and 
                row.rental_amount and row.rental_amount > 0):
                # VBA Line 543: liacurrent = liacurrent + rental * pv_factor / baldatepv
                if baldatepv > 0 and row.pv_factor:
                    liacurrent += row.rental_amount * row.pv_factor / baldatepv
        
        # Apply sublease multiplier (VBA: * subl) - VBA Line 362
        subl = -1 if lease_data.sublease == "Yes" else 1
        liacurrent_final = liacurrent * subl
        
        # VBA Lines 560-561: Current = liacurrent, Non-current = Total - Current
        # Sheets("Results").Range("E4").Offset(num, 0).Formula = liacurrent * subl
        # Sheets("Results").Range("D4").Offset(num, 0).Formula = D4 - liacurrent * subl
        closing_liability_current = abs(liacurrent_final)
        closing_liability_non_current = closing_liability_total - closing_liability_current
        
        # Ensure non-negative (safety check)
        if closing_liability_non_current < 0:
            closing_liability_non_current = 0
            closing_liability_current = closing_liability_total
        
        # TODO: Method 1 (A5 <> 0) - When projection disabled:
        # VBA Line 563: Current = Max(Abs(D4) - Abs(AD4), 0) * subl
        # Where AD4 = projected liability 12 months ahead (requires projection calculation)
        # This would require implementing the full projection logic first
        
        # Calculate Projections (VBA Lines 510-568)
        from lease_accounting.core.projection_calculator import ProjectionCalculator
        
        projection_calc = ProjectionCalculator(schedule, lease_data)
        projections = projection_calc.calculate_projections(
            balance_date=self.filters.end_date,
            projection_periods=self.filters.projection_periods,
            period_months=self.filters.projection_period_months,
            enable_projections=self.filters.enable_projections
        )
        
        # Log for debugging
        logger.info(f"📊 Projections calculated: {len(projections)} periods for lease {lease_data.auto_id}")
        if projections:
            logger.info(f"   First projection: {projections[0].get('projection_date')}, Last: {projections[-1].get('projection_date')}")
        
        # Calculate Security Deposit Current/Non-Current Split (VBA Lines 553-557)
        # VBA Logic:
        #   If projectionmode = 1 Then
        #       If sec_current = 0 Then
        #           N4 (Current) = M4 (Non-current) * subl
        #           M4 (Non-current) = 0
        #       End If
        #   End If
        # Where sec_current = security deposit PV at projection period 1 (12 months ahead)
        closing_security_current = 0.0
        closing_security_non_current = abs(closing_security) if closing_security > 0 else 0.0
        
        if projections and len(projections) > 0:
            # Get security deposit PV at projection period 1 (12 months ahead)
            # VBA Line 530: If projectionmode = 1 Then sec_current = cell.Offset(0, 9).Value
            # We need to find the security deposit PV at the first projection date
            first_projection_date_str = projections[0].get('projection_date')
            if first_projection_date_str:
                from datetime import datetime
                try:
                    first_projection_date = datetime.fromisoformat(first_projection_date_str).date() if isinstance(first_projection_date_str, str) else first_projection_date_str
                    
                    # Find security deposit PV at projection date
                    sec_current_at_projection = 0.0
                    for row in schedule:
                        row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
                        if row_date and row_date == first_projection_date:
                            sec_current_at_projection = row.security_deposit_pv or 0.0
                            break
                        elif row_date and row_date > first_projection_date:
                            # Use previous row's value (interpolation)
                            if len(schedule) > 0:
                                prev_idx = schedule.index(row) - 1
                                if prev_idx >= 0:
                                    sec_current_at_projection = schedule[prev_idx].security_deposit_pv or 0.0
                            break
                    
                    # VBA Line 554: If sec_current = 0 Then
                    # If security deposit at projection date is 0, all is current
                    if abs(sec_current_at_projection) < 0.01:  # Effectively 0
                        closing_security_current = closing_security_non_current * subl
                        closing_security_non_current = 0.0
                    else:
                        # Otherwise, split based on what will be returned in next 12 months
                        # Current portion = difference between current security and security at projection
                        closing_security_current = abs(closing_security - sec_current_at_projection) * abs(subl)
                        closing_security_non_current = abs(sec_current_at_projection) * abs(subl)
                        
                        # Ensure totals match
                        if closing_security_current + closing_security_non_current > abs(closing_security) * 1.01:
                            # Recalculate to ensure accuracy
                            closing_security_current = max(0, (abs(closing_security) - abs(sec_current_at_projection)) * abs(subl))
                            closing_security_non_current = abs(sec_current_at_projection) * abs(subl)
                    
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing projection date for security split: {e}")
                    # Default: keep as non-current
                    closing_security_non_current = abs(closing_security) if closing_security > 0 else 0.0
                    closing_security_current = 0.0
        
        # Calculate missing Results table columns (Z4, AA4, AB4, BB4, BC4, BD4, BE4, BI4)
        # VBA Lines 600-603, 490, 585, 597, 599, 454, 473
        
        # Z4, AA4: Original Lease ID and Modification Indicator (VBA Lines 600-602)
        original_lease_id = self._find_original_lease_id(lease_data)
        modification_indicator = "Modifier" if lease_data.auto_id != original_lease_id else ""
        
        # AB4: Initial ROU Asset (VBA Line 603)
        # If ai = oai And Lease_start_date > opendate And Lease_start_date <= baldate Then AB4 = I9 (initial ROU)
        initial_rou_asset = None
        if (lease_data.auto_id == original_lease_id and  # Only for original leases (not modifiers)
            lease_data.lease_start_date and
            self.filters.start_date and self.filters.end_date and
            self.filters.start_date < lease_data.lease_start_date <= self.filters.end_date):
            # Find initial ROU from schedule (first row after lease start = I9)
            for row in schedule:
                row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
                if row_date and row_date == lease_data.lease_start_date:
                    initial_rou_asset = row.rou_asset or 0.0
                    break
        
        # BB4: Security Deposit Gross (VBA Lines 421-424, 490)
        security_deposit_gross = self._calculate_security_deposit_gross(lease_data, self.filters.end_date)
        
        # BC4: Accumulated Depreciation (VBA Line 585)
        # Only calculated when projections enabled and projection mode 6 exists
        accumulated_depreciation = None
        if projections and len(projections) > 0:
            # VBA: deprp + H4 + J7 (accumulated from Firstdate to opendate + period depreciation + J7)
            # For now, calculate from lease start to end_date
            accumulated_depreciation = self._calculate_accumulated_depreciation(
                schedule, lease_data, self.filters.start_date, self.filters.end_date
            )
        
        # BD4: Initial Direct Expenditure on transition (VBA Line 599)
        initial_direct_expenditure_period = None
        if lease_data.transition_option and lease_data.transition_option != "2B":
            # VBA: If Firstdate >= opendate And Firstdate <= baldate And Transition_option <> "2B"
            first_date = lease_data.transition_date if (lease_data.transition_option == "2B") else lease_data.lease_start_date
            if (first_date and self.filters.start_date and self.filters.end_date and
                self.filters.start_date <= first_date <= self.filters.end_date):
                initial_direct_expenditure_period = lease_data.initial_direct_expenditure or 0.0
        
        # BE4: Prepaid Accrual (VBA Line 597)
        prepaid_accrual_period = None
        if lease_data.transition_date and self.filters.start_date:
            transition_date_minus_one = lease_data.transition_date - timedelta(days=1)
            # VBA: If transitiondate1 <= opendate Then BE4 = Prepaid_accrual
            if transition_date_minus_one <= self.filters.start_date:
                prepaid_accrual_period = lease_data.prepaid_accrual or 0.0
        
        # Calculate Gain/Loss Breakdown Components (VBA Lines 453-473)
        # Get values from modification processing if available
        covid_pe_gain = lease_data.calculated_fields.get('covid_pe_gain', None)
        modification_gain = lease_data.calculated_fields.get('modification_gain', None)
        sublease_gain_loss = lease_data.calculated_fields.get('sublease_gainloss', None)
        sublease_modification_gain_loss = lease_data.calculated_fields.get('sublease_modification_gainloss', None)
        
        # VBA Line 454: COVID PE Gain - only if Lease_start_date in period
        if covid_pe_gain is None:
            if (lease_data.lease_start_date and self.filters.start_date and self.filters.end_date and
                self.filters.start_date < lease_data.lease_start_date <= self.filters.end_date):
                # COVID PE gain is calculated during modification processing (K7)
                # For now, set to 0 if not calculated
                covid_pe_gain = 0.0
        
        # VBA Line 456: Modification Gain - only if Lease_start_date in period
        if modification_gain is None:
            if (lease_data.lease_start_date and self.filters.start_date and self.filters.end_date and
                self.filters.start_date < lease_data.lease_start_date <= self.filters.end_date and
                lease_data.modifies_this_id and lease_data.modifies_this_id > 0):
                # Modification gain is calculated during modification processing (K6)
                # Would need modification processing to calculate properly
                modification_gain = 0.0
        
        # VBA Line 458: Sublease Gain/Loss (initial recognition, not modification)
        if sublease_gain_loss is None:
            if (lease_data.sublease == "Yes" and
                lease_data.lease_start_date and self.filters.start_date and self.filters.end_date and
                self.filters.start_date < lease_data.lease_start_date <= self.filters.end_date and
                (not lease_data.modifies_this_id or lease_data.modifies_this_id <= 0)):
                # VBA: sublease_gainloss = I9 - G9 (ROU Asset - Lease Liability at lease start)
                # Find initial ROU and Liability at lease start
                initial_rou = 0.0
                initial_liability = 0.0
                for row in schedule:
                    row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
                    if row_date and row_date == lease_data.lease_start_date:
                        initial_rou = row.rou_asset or 0.0
                        initial_liability = row.lease_liability or 0.0
                        break
                sublease_gain_loss = initial_rou - initial_liability
        
        # VBA Line 460: Sublease Modification Gain/Loss
        if sublease_modification_gain_loss is None:
            if (lease_data.sublease == "Yes" and
                lease_data.lease_start_date and self.filters.start_date and self.filters.end_date and
                self.filters.start_date < lease_data.lease_start_date <= self.filters.end_date and
                lease_data.modifies_this_id and lease_data.modifies_this_id > 0):
                # Sublease modification gain is calculated during modification processing (K5)
                # Would need modification processing to calculate properly
                sublease_modification_gain_loss = 0.0
        
        # VBA Line 462-468: Termination Gain/Loss (if termination_date in period)
        termination_gain_loss = None
        if (lease_data.termination_date and self.filters.start_date and self.filters.end_date and
            self.filters.start_date < lease_data.termination_date <= self.filters.end_date):
            # Find termination row in schedule
            termination_row = None
            for row in schedule:
                row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
                if row_date and row_date == lease_data.termination_date:
                    termination_row = row
                    break
            
            if termination_row:
                # VBA Line 468: Termination gain = Termination_penalty + ROU - Liability - sec_grossT + Security_PV - ARO_PV + All other gains
                sec_grossT = self._calculate_security_deposit_gross(lease_data, lease_data.termination_date)
                termination_penalty = lease_data.termination_penalty or 0.0
                term_rou = termination_row.rou_asset or 0.0
                term_liability = termination_row.lease_liability or 0.0
                term_security_pv = termination_row.security_deposit_pv or 0.0
                term_aro_pv = termination_row.aro_provision or 0.0
                
                termination_gain_loss = (
                    termination_penalty +
                    term_rou -
                    term_liability -
                    sec_grossT +
                    term_security_pv -
                    term_aro_pv +
                    (covid_pe_gain or 0.0) +
                    (modification_gain or 0.0) +
                    (sublease_gain_loss or 0.0) +
                    (sublease_modification_gain_loss or 0.0)
                )
        
        # Calculate total gain_loss_pnl (VBA Line 468 or 472)
        total_gain_loss = 0.0
        if termination_gain_loss is not None:
            total_gain_loss = termination_gain_loss
        else:
            # VBA Line 472: Non-termination gain = COVID_PE_Gain + modi_gain + sublease_gainloss + sublease_modi_gainloss
            total_gain_loss = (
                (covid_pe_gain or 0.0) +
                (modification_gain or 0.0) +
                (sublease_gain_loss or 0.0) +
                (sublease_modification_gain_loss or 0.0)
            )
        
        # Store individual components for later use
        if covid_pe_gain is None:
            covid_pe_gain = 0.0
        
        # Calculate remaining ROU life (BH4) - VBA Lines 495-497
        remaining_rou_life = None
        if schedule:
            # Find last ROU date (useful_life or end_date)
            last_rou_date = lease_data.useful_life or lease_data.end_date
            if last_rou_date:
                if self.filters.end_date:
                    days_diff = (last_rou_date - self.filters.end_date).days
                    remaining_rou_life = max(0, days_diff)
                    # VBA: If termination_date < baldate Then rem_ROUlife = 0
                    if lease_data.termination_date and lease_data.termination_date < self.filters.end_date:
                        remaining_rou_life = 0
                    # VBA: If date_modified < baldate Then rem_ROUlife = 0
                    if lease_data.date_modified and lease_data.date_modified < self.filters.end_date:
                        remaining_rou_life = 0
        
        # Create result object (matching VBA Results sheet)
        result = LeaseResult(
            lease_id=lease_data.auto_id,
            opening_lease_liability=opening_liability,
            opening_rou_asset=opening_rou,
            interest_expense=period_activity['interest'],
            depreciation_expense=period_activity['depreciation'],
            rent_paid=period_activity['rent_paid'],
            aro_interest=period_activity.get('aro_interest', 0.0),
            security_deposit_change=period_activity.get('security_change', 0.0),
            closing_lease_liability_non_current=closing_liability_non_current,
            closing_lease_liability_current=closing_liability_current,
            closing_rou_asset=closing_rou,
            closing_aro_liability=closing_aro,
            closing_security_deposit=closing_security,
            closing_security_deposit_current=closing_security_current,
            closing_security_deposit_non_current=closing_security_non_current,
            gain_loss_pnl=total_gain_loss,
            # Gain/Loss Breakdown Components
            covid_pe_gain=covid_pe_gain,
            modification_gain=modification_gain,
            sublease_gain_loss=sublease_gain_loss,
            sublease_modification_gain_loss=sublease_modification_gain_loss,
            termination_gain_loss=termination_gain_loss,
            asset_class=lease_data.asset_class,
            cost_center=lease_data.cost_centre,
            currency=lease_data.currency,
            description=lease_data.description,
            asset_code=lease_data.asset_id_code,
            borrowing_rate=lease_data.borrowing_rate,
            projections=projections,
            # Missing columns
            original_lease_id=original_lease_id,
            modification_indicator=modification_indicator,
            initial_rou_asset=initial_rou_asset,
            security_deposit_gross=security_deposit_gross,
            accumulated_depreciation=accumulated_depreciation,
            initial_direct_expenditure_period=initial_direct_expenditure_period,
            prepaid_accrual_period=prepaid_accrual_period,
            remaining_rou_life=remaining_rou_life
        )
        
        return result
    
    def _get_pv_factor_at_date(self, schedule: List[PaymentScheduleRow], 
                               balance_date: date, lease_data: LeaseData) -> float:
        """
        Get PV factor at balance date (baldatepv)
        VBA: Find cell.Value = baldate, get cell.Offset(0, 2).Value (PV factor)
        """
        # First, try to find exact date match
        for row in schedule:
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if row_date == balance_date:
                return row.pv_factor if row.pv_factor else 1.0
        
        # If no exact match, interpolate between surrounding rows
        # Find the row just before and just after balance_date
        prev_row = None
        next_row = None
        
        for i, row in enumerate(schedule):
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if not row_date:
                continue
            if row_date < balance_date:
                prev_row = row
            elif row_date > balance_date:
                next_row = row
                break
        
        # If we have both, interpolate (simplified - use previous row's PV factor)
        if prev_row:
            return prev_row.pv_factor if prev_row.pv_factor else 1.0
        
        # Fallback: calculate PV factor directly
        if schedule:
            if lease_data.borrowing_rate is None:
                raise ValueError("borrowing_rate is required but was not provided in the lease data")
            discount_rate = lease_data.borrowing_rate / 100
            # icompound should be compound_months if provided, otherwise derive from frequency
            if lease_data.compound_months and lease_data.compound_months > 0:
                icompound = lease_data.compound_months
            else:
                # Derive from frequency: 1=monthly, 3=quarterly, 6=semi-annually, 12=annually
                freq = lease_data.frequency_months or 1
                if freq == 3:
                    icompound = 3  # Quarterly
                elif freq == 6:
                    icompound = 6  # Semi-annually
                elif freq >= 12:
                    icompound = 12  # Annually
                else:
                    icompound = 1  # Monthly
            first_row = schedule[0]
            start_date = first_row.date if hasattr(first_row, 'date') else (first_row.payment_date if hasattr(first_row, 'payment_date') else None)
            if not start_date:
                return 1.0
            days_from_start = (balance_date - start_date).days
            
            if days_from_start > 0:
                pv_factor = 1 / ((1 + discount_rate * icompound / 12) ** ((days_from_start / 365) * 12 / icompound))
                return pv_factor
        
        return 1.0
    
    def get_opening_balances(self, schedule: List[PaymentScheduleRow], 
                            balance_date: date) -> tuple:
        """
        Get opening balances at a specific date
        
        VBA Source: VB script/Code, compu() Sub (Lines 367-381)
        VBA Logic:
          1. If cell.Value = opendate: use that row (Line 367)
          2. If cell.Value < opendate And cell.Offset(1, 0).Value > opendate:
             INSERT row with opendate and COPY values from previous row (columns E-O) (Lines 374-380)
        Returns: (liability, rou, aro, security_deposit)
        """
        # VBA logic: find exact match or interpolate by inserting row
        for i, row in enumerate(schedule):
            # Get date from row
            row_date = row.payment_date
            if hasattr(row_date, 'date'):
                row_date = row_date.date()
            elif not isinstance(row_date, date):
                row_date = getattr(row, 'date', row_date)
            
            # Exact match (VBA: If cell.Value = opendate)
            if row_date == balance_date:
                return (row.lease_liability or 0.0, row.rou_asset or 0.0,
                       getattr(row, 'aro_provision', 0.0) or 0.0,
                       getattr(row, 'security_deposit_pv', 0.0) or 0.0)
            
            # Interpolation logic (VBA: If cell.Value < opendate And cell.Offset(1, 0).Value > opendate)
            # If balance_date falls between this row and next row
            if i < len(schedule) - 1:
                next_row = schedule[i + 1]
                next_date = next_row.payment_date
                if hasattr(next_date, 'date'):
                    next_date = next_date.date()
                elif not isinstance(next_date, date):
                    next_date = getattr(next_row, 'date', next_date)
                
                # VBA: inserts row and copies values from current row (columns E-O)
                # In Python: use current row's values (simulates copy)
                if row_date < balance_date < next_date:
                    return (row.lease_liability or 0.0, row.rou_asset or 0.0,
                           getattr(row, 'aro_provision', 0.0) or 0.0,
                           getattr(row, 'security_deposit_pv', 0.0) or 0.0)
        
        # If balance_date is before first row or after last row
        if schedule:
            first_row = schedule[0]
            first_date = first_row.date  # Use .date property directly
            if isinstance(first_date, datetime):
                first_date = first_date.date()
            
            if balance_date < first_date:
                # VBA Line 364: If lease_start_date > opendate, skip opening balance calculation
                # But if opendate is between lease_start and first payment, use first row values
                # For now, return first row's values (which represents opening balances at lease start)
                return (first_row.lease_liability or 0.0, first_row.rou_asset or 0.0,
                       getattr(first_row, 'aro_provision', 0.0) or 0.0,
                       getattr(first_row, 'security_deposit_pv', 0.0) or 0.0)
            else:
                # After lease end - use last row
                last_row = schedule[-1]
                return (last_row.lease_liability or 0.0, last_row.rou_asset or 0.0,
                       getattr(last_row, 'aro_provision', 0.0) or 0.0,
                       getattr(last_row, 'security_deposit_pv', 0.0) or 0.0)
        
        return (0.0, 0.0, 0.0, 0.0)
    
    def get_closing_balances(self, schedule: List[PaymentScheduleRow],
                            balance_date: date) -> tuple:
        """
        Get closing balances at a specific date
        
        VBA Source: VB script/Code, compu() Sub (Lines 404-419)
        VBA Logic:
          1. Force end date check (Line 386): Max(date_modified, termination_date)
          2. If cell.Value = baldate: use that row (Line 405)
          3. If cell.Value < baldate And cell.Offset(1, 0).Value > baldate:
             INSERT row with baldate and COPY values from previous row (columns E-O) (Lines 413-418)
        Returns: (liability, rou, aro, security_deposit)
        """
        closing_liability = 0.0
        closing_rou = 0.0
        closing_aro = 0.0
        closing_security = 0.0
        
        for i, row in enumerate(schedule):
            # Get date from row
            row_date = row.payment_date
            if hasattr(row_date, 'date'):
                row_date = row_date.date()
            elif not isinstance(row_date, date):
                row_date = getattr(row, 'date', row_date)
            
            # Exact match (VBA: If cell.Value = baldate)
            if row_date == balance_date:
                return (row.lease_liability, row.rou_asset, 
                       getattr(row, 'aro_provision', 0.0) or 0.0,
                       getattr(row, 'security_deposit_pv', 0.0) or 0.0)
            
            # Interpolation logic (VBA lines 413-418):
            # If cell.Value < baldate And cell.Offset(1, 0).Value > baldate
            # INSERT row with baldate and COPY values from current row
            if i < len(schedule) - 1:
                next_row = schedule[i + 1]
                next_date = next_row.payment_date
                if hasattr(next_date, 'date'):
                    next_date = next_date.date()
                elif not isinstance(next_date, date):
                    next_date = getattr(next_row, 'date', next_date)
                
                # Balance date falls between two payment dates
                # VBA copies values from current row (simulated here)
                if row_date < balance_date < next_date:
                    return (row.lease_liability, row.rou_asset,
                           getattr(row, 'aro_provision', 0.0) or 0.0,
                           getattr(row, 'security_deposit_pv', 0.0) or 0.0)
            
            # Track last row up to balance_date (for dates after lease end)
            if row_date <= balance_date:
                closing_liability = row.lease_liability or 0.0
                closing_rou = row.rou_asset or 0.0
                closing_aro = getattr(row, 'aro_provision', 0.0) or 0.0
                closing_security = getattr(row, 'security_deposit_pv', 0.0) or 0.0
        
        # Return last tracked values (if balance_date is after all rows)
        # If no values were set, return first row's values as fallback
        if closing_liability == 0 and closing_rou == 0 and schedule:
            first_row = schedule[0]
            closing_liability = first_row.lease_liability or 0.0
            closing_rou = first_row.rou_asset or 0.0
            closing_aro = getattr(first_row, 'aro_provision', 0.0) or 0.0
            closing_security = getattr(first_row, 'security_deposit_pv', 0.0) or 0.0
        
        return (closing_liability, closing_rou, closing_aro, closing_security)
    
    def calculate_period_activity(self, schedule: List[PaymentScheduleRow],
                                  start_date: date, end_date: date, 
                                  date_modified: Optional[date] = None) -> dict:
        """
        Calculate depreciation, interest, and rent paid for period
        
        VBA Source: VB script/Code, compu() Sub, findPL section (Lines 429-477)
        VBA Logic:
          - Line 438: If cell.Value > opendate And cell.Value <= closedate
          - Line 439: Not_modified flag (excludes date_modified from rent_paid)
          - Line 440-444: Accumulate depreciation, interest, changeROU, AROintt, RentPaid
          - Line 445: Security deposit interest (delta calculation)
          - Lines 454-460: Special gains/losses (COVID PE, modification, sublease)
          - Lines 462-474: Termination gain/loss calculation
        Returns: dict with 'depreciation', 'interest', 'rent_paid', 'aro_interest', 'security_change'
        """
        depreciation = 0.0
        interest = 0.0
        rent_paid = 0.0
        aro_interest = 0.0
        security_change = 0.0
        change_rou = 0.0
        
        prev_security_pv = 0.0
        
        for i, row in enumerate(schedule):
            # Skip opening row
            if row.is_opening:
                # Track opening security deposit for delta calculation
                prev_security_pv = row.security_deposit_pv or 0.0
                continue
                
            # Get date from row
            row_date = row.payment_date
            if hasattr(row_date, 'date'):
                row_date = row_date.date()
            elif not isinstance(row_date, date):
                row_date = getattr(row, 'date', row_date)
            
            # VBA Line 438: cell.Value > opendate And cell.Value <= closedate
            # start_date is already opendate (from_date - 1), end_date is closedate (to_date)
            # CRITICAL: VBA uses > (greater than) not >=, so opendate is EXCLUDED
            # Python condition must match: row_date > start_date AND row_date <= end_date
            if start_date < row_date <= end_date:  # Same as: row_date > start_date AND row_date <= end_date
                # VBA Line 432-437: If openinsert_Flag = 1, subtract values
                # (handled separately in get_opening_balances)
                
                # VBA Line 439: Not_modified flag
                Not_modified = 1
                if date_modified and row_date == date_modified:
                    Not_modified = 0
                
                # VBA Line 440-444: Accumulate period activity
                depreciation += abs(row.depreciation or 0.0)
                interest += abs(row.interest or 0.0)
                rent_paid += (row.rental_amount or 0.0) * Not_modified  # CRITICAL: Exclude date_modified
                change_rou += row.change_in_rou or 0.0
                
                if row.aro_interest:
                    aro_interest += row.aro_interest
                
                # VBA Line 445: Security deposit change (delta calculation)
                if i > 0:  # cell.Row > 9
                    curr_security_pv = row.security_deposit_pv or 0.0
                    security_change += curr_security_pv - prev_security_pv
                    
                    # VBA Line 446-450: Special handling for security increase formulas
                    # (Complex formula parsing - simplified here)
                
                prev_security_pv = row.security_deposit_pv or 0.0
        
        return {
            'depreciation': depreciation,
            'interest': interest,
            'rent_paid': rent_paid,
            'aro_interest': aro_interest,
            'security_change': security_change,
            'change_rou': change_rou
        }
    
    def _find_original_lease_id(self, lease_data: LeaseData) -> int:
        """
        Find original lease ID by following modifies_this_id chain
        VBA Source: orj_id() Sub (Lines 1116-1123)
        VBA Logic: Follows modifies_this_id chain until finding original lease
        """
        current_id = lease_data.auto_id
        # VBA: oai = kai, then loop up to 100 times
        for _ in range(100):  # Max 100 levels to avoid infinite loops
            # In VBA: Range("Modifies_this_ID").Offset(oai, 0).Value
            # For now, we track this in lease_data.modifies_this_id
            # If lease_data doesn't have access to other leases, we return current_id
            # This will need to be enhanced when we have lease database access
            if lease_data.modifies_this_id and lease_data.modifies_this_id > 0:
                current_id = lease_data.modifies_this_id
                # TODO: Load the modified lease data to continue chain
                # For now, return the first level of modification
                break
            else:
                break
        
        return current_id
    
    def _calculate_security_deposit_gross(self, lease_data: LeaseData, balance_date: date) -> float:
        """
        Calculate Security Deposit Gross Amount
        VBA Source: Lines 421-424, 490
        VBA Logic: sec_gross = Security_deposit + sum of increases up to baldate
        """
        # VBA Line 421: sec_gross = Range("Security_deposit").Offset(ai, 0).Value
        sec_gross = lease_data.security_deposit or 0.0
        
        # VBA Lines 422-424: Sum increases if security_date <= baldate
        security_dates = lease_data.security_dates or []
        if security_dates and len(security_dates) > 0:
            for i, sec_date in enumerate(security_dates[:4]):  # VBA: qqq = 1 To 4
                if sec_date and sec_date > date(1900, 1, 1):  # Valid date
                    if sec_date <= balance_date:
                        # Add corresponding increase amount
                        increases = [lease_data.increase_security_1, lease_data.increase_security_2,
                                   lease_data.increase_security_3, lease_data.increase_security_4]
                        if i < len(increases) and increases[i]:
                            sec_gross += increases[i] or 0.0
                    else:
                        # VBA: Exit For when date > baldate
                        break
        
        return sec_gross
    
    def _calculate_accumulated_depreciation(self, schedule: List[PaymentScheduleRow],
                                          lease_data: LeaseData, start_date: date, end_date: date) -> float:
        """
        Calculate Accumulated Depreciation from lease start
        VBA Source: Line 585
        VBA Logic: deprp (from Firstdate to opendate) + H4 (period depreciation) + J7 (from schedule calc)
        """
        # VBA Line 508: Firstdate = Transition_date if Option 2B, else Lease_start_date
        first_date = lease_data.transition_date if (lease_data.transition_option == "2B") else lease_data.lease_start_date
        if not first_date:
            first_date = lease_data.lease_start_date
        
        if not first_date:
            return 0.0
        
        accumulated_dep = 0.0
        
        # VBA Line 583: For cell.Value > Firstdate And cell.Value <= opendate
        for row in schedule:
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if not row_date:
                continue
            
            # Accumulate depreciation from Firstdate to opendate (start_date)
            if first_date < row_date <= start_date:
                accumulated_dep += abs(row.depreciation or 0.0)
        
        # Add period depreciation (already calculated in period_activity)
        # This would be added in results_processor when building the row
        # For now, return accumulated up to start_date
        
        return accumulated_dep

