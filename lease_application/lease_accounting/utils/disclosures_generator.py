"""
Disclosures Generator
Generates IFRS 16 / ASC 842 disclosure requirements

VBA Source: JournalD sheet - Disclosures section
"""

from typing import List, Dict, Any, Optional
from datetime import date
from lease_accounting.core.models import LeaseResult, LeaseData, PaymentScheduleRow


class DisclosuresGenerator:
    """
    Generate lease accounting disclosures
    Matches Excel JournalD sheet disclosures section
    """
    
    def __init__(self):
        self.disclosures: Dict[str, Any] = {}
    
    def generate_disclosures(
        self,
        lease_results: List[LeaseResult],
        lease_data_list: List[LeaseData],
        schedule_list: List[List[PaymentScheduleRow]],
        balance_date: date,
        gaap_standard: str = "IFRS"
    ) -> Dict[str, Any]:
        """
        Generate complete disclosures for lease portfolio
        
        Returns disclosure dictionary with:
        - Maturity Analysis (payments by year)
        - Total Lease Liability by entity/region
        - Total ROU Asset by category
        - Variable Lease Payments
        - Short-term Leases excluded
        - Lease Incentives Received
        - Extension/Renewal Options
        - Purchase Options
        """
        self.disclosures = {}
        
        # Aggregate data across all leases
        all_schedules = []
        for schedules in schedule_list:
            all_schedules.extend(schedules)
        
        # 1. Maturity Analysis - Lease payments due by year
        self.disclosures['maturity_analysis'] = self._calculate_maturity_analysis(
            all_schedules, balance_date
        )
        
        # 2. Total Lease Liability by entity/region
        # Handle both LeaseResult objects and dict results
        if lease_results and len(lease_results) > 0:
            # Check if first item is dict or object
            if isinstance(lease_results[0], dict):
                # Dict format - access as dict
                self.disclosures['liability_by_entity'] = self._aggregate_by_field_dict(
                    lease_results, lease_data_list, 'group_entity_name',
                    lambda r: (r.get('closing_lease_liability_current') or 0.0) + (r.get('closing_lease_liability_non_current') or 0.0)
                )
            else:
                # LeaseResult object format
                self.disclosures['liability_by_entity'] = self._aggregate_by_field(
                    lease_results, lease_data_list, 'group_entity_name',
                    lambda r: (r.closing_lease_liability_current or 0.0) + (r.closing_lease_liability_non_current or 0.0)
                )
        else:
            self.disclosures['liability_by_entity'] = {}
        
        # 3. Total ROU Asset by category (asset_class)
        if lease_results and len(lease_results) > 0:
            if isinstance(lease_results[0], dict):
                self.disclosures['rou_by_category'] = self._aggregate_by_field_dict(
                    lease_results, lease_data_list, 'asset_class',
                    lambda r: r.get('closing_rou_asset') or 0.0
                )
            else:
                self.disclosures['rou_by_category'] = self._aggregate_by_field(
                    lease_results, lease_data_list, 'asset_class',
                    lambda r: r.closing_rou_asset or 0.0
                )
        else:
            self.disclosures['rou_by_category'] = {}
        
        # 4. Variable Lease Payments (rental escalations indexed to rates)
        self.disclosures['variable_payments'] = self._calculate_variable_payments(
            lease_data_list, all_schedules
        )
        
        # 5. Short-term Leases excluded
        self.disclosures['short_term_leases'] = self._count_short_term_leases(
            lease_data_list, gaap_standard
        )
        
        # 6. Lease Incentives Received
        self.disclosures['lease_incentives'] = sum(
            (ld.lease_incentive or 0.0) for ld in lease_data_list
        )
        
        # 7. Extension/Renewal Options
        self.disclosures['extension_options'] = self._count_extension_options(lease_data_list)
        
        # 8. Purchase Options
        self.disclosures['purchase_options'] = self._count_purchase_options(lease_data_list)
        
        return self.disclosures
    
    def _calculate_maturity_analysis(
        self,
        schedules: List[PaymentScheduleRow],
        balance_date: date
    ) -> List[Dict[str, Any]]:
        """
        Calculate maturity analysis - payments due by year
        Groups payments into year buckets (Year 1, Year 2, Year 3-5, Beyond 5 years)
        """
        maturity_by_year: Dict[int, float] = {}
        
        for row in schedules:
            row_date = row.date if hasattr(row, 'date') else (row.payment_date if hasattr(row, 'payment_date') else None)
            if not row_date or row_date <= balance_date:
                continue
            
            rental = row.rental_amount or 0.0
            if rental > 0:
                year = row_date.year
                if year not in maturity_by_year:
                    maturity_by_year[year] = 0.0
                maturity_by_year[year] += rental
        
        # Group into disclosure buckets: Year 1, Year 2, Year 3-5, Beyond 5 years
        current_year = balance_date.year
        maturity_analysis = []
        
        year_1_total = maturity_by_year.get(current_year + 1, 0.0)
        year_2_total = maturity_by_year.get(current_year + 2, 0.0)
        years_3_to_5 = sum(
            maturity_by_year.get(year, 0.0)
            for year in range(current_year + 3, current_year + 6)
        )
        beyond_5 = sum(
            maturity_by_year.get(year, 0.0)
            for year in maturity_by_year.keys()
            if year > current_year + 5
        )
        
        maturity_analysis.append({
            'period': 'Year 1',
            'year': current_year + 1,
            'total_payments': year_1_total
        })
        maturity_analysis.append({
            'period': 'Year 2',
            'year': current_year + 2,
            'total_payments': year_2_total
        })
        maturity_analysis.append({
            'period': 'Years 3-5',
            'years': f'{current_year + 3}-{current_year + 5}',
            'total_payments': years_3_to_5
        })
        maturity_analysis.append({
            'period': 'Beyond 5 years',
            'total_payments': beyond_5
        })
        
        return maturity_analysis
    
    def _aggregate_by_field(
        self,
        lease_results: List[LeaseResult],
        lease_data_list: List[LeaseData],
        field_name: str,
        value_func
    ) -> Dict[str, float]:
        """
        Aggregate lease results by a field (entity, asset_class, etc.)
        For LeaseResult objects
        """
        aggregated: Dict[str, float] = {}
        
        # Create mapping from lease_id to lease_data
        data_map = {ld.auto_id: ld for ld in lease_data_list}
        
        for result in lease_results:
            lease_data = data_map.get(result.lease_id)
            if not lease_data:
                continue
            
            field_value = getattr(lease_data, field_name, 'Unknown') or 'Unknown'
            value = value_func(result)
            
            if field_value not in aggregated:
                aggregated[field_value] = 0.0
            aggregated[field_value] += value
        
        return aggregated
    
    def _aggregate_by_field_dict(
        self,
        lease_results: List[Dict],
        lease_data_list: List[LeaseData],
        field_name: str,
        value_func
    ) -> Dict[str, float]:
        """
        Aggregate lease results by a field (entity, asset_class, etc.)
        For dict results (from API)
        """
        aggregated: Dict[str, float] = {}
        
        # Create mapping from lease_id to lease_data
        data_map = {ld.auto_id: ld for ld in lease_data_list}
        
        for result in lease_results:
            lease_id = result.get('lease_id') or result.get('auto_id')
            if not lease_id:
                continue
                
            lease_data = data_map.get(lease_id)
            if not lease_data:
                continue
            
            field_value = getattr(lease_data, field_name, 'Unknown') or 'Unknown'
            value = value_func(result)
            
            if field_value not in aggregated:
                aggregated[field_value] = 0.0
            aggregated[field_value] += value
        
        return aggregated
    
    def _calculate_variable_payments(
        self,
        lease_data_list: List[LeaseData],
        schedules: List[PaymentScheduleRow]
    ) -> Dict[str, Any]:
        """
        Calculate variable lease payments (index-linked or CPI-linked escalations)
        """
        variable_leases = []
        total_variable = 0.0
        
        for lease_data in lease_data_list:
            if lease_data.index_rate_table or lease_data.escalation_percent:
                # Check if escalation is variable (index-linked)
                if lease_data.index_rate_table:
                    # Sum variable payments from schedule
                    lease_schedules = [s for s in schedules if hasattr(s, 'lease_id') and getattr(s, 'lease_id') == lease_data.auto_id]
                    variable_amount = sum(
                        (s.rental_amount or 0.0) for s in lease_schedules
                        if s.rental_amount and s.rental_amount > 0
                    )
                    variable_leases.append({
                        'lease_id': lease_data.auto_id,
                        'description': lease_data.description,
                        'variable_amount': variable_amount
                    })
                    total_variable += variable_amount
        
        return {
            'total_variable_payments': total_variable,
            'variable_lease_count': len(variable_leases),
            'variable_leases': variable_leases
        }
    
    def _count_short_term_leases(
        self,
        lease_data_list: List[LeaseData],
        gaap_standard: str
    ) -> Dict[str, Any]:
        """
        Count short-term leases excluded from calculation
        """
        if gaap_standard == "US-GAAP":
            short_term = [ld for ld in lease_data_list if ld.short_term_lease_usgaap == "Yes"]
        else:
            short_term = [ld for ld in lease_data_list if ld.short_term_lease_ifrs == "Yes"]
        
        total_rent = sum((ld.rental_1 or 0.0) * 12 for ld in short_term)  # Approximate annual
        
        return {
            'count': len(short_term),
            'total_annual_rent': total_rent,
            'short_term_leases': [
                {
                    'lease_id': ld.auto_id,
                    'description': ld.description,
                    'rental': ld.rental_1 or 0.0
                }
                for ld in short_term
            ]
        }
    
    def _count_extension_options(self, lease_data_list: List[LeaseData]) -> Dict[str, Any]:
        """
        Count leases with extension/renewal options
        """
        # Extension options would be tracked in lease_data if field exists
        # For now, return placeholder structure
        return {
            'count': 0,
            'leases_with_extensions': []
        }
    
    def _count_purchase_options(self, lease_data_list: List[LeaseData]) -> Dict[str, Any]:
        """
        Count leases with purchase options
        """
        purchase_options = [
            ld for ld in lease_data_list
            if ld.bargain_purchase == "Yes" or (ld.purchase_option_price and ld.purchase_option_price > 0)
        ]
        
        return {
            'count': len(purchase_options),
            'total_purchase_price': sum((ld.purchase_option_price or 0.0) for ld in purchase_options),
            'leases_with_purchase_options': [
                {
                    'lease_id': ld.auto_id,
                    'description': ld.description,
                    'purchase_price': ld.purchase_option_price or 0.0
                }
                for ld in purchase_options
            ]
        }

