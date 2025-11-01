"""
Journal Entry Generator
Creates Excel-style journal entries (JournalD sheet)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from lease_accounting.core.models import PaymentScheduleRow, LeaseResult


@dataclass
class JournalEntry:
    """Single journal entry matching Excel JournalD sheet structure"""
    bs_pl: str  # "BS" or "PL"
    account_code: str = ""
    account_name: str = ""
    result_period: float = 0.0  # Column F: Current period closing
    previous_period: float = 0.0  # Column E: Previous period closing
    opening_balance: float = 0.0  # Column D: Opening balance (BS = Previous Period closing, PL = 0)
    incremental_adjustment: float = 0.0  # Column H: Change during period
    ifrs_adjustment: float = 0.0  # Column G: IFRS/Ind-AS adjustment
    usgaap_entry: float = 0.0  # Column I: US-GAAP entry (when comparing)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'bs_pl': self.bs_pl,
            'account_code': self.account_code,
            'account_name': self.account_name,
            'result_period': self.result_period,
            'previous_period': self.previous_period,
            'opening_balance': self.opening_balance,
            'incremental_adjustment': self.incremental_adjustment,
            'ifrs_adjustment': self.ifrs_adjustment,
            'usgaap_entry': self.usgaap_entry,
        }


class JournalGenerator:
    """
    Generate journal entries from lease schedule
    Ports Excel JournalD sheet logic
    """
    
    def __init__(self, gaap_standard: str = "IFRS"):
        self.gaap_standard = gaap_standard  # "IFRS", "IndAS", or "US-GAAP"
        self.journal_entries: List[JournalEntry] = []
    
    def generate_journals(
        self,
        lease_result: LeaseResult,
        schedule: List[PaymentScheduleRow],
        previous_result: Optional[LeaseResult] = None
    ) -> List[JournalEntry]:
        """
        Generate complete journal entries
        Matches Excel JournalD sheet structure
        
        VBA Source: VB script/FuncS, copy_opening() and copy_IFRS()
        JournalD Sheet Structure:
          - Column D = Opening Balance (Previous Period closing for BS, 0 for PL)
          - Column E = Previous Period closing (from previous calculation)
          - Column F = Result Period closing (current calculation)
          - Column G = IFRS/Ind-AS Adjustment (when comparing IFRS vs US-GAAP)
        """
        self.journal_entries = []
        
        # Opening balance entries - show CLOSING balances (not opening)
        # VBA JournalD: Column F = Result Period shows closing balances at to_date
        # Column E = Previous Period shows closing balances at from_date - 1
        # Column D = Opening Balance (VBA copy_opening: PL items = 0, BS items = Previous Period closing)
        # Column G = Incremental Adjustment shows the change during the period
        
        # For Liability: Show closing balance (not opening)
        opening_liab = lease_result.opening_lease_liability or 0.0
        closing_liab_total = (lease_result.closing_lease_liability_current or 0.0) + (lease_result.closing_lease_liability_non_current or 0.0)
        
        prev_opening_liab = previous_result.opening_lease_liability if previous_result else 0.0
        prev_closing_liab = ((previous_result.closing_lease_liability_current or 0.0) + (previous_result.closing_lease_liability_non_current or 0.0)) if previous_result else 0.0
        
        # Opening balance = Previous Period closing for BS items, 0 for PL items
        # VBA: If cell.Offset(0, -4).Value = "PL" Then cell.Formula = 0 Else cell.Formula = cell.Offset(0, -1).Value
        prev_liab_non_current = -(previous_result.closing_lease_liability_non_current or 0.0) if previous_result else 0
        prev_liab_current = -(previous_result.closing_lease_liability_current or 0.0) if previous_result else 0
        
        self._add_entry(
            bs_pl="BS",
            account_name="Lease Liability Non-current",
            result_period=-(lease_result.closing_lease_liability_non_current or 0.0),
            previous_period=prev_liab_non_current,
            opening_balance=prev_liab_non_current  # BS item: Opening = Previous Period closing
        )
        
        self._add_entry(
            bs_pl="BS",
            account_name="Lease Liability Current",
            result_period=-(lease_result.closing_lease_liability_current or 0.0),
            previous_period=prev_liab_current,
            opening_balance=prev_liab_current  # BS item: Opening = Previous Period closing
        )
        
        # Interest expense (PL item: Opening = 0)
        self._add_entry(
            bs_pl="PL",
            account_name="Interest Cost",
            result_period=lease_result.interest_expense,
            previous_period=previous_result.interest_expense if previous_result else 0,
            opening_balance=0.0  # PL item: Opening = 0
        )
        
        # ROU Asset (BS item: Opening = Previous Period closing)
        prev_rou = previous_result.closing_rou_asset if previous_result else 0
        self._add_entry(
            bs_pl="BS",
            account_name="RoU Asset (net)",
            result_period=lease_result.closing_rou_asset,
            previous_period=prev_rou,
            opening_balance=prev_rou  # BS item: Opening = Previous Period closing
        )
        
        # Depreciation (PL item: Opening = 0)
        self._add_entry(
            bs_pl="PL",
            account_name="Depreciation",
            result_period=lease_result.depreciation_expense,
            previous_period=previous_result.depreciation_expense if previous_result else 0,
            opening_balance=0.0  # PL item: Opening = 0
        )
        
        # Gain/Loss (PL item: Opening = 0)
        if lease_result.gain_loss_pnl != 0:
            self._add_entry(
                bs_pl="PL",
                account_name="(Gain)/Loss in P&L",
                result_period=lease_result.gain_loss_pnl,
                previous_period=previous_result.gain_loss_pnl if previous_result else 0,
                opening_balance=0.0  # PL item: Opening = 0
            )
        
        # ARO Interest (PL item: Opening = 0)
        if lease_result.aro_interest != 0:
            self._add_entry(
                bs_pl="PL",
                account_name="ARO Interest",
                result_period=lease_result.aro_interest,
                previous_period=previous_result.aro_interest if previous_result else 0,
                opening_balance=0.0  # PL item: Opening = 0
            )
        
        # ARO Provision Closing (BS item: Opening = Previous Period closing)
        prev_aro = previous_result.closing_aro_liability if previous_result else 0
        if lease_result.closing_aro_liability != 0:
            self._add_entry(
                bs_pl="BS",
                account_name="ARO Provision Closing",
                result_period=lease_result.closing_aro_liability,
                previous_period=prev_aro,
                opening_balance=prev_aro  # BS item: Opening = Previous Period closing
            )
        
        # Security Deposit Interest (PL item: Opening = 0)
        if lease_result.security_deposit_change != 0:
            self._add_entry(
                bs_pl="PL",
                account_name="Interest on Security Dep",
                result_period=lease_result.security_deposit_change,
                previous_period=previous_result.security_deposit_change if previous_result else 0,
                opening_balance=0.0  # PL item: Opening = 0
            )
        
        # Security Deposit - Show as single asset (BS item: Opening = Previous Period closing)
        prev_sec = -(previous_result.closing_security_deposit or 0.0) if previous_result else 0
        if lease_result.closing_security_deposit > 0:
            self._add_entry(
                bs_pl="BS",
                account_name="Security Deposit",
                account_code="",  # No specific code for security deposit
                result_period=-lease_result.closing_security_deposit,
                previous_period=prev_sec,
                opening_balance=prev_sec  # BS item: Opening = Previous Period closing
            )
        
        # Rent Paid (PL item: Opening = 0)
        self._add_entry(
            bs_pl="PL",
            account_name="Rent Paid",
            result_period=-lease_result.rent_paid,
            previous_period=-previous_result.rent_paid if previous_result else 0,
            opening_balance=0.0  # PL item: Opening = 0
        )
        
        # Retained Earnings (balancing entry - BS item: Opening = Previous Period closing)
        total_debits = sum(e.result_period for e in self.journal_entries if e.result_period > 0)
        total_credits = sum(e.result_period for e in self.journal_entries if e.result_period < 0)
        retained_earnings = total_credits + total_debits
        prev_retained = -(previous_result.gain_loss_pnl or 0.0) if previous_result else 0
        
        self._add_entry(
            bs_pl="BS",
            account_name="Retained Earnings",
            result_period=-retained_earnings,
            previous_period=prev_retained,
            opening_balance=prev_retained  # BS item: Opening = Previous Period closing
        )
        
        # Calculate incremental adjustments (Column H = Result Period - Previous Period)
        for entry in self.journal_entries:
            entry.incremental_adjustment = entry.result_period - entry.previous_period
            
            # Calculate IFRS vs US-GAAP differences (Column G and I)
            # VBA: copy_IFRS() copies Column F to Column G when GAAP = "IFRS/Ind-AS"
            if self.gaap_standard in ["IFRS", "IndAS"]:
                entry.ifrs_adjustment = entry.result_period
                entry.usgaap_entry = 0.0
            elif self.gaap_standard == "US-GAAP":
                entry.ifrs_adjustment = 0.0
                entry.usgaap_entry = entry.result_period
            else:
                # Default: set both to result_period (no comparison)
                entry.ifrs_adjustment = entry.result_period
                entry.usgaap_entry = entry.result_period
        
        return self.journal_entries
    
    def _get_account_code(self, account_name: str) -> str:
        """Map account name to account code (Chart of Accounts)"""
        account_code_map = {
            "Lease Liability Non-current": "2101",
            "Lease Liability Current": "2102",
            "RoU Asset (net)": "1200",
            "Interest Cost": "5101",
            "Depreciation": "5102",
            "Rent Paid": "5103",
            "ARO Interest": "5104",
            "Interest on Security Dep": "5105",
            "ARO Provision Closing": "2201",
            "Security Deposit - Non-current": "1201",
            "Security Deposit - Current": "1202",
            "Retained Earnings": "3100",
            "(Gain)/Loss in P&L": "5200",
        }
        return account_code_map.get(account_name, "")
    
    def _add_entry(self, bs_pl: str, account_name: str, 
                   account_code: str = "",
                   result_period: float = 0.0, previous_period: float = 0.0,
                   opening_balance: Optional[float] = None):
        """
        Add a journal entry
        VBA: Opening balance = Previous Period closing for BS items, 0 for PL items
        """
        # Auto-assign account code if not provided
        if not account_code:
            account_code = self._get_account_code(account_name)
        
        # Auto-calculate opening_balance if not provided (VBA copy_opening logic)
        if opening_balance is None:
            if bs_pl == "PL":
                opening_balance = 0.0  # PL items: Opening = 0
            else:
                opening_balance = previous_period  # BS items: Opening = Previous Period closing
        
        entry = JournalEntry(
            bs_pl=bs_pl,
            account_name=account_name,
            account_code=account_code,
            result_period=result_period,
            previous_period=previous_period,
            opening_balance=opening_balance
        )
        self.journal_entries.append(entry)
    
    def verify_balance(self) -> bool:
        """
        Verify that journal entries balance (debits = credits)
        Should sum to zero
        """
        total = sum(entry.result_period for entry in self.journal_entries)
        return abs(total) < 0.01  # Allow for rounding
    
    def get_debit_credit_summary(self) -> Dict[str, float]:
        """Get summary of debits and credits"""
        debits = sum(entry.result_period for entry in self.journal_entries if entry.result_period > 0)
        credits = abs(sum(entry.result_period for entry in self.journal_entries if entry.result_period < 0))
        difference = debits - credits
        
        return {
            'total_debits': debits,
            'total_credits': credits,
            'difference': difference,
            'is_balanced': abs(difference) < 0.01
        }


def generate_lease_journal(
    lease_result: LeaseResult,
    schedule: List[PaymentScheduleRow],
    previous_result: Optional[LeaseResult] = None,
    gaap_standard: str = "IFRS"
) -> List[JournalEntry]:
    """
    Convenience function to generate journal entries
    """
    generator = JournalGenerator(gaap_standard=gaap_standard)
    return generator.generate_journals(lease_result, schedule, previous_result)

