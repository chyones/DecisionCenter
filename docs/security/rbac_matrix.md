# RBAC Matrix

Authoritative role rules are defined in Sections 8 and 9 of the workflow spec.

| Role | Documents | Email | Odoo | Publish |
|---|---|---|---|---|
| Executive Sponsor | Authorized projects | Authorized shared mailboxes | Authorized project facts | Approve final reports |
| Senior Manager | Authorized projects | Own mailbox and mapped shared mailboxes | Authorized project facts | Request approval |
| Finance Manager | Finance documents | Finance shared mailboxes | Financial facts | Review finance claims |
| Project Manager | Assigned project documents | Assigned project mailboxes | Operational facts | Review project claims |
| Viewer | Explicitly granted documents | None by default | None by default | None |

Access must be enforced at Node 1 and again at every retrieval node.
