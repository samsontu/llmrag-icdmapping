# Week 1 — LLM mental model + ICD landscape

> Personal notes, not a polished writeup. Goal: write in your own words. If you can't, you don't understand it yet.

## LLM mental model

- **Tokenization:** ...
- **Attention (one paragraph):** ...
- **Context window vs. parameters (distinct):** ...
- **Training stages:** pretraining → instruction tuning → RLHF / preference tuning.
- **Sampling:** temperature, top-p, what each actually does to the distribution.
- **Pricing model:** input vs. output, prompt caching, why caching matters when you re-use big context.

## ICD landscape

- **ICD-10-CM (US):** clinical modification maintained by CDC/NCHS. ~70k codes. Updated annually.
- **ICD-10 (WHO):** ~14k codes. Different from ICD-10-CM.
- **ICD-11 Foundation:** the canonical semantic network. Multi-parent. ~85k entities.
- **ICD-11 MMS:** the linearization for mortality + morbidity statistics. Hierarchical, single-parent within MMS.
- **Post-coordination:** ICD-11 allows combining a stem code with extension codes (anatomy, laterality, severity, agent, temporal). A single ICD-10-CM code may map to a *cluster* in ICD-11.
- **ICD-11 API:** OAuth 2.0 client-credentials; rate-limited; cache aggressively.

## Open questions to revisit later

- [ ] How do WHO maintain the Foundation versus MMS — what's the source of truth?
- [ ] What's the licensing situation for redistributing ICD-11 content?
- [ ] What's the right granularity to map at — leaf-only, or also blocks?

## Cost recorded for week 1

- [ ] Total LLM spend this week: $___
- [ ] Anthropic vs OpenAI: $___ / $___
