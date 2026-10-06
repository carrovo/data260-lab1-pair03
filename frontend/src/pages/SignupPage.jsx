import { useState } from 'react'
import { signupStudent } from '../api'

const initialFormData = {
  full_name: '',
  email: '',
  city: '',
  password: '',
}

function SignupPage() {
  const [formData, setFormData] = useState(initialFormData)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  function handleChange(event) {
    const { name, value } = event.target

    setFormData((currentData) => ({
      ...currentData,
      [name]: value,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')

    try {
      const student = await signupStudent(formData)

      setMessage(
        `Account created successfully for ${student.full_name}.`,
      )
      setFormData(initialFormData)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="form-card">
      <h1>Create a student account</h1>
      <p>Sign up to search for jobs and internships.</p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="full-name">Full name</label>
        <input
          id="full-name"
          name="full_name"
          type="text"
          value={formData.full_name}
          onChange={handleChange}
          maxLength="255"
          required
        />

        <label htmlFor="signup-email">Email</label>
        <input
          id="signup-email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          required
        />

        <label htmlFor="city">City</label>
        <input
          id="city"
          name="city"
          type="text"
          value={formData.city}
          onChange={handleChange}
          maxLength="100"
          required
        />

        <label htmlFor="signup-password">Password</label>
        <input
          id="signup-password"
          name="password"
          type="password"
          value={formData.password}
          onChange={handleChange}
          minLength="8"
          maxLength="72"
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Creating account...' : 'Create account'}
        </button>
      </form>

      {message && <p className="success-message">{message}</p>}
      {error && <p className="error-message">{error}</p>}
    </section>
  )
}

export default SignupPage