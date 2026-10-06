function LoginPage() {
    function handleSubmit(event) {
      event.preventDefault()
    }
  
    return (
      <section className="form-card">
        <h1>Student login</h1>
        <p>Log in to access your student account.</p>
  
        <form onSubmit={handleSubmit}>
          <label htmlFor="login-email">Email</label>
          <input id="login-email" name="email" type="email" required />
  
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            name="password"
            type="password"
            required
          />
  
          <button type="submit">Log in</button>
        </form>
      </section>
    )
  }
  
  export default LoginPage