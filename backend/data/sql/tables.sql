-- Drop existing tables if they exist
DROP TABLE IF EXISTS optimization_results;
DROP TABLE IF EXISTS scan_result;
DROP TABLE IF EXISTS scan;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS site;
DROP TABLE IF EXISTS user_buylist_card;
DROP TABLE IF EXISTS user;

-- Create users table
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128)
);

-- Create site table
CREATE TABLE IF NOT EXISTS site (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) UNIQUE NOT NULL,
    url VARCHAR(255) NOT NULL,
    method VARCHAR(50) NOT NULL,
    active BOOLEAN DEFAULT 1,
    type VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL
);

-- Create settings table
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(255) UNIQUE NOT NULL,
    value VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- Create scan table
CREATE TABLE IF NOT EXISTS scan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME NOT NULL
);

-- Create scan_result table
CREATE TABLE IF NOT EXISTS scan_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    site_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    set_name VARCHAR(255),
    set_code VARCHAR(10),
    language VARCHAR(50) DEFAULT 'English',
    version VARCHAR(255) DEFAULT 'Standard',
    foil BOOLEAN DEFAULT 0,
    quantity INTEGER DEFAULT 0,
    quality VARCHAR(50) DEFAULT 'NM',
    price FLOAT,
    updated_at DATETIME,
    FOREIGN KEY (scan_id) REFERENCES scan(id) ON DELETE CASCADE,
    FOREIGN KEY (site_id) REFERENCES site(id)
);

-- Create user_buylist_card table
CREATE TABLE IF NOT EXISTS user_buylist_card (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    set_name VARCHAR(255),
    set_code VARCHAR(10),
    language VARCHAR(50) DEFAULT 'English',
    version VARCHAR(255) DEFAULT 'Standard',
    foil BOOLEAN DEFAULT 0,
    quantity INTEGER DEFAULT 1,
    quality VARCHAR(50) DEFAULT 'NM',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

-- Create optimization_results table
CREATE TABLE IF NOT EXISTS optimization_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    message VARCHAR(255),
    sites_scraped INTEGER,
    cards_scraped INTEGER,
    solutions JSON,
    errors JSON,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scan(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_user_email ON user(email);
CREATE INDEX IF NOT EXISTS ix_user_username ON user(username);
CREATE INDEX IF NOT EXISTS idx_site_name ON site(name);
CREATE INDEX IF NOT EXISTS idx_scan_date ON scan(created_at);
CREATE INDEX IF NOT EXISTS idx_scan_result_scan_id ON scan_result(scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_result_site_id ON scan_result(site_id);
CREATE INDEX IF NOT EXISTS idx_user_buylist_card_user_id ON user_buylist_card(user_id);
CREATE INDEX IF NOT EXISTS idx_optimization_results_scan_id ON optimization_results(scan_id);
