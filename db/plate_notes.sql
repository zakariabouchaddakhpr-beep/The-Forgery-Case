-- The Restorer's conservation file: documented PHYSICAL features of each simulated plate (see tools/make_plates.py).
-- No verdicts, no dates, no material names. x, y, r are fractions of the plate, the same numbers as CLUES in
-- files/game.html; r IS NULL means a whole-plate note. Idempotent: safe to run on every setup, and edits to the
-- rows below reach existing databases (the table is refilled in one transaction).
SET client_min_messages = warning;  -- no NOTICE on stderr when the table already exists
CREATE TABLE IF NOT EXISTS plate_notes (
  id          serial PRIMARY KEY,
  case_id     text NOT NULL,
  kind        text NOT NULL CHECK (kind IN ('xray', 'uv', 'macro', 'raking_light')),
  x           real,
  y           real,
  r           real,
  feature     text NOT NULL,
  description text NOT NULL
);

BEGIN;
DELETE FROM plate_notes;
INSERT INTO plate_notes (case_id, kind, x, y, r, feature, description)
SELECT * FROM (VALUES
  ('case_starry_night', 'uv', NULL::real, NULL::real, NULL::real, 'varnish fluorescence', 'Even greenish fluorescence across the whole surface, the glow of an aged natural-resin varnish.'),
  ('case_starry_night', 'uv', 0.720, 0.121, 0.04, 'dark patch', 'Small dark, sharp-edged patch that does not fluoresce; it sits on top of the glowing varnish (a later retouching).'),
  ('case_starry_night', 'uv', 0.469, 0.519, 0.04, 'dark patch', 'Small dark, sharp-edged patch that does not fluoresce; it sits on top of the glowing varnish (a later retouching).'),
  ('case_starry_night', 'uv', 0.102, 0.422, 0.04, 'dark patch', 'Small dark, sharp-edged patch that does not fluoresce; it sits on top of the glowing varnish (a later retouching).'),
  ('case_starry_night', 'uv', 0.212, 0.110, 0.04, 'dark patch', 'Small dark, sharp-edged patch that does not fluoresce; it sits on top of the glowing varnish (a later retouching).'),
  ('case_starry_night', 'xray', NULL, NULL, NULL, 'brushwork density', 'Dense, lively brushwork; bright where thick light paint was laid on. No forms that differ from the visible composition.'),
  ('case_starry_night', 'macro', NULL, NULL, NULL, 'crack network', 'Irregular, branching crack network with cells of uneven size and dirt-darkened edges.'),
  ('case_starry_night', 'raking_light', NULL, NULL, NULL, 'relief', 'Pronounced relief: thick impasto ridges follow the brushstrokes.'),
  ('case_widows_supper', 'xray', NULL, NULL, NULL, 'hidden forms', 'Under the visible scene the X-ray shows forms that do not match it.'),
  ('case_widows_supper', 'xray', 0.24, 0.55, 0.15, 'large oval form', 'Large bright oval form under the seated figure on the left; its outline follows nothing in the visible painting.'),
  ('case_widows_supper', 'xray', 0.54, 0.15, 0.08, 'straight boundary', 'A straight boundary between a lighter and a darker field, like the horizon of an earlier picture turned on its side by 90 degrees.'),
  ('case_widows_supper', 'uv', NULL, NULL, NULL, 'uniform fluorescence', 'Dull, uniform violet fluorescence; no patchy greenish glow of an aged varnish and no visible retouchings.'),
  ('case_widows_supper', 'macro', NULL, NULL, NULL, 'crack network', 'Very regular, grid-like crack network of near-equal cells; the cracks are filled with a uniform black material and have crisp edges.'),
  ('case_widows_supper', 'raking_light', NULL, NULL, NULL, 'relief', 'Flat, glassy surface with very little relief.'),
  ('case_blue_horses_dusk', 'uv', NULL, NULL, NULL, 'white fluorescence', 'Most white passages fluoresce a bright yellow-green.'),
  ('case_blue_horses_dusk', 'uv', 0.07, 0.40, 0.06, 'dark trunk', 'The white of the left tree trunk absorbs UV and reads almost black-violet, unlike the other whites.'),
  ('case_blue_horses_dusk', 'uv', 0.74, 0.35, 0.06, 'dark trunk', 'The white of the right tree trunk absorbs UV and reads almost black-violet, unlike the other whites.'),
  ('case_blue_horses_dusk', 'xray', NULL, NULL, NULL, 'brushwork density', 'Brushwork consistent with the visible composition; no hidden forms.'),
  ('case_blue_horses_dusk', 'macro', NULL, NULL, NULL, 'crack network', 'Almost no craquelure; the few cracks are fine, faint and short.'),
  ('case_blue_horses_dusk', 'raking_light', NULL, NULL, NULL, 'relief', 'Moderate relief following the brushstrokes.')
) AS v(case_id, kind, x, y, r, feature, description);
COMMIT;
