"""Server-only licensed-data gateway boundary. No model or ledger operations."""
import hmac
import os
from datetime import datetime, timezone
from fastapi import HTTPException


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class DataProviderError(Exception):
    def __init__(self, code, message, *, http_status=None, retryable=False,
                 requires_operator=False, required_tier=None, retry_after=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.requires_operator = requires_operator
        self.required_tier = required_tier
        self.retry_after = retry_after

    def diagnostic(self, checked_at=None):
        return {'code': self.code, 'message': self.message,
                'checkedAt': checked_at or utc_now(),
                'httpStatus': self.http_status, 'retryable': self.retryable,
                'requiresOperator': self.requires_operator,
                'requiredTier': self.required_tier,
                'retryAfterSeconds': self.retry_after}


def require_render_runtime():
    # This check precedes ALL licensed provider credential reads. The existing
    # Vercel Python simulation service must never receive or use these keys.
    if os.environ.get('RENDER') != 'true' or not os.environ.get('RENDER_SERVICE_ID'):
        raise DataProviderError('render_backend_required',
                                'The licensed-data gateway must run on the configured Render backend. No provider request was made.',
                                requires_operator=True)


def authorize_data_bridge(authorization):
    expected = os.environ.get('GRIDIRON_DATA_BRIDGE_TOKEN', '')
    if len(expected) < 32:
        raise HTTPException(503, 'The server-to-server data bridge is not configured.')
    actual = authorization or ''
    if not hmac.compare_digest(actual.encode('utf-8'), ('Bearer ' + expected).encode('utf-8')):
        raise HTTPException(401, 'Unauthorized data bridge request.')
