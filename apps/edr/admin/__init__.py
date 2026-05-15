"""Phase 2B admin Visual Control Plane modules.

This package collects admin-only helpers and the service catalog used by the
``/admin/*`` endpoints. The package boundary is intentional: nothing here may
import or call connectors that handle business credentials at runtime; the
catalog is metadata-only and complies with C-6 (no credential values, even
masked).
"""
