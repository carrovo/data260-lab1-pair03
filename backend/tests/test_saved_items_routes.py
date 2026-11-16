"""Authenticated saved-item facade, using isolated SQL and Mongo test stores."""
import pytest
from datetime import datetime

from backend.app import repos
from backend.app.config import settings
from backend.app.routers import saved_items
from backend.tests.test_student_assistant import _headers, _seed_opportunities, _signup


@pytest.mark.parametrize('mode', ['sql', 'mongo'])
def test_saved_items_owned_idempotent_and_authoritative(auth_test_context, monkeypatch, mode):
    client, engine = auth_test_context
    monkeypatch.setattr(settings, 'persistence', mode)
    if mode == 'mongo':
        import mongomock
        from backend.common.mongo_store import CompanyStore, JobStore
        database = mongomock.MongoClient()['saved_test']
        monkeypatch.setattr(repos, 'get_mongo_database', lambda: database)
        monkeypatch.setattr(saved_items, 'get_mongo_database', lambda: database)
        company = CompanyStore(database).create(**{'email': 'company@example.test', 'password_hash': 'synthetic', 'name': 'Synthetic company', 'city': 'San Jose'})
        job = JobStore(database).create(company.id, **{'title': 'Synthetic job', 'description': 'Test', 'city': 'San Jose'})
        # Event fixtures use the existing production store through the repository.
        event = repos.make_repos(None).events.create(company.id, {'title': 'Synthetic event', 'description': 'Test', 'city': 'San Jose', 'starts_at': datetime(2030, 1, 1), 'ends_at': datetime(2030, 1, 2)})
        ids = {'first_job': job.id, 'event': event.id}
    else:
        ids = _seed_opportunities(engine)
    _, token = _signup(client, 'one@example.com')
    _, other = _signup(client, 'two@example.com')
    headers = _headers(token)
    assert client.get('/auth/saved-items').status_code == 401
    for kind, identifier in [('job', ids['first_job']), ('event', ids['event'])]:
        payload = {'item_type': kind, f'{kind}_id': identifier}
        for _ in range(2):
            response = client.post('/auth/saved-items', json=payload, headers=headers)
            assert response.status_code == 200, response.text
        assert sum(row['item_type'] == kind for row in response.json()) == 1
    assert len(client.get('/auth/saved-items', headers=headers).json()) == 2
    assert client.get('/auth/saved-items', headers=_headers(other)).json() == []
    assert client.delete(f"/auth/saved-items/job/{ids['first_job']}", headers=_headers(other)).status_code == 204
    assert len(client.get('/auth/saved-items', headers=headers).json()) == 2
    assert client.delete(f"/auth/saved-items/job/{ids['first_job']}", headers=headers).status_code == 204
    assert len(client.get('/auth/saved-items', headers=headers).json()) == 1
    assert client.post('/auth/saved-items', json={'item_type': 'job', 'job_id': 999999}, headers=headers).status_code == 404
    assert client.post('/auth/saved-items', json={'item_type': 'job', 'event_id': 1}, headers=headers).status_code == 422
    for invalid_id in [0, -1, True, 1.5, "1"]:
        assert client.post('/auth/saved-items', json={'item_type': 'job', 'job_id': invalid_id}, headers=headers).status_code == 422
    for suffix in ['job/0', 'event/-1', 'job/not-an-id', 'company/1']:
        assert client.delete(f'/auth/saved-items/{suffix}', headers=headers).status_code == 422
    assert client.post('/auth/saved-items', json={'item_type': 'job', 'job_id': ids['first_job'], 'student_id': 999}, headers=headers).status_code == 422
    assert client.post('/auth/saved-items', json={'item_type': 'job', 'job_id': ids['first_job']}).status_code == 401
    assert client.delete(f"/auth/saved-items/job/{ids['first_job']}").status_code == 401
    assert client.delete(f"/auth/saved-items/job/{ids['first_job']}", headers=headers).status_code == 204


def test_conversation_id_header_is_readable_by_the_development_frontend(auth_test_context):
    client, _ = auth_test_context
    from backend.app.main import app
    from backend.app.routers import assistant
    from backend.app.ai.ollama_client import FakeModelClient
    app.dependency_overrides[assistant.get_memory_store] = lambda: None
    app.dependency_overrides[assistant.get_model_client] = lambda: FakeModelClient([{'role': 'assistant', 'content': 'Synthetic reply', 'tool_calls': None}])
    _, token = _signup(client)
    response = client.post('/assistant/chat', headers={**_headers(token), 'Origin': 'http://localhost:5173'}, json={'message': 'Synthetic'})
    assert response.status_code == 200
    assert 'X-Conversation-Id' in response.headers['access-control-expose-headers']


def test_failed_persistence_is_not_reported_as_a_successful_save(auth_test_context, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    client, engine = auth_test_context
    monkeypatch.setattr(settings, 'persistence', 'sql')
    ids = _seed_opportunities(engine)
    _, token = _signup(client)
    original = saved_items.make_repos
    def failing_repositories(db):
        repositories = original(db)
        def fail(*args):
            raise IntegrityError('synthetic persistence failure', {}, Exception('synthetic'))
        repositories.saved_items.create = fail
        return repositories
    monkeypatch.setattr(saved_items, 'make_repos', failing_repositories)
    with pytest.raises(IntegrityError):
        client.post('/auth/saved-items', json={'item_type': 'job', 'job_id': ids['first_job']}, headers=_headers(token))
    assert client.get('/auth/saved-items', headers=_headers(token)).json() == []
