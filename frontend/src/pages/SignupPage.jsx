function SignupPage() {
    function handleSubmit(event) {
      event.preventDefault()
    }
  
    return (
      <section className="form-card">
        <h1>Create a student account</h1>
        <p>Sign up to search for jobs and internships.</p>
  
        <form onSubmit={handleSubmit}>
          <label htmlFor="full-name">Full name</label>
          <input id="full-name" name="full_name" type="text" required />
  
          <label htmlFor="signup-email">Email</label>
          <input id="signup-email" name="email" type="email" required />
  
          <label htmlFor="city">City</label>
          <input id="city" name="city" type="text" required />
  
          <label htmlFor="signup-password">Password</label>
          <input
            id="signup-password"
            name="password"
            type="password"
            required
          />
  
          <button type="submit">Create account</button>
        </form>
      </section>
    )
  }
  
  export default SignupPage