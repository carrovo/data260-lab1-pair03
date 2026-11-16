"""Offline budgets and canonical coverage, not measured/live token evidence."""
import json

import pytest

from backend.app.ai.compaction import (
    CompactionError, MAX_QUOTES_PER_GROUP, SUMMARY_OUTPUT_TOKENS, _expand_selection,
    _excerpts, canonical_source, compact, prepare_compaction, requirements,
)
from backend.app.ai.memory import MemoryModelClient, get_memory_store
from backend.app.ai.ollama_client import ModelClient, OllamaClient
from backend.app.ai.usage import UsageRecorder
from backend.common.assistant_memory import MemoryStore
from backend.harness.fixtures import HarnessContext
import mongomock


class NoInference(ModelClient):
    context_capacity = 4096

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        raise AssertionError('Offline preflight must not invoke a model')


def repetitive_history():
    # 32 public turns with repeated equivalents/procedural scaffolding, including
    # concrete opportunity facts, an uncertainty and an explicit negation.
    messages = []
    for i in range(16):
        city = 'My preferred city is San Jose.' if i % 2 else 'San Jose is my preferred city.'
        submission = 'No application has been submitted.' if i % 2 else 'I have not submitted an application.'
        messages.extend([
            {'role': 'user', 'content': (
                'Synthetic planning notes: ' + city + ' ' + submission + ' '
                'My application status is unknown. My next step is to check eligibility with tools. '
                'Job #7 belongs to company #3. Event #9 eligibility is unknown. '
                'I will review the posting requirements. Please acknowledge these notes only.'
            )},
            {'role': 'assistant', 'content': 'Understood. I will help you review the requirements.'},
        ])
    return messages


def test_32_message_repetition_is_bounded_without_losing_essential_facts():
    messages = repetitive_history()
    client = NoInference()
    plan = prepare_compaction(messages, client)
    required = requirements(messages)
    visible = json.dumps(required)
    assert len(messages) == 32 and len(plan['quotes']) < 16
    for fact in ['San Jose', 'unknown', 'eligibility with tools', 'Job #7', 'company #3', 'Event #9']:
        assert fact.casefold() in visible.casefold()
    assert 'No application has been submitted.' in visible
    assert 'I have not submitted an application.' not in visible  # Same fact, latest exact wording.
    assert 'I will review the posting requirements.' not in visible
    assert 'I will help you review' not in visible
    assert client.calls == 0
    assert plan['budget']['source'].startswith('estimated_')
    assert plan['budget']['estimated_input_tokens'] + plan['budget']['reserved_output_tokens'] <= 4096
    assert 0 < plan['budget']['reserved_output_tokens'] <= SUMMARY_OUTPUT_TOKENS
    source = json.loads(plan['messages'][-1]['content'].split('\n', 1)[1].rsplit('\n', 1)[0])
    assert set(source) == {'quotes', 'required_ids'}
    assert len(source['quotes']) == len(set(source['quotes']))


def test_every_canonical_quote_has_actual_source_provenance_and_consistent_schema():
    messages = repetitive_history()
    plan = prepare_compaction(messages, NoInference())
    for record in plan['quotes']:
        ref = record['source']
        excerpt = _excerpts(messages[ref['message_index']]['content'])[ref['excerpt_index']]
        assert excerpt[ref['start']:ref['end']] == record['quote']
        assert ref['message_index'] in record['equivalent_message_indices']
    for key, ids in plan['groups'].items():
        schema = plan['schema']['properties'][key]
        assert schema['minItems'] == schema['maxItems'] == len(ids) <= MAX_QUOTES_PER_GROUP
        if ids:
            assert schema['items']['enum'] == ids
    assert len(_expand_selection(json.dumps(plan['groups']), plan, messages)) == 3


def test_distinct_preferences_corrections_negations_and_identifiers_are_not_coalesced():
    facts = [
        'My preferred city is San Jose.', 'My preferred city is Oakland.',
        'My preferred city is San Jose.', 'I will not work remotely.',
        'I will work remotely.', 'I want to work full time.', 'I will help you compare company Acme.', 'Application #4 was not approved.',
        'Application #4 is now approved.', 'I have a forklift certification.',
        'Job #7 salary is unknown.', 'Job #8 salary is $30.',
    ]
    messages = [{'role': 'user', 'content': f} for f in facts]
    plan = canonical_source(messages)
    observed = [r['quote'] for r in plan['quotes']]
    assert observed.index(facts[1]) < observed.index(facts[2])
    assert all(f in observed for f in facts[3:])
    assert len(observed) == len(facts) - 1
    # Numeric signs are source facts, not list bullets to trim.
    assert canonical_source([{'role':'user','content':'-5 is the measured balance.'}])['quotes'][0]['quote'].startswith('-5')


@pytest.mark.parametrize('capacity', [None, 128])
def test_missing_or_small_context_capacity_fails_without_a_model_call(capacity):
    client = NoInference()
    client.context_capacity = capacity
    with pytest.raises(CompactionError, match='capacity_unavailable|context_budget_exceeded'):
        compact(repetitive_history(), client, UsageRecorder())
    assert client.calls == 0


def test_more_than_40_distinct_other_facts_are_rejected_not_silently_truncated():
    messages = [{'role':'user', 'content':f'Certificate number {i} is active.'} for i in range(45)]
    client = NoInference()
    assert len(canonical_source(messages)['quotes']) == 45
    with pytest.raises(CompactionError, match='essential_source_exceeds_summary_limits'):
        compact(messages, client, UsageRecorder())
    assert client.calls == 0


def test_infeasible_long_fact_keeps_history_and_version_without_inference():
    store = MemoryStore(mongomock.MongoClient(tz_aware=True).budget)
    store.initialize()
    client = NoInference()
    with HarnessContext(client) as context:
        context.app.dependency_overrides[get_memory_store] = lambda: store
        document = store.start(context.ids['student'])
        messages = [
            {'role':'user','content':'My preferred role is ' + 'important ' * 650},
            {'role':'assistant','content':'Noted.'},
            {'role':'user','content':'Please recall that role.'},
        ]
        store.save_conversation(document, messages)
        before = store.conversation(context.ids['student'], document['_id'])
        response = context.chat({'message':'/compact','conversation_id':document['_id']},trace_id='budget-impossible')
        assert response.status_code == 200
        assert response.json()['compaction']['status'] == 'failed'
        assert response.json()['compaction']['error'] == 'summary_too_large'
        assert response.json()['usage']['model_calls'] == 0
        assert store.conversation(context.ids['student'], document['_id']) == before
        assert client.calls == 0


@pytest.mark.parametrize('mutation', ['missing','duplicate','reordered','wrong_type'])
def test_reference_selection_cannot_omit_reorder_duplicate_or_invent_facts(mutation):
    messages = repetitive_history()
    plan = prepare_compaction(messages, NoInference())
    selected = json.loads(json.dumps(plan['groups']))
    key = next(k for k, ids in selected.items() if len(ids) > 1)
    if mutation == 'missing': selected[key].pop()
    if mutation == 'duplicate': selected[key][-1] = selected[key][0]
    if mutation == 'reordered': selected[key].reverse()
    if mutation == 'wrong_type': selected[key][0] = True  # JSON boolean is not an ID.
    with pytest.raises(CompactionError, match='required_references|invalid_summary_references'):
        _expand_selection(json.dumps(selected), plan, messages)


def test_memory_injection_is_included_in_the_estimated_budget_without_live_services():
    client = OllamaClient()
    plain = prepare_compaction(repetitive_history(), client)
    wrapped = MemoryModelClient(client, [])
    planned = prepare_compaction(repetitive_history(), wrapped)
    assert planned['budget']['context_capacity'] == client.num_ctx
    assert planned['budget']['estimated_input_tokens'] > plain['budget']['estimated_input_tokens']
    assert wrapped.prepare_messages(planned['messages'])[0]['content'].endswith(wrapped.data)


def test_existing_configured_output_cap_is_not_silently_raised():
    client = OllamaClient()
    client.num_predict = 16
    with pytest.raises(CompactionError, match='configured_output_budget_insufficient'):
        prepare_compaction(repetitive_history(), MemoryModelClient(client, []))
    assert client.num_predict == 16


def test_stored_catalog_keeps_corrections_in_global_order_across_categories():
    from backend.app.ai.compaction import validate_summary
    messages = [
        {'role':'user','content':'My work mode is remote.'},
        {'role':'user','content':'I will not work remotely.'},
        {'role':'user','content':'Please recall my work preference.'},
        {'role':'assistant','content':'Noted.'},
    ]
    candidate = validate_summary(json.dumps(requirements(messages)), messages)
    facts = _excerpts(candidate[0]['content'])
    assert facts.index(messages[0]['content']) < facts.index(messages[1]['content'])
    # Recompaction reads that same global order, never alphabetical group order.
    planned = canonical_source(candidate)
    again = [record['quote'] for record in planned['quotes']]
    assert again.index(messages[0]['content']) < again.index(messages[1]['content'])


def test_unknown_case_sensitive_identifiers_are_not_treated_as_equivalent_notes():
    messages = [
        {'role':'user','content':'My certificate code is AbC.'},
        {'role':'user','content':'My certificate code is abc.'},
    ]
    assert [r['quote'] for r in canonical_source(messages)['quotes']] == [m['content'] for m in messages]


def test_unresolved_eligibility_action_is_retained_without_a_next_step_label():
    messages = [
        {'role':'user','content':'I will check eligibility with tools.'},
        {'role':'user','content':'Continue.'},
        {'role':'assistant','content':'Noted.'},
    ]
    assert messages[0]['content'] in [r['quote'] for r in canonical_source(messages)['quotes']]
