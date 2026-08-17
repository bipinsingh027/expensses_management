"""Regression tests for local Site Expense Manager (no-auth, SQLite).

Covers: root/dashboard, resources (accounts, sites, categories, rules,
statements, transactions, settings), and the new /api/backup + /api/restore
round-trip and error paths.
"""
import io
import os
import zipfile
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')


# ---------- existing endpoints regression ----------
def test_root():
    r = requests.get(BASE_URL + '/api/')
    assert r.status_code == 200
    data = r.json()
    assert data.get('database') == 'SQLite'
    assert data.get('offline_ready') is True


def test_dashboard_shape():
    r = requests.get(BASE_URL + '/api/dashboard')
    assert r.status_code == 200
    data = r.json()
    for key in ('summary', 'site_totals', 'category_totals', 'account_totals', 'recent'):
        assert key in data
    assert isinstance(data['summary']['transactions'], int)


def test_resource_lists():
    for path, min_count in [('/api/accounts', 1), ('/api/sites', 1),
                            ('/api/categories', 1), ('/api/rules', 0),
                            ('/api/statements', 0), ('/api/transactions', 1)]:
        r = requests.get(BASE_URL + path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        body = r.json()
        assert isinstance(body, list)
        assert len(body) >= min_count, f"{path} count={len(body)}"


def test_settings():
    r = requests.get(BASE_URL + '/api/settings')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert 'company_name' in data


# ---------- backup + restore round-trip ----------
def _download_backup():
    r = requests.get(BASE_URL + '/api/backup')
    assert r.status_code == 200
    cd = r.headers.get('content-disposition', '')
    assert 'attachment' in cd.lower()
    assert '.zip' in cd.lower()
    return r.content


def test_backup_is_valid_zip_with_db():
    content = _download_backup()
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        names = z.namelist()
    assert 'site_expense_manager.sqlite3' in names


def test_restore_round_trip_preserves_data():
    tx_before = len(requests.get(BASE_URL + '/api/transactions').json())
    accounts_before = len(requests.get(BASE_URL + '/api/accounts').json())
    sites_before = len(requests.get(BASE_URL + '/api/sites').json())

    backup = _download_backup()
    r = requests.post(BASE_URL + '/api/restore',
                      files={'file': ('backup.zip', io.BytesIO(backup), 'application/zip')})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get('restored') is True
    assert data['transactions'] >= tx_before
    assert data['accounts'] == accounts_before
    assert data['sites'] == sites_before

    # data still returned after restore
    assert len(requests.get(BASE_URL + '/api/transactions').json()) >= tx_before
    assert len(requests.get(BASE_URL + '/api/accounts').json()) == accounts_before
    assert len(requests.get(BASE_URL + '/api/sites').json()) == sites_before


def test_restore_rejects_non_zip():
    r = requests.post(BASE_URL + '/api/restore',
                      files={'file': ('bad.txt', io.BytesIO(b'not a zip file'), 'text/plain')})
    assert r.status_code == 400
    body = r.json()
    assert 'detail' in body


def test_restore_rejects_empty_file():
    r = requests.post(BASE_URL + '/api/restore',
                      files={'file': ('empty.zip', io.BytesIO(b''), 'application/zip')})
    assert r.status_code == 400


def test_restore_rejects_zip_without_db():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('random.txt', 'hello')
    buf.seek(0)
    r = requests.post(BASE_URL + '/api/restore',
                      files={'file': ('nodb.zip', buf, 'application/zip')})
    assert r.status_code == 400
