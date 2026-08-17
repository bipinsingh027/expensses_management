import io
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')

# Authentication, dashboard, protected resources, and statement import regression coverage.
def test_admin_login_cookie_and_me():
    s = requests.Session()
    r = s.post(BASE_URL + '/api/auth/login', json={'email': 'admin@siteexpense.local', 'password': 'admin123'})
    assert r.status_code == 200, r.text
    assert 'access_token' in s.cookies
    assert 'HttpOnly' in r.headers.get('set-cookie', '')
    me = s.get(BASE_URL + '/api/auth/me')
    assert me.status_code == 200 and me.json()['role'] == 'admin'

def test_employee_login_and_permissions():
    s = requests.Session()
    r = s.post(BASE_URL + '/api/auth/login', json={'email': 'rohan@siteexpense.local', 'password': 'employee123'})
    assert r.status_code == 200, r.text
    assert r.json()['role'] == 'employee'
    assert s.get(BASE_URL + '/api/dashboard').status_code == 200
    assert s.get(BASE_URL + '/api/users').status_code == 403

def test_protected_dashboard_and_resources_have_data():
    s = requests.Session(); s.post(BASE_URL + '/api/auth/login', json={'email': 'admin@siteexpense.local', 'password': 'admin123'})
    assert s.get(BASE_URL + '/api/dashboard').json()['summary']['transactions'] >= 1
    assert len(s.get(BASE_URL + '/api/sites').json()) >= 1
    assert len(s.get(BASE_URL + '/api/categories').json()) >= 1
    assert len(s.get(BASE_URL + '/api/transactions').json()) >= 1

def test_csv_upload_import():
    s = requests.Session(); s.post(BASE_URL + '/api/auth/login', json={'email': 'admin@siteexpense.local', 'password': 'admin123'})
    users = s.get(BASE_URL + '/api/users').json(); employee = next(u for u in users if u['role'] == 'employee')
    csv = b'date,amount,description\n2026-02-01,123.45,TEST upload fuel\n'
    r = s.post(BASE_URL + '/api/statements/upload', data={'employee_id': employee['id'], 'statement_month': 'February', 'statement_year': '2026'}, files={'file': ('TEST_upload.csv', io.BytesIO(csv), 'text/csv')})
    assert r.status_code == 200, r.text
    assert r.json()['imported'] == 1