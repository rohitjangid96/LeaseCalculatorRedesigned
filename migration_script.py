import sqlite3

def migrate_email_settings():
    try:
        # Connect to the source database
        source_conn = sqlite3.connect('../Lease/lease_management.db')
        source_conn.row_factory = sqlite3.Row
        source_cursor = source_conn.cursor()

        # Fetch the email settings
        source_cursor.execute("SELECT * FROM email_settings WHERE is_active = 1 ORDER BY setting_id DESC LIMIT 1")
        email_settings = source_cursor.fetchone()

        if not email_settings:
            print("No active email settings found in the source database.")
            return

        # Connect to the destination database
        dest_conn = sqlite3.connect('lease_management.db')
        dest_cursor = dest_conn.cursor()

        # Prepare the data for insertion
        config_data = {
            "SMTP_HOST": email_settings["smtp_host"],
            "SMTP_PORT": email_settings["smtp_port"],
            "SMTP_USERNAME": email_settings["smtp_username"],
            "SMTP_PASSWORD": email_settings["smtp_password"],
            "SMTP_FROM": email_settings["from_email"],
        }

        # Insert or update the data in the app_config table
        for key, value in config_data.items():
            dest_cursor.execute("INSERT INTO app_config(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

        dest_conn.commit()
        print("Email settings migrated successfully.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if 'source_conn' in locals() and source_conn:
            source_conn.close()
        if 'dest_conn' in locals() and dest_conn:
            dest_conn.close()

if __name__ == '__main__':
    migrate_email_settings()
