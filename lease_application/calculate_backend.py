"""
Lease Calculation Backend API
Handles lease calculation requests and returns schedules, journal entries, and results
"""

from flask import Blueprint, request, jsonify, session
from datetime import date, datetime
from typing import Optional, List
import logging
from lease_accounting.core.models import LeaseData, ProcessingFilters
from lease_accounting.schedule.generator_vba_complete import generate_complete_schedule
from lease_accounting.core.processor import LeaseProcessor
from lease_accounting.core.results_processor import ResultsProcessor
from lease_accounting.utils.journal_generator import JournalGenerator
from auth import require_login
import database

# Create blueprint
calc_bp = Blueprint('calc', __name__, url_prefix='/api')

logger = logging.getLogger(__name__)


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string to date object"""
    if not date_str:
        return None
    try:
        if isinstance(date_str, str):
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        return date_str
    except (ValueError, TypeError):
        return None


@calc_bp.route('/calculate_lease', methods=['POST'])
@require_login
def calculate_lease():
    """
    Main endpoint for lease calculation
    Returns complete schedule, journal entries, and results
    """
    try:
        data = request.json
        
        logger.info(f"📥 Received calculation request:")
        logger.info(f"   lease_start: {data.get('lease_start_date')}, end: {data.get('lease_end_date')}")
        logger.info(f"   from_date: {data.get('from_date')}, to_date: {data.get('to_date')}")
        logger.info(f"   rental_schedule entries: {len(data.get('rental_schedule', []))}")
        
        # Map form fields to lease data structure
        # rental_schedule is always present and is the source of truth for rental amounts
        lease_start = _parse_date(data.get('lease_start_date'))
        end_date = _parse_date(data.get('lease_end_date') or data.get('end_date'))
        
        if lease_start and end_date and lease_start >= end_date:
            logger.warning(f"⚠️  Lease end date ({end_date}) must be AFTER start date ({lease_start})!")
        
        # Extract borrowing_rate properly from payload (check 'ibr' first, then 'borrowing_rate')
        ibr_val = data.get('ibr')
        br_val = data.get('borrowing_rate')
        borrowing_rate = None
        if ibr_val is not None and ibr_val != '':
            try:
                borrowing_rate = float(ibr_val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid borrowing_rate value in 'ibr' field: {ibr_val}. Must be a valid number.")
        elif br_val is not None and br_val != '':
            try:
                borrowing_rate = float(br_val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid borrowing_rate value in 'borrowing_rate' field: {br_val}. Must be a valid number.")
        
        # Don't raise error if borrowing_rate is None - let LeaseData handle it with proper defaults
        # The form should always provide ibr, but calculation should handle missing values gracefully
        if borrowing_rate is None:
            logger.warning("⚠️  borrowing_rate not provided in payload. Will use default from LeaseData if available.")
            borrowing_rate = None  # Let LeaseData model handle default
        
        # CRITICAL: Extract frequency_months BEFORE creating LeaseData
        # Check frequency_months first, then rent_frequency, then default to 1
        freq_months_raw = data.get('frequency_months')
        rent_freq_raw = data.get('rent_frequency')
        logger.debug(f"📊 Frequency from payload: frequency_months={freq_months_raw}, rent_frequency={rent_freq_raw}")
        # Check if frequency_months exists (even if 0), otherwise use rent_frequency, otherwise default to 1
        if freq_months_raw is not None:
            frequency_months = int(freq_months_raw) if freq_months_raw else 1
        elif rent_freq_raw is not None:
            frequency_months = int(rent_freq_raw) if rent_freq_raw else 1
        else:
            frequency_months = 1
        logger.info(f"📊 Using frequency_months={frequency_months} for payment generation (quarterly=3, monthly=1)")
        
        # CRITICAL: Extract day_of_month BEFORE creating LeaseData
        # Check day_of_month first, then pay_day_of_month, then default to '1'
        day_of_month_raw = data.get('day_of_month')
        pay_day_of_month_raw = data.get('pay_day_of_month')
        if day_of_month_raw:
            day_of_month = str(day_of_month_raw)
        elif pay_day_of_month_raw:
            day_of_month = str(pay_day_of_month_raw)
        else:
            day_of_month = '1'
        logger.debug(f"📅 Using day_of_month={day_of_month} for payment generation")
        
        # Parse lease data from form - map to LeaseData structure
        lease_data = LeaseData(
            auto_id=data.get('lease_id', 1),
            description=data.get('agreement_title') or data.get('description', ''),
            asset_class=data.get('asset_class', ''),
            asset_id_code=data.get('asset_id_code', ''),
            
            # Dates
            lease_start_date=_parse_date(data.get('lease_start_date')),
            first_payment_date=_parse_date(data.get('first_payment_date')),
            end_date=end_date,
            agreement_date=_parse_date(data.get('rent_agreement_date') or data.get('agreement_date')),
            termination_date=_parse_date(data.get('termination_date')),
            
            # Financial Terms
            tenure=float(data.get('tenure_months', 0) or 0),
            frequency_months=frequency_months,
            day_of_month=day_of_month,
            
            # Payments
            manual_adj="Yes" if str(data.get('manual_adj', '')).lower() in ['yes', 'on', 'true', '1'] else "No",
            payment_type=data.get('payment_type', 'advance').lower() or 'advance',  # "advance" or "arrear"
            
            # Rental Schedule from form - always required (source of truth for rentals)
            rental_schedule=data.get('rental_schedule'),  # List of dicts with start_date, end_date, amount, rental_count
            
            # Escalation - No defaults, must be explicitly provided
            escalation_start=_parse_date(data.get('escalation_start_date')),
            escalation_percent=float(data.get('escalation_percentage', 0) or data.get('escalation_percent', 0) or 0),
            esc_freq_months=int(data.get('escalation_frequency') or data.get('esc_freq_months') or 0) if (data.get('escalation_frequency') or data.get('esc_freq_months')) else None,
            accrual_day=int(data.get('rent_accrual_day', 1) or data.get('accrual_day', 1) or 1),
            index_rate_table=data.get('index_rate_table'),
            
            # Rates
            borrowing_rate=borrowing_rate,
            compound_months=int(data.get('compound_months')) if data.get('compound_months') else None,
            fv_of_rou=float(data.get('fair_value', 0) or data.get('fv_of_rou', 0) or 0),
            
            # Residual
            bargain_purchase=data.get('bargain_purchase', 'No'),
            purchase_option_price=float(data.get('purchase_option_price', 0) or 0),
            title_transfer=data.get('title_transfer', 'No'),
            useful_life=_parse_date(data.get('useful_life_end_date')),
            
            # Entity
            currency=data.get('currency', 'USD'),
            cost_centre=data.get('cost_center', '') or data.get('cost_centre', ''),
            counterparty=data.get('company_name') or data.get('counterparty', ''),
            
            # Security
            security_deposit=float(data.get('security_deposit_amount', 0) or data.get('security_deposit', 0) or 0),
            security_discount=float(data.get('security_discount_rate', 0) or data.get('security_discount', 0) or 0),
            increase_security_1=0,
            increase_security_2=0,
            increase_security_3=0,
            increase_security_4=0,
            security_dates=[None, None, None, None],
            
            # ARO
            aro=float(data.get('aro_initial_estimate', 0) or data.get('aro', 0) or 0),
            aro_table=int(data.get('aro_table', 0) or 0),
            aro_revisions=[0, 0, 0, 0],
            aro_dates=[None, None, None, None],
            
            # Initial Costs
            initial_direct_expenditure=float(data.get('initial_direct_expenditure', 0) or 0),
            lease_incentive=float(data.get('lease_incentive', 0) or 0),
            
            # Modifications
            modifies_this_id=None,
            modified_by_this_id=None,
            date_modified=None,
            
            # Sublease
            sublease=data.get('sublease', 'No'),
            sublease_rou=float(data.get('sublease_rou', 0) or 0),
            
            # Other
            profit_center=data.get('profit_center', ''),
            group_entity_name=data.get('group_entity_name', ''),
            short_term_lease_ifrs=data.get('short_term_ifrs', 'No'),
            short_term_lease_usgaap=data.get('short_term_usgaap', 'No'),
        )
        
        # Parse date range filters
        from_date = _parse_date(data.get('from_date'))
        to_date = _parse_date(data.get('to_date'))
        
        if not from_date:
            from_date = lease_data.lease_start_date or date.today()
        if not to_date:
            to_date = lease_data.end_date or date.today()
        
        # Create filters
        filters = ProcessingFilters(
            start_date=from_date,
            end_date=to_date,
            gaap_standard=data.get('gaap_standard', 'IFRS')
        )
        
        # Set gaap_standard on lease_data
        lease_data.gaap_standard = filters.gaap_standard
        
        # Generate full schedule
        logger.info("📅 Generating payment schedule...")
        full_schedule = generate_complete_schedule(lease_data)
        
        if not full_schedule:
            return jsonify({'error': 'Failed to generate schedule - check lease parameters'}), 400
        
        logger.info(f"✅ Generated {len(full_schedule)} schedule rows")
        
        # Process lease
        logger.info("🔄 Processing lease...")
        processor = LeaseProcessor(filters)
        result = processor.process_single_lease(lease_data)
        
        if not result:
            return jsonify({'error': 'Failed to process lease'}), 400
        
        logger.info(f"✅ Lease processed: Opening Liability={result.opening_lease_liability:,.2f}")
        
        # Filter schedule by date range
        schedule = list(full_schedule)
        
        # If to_date is not a payment date, INSERT row and COPY values from previous row
        if to_date:
            to_date_exists = any(row.date == to_date for row in schedule)
            
            if not to_date_exists:
                for i, row in enumerate(schedule):
                    if row.date > to_date:
                        prev_row = schedule[i-1] if i > 0 else row
                        from lease_accounting.core.models import PaymentScheduleRow
                        new_row = PaymentScheduleRow(
                            date=to_date,
                            rental_amount=0.0,
                            pv_factor=prev_row.pv_factor,
                            interest=0.0,
                            lease_liability=prev_row.lease_liability,
                            pv_of_rent=0.0,
                            rou_asset=prev_row.rou_asset,
                            depreciation=0.0,
                            change_in_rou=0.0,
                            security_deposit_pv=prev_row.security_deposit_pv,
                            aro_gross=prev_row.aro_gross,
                            aro_interest=0.0,
                            aro_provision=prev_row.aro_provision,
                            principal=0.0,
                            remaining_balance=None
                        )
                        schedule.insert(i, new_row)
                        break
        
        # Generate journal entries
        logger.info("📝 Generating journal entries...")
        journal_gen = JournalGenerator(gaap_standard=filters.gaap_standard)
        journals = journal_gen.generate_journals(result, schedule, None)
        
        # Prepare response
        response = {
            'lease_result': result.to_dict(),
            'schedule': [row.to_dict() for row in schedule],
            'journal_entries': [j.to_dict() for j in journals],
            'date_range': {
                'filtered': bool(from_date or to_date),
                'from_date': from_date.isoformat() if from_date else None,
                'to_date': to_date.isoformat() if to_date else None,
            }
        }
        
        logger.info("✅ Calculation complete")
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"❌ Error in calculate_lease: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _map_lease_to_leasedata(lease_dict: dict) -> LeaseData:
    """Map database lease dict to LeaseData model"""
    # Extract borrowing_rate properly from payload (check 'ibr' first, then 'borrowing_rate')
    ibr_val = lease_dict.get('ibr')
    br_val = lease_dict.get('borrowing_rate')
    borrowing_rate = None
    if ibr_val is not None and ibr_val != '':
        try:
            borrowing_rate = float(ibr_val)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid borrowing_rate value in 'ibr' field: {ibr_val}. Must be a valid number.")
    elif br_val is not None and br_val != '':
        try:
            borrowing_rate = float(br_val)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid borrowing_rate value in 'borrowing_rate' field: {br_val}. Must be a valid number.")
    
    if borrowing_rate is None:
        raise ValueError("borrowing_rate is required. Please provide either 'ibr' or 'borrowing_rate' field in the lease data.")
    
    # Parse rental_schedule from JSON if it exists in database
    rental_schedule = None
    rental_schedule_str = lease_dict.get('rental_schedule')
    if rental_schedule_str:
        try:
            import json
            if isinstance(rental_schedule_str, str):
                rental_schedule = json.loads(rental_schedule_str)
            else:
                rental_schedule = rental_schedule_str
        except (json.JSONDecodeError, TypeError):
            rental_schedule = None
    
    return LeaseData(
        auto_id=lease_dict.get('lease_id', 0),
        description=lease_dict.get('agreement_title') or lease_dict.get('description', ''),
        asset_class=lease_dict.get('asset_class', ''),
        asset_id_code=lease_dict.get('asset_id_code', ''),
        
        # Dates
        lease_start_date=_parse_date(lease_dict.get('lease_start_date')),
        first_payment_date=_parse_date(lease_dict.get('first_payment_date')),
        end_date=_parse_date(lease_dict.get('lease_end_date') or lease_dict.get('end_date')),
        agreement_date=_parse_date(lease_dict.get('rent_agreement_date') or lease_dict.get('agreement_date')),
        termination_date=_parse_date(lease_dict.get('termination_date')),
        
        # Financial Terms
        tenure=float(lease_dict.get('tenure_months', 0) or 0),
        frequency_months=int(lease_dict.get('rent_frequency', 1) or 1),
        day_of_month=str(lease_dict.get('pay_day_of_month', '1') or '1'),
        
        # Payments
        manual_adj="Yes" if str(lease_dict.get('manual_adj', '')).lower() in ['yes', 'on', 'true', '1'] else "No",
        payment_type=lease_dict.get('payment_type', 'advance').lower() or 'advance',  # "advance" or "arrear"
        
        # Rental Schedule from database - always required (source of truth for rentals)
        rental_schedule=rental_schedule,
        
        # Escalation - No defaults, must be explicitly provided
        escalation_start=_parse_date(lease_dict.get('escalation_start_date')),
        escalation_percent=float(lease_dict.get('escalation_percentage', 0) or 0),
        esc_freq_months=int(lease_dict.get('escalation_frequency') or lease_dict.get('esc_freq_months') or 0) if (lease_dict.get('escalation_frequency') or lease_dict.get('esc_freq_months')) else None,
        accrual_day=int(lease_dict.get('rent_accrual_day', 1) or 1),
        
        # Rates
        borrowing_rate=borrowing_rate,
        compound_months=int(lease_dict.get('compound_months')) if lease_dict.get('compound_months') else None,
        fv_of_rou=float(lease_dict.get('fair_value', 0) or 0),
        
        # Residual
        bargain_purchase=lease_dict.get('bargain_purchase', 'No'),
        purchase_option_price=float(lease_dict.get('purchase_option_price', 0) or 0),
        title_transfer=lease_dict.get('title_transfer', 'No'),
        useful_life=_parse_date(lease_dict.get('useful_life_end_date')),
        
        # Entity
        currency=lease_dict.get('currency', 'USD'),
        cost_centre=lease_dict.get('cost_center', '') or lease_dict.get('cost_centre', ''),
        counterparty=lease_dict.get('company_name') or lease_dict.get('counterparty', ''),
        
        # Security
        security_deposit=float(lease_dict.get('security_deposit_amount', 0) or 0),
        security_discount=float(lease_dict.get('security_discount_rate', 0) or 0),
        increase_security_1=0,
        increase_security_2=0,
        increase_security_3=0,
        increase_security_4=0,
        security_dates=[None, None, None, None],
        
        # ARO
        aro=float(lease_dict.get('aro_initial_estimate', 0) or 0),
        aro_table=int(lease_dict.get('aro_table', 0) or 0),
        aro_revisions=[0, 0, 0, 0],
        aro_dates=[None, None, None, None],
        
        # Initial Costs
        initial_direct_expenditure=float(lease_dict.get('initial_direct_expenditure', 0) or 0),
        lease_incentive=float(lease_dict.get('lease_incentive', 0) or 0),
        
        # Modifications
        modifies_this_id=None,
        modified_by_this_id=None,
        date_modified=None,
        
        # Sublease
        sublease=lease_dict.get('sublease', 'No'),
        sublease_rou=float(lease_dict.get('sublease_rou', 0) or 0),
        
        # Other
        profit_center=lease_dict.get('profit_center', ''),
        group_entity_name=lease_dict.get('group_entity_name', ''),
        short_term_lease_ifrs=lease_dict.get('short_term_ifrs', 'No'),
        short_term_lease_usgaap=lease_dict.get('short_term_usgaap', 'No'),
    )


@calc_bp.route('/consolidate_reports', methods=['POST'])
@require_login
def consolidate_reports():
    """
    Bulk consolidate calculation endpoint
    Processes multiple leases and returns consolidated results
    """
    try:
        data = request.json
        user_id = session['user_id']
        
        # Get lease IDs to process
        lease_ids = data.get('lease_ids', [])
        if not lease_ids:
            return jsonify({'error': 'No lease IDs provided'}), 400
        
        logger.info(f"📥 Received consolidate request: {len(lease_ids)} leases")
        
        # Parse date range filters
        from_date = _parse_date(data.get('from_date'))
        to_date = _parse_date(data.get('to_date'))
        
        if not from_date:
            from_date = date.today()
        if not to_date:
            to_date = date.today()
        
        # Create filters
        filters = ProcessingFilters(
            start_date=from_date,
            end_date=to_date,
            gaap_standard=data.get('gaap_standard', 'IFRS'),
            cost_center_filter=data.get('cost_center_filter'),
            entity_filter=data.get('entity_filter'),
            asset_class_filter=data.get('asset_class_filter'),
            profit_center_filter=data.get('profit_center_filter')
        )
        
        # Fetch leases from database
        logger.info(f"📋 Fetching {len(lease_ids)} leases from database...")
        lease_data_list = []
        
        for lease_id in lease_ids:
            try:
                lease_dict = database.get_lease(lease_id, user_id)
                if not lease_dict:
                    logger.warning(f"⚠️  Lease {lease_id} not found or not accessible")
                    continue
                
                # Map to LeaseData
                lease_data = _map_lease_to_leasedata(lease_dict)
                lease_data.gaap_standard = filters.gaap_standard
                lease_data_list.append(lease_data)
                
            except Exception as e:
                logger.error(f"❌ Error mapping lease {lease_id}: {e}")
                continue
        
        if not lease_data_list:
            return jsonify({'error': 'No valid leases found'}), 400
        
        logger.info(f"✅ Mapped {len(lease_data_list)} leases to LeaseData")
        
        # Process bulk leases
        logger.info(f"🔄 Processing {len(lease_data_list)} leases...")
        results_processor = ResultsProcessor(filters)
        bulk_result = results_processor.process_bulk_leases(lease_data_list)
        
        logger.info(f"✅ Bulk processing complete: {bulk_result['processed_count']} processed, {bulk_result['skipped_count']} skipped")
        
        # Prepare response
        response = {
            'success': True,
            'results': bulk_result['results'],
            'aggregated_totals': bulk_result['aggregated_totals'],
            'consolidated_journals': bulk_result['consolidated_journals'],
            'statistics': {
                'processed_count': bulk_result['processed_count'],
                'skipped_count': bulk_result['skipped_count'],
                'total_count': bulk_result['total_count']
            },
            'date_range': {
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat()
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"❌ Error in consolidate_reports: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

