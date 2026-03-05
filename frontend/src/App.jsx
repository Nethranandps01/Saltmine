import { useState } from 'react'
import ProjectForm from './components/ProjectForm'
import ComplianceReport from './components/ComplianceReport'
import styles from './App.module.css'

export default function App() {
    const [report, setReport] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    async function handleSubmit(formData) {
        setLoading(true)
        setError(null)
        setReport(null)
        try {
            const res = await fetch('/api/compliance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Server error')
            }
            const data = await res.json()
            setReport(data)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    function handleReset() {
        setReport(null)
        setError(null)
    }

    return (
        <div className={styles.layout}>
            {/* ── Sidebar nav ── */}
            <aside className={styles.sidebar}>
                <div className={styles.logo}>
                    <span className={styles.logoIcon}>⚡</span>
                    <span className={styles.logoText}>Salt-Mine</span>
                </div>
                <nav className={styles.nav}>
                    <span className={`${styles.navItem} ${styles.navActive}`}>
                        <span>🏛</span> IBC Compliance
                    </span>
                    <span className={styles.navItem}><span>📋</span> Reports</span>
                    <span className={styles.navItem}><span>🗺</span> Space Mapper</span>
                </nav>
                <div className={styles.sidebarFooter}>
                    <div className={styles.ibcBadge}>IBC 2021</div>
                    <div className={styles.aiBadge}>
                        <span className={styles.dot} /> Gemini 2.0 Flash
                    </div>
                </div>
            </aside>

            {/* ── Main content ── */}
            <main className={styles.main}>
                {!report ? (
                    <ProjectForm onSubmit={handleSubmit} loading={loading} error={error} />
                ) : (
                    <ComplianceReport data={report} onReset={handleReset} />
                )}
            </main>
        </div>
    )
}
