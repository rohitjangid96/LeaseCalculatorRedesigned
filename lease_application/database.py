"""
Simplified Database layer - Users only
"""
import sqlite3
from typing import Dict, Optional
import bcrypt
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = "lease_management.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database tables - Users and Leases"""
    with get_db_connection() as conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Leases table - stores all lease data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leases (
                lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                agreement_title TEXT,
                company_name TEXT,
                asset_class TEXT,
                asset_title TEXT,
                asset_id_code TEXT,
                currency TEXT,
                counterparty TEXT,
                asset_location TEXT,
                related_party INTEGER DEFAULT 0,
                lease_start_date DATE,
                lease_end_date DATE,
                rent_agreement_date DATE,
                posting_date_same INTEGER DEFAULT 1,
                posting_date DATE,
                judgements TEXT,
                payment_type TEXT,
                first_payment_date DATE,
                rent_frequency INTEGER,
                payment_interval INTEGER,
                pay_day_of_month TEXT,
                rent_accrual_day INTEGER,
                rental_amount REAL,
                escalation_start_date DATE,
                escalation_frequency INTEGER,
                fair_value REAL,
                irr REAL,
                ibr REAL,
                compound_months INTEGER,
                use_rate_type TEXT,
                initial_direct_expenditure REAL,
                lease_incentive REAL,
                has_purchase_option INTEGER DEFAULT 0,
                purchase_option_price REAL,
                useful_life_months INTEGER,
                useful_life_end_date DATE,
                has_security_deposit INTEGER DEFAULT 0,
                security_deposit_amount REAL,
                security_deposit_date DATE,
                security_discount_rate REAL,
                has_aro INTEGER DEFAULT 0,
                aro_initial_estimate REAL,
                transition_date DATE,
                transition_option TEXT,
                lease_classification TEXT,
                short_term_usgaap INTEGER DEFAULT 0,
                short_term_ifrs INTEGER DEFAULT 0,
                low_value_asset INTEGER DEFAULT 0,
                scope_exemption INTEGER DEFAULT 0,
                cost_center TEXT,
                allocation TEXT,
                entered_by TEXT,
                last_modified_date DATE,
                reviewed_by TEXT,
                last_reviewed_date DATE,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Add role and is_active columns if they don't exist (migration for existing databases)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migrate leases table - add missing columns if they don't exist
        migrate_leases_table(conn)
        
        logger.info("✅ Database initialized (users and leases tables)")


def migrate_leases_table(conn):
    """Add missing columns to leases table for compatibility with form fields"""
    migrations = [
        ("agreement_title", "TEXT"),
        ("company_name", "TEXT"),
        ("lease_end_date", "DATE"),
        ("status", "TEXT DEFAULT 'draft'"),
        ("escalation_percentage", "REAL"),
        ("rental_amount", "REAL"),
        ("escalation_frequency", "INTEGER"),
        ("rent_frequency", "INTEGER"),
        ("payment_interval", "INTEGER"),
        ("pay_day_of_month", "TEXT"),
        ("rent_accrual_day", "INTEGER"),
        ("payment_type", "TEXT"),
        ("rent_agreement_date", "DATE"),
        ("posting_date", "DATE"),
        ("asset_title", "TEXT"),
        ("related_party", "INTEGER DEFAULT 0"),
        ("posting_date_same", "INTEGER DEFAULT 1"),
        ("judgements", "TEXT"),
        ("has_purchase_option", "INTEGER DEFAULT 0"),
        ("purchase_option_price", "REAL"),
        ("useful_life_months", "INTEGER"),
        ("useful_life_end_date", "DATE"),
        ("has_security_deposit", "INTEGER DEFAULT 0"),
        ("security_deposit_amount", "REAL"),
        ("security_deposit_date", "DATE"),
        ("security_discount_rate", "REAL"),
        ("has_aro", "INTEGER DEFAULT 0"),
        ("aro_initial_estimate", "REAL"),
        ("transition_date", "DATE"),
        ("transition_option", "TEXT"),
        ("lease_classification", "TEXT"),
        ("short_term_usgaap", "INTEGER DEFAULT 0"),
        ("short_term_ifrs", "INTEGER DEFAULT 0"),
        ("low_value_asset", "INTEGER DEFAULT 0"),
        ("scope_exemption", "INTEGER DEFAULT 0"),
        ("cost_center", "TEXT"),
        ("allocation", "TEXT"),
        ("entered_by", "TEXT"),
        ("last_modified_date", "DATE"),
        ("reviewed_by", "TEXT"),
        ("last_reviewed_date", "DATE"),
        ("rental_schedule", "TEXT"),  # JSON string storing rental schedule array
        # Financial fields
        ("ibr", "REAL"),  # Incremental Borrowing Rate
        ("irr", "REAL"),
        ("fair_value", "REAL"),
        ("compound_months", "INTEGER"),
        ("use_rate_type", "TEXT"),
        ("initial_direct_expenditure", "REAL"),
        ("lease_incentive", "REAL"),
        # Missing form fields
        ("tenure_months", "REAL"),
        ("tenure_days_input", "INTEGER"),
        ("has_renewal_option", "INTEGER DEFAULT 0"),
        ("renewal_start_date", "DATE"),
        ("renewal_end_date", "DATE"),
        ("renewal_term", "TEXT"),
        ("has_termination_option", "INTEGER DEFAULT 0"),
        ("lease_classification_usgaap", "TEXT"),
        ("scope_exemption_applied", "INTEGER DEFAULT 0"),
        ("sublease_start_date", "DATE"),
        ("sublease_end_date", "DATE"),
        ("sublease_payment_details", "TEXT"),  # JSON string for sublease payment details
    ]
    
    # Check if borrowing_rate exists and migrate it to ibr if needed
    try:
        cursor = conn.execute("PRAGMA table_info(leases)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # If borrowing_rate exists but ibr doesn't, copy data and rename
        if 'borrowing_rate' in existing_columns and 'ibr' not in existing_columns:
            logger.info("🔄 Migrating borrowing_rate to ibr column")
            try:
                conn.execute("ALTER TABLE leases ADD COLUMN ibr REAL")
                conn.execute("UPDATE leases SET ibr = borrowing_rate WHERE borrowing_rate IS NOT NULL")
                logger.info("✅ Migrated borrowing_rate data to ibr column")
            except sqlite3.OperationalError as e:
                logger.warning(f"⚠️ Could not migrate borrowing_rate to ibr: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Error checking for column migration: {e}")
    
    for column_name, column_def in migrations:
        try:
            conn.execute(f"ALTER TABLE leases ADD COLUMN {column_name} {column_def}")
            logger.info(f"✅ Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                logger.warning(f"⚠️ Could not add column {column_name}: {e}")


# ============ USER MANAGEMENT ============

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_user(username: str, password: str, email: Optional[str] = None) -> int:
    """Create a new user"""
    password_hash = hash_password(password)
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email)
        )
        return cursor.lastrowid


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user and return user data if valid"""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        
        if row and verify_password(password, row['password_hash']):
            return dict(row)
        return None


def get_user(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT user_id, username, email, role, is_active, created_at FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


# ============ LEASE MANAGEMENT ============

def save_lease(user_id: int, lease_data: Dict) -> int:
    """Save or update a lease"""
    lease_id = lease_data.get('lease_id')
    
    # Map form field names to database column names
    field_mapping = {
        'agreement_title': 'agreement_title',
        'company_name': 'company_name',
        'escalation_percentage': 'escalation_percentage',
        'rental_amount': 'rental_amount',
        'escalation_frequency': 'escalation_frequency',
        'rent_frequency': 'rent_frequency',
        'payment_interval': 'payment_interval',
        'pay_day_of_month': 'pay_day_of_month',
        'rent_accrual_day': 'rent_accrual_day',
        'payment_type': 'payment_type',
        'rent_agreement_date': 'rent_agreement_date',
        'posting_date': 'posting_date',
        'asset_title': 'asset_title',
        'lease_end_date': 'lease_end_date',
        'status': 'status',
        'ibr': 'ibr',  # Form field 'ibr' maps to database column 'ibr'
        'asset_id_code': 'asset_id_code',
        'asset_class': 'asset_class',
        'asset_location': 'asset_location',
        'counterparty': 'counterparty',
        'currency': 'currency',
        'lease_start_date': 'lease_start_date',
        'first_payment_date': 'first_payment_date',
        'escalation_start_date': 'escalation_start_date',
        'fair_value': 'fair_value',
        'irr': 'irr',
        'compound_months': 'compound_months',
        'use_rate_type': 'use_rate_type',
        'initial_direct_expenditure': 'initial_direct_expenditure',
        'lease_incentive': 'lease_incentive',
        'purchase_option_price': 'purchase_option_price',
        'useful_life_months': 'useful_life_months',
        'useful_life_end_date': 'useful_life_end_date',
        'security_deposit_amount': 'security_deposit_amount',
        'security_deposit_date': 'security_deposit_date',
        'security_discount_rate': 'security_discount_rate',
        'transition_date': 'transition_date',
        'transition_option': 'transition_option',
        'lease_classification': 'lease_classification',
        'cost_center': 'cost_center',
        'allocation': 'allocation',
        'entered_by': 'entered_by',
        'last_modified_date': 'last_modified_date',
        'reviewed_by': 'reviewed_by',
        'last_reviewed_date': 'last_reviewed_date',
        'judgements': 'judgements',
        'termination_date': 'termination_date',
        'termination_penalty': 'termination_penalty',
        # New fields
        'tenure_months': 'tenure_months',
        'tenure_days_input': 'tenure_days_input',
        'has_renewal_option': 'has_renewal_option',
        'renewal_start_date': 'renewal_start_date',
        'renewal_end_date': 'renewal_end_date',
        'renewal_term': 'renewal_term',
        'has_termination_option': 'has_termination_option',
        'lease_classification_usgaap': 'lease_classification_usgaap',
        'scope_exemption_applied': 'scope_exemption_applied',
        'sublease_start_date': 'sublease_start_date',
        'sublease_end_date': 'sublease_end_date',
        'sublease_payment_details': 'sublease_payment_details',
    }
    
    # Create mapped data
    mapped_data = {}
    
    for key, value in lease_data.items():
        if key == 'lease_id' or key == 'user_id':
            continue
        
        # Handle rental_schedule - convert to JSON string for storage
        if key == 'rental_schedule' and value is not None:
            import json
            if isinstance(value, (list, dict)):
                mapped_data['rental_schedule'] = json.dumps(value)
            else:
                mapped_data['rental_schedule'] = value
            continue
        
        # Handle sublease_payment_details - convert to JSON string for storage
        if key == 'sublease_payment_details' and value is not None:
            import json
            if isinstance(value, (list, dict)):
                mapped_data['sublease_payment_details'] = json.dumps(value)
            else:
                mapped_data['sublease_payment_details'] = value
            continue
        
        # Use mapped name if exists, otherwise use original
        db_key = field_mapping.get(key, key)
        mapped_data[db_key] = value
    
    # Also map legacy fields - handle both directions
    # Map agreement_title to lease_name if lease_name exists in database
    if 'agreement_title' in mapped_data and mapped_data.get('agreement_title'):
        # Check if we need to also populate lease_name (old column name)
        mapped_data['lease_name'] = mapped_data.get('agreement_title')
    elif 'lease_name' in lease_data and lease_data.get('lease_name'):
        # If only lease_name is provided, use it for both
        if 'agreement_title' not in mapped_data:
            mapped_data['agreement_title'] = lease_data.get('lease_name')
        mapped_data['lease_name'] = lease_data.get('lease_name')
    
    # Ensure lease_name is not empty if it's required in database
    # Always populate lease_name if the column exists (it's NOT NULL)
    if 'lease_name' not in mapped_data or not mapped_data.get('lease_name') or mapped_data.get('lease_name') == '':
        # Use agreement_title if available, otherwise use a default
        if mapped_data.get('agreement_title') and mapped_data.get('agreement_title').strip() != '':
            mapped_data['lease_name'] = mapped_data.get('agreement_title')
        elif lease_data.get('agreement_title') and lease_data.get('agreement_title').strip() != '':
            mapped_data['lease_name'] = lease_data.get('agreement_title')
        else:
            # Provide a default value if neither exists
            mapped_data['lease_name'] = 'Untitled Lease'
    
    # Also ensure agreement_title is set if lease_name is available but agreement_title is not
    if (not mapped_data.get('agreement_title') or mapped_data.get('agreement_title') == '') and mapped_data.get('lease_name'):
        mapped_data['agreement_title'] = mapped_data.get('lease_name')
    
    if 'counterparty' in lease_data and 'company_name' not in mapped_data:
        mapped_data['company_name'] = lease_data.get('counterparty')
    if 'end_date' in lease_data and 'lease_end_date' not in mapped_data:
        mapped_data['lease_end_date'] = lease_data.get('end_date')
    
    # Convert checkboxes to integers
    for key in ['related_party', 'posting_date_same', 'has_purchase_option', 
                'has_security_deposit', 'has_aro', 'short_term_usgaap', 
                'short_term_ifrs', 'low_value_asset', 'scope_exemption',
                'has_renewal_option', 'has_termination_option', 'scope_exemption_applied']:
        if key in mapped_data:
            mapped_data[key] = 1 if mapped_data[key] in [True, 'true', '1', 'on'] else 0
    
    # Handle dates - convert empty strings to None
    date_fields = ['lease_start_date', 'lease_end_date', 'rent_agreement_date', 
                   'posting_date', 'first_payment_date', 'escalation_start_date',
                   'useful_life_end_date', 'security_deposit_date', 'transition_date',
                   'last_modified_date', 'last_reviewed_date', 'termination_date',
                   'renewal_start_date', 'renewal_end_date', 'sublease_start_date', 'sublease_end_date']
    
    for field in date_fields:
        if field in mapped_data and (mapped_data[field] == '' or mapped_data[field] is None):
            mapped_data[field] = None
    
    # Convert numeric strings to proper types
    numeric_fields = ['escalation_percentage', 'rental_amount', 'escalation_frequency', 
                     'rent_frequency', 'payment_interval', 'rent_accrual_day',
                     'purchase_option_price', 'useful_life_months', 'security_deposit_amount',
                     'security_discount_rate', 'aro_initial_estimate', 'ibr']
    
    for field in numeric_fields:
        if field in mapped_data:
            value = mapped_data[field]
            # Convert empty strings to None for numeric fields
            if value == '' or value is None:
                mapped_data[field] = None
            else:
                try:
                    mapped_data[field] = float(value) if '.' in str(value) else int(value)
                except (ValueError, TypeError):
                    mapped_data[field] = None
    
    mapped_data['user_id'] = user_id
    
    # Use mapped_data instead of lease_data from here
    lease_data_to_save = mapped_data
    
    if lease_id:
        # Update existing lease
        update_fields = [k for k in lease_data_to_save.keys() if k != 'lease_id' and k != 'user_id']
        if not update_fields:
            logger.warning("No fields to update")
            return lease_id
        
        # Filter out None values for optional fields that might cause issues
        filtered_fields = []
        filtered_values = []
        for field in update_fields:
            value = lease_data_to_save.get(field)
            # Allow None values for IBR and other numeric fields, as well as boolean fields
            if value is not None or field in ['related_party', 'posting_date_same', 'has_purchase_option', 
                                             'has_security_deposit', 'has_aro', 'short_term_usgaap', 
                                             'short_term_ifrs', 'low_value_asset', 'scope_exemption',
                                             'ibr']:
                filtered_fields.append(field)
                filtered_values.append(value)
        
        if not filtered_fields:
            logger.warning("No valid fields to update after filtering")
            return lease_id

        with get_db_connection() as conn:
            # Get existing columns from database
            cursor = conn.execute("PRAGMA table_info(leases)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Filter update fields to only include columns that exist
            valid_update_fields = []
            valid_update_values = []
            for i, field in enumerate(filtered_fields):
                if field in existing_columns:
                    valid_update_fields.append(field)
                    valid_update_values.append(filtered_values[i])
                else:
                    logger.warning(f"Skipping field '{field}' - column does not exist in database")
            
            if not valid_update_fields:
                logger.warning("No valid fields to update after filtering for existing columns")
                return lease_id
            
            set_clause = ', '.join([f"{f} = ?" for f in valid_update_fields])
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            
            update_values = valid_update_values.copy()
            update_values.append(lease_id)
            update_values.append(user_id)
            
            # Log IBR update for debugging
            if 'ibr' in valid_update_fields:
                ibr_index = valid_update_fields.index('ibr')
                logger.info(f"📝 Updating IBR for lease {lease_id}: {valid_update_values[ibr_index]}")
            
            logger.info(f"📝 UPDATE SQL: UPDATE leases SET {set_clause} WHERE lease_id = ? AND user_id = ?")
            logger.info(f"📝 UPDATE values: {update_values}")
            
            conn.execute(
                f"UPDATE leases SET {set_clause} WHERE lease_id = ? AND user_id = ?",
                update_values
            )
            conn.commit()
            
            # Verify the update
            updated_row = conn.execute(
                "SELECT ibr FROM leases WHERE lease_id = ? AND user_id = ?",
                (lease_id, user_id)
            ).fetchone()
            if updated_row:
                logger.info(f"✅ Verified IBR after update: {updated_row[0]}")
        return lease_id
    else:
        # Create new lease
        fields = [k for k in lease_data_to_save.keys() if k != 'lease_id']
        # Filter out None values for fields that can't be None
        filtered_fields = []
        filtered_values = []
        for field in fields:
            value = lease_data_to_save.get(field)
            # Include field even if None for optional fields
            filtered_fields.append(field)
            filtered_values.append(value)
        
        if not filtered_fields:
            logger.error("No fields to insert")
            raise ValueError("No fields to insert into leases table")
        
        with get_db_connection() as conn:
            # Get existing columns from database
            cursor = conn.execute("PRAGMA table_info(leases)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Filter fields to only include columns that exist in database
            valid_fields = []
            valid_values = []
            for i, field in enumerate(filtered_fields):
                if field in existing_columns:
                    valid_fields.append(field)
                    valid_values.append(filtered_values[i])
                else:
                    logger.warning(f"Skipping field '{field}' - column does not exist in database")
            
            if not valid_fields:
                logger.error("No valid fields to insert after filtering for existing columns")
                raise ValueError("No valid fields to insert into leases table")
            
            placeholders = ', '.join(['?' for _ in valid_fields])
            
            try:
                cursor = conn.execute(
                    f"INSERT INTO leases ({', '.join(valid_fields)}) VALUES ({placeholders})",
                    valid_values
                )
                return cursor.lastrowid
            except sqlite3.OperationalError as e:
                logger.error(f"Error inserting lease: {e}")
                logger.error(f"Fields being inserted: {valid_fields}")
                logger.error(f"Values: {valid_values[:5]}...")  # Log first 5 values
                raise


def get_lease(lease_id: int, user_id: int) -> Optional[Dict]:
    """Get lease by ID (only if owned by user)"""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM leases WHERE lease_id = ? AND user_id = ?",
            (lease_id, user_id)
            ).fetchone()
        if not row:
            return None
        
        # Convert sqlite3.Row to dict properly
        # Use column names as keys to ensure correct field names
        lease_dict = {key: row[key] for key in row.keys()}
        
        # Log IBR value for debugging
        ibr_value = lease_dict.get('ibr')
        logger.info(f"📋 Retrieved lease {lease_id}: IBR = {ibr_value} (type: {type(ibr_value)})")
        # Ensure IBR is properly converted to a number if it exists
        if ibr_value is not None and ibr_value != '':
            try:
                lease_dict['ibr'] = float(ibr_value)
                logger.info(f"📋 Converted IBR to float: {lease_dict['ibr']}")
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Could not convert IBR to float: {e}")
        
        # Parse JSON fields back to objects for form auto-population
        import json
        if lease_dict.get('rental_schedule'):
            try:
                if isinstance(lease_dict['rental_schedule'], str):
                    lease_dict['rental_schedule'] = json.loads(lease_dict['rental_schedule'])
                    logger.debug(f"✅ Parsed rental_schedule from JSON string to list with {len(lease_dict['rental_schedule'])} entries")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ Error parsing rental_schedule: {e}")
                pass  # Keep as string if parsing fails
        
        if lease_dict.get('sublease_payment_details'):
            try:
                if isinstance(lease_dict['sublease_payment_details'], str):
                    lease_dict['sublease_payment_details'] = json.loads(lease_dict['sublease_payment_details'])
            except (json.JSONDecodeError, TypeError):
                pass  # Keep as string if parsing fails
        
        logger.debug(f"📋 Returning lease_dict with rental_schedule: {type(lease_dict.get('rental_schedule'))}, value: {lease_dict.get('rental_schedule')}")
        return lease_dict


def get_all_leases(user_id: int) -> list:
    """Get all leases for a user"""
    with get_db_connection() as conn:
        # Check if new columns exist, otherwise use old column names
        cursor = conn.execute("PRAGMA table_info(leases)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Build SELECT with fallbacks for missing columns
        select_parts = ["lease_id"]
        
        if 'agreement_title' in columns:
            select_parts.append("agreement_title")
        elif 'lease_name' in columns:
            select_parts.append("lease_name as agreement_title")
        else:
            select_parts.append("NULL as agreement_title")
        
        if 'company_name' in columns:
            select_parts.append("company_name")
        elif 'counterparty' in columns:
            select_parts.append("counterparty as company_name")
        else:
            select_parts.append("NULL as company_name")
        
        select_parts.append("asset_class")
        select_parts.append("lease_start_date")
        
        if 'lease_end_date' in columns:
            select_parts.append("lease_end_date")
        elif 'end_date' in columns:
            select_parts.append("end_date as lease_end_date")
        else:
            select_parts.append("NULL as lease_end_date")
        
        if 'status' in columns:
            select_parts.append("status")
        elif 'approval_status' in columns:
            select_parts.append("approval_status as status")
        else:
            select_parts.append("'draft' as status")
        
        select_parts.append("created_at")
        
        query = f"""SELECT {', '.join(select_parts)}
                   FROM leases 
                   WHERE user_id = ? 
                   ORDER BY created_at DESC"""
        
        rows = conn.execute(query, (user_id,)).fetchall()
        return [dict(row) for row in rows]


def delete_lease(lease_id: int, user_id: int) -> bool:
    """Delete a lease (only if owned by user)"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM leases WHERE lease_id = ? AND user_id = ?",
            (lease_id, user_id)
        )
        return cursor.rowcount > 0


# Initialize database on import
init_database()
