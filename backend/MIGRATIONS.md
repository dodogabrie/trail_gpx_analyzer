# Database Migrations Guide

This project uses **Flask-Migrate** (Alembic) for managing database schema changes.

## Setup (First Time Only)

### 1. Install Flask-Migrate

```bash
pip install flask-migrate
```

Add to `requirements.txt`:
```
flask-migrate
```

### 2. Initialize Migrations

```bash
cd backend
flask db init
```

This creates a `migrations/` directory with the Alembic configuration.

### 3. Create Initial Migration

```bash
flask db migrate -m "Initial migration"
```

This generates a migration script based on your current models.

### 4. Apply Migration

```bash
flask db upgrade
```

This runs the migration and creates all tables.

---

## Common Migration Commands

### Create a New Migration

After adding/modifying models:

```bash
flask db migrate -m "Add performance tracking tables"
```

This auto-generates a migration script by comparing your models to the current database schema.

### Apply Migrations

```bash
flask db upgrade
```

Applies all pending migrations.

### Rollback Last Migration

```bash
flask db downgrade
```

Reverts the last applied migration.

### View Migration History

```bash
flask db history
```

Shows all migrations with their revision IDs.

### View Current Revision

```bash
flask db current
```

Shows which migration is currently applied.

### Upgrade to Specific Revision

```bash
flask db upgrade <revision_id>
```

### Downgrade to Specific Revision

```bash
flask db downgrade <revision_id>
```

---

## Migration Workflow

### Adding New Tables/Columns

1. **Modify your models** (e.g., add new model or field)
   ```python
   # backend/models/new_model.py
   class NewModel(db.Model):
       id = db.Column(db.Integer, primary_key=True)
       name = db.Column(db.String(100))
   ```

2. **Import the model** in `models/__init__.py`
   ```python
   from .new_model import NewModel
   __all__.append('NewModel')
   ```

3. **Generate migration**
   ```bash
   flask db migrate -m "Add NewModel table"
   ```

4. **Review the generated migration** in `migrations/versions/`
   - Check the `upgrade()` and `downgrade()` functions
   - Verify column types, constraints, and foreign keys

5. **Apply migration**
   ```bash
   flask db upgrade
   ```

### Modifying Existing Tables

Flask-Migrate auto-detects:
- New columns
- Deleted columns
- Changed column types (sometimes)
- New indexes

**Manual edits needed for:**
- Column renames (Alembic sees this as drop + add)
- Complex data transformations
- Enum type changes

**Example: Renaming a column**

Edit the generated migration:
```python
def upgrade():
    # Auto-generated (WRONG):
    # op.drop_column('users', 'old_name')
    # op.add_column('users', sa.Column('new_name', sa.String(100)))

    # Manual fix (CORRECT):
    op.alter_column('users', 'old_name', new_column_name='new_name')

def downgrade():
    op.alter_column('users', 'new_name', new_column_name='old_name')
```

---

## Migration Structure

```
backend/
├── migrations/
│   ├── alembic.ini          # Alembic configuration
│   ├── env.py               # Migration environment
│   ├── script.py.mako       # Migration template
│   └── versions/            # Migration scripts
│       ├── 001_initial.py
│       ├── 002_add_cache.py
│       └── 003_add_performance.py
├── models/                  # SQLAlchemy models
├── manage.py                # Migration CLI wrapper
└── app.py                   # Flask app with Migrate
```

---

## Best Practices

### 1. Always Review Generated Migrations

Auto-generated migrations may miss:
- Data migrations
- Complex constraints
- Multi-step changes

### 2. Test Migrations Before Deploying

```bash
# Test upgrade
flask db upgrade

# Test downgrade
flask db downgrade

# Re-upgrade
flask db upgrade
```

### 3. Never Edit Applied Migrations

If a migration is already applied (in production):
- Create a NEW migration to fix issues
- Don't modify the old migration file

### 4. Use Descriptive Messages

```bash
# Good
flask db migrate -m "Add user_achievements table for gamification"

# Bad
flask db migrate -m "Update"
```

### 5. Backup Database Before Major Migrations

```bash
# SQLite backup
cp instance/app.db instance/app.db.backup

# PostgreSQL backup
pg_dump mydb > backup.sql
```

---

## Migrating Existing Project

If you have an existing database without migrations:

### Option 1: Start Fresh (Development Only)

```bash
# Delete database
rm instance/app.db

# Initialize migrations
flask db init

# Create initial migration
flask db migrate -m "Initial migration"

# Apply migration
flask db upgrade
```

### Option 2: Stamp Existing Database (Production)

```bash
# Initialize migrations
flask db init

# Create initial migration reflecting current state
flask db migrate -m "Initial migration from existing DB"

# DON'T apply - just stamp the database
flask db stamp head
```

This marks the database as up-to-date without running the migration.

---

## Troubleshooting

### Migration Fails: "Target database is not up to date"

```bash
flask db stamp head
```

### Migration Generates Empty Script

Your models might not have changed, or Flask-Migrate didn't detect changes.

Force create a migration:
```bash
flask db revision -m "Manual migration"
```

Then manually write the `upgrade()` and `downgrade()` functions.

### Circular Import Errors

Ensure all models are imported in `models/__init__.py` before Flask-Migrate runs.

### "Can't locate revision" Error

The `alembic_version` table is out of sync.

```bash
# Check current revision
flask db current

# If empty, stamp it
flask db stamp head
```

---

## Example: Adding Performance Tables

### Step 1: Models Already Created ✅

```python
# backend/models/performance_snapshot.py
class PerformanceSnapshot(db.Model):
    __tablename__ = 'performance_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # ... more fields
```

### Step 2: Generate Migration

```bash
cd backend
flask db migrate -m "Add performance tracking tables"
```

Output:
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.autogenerate.compare] Detected added table 'performance_snapshots'
INFO  [alembic.autogenerate.compare] Detected added table 'grade_performance_history'
INFO  [alembic.autogenerate.compare] Detected added table 'user_achievements'
  Generating /backend/migrations/versions/xxx_add_performance_tracking_tables.py ...  done
```

### Step 3: Review Migration

```bash
cat migrations/versions/xxx_add_performance_tracking_tables.py
```

### Step 4: Apply Migration

```bash
flask db upgrade
```

Output:
```
INFO  [alembic.runtime.migration] Running upgrade -> xxx, Add performance tracking tables
✓ Migration applied successfully!
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/migrations.yml
name: Database Migrations

on:
  push:
    branches: [main]

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run migrations
        run: |
          cd backend
          flask db upgrade
```

---

## Migration Checklist

Before deploying:

- [ ] Reviewed generated migration
- [ ] Tested upgrade locally
- [ ] Tested downgrade locally
- [ ] Backed up production database
- [ ] Migration is idempotent (can run multiple times safely)
- [ ] Migration includes both upgrade() and downgrade()
- [ ] Large data migrations are batched/optimized
- [ ] Deployment plan includes rollback procedure

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `flask db init` | Initialize migrations (first time) |
| `flask db migrate -m "message"` | Generate new migration |
| `flask db upgrade` | Apply all pending migrations |
| `flask db downgrade` | Rollback last migration |
| `flask db history` | Show migration history |
| `flask db current` | Show current revision |
| `flask db stamp head` | Mark DB as up-to-date |
| `flask db revision -m "msg"` | Create empty migration |

---

## Replacing Old Migration Scripts

Your old scripts:
- `migrate_cache_table.py`
- `migrate_user_calibration.py`
- `migrate_performance_tables.py`

Can now be replaced with:

```bash
# One-time: Create comprehensive migration
flask db migrate -m "Consolidated migration: cache, calibration, and performance tables"

# Apply to all environments
flask db upgrade
```

**Cleanup:**
```bash
# Archive old scripts
mkdir -p backend/legacy_migrations
mv backend/migrate_*.py backend/legacy_migrations/
```

---

## Documentation

**Official Docs:**
- Flask-Migrate: https://flask-migrate.readthedocs.io/
- Alembic: https://alembic.sqlalchemy.org/

**Tutorials:**
- https://blog.miguelgrinberg.com/post/flask-migrate-alembic-database-migration-wrapper-for-flask
