# Multilingual evaluation (SYNTHETIC data)

> Measured on **synthetic, template-generated** text plus a tiny hand-written check set.
> These numbers do **not** show real-world accuracy. Regenerate with
> `python -m ml.evaluate_multilingual` (after `python -m ml.train_text_classifier`).

- Text model: `textclf-v1-7f49156483` (trained on English only)
- Translator: `wordlist-v1` (word-by-word lookup in app/ml/hindi_glossary.py)
- Seed: 42; review threshold: confidence < 0.5

## Language detection

| Language | Rows detected correctly |
|---|---|
| en | 1.000 |
| hi | 1.000 |
| hi-Latn | 1.000 |
| hi-Latn check set | 1.000 |

## Classification

| Rows | n | Accuracy | Macro-F1 | Flagged for review |
|---|---|---|---|---|
| en (unseen templates, no translation needed) | 636 | 0.719 | 0.696 | 0.374 |
| hi without translation | 540 | 0.111 | 0.022 | 1.000 |
| hi with word-list translation | 540 | 0.922 | 0.922 | 0.170 |
| hi-Latn without translation | 540 | 0.307 | 0.290 | 0.776 |
| hi-Latn with word-list translation | 540 | 0.859 | 0.856 | 0.222 |
| hi-Latn check set (new wording), with translation | 18 | 0.778 | 0.778 | 0.222 |

Share of rows with at least one word not in the word list: hi 0.063, hi-Latn 0.817, check set 1.000

## Check set: what the classifier actually read

| Romanised Hindi | English given to the model | Predicted | True |
|---|---|---|---|
| Station par kisi ne meri jeb kaat li | station someone my jeb kaat li | theft | theft |
| Mera wallet gayab hai, lagta hai kisi ne utha liya | my wallet gayab lagta someone utha | theft | theft |
| Ek ladka mujhe ghoor raha hai aur peeche aa raha hai | a ladka me ghoor aur peeche | harassment | harassment |
| Dukaandaar ne mujhe galat tarike se chhua | dukaandaar me galat tarike chhua | harassment | harassment |
| Meri beti behosh ho gayi hai | my beti behosh | theft | medical_emergency |
| Mere pet mein bahut dard ho raha hai aur ulti aa rahi hai | my pet very pain aur ulti | medical_emergency | medical_emergency |
| Hamari car ka accident ho gaya, sir mein chot lagi hai | our car accident sir chot | accident | accident |
| Seedhi se gir gaye, pair toot gaya lagta hai | seedhi fallen knocked down pair toot lagta | accident | accident |
| Mera beta mele mein kahin chala gaya | my beta mele kahin chala | theft | lost_person |
| Hum apne group se bichhad gaye hain | hum my group bichhad | lost_person | lost_person |
| Ek aadmi ATM ke paas sabko dekh raha hai | a man atm near sabko dekh | suspicious_activity | suspicious_activity |
| Gate ke paas ek ajeeb packet rakha hai | gate near a ajeeb packet rakha | natural_disaster | suspicious_activity |
| Zameen hil rahi thi, sab log bahar bhaag gaye | zameen shaking sab people bahar bhaag | suspicious_activity | natural_disaster |
| Nadi ka paani sadak tak aa gaya hai | nadi water road tak | natural_disaster | natural_disaster |
| Restaurant mein aag lag gayi, sab taraf dhuan hai | restaurant fire sab taraf smoke | fire | fire |
| Bijli ke taar se aag nikal rahi hai | bijli taar fire coming out | fire | fire |
| Hotel ne booking cancel kar di, ab kahan rukein? | hotel booking cancel kahan rukein | other | other |
| Auto wale ne double kiraya le liya | auto double kiraya le | other | other |

## How to read this

- The Hindi and romanised Hindi template rows are an OPTIMISTIC upper bound: the word list was written while looking at those templates.
- The check set has only 18 sentences (2 per category), so its accuracy is very uncertain; it mainly shows that new words are lost and how that hurts.
- 'Without translation' shows why the translation step is needed at all.

## Known limitations

- Word-by-word lookup ignores grammar and word order; unknown Hindi words are lost (in romanised Hindi they are kept as they are, which only helps if they are English).
- Only the vocabulary of the demo is covered. A real system would use a proper translation model behind the same Translator interface.
- Mixed-language messages and spelling variants (e.g. 'chori' vs 'chorii') are only partly handled.
