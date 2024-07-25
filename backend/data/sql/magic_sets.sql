
DROP TABLE IF EXISTS sets;

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

INSERT INTO sets (set_name, set_code, set_symbol, release_date, set_type, card_count, is_digital) VALUES
('Limited Edition Alpha', 'LEA', 'ss-lea', '1993-08-05', 'core', 295, 0),
('Limited Edition Beta', 'LEB', 'ss-leb', '1993-10-01', 'core', 302, 0),
('Unlimited Edition', '2ED', 'ss-2ed', '1993-12-01', 'core', 302, 0),
('Revised Edition', '3ED', 'ss-3ed', '1994-04-01', 'core', 306, 0),
('Fourth Edition', '4ED', 'ss-4ed', '1995-04-01', 'core', 378, 0),
('Fifth Edition', '5ED', 'ss-5ed', '1997-03-24', 'core', 449, 0),
('Classic Sixth Edition', '6ED', 'ss-6ed', '1999-04-28', 'core', 350, 0),
('Seventh Edition', '7ED', 'ss-7ed', '2001-04-11', 'core', 350, 0),
('Eighth Edition', '8ED', 'ss-8ed', '2003-07-28', 'core', 357, 0),
('Ninth Edition', '9ED', 'ss-9ed', '2005-07-29', 'core', 359, 0),
('Tenth Edition', '10E', 'ss-10e', '2007-07-13', 'core', 383, 0),
('Magic 2010', 'M10', 'ss-m10', '2009-07-17', 'core', 249, 0),
('Magic 2011', 'M11', 'ss-m11', '2010-07-16', 'core', 249, 0),
('Magic 2012', 'M12', 'ss-m12', '2011-07-15', 'core', 249, 0),
('Magic 2013', 'M13', 'ss-m13', '2012-07-13', 'core', 249, 0),
('Magic 2014', 'M14', 'ss-m14', '2013-07-19', 'core', 249, 0),
('Magic 2015', 'M15', 'ss-m15', '2014-07-18', 'core', 269, 0),
('Magic Origins', 'ORI', 'ss-ori', '2015-07-17', 'core', 272, 0),
('Core Set 2019', 'M19', 'ss-m19', '2018-07-13', 'core', 280, 0),
('Core Set 2020', 'M20', 'ss-m20', '2019-07-12', 'core', 280, 0),
('Core Set 2021', 'M21', 'ss-m21', '2020-07-03', 'core', 274, 0),

-- Early Expansion Sets
('Arabian Nights', 'ARN', 'ss-arn', '1993-12-01', 'expansion', 92, 0),
('Antiquities', 'ATQ', 'ss-atq', '1994-03-01', 'expansion', 100, 0),
('Legends', 'LEG', 'ss-leg', '1994-06-01', 'expansion', 310, 0),
('The Dark', 'DRK', 'ss-drk', '1994-08-01', 'expansion', 119, 0),
('Fallen Empires', 'FEM', 'ss-fem', '1994-11-01', 'expansion', 187, 0),
('Ice Age', 'ICE', 'ss-ice', '1995-06-01', 'expansion', 383, 0),
('Homelands', 'HML', 'ss-hml', '1995-10-01', 'expansion', 140, 0),
('Alliances', 'ALL', 'ss-all', '1996-06-10', 'expansion', 199, 0),
('Mirage', 'MIR', 'ss-mir', '1996-10-08', 'expansion', 350, 0),
('Visions', 'VIS', 'ss-vis', '1997-02-03', 'expansion', 167, 0),
('Weatherlight', 'WTH', 'ss-wth', '1997-06-09', 'expansion', 167, 0),
('Tempest', 'TMP', 'ss-tmp', '1997-10-14', 'expansion', 350, 0),
('Stronghold', 'STH', 'ss-sth', '1998-03-02', 'expansion', 143, 0),
('Exodus', 'EXO', 'ss-exo', '1998-06-15', 'expansion', 143, 0),

-- Urza Block
('Urza''s Saga', 'USG', 'ss-usg', '1998-10-12', 'expansion', 350, 0),
('Urza''s Legacy', 'ULG', 'ss-ulg', '1999-02-15', 'expansion', 143, 0),
('Urza''s Destiny', 'UDS', 'ss-uds', '1999-06-07', 'expansion', 143, 0),

-- Masques Block
('Mercadian Masques', 'MMQ', 'ss-mmq', '1999-10-04', 'expansion', 350, 0),
('Nemesis', 'NEM', 'ss-nem', '2000-02-14', 'expansion', 143, 0),
('Prophecy', 'PCY', 'ss-pcy', '2000-06-05', 'expansion', 143, 0),

-- Invasion Block
('Invasion', 'INV', 'ss-inv', '2000-10-02', 'expansion', 350, 0),
('Planeshift', 'PLS', 'ss-pls', '2001-02-05', 'expansion', 143, 0),
('Apocalypse', 'APC', 'ss-apc', '2001-06-04', 'expansion', 143, 0),

-- Odyssey Block
('Odyssey', 'ODY', 'ss-ody', '2001-10-01', 'expansion', 350, 0),
('Torment', 'TOR', 'ss-tor', '2002-02-04', 'expansion', 143, 0),
('Judgment', 'JUD', 'ss-jud', '2002-05-27', 'expansion', 143, 0),

-- Onslaught Block
('Onslaught', 'ONS', 'ss-ons', '2002-10-07', 'expansion', 350, 0),
('Legions', 'LGN', 'ss-lgn', '2003-02-03', 'expansion', 145, 0),
('Scourge', 'SCG', 'ss-scg', '2003-05-26', 'expansion', 143, 0),

-- Mirrodin Block
('Mirrodin', 'MRD', 'ss-mrd', '2003-10-02', 'expansion', 306, 0),
('Darksteel', 'DST', 'ss-dst', '2004-02-06', 'expansion', 165, 0),
('Fifth Dawn', '5DN', 'ss-5dn', '2004-06-04', 'expansion', 165, 0),

-- Kamigawa Block
('Champions of Kamigawa', 'CHK', 'ss-chk', '2004-10-01', 'expansion', 306, 0),
('Betrayers of Kamigawa', 'BOK', 'ss-bok', '2005-02-04', 'expansion', 165, 0),
('Saviors of Kamigawa', 'SOK', 'ss-sok', '2005-06-03', 'expansion', 165, 0),

-- Ravnica Block
('Ravnica: City of Guilds', 'RAV', 'ss-rav', '2005-10-07', 'expansion', 306, 0),
('Guildpact', 'GPT', 'ss-gpt', '2006-02-03', 'expansion', 165, 0),
('Dissension', 'DIS', 'ss-dis', '2006-05-05', 'expansion', 180, 0),

-- Time Spiral Block
('Time Spiral', 'TSP', 'ss-tsp', '2006-10-06', 'expansion', 301, 0),
('Planar Chaos', 'PLC', 'ss-plc', '2007-02-02', 'expansion', 165, 0),
('Future Sight', 'FUT', 'ss-fut', '2007-05-04', 'expansion', 180, 0),

-- Lorwyn Block
('Lorwyn', 'LRW', 'ss-lrw', '2007-10-12', 'expansion', 301, 0),
('Morningtide', 'MOR', 'ss-mor', '2008-02-01', 'expansion', 150, 0),

-- Shadowmoor Block
('Shadowmoor', 'SHM', 'ss-shm', '2008-05-02', 'expansion', 301, 0),
('Eventide', 'EVE', 'ss-eve', '2008-07-25', 'expansion', 180, 0),

-- Alara Block
('Shards of Alara', 'ALA', 'ss-ala', '2008-10-03', 'expansion', 249, 0),
('Conflux', 'CON', 'ss-con', '2009-02-06', 'expansion', 145, 0),
('Alara Reborn', 'ARB', 'ss-arb', '2009-04-30', 'expansion', 145, 0),

-- Zendikar Block
('Zendikar', 'ZEN', 'ss-zen', '2009-10-02', 'expansion', 249, 0),
('Worldwake', 'WWK', 'ss-wwk', '2010-02-05', 'expansion', 145, 0),
('Rise of the Eldrazi', 'ROE', 'ss-roe', '2010-04-23', 'expansion', 248, 0),

-- Scars of Mirrodin Block
('Scars of Mirrodin', 'SOM', 'ss-som', '2010-10-01', 'expansion', 249, 0),
('Mirrodin Besieged', 'MBS', 'ss-mbs', '2011-02-04', 'expansion', 155, 0),
('New Phyrexia', 'NPH', 'ss-nph', '2011-05-13', 'expansion', 175, 0),

-- Innistrad Block
('Innistrad', 'ISD', 'ss-isd', '2011-09-30', 'expansion', 264, 0),
('Dark Ascension', 'DKA', 'ss-dka', '2012-02-03', 'expansion', 158, 0),
('Avacyn Restored', 'AVR', 'ss-avr', '2012-05-04', 'expansion', 244, 0),

-- Return to Ravnica Block
('Return to Ravnica', 'RTR', 'ss-rtr', '2012-10-05', 'expansion', 274, 0),
('Gatecrash', 'GTC', 'ss-gtc', '2013-02-01', 'expansion', 249, 0),
('Dragon''s Maze', 'DGM', 'ss-dgm', '2013-05-03', 'expansion', 156, 0),

-- Theros Block
('Theros', 'THS', 'ss-ths', '2013-09-27', 'expansion', 249, 0),
('Born of the Gods', 'BNG', 'ss-bng', '2014-02-07', 'expansion', 165, 0),
('Journey into Nyx', 'JOU', 'ss-jou', '2014-05-02', 'expansion', 165, 0),

-- Khans of Tarkir Block
('Khans of Tarkir', 'KTK', 'ss-ktk', '2014-09-26', 'expansion', 269, 0),
('Fate Reforged', 'FRF', 'ss-frf', '2015-01-23', 'expansion', 185, 0),
('Dragons of Tarkir', 'DTK', 'ss-dtk', '2015-03-27', 'expansion', 264, 0),

-- Battle for Zendikar Block
('Battle for Zendikar', 'BFZ', 'ss-bfz', '2015-10-02', 'expansion', 274, 0),
('Oath of the Gatewatch', 'OGW', 'ss-ogw', '2016-01-22', 'expansion', 184, 0),

-- Shadows over Innistrad Block
('Shadows over Innistrad', 'SOI', 'ss-soi', '2016-04-08', 'expansion', 297, 0),
('Eldritch Moon', 'EMN', 'ss-emn', '2016-07-22', 'expansion', 205, 0),

-- Kaladesh Block
('Kaladesh', 'KLD', 'ss-kld', '2016-09-30', 'expansion', 264, 0),
('Aether Revolt', 'AER', 'ss-aer', '2017-01-20', 'expansion', 184, 0),

-- Amonkhet Block
('Amonkhet', 'AKH', 'ss-akh', '2017-04-28', 'expansion', 269, 0),
('Hour of Devastation', 'HOU', 'ss-hou', '2017-07-14', 'expansion', 199, 0),

-- Ixalan Block
('Ixalan', 'XLN', 'ss-xln', '2017-09-29', 'expansion', 279, 0),
('Rivals of Ixalan', 'RIX', 'ss-rix', '2018-01-19', 'expansion', 196, 0),

-- Dominaria
('Dominaria', 'DOM', 'ss-dom', '2018-04-27', 'expansion', 269, 0),

-- Guilds of Ravnica Block
('Guilds of Ravnica', 'GRN', 'ss-grn', '2018-10-05', 'expansion', 259, 0),
('Ravnica Allegiance', 'RNA', 'ss-rna', '2019-01-25', 'expansion', 259, 0),
('War of the Spark', 'WAR', 'ss-war', '2019-05-03', 'expansion', 264, 0),

-- Recent Sets
('Throne of Eldraine', 'ELD', 'ss-eld', '2019-10-04', 'expansion', 269, 0),
('Theros Beyond Death', 'THB', 'ss-thb', '2020-01-24', 'expansion', 254, 0),
('Ikoria: Lair of Behemoths', 'IKO', 'ss-iko', '2020-04-24', 'expansion', 274, 0),
('Zendikar Rising', 'ZNR', 'ss-znr', '2020-09-25', 'expansion', 280, 0),
('Kaldheim', 'KHM', 'ss-khm', '2021-02-05', 'expansion', 285, 0),
('Strixhaven: School of Mages', 'STX', 'ss-stx', '2021-04-23', 'expansion', 275, 0),
('Adventures in the Forgotten Realms', 'AFR', 'ss-afr', '2021-07-23', 'expansion', 281, 0),
('Innistrad: Midnight Hunt', 'MID', 'ss-mid', '2021-09-24', 'expansion', 277, 0),
('Innistrad: Crimson Vow', 'VOW', 'ss-vow', '2021-11-19', 'expansion', 277, 0),
('Kamigawa: Neon Dynasty', 'NEO', 'ss-neo', '2022-02-18', 'expansion', 302, 0),
('Streets of New Capenna', 'SNC', 'ss-snc', '2022-04-29', 'expansion', 281, 0),
('Dominaria United', 'DMU', 'ss-dmu', '2022-09-09', 'expansion', 281, 0),
('The Brothers'' War', 'BRO', 'ss-bro', '2022-11-18', 'expansion', 287, 0),
('Phyrexia: All Will Be One', 'ONE', 'ss-one', '2023-02-10', 'expansion', 271, 0),
('March of the Machine', 'MOM', 'ss-mom', '2023-04-21', 'expansion', 281, 0),
('March of the Machine: The Aftermath', 'MAT', 'ss-mat', '2023-05-12', 'expansion', 50, 0),
('Wilds of Eldraine', 'WOE', 'ss-woe', '2023-09-08', 'expansion', 281, 0),
('The Lost Caverns of Ixalan', 'LCI', 'ss-lci', '2023-11-17', 'expansion', 281, 0),

-- Supplemental Sets
('Commander 2011', 'CMD', 'ss-cmd', '2011-06-17', 'commander', 78, 0),
('Commander 2013', 'C13', 'ss-c13', '2013-11-01', 'commander', 51, 0),
('Commander 2014', 'C14', 'ss-c14', '2014-11-07', 'commander', 61, 0),
('Commander 2015', 'C15', 'ss-c15', '2015-11-13', 'commander', 56, 0),
('Commander 2016', 'C16', 'ss-c16', '2016-11-11', 'commander', 56, 0),
('Commander 2017', 'C17', 'ss-c17', '2017-08-25', 'commander', 56, 0),
('Commander 2018', 'C18', 'ss-c18', '2018-08-10', 'commander', 59, 0),
('Commander 2019', 'C19', 'ss-c19', '2019-08-23', 'commander', 59, 0),
('Commander 2020', 'C20', 'ss-c20', '2020-05-15', 'commander', 71, 0),
('Commander 2021', 'C21', 'ss-c21', '2021-04-23', 'commander', 81, 0),
('Commander Collection: Green', 'CC1', 'ss-cc1', '2020-12-04', 'commander', 8, 0),
('Commander Collection: Black', 'CC2', 'ss-cc2', '2022-01-28', 'commander', 8, 0),

-- Conspiracy Sets
('Conspiracy', 'CNS', 'ss-cns', '2014-06-06', 'conspiracy', 210, 0),
('Conspiracy: Take the Crown', 'CN2', 'ss-cn2', '2016-08-26', 'conspiracy', 221, 0),

-- Battlebond
('Battlebond', 'BBD', 'ss-bbd', '2018-06-08', 'draft_innovation', 254, 0),

-- Masters Sets
('Modern Masters', 'MMA', 'ss-mma', '2013-06-07', 'masters', 229, 0),
('Modern Masters 2015', 'MM2', 'ss-mm2', '2015-05-22', 'masters', 249, 0),
('Eternal Masters', 'EMA', 'ss-ema', '2016-06-10', 'masters', 249, 0),
('Modern Masters 2017', 'MM3', 'ss-mm3', '2017-03-17', 'masters', 249, 0),
('Iconic Masters', 'IMA', 'ss-ima', '2017-11-17', 'masters', 249, 0),
('Masters 25', 'A25', 'ss-a25', '2018-03-16', 'masters', 249, 0),
('Ultimate Masters', 'UMA', 'ss-uma', '2018-12-07', 'masters', 254, 0),
('Double Masters', '2XM', 'ss-2xm', '2020-08-07', 'masters', 332, 0),
('Double Masters 2022', '2X2', 'ss-2x2', '2022-07-08', 'masters', 332, 0),

-- Un-Sets
('Unglued', 'UGL', 'ss-ugl', '1998-08-11', 'un_set', 88, 0),
('Unhinged', 'UNH', 'ss-unh', '2004-11-19', 'un_set', 141, 0),
('Unstable', 'UST', 'ss-ust', '2017-12-08', 'un_set', 216, 0),
('Unsanctioned', 'UND', 'ss-und', '2020-02-29', 'un_set', 16, 0),
('Unfinity', 'UNF', 'ss-unf', '2022-10-07', 'un_set', 259, 0),

-- Digital-Only Sets
('Amonkhet Remastered', 'AKR', 'ss-akr', '2020-08-13', 'digital', 338, 1),
('Kaladesh Remastered', 'KLR', 'ss-klr', '2020-11-12', 'digital', 301, 1),
('Time Spiral Remastered', 'TSR', 'ss-tsr', '2021-03-19', 'digital', 289, 1),
('Jumpstart: Historic Horizons', 'J21', 'ss-j21', '2021-08-12', 'digital', 782, 1),
('Alchemy: Innistrad', 'Y22', 'ss-y22', '2021-12-09', 'digital', 63, 1),
('Alchemy: Kamigawa', 'YNE', 'ss-YNE', '2022-03-17', 'digital', 20, 1),
('Alchemy: New Capenna', 'YSN', 'ss-YSN', '2022-06-02', 'digital', 30, 1),
('Alchemy Horizons: Baldur''s Gate', 'HBG', 'ss-hbg', '2022-07-07', 'digital', 81, 1),

-- Other Special Sets
('Planechase', 'HOP', 'ss-hop', '2009-09-04', 'planechase', 86, 0),
('Archenemy', 'ARC', 'ss-arc', '2010-06-18', 'archenemy', 61, 0),
('Planechase 2012', 'PC2', 'ss-pc2', '2012-06-01', 'planechase', 86, 0),
('Modern Horizons', 'MH1', 'ss-mh1', '2019-06-14', 'draft_innovation', 254, 0),
('Modern Horizons 2', 'MH2', 'ss-mh2', '2021-06-18', 'draft_innovation', 303, 0),
('Jumpstart', 'JMP', 'ss-jmp', '2020-07-17', 'draft_innovation', 500, 0),
('Jumpstart 2022', 'J22', 'ss-j22', '2022-12-02', 'draft_innovation', 500, 0),

-- Recent Commander Sets
('Commander Legends', 'CMR', 'ss-cmr', '2020-11-20', 'commander', 361, 0),
('Commander Legends: Battle for Baldur''s Gate', 'CLB', 'ss-clb', '2022-06-10', 'commander', 361, 0),
('Commander Masters', 'CMM', 'ss-cmm', '2023-08-04', 'commander', 351, 0),
('Commander Collection: Red', 'CC3', 'ss-cc3', '2023-03-03', 'commander', 8, 0),

-- Other Supplemental Products
('Mystery Booster', 'MB1', 'ss-mb1', '2020-03-13', 'master', 1694, 0),
('Universes Beyond: Warhammer 40,000', '40K', 'ss-40k', '2022-10-07', 'commander', 168, 0),
('Universes Beyond: Lord of the Rings', 'LTR', 'ss-ltr', '2023-06-23', 'draft_innovation', 280, 0),
('Universes Beyond: Doctor Who', 'WHO', 'ss-who', '2023-10-13', 'commander', 192, 0),

-- Very Recent Sets
('Murders at Karlov Manor', 'MKM', 'ss-mkm', '2024-02-09', 'expansion', 281, 0),
('Fallout', 'FAL', 'ss-fal', '2024-03-08', 'commander', 301, 0),
('Outlaws of Thunder Junction', 'OTJ', 'ss-otj', '2024-04-19', 'expansion', 281, 0),
('Bloomburrow', 'BLB', 'ss-blb', '2024-07-12', 'expansion', 281, 0),

-- Additional Supplemental Sets
('Secret Lair Drop Series', 'SLD', 'ss-sld', '2019-12-02', 'box', NULL, 0),
('Signature Spellbook: Jace', 'SS1', 'ss-ss1', '2018-06-15', 'spellbook', 8, 0),
('Signature Spellbook: Gideon', 'SS2', 'ss-ss2', '2019-06-28', 'spellbook', 8, 0),
('Signature Spellbook: Chandra', 'SS3', 'ss-ss3', '2020-06-26', 'spellbook', 8, 0),

-- From the Vault Series (examples)
('From the Vault: Dragons', 'DRB', 'ss-drb', '2008-08-29', 'from_the_vault', 15, 0),
('From the Vault: Exiled', 'V09', 'ss-v09', '2009-08-28', 'from_the_vault', 15, 0),
('From the Vault: Relics', 'V10', 'ss-v10', '2010-08-27', 'from_the_vault', 15, 0),
('From the Vault: Legends', 'V11', 'ss-v11', '2011-08-26', 'from_the_vault', 15, 0),
('From the Vault: Realms', 'V12', 'ss-v12', '2012-08-31', 'from_the_vault', 15, 0),
('From the Vault: Twenty', 'V13', 'ss-v13', '2013-08-23', 'from_the_vault', 20, 0),

-- Duel Decks (examples)
('Duel Decks: Elves vs. Goblins', 'EVG', 'ss-evg', '2007-11-16', 'duel_deck', 120, 0),
('Duel Decks: Jace vs. Chandra', 'DD2', 'ss-dd2', '2008-11-07', 'duel_deck', 120, 0),
('Duel Decks: Divine vs. Demonic', 'DDC', 'ss-ddc', '2009-04-10', 'duel_deck', 120, 0),
('Duel Decks: Garruk vs. Liliana', 'DDD', 'ss-ddd', '2009-10-30', 'duel_deck', 120, 0),
('Duel Decks: Phyrexia vs. the Coalition', 'DDE', 'ss-dde', '2010-03-19', 'duel_deck', 120, 0);