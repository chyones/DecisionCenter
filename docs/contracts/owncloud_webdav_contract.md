# ownCloud WebDAV Contract

ownCloud is a secondary document source. It must follow the same RBAC,
revision, and evidence normalization rules as SharePoint.

## Required Metadata

- file path
- project code mapping
- modified timestamp
- revision marker when available
- content hash

ownCloud evidence must not override SharePoint unless it is demonstrably the
latest approved source.
