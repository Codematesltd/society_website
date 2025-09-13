# Society Website - AI Coding Agent Instructions

This is a **Flask-based society management system** for a cooperative/chit fund society with multi-role user access (members, staff, admin/manager) and Supabase as the backend database.

## Architecture Overview

### Core Structure
- **Flask app factory pattern**: Main app created via `app/__init__.py:create_app()`, extended in root `app.py`
- **Blueprint-based modularization**: Each role/feature has its own blueprint with URL prefixes
- **Dual registration pattern**: Blueprints registered in both `app/__init__.py` and root `app.py` for flexibility
- **Supabase integration**: PostgreSQL database accessed via Supabase client throughout

### Key Blueprints & URL Structure
```
/auth/*          - Authentication (login, password reset, role detection)
/loan/*          - Finance/loan operations (blueprint: finance_bp)
/staff/*         - Staff dashboard and member management  
/admin/*         - Admin dashboard, approvals, audit reports
/manager/*       - Manager login and staff management
/members/*       - Member dashboard and account operations
```

### Database Architecture
- **Multi-tenant role system**: `members`, `staff`, `manager` tables with shared email-based authentication
- **Financial core**: `loans`, `loan_records`, `transactions`, `expenses` tables for complete audit trail
- **Key columns to note**: `members.share_amount`, `loan_records.interest_amount` for calculations

## Development Patterns

### Authentication & Authorization
- **Session-based auth** with JWT tokens for API validation
- **Role detection**: `find_role(email)` checks across all user tables
- **Decorators**: Use `@login_required` and `@role_required('staff', 'admin')` for access control
- **Password security**: Enforced complexity with bcrypt hashing

### Supabase Integration
```python
# Standard pattern across the codebase
from supabase import create_client
SUPABASE_URL = os.environ.get("SUPABASE_URL")  
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Query pattern with error handling
resp = supabase.table('members').select('*').eq('email', email).execute()
data = resp.data if hasattr(resp, 'data') and resp.data else []
```

### Financial Calculations
- **Total amounts**: Include `balance + share_amount + interest_amount` (see `/admin/api/total-amount-summary`)
- **EMI calculations**: Monthly reducing balance method in `app/admin/api.py:loan_info()`
- **Audit trails**: All transactions logged with date, amount, type, and reference IDs

### File Upload & Processing
- **Compression**: Images auto-compressed to <100KB using PIL
- **Storage**: Supabase storage buckets for photos/signatures
- **PDF generation**: Uses `xhtml2pdf` and `pdfkit` for certificates and statements

## Critical Workflows

### Development Environment
```bash
# Setup (Windows PowerShell)
pip install -r requirements.txt
# Set environment variables in .env file
flask create-manager <username> <email> <password>  # Create admin
python app.py  # Run development server
```

### Adding New Financial Features
1. **API endpoint**: Add to appropriate blueprint (e.g., `app/admin/api.py`)
2. **Database queries**: Use error-safe Supabase patterns with `hasattr(resp, 'data')`
3. **Excel exports**: Follow pattern in audit endpoints using pandas + BytesIO
4. **Frontend integration**: Update dashboard templates and include CSRF handling

### Blueprint Extension Pattern
```python
# In blueprint __init__.py
finance_bp = Blueprint("finance", __name__, url_prefix="/loan")

# In root app.py - add proxy routes for URL compatibility
@app.route('/finance/api/apply', methods=['POST'])
def _proxy_apply():
    return apply_loan()  # Delegate to blueprint function
```

## Key Files for AI Context

- **`app/config.py`**: Environment variables and Flask configuration
- **`app/auth/routes.py`**: Complete authentication system with role detection
- **`app/admin/api.py`**: Financial calculations, audit endpoints, Excel exports
- **`app/finance/api.py`**: Loan processing, EMI calculations, certificate generation
- **`requirements.txt`**: Full dependency list including Supabase, pandas, pdfkit

## Common Gotchas

- **Dual blueprint registration**: Routes may exist in both blueprint and root app - check both locations
- **Role precedence**: Manager role checked first in `find_role()` to avoid staff misclassification
- **Session timeouts**: Managers have 20-minute sessions, others have 1-hour sessions
- **Supabase response**: Always check `hasattr(resp, 'data')` before accessing `resp.data`
- **Excel exports**: Use `make_response()` with proper MIME types and headers

## Testing & Debugging

- **Check routes**: Use `flask routes` to see all registered endpoints
- **Database inspection**: Direct SQL queries via Supabase dashboard for data verification
- **Log patterns**: Blueprint imports show success/failure messages on startup
- **Error handling**: Most endpoints return JSON with `{status: 'error', message: '...'}` format