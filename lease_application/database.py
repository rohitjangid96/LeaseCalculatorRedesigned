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

        # App configuration table (key-value)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Lease audit trail
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lease_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lease_id INTEGER NOT NULL,
                user TEXT,
                action TEXT,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        
        create_document_table(conn)
        create_audit_table(conn)
        logger.info("✅ Database initialized (users and leases tables)")


def create_audit_table(conn):
    """Create the lease_data_audit table"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lease_data_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lease_id INTEGER NOT NULL,
            changed_by_user_id INTEGER NOT NULL,
            changed_by_username TEXT,
            change_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            action TEXT NOT NULL,
            FOREIGN KEY (lease_id) REFERENCES leases (lease_id)
        );
    """)
    logger.info("✅ lease_data_audit table initialized")


def create_document_table(conn):
    """Create the lease_documents table"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lease_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lease_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uploaded_by INTEGER,
            document_type TEXT,
            FOREIGN KEY (lease_id) REFERENCES leases (lease_id),
            FOREIGN KEY (uploaded_by) REFERENCES users (user_id)
        )
    """)
    logger.info("✅ lease_documents table initialized")


def save_document_metadata(lease_id, file_name, file_path, file_size, uploaded_by, document_type=None):
    """Saves document metadata to the database."""
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO lease_documents (lease_id, file_name, file_path, file_size, uploaded_by, document_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lease_id, file_name, file_path, file_size, uploaded_by, document_type)
        )


def get_documents_by_lease(lease_id):
    """Retrieves all documents for a given lease, excluding file_path."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT document_id, lease_id, file_name, file_size, uploaded_at, uploaded_by, document_type
               FROM lease_documents WHERE lease_id = ? ORDER BY uploaded_at DESC""",
            (lease_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_document_by_id(document_id):
    """Retrieves a single document's metadata by its ID."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lease_documents WHERE document_id = ?",
            (document_id,)
        ).fetchone()
        return dict(row) if row else None


# ============ APP CONFIG ============
def get_configs() -> Dict:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT key, value FROM app_config").fetchall()
        return {r['key']: r['value'] for r in rows}

def set_config(key: str, value: str):
    with get_db_connection() as conn:
        conn.execute("INSERT INTO app_config(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

def get_config(key: str) -> Optional[str]:
    with get_db_connection() as conn:
        row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else None


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
        ("submitted_by", "TEXT"),
        ("submitted_at", "TIMESTAMP"),
        ("approved_by", "TEXT"),
        ("approved_at", "TIMESTAMP"),
        ("rejection_reason", "TEXT"),
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


# ============ EMAIL ============
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(smtp_host: str, smtp_port: int, username: str, password: str, from_addr: str, to_addrs: list, subject: str, html_body: str):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = ', '.join(to_addrs)

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        if username and password:
            server.login(username, password)
        server.sendmail(from_addr, to_addrs, msg.as_string())


# ============ ADMIN / USERS ============
def list_users() -> list:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT user_id, username, email, role, is_active, created_at FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def set_user_role(user_id: int, role: str):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))

def set_user_active(user_id: int, is_active: bool):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if is_active else 0, user_id))


def add_lease_audit(lease_id: int, user: str, action: str, comment: str = None):
    with get_db_connection() as conn:
        conn.execute("INSERT INTO lease_audit(lease_id, user, action, comment) VALUES(?, ?, ?, ?)", (lease_id, user, action, comment))


# ============ APPROVAL FLOW ============
def submit_lease_for_review(lease_id: int, user_id: int):
    old_lease = get_lease(lease_id, user_id)
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE leases SET status = 'submitted', submitted_by = (SELECT username FROM users WHERE user_id = ?), submitted_at = CURRENT_TIMESTAMP WHERE lease_id = ? AND user_id = ?",
            (user_id, lease_id, user_id)
        )
    new_lease = get_lease(lease_id, user_id)
    user = get_user(user_id)
    username = user.get('username', str(user_id))
    add_data_change_audit_log(lease_id, user_id, username, 'status', old_lease.get('status'), new_lease.get('status'), action='UPDATE')

def approve_lease(lease_id: int, approver_user_id: int):
    old_lease = get_lease(lease_id)
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE leases SET status = 'approved', approved_by = (SELECT username FROM users WHERE user_id = ?), approved_at = CURRENT_TIMESTAMP, last_reviewed_date = CURRENT_TIMESTAMP, reviewed_by = (SELECT username FROM users WHERE user_id = ?) WHERE lease_id = ?",
            (approver_user_id, approver_user_id, lease_id)
        )
    new_lease = get_lease(lease_id)
    user = get_user(approver_user_id)
    username = user.get('username', str(approver_user_id))
    add_data_change_audit_log(lease_id, approver_user_id, username, 'status', old_lease.get('status'), new_lease.get('status'), action='UPDATE')

def reject_lease(lease_id: int, approver_user_id: int, reason: str):
    old_lease = get_lease(lease_id)
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE leases SET status = 'rejected', rejection_reason = ?, approved_by = NULL, approved_at = NULL, last_reviewed_date = CURRENT_TIMESTAMP, reviewed_by = (SELECT username FROM users WHERE user_id = ?) WHERE lease_id = ?",
            (reason, approver_user_id, lease_id)
        )
    new_lease = get_lease(lease_id)
    user = get_user(approver_user_id)
    username = user.get('username', str(approver_user_id))
    add_data_change_audit_log(lease_id, approver_user_id, username, 'status', old_lease.get('status'), new_lease.get('status'), action='UPDATE')
    if reason:
        add_data_change_audit_log(lease_id, approver_user_id, username, 'rejection_reason', old_lease.get('rejection_reason'), reason, action='UPDATE')


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


def get_user_by_username(username: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT user_id, username, email, role, is_active, created_at FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        return dict(row) if row else None


# ============ LEASE MANAGEMENT ============

def add_data_change_audit_log(lease_id, user_id, username, field_name, old_value, new_value, action='UPDATE'):
    """Logs a specific data field change for a lease."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO lease_data_audit (lease_id, changed_by_user_id, changed_by_username, field_name, old_value, new_value, action)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (lease_id, user_id, username, field_name, str(old_value), str(new_value), action)
        )


def save_lease(user_id: int, lease_data: Dict, role: str = 'user') -> tuple:
    """Save or update a lease and audit the changes."""
    lease_id = lease_data.get('lease_id')
    old_lease_data = None
    if lease_id:
        old_lease_data = get_lease(lease_id)

    field_mapping = {
        'agreement_title': 'agreement_title', 'company_name': 'company_name', 'escalation_percentage': 'escalation_percentage',
        'rental_amount': 'rental_amount', 'escalation_frequency': 'escalation_frequency', 'rent_frequency': 'rent_frequency',
        'payment_interval': 'payment_interval', 'pay_day_of_month': 'pay_day_of_month', 'rent_accrual_day': 'rent_accrual_day',
        'payment_type': 'payment_type', 'rent_agreement_date': 'rent_agreement_date', 'posting_date': 'posting_date',
        'asset_title': 'asset_title', 'lease_end_date': 'lease_end_date', 'status': 'status', 'ibr': 'ibr',
        'asset_id_code': 'asset_id_code', 'asset_class': 'asset_class', 'asset_location': 'asset_location',
        'counterparty': 'counterparty', 'currency': 'currency', 'lease_start_date': 'lease_start_date',
        'first_payment_date': 'first_payment_date', 'escalation_start_date': 'escalation_start_date', 'fair_value': 'fair_value',
        'irr': 'irr', 'compound_months': 'compound_months', 'use_rate_type': 'use_rate_type',
        'initial_direct_expenditure': 'initial_direct_expenditure', 'lease_incentive': 'lease_incentive',
        'purchase_option_price': 'purchase_option_price', 'useful_life_months': 'useful_life_months',
        'useful_life_end_date': 'useful_life_end_date', 'security_deposit_amount': 'security_deposit_amount',
        'security_deposit_date': 'security_deposit_date', 'security_discount_rate': 'security_discount_rate',
        'transition_date': 'transition_date', 'transition_option': 'transition_option', 'lease_classification': 'lease_classification',
        'cost_center': 'cost_center', 'allocation': 'allocation', 'entered_by': 'entered_by',
        'last_modified_date': 'last_modified_date', 'reviewed_by': 'reviewed_by', 'last_reviewed_date': 'last_reviewed_date',
        'judgements': 'judgements', 'termination_date': 'termination_date', 'termination_penalty': 'termination_penalty',
        'tenure_months': 'tenure_months', 'tenure_days_input': 'tenure_days_input', 'has_renewal_option': 'has_renewal_option',
        'renewal_start_date': 'renewal_start_date', 'renewal_end_date': 'renewal_end_date', 'renewal_term': 'renewal_term',
        'has_termination_option': 'has_termination_option', 'lease_classification_usgaap': 'lease_classification_usgaap',
        'scope_exemption_applied': 'scope_exemption_applied', 'sublease_start_date': 'sublease_start_date',
        'sublease_end_date': 'sublease_end_date', 'sublease_payment_details': 'sublease_payment_details',
    }
    
    mapped_data = {}
    for key, value in lease_data.items():
        if key in ['lease_id', 'user_id']:
            continue
        if key in ['rental_schedule', 'sublease_payment_details'] and value is not None:
            import json
            mapped_data[key] = json.dumps(value) if isinstance(value, (list, dict)) else value
            continue
        db_key = field_mapping.get(key, key)
        mapped_data[db_key] = value

    if 'agreement_title' in mapped_data and mapped_data.get('agreement_title'):
        mapped_data['lease_name'] = mapped_data.get('agreement_title')
    elif 'lease_name' in lease_data and lease_data.get('lease_name'):
        if 'agreement_title' not in mapped_data:
            mapped_data['agreement_title'] = lease_data.get('lease_name')
        mapped_data['lease_name'] = lease_data.get('lease_name')
    
    if 'lease_name' not in mapped_data or not mapped_data.get('lease_name'):
        mapped_data['lease_name'] = mapped_data.get('agreement_title') or 'Untitled Lease'
    
    if not mapped_data.get('agreement_title') and mapped_data.get('lease_name'):
        mapped_data['agreement_title'] = mapped_data.get('lease_name')
    
    if 'counterparty' in lease_data and 'company_name' not in mapped_data:
        mapped_data['company_name'] = lease_data.get('counterparty')
    if 'end_date' in lease_data and 'lease_end_date' not in mapped_data:
        mapped_data['lease_end_date'] = lease_data.get('end_date')

    for key in ['related_party', 'posting_date_same', 'has_purchase_option', 'has_security_deposit', 'has_aro', 'short_term_usgaap', 'short_term_ifrs', 'low_value_asset', 'scope_exemption', 'has_renewal_option', 'has_termination_option', 'scope_exemption_applied']:
        if key in mapped_data:
            mapped_data[key] = 1 if mapped_data[key] in [True, 'true', '1', 'on'] else 0

    date_fields = ['lease_start_date', 'lease_end_date', 'rent_agreement_date', 'posting_date', 'first_payment_date', 'escalation_start_date', 'useful_life_end_date', 'security_deposit_date', 'transition_date', 'last_modified_date', 'last_reviewed_date', 'termination_date', 'renewal_start_date', 'renewal_end_date', 'sublease_start_date', 'sublease_end_date']
    for field in date_fields:
        if field in mapped_data and not mapped_data[field]:
            mapped_data[field] = None

    numeric_fields = ['escalation_percentage', 'rental_amount', 'escalation_frequency', 'rent_frequency', 'payment_interval', 'rent_accrual_day', 'purchase_option_price', 'useful_life_months', 'security_deposit_amount', 'security_discount_rate', 'aro_initial_estimate', 'ibr']
    for field in numeric_fields:
        if field in mapped_data:
            value = mapped_data[field]
            if value in ['', None]:
                mapped_data[field] = None
            else:
                try:
                    mapped_data[field] = float(value) if '.' in str(value) else int(value)
                except (ValueError, TypeError):
                    mapped_data[field] = None
    
    mapped_data['user_id'] = user_id
    lease_data_to_save = mapped_data

    if lease_id:
        # Update
        update_fields = [k for k in lease_data_to_save.keys() if k not in ['lease_id', 'user_id']]
        if not update_fields:
            return lease_id, old_lease_data
        
        with get_db_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(leases)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            valid_update_fields = {f for f in update_fields if f in existing_columns}
            if not valid_update_fields:
                return lease_id, old_lease_data

            set_clause = ', '.join([f"{f} = ?" for f in valid_update_fields]) + ", updated_at = CURRENT_TIMESTAMP"
            update_values = [lease_data_to_save.get(f) for f in valid_update_fields]
            update_values.append(lease_id)
            
            if role != 'admin':
                update_values.append(user_id)
                conn.execute(f"UPDATE leases SET {set_clause} WHERE lease_id = ? AND user_id = ?", update_values)
            else:
                conn.execute(f"UPDATE leases SET {set_clause} WHERE lease_id = ?", update_values)
        
        if old_lease_data:
            user = get_user(user_id)
            username = user.get('username', str(user_id))
            for key, new_value in lease_data_to_save.items():
                if key in ['user_id', 'lease_id', 'created_at', 'updated_at']:
                    continue
                old_value = old_lease_data.get(key)
                if str(old_value) != str(new_value):
                    add_data_change_audit_log(lease_id, user_id, username, key, old_value, new_value, action='UPDATE')
        
        return lease_id, old_lease_data
    else:
        # Create
        with get_db_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(leases)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            valid_fields = {f for f in lease_data_to_save.keys() if f in existing_columns}
            if not valid_fields:
                raise ValueError("No valid fields to insert")

            placeholders = ', '.join(['?' for _ in valid_fields])
            field_names = ', '.join(valid_fields)
            field_values = [lease_data_to_save.get(f) for f in valid_fields]
            
            cursor = conn.execute(f"INSERT INTO leases ({field_names}) VALUES ({placeholders})", field_values)
            new_lease_id = cursor.lastrowid

        user = get_user(user_id)
        username = user.get('username', str(user_id))
        for key, value in lease_data_to_save.items():
            if key not in ['user_id', 'lease_id']:
                add_data_change_audit_log(new_lease_id, user_id, username, key, None, value, action='CREATE')
        
        return new_lease_id, old_lease_data


def get_lease(lease_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
    """Get lease by ID. If user_id is provided, check for ownership."""
    with get_db_connection() as conn:
        if user_id:
            row = conn.execute(
                "SELECT * FROM leases WHERE lease_id = ? AND user_id = ?",
                (lease_id, user_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM leases WHERE lease_id = ?",
                (lease_id,)
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


def get_leases_by_user(user_id: int) -> list:
    """Get all leases for a specific user"""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leases WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_all_leases() -> list:
    """Get all leases from the database"""
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM leases ORDER BY created_at DESC").fetchall()
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
