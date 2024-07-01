
DROP TABLE IF EXISTS magic_sets;

CREATE TABLE magic_sets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    set_name VARCHAR(255) NOT NULL,
    set_code VARCHAR(10) NOT NULL UNIQUE,
    set_symbol VARCHAR(50),
    release_date DATE,
    set_type VARCHAR(50),
    card_count INT,
    is_digital BOOLEAN DEFAULT FALSE,
    UNIQUE (set_name, set_code)
);

INSERT INTO magic_sets (set_name, set_code, set_symbol, release_date, set_type, card_count, is_digital) VALUES
('Limited Edition Alpha', 'LEA', 'ss-lea', '1993-08-05', 'core', 295, FALSE),
('Limited Edition Beta', 'LEB', 'ss-leb', '1993-10-01', 'core', 302, FALSE),
('Unlimited Edition', '2ED', 'ss-2ed', '1993-12-01', 'core', 302, FALSE),
('Revised Edition', '3ED', 'ss-3ed', '1994-04-01', 'core', 306, FALSE),
('Fourth Edition', '4ED', 'ss-4ed', '1995-04-01', 'core', 378, FALSE),
('Fifth Edition', '5ED', 'ss-5ed', '1997-03-24', 'core', 449, FALSE),
('Classic Sixth Edition', '6ED', 'ss-6ed', '1999-04-28', 'core', 350, FALSE),
('Seventh Edition', '7ED', 'ss-7ed', '2001-04-11', 'core', 350, FALSE),
('Eighth Edition', '8ED', 'ss-8ed', '2003-07-28', 'core', 357, FALSE),
('Ninth Edition', '9ED', 'ss-9ed', '2005-07-29', 'core', 359, FALSE),
('Tenth Edition', '10E', 'ss-10e', '2007-07-13', 'core', 383, FALSE),
('Magic 2010', 'M10', 'ss-m10', '2009-07-17', 'core', 249, FALSE),
('Magic 2011', 'M11', 'ss-m11', '2010-07-16', 'core', 249, FALSE),
('Magic 2012', 'M12', 'ss-m12', '2011-07-15', 'core', 249, FALSE),
('Magic 2013', 'M13', 'ss-m13', '2012-07-13', 'core', 249, FALSE),
('Magic 2014', 'M14', 'ss-m14', '2013-07-19', 'core', 249, FALSE),
('Magic 2015', 'M15', 'ss-m15', '2014-07-18', 'core', 269, FALSE),
('Magic Origins', 'ORI', 'ss-ori', '2015-07-17', 'core', 272, FALSE),
('Core Set 2019', 'M19', 'ss-m19', '2018-07-13', 'core', 280, FALSE),
('Core Set 2020', 'M20', 'ss-m20', '2019-07-12', 'core', 280, FALSE),
('Core Set 2021', 'M21', 'ss-m21', '2020-07-03', 'core', 274, FALSE),

-- Early Expansion Sets
('Arabian Nights', 'ARN', 'ss-arn', '1993-12-01', 'expansion', 92, FALSE),
('Antiquities', 'ATQ', 'ss-atq', '1994-03-01', 'expansion', 100, FALSE),
('Legends', 'LEG', 'ss-leg', '1994-06-01', 'expansion', 310, FALSE),
('The Dark', 'DRK', 'ss-drk', '1994-08-01', 'expansion', 119, FALSE),
('Fallen Empires', 'FEM', 'ss-fem', '1994-11-01', 'expansion', 187, FALSE),
('Ice Age', 'ICE', 'ss-ice', '1995-06-01', 'expansion', 383, FALSE),
('Homelands', 'HML', 'ss-hml', '1995-10-01', 'expansion', 140, FALSE),
('Alliances', 'ALL', 'ss-all', '1996-06-10', 'expansion', 199, FALSE),
('Mirage', 'MIR', 'ss-mir', '1996-10-08', 'expansion', 350, FALSE),
('Visions', 'VIS', 'ss-vis', '1997-02-03', 'expansion', 167, FALSE),
('Weatherlight', 'WTH', 'ss-wth', '1997-06-09', 'expansion', 167, FALSE),
('Tempest', 'TMP', 'ss-tmp', '1997-10-14', 'expansion', 350, FALSE),
('Stronghold', 'STH', 'ss-sth', '1998-03-02', 'expansion', 143, FALSE),
('Exodus', 'EXO', 'ss-exo', '1998-06-15', 'expansion', 143, FALSE),

-- Urza Block
('Urza''s Saga', 'USG', 'ss-usg', '1998-10-12', 'expansion', 350, FALSE),
('Urza''s Legacy', 'ULG', 'ss-ulg', '1999-02-15', 'expansion', 143, FALSE),
('Urza''s Destiny', 'UDS', 'ss-uds', '1999-06-07', 'expansion', 143, FALSE),

-- Masques Block
('Mercadian Masques', 'MMQ', 'ss-mmq', '1999-10-04', 'expansion', 350, FALSE),
('Nemesis', 'NEM', 'ss-nem', '2000-02-14', 'expansion', 143, FALSE),
('Prophecy', 'PCY', 'ss-pcy', '2000-06-05', 'expansion', 143, FALSE),

-- Invasion Block
('Invasion', 'INV', 'ss-inv', '2000-10-02', 'expansion', 350, FALSE),
('Planeshift', 'PLS', 'ss-pls', '2001-02-05', 'expansion', 143, FALSE),
('Apocalypse', 'APC', 'ss-apc', '2001-06-04', 'expansion', 143, FALSE),

-- Odyssey Block
('Odyssey', 'ODY', 'ss-ody', '2001-10-01', 'expansion', 350, FALSE),
('Torment', 'TOR', 'ss-tor', '2002-02-04', 'expansion', 143, FALSE),
('Judgment', 'JUD', 'ss-jud', '2002-05-27', 'expansion', 143, FALSE),

-- Onslaught Block
('Onslaught', 'ONS', 'ss-ons', '2002-10-07', 'expansion', 350, FALSE),
('Legions', 'LGN', 'ss-lgn', '2003-02-03', 'expansion', 145, FALSE),
('Scourge', 'SCG', 'ss-scg', '2003-05-26', 'expansion', 143, FALSE),

-- Mirrodin Block
('Mirrodin', 'MRD', 'ss-mrd', '2003-10-02', 'expansion', 306, FALSE),
('Darksteel', 'DST', 'ss-dst', '2004-02-06', 'expansion', 165, FALSE),
('Fifth Dawn', '5DN', 'ss-5dn', '2004-06-04', 'expansion', 165, FALSE),

-- Kamigawa Block
('Champions of Kamigawa', 'CHK', 'ss-chk', '2004-10-01', 'expansion', 306, FALSE),
('Betrayers of Kamigawa', 'BOK', 'ss-bok', '2005-02-04', 'expansion', 165, FALSE),
('Saviors of Kamigawa', 'SOK', 'ss-sok', '2005-06-03', 'expansion', 165, FALSE),

-- Ravnica Block
('Ravnica: City of Guilds', 'RAV', 'ss-rav', '2005-10-07', 'expansion', 306, FALSE),
('Guildpact', 'GPT', 'ss-gpt', '2006-02-03', 'expansion', 165, FALSE),
('Dissension', 'DIS', 'ss-dis', '2006-05-05', 'expansion', 180, FALSE),

-- Time Spiral Block
('Time Spiral', 'TSP', 'ss-tsp', '2006-10-06', 'expansion', 301, FALSE),
('Planar Chaos', 'PLC', 'ss-plc', '2007-02-02', 'expansion', 165, FALSE),
('Future Sight', 'FUT', 'ss-fut', '2007-05-04', 'expansion', 180, FALSE),

-- Lorwyn Block
('Lorwyn', 'LRW', 'ss-lrw', '2007-10-12', 'expansion', 301, FALSE),
('Morningtide', 'MOR', 'ss-mor', '2008-02-01', 'expansion', 150, FALSE),

-- Shadowmoor Block
('Shadowmoor', 'SHM', 'ss-shm', '2008-05-02', 'expansion', 301, FALSE),
('Eventide', 'EVE', 'ss-eve', '2008-07-25', 'expansion', 180, FALSE),

-- Alara Block
('Shards of Alara', 'ALA', 'ss-ala', '2008-10-03', 'expansion', 249, FALSE),
('Conflux', 'CON', 'ss-con', '2009-02-06', 'expansion', 145, FALSE),
('Alara Reborn', 'ARB', 'ss-arb', '2009-04-30', 'expansion', 145, FALSE),

-- Zendikar Block
('Zendikar', 'ZEN', 'ss-zen', '2009-10-02', 'expansion', 249, FALSE),
('Worldwake', 'WWK', 'ss-wwk', '2010-02-05', 'expansion', 145, FALSE),
('Rise of the Eldrazi', 'ROE', 'ss-roe', '2010-04-23', 'expansion', 248, FALSE),

-- Scars of Mirrodin Block
('Scars of Mirrodin', 'SOM', 'ss-som', '2010-10-01', 'expansion', 249, FALSE),
('Mirrodin Besieged', 'MBS', 'ss-mbs', '2011-02-04', 'expansion', 155, FALSE),
('New Phyrexia', 'NPH', 'ss-nph', '2011-05-13', 'expansion', 175, FALSE),

-- Innistrad Block
('Innistrad', 'ISD', 'ss-isd', '2011-09-30', 'expansion', 264, FALSE),
('Dark Ascension', 'DKA', 'ss-dka', '2012-02-03', 'expansion', 158, FALSE),
('Avacyn Restored', 'AVR', 'ss-avr', '2012-05-04', 'expansion', 244, FALSE),

-- Return to Ravnica Block
('Return to Ravnica', 'RTR', 'ss-rtr', '2012-10-05', 'expansion', 274, FALSE),
('Gatecrash', 'GTC', 'ss-gtc', '2013-02-01', 'expansion', 249, FALSE),
('Dragon''s Maze', 'DGM', 'ss-dgm', '2013-05-03', 'expansion', 156, FALSE),

-- Theros Block
('Theros', 'THS', 'ss-ths', '2013-09-27', 'expansion', 249, FALSE),
('Born of the Gods', 'BNG', 'ss-bng', '2014-02-07', 'expansion', 165, FALSE),
('Journey into Nyx', 'JOU', 'ss-jou', '2014-05-02', 'expansion', 165, FALSE),

-- Khans of Tarkir Block
('Khans of Tarkir', 'KTK', 'ss-ktk', '2014-09-26', 'expansion', 269, FALSE),
('Fate Reforged', 'FRF', 'ss-frf', '2015-01-23', 'expansion', 185, FALSE),
('Dragons of Tarkir', 'DTK', 'ss-dtk', '2015-03-27', 'expansion', 264, FALSE),

-- Battle for Zendikar Block
('Battle for Zendikar', 'BFZ', 'ss-bfz', '2015-10-02', 'expansion', 274, FALSE),
('Oath of the Gatewatch', 'OGW', 'ss-ogw', '2016-01-22', 'expansion', 184, FALSE),

-- Shadows over Innistrad Block
('Shadows over Innistrad', 'SOI', 'ss-soi', '2016-04-08', 'expansion', 297, FALSE),
('Eldritch Moon', 'EMN', 'ss-emn', '2016-07-22', 'expansion', 205, FALSE),

-- Kaladesh Block
('Kaladesh', 'KLD', 'ss-kld', '2016-09-30', 'expansion', 264, FALSE),
('Aether Revolt', 'AER', 'ss-aer', '2017-01-20', 'expansion', 184, FALSE),

-- Amonkhet Block
('Amonkhet', 'AKH', 'ss-akh', '2017-04-28', 'expansion', 269, FALSE),
('Hour of Devastation', 'HOU', 'ss-hou', '2017-07-14', 'expansion', 199, FALSE),

-- Ixalan Block
('Ixalan', 'XLN', 'ss-xln', '2017-09-29', 'expansion', 279, FALSE),
('Rivals of Ixalan', 'RIX', 'ss-rix', '2018-01-19', 'expansion', 196, FALSE),

-- Dominaria
('Dominaria', 'DOM', 'ss-dom', '2018-04-27', 'expansion', 269, FALSE),

-- Guilds of Ravnica Block
('Guilds of Ravnica', 'GRN', 'ss-grn', '2018-10-05', 'expansion', 259, FALSE),
('Ravnica Allegiance', 'RNA', 'ss-rna', '2019-01-25', 'expansion', 259, FALSE),
('War of the Spark', 'WAR', 'ss-war', '2019-05-03', 'expansion', 264, FALSE),

-- Recent Sets
('Throne of Eldraine', 'ELD', 'ss-eld', '2019-10-04', 'expansion', 269, FALSE),
('Theros Beyond Death', 'THB', 'ss-thb', '2020-01-24', 'expansion', 254, FALSE),
('Ikoria: Lair of Behemoths', 'IKO', 'ss-iko', '2020-04-24', 'expansion', 274, FALSE),
('Zendikar Rising', 'ZNR', 'ss-znr', '2020-09-25', 'expansion', 280, FALSE),
('Kaldheim', 'KHM', 'ss-khm', '2021-02-05', 'expansion', 285, FALSE),
('Strixhaven: School of Mages', 'STX', 'ss-stx', '2021-04-23', 'expansion', 275, FALSE),
('Adventures in the Forgotten Realms', 'AFR', 'ss-afr', '2021-07-23', 'expansion', 281, FALSE),
('Innistrad: Midnight Hunt', 'MID', 'ss-mid', '2021-09-24', 'expansion', 277, FALSE),
('Innistrad: Crimson Vow', 'VOW', 'ss-vow', '2021-11-19', 'expansion', 277, FALSE),
('Kamigawa: Neon Dynasty', 'NEO', 'ss-neo', '2022-02-18', 'expansion', 302, FALSE),
('Streets of New Capenna', 'SNC', 'ss-snc', '2022-04-29', 'expansion', 281, FALSE),
('Dominaria United', 'DMU', 'ss-dmu', '2022-09-09', 'expansion', 281, FALSE),
('The Brothers'' War', 'BRO', 'ss-bro', '2022-11-18', 'expansion', 287, FALSE),
('Phyrexia: All Will Be One', 'ONE', 'ss-one', '2023-02-10', 'expansion', 271, FALSE),
('March of the Machine', 'MOM', 'ss-mom', '2023-04-21', 'expansion', 281, FALSE),
('March of the Machine: The Aftermath', 'MAT', 'ss-mat', '2023-05-12', 'expansion', 50, FALSE),
('Wilds of Eldraine', 'WOE', 'ss-woe', '2023-09-08', 'expansion', 281, FALSE),
('The Lost Caverns of Ixalan', 'LCI', 'ss-lci', '2023-11-17', 'expansion', 281, FALSE),

-- Supplemental Sets
('Commander 2011', 'CMD', 'ss-cmd', '2011-06-17', 'commander', 78, FALSE),
('Commander 2013', 'C13', 'ss-c13', '2013-11-01', 'commander', 51, FALSE),
('Commander 2014', 'C14', 'ss-c14', '2014-11-07', 'commander', 61, FALSE),
('Commander 2015', 'C15', 'ss-c15', '2015-11-13', 'commander', 56, FALSE),
('Commander 2016', 'C16', 'ss-c16', '2016-11-11', 'commander', 56, FALSE),
('Commander 2017', 'C17', 'ss-c17', '2017-08-25', 'commander', 56, FALSE),
('Commander 2018', 'C18', 'ss-c18', '2018-08-10', 'commander', 59, FALSE),
('Commander 2019', 'C19', 'ss-c19', '2019-08-23', 'commander', 59, FALSE),
('Commander 2020', 'C20', 'ss-c20', '2020-05-15', 'commander', 71, FALSE),
('Commander 2021', 'C21', 'ss-c21', '2021-04-23', 'commander', 81, FALSE),
('Commander Collection: Green', 'CC1', 'ss-cc1', '2020-12-04', 'commander', 8, FALSE),
('Commander Collection: Black', 'CC2', 'ss-cc2', '2022-01-28', 'commander', 8, FALSE),

-- Conspiracy Sets
('Conspiracy', 'CNS', 'ss-cns', '2014-06-06', 'conspiracy', 210, FALSE),
('Conspiracy: Take the Crown', 'CN2', 'ss-cn2', '2016-08-26', 'conspiracy', 221, FALSE),

-- Battlebond
('Battlebond', 'BBD', 'ss-bbd', '2018-06-08', 'draft_innovation', 254, FALSE),

-- Masters Sets
('Modern Masters', 'MMA', 'ss-mma', '2013-06-07', 'masters', 229, FALSE),
('Modern Masters 2015', 'MM2', 'ss-mm2', '2015-05-22', 'masters', 249, FALSE),
('Eternal Masters', 'EMA', 'ss-ema', '2016-06-10', 'masters', 249, FALSE),
('Modern Masters 2017', 'MM3', 'ss-mm3', '2017-03-17', 'masters', 249, FALSE),
('Iconic Masters', 'IMA', 'ss-ima', '2017-11-17', 'masters', 249, FALSE),
('Masters 25', 'A25', 'ss-a25', '2018-03-16', 'masters', 249, FALSE),
('Ultimate Masters', 'UMA', 'ss-uma', '2018-12-07', 'masters', 254, FALSE),
('Double Masters', '2XM', 'ss-2xm', '2020-08-07', 'masters', 332, FALSE),
('Double Masters 2022', '2X2', 'ss-2x2', '2022-07-08', 'masters', 332, FALSE),

-- Un-Sets
('Unglued', 'UGL', 'ss-ugl', '1998-08-11', 'un_set', 88, FALSE),
('Unhinged', 'UNH', 'ss-unh', '2004-11-19', 'un_set', 141, FALSE),
('Unstable', 'UST', 'ss-ust', '2017-12-08', 'un_set', 216, FALSE),
('Unsanctioned', 'UND', 'ss-und', '2020-02-29', 'un_set', 16, FALSE),
('Unfinity', 'UNF', 'ss-unf', '2022-10-07', 'un_set', 259, FALSE),

-- Digital-Only Sets
('Amonkhet Remastered', 'AKR', 'ss-akr', '2020-08-13', 'digital', 338, TRUE),
('Kaladesh Remastered', 'KLR', 'ss-klr', '2020-11-12', 'digital', 301, TRUE),
('Time Spiral Remastered', 'TSR', 'ss-tsr', '2021-03-19', 'digital', 289, TRUE),
('Jumpstart: Historic Horizons', 'J21', 'ss-j21', '2021-08-12', 'digital', 782, TRUE),
('Alchemy: Innistrad', 'Y22', 'ss-y22', '2021-12-09', 'digital', 63, TRUE),
('Alchemy: Kamigawa', 'YNE', 'ss-YNE', '2022-03-17', 'digital', 20, TRUE),
('Alchemy: New Capenna', 'YSN', 'ss-YSN', '2022-06-02', 'digital', 30, TRUE),
('Alchemy Horizons: Baldur''s Gate', 'HBG', 'ss-hbg', '2022-07-07', 'digital', 81, TRUE),

-- Other Special Sets
('Planechase', 'HOP', 'ss-hop', '2009-09-04', 'planechase', 86, FALSE),
('Archenemy', 'ARC', 'ss-arc', '2010-06-18', 'archenemy', 61, FALSE),
('Planechase 2012', 'PC2', 'ss-pc2', '2012-06-01', 'planechase', 86, FALSE),
('Modern Horizons', 'MH1', 'ss-mh1', '2019-06-14', 'draft_innovation', 254, FALSE),
('Modern Horizons 2', 'MH2', 'ss-mh2', '2021-06-18', 'draft_innovation', 303, FALSE),
('Jumpstart', 'JMP', 'ss-jmp', '2020-07-17', 'draft_innovation', 500, FALSE),
('Jumpstart 2022', 'J22', 'ss-j22', '2022-12-02', 'draft_innovation', 500, FALSE),

-- Recent Commander Sets
('Commander Legends', 'CMR', 'ss-cmr', '2020-11-20', 'commander', 361, FALSE),
('Commander Legends: Battle for Baldur''s Gate', 'CLB', 'ss-clb', '2022-06-10', 'commander', 361, FALSE),
('Commander Masters', 'CMM', 'ss-cmm', '2023-08-04', 'commander', 351, FALSE),
('Commander Collection: Red', 'CC3', 'ss-cc3', '2023-03-03', 'commander', 8, FALSE),

-- Other Supplemental Products
('Mystery Booster', 'MB1', 'ss-mb1', '2020-03-13', 'master', 1694, FALSE),
('Universes Beyond: Warhammer 40,000', '40K', 'ss-40k', '2022-10-07', 'commander', 168, FALSE),
('Universes Beyond: Lord of the Rings', 'LTR', 'ss-ltr', '2023-06-23', 'draft_innovation', 280, FALSE),
('Universes Beyond: Doctor Who', 'WHO', 'ss-who', '2023-10-13', 'commander', 192, FALSE),

-- Very Recent Sets
('Murders at Karlov Manor', 'MKM', 'ss-mkm', '2024-02-09', 'expansion', 281, FALSE),
('Fallout', 'FAL', 'ss-fal', '2024-03-08', 'commander', 301, FALSE),
('Outlaws of Thunder Junction', 'OTJ', 'ss-otj', '2024-04-19', 'expansion', 281, FALSE),
('Bloomburrow', 'BLB', 'ss-blb', '2024-07-12', 'expansion', 281, FALSE),

-- Additional Supplemental Sets
('Secret Lair Drop Series', 'SLD', 'ss-sld', '2019-12-02', 'box', NULL, FALSE),
('Signature Spellbook: Jace', 'SS1', 'ss-ss1', '2018-06-15', 'spellbook', 8, FALSE),
('Signature Spellbook: Gideon', 'SS2', 'ss-ss2', '2019-06-28', 'spellbook', 8, FALSE),
('Signature Spellbook: Chandra', 'SS3', 'ss-ss3', '2020-06-26', 'spellbook', 8, FALSE),

-- From the Vault Series (examples)
('From the Vault: Dragons', 'DRB', 'ss-drb', '2008-08-29', 'from_the_vault', 15, FALSE),
('From the Vault: Exiled', 'V09', 'ss-v09', '2009-08-28', 'from_the_vault', 15, FALSE),
('From the Vault: Relics', 'V10', 'ss-v10', '2010-08-27', 'from_the_vault', 15, FALSE),
('From the Vault: Legends', 'V11', 'ss-v11', '2011-08-26', 'from_the_vault', 15, FALSE),
('From the Vault: Realms', 'V12', 'ss-v12', '2012-08-31', 'from_the_vault', 15, FALSE),
('From the Vault: Twenty', 'V13', 'ss-v13', '2013-08-23', 'from_the_vault', 20, FALSE),

-- Duel Decks (examples)
('Duel Decks: Elves vs. Goblins', 'EVG', 'ss-evg', '2007-11-16', 'duel_deck', 120, FALSE),
('Duel Decks: Jace vs. Chandra', 'DD2', 'ss-dd2', '2008-11-07', 'duel_deck', 120, FALSE),
('Duel Decks: Divine vs. Demonic', 'DDC', 'ss-ddc', '2009-04-10', 'duel_deck', 120, FALSE),
('Duel Decks: Garruk vs. Liliana', 'DDD', 'ss-ddd', '2009-10-30', 'duel_deck', 120, FALSE),
('Duel Decks: Phyrexia vs. the Coalition', 'DDE', 'ss-dde', '2010-03-19', 'duel_deck', 120, FALSE);