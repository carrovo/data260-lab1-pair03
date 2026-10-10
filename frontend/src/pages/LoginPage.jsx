import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuth from '../auth/useAuth'


const initialFormData = {
  email: '',
  password: '',
}

function LoginPage() {
  const [formData, setFormData] = useState(initialFormData)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { signIn } = useAuth()
  const navigate = useNavigate()

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

    try {
      const response = await signIn(formData)

      navigate('/jobs', {
        replace: true,
        state: {
          successMessage: `Welcome back, ${response.student.full_name}.`,
        },
      })
    } catch (requestError) {
      setError(requestError.message)
      setLoading(false)
    }
  }

  return (
    <section className="form-card">
      <h1>Student login</h1>
      <p>Log in to access your student account.</p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          required
        />

        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          value={formData.password}
          onChange={handleChange}
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Log in'}
        </button>
      </form>
      {error && <p className="error-message">{error}</p>}
    </section>
  )
}

export default LoginPage
