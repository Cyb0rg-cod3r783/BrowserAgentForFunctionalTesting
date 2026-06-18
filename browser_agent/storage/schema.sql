CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_versions (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES applications(id),
    label TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES app_versions(id),
    url_pattern TEXT NOT NULL,
    title TEXT,
    purpose TEXT,
    accessibility_snapshot TEXT
);

CREATE TABLE IF NOT EXISTS elements (
    id TEXT PRIMARY KEY,
    page_id TEXT NOT NULL REFERENCES pages(id),
    element_type TEXT NOT NULL,
    semantic_label TEXT NOT NULL,
    locators TEXT NOT NULL,
    validation_rules TEXT,
    observed_values TEXT
);

CREATE TABLE IF NOT EXISTS user_flows (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES app_versions(id),
    name TEXT NOT NULL,
    description TEXT,
    start_url TEXT NOT NULL,
    steps TEXT NOT NULL,
    expected_outcome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS test_cases (
    id TEXT PRIMARY KEY,
    flow_id TEXT NOT NULL REFERENCES user_flows(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    steps TEXT NOT NULL,
    assertions TEXT NOT NULL,
    confidence REAL DEFAULT 0.0,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_runs (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES applications(id),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    errored INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS test_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES test_runs(id),
    test_case_id TEXT NOT NULL REFERENCES test_cases(id),
    test_name TEXT,
    category TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    step_results TEXT,
    assertion_results TEXT,
    error_detail TEXT,
    failure_screenshot TEXT
);

CREATE TABLE IF NOT EXISTS llm_cache (
    input_hash TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
