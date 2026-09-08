import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ArrowUpRight, Check, Inbox, Plus, Search, SlidersHorizontal, X } from 'lucide-react'
import './styles.css'

const statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
const emptyForm = { title: '', description: '', requesterName: '', requesterEmail: '', assignee: '', status: 'Open' }

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.message || 'Something went wrong')
  }
  return response.status === 204 ? null : response.json()
}

function App() {
  const [inquiries, setInquiries] = useState([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [editing, setEditing] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadInquiries = async () => {
    setLoading(true)
    try {
      setInquiries(await api(`/api/inquiries?search=${encodeURIComponent(search)}&status=${encodeURIComponent(statusFilter)}`))
      setError('')
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => {
    const timer = setTimeout(loadInquiries, 250)
    return () => clearTimeout(timer)
  }, [search, statusFilter])

  const openCreate = () => { setEditing(null); setForm(emptyForm); setShowForm(true) }
  const openEdit = (inquiry) => {
    setEditing(inquiry.id)
    setForm({ title: inquiry.title, description: inquiry.description, requesterName: inquiry.requesterName, requesterEmail: inquiry.requesterEmail, assignee: inquiry.assignee || '', status: inquiry.status })
    setShowForm(true)
  }
  const saveInquiry = async (event) => {
    event.preventDefault()
    try {
      await api(editing ? `/api/inquiries/${editing}` : '/api/inquiries', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(form) })
      setShowForm(false); await loadInquiries()
    } catch (err) { setError(err.message) }
  }
  const updateField = async (id, field, value) => {
    try {
      const updated = await api(`/api/inquiries/${id}/${field}`, { method: 'PATCH', body: JSON.stringify({ [field === 'assignment' ? 'assignee' : 'status']: value }) })
      setInquiries(current => current.map(item => item.id === id ? updated : item))
    } catch (err) { setError(err.message) }
  }

  const counts = statuses.reduce((result, status) => ({ ...result, [status]: inquiries.filter(item => item.status === status).length }), {})

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark"><Inbox size={18} /></span><span>inquiry<span className="brand-accent">desk</span></span></div>
      <div className="topbar-meta"><span className="live-dot" /> Operations workspace <span className="avatar">OD</span></div>
    </header>
    <main className="content">
      <section className="intro"><div><p className="eyebrow">Service operations / All inquiries</p><h1>Keep every question moving.</h1><p className="subhead">A clear view of what needs attention, who owns it, and what happens next.</p></div><button className="primary-button" onClick={openCreate}><Plus size={18} /> New inquiry</button></section>
      <section className="stats" aria-label="Inquiry summary">
        <div className="stat-card total"><span>Total inquiries</span><strong>{inquiries.length}</strong><small>in current view</small></div>
        <div className="stat-card"><span>Open</span><strong>{counts.Open || 0}</strong><small className="status-note open-note">Needs an owner</small></div>
        <div className="stat-card"><span>In progress</span><strong>{counts['In Progress'] || 0}</strong><small className="status-note progress-note">Being worked on</small></div>
        <div className="stat-card"><span>Resolved</span><strong>{counts.Resolved || 0}</strong><small className="status-note resolved-note">Ready to close</small></div>
      </section>
      <section className="toolbar"><div className="search-box"><Search size={18} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search inquiries, people, or email" /></div><div className="filter-wrap"><SlidersHorizontal size={16} /><select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All statuses</option>{statuses.map(status => <option key={status}>{status}</option>)}</select></div></section>
      {error && <div className="error-banner">{error}<button onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button></div>}
      <section className="inquiry-panel"><div className="panel-heading"><div><h2>Inquiry queue</h2><span>{loading ? 'Refreshing...' : `${inquiries.length} ${inquiries.length === 1 ? 'result' : 'results'}`}</span></div><span className="updated-label">Updated just now</span></div>
        {loading ? <div className="empty-state">Loading inquiry queue...</div> : inquiries.length === 0 ? <div className="empty-state"><Inbox size={28} /><strong>No inquiries found</strong><span>Try a different search or create a new inquiry.</span></div> : <div className="inquiry-list">{inquiries.map(inquiry => <article className="inquiry-row" key={inquiry.id}><div className="inquiry-main"><div className="inquiry-icon">{inquiry.title.slice(0, 1).toUpperCase()}</div><div className="inquiry-copy"><div className="title-line"><h3>{inquiry.title}</h3><button className="edit-link" onClick={() => openEdit(inquiry)}>Edit <ArrowUpRight size={14} /></button></div><p>{inquiry.description}</p><div className="requester"><span>{inquiry.requesterName}</span><span className="separator">/</span><span>{inquiry.requesterEmail}</span></div></div></div><div className="inquiry-controls"><label>Status<select className={`status-select status-${inquiry.status.toLowerCase().replace(' ', '-')}`} value={inquiry.status} onChange={event => updateField(inquiry.id, 'status', event.target.value)}>{statuses.map(status => <option key={status}>{status}</option>)}</select></label><label>Assigned to<select value={inquiry.assignee || ''} onChange={event => updateField(inquiry.id, 'assignment', event.target.value)}><option value="">Unassigned</option><option>Jordan Lee</option><option>Sam Rivera</option><option>Alex Morgan</option></select></label></div></article>)}</div>}
      </section>
    </main>
    {showForm && <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && setShowForm(false)}><form className="modal" onSubmit={saveInquiry}><div className="modal-heading"><div><p className="eyebrow">{editing ? 'Update record' : 'New record'}</p><h2>{editing ? 'Edit inquiry' : 'Create an inquiry'}</h2></div><button type="button" className="icon-button" onClick={() => setShowForm(false)} aria-label="Close"><X size={19} /></button></div><div className="form-grid"><label className="wide">Subject<input required maxLength="160" value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} placeholder="What does the customer need?" /></label><label className="wide">Description<textarea required rows="4" value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} placeholder="Add the details needed to resolve this inquiry." /></label><label>Requester name<input required value={form.requesterName} onChange={event => setForm({ ...form, requesterName: event.target.value })} /></label><label>Requester email<input required type="email" value={form.requesterEmail} onChange={event => setForm({ ...form, requesterEmail: event.target.value })} /></label><label>Assignee<select value={form.assignee} onChange={event => setForm({ ...form, assignee: event.target.value })}><option value="">Unassigned</option><option>Jordan Lee</option><option>Sam Rivera</option><option>Alex Morgan</option></select></label><label>Status<select value={form.status} onChange={event => setForm({ ...form, status: event.target.value })}>{statuses.map(status => <option key={status}>{status}</option>)}</select></label></div><div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setShowForm(false)}>Cancel</button><button type="submit" className="primary-button"><Check size={17} /> {editing ? 'Save changes' : 'Create inquiry'}</button></div></form></div>}
  </div>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)