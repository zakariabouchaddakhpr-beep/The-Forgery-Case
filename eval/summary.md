# Evaluation results

Run: 2026-10-15 02:23 against http://localhost:5678/webhook

| Metric | Result |
|---|---|
| Turns answered | 11/11 |
| Orchestrator routed to the expected expert | 11/11 |
| Answers containing the key fact(s) | 8/9 |
| Latency median / max (s) | 2.5 / 5.0 |
| Prompt-injection / leak probes passed | 3/3 |
| Malformed requests rejected | 4/4 |

| Expert | Median latency (s) |
|---|---|
| scientist | 2.5 |
| restorer | 2.5 |
| archivist | 1.9 |
| curator | 4.5 |

| Case | Verdict filed | Score | Key experts missed | Second filing refused |
|---|---|---|---|---|
| case_widows_supper | forged | 100 | - | True |
| case_blue_horses_dusk | forged | 100 | - | True |
| case_starry_night | authentic | 100 | - | True |

## Every turn

| Case | Question | Expected | Routed | Facts | s |
|---|---|---|---|---|---|
| case_widows_supper | What is the paint binder made of, and when was that material first available? | scientist | scientist | yes | 4.4 |
| case_widows_supper | What does the X-ray show under the paint? | restorer | restorer | yes | 2.4 |
| case_widows_supper | Who sold the painting, and when did it surface? | archivist | archivist | yes | 2.9 |
| case_widows_supper | Does this fit the painter's other known works? | curator | curator | yes | 5.0 |
| case_blue_horses_dusk | Which white pigment is in the paint sample, and when did it become available? | scientist | scientist | yes | 2.5 |
| case_blue_horses_dusk | How do the white passages behave under UV light? | restorer | restorer | yes | 3.1 |
| case_blue_horses_dusk | What do the sale records say about the 2003 sale? | archivist | archivist | no | 1.8 |
| case_blue_horses_dusk | Is the style consistent with Moll's other paintings? | curator | curator | yes | 3.9 |
| case_starry_night | Is cobalt blue consistent with a painting from 1889? | scientist | scientist | yes | 2.0 |
| case_starry_night | What do the dark patches under UV mean? | restorer | restorer | yes | 2.5 |
| case_starry_night | How did the painting reach the museum? | archivist | archivist | yes | 1.9 |
