# Database Migration Guide

## Migration: Dynamic Group Sizing

### Overview
This migration updates the `roommate_groups` table to support flexible group sizes and automatic member counting.

### Changes
1. ✅ Added `current_member_count` column (auto-updated via trigger)
2. ✅ Made `target_group_size` nullable (optional limit)
3. ✅ Created trigger to auto-update member count
4. ✅ Added index for better query performance

---

## How to Apply Migration

### Option 1: via Supabase Dashboard (Recommended)

1. Go to Supabase Dashboard → SQL Editor
2. Copy contents of `001_dynamic_group_sizing.sql`
3. Paste and run the migration
4. Verify with the test queries at the bottom

### Option 2: via psql command line

```bash
# Connect to your database
psql "postgresql://user:password@host:port/database"

# Run migration
\i migrations/001_dynamic_group_sizing.sql

# Verify
SELECT id, group_name, current_member_count, target_group_size 
FROM roommate_groups 
LIMIT 5;
```

### Option 3: via Python script

```python
from app.db import get_db_connection

with open('migrations/001_dynamic_group_sizing.sql', 'r') as f:
    migration_sql = f.read()

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute(migration_sql)
conn.commit()
print("Migration applied successfully!")
```

---

## Verification

After running the migration, verify it worked:

```sql
-- 1. Check column exists and has correct values
SELECT id, group_name, current_member_count, target_group_size
FROM roommate_groups
LIMIT 10;

-- 2. Check trigger exists
SELECT tgname, tgtype, tgenabled 
FROM pg_trigger 
WHERE tgname = 'group_member_count_trigger';

-- 3. Test the trigger - add a member
INSERT INTO group_members (group_id, user_id, status)
VALUES ('<group_id>', '<user_id>', 'accepted');

-- Check count increased
SELECT current_member_count FROM roommate_groups WHERE id = '<group_id>';

-- 4. Test trigger - remove member
DELETE FROM group_members WHERE group_id = '<group_id>' AND user_id = '<user_id>';

-- Check count decreased
SELECT current_member_count FROM roommate_groups WHERE id = '<group_id>';
```

---

## Rollback

If you need to revert the changes:

```bash
psql "postgresql://..." -f migrations/001_dynamic_group_sizing_rollback.sql
```

---

## Impact Assessment

**Breaking Changes**: ❌ None
- `target_group_size` can now be NULL, but existing queries will still work
- New column `current_member_count` is auto-maintained, no code changes needed

**Performance**: ✅ Improved
- New index speeds up queries for open groups
- Trigger is lightweight (single row update)

**Data Migration**: ✅ Automatic
- Existing groups get correct `current_member_count` based on actual members
- All existing `target_group_size` values preserved

---

## Next Steps

After migration is applied:

1. ✅ Test in development environment
2. ✅ Apply to staging
3. ⏳ Monitor for 24 hours
4. ⏳ Apply to production
5. ⏳ Proceed with Phase 2: User-Group Matching Service
