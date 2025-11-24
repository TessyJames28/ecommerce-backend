BSNG_ERROR_MAP = {
    # 1xxx Authentication & Authorization Errors
    "BSNG-1001": {"http": 401, "message": "Invalid or missing API token"},
    "BSNG-1002": {"http": 401, "message": "Account has been disabled"},
    "BSNG-1003": {"http": 401, "message": "Account is dormant (inactive)"},
    "BSNG-1005": {"http": 403, "message": "Account requires pre-approval before sending"},
    "BSNG-1007": {"http": 403, "message": "API access has been restricted"},

    # 2xxx Request Validation & Parameter Errors
    "BSNG-2001": {"http": 422, "message": "Required 'from' parameter is missing"},
    "BSNG-2002": {"http": 422, "message": "Required 'body' parameter is missing"},
    "BSNG-2003": {"http": 422, "message": "Required 'to' parameter is missing"},
    "BSNG-2004": {"http": 422, "message": "Invalid sender ID format"},
    "BSNG-2006": {"http": 422, "message": "Invalid phone number format"},
    "BSNG-2008": {"http": 422, "message": "Message exceeds maximum length"},
    "BSNG-2010": {"http": 422, "message": "Message contains prohibited content"},

    # 3xxx Business Logic & Resource Errors
    "BSNG-3001": {"http": 402, "message": "Insufficient wallet balance (minimum ₦1,000 required)"},
    "BSNG-3002": {"http": 422, "message": "No valid recipients found"},
    "BSNG-3003": {"http": 429, "message": "Daily sending limit exceeded"},
    "BSNG-3004": {"http": 429, "message": "Rate limit exceeded - too many requests"},
    "BSNG-3006": {"http": 503, "message": "SMS gateway unavailable or down"},
    "BSNG-3008": {"http": 403, "message": "International messaging not enabled for account"},
    "BSNG-3009": {"http": 403, "message": "Insufficient recharge history (₦200,000 minimum for international)"},

    # 5xxx System & Server Errors
    "BSNG-5001": {"http": 500, "message": "Internal server error"},
    "BSNG-5003": {"http": 503, "message": "Service temporarily unavailable"},
    "BSNG-5004": {"http": 504, "message": "Gateway timeout"},
}
