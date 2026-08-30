# Direction P v2 causal graph and claim boundary

```text
scene generator ──> visual first hop (A R1 B) ─┐
                                               ├─> joint prompt ─> semantic CLL ranking ─> Y
bridge treatment ─> textual second hop (B R2 C)┘

model family ────────────────────────────────────────────────────────────────> Y
serialization ───────────────────────────────────────────────────────────────> Y
```

The treatment changes only `R2` in supplied text. The image, entities,
question, semantic candidate set, and option permutation are paired and fixed.
`R2` is absent from the image, so treatment does not cause image–text
consistency. Construct validity, uptake, and measurement are preconditions for
interpreting the paired contrast; none is a mediator to condition on per scene.

The identified target is a protocol-specific behavioral ITT. The graph does not
identify a latent reasoning trace or an internal compositional mechanism.

