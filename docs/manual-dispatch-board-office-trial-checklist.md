# Manual Dispatch Board Office Trial Checklist

Use this short checklist during office trial days.

## Start of Day

1. Open PowerShell in the project folder.
2. Start the system:

   ```powershell
   .\tools\start_office_trial.ps1
   ```

3. Open:

   ```text
   http://127.0.0.1:8130/frontend/
   ```

4. Log in.
5. Confirm the Dispatch Date.
6. Confirm Task Pool loads.
7. Confirm Drivers and Vehicles are available.

## During Dispatch

1. Add Orders.
2. Check Delivery Date and Product Details.
3. Assign Orders to Drivers and Trips.
4. Select Vehicles.
5. Generate Final Trip Summary.
6. Save and Export.
7. Check the downloaded Excel file.
8. Load History if you need to review saved summaries.

## End of Day

1. Backup the database:

   ```powershell
   .\tools\backup_sqlite_db.ps1
   ```

2. Confirm a new timestamped backup exists in `backups/`.
3. Do not delete `data/manual_dispatch.sqlite3`.
4. Stop the backend with `Ctrl+C` if the system is no longer needed.

## Important Reminders

- The board is manual dispatch only.
- It does not auto-assign Drivers or Vehicles.
- It does not calculate ETA.
- It does not use Google Maps or route optimization.
- Backups are local files. Keep them safe during the trial.
