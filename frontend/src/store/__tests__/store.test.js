import test from 'node:test'
import assert from 'node:assert/strict'
import { createAppStore } from '../createStore.js'
import { toSerializableError, normalizeIds } from '../errors.js'
import { searchJobs, loadJob, createMyJob, selectJobList, selectJobDetail, selectMyJobs } from '../jobsSlice.js'
import { submitJobApplication, loadMyApplications, updateApplicantStatus, loadApplicants, selectApplicationForJob, selectApplicants } from '../applicationsSlice.js'
import { registerForEvent, loadMyRegistrations, selectIsRegistered, selectRegisterState, searchEvents } from '../eventsSlice.js'
import { loadCompanyProfile, saveCompanyProfile, selectCompanyProfile } from '../companiesSlice.js'

function httpError(status, message, detail) {
  const e = new Error(message)
  e.status = status
  if (detail !== undefined) e.response = { status, data: { detail } }
  return e
}

function makeStore(student = {}, company = {}) {
  return createAppStore({ student, company })
}

test('toSerializableError keeps message, status and detail as plain data', () => {
  const out = toSerializableError(httpError(409, 'conflict', 'Already applied'))
  assert.deepEqual(out, { message: 'conflict', status: 409, response: { data: { detail: 'Already applied' } } })
  assert.deepEqual(JSON.parse(JSON.stringify(out)), out)
})

test('toSerializableError handles validation arrays and unknown errors', () => {
  const out = toSerializableError({ response: { status: 422, data: { detail: [{ msg: 'bad', loc: ['x'] }] } } })
  assert.equal(out.status, 422)
  assert.deepEqual(out.response.data.detail, [{ msg: 'bad' }])
  assert.equal(toSerializableError(undefined).status, null)
})

test('normalizeIds stringifies id fields only', () => {
  const out = normalizeIds([{ id: 1, job_id: 2, salary: 5, company: { id: 3 } }])
  assert.deepEqual(out, [{ id: '1', job_id: '2', salary: 5, company: { id: '3' } }])
})

test('searchJobs stores results and passes the query through', async () => {
  let seen
  const store = makeStore({ fetchJobs: async (q) => { seen = q; return [{ id: 7, title: 'A' }] } })
  await store.dispatch(searchJobs({ keyword: 'ml', city: 'Fremont' }))
  assert.deepEqual(seen, { keyword: 'ml', city: 'Fremont' })
  const list = selectJobList(store.getState())
  assert.equal(list.status, 'succeeded')
  assert.equal(list.items[0].id, '7')
})

test('searchJobs failure stores a serializable error', async () => {
  const store = makeStore({ fetchJobs: async () => { throw httpError(500, 'boom') } })
  await store.dispatch(searchJobs({}))
  const list = selectJobList(store.getState())
  assert.equal(list.status, 'failed')
  assert.equal(list.error.status, 500)
})

test('loadJob marks 404 as notFound without an error', async () => {
  const store = makeStore({ fetchJob: async () => { throw httpError(404, 'nope') } })
  await store.dispatch(loadJob('x'))
  const d = selectJobDetail(store.getState())
  assert.equal(d.notFound, true)
  assert.equal(d.error, null)
})

test('createMyJob refreshes the company job list', async () => {
  const jobs = [{ id: 1 }]
  const store = makeStore({}, {
    createJob: async (p) => { jobs.push({ id: 2, ...p }); return { id: 2 } },
    listJobs: async () => jobs,
  })
  await store.dispatch(createMyJob({ title: 'T' }))
  assert.equal(selectMyJobs(store.getState()).items.length, 2)
})

test('submitJobApplication adds to my applications; 409 is kept as an error', async () => {
  const student = {
    submitApplication: async () => ({ id: 9, job_id: 4, status: 'submitted' }),
  }
  const store = makeStore(student)
  await store.dispatch(submitJobApplication({ jobId: 4, resumeFile: null, token: 't' }))
  assert.equal(selectApplicationForJob(store.getState(), 4).id, '9')

  const store2 = makeStore({ submitApplication: async () => { throw httpError(409, 'dup') } })
  const res = await store2.dispatch(submitJobApplication({ jobId: 4, resumeFile: null, token: 't' }))
  assert.equal(res.meta.requestStatus, 'rejected')
  assert.equal(res.payload.status, 409)
})

test('loadMyApplications passes token and status filter', async () => {
  let args
  const store = makeStore({ fetchMyApplications: async (...a) => { args = a; return [] } })
  await store.dispatch(loadMyApplications({ token: 'tok', status: 'accepted' }))
  assert.deepEqual(args, ['tok', 'accepted'])
})

test('updateApplicantStatus calls the API then reloads applicants', async () => {
  const calls = []
  const store = makeStore({}, {
    updateApplicationStatus: async (id, s) => { calls.push(['put', id, s]) },
    listApplicants: async (jobId) => { calls.push(['get', jobId]); return [{ id: 1, status: 'accepted' }] },
  })
  await store.dispatch(updateApplicantStatus({ applicationId: 1, status: 'accepted', jobId: 5 }))
  assert.deepEqual(calls, [['put', 1, 'accepted'], ['get', 5]])
  assert.equal(selectApplicants(store.getState()).items[0].status, 'accepted')
})

test('loadApplicants records which job the list belongs to', async () => {
  const store = makeStore({}, { listApplicants: async () => [] })
  await store.dispatch(loadApplicants(12))
  assert.equal(selectApplicants(store.getState()).jobId, '12')
})

test('registerForEvent reloads registrations and selectIsRegistered works', async () => {
  const regs = []
  const store = makeStore({
    registerForEvent: async (eventId) => { regs.push({ id: 1, event_id: eventId }); return { ok: true } },
    fetchMyRegistrations: async () => regs,
  })
  await store.dispatch(registerForEvent({ eventId: 3, token: 't' }))
  assert.equal(selectRegisterState(store.getState()).status, 'succeeded')
  assert.equal(selectIsRegistered(store.getState(), '3'), true)
  assert.equal(selectIsRegistered(store.getState(), '4'), false)
})

test('registerForEvent duplicate registration surfaces the status', async () => {
  const store = makeStore({ registerForEvent: async () => { throw httpError(409, 'dup') } })
  await store.dispatch(registerForEvent({ eventId: 3, token: 't' }))
  assert.equal(selectRegisterState(store.getState()).error.status, 409)
})

test('searchEvents and loadMyRegistrations store lists', async () => {
  const store = makeStore({
    fetchEvents: async () => [{ id: 1 }],
    fetchMyRegistrations: async () => [{ id: 2, event_id: 1 }],
  })
  await store.dispatch(searchEvents('x'))
  await store.dispatch(loadMyRegistrations('t'))
  assert.equal(store.getState().events.list.items.length, 1)
  assert.equal(store.getState().events.registrations.items.length, 1)
})

test('company profile load and save', async () => {
  const store = makeStore({}, {
    getProfile: async () => ({ id: 1, name: 'Acme' }),
    saveProfile: async (p) => ({ id: 1, ...p }),
  })
  await store.dispatch(loadCompanyProfile())
  assert.equal(selectCompanyProfile(store.getState()).data.name, 'Acme')
  await store.dispatch(saveCompanyProfile({ name: 'New' }))
  assert.equal(selectCompanyProfile(store.getState()).data.name, 'New')
})

test('state stays serializable after failures', async () => {
  const store = makeStore({ fetchJobs: async () => { throw httpError(401, 'auth', 'Not authenticated') } })
  await store.dispatch(searchJobs({}))
  assert.doesNotThrow(() => JSON.stringify(store.getState()))
})
