import re

# Read the file
with open('app/services/sync_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Replace the loop in sync_from_mysql to use batch tracking
old_loop = '''            for row in rows:
                row_key = self._get_row_key(row, "mysql")
                if not row_key:
                    continue

                current_hash = self.compute_row_hash(row)
                tracked = self.mysql.get_tracked_row(self.config_id, row_key, "mysql")

                if tracked and tracked["source_hash"] == current_hash:
                    total_skipped += 1
                    continue

                # Build sheet row (only mapped from_mysql/bidirectional columns)
                try:
                    sheet_row = self.mapping.db_row_to_sheet_row(row, "from_mysql")
                except MappingError as e:
                    errors.append(f"Row key={row_key} transform error: {e}")
                    continue

                values = [sheet_row.get(col, "") for col in sheet_cols]

                # Check if this key was previously written to a sheet row
                prev_row = self._get_sheet_row_for_key(row_key)

                if prev_row:
                    # Update in-place
                    last_col = sheet_cols[-1] if sheet_cols else "Z"
                    pending_updates.append({
                        "range": f"{self._sheet_id}!A{prev_row}:{last_col}{prev_row}",
                        "values": [values],
                    })
                    total_updated += 1
                    # Track with the row number where it currently lives
                    row_for_track = dict(row)
                    row_for_track["_sheet_row"] = prev_row
                    self.mysql.upsert_tracked_row(
                        self.config_id, row_key, current_hash,
                        json.dumps(row_for_track, ensure_ascii=False, default=str), "mysql",
                    )
                else:
                    # Append new row — store its position in new_rows list for later mapping
                    new_rows.append(values)
                    new_row_index = len(new_rows) - 1  # 0-based index within new_rows

                    total_new += 1
                    # Track with a placeholder _sheet_row; will be updated after append
                    row_for_track = dict(row)
                    row_for_track["_sheet_row"] = next_append_row + new_row_index
                    self.mysql.upsert_tracked_row(
                        self.config_id, row_key, current_hash,
                        json.dumps(row_for_track, ensure_ascii=False, default=str), "mysql",
                    )'''

new_loop = '''            # Batch fetch all tracked rows
            row_keys = []
            valid_rows = []
            
            for row in rows:
                row_key = self._get_row_key(row, "mysql")
                if row_key:
                    row_keys.append(row_key)
                    valid_rows.append((row_key, row))
            
            # Batch fetch tracked rows
            tracked_rows = self.mysql.batch_get_tracked_rows(
                self.config_id, row_keys, "mysql"
            )
            
            # Process with cached tracking data
            tracking_to_upsert = []
            
            for row_key, row in valid_rows:
                current_hash = self.compute_row_hash(row)
                tracked = tracked_rows.get(row_key)
                
                if tracked and tracked["source_hash"] == current_hash:
                    total_skipped += 1
                    continue
                
                # Build sheet row (only mapped from_mysql/bidirectional columns)
                try:
                    sheet_row = self.mapping.db_row_to_sheet_row(row, "from_mysql")
                except MappingError as e:
                    errors.append(f"Row key={row_key} transform error: {e}")
                    continue
                
                values = [sheet_row.get(col, "") for col in sheet_cols]
                
                # Check if this key was previously written to a sheet row
                prev_row = self._get_sheet_row_for_key(row_key)
                
                if prev_row:
                    # Update in-place
                    last_col = sheet_cols[-1] if sheet_cols else "Z"
                    pending_updates.append({
                        "range": f"{self._sheet_id}!A{prev_row}:{last_col}{prev_row}",
                        "values": [values],
                    })
                    total_updated += 1
                    # Track with the row number where it currently lives
                    row_for_track = dict(row)
                    row_for_track["_sheet_row"] = prev_row
                    tracking_to_upsert.append((
                        row_key, current_hash,
                        json.dumps(row_for_track, ensure_ascii=False, default=str),
                    ))
                else:
                    # Append new row — store its position in new_rows list for later mapping
                    new_rows.append(values)
                    new_row_index = len(new_rows) - 1  # 0-based index within new_rows
                    
                    total_new += 1
                    # Track with a placeholder _sheet_row; will be updated after append
                    row_for_track = dict(row)
                    row_for_track["_sheet_row"] = next_append_row + new_row_index
                    tracking_to_upsert.append((
                        row_key, current_hash,
                        json.dumps(row_for_track, ensure_ascii=False, default=str),
                    ))'''

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("Successfully replaced the loop code")
else:
    print("Pattern not found in file")
    # Debug: find where the loop starts
    idx = content.find('for row in rows:')
    if idx > 0:
        print(f"Found 'for row in rows:' at index {idx}")
        # Print surrounding context
        print("\nContext around 'for row in rows:':")
        print(repr(content[idx:idx+500]))

# Write the modified content back
with open('app/services/sync_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nFile updated successfully!")
