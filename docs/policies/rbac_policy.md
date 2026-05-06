# RBAC Policy

Decision Center must enforce RBAC before retrieval and inside each connector
call. A user may only retrieve evidence for projects, mailboxes, and Odoo
records explicitly mapped to that user or role.

The canonical role model is the 9-role matrix in `docs/security/rbac_matrix.md`.
