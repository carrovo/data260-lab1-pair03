// Company-side requests, on the shared Axios instance (it adds the company
// token and handles 401). Kept thin so the slices can be tested with a fake.
import api from '../services/api'

export const companyApi = {
  getProfile: () => api.get('/companies/me').then((r) => r.data),
  saveProfile: (payload) => api.put('/companies/me', payload).then((r) => r.data),

  listJobs: () => api.get('/companies/jobs').then((r) => r.data || []),
  createJob: (payload) => api.post('/companies/jobs', payload).then((r) => r.data),

  listApplicants: (jobId) =>
    api.get(`/companies/jobs/${jobId}/applicants`).then((r) => r.data || []),
  updateApplicationStatus: (applicationId, status) =>
    api.put(`/companies/applications/${applicationId}/status`, { status }),

  listEvents: () => api.get('/companies/events').then((r) => r.data || []),
  createEvent: (payload) => api.post('/companies/events', payload).then((r) => r.data),
  listRegistrants: (eventId) =>
    api.get(`/companies/events/${eventId}/registrants`).then((r) => r.data || []),
}
