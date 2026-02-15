-- Seed database: osiris_test
CREATE DATABASE osiris_test;
\connect osiris_test

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(128) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO users (username, email) VALUES
    ('alice', 'alice@example.com'),
    ('bob', 'bob@example.com'),
    ('carol', 'carol@example.com');

INSERT INTO sessions (user_id, token, expires_at) VALUES
    (1, 'tok_alice_001', NOW() + INTERVAL '24 hours'),
    (2, 'tok_bob_001', NOW() + INTERVAL '12 hours');

-- Seed database: osiris_analytics
CREATE DATABASE osiris_analytics;
\connect osiris_analytics

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO events (event_type, payload) VALUES
    ('page_view', '{"path": "/home", "user_agent": "Mozilla/5.0"}'),
    ('signup', '{"method": "email", "plan": "free"}'),
    ('purchase', '{"amount": 29.99, "currency": "USD", "items": ["pro-plan"]}');
