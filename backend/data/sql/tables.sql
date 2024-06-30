-- Drop existing tables if they exist
DROP TABLE IF EXISTS sites;
DROP TABLE IF EXISTS cards;
DROP TABLE IF EXISTS card_list;

-- Create sites table
CREATE TABLE sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(255) NOT NULL,
    method VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL,
    country VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL
);

-- Create cards table
CREATE TABLE cards (
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