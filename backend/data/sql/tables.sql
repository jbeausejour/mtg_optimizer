-- Drop existing tables if they exist
DROP TABLE IF EXISTS scan_result;
DROP TABLE IF EXISTS scan;
DROP TABLE IF EXISTS optimization_result;
DROP TABLE IF EXISTS card_list;
DROP TABLE IF EXISTS card_data;
DROP TABLE IF EXISTS card;
DROP TABLE IF EXISTS site;
DROP TABLE IF EXISTS sets;

-- Create sets table
CREATE TABLE sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_name VARCHAR(255) NOT NULL,
    set_code VARCHAR(10) NOT NULL UNIQUE,
    set_symbol VARCHAR(50),
    release_date DATE,
    set_type VARCHAR(50),
    card_count INTEGER,
    is_digital INTEGER DEFAULT 0,
    UNIQUE (set_name, set_code)
);

-- Create site table
CREATE TABLE site (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    url VARCHAR(255) NOT NULL UNIQUE,
    method VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL,
    country VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL
);

-- Create card table
CREATE TABLE card (
    id SERIAL PRIMARY KEY,
    site VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    edition VARCHAR(255) NOT NULL,
    version VARCHAR(255),
    foil BOOLEAN NOT NULL DEFAULT FALSE,
    quality VARCHAR(255) NOT NULL,
    language VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL,
    price FLOAT NOT NULL,
    set_id INTEGER,
    FOREIGN KEY (set_id) REFERENCES sets(id)
);

-- Create card_data table
CREATE TABLE card_data (
    id SERIAL PRIMARY KEY,
    card_name VARCHAR(255) NOT NULL,
    oracle_id VARCHAR(255) NOT NULL,
    multiverse_ids VARCHAR(255),
    reserved BOOLEAN,
    lang VARCHAR(10),
    set_code VARCHAR(10),
    set_name VARCHAR(255),
    collector_number VARCHAR(20),
    variation BOOLEAN,
    promo BOOLEAN,
    prices JSON,
    purchase_uris JSON,
    cardconduit_data JSON,
    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    purchase_data JSON
);

-- Create card_list table
CREATE TABLE card_list (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    edition VARCHAR(255),
    version VARCHAR(255),
    foil BOOLEAN,
    quality VARCHAR(255) NOT NULL,
    language VARCHAR(255) NOT NULL DEFAULT 'English',
    quantity INTEGER NOT NULL DEFAULT 1
);

-- Create optimization_result table
CREATE TABLE optimization_result (
    id SERIAL PRIMARY KEY,
    card_names JSON NOT NULL,
    results JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create scan table
CREATE TABLE scan (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    card_names JSON NOT NULL
);

-- Create scan_result table
CREATE TABLE scan_result (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    site_id INTEGER NOT NULL,
    price FLOAT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scan(id),
    FOREIGN KEY (card_id) REFERENCES card(id),
    FOREIGN KEY (site_id) REFERENCES site(id)
);

-- Add indexes for frequently accessed columns
CREATE INDEX idx_card_name ON card(name);
CREATE INDEX idx_card_edition ON card(edition);
CREATE INDEX idx_card_price ON card(price);
CREATE INDEX idx_site_name ON site(name);
CREATE INDEX idx_scan_date ON scan(date);
CREATE INDEX idx_sets_set_code ON sets(set_code);

COMMENT ON TABLE card_data IS 'Stores detailed card data from Scryfall and CardConduit';
COMMENT ON TABLE sets IS 'Stores information about Magic: The Gathering card sets';
COMMENT ON TABLE site IS 'Stores information about card-selling websites';
COMMENT ON TABLE card IS 'Stores information about individual Magic cards';
COMMENT ON TABLE card_list IS 'Stores lists of cards for various purposes';
COMMENT ON TABLE optimization_result IS 'Stores results of card optimization processes';
COMMENT ON TABLE scan IS 'Stores information about card scanning processes';
COMMENT ON TABLE scan_result IS 'Stores results of individual card scans';