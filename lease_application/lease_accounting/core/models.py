"""
Data models for lease accounting system
Ports Excel data structure to Python
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal


@dataclass
class LeaseData:
    """Complete lease data structure - mirrors Excel Data sheet"""
    
    # Identifiers
    auto_id: int
    description: str = ""
    asset_class: str = ""
    asset_id_code: str = ""
    
    # Dates
    lease_start_date: Optional[date] = None
    first_payment_date: Optional[date] = None
    end_date: Optional[date] = None
    agreement_date: Optional[date] = None
    termination_date: Optional[date] = None
    date_modified: Optional[date] = None
    transition_date: Optional[date] = None
    
    # Financial Terms
    tenure: Optional[float] = None
    frequency_months: int = 1
    day_of_month: int = 1
    accrual_day: int = 1
    
    # Payments
    manual_adj: str = "No"
    payment_type: str = "advance"  # "advance" or "arrear" - determines payment period direction
    rental_dates: List[Optional[date]] = field(default_factory=list)
    
    # Rental Schedule from form (use this instead of recalculating if provided)
    # Format: [{"start_date": "2025-01-01", "end_date": "2025-12-31", "rental_count": 12, "amount": 50000}, ...]
    rental_schedule: Optional[List[Dict]] = None
    
    # Escalation
    escalation_start: Optional[date] = None
    escalation_percent: Optional[float] = None
    esc_freq_months: int = 12
    index_rate_table: Optional[str] = None
    
    # Discount & Rates
    borrowing_rate: Optional[float] = None
    compound_months: Optional[int] = None
    fv_of_rou: Optional[float] = None
    
    # Residual & Purchase
    bargain_purchase: str = "No"
    purchase_option_price: Optional[float] = None
    title_transfer: str = "No"
    useful_life: Optional[date] = None
    
    # Entity Information
    currency: str = "USD"
    group_entity_name: str = ""
    region: str = ""
    cost_element: str = ""
    profit_center: str = ""
    cost_centre: str = ""
    segment: str = ""
    counterparty: str = ""
    vendor_code: str = ""
    agreement_type: str = ""
    
    # Responsible Persons
    responsible_person_operations: str = ""
    responsible_person_accounts: str = ""
    
    # Security Deposits
    security_deposit: Optional[float] = None
    security_discount: Optional[float] = None
    increase_security_1: Optional[float] = None
    increase_security_2: Optional[float] = None
    increase_security_3: Optional[float] = None
    increase_security_4: Optional[float] = None
    security_dates: List[Optional[date]] = field(default_factory=list)
    
    # ARO (Asset Retirement Obligation)
    aro: Optional[float] = None
    aro_table: int = 0
    aro_revisions: List[Optional[float]] = field(default_factory=list)
    aro_dates: List[Optional[date]] = field(default_factory=list)
    
    # Lease Modifications
    modifies_this_id: Optional[int] = None
    modified_by_this_id: Optional[int] = None
    
    # Initial Costs & Incentives
    initial_direct_expenditure: Optional[float] = None
    prepaid_accrual: Optional[float] = None
    lease_incentive: Optional[float] = None
    scope_reduction: Optional[float] = None
    scope_date: Optional[date] = None
    
    # Sublease
    sublease: str = "No"
    sublease_rou: Optional[float] = None
    
    # Impairment
    impairment1: Optional[float] = None
    impairment2: Optional[float] = None
    impairment3: Optional[float] = None
    impairment4: Optional[float] = None
    impairment5: Optional[float] = None
    impairment_dates: List[Optional[date]] = field(default_factory=list)
    
    # Special Classifications
    intra_group_lease: str = "No"
    finance_lease_usgaap: str = "No"
    short_term_lease_ifrs: str = "No"
    short_term_lease_usgaap: str = "No"
    practical_expedient: str = "No"
    
    # GAAP Standard (used for depreciation calculation)
    gaap_standard: str = "IFRS"  # IFRS, IndAS, or US-GAAP
    
    # Transition
    transition_option: Optional[str] = None
    
    # Termination
    termination_penalty: Optional[float] = None
    
    # Head Lease
    head_lease_id: Optional[int] = None
    
    # Audit Fields
    entered_by: str = ""
    last_modified_by: str = ""
    last_reviewed_by: str = ""
    
    # Calculated fields (populated during processing)
    calculated_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentScheduleRow:
    """Single row in payment schedule - matches Excel Compute sheet columns"""
    # Column C - Date
    date: date
    
    # Alias for date (for compatibility with code that uses payment_date)
    @property
    def payment_date(self):
        """Return date as payment_date for compatibility"""
        return self.date
    
    # Column D - Rental amount
    rental_amount: float = 0.0
    
    # Column E - PV factor (present value factor)
    pv_factor: float = 1.0
    
    # Column F - Interest (compound interest on liability)
    interest: float = 0.0
    
    # Column G - Lease Liability (outstanding balance)
    lease_liability: float = 0.0
    
    # Column H - PV of Rent (PV factor × Rental)
    pv_of_rent: float = 0.0
    
    # Column I - ROU Asset (carrying amount after depreciation)
    rou_asset: float = 0.0
    
    # Column J - Depreciation
    depreciation: float = 0.0
    
    # Column K - Change in ROU
    change_in_rou: float = 0.0
    
    # Column L - Security Deposit (PV)
    security_deposit_pv: float = 0.0
    
    # Column M - ARO Gross (initial ARO amount for the row)
    aro_gross: Optional[float] = None
    
    # Column N - ARO Interest (accrued ARO interest)
    aro_interest: Optional[float] = None
    
    # Column O - ARO Provision (PV of ARO liability)
    aro_provision: Optional[float] = None
    
    # Additional fields
    principal: float = 0.0  # Calculated: rental - interest
    remaining_balance: Optional[float] = None
    is_opening: bool = False
    is_closing: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'date': self.date.isoformat() if self.date else None,
            'rental_amount': self.rental_amount,
            'pv_factor': self.pv_factor,
            'interest': self.interest,
            'lease_liability': self.lease_liability,
            'pv_of_rent': self.pv_of_rent,
            'rou_asset': self.rou_asset,
            'depreciation': self.depreciation,
            'change_in_rou': self.change_in_rou,
            'security_deposit_pv': self.security_deposit_pv,
            'aro_gross': self.aro_gross,
            'aro_interest': self.aro_interest,
            'aro_provision': self.aro_provision,
            'principal': self.principal,
            'remaining_balance': self.remaining_balance,
        }


@dataclass
class LeaseResult:
    """Results for a single lease - mirrors Excel Results sheet"""
    lease_id: int
    
    # Opening Balances
    opening_lease_liability: float = 0.0
    opening_rou_asset: float = 0.0
    opening_aro_liability: float = 0.0
    opening_security_deposit: float = 0.0
    
    # Period Activity
    interest_expense: float = 0.0
    depreciation_expense: float = 0.0
    rent_paid: float = 0.0
    aro_interest: float = 0.0
    security_deposit_change: float = 0.0
    
    # Closing Balances
    closing_lease_liability_current: float = 0.0
    closing_lease_liability_non_current: float = 0.0
    closing_rou_asset: float = 0.0
    closing_aro_liability: float = 0.0
    closing_security_deposit: float = 0.0
    closing_security_deposit_current: float = 0.0  # N4: Security Deposit Current portion
    closing_security_deposit_non_current: float = 0.0  # M4: Security Deposit Non-Current portion
    
    # Gain/Loss
    gain_loss_pnl: float = 0.0
    
    # Gain/Loss Breakdown Components (VBA Lines 453-473)
    covid_pe_gain: Optional[float] = None  # COVID Practical Expedient Gain (BI4, also separate)
    modification_gain: Optional[float] = None  # Gain on modification
    sublease_gain_loss: Optional[float] = None  # Gain/Loss on sublease initial recognition
    sublease_modification_gain_loss: Optional[float] = None  # Gain/Loss on sublease modification
    termination_gain_loss: Optional[float] = None  # Gain/Loss on termination (includes penalty)
    
    # Projections
    projections: List[Dict[str, Any]] = field(default_factory=list)
    
    # Additional Info
    asset_class: str = ""
    cost_center: str = ""
    currency: str = ""
    description: str = ""
    asset_code: str = ""
    borrowing_rate: Optional[float] = None
    remaining_rou_life: Optional[float] = None
    
    # Missing Results Table Columns (Z4, AA4, AB4, AC4-AG4, BB4, BC4, BD4, BE4, BI4)
    original_lease_id: Optional[int] = None  # Z4: Original Lease ID (after following modifies_this_id chain)
    modification_indicator: str = ""  # AA4: "Modifier" if this lease modifies another
    initial_rou_asset: Optional[float] = None  # AB4: Initial ROU Asset for new leases
    security_deposit_gross: Optional[float] = None  # BB4: Security Deposit Gross Amount
    accumulated_depreciation: Optional[float] = None  # BC4: Accumulated Depreciation from lease start
    initial_direct_expenditure_period: Optional[float] = None  # BD4: Initial Direct Expenditure on transition
    prepaid_accrual_period: Optional[float] = None  # BE4: Prepaid Accrual on transition
    covid_pe_gain: Optional[float] = None  # BI4: COVID Practical Expedient Gain
    
    # Projection data columns (AC4-AG4) - stored as list of projection dicts
    # AC4-AG4 columns are populated from projections list, one set per projection mode (1-6)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'lease_id': self.lease_id,
            'opening_lease_liability': self.opening_lease_liability,
            'opening_rou_asset': self.opening_rou_asset,
            'opening_aro_liability': self.opening_aro_liability,
            'opening_security_deposit': self.opening_security_deposit,
            'interest_expense': self.interest_expense,
            'depreciation_expense': self.depreciation_expense,
            'rent_paid': self.rent_paid,
            'aro_interest': self.aro_interest,
            'security_deposit_change': self.security_deposit_change,
            'closing_lease_liability_current': self.closing_lease_liability_current,
            'closing_lease_liability_non_current': self.closing_lease_liability_non_current,
            'closing_rou_asset': self.closing_rou_asset,
            'closing_aro_liability': self.closing_aro_liability,
            'closing_security_deposit': self.closing_security_deposit,
            'gain_loss_pnl': self.gain_loss_pnl,
            'projections': self.projections,
            'asset_class': self.asset_class,
            'cost_center': self.cost_center,
            'currency': self.currency,
            'description': self.description,
            'asset_code': self.asset_code,
            'borrowing_rate': self.borrowing_rate,
            'remaining_rou_life': self.remaining_rou_life,
            # Missing Results Table Columns
            'original_lease_id': self.original_lease_id,
            'modification_indicator': self.modification_indicator,
            'initial_rou_asset': self.initial_rou_asset,
            'security_deposit_gross': self.security_deposit_gross,
            'accumulated_depreciation': self.accumulated_depreciation,
            'initial_direct_expenditure_period': self.initial_direct_expenditure_period,
            'prepaid_accrual_period': self.prepaid_accrual_period,
            'covid_pe_gain': self.covid_pe_gain,
            # Gain/Loss Breakdown
            'modification_gain': self.modification_gain,
            'sublease_gain_loss': self.sublease_gain_loss,
            'sublease_modification_gain_loss': self.sublease_modification_gain_loss,
            'termination_gain_loss': self.termination_gain_loss,
        }


@dataclass
class ProcessingFilters:
    """Filters for processing leases - mirrors Excel Results sheet inputs"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_lease_id: Optional[int] = None
    end_lease_id: Optional[int] = None
    cost_center_filter: Optional[str] = None
    entity_filter: Optional[str] = None
    asset_class_filter: Optional[str] = None
    profit_center_filter: Optional[str] = None
    gaap_standard: str = "IFRS"  # IFRS, IndAS, or US-GAAP
    enable_projections: bool = True  # VBA: A3.Value = 1 (enable projections)
    projection_periods: int = 3  # Number of periods to calculate (max 6)
    projection_period_months: int = 3  # Months per period (VBA: A4.Value)

