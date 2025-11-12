#!/usr/bin/env python3
import sqlite3
import os

# Check notification settings
db_path = "lease_application/lease_management.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== NOTIFICATION SETTINGS ===")
    cursor.execute("SELECT * FROM notification_settings")
    settings = cursor.fetchall()
    if settings:
        for setting in settings:
            print(f"Rule ID: {setting[0]}, Field: {setting[1]}, Days: {setting[2]}, Role: {setting[3]}")
    else:
        print("No notification settings found!")

    print("\n=== USERS ===")
    cursor.execute("SELECT user_id, username, role FROM users")
    users = cursor.fetchall()
    for user in users:
        print(f"User ID: {user[0]}, Username: {user[1]}, Role: {user[2]}")

    print("\n=== LEASES WITH DATES ===")
    cursor.execute("SELECT lease_id, agreement_title, lease_end_date, termination_date FROM leases WHERE lease_end_date IS NOT NULL OR termination_date IS NOT NULL LIMIT 5")
    leases = cursor.fetchall()
    for lease in leases:
        print(f"Lease ID: {lease[0]}, Title: {lease[1]}, End: {lease[2]}, Term: {lease[3]}")

    print("\n=== USER NOTIFICATIONS ===")
    cursor.execute("SELECT COUNT(*) FROM user_notifications")
    count = cursor.fetchone()[0]
    print(f"Total notifications: {count}")

    conn.close()
else:
    print("Database not found!")
