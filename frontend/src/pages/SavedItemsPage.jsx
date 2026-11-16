import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { refreshSavedItems, selectSavedItems, unsaveItem } from '../store/savedItemsSlice.js'

export default function SavedItemsPage() {
  const dispatch = useDispatch()
  const { items, status, error } = useSelector(selectSavedItems)
  useEffect(() => { dispatch(refreshSavedItems()) }, [dispatch])
  return <section className="page-shell">
    <div className="page-header"><h1>Saved items</h1>
      <button className="secondary-button" disabled={status === 'loading'} onClick={() => dispatch(refreshSavedItems())}>Refresh</button>
    </div>
    {status === 'loading' && <p role="status">Loading saved items...</p>}
    {error && <p role="alert" className="error-message">{error}</p>}
    {status === 'succeeded' && !items.length && <p>No saved opportunities yet.</p>}
    {items.map(item => {
      const id = item.job_id ?? item.event_id
      return <article className="surface-card" key={`${item.item_type}:${id}`}>
        <Link to={`/${item.item_type === 'job' ? 'jobs' : 'events'}/${id}`}>View saved {item.item_type} #{id}</Link>{' '}
        <button className="secondary-button" disabled={status === 'loading'} onClick={() => dispatch(unsaveItem(item.item_type, id))}>Unsave</button>
      </article>
    })}
  </section>
}
