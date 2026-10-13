import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function Events() {
  const [events, setEvents] = useState([]);
  const [registrants, setRegistrants] = useState({});
  const [expandedEvent, setExpandedEvent] = useState(null);

  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState(null);

  const [form, setForm] = useState({
    name: "",
    description: "",
    date: "",
    time: "",
    city: "San Jose",
    location: "",
    eligibility: "",
  });

  const loadEvents = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get("/companies/events");
      setEvents(response.data || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      setPosting(true);
      setError(null);

      const dateTime = form.date
        ? new Date(`${form.date}T00:00:00`).toISOString()
        : null;

      await api.post("/companies/events", {
        ...form,
        date: dateTime,
      });

      setForm({
        name: "",
        description: "",
        date: "",
        time: "",
        city: "San Jose",
        location: "",
        eligibility: "",
      });

      await loadEvents();
    } catch (err) {
      setError(err);
    } finally {
      setPosting(false);
    }
  };

  const loadRegistrants = async (eventId) => {
    if (expandedEvent === eventId) {
      setExpandedEvent(null);
      return;
    }

    try {
      setError(null);

      const response = await api.get(
        `/companies/events/${eventId}/registrants`
      );

      setRegistrants((prev) => ({
        ...prev,
        [eventId]: response.data || [],
      }));

      setExpandedEvent(eventId);
    } catch (err) {
      setError(err);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <Loading label="Loading events..." />
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">RECRUITING EVENTS</p>

          <h1>Events</h1>

          <p>
            Create recruiting events, connect with students, and manage
            registrations from one place.
          </p>
        </div>

        <div className="event-summary-chip">
          <span>{events.length}</span>
          {events.length === 1 ? "Event" : "Events"}
        </div>
      </div>

      <ErrorMessage error={error} />

      <div className="events-layout">
        {/* CREATE EVENT */}
        <section className="dashboard-card event-create-card">
          <div className="card-heading">
            <div className="card-heading-icon">＋</div>

            <div>
              <h2>Create an event</h2>
              <p>Publish a recruiting event for students.</p>
            </div>
          </div>

          <form className="event-form" onSubmit={handleSubmit}>
            <label>
              Event name
              <input
                name="name"
                value={form.name}
                onChange={handleChange}
                placeholder="e.g. Data & Analytics Career Night"
                required
              />
            </label>

            <label>
              Description
              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="Tell students what they can expect..."
                rows="4"
              />
            </label>

            <div className="form-two-column">
              <label>
                Date
                <input
                  type="date"
                  name="date"
                  value={form.date}
                  onChange={handleChange}
                  required
                />
              </label>

              <label>
                Time
                <input
                  name="time"
                  value={form.time}
                  onChange={handleChange}
                  placeholder="5:00 PM"
                />
              </label>
            </div>

            <div className="form-two-column">
              <label>
                City
                <select
                  name="city"
                  value={form.city}
                  onChange={handleChange}
                  required
                >
                  <option value="San Jose">San Jose</option>
                  <option value="Santa Clara">Santa Clara</option>
                  <option value="Fremont">Fremont</option>
                </select>
              </label>

              <label>
                Location
                <input
                  name="location"
                  value={form.location}
                  onChange={handleChange}
                  placeholder="San Jose State University"
                />
              </label>
            </div>

            <label>
              Eligibility
              <input
                name="eligibility"
                value={form.eligibility}
                onChange={handleChange}
                placeholder="Open to students interested in analytics..."
              />
            </label>

            <button
              type="submit"
              className="primary-action-button event-submit"
              disabled={posting}
            >
              {posting ? "Publishing..." : "Publish event"}
            </button>
          </form>
        </section>

        {/* EVENT LIST */}
        <section className="events-list-section">
          <div className="section-title-row">
            <div>
              <h2>Your events</h2>
              <p>Manage events created by your company.</p>
            </div>
          </div>

          {events.length === 0 ? (
            <div className="dashboard-card empty-state events-empty">
              <div className="empty-state-inner">
                <div className="empty-state-icon">◇</div>

                <h2>No events posted yet</h2>

                <p>
                  Create your first recruiting event to start connecting
                  with students.
                </p>
              </div>
            </div>
          ) : (
            <div className="event-card-grid">
              {events.map((event) => {
                const eventRegistrants = registrants[event.id] || [];

                return (
                  <article
                    className="dashboard-card recruiter-event-card"
                    key={event.id}
                  >
                    <div className="event-card-top">
                      <div className="event-date-badge">
                        <span>
                          {event.date
                            ? new Date(event.date)
                                .toLocaleString("en-US", {
                                  month: "short",
                                })
                                .toUpperCase()
                            : "—"}
                        </span>

                        <strong>
                          {event.date
                            ? new Date(event.date).getDate()
                            : "—"}
                        </strong>
                      </div>

                      <div className="event-card-title">
                        <h3>{event.name}</h3>

                        <span className="event-status-badge">
                          Upcoming
                        </span>
                      </div>
                    </div>

                    {event.description && (
                      <p className="event-description">
                        {event.description}
                      </p>
                    )}

                    <div className="event-meta-grid">
                      <div>
                        <span className="event-meta-label">Date</span>
                        <strong>
                          {event.date
                            ? new Date(event.date).toLocaleDateString()
                            : "Not specified"}
                        </strong>
                      </div>

                      <div>
                        <span className="event-meta-label">Time</span>
                        <strong>{event.time || "Not specified"}</strong>
                      </div>

                      <div>
                        <span className="event-meta-label">City</span>
                        <strong>{event.city || "Not specified"}</strong>
                      </div>

                      <div>
                        <span className="event-meta-label">Location</span>
                        <strong>
                          {event.location || "Not specified"}
                        </strong>
                      </div>
                    </div>

                    {event.eligibility && (
                      <div className="event-eligibility">
                        <span>Eligibility</span>
                        <p>{event.eligibility}</p>
                      </div>
                    )}

                    <div className="event-card-footer">
                      <button
                        type="button"
                        className="secondary-action-button"
                        onClick={() => loadRegistrants(event.id)}
                      >
                        {expandedEvent === event.id
                          ? "Hide registrations"
                          : "View registrations"}
                      </button>
                    </div>

                    {expandedEvent === event.id && (
                      <div className="event-registrants">
                        <div className="registrants-heading">
                          <strong>Registered students</strong>
                          <span>{eventRegistrants.length}</span>
                        </div>

                        {eventRegistrants.length === 0 ? (
                          <p className="registrants-empty">
                            No students have registered yet.
                          </p>
                        ) : (
                          <div className="registrant-list">
                            {eventRegistrants.map((student) => (
                              <Link
                                key={student.student_id}
                                to={`/company/students/${student.student_id}`}
                                className="registrant-item"
                              >
                                <div className="student-avatar">
                                  {student.name
                                    ? student.name
                                        .charAt(0)
                                        .toUpperCase()
                                    : "S"}
                                </div>

                                <div>
                                  <strong>{student.name}</strong>

                                  <span>
                                    {student.college_name ||
                                      student.email}
                                  </span>
                                </div>
                              </Link>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}