PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version VALUES('0e4819adbdb2');
CREATE TABLE site (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	url VARCHAR(255) NOT NULL, 
	method VARCHAR(50) NOT NULL, 
	active BOOLEAN NOT NULL, 
	country VARCHAR(50) NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	UNIQUE (url)
);
INSERT INTO site VALUES(1,'atlascollectables','https://www.atlascollectables.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(2,'topdeckhero','https://www.topdeckhero.com/products/multi_search','other',1,'Canada','Primary');
INSERT INTO site VALUES(3,'tome2boutique','https://tome2boutique.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(4,'levalet','https://levalet.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(5,'comichunter','https://comichunter.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(6,'gamekeeperonline','https://www.gamekeeperonline.com/products/multi_search','other',1,'Canada','Primary');
INSERT INTO site VALUES(7,'lesecretdeskorrigans','https://lesecretdeskorrigans.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(8,'godsarena','https://godsarena.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(9,'jeux3dragons','https://jeux3dragons.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(10,'cartamagica','https://cartamagica.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(11,'houseofcards','https://houseofcards.ca/pages/deck-builder','newDeckbuilder',1,'Canada','Primary');
INSERT INTO site VALUES(12,'fusiongamingonline','https://www.fusiongamingonline.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(13,'kanatacg','https://kanatacg.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(14,'acgamesonline','https://acgamesonline.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(15,'collect-edition','https://collect-edition.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(16,'expeditionjeux','https://www.expeditionjeux.com/products/multi_search','other',1,'Canada','Primary');
INSERT INTO site VALUES(17,'magiccave','https://magiccave.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(18,'orchardcitygames','https://orchardcitygames.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(19,'jjcards','https://jjcards.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(20,'dragontcg','https://dragontcg.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Primary');
INSERT INTO site VALUES(21,'firstplayer','https://firstplayer.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(22,'mtgnorth','https://mtgnorth.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(23,'jittedivision','https://jittedivision.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(24,'gamersden','https://gamersden.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(25,'gauntletgamesvictoria','https://gauntletgamesvictoria.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(26,'sequencecomics','https://sequencecomics.crystalcommerce.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(27,'tradingpost','https://tradingpost.roundtabletavern.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(28,'mtg.collect-edition','https://mtg.collect-edition.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(29,'obsidiangames','https://obsidiangames.ca/pages/mtg-deck-builder','other',1,'Canada','Extended');
INSERT INTO site VALUES(30,'mozmagic','https://www.mozmagic.com/products/multi_search','add_to_cart',1,'Canada','Extended');
INSERT INTO site VALUES(31,'a2ztcg','https://a2ztcg.crystalcommerce.com/products/multi_search','add_to_cart',0,'USA','Extended');
INSERT INTO site VALUES(32,'thebeardeddragongames','https://thebeardeddragongames.crystalcommerce.com/products/multi_search','add_to_cart',0,'USA','Extended');
INSERT INTO site VALUES(33,'brainstormgamespdx','https://brainstormgamespdx.crystalcommerce.com/products/multi_search','add_to_cart',0,'USA','Extended');
INSERT INTO site VALUES(34,'thetoytrove','https://www.thetoytrove.com/products/multi_search','add_to_cart',0,'USA','NotWorking');
INSERT INTO site VALUES(35,'noblecards','https://www.noblecards.ca/products/multi_search','add_to_cart',0,'Canada','NoInventory');
INSERT INTO site VALUES(36,'cbagames','https://www.cbagames.com/products/multi_search','add_to_cart',0,'Canada','NoInventory');
INSERT INTO site VALUES(37,'bruteforcemtg','https://www.bruteforcemtg.com/products/multi_search','add_to_cart',0,'Canada','NotWorking');
INSERT INTO site VALUES(38,'everythinggames','https://www.everythinggames.ca/pages/copy-of-faq','newDeckbuilder',0,'Canada','NoInventory');
CREATE TABLE optimization_result (
	id INTEGER NOT NULL, 
	card_names JSON, 
	results JSON, 
	timestamp DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE scan (
	id INTEGER NOT NULL, 
	date DATETIME, 
	PRIMARY KEY (id)
);
INSERT INTO scan VALUES(1,'2024-07-01 23:25:31.068047');
CREATE TABLE scryfall_card_data (
	id INTEGER NOT NULL, 
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
	scan_timestamp DATETIME, 
	purchase_data JSON, 
	PRIMARY KEY (id)
);
CREATE TABLE user_buylist_card (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	edition VARCHAR(255), 
	version VARCHAR(255), 
	foil BOOLEAN, 
	quality VARCHAR(255) NOT NULL, 
	language VARCHAR(255) NOT NULL, 
	quantity INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE marketplace_card (
	id INTEGER NOT NULL, 
	site VARCHAR(255) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	edition VARCHAR(255) NOT NULL, 
	version VARCHAR(255), 
	foil BOOLEAN NOT NULL, 
	quality VARCHAR(255) NOT NULL, 
	language VARCHAR(255) NOT NULL, 
	quantity INTEGER NOT NULL, 
	price FLOAT NOT NULL, 
	set_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_card_set_id FOREIGN KEY(set_id) REFERENCES sets (id)
);
CREATE TABLE _alembic_tmp_scan (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE card_data (
	id INTEGER NOT NULL, 
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
	scan_timestamp DATETIME, purchase_data JSON, 
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS "scan_result" (
	id INTEGER NOT NULL, 
	scan_id INTEGER NOT NULL, 
	card_id INTEGER NOT NULL, 
	site_id INTEGER NOT NULL, 
	price FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(scan_id) REFERENCES scan (id), 
	FOREIGN KEY(card_id) REFERENCES card (id), 
	FOREIGN KEY(site_id) REFERENCES site (id)
);
CREATE TABLE IF NOT EXISTS "card" (
	a INTEGER, 
	set_id INTEGER, 
	CONSTRAINT fk_card_set_id FOREIGN KEY(set_id) REFERENCES sets (id)
);
CREATE TABLE sets (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(10) NOT NULL, 
	tcgplayer_id INTEGER, 
	name VARCHAR(255) NOT NULL, 
	uri VARCHAR(255), 
	scryfall_uri VARCHAR(255), 
	search_uri VARCHAR(255), 
	released_at DATE, 
	set_type VARCHAR(50), 
	card_count INTEGER, 
	printed_size INTEGER, 
	digital BOOLEAN, 
	nonfoil_only BOOLEAN, 
	foil_only BOOLEAN, 
	icon_svg_uri VARCHAR(255), 
	last_updated DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_sets_code UNIQUE (code)
);
COMMIT;
