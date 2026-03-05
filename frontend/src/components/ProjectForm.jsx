import { useState } from 'react'
import styles from './ProjectForm.module.css'

const DEFAULTS = {
    project_name: 'Tower A POC',
    num_floors: 2,
    sqft_per_floor: 10000,
    total_headcount: 90,
    male_pct: 50,
    regularity: 'permanent',
    is_sprinklered: true,
    num_meeting_rooms: 3,
    meeting_room_capacity: 10,
    actual_exits_per_floor: 2,
    actual_wc_male_per_floor: 2,
    actual_wc_female_per_floor: 2,
    actual_lavatories_per_floor: 3,
    actual_drinking_fountains: 1,
    actual_service_sinks: 1,
}

function Field({ label, hint, children }) {
    return (
        <div className={styles.field}>
            <label className={styles.label}>
                {label}
                {hint && <span className={styles.hint}>{hint}</span>}
            </label>
            {children}
        </div>
    )
}

function NumInput({ name, value, onChange, min = 0, step = 1 }) {
    return (
        <input
            type="number"
            className={styles.input}
            name={name}
            value={value}
            onChange={onChange}
            min={min}
            step={step}
        />
    )
}

export default function ProjectForm({ onSubmit, loading, error }) {
    const [form, setForm] = useState(DEFAULTS)

    function set(key, val) {
        setForm(f => ({ ...f, [key]: val }))
    }

    function handleChange(e) {
        const { name, value, type, checked } = e.target
        if (type === 'checkbox') return set(name, checked)
        const num = ['num_floors', 'sqft_per_floor', 'total_headcount', 'male_pct',
            'num_meeting_rooms', 'meeting_room_capacity', 'actual_exits_per_floor',
            'actual_wc_male_per_floor', 'actual_wc_female_per_floor',
            'actual_lavatories_per_floor', 'actual_drinking_fountains', 'actual_service_sinks']
        set(name, num.includes(name) ? Number(value) : value)
    }

    function handleSubmit(e) {
        e.preventDefault()
        onSubmit(form)
    }

    const female_pct = 100 - form.male_pct

    return (
        <div className={styles.wrap}>
            {/* ── Header ── */}
            <div className={styles.header}>
                <div className={styles.headerBadge}>🏛 IBC 2021 · Business (B) Occupancy</div>
                <h1 className={styles.title}>
                    IBC <span>Compliance</span> Checker
                </h1>
                <p className={styles.subtitle}>
                    AI-powered analysis using Gemini 2.0 Flash · Occupancy Load · Plumbing · Egress
                </p>
            </div>

            <form className={styles.form} onSubmit={handleSubmit}>

                {/* ── Section 1: Project ── */}
                <section className={`${styles.section} fade-up`}>
                    <h2 className={styles.sectionTitle}>
                        <span className={styles.sectionNum}>01</span> Project Info
                    </h2>
                    <div className={styles.grid2}>
                        <Field label="Project Name">
                            <input
                                type="text"
                                className={styles.input}
                                name="project_name"
                                value={form.project_name}
                                onChange={handleChange}
                                placeholder="e.g. Tower A POC"
                            />
                        </Field>
                        <Field label="Occupancy Regularity">
                            <select className={styles.select} name="regularity" value={form.regularity} onChange={handleChange}>
                                <option value="permanent">Permanent (employees)</option>
                                <option value="transient">Transient (visitors)</option>
                                <option value="mixed">Mixed</option>
                            </select>
                        </Field>
                    </div>
                    <div className={styles.checkRow}>
                        <label className={styles.checkLabel}>
                            <input type="checkbox" name="is_sprinklered" checked={form.is_sprinklered} onChange={handleChange} className={styles.checkbox} />
                            <span>Building is fully sprinklered</span>
                            <span className={styles.checkHint}>(affects travel distance limit: 300 ft vs 200 ft)</span>
                        </label>
                    </div>
                </section>

                {/* ── Section 2: Building ── */}
                <section className={`${styles.section} fade-up-1`}>
                    <h2 className={styles.sectionTitle}>
                        <span className={styles.sectionNum}>02</span> Building Dimensions
                    </h2>
                    <div className={styles.grid3}>
                        <Field label="Number of Floors" hint="floors occupied">
                            <NumInput name="num_floors" value={form.num_floors} onChange={handleChange} min={1} />
                        </Field>
                        <Field label="Usable Area per Floor" hint="sq ft">
                            <NumInput name="sqft_per_floor" value={form.sqft_per_floor} onChange={handleChange} min={100} step={100} />
                        </Field>
                        <div className={styles.statCard}>
                            <div className={styles.statLabel}>Total Usable Area</div>
                            <div className={styles.statValue}>{(form.num_floors * form.sqft_per_floor).toLocaleString()}</div>
                            <div className={styles.statUnit}>sq ft</div>
                        </div>
                    </div>
                </section>

                {/* ── Section 3: Headcount ── */}
                <section className={`${styles.section} fade-up-2`}>
                    <h2 className={styles.sectionTitle}>
                        <span className={styles.sectionNum}>03</span> Headcount
                    </h2>
                    <div className={styles.grid3}>
                        <Field label="Total Headcount" hint="all floors">
                            <NumInput name="total_headcount" value={form.total_headcount} onChange={handleChange} min={1} />
                        </Field>
                        <Field label="% Male Occupants">
                            <div className={styles.sliderWrap}>
                                <input
                                    type="range" min={0} max={100}
                                    name="male_pct" value={form.male_pct}
                                    onChange={handleChange}
                                    className={styles.slider}
                                />
                                <div className={styles.sliderLabels}>
                                    <span>♂ {form.male_pct}%</span>
                                    <span>♀ {female_pct}%</span>
                                </div>
                            </div>
                        </Field>
                        <div className={styles.statCard}>
                            <div className={styles.statLabel}>Per Floor (avg)</div>
                            <div className={styles.statValue}>{Math.ceil(form.total_headcount / form.num_floors)}</div>
                            <div className={styles.statUnit}>people</div>
                        </div>
                    </div>
                </section>

                {/* ── Section 4: Spaces ── */}
                <section className={`${styles.section} fade-up-3`}>
                    <h2 className={styles.sectionTitle}>
                        <span className={styles.sectionNum}>04</span> Meeting Rooms
                    </h2>
                    <div className={styles.grid3}>
                        <Field label="Number of Meeting Rooms" hint="all floors total">
                            <NumInput name="num_meeting_rooms" value={form.num_meeting_rooms} onChange={handleChange} />
                        </Field>
                        <Field label="Avg Capacity per Room" hint="people">
                            <NumInput name="meeting_room_capacity" value={form.meeting_room_capacity} onChange={handleChange} min={1} />
                        </Field>
                        <div className={styles.statCard}>
                            <div className={styles.statLabel}>Meeting Capacity</div>
                            <div className={styles.statValue}>{form.num_meeting_rooms * form.meeting_room_capacity}</div>
                            <div className={styles.statUnit}>total seats</div>
                        </div>
                    </div>
                </section>

                {/* ── Section 5: Actual Design ── */}
                <section className={`${styles.section} fade-up-4`}>
                    <h2 className={styles.sectionTitle}>
                        <span className={styles.sectionNum}>05</span> Actual Design Values
                        <span className={styles.sectionBadge}>from drawings</span>
                    </h2>
                    <p className={styles.sectionDesc}>
                        Enter what's in your current test-fit design. The AI will compare these to IBC minimums.
                    </p>

                    <div className={styles.designGrid}>
                        <div className={styles.designGroup}>
                            <div className={styles.groupTitle}>🚪 Egress</div>
                            <Field label="Exits per Floor">
                                <NumInput name="actual_exits_per_floor" value={form.actual_exits_per_floor} onChange={handleChange} min={0} />
                            </Field>
                        </div>

                        <div className={styles.designGroup}>
                            <div className={styles.groupTitle}>🚿 Plumbing — per Floor</div>
                            <div className={styles.grid2}>
                                <Field label="Male WCs">
                                    <NumInput name="actual_wc_male_per_floor" value={form.actual_wc_male_per_floor} onChange={handleChange} min={0} />
                                </Field>
                                <Field label="Female WCs">
                                    <NumInput name="actual_wc_female_per_floor" value={form.actual_wc_female_per_floor} onChange={handleChange} min={0} />
                                </Field>
                                <Field label="Lavatories (sinks)">
                                    <NumInput name="actual_lavatories_per_floor" value={form.actual_lavatories_per_floor} onChange={handleChange} min={0} />
                                </Field>
                            </div>
                        </div>

                        <div className={styles.designGroup}>
                            <div className={styles.groupTitle}>🏢 Whole Building</div>
                            <div className={styles.grid2}>
                                <Field label="Drinking Fountains">
                                    <NumInput name="actual_drinking_fountains" value={form.actual_drinking_fountains} onChange={handleChange} min={0} />
                                </Field>
                                <Field label="Service Sinks">
                                    <NumInput name="actual_service_sinks" value={form.actual_service_sinks} onChange={handleChange} min={0} />
                                </Field>
                            </div>
                        </div>
                    </div>
                </section>

                {/* ── Error ── */}
                {error && (
                    <div className={styles.error}>
                        <span>⚠️</span> {error}
                    </div>
                )}

                {/* ── Submit ── */}
                <div className={styles.submitRow}>
                    <button type="submit" className={styles.submitBtn} disabled={loading}>
                        {loading ? (
                            <>
                                <span className={styles.spinner} />
                                Running Gemini IBC Analysis…
                            </>
                        ) : (
                            <>⚡ Run IBC Compliance Check</>
                        )}
                    </button>
                    <p className={styles.submitNote}>
                        Powered by Gemini 2.0 Flash · IBC 2021 · Occupancy · Plumbing · Egress
                    </p>
                </div>
            </form>
        </div>
    )
}
