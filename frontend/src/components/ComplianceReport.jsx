import styles from './ComplianceReport.module.css'

const MODULE_ICONS = {
    'Occupancy Load': '👥',
    'Plumbing': '🚿',
    'Egress': '🚪',
}

const CONF_COLORS = {
    high: { color: '#1fcc6e', bg: '#1fcc6e18' },
    medium: { color: '#ffb830', bg: '#ffb83018' },
    low: { color: '#ff4545', bg: '#ff454518' },
}

function PassBadge({ val, size = 'sm' }) {
    if (val === true) return <span className={`${styles.badge} ${styles.pass} ${styles[size]}`}>✅ PASS</span>
    if (val === false) return <span className={`${styles.badge} ${styles.fail} ${styles[size]}`}>❌ FAIL</span>
    return <span className={`${styles.badge} ${styles.na} ${styles[size]}`}>⚠️ Verify</span>
}

function ScoreRing({ pct }) {
    const r = 44
    const circ = 2 * Math.PI * r
    const dash = (pct / 100) * circ
    const color = pct >= 80 ? '#1fcc6e' : pct >= 50 ? '#ffb830' : '#ff4545'
    return (
        <div className={styles.ringWrap}>
            <svg width={104} height={104} viewBox="0 0 104 104">
                <circle cx={52} cy={52} r={r} fill="none" stroke="#1e3055" strokeWidth={10} />
                <circle
                    cx={52} cy={52} r={r} fill="none"
                    stroke={color} strokeWidth={10}
                    strokeDasharray={`${dash} ${circ}`}
                    strokeLinecap="round"
                    transform="rotate(-90 52 52)"
                    style={{ transition: 'stroke-dasharray 1s ease' }}
                />
            </svg>
            <div className={styles.ringInner}>
                <span className={styles.ringPct} style={{ color }}>{pct}%</span>
            </div>
        </div>
    )
}

function ModuleCard({ module }) {
    const icon = MODULE_ICONS[module.module] || '📋'
    const pass = module.overall_pass
    return (
        <div className={`${styles.moduleCard} ${pass === true ? styles.modPass : pass === false ? styles.modFail : styles.modNa}`}>
            <div className={styles.moduleHeader}>
                <div className={styles.moduleTitle}>
                    <span className={styles.moduleIcon}>{icon}</span>
                    <div>
                        <div className={styles.moduleName}>{module.module}</div>
                        <div className={styles.moduleRef}>{module.ibc_chapter}</div>
                    </div>
                </div>
                <PassBadge val={pass} size="lg" />
            </div>

            <table className={styles.checkTable}>
                <thead>
                    <tr>
                        <th>Check</th>
                        <th>Formula</th>
                        <th>IBC Required</th>
                        <th>Design Actual</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {module.checks.map((c, i) => (
                        <>
                            <tr key={i} className={c.pass === true ? styles.rowPass : c.pass === false ? styles.rowFail : ''}>
                                <td className={styles.checkName}>
                                    {c.check}
                                    <div className={styles.ibcRef}>{c.ibc_ref}</div>
                                </td>
                                <td className={styles.formula}>{c.formula}</td>
                                <td className={styles.required}>{c.required}</td>
                                <td className={styles.actual}>
                                    {c.actual_val == null
                                        ? <em className={styles.naText}>{c.actual}</em>
                                        : c.actual}
                                </td>
                                <td><PassBadge val={c.pass} /></td>
                            </tr>
                            <tr key={`note-${i}`} className={styles.noteRow}>
                                <td colSpan={5}>
                                    <span className={styles.noteText}>📖 {c.note}</span>
                                </td>
                            </tr>
                        </>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

function RoomMappingTable({ rooms }) {
    return (
        <div className={styles.roomSection}>
            <h2 className={styles.sectionTitle}>
                <span className={styles.sectionIcon}>🏢</span>
                Room / Space Mapping
                <span className={styles.secBadge}>AI · Gemini 2.0 Flash</span>
            </h2>
            <div className={styles.tableWrap}>
                <table className={styles.roomTable}>
                    <thead>
                        <tr>
                            <th>Space Name</th>
                            <th>Enclosure</th>
                            <th>Cap.</th>
                            <th>Sqft</th>
                            <th>IBC Function of Space</th>
                            <th>Load Factor</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rooms.map((r, i) => {
                            const conf = CONF_COLORS[r.confidence] || { color: '#8899bb', bg: '#8899bb18' }
                            return (
                                <>
                                    <tr key={i}>
                                        <td className={styles.roomName}>{r.name}</td>
                                        <td><span className={styles.enc}>{r.enclosure}</span></td>
                                        <td className={styles.mono}>{r.capacity}</td>
                                        <td className={styles.mono}>{r.area_sqft?.toLocaleString()}</td>
                                        <td className={styles.ibcCat}>{r.ibc_category}</td>
                                        <td className={styles.mono}>{r.load_factor} {r.area_method}</td>
                                        <td>
                                            <span className={styles.confBadge} style={{ color: conf.color, background: conf.bg, borderColor: conf.color + '40' }}>
                                                {r.confidence}
                                            </span>
                                        </td>
                                    </tr>
                                    {r.reasoning && (
                                        <tr key={`r-note-${i}`} className={styles.noteRow}>
                                            <td colSpan={7}>
                                                <span className={styles.noteText}>💬 {r.reasoning}</span>
                                            </td>
                                        </tr>
                                    )}
                                </>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

export default function ComplianceReport({ data, onReset }) {
    const { project, summary, modules, room_mappings, timestamp } = data
    const date = new Date(timestamp).toLocaleString()

    function handlePrint() { window.print() }

    return (
        <div className={styles.wrap}>
            {/* ── Top bar ── */}
            <div className={styles.topBar}>
                <button className={styles.backBtn} onClick={onReset}>← New Project</button>
                <button className={styles.printBtn} onClick={handlePrint}>🖨 Export PDF</button>
            </div>

            {/* ── Header ── */}
            <div className={styles.header + ' fade-up'}>
                <div className={styles.headerLeft}>
                    <div className={styles.reportBadge}>⚡ Salt-Mine · IBC Compliance Report</div>
                    <h1 className={styles.title}>
                        <span className={styles.titleAccent}>{project.project_name}</span>
                    </h1>
                    <p className={styles.meta}>
                        {date} &nbsp;·&nbsp; IBC 2021 &nbsp;·&nbsp; Business (B) Occupancy &nbsp;·&nbsp;{' '}
                        {project.is_sprinklered ? '✅ Sprinklered' : '⚠️ Unsprinklered'}
                    </p>
                </div>
                <ScoreRing pct={summary.pass_pct} />
            </div>

            {/* ── Stats bar ── */}
            <div className={`${styles.statsBar} fade-up-1`}>
                {[
                    ['Floors', project.num_floors, 'occupied'],
                    ['Sqft / Floor', project.sqft_per_floor?.toLocaleString(), 'usable area'],
                    ['Total Sqft', (project.num_floors * project.sqft_per_floor)?.toLocaleString(), 'all floors'],
                    ['Headcount', project.total_headcount, project.regularity],
                    ['Per Floor', Math.ceil(project.total_headcount / project.num_floors), 'avg occupants'],
                    ['Meeting Rooms', project.num_meeting_rooms, `${project.meeting_room_capacity} cap each`],
                ].map(([label, val, sub]) => (
                    <div className={styles.stat} key={label}>
                        <div className={styles.statLabel}>{label}</div>
                        <div className={styles.statValue}>{val}</div>
                        <div className={styles.statSub}>{sub}</div>
                    </div>
                ))}
            </div>

            {/* ── Summary cards ── */}
            <div className={`${styles.summaryRow} fade-up-2`}>
                <div className={`${styles.sumCard} ${styles.sumPass}`}>
                    <div className={styles.sumLabel}>✅ Passed</div>
                    <div className={styles.sumValue}>{summary.passed}</div>
                </div>
                <div className={`${styles.sumCard} ${summary.failed > 0 ? styles.sumFail : styles.sumPass}`}>
                    <div className={styles.sumLabel}>❌ Failed</div>
                    <div className={styles.sumValue}>{summary.failed}</div>
                </div>
                <div className={`${styles.sumCard} ${styles.sumNa}`}>
                    <div className={styles.sumLabel}>⚠️ Verify</div>
                    <div className={styles.sumValue}>{summary.na}</div>
                </div>
                <div className={styles.sumCard}>
                    <div className={styles.sumLabel}>📋 Total Checks</div>
                    <div className={styles.sumValue}>{summary.total_checks}</div>
                </div>
            </div>

            {/* ── IBC Modules ── */}
            <div className={`${styles.modules} fade-up-3`}>
                <h2 className={styles.sectionTitle}>
                    <span className={styles.sectionIcon}>📋</span>
                    IBC Compliance Checks — 3 Modules
                </h2>
                {modules.map((m, i) => <ModuleCard key={i} module={m} />)}
            </div>

            {/* ── Room Mapping ── */}
            {room_mappings?.length > 0 && (
                <div className="fade-up-4">
                    <RoomMappingTable rooms={room_mappings} />
                </div>
            )}

            <div className={styles.footer}>
                Salt-Mine · IBC 2021 Compliance Engine · Powered by Gemini 2.0 Flash
                <br />
                <small>For planning and test-fit analysis only. Consult a licensed Architect before permit submission.</small>
            </div>
        </div>
    )
}
