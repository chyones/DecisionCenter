# Microsoft Graph Contract

Microsoft Graph is used for SharePoint and email access through n8n.

## Rules

- Use delegated or application permissions approved by the business owner.
- Enforce Microsoft Entra identity and project RBAC before retrieval.
- Return excerpts, metadata, and source IDs only.
- Do not persist full email bodies in reports.

## Required Metadata

- drive item ID or message ID
- source path or mailbox
- timestamp
- sender and recipient metadata for email
- SHA-256 hash for body or file content reference
