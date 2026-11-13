-- The Forgery Case: game state + Scientist reference tables + sealed truth.
-- Runs once, on the first start of the postgres container.

-- ---------- game state ----------
CREATE TABLE sessions (
  session_id   text PRIMARY KEY,
  case_id      text NOT NULL,
  actions_used int  NOT NULL DEFAULT 0,
  verdict      text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- every expert turn; the Curator reads this as its case history
CREATE TABLE case_interactions (
  id             serial PRIMARY KEY,
  session_id     text NOT NULL REFERENCES sessions(session_id),
  case_id        text NOT NULL,
  turn_index     int  NOT NULL,
  agent          text NOT NULL,
  player_message text NOT NULL,
  agent_reply    jsonb NOT NULL,          -- {content, summary, sources, caveats, details}
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON case_interactions (session_id, turn_index);

-- ---------- Scientist reference data (was n8n Data Tables "cases" / "materials") ----------
CREATE TABLE cases (
  case_id text PRIMARY KEY,
  claimed_start int, claimed_end int,
  provenance_start int, provenance_end int,
  radiocarbon_start int, radiocarbon_end int,
  stylistic_start int, stylistic_end int
);
INSERT INTO cases VALUES
  ('case_starry_night',     1889, 1889, 1889, 2026, 1860, 1900, 1880, 1895),
  ('case_widows_supper',    1650, 1700, 1650, 1700, 1640, 1710, 1650, 1700),
  ('case_blue_horses_dusk', 1914, 1914, 1910, 1920, 1900, 1930, 1910, 1918);

CREATE TABLE materials (
  material        text PRIMARY KEY,
  first_available int  NOT NULL,
  source          text NOT NULL DEFAULT 'verify'  -- approximate literature values, check before the report
);
INSERT INTO materials (material, first_available) VALUES
  ('phenolformaldehyde_resin', 1907), ('titanium_white', 1921), ('zinc_white', 1834),
  ('cobalt_blue', 1802), ('synthetic_ultramarine', 1826), ('emerald_green', 1814),
  ('chrome_yellow', 1809), ('prussian_blue', 1706), ('lead_white', -3000);

-- ---------- SEALED ground truth ----------
-- Read ONLY by the Game workflow's verdict scorer. No agent workflow queries this table.
CREATE TABLE case_truth (
  case_id        text PRIMARY KEY,
  verdict        text NOT NULL CHECK (verdict IN ('authentic', 'forged', 'inconclusive')),
  key_agents     text[] NOT NULL,   -- experts whose findings carry the case
  explanation    text NOT NULL,
  red_herrings   text NOT NULL
);
INSERT INTO case_truth VALUES
  ('case_starry_night', 'authentic', ARRAY['scientist','archivist','restorer'],
   'Every date window agrees: cobalt blue (from 1802) fits 1889, the provenance runs unbroken to the 1941 museum acquisition, and the plates show heavy impasto and a natural, irregular crack network under aged varnish. Nothing in the evidence contradicts the attribution.',
   'Small dark retouchings under UV are ordinary later conservation, not a sign of fabrication.'),
  ('case_widows_supper', 'forged', ARRAY['scientist','restorer'],
   'The paint is bound in phenolformaldehyde resin, which did not exist before 1907: a 207-year gap with the claimed 1650-1700 date. The X-ray shows an unrelated earlier composition under the paint (a genuine period canvas scraped and reused, which is also why radiocarbon fits), the UV shows no aged-varnish fluorescence, and the craquelure is uniform and filled with dark material, as produced by baking.',
   'The public endorsement by a respected period expert carries no physical weight; the matching radiocarbon date only dates the reused canvas.'),
  ('case_blue_horses_dusk', 'forged', ARRAY['restorer','scientist'],
   'The paint sample alone is ambiguous (titanium white 1921 vs zinc white 1834), but the UV plate settles it: the large white passages absorb UV and read dark, the behaviour of titanium white, unavailable until 1921, seven years after the claimed 1914 date. The surface is fresh, with almost no craquelure for a century-old painting.',
   'The zinc-white highlights that glow under UV fit 1914 and are what make the case look plausible.');
