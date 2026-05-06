#!/usr/bin/env python3
"""
Fix duplicate method definitions in mysql_service.py.
Removes the first definition of batch_get_tracked_rows and batch_upsert_tracked_rows.
"""

with open('app/services/mysql_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all method definition line numbers
batch_get_lines = []
batch_upsert_lines = []

for i, line in enumerate(lines):
    if '    def batch_get_tracked_rows(' in line:
        batch_get_lines.append(i)
    if '    def batch_upsert_tracked_rows(' in line:
        batch_upsert_lines.append(i)

print(f"Found batch_get_tracked_rows at lines: {[x+1 for x in batch_get_lines]}")
print(f"Found batch_upsert_tracked_rows at lines: {[x+1 for x in batch_upsert_lines]}")

# We want to remove the FIRST definition of each method
# The first batch_get_tracked_rows is at batch_get_lines[0]
# The first batch_upsert_tracked_rows is at batch_upsert_lines[0]

# Find the end of first batch_get_tracked_rows
# It ends at the line before the second definition starts
get_end1 = batch_get_lines[1]  # End is exclusive

# Find the end of first batch_upsert_tracked_rows
# It ends at the line before the second definition starts
upsert_end1 = batch_upsert_lines[1]  # End is exclusive

print(f"Removing lines {batch_get_lines[0]+1}-{get_end1} (first batch_get_tracked_rows)")
print(f"Removing lines {batch_upsert_lines[0]+1}-{upsert_end1} (first batch_upsert_tracked_rows)")

# Remove the first duplicate methods
# Need to remove in reverse order to preserve line numbers
lines_to_remove = list(range(batch_upsert_lines[0], upsert_end1)) + list(range(batch_get_lines[0], get_end1))
lines_to_remove.sort(reverse=True)

for line_num in lines_to_remove:
    del lines[line_num]

print(f"Removed {len(lines_to_remove)} lines")

# Write back
with open('app/services/mysql_service.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done! Duplicate methods removed.")
