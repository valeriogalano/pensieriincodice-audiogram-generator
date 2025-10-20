---
apply: always
---

# Documentation Consistency (v1.2)

When making changes to the project code, database, or something else, you MUST maintain documentation synchronization.

## Database Schema Changes

When modifying database schema files (*.sql), you MUST update README.md in the SAME operation:

1. **After any table creation/deletion/modification**, immediately:
   - Search for the table name in README.md
   - Add/remove/update the corresponding entry in the "Database Structure" section
   - Update any affected relationships in the "Key Relationships" section
   - Mark the documentation update as completed before finishing the task

2. **Required for these operations**:
   - Creating new tables → Add description in README.md
   - Dropping tables → Remove description from README.md
   - Renaming tables → Update all references in README.md
   - Adding/removing columns → Update table description if significant
   - Modifying relationships → Update "Key Relationships" section

## General Documentation Updates

For non-database changes, update README.md files with any changes to:
- Features and functionality
- Installation instructions
- Usage examples
- Dependencies
- Structure definition

## Technical Documentation Synchronization

Keep technical documentation synchronized (.md files) with:
- New APIs or interfaces
- Configuration parameter changes
- Architecture modifications
- New modules or components

## Verification and Reporting

1. **Verify consistency** between code and documentation before completing the task
2. **Explicitly report** to the user which documentation files you have updated during modifications
3. **Never complete a database modification task** without updating README.md
