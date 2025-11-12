"""
Notification Service for Critical Date Notifications
"""

import logging
from datetime import datetime, timedelta
from lease_application.database import get_db_connection

logger = logging.getLogger(__name__)


def run_daily_date_check(db_conn=None):
    """
    Evaluates all active leases against all active notification rules and creates new
    entries in user_notifications if the trigger date matches today.

    Args:
        db_conn: Optional database connection. If None, creates a new connection.
    """
    logger.info("🔔 Starting daily date check for notifications")

    # Use provided connection or create new one
    if db_conn is None:
        with get_db_connection() as conn:
            return _run_check_with_connection(conn)
    else:
        return _run_check_with_connection(db_conn)


def _run_check_with_connection(conn):
    """Internal function to run the check with a database connection."""
    try:
        today = datetime.now().date()
        logger.info(f"📅 Checking notifications for date: {today}")

        # Get all active notification rules
        rules = conn.execute("""
            SELECT rule_id, trigger_field, days_in_advance, recipient_role, message_template
            FROM notification_settings
            WHERE is_active = 1
        """).fetchall()

        if not rules:
            logger.info("ℹ️ No active notification rules found")
            return 0

        logger.info(f"📋 Found {len(rules)} active notification rules")

        notifications_created = 0

        for rule in rules:
            rule_id = rule['rule_id']
            trigger_field = rule['trigger_field']
            days_in_advance = rule['days_in_advance']
            recipient_role = rule['recipient_role']
            message_template = rule['message_template']

            logger.debug(f"🔍 Processing rule {rule_id}: {trigger_field} - {days_in_advance} days - {recipient_role}")

            # Get all active leases with the trigger field
            leases = conn.execute(f"""
                SELECT lease_id, {trigger_field}, agreement_title, company_name
                FROM leases
                WHERE {trigger_field} IS NOT NULL
                AND status IN ('approved', 'submitted')
            """).fetchall()

            logger.debug(f"🏢 Found {len(leases)} leases with {trigger_field}")

            for lease in leases:
                lease_id = lease['lease_id']
                trigger_date_str = lease[trigger_field]
                agreement_title = lease['agreement_title'] or f"Lease #{lease_id}"
                company_name = lease['company_name'] or "Unknown Company"

                try:
                    # Parse the trigger date
                    if isinstance(trigger_date_str, str):
                        trigger_date = datetime.strptime(trigger_date_str, '%Y-%m-%d').date()
                    else:
                        # Assume it's already a date object
                        trigger_date = trigger_date_str

                    # Calculate the target notification date
                    target_date = trigger_date - timedelta(days=days_in_advance)

                    # Check if today matches the target date
                    if target_date == today:
                        logger.info(f"🎯 Match found: Lease {lease_id} ({agreement_title}) - {trigger_field} on {trigger_date} - notify {days_in_advance} days in advance")

                        # Get users with the recipient role
                        users = conn.execute("""
                            SELECT user_id, username
                            FROM users
                            WHERE role = ? AND is_active = 1
                        """, (recipient_role,)).fetchall()

                        logger.debug(f"👥 Found {len(users)} users with role '{recipient_role}'")

                        for user in users:
                            user_id = user['user_id']
                            username = user['username']

                            # Check for existing notification to prevent duplicates
                            existing = conn.execute("""
                                SELECT notification_id FROM user_notifications
                                WHERE lease_id = ? AND user_id = ? AND target_date = ? AND message LIKE ?
                                AND is_dismissed = 0
                            """, (lease_id, user_id, target_date.isoformat(), message_template[:50] + '%')).fetchone()

                            if existing:
                                logger.debug(f"⏭️ Skipping duplicate notification for user {username} on lease {lease_id}")
                                continue

                            # Create the notification message
                            message = message_template.format(
                                lease_id=lease_id,
                                agreement_title=agreement_title,
                                company_name=company_name,
                                days_in_advance=days_in_advance,
                                target_date=target_date.isoformat(),
                                trigger_date=trigger_date.isoformat()
                            )

                            # Insert the notification
                            conn.execute("""
                                INSERT INTO user_notifications (lease_id, user_id, message, target_date)
                                VALUES (?, ?, ?, ?)
                            """, (lease_id, user_id, message, target_date.isoformat()))

                            notifications_created += 1
                            logger.info(f"✅ Created notification for user {username}: {message[:100]}...")

                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Error processing lease {lease_id} for rule {rule_id}: {e}")
                    continue

        logger.info(f"🎉 Daily date check completed. Created {notifications_created} notifications.")
        return notifications_created

    except Exception as e:
        logger.error(f"❌ Error in daily date check: {e}")
        raise


def get_user_notifications(user_id, include_read=False, include_dismissed=False):
    """
    Get notifications for a specific user.

    Args:
        user_id: User ID to get notifications for
        include_read: Whether to include read notifications
        include_dismissed: Whether to include dismissed notifications

    Returns:
        List of notification dictionaries
    """
    with get_db_connection() as conn:
        query = """
            SELECT n.*, l.agreement_title, l.company_name
            FROM user_notifications n
            JOIN leases l ON n.lease_id = l.lease_id
            WHERE n.user_id = ?
        """

        conditions = []
        if not include_read:
            conditions.append("n.is_read = 0")
        if not include_dismissed:
            conditions.append("n.is_dismissed = 0")

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += " ORDER BY n.sent_at DESC"

        rows = conn.execute(query, (user_id,)).fetchall()
        return [dict(row) for row in rows]


def mark_notification_read(notification_id, user_id):
    """
    Mark a notification as read.

    Args:
        notification_id: Notification ID to mark as read
        user_id: User ID (for security check)

    Returns:
        True if successful, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            UPDATE user_notifications
            SET is_read = 1
            WHERE notification_id = ? AND user_id = ?
        """, (notification_id, user_id))
        return cursor.rowcount > 0


def dismiss_notification(notification_id, user_id):
    """
    Mark a notification as dismissed.

    Args:
        notification_id: Notification ID to dismiss
        user_id: User ID (for security check)

    Returns:
        True if successful, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            UPDATE user_notifications
            SET is_dismissed = 1
            WHERE notification_id = ? AND user_id = ?
        """, (notification_id, user_id))
        return cursor.rowcount > 0


def dismiss_all_notifications(user_id):
    """
    Mark all notifications for a user as dismissed.

    Args:
        user_id: User ID

    Returns:
        Number of notifications dismissed
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            UPDATE user_notifications
            SET is_dismissed = 1
            WHERE user_id = ? AND is_dismissed = 0
        """, (user_id,))
        return cursor.rowcount
