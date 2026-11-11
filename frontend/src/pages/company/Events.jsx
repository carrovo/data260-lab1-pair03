import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import {
  clearCreateEventState,
  createMyEvent,
  loadMyEvents,
  loadRegistrants as loadEventRegistrants,
  selectEventCreate,
  selectMyEvents,
  selectRegistrants,
} from "../../store/eventsSlice";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function Events() {
  const dispatch = useDispatch();
  const myEvents = useSelector(selectMyEvents);
  const createState = useSelector(selectEventCreate);
  const registrantState = useSelector(selectRegistrants);
  const [expandedEvent, setExpandedEvent] = useState(null);

  const events = myEvents.items;
  const registrants = { [registrantState.eventId]: registrantState.items };
  const loading = myEvents.status === "idle" || myEvents.status === "loading";
  const posting = createState.status === "loading";
  const error = createState.error || registrantState.error || myEvents.error;

  const [form, setForm] = useState({
    title: "",
    description: "",
    date: "",
    startTime: "",
    endTime: "",
    city: "San Jose",
    location: "",
    major: "",
    eligibility: "",
  });

  useEffect(() => {
    dispatch(clearCreateEventState());
    dispatch(loadMyEvents());
  }, [dispatch]);

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const startsAt = new Date(
      `${form.date}T${form.startTime}:00`
    ).toISOString();

    const endsAt = new Date(
      `${form.date}T${form.endTime}:00`
    ).toISOString();

    const result = await dispatch(
      createMyEvent({
        title: form.title.trim(),
        description: form.description.trim(),
        city: form.city,
        starts_at: startsAt,
        ends_at: endsAt,
        location: form.location.trim() || null,
        major: form.major.trim() || null,
        eligibility: form.eligibility.trim() || null,
      }),
    );

    if (createMyEvent.fulfilled.match(result)) {
      setForm({
        title: "",
        description: "",
        date: "",
        startTime: "",
        endTime: "",
        city: "San Jose",
        location: "",
        major: "",
        eligibility: "",
      });
    }
  };

  const loadRegistrants = async (eventId) => {
    if (expandedEvent === eventId) {
      setExpandedEvent(null);
      return;
    }

    const result = await dispatch(loadEventRegistrants(eventId));

    if (loadEventRegistrants.fulfilled.match(result)) {
      setExpandedEvent(eventId);
    }
  };

  if (loading) {
    return (
      <div className="company-dashboard-page">
        <Loading label="Loading events..." />
      </div>
    );
  }

  return (
    <div className="company-dashboard-page">
      <div className="company-page-header">
        <div className="company-page-header-main">
          <p className="company-page-eyebrow">RECRUITING EVENTS</p>
          <h1>Events</h1>
          <p>
            Create recruiting events and manage student
            registrations.
          </p>
        </div>
      </div>

      <ErrorMessage error={error} />

      <section className="dashboard-card event-create-card">
        <h2>Create an event</h2>

        <form className="event-form" onSubmit={handleSubmit}>
          <label>
            Event title
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Description
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              rows="4"
              required
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
              Start time
              <input
                type="time"
                name="startTime"
                value={form.startTime}
                onChange={handleChange}
                required
              />
            </label>
          </div>

          <div className="form-two-column">
            <label>
              End time
              <input
                type="time"
                name="endTime"
                value={form.endTime}
                onChange={handleChange}
                required
              />
            </label>

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
          </div>

          <label>
            Location
            <input
              name="location"
              value={form.location}
              onChange={handleChange}
            />
          </label>

          <label>
            Major
            <input
              name="major"
              value={form.major}
              onChange={handleChange}
              placeholder="e.g. Computer Science"
            />
          </label>

          <label>
            Eligibility
            <input
              name="eligibility"
              value={form.eligibility}
              onChange={handleChange}
            />
          </label>

          <button
            type="submit"
            className="primary-action-button"
            disabled={posting}
          >
            {posting ? "Publishing..." : "Publish event"}
          </button>
        </form>
      </section>

      <section className="events-list-section">
        <h2>Your events</h2>

        {events.length === 0 ? (
          <div className="dashboard-card empty-state">
            <h3>No events posted yet</h3>
          </div>
        ) : (
          <div className="event-card-grid">
            {events.map((event) => {
              const eventRegistrants =
                registrants[event.id] || [];

              return (
                <article
                  key={event.id}
                  className="dashboard-card recruiter-event-card"
                >
                  <h3>{event.title}</h3>

                  <p>{event.description}</p>

                  <p>
                    <strong>Date:</strong>{" "}
                    {new Date(
                      event.starts_at
                    ).toLocaleDateString()}
                  </p>

                  <p>
                    <strong>Time:</strong>{" "}
                    {new Date(
                      event.starts_at
                    ).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                    {" – "}
                    {new Date(
                      event.ends_at
                    ).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </p>

                  <p>
                    <strong>City:</strong> {event.city}
                  </p>

                  <p>
                    <strong>Location:</strong>{" "}
                    {event.location || "Not specified"}
                  </p>

                  {event.major && (
                    <p>
                      <strong>Major:</strong> {event.major}
                    </p>
                  )}

                  {event.eligibility && (
                    <p>
                      <strong>Eligibility:</strong>{" "}
                      {event.eligibility}
                    </p>
                  )}

                  <button
                    type="button"
                    className="secondary-action-button"
                    onClick={() =>
                      loadRegistrants(event.id)
                    }
                  >
                    {expandedEvent === event.id
                      ? "Hide registrations"
                      : "View registrations"}
                  </button>

                  {expandedEvent === event.id && (
                    <div className="event-registrants">
                      <h4>Registered students</h4>

                      {eventRegistrants.length === 0 ? (
                        <p>No registrations yet.</p>
                      ) : (
                        eventRegistrants.map((student) => (
                          <div
                            key={`${event.id}-${student.student_id}`}
                            className="registrant-row"
                          >
                            <strong>
                              {student.full_name}
                            </strong>

                            <span>{student.email}</span>

                            <span>
                              {student.college_name ||
                                "College not specified"}
                            </span>
                          </div>
                        ))
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
  );
}
