-- Hardcore Fashion Store — Full Seed Data
-- Run AFTER: python manage.py migrate
-- Usage: psql -U postgres -d hardcore_fashion -f database/seed_data.sql

-- ── Categories ──────────────────────────────────────────────────────────────
INSERT INTO store_category (name, slug, description) VALUES
  ('T-Shirts',     't-shirts',    'Premium heavyweight graphic tees for the bold.'),
  ('Hoodies',      'hoodies',     'Oversized and statement hoodies built for the streets.'),
  ('Jackets',      'jackets',     'Leather, denim, and bomber jackets with attitude.'),
  ('Trousers',     'trousers',    'Cargo, slim, and wide-leg trousers for every look.'),
  ('Footwear',     'footwear',    'Boots, trainers, and statement shoes.'),
  ('Accessories',  'accessories', 'Belts, chains, caps, and finishing touches.')
ON CONFLICT (slug) DO NOTHING;

-- ── Products ─────────────────────────────────────────────────────────────────
INSERT INTO store_product (name, slug, description, price, stock, is_featured, category_id, created_at, updated_at) VALUES

  -- T-Shirts
  ('Black Skull Tee',
   'black-skull-tee',
   'Heavyweight 280gsm cotton tee featuring a hand-drawn skull graphic on the chest. Relaxed fit, pre-shrunk, and built to last.',
   29.99, 50, TRUE,
   (SELECT id FROM store_category WHERE slug='t-shirts'), NOW(), NOW()),

  ('Gold Crest Tee',
   'gold-crest-tee',
   'Clean black tee with a gold foil Hardcore Fashion crest emblem. Slim fit, 100% organic cotton.',
   34.99, 35, FALSE,
   (SELECT id FROM store_category WHERE slug='t-shirts'), NOW(), NOW()),

  -- Hoodies
  ('Gold Chain Hoodie',
   'gold-chain-hoodie',
   'Oversized 400gsm fleece hoodie with an embroidered gold chain graphic across the chest. Kangaroo pocket, ribbed cuffs.',
   64.99, 30, TRUE,
   (SELECT id FROM store_category WHERE slug='hoodies'), NOW(), NOW()),

  ('Acid Wash Pullover',
   'acid-wash-pullover',
   'Vintage acid-wash effect pullover hoodie in charcoal. Dropped shoulders, raw hem, unisex sizing.',
   54.99, 20, FALSE,
   (SELECT id FROM store_category WHERE slug='hoodies'), NOW(), NOW()),

  -- Jackets
  ('Moto Leather Jacket',
   'moto-leather-jacket',
   'Genuine full-grain leather biker jacket with silver asymmetric zip, quilted shoulders, and snap-button lapels.',
   149.99, 15, TRUE,
   (SELECT id FROM store_category WHERE slug='jackets'), NOW(), NOW()),

  ('Washed Denim Jacket',
   'washed-denim-jacket',
   'Heavy-duty washed black denim jacket with distressed detailing and oversized fit. Two chest pockets.',
   89.99, 25, FALSE,
   (SELECT id FROM store_category WHERE slug='jackets'), NOW(), NOW()),

  -- Trousers
  ('Tactical Cargo Pants',
   'tactical-cargo-pants',
   'Six-pocket tactical cargo trousers in matte black ripstop fabric. Adjustable ankle cuffs, D-ring hardware.',
   74.99, 40, TRUE,
   (SELECT id FROM store_category WHERE slug='trousers'), NOW(), NOW()),

  ('Slim Tapered Joggers',
   'slim-tapered-joggers',
   'Slim-tapered joggers in heavyweight French terry. Elasticated waist with drawstring, zip ankle.',
   49.99, 45, FALSE,
   (SELECT id FROM store_category WHERE slug='trousers'), NOW(), NOW()),

  -- Footwear
  ('Combat Lace-Up Boots',
   'combat-lace-up-boots',
   'Genuine leather combat boots with steel-toe cap, Goodyear welt construction, and chunky lug sole.',
   129.99, 18, TRUE,
   (SELECT id FROM store_category WHERE slug='footwear'), NOW(), NOW()),

  ('High-Top Trainers',
   'high-top-trainers',
   'Vulcanised high-top canvas trainers with gold eyelets and a thick cupsole. Available in black/gold.',
   69.99, 3, FALSE,
   (SELECT id FROM store_category WHERE slug='footwear'), NOW(), NOW()),

  -- Accessories
  ('Studded Leather Belt',
   'studded-leather-belt',
   'Full-grain black leather belt with pyramid stud detailing and a matte gold pin buckle. 35mm width.',
   24.99, 100, FALSE,
   (SELECT id FROM store_category WHERE slug='accessories'), NOW(), NOW()),

  ('Gold Cuban Chain',
   'gold-cuban-chain',
   '18k gold-plated 10mm Cuban link chain, 55cm length. Lobster clasp, tarnish-resistant coating.',
   44.99, 60, TRUE,
   (SELECT id FROM store_category WHERE slug='accessories'), NOW(), NOW())

ON CONFLICT (slug) DO NOTHING;
