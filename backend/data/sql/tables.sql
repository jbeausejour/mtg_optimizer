-- Drop existing tables if they exist
DROP TABLE IF EXISTS sites;
DROP TABLE IF EXISTS cards;
DROP TABLE IF EXISTS card_list;

-- Create sites table
CREATE TABLE site (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(255) NOT NULL,
    method VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL,
    country VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL
);

-- Create cards table
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
    price FLOAT NOT NULL
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

-- Create card_list table
CREATE TABLE optimization_result (
    id SERIAL PRIMARY KEY,
    card_names JSON NOT NULL,
    results JSON,
    timestamp DateTime
);

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
    site VARCHAR(100) NOT NULL,
    price FLOAT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scan(id),
    FOREIGN KEY (card_id) REFERENCES card(id)
);