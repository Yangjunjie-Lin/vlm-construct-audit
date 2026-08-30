# Direction P v2 novelty boundary

Decision: `NOVELTY_PASS_WITH_CAUTION`.

The search was updated through 2026-08-30 using OpenAlex, arXiv, and a focused
web search, with original papers inspected at the title/abstract level. The
strongest boundary is MultiModalQA: it already constructs questions that need
joint reasoning across modalities. WebQA and MuRAG likewise cover multimodal,
multihop evidence aggregation. CLEVR/GQA, Winoground, ARO, CREPE, and
SugarCrepe cover compositional visual reasoning or image-text compositionality.
MMStar explicitly audits whether visual input is indispensable and detects data
leakage. None of these ingredients is new.

Conflict is also prior art and scientifically different. MMMC directly studies
inherent modality conflict. Direction P v2 cannot cite conflict sensitivity as
evidence for complementary bridge composition: its image never depicts the
second hop, so correct and corrupted text remain noncontradictory with visible
facts.

The only defensible candidate contribution is:

> Prospective testing of known-DGP-calibrated behavioral claim certification on
> a VLM intervention construct that is unimodally non-identifiable,
> cross-modally complementary, and free of direct conflict confounding.

This is a conjunction claim. It is not novelty for two-hop relations, synthetic
shapes, multimodal reasoning, cross-modal complementarity, SESOI selection,
Holm correction, the P3 label, leakage-safe generation, or task-specific uptake
gates. It does not establish an internal reasoning mechanism.

The caution is substantive: MultiModalQA is close task-level prior art, while
MMStar and SugarCrepe already motivate modality-necessity and shortcut audits.
A paper must therefore lead with prospective construct-valid intervention and
claim-certification methodology, not with a new multimodal reasoning benchmark.

