# Causal Graph

Variables:

- `A`: correctness of supplied evidence.
- `F`: serialization format.
- `E`: elicitation contract shown to the model.
- `U`: latent uptake, or an explicitly measured proxy on an independent split.
- `Y*`: latent target reasoning construct.
- `O`: observable model response.
- `M`: scoring/measurement operator applied to a response.
- `S`: observed score.
- `C`: model, scene, task, and template characteristics.

The working graph is:

```text
                 C ───────┬──────────┬──────────┐
                 │        │          │          │
                 ▼        ▼          ▼          ▼
      A ───────► U ─────► O ───────► S          Y*
      │          ▲        ▲           ▲
      │          │        │           │
      └──────────┼───────►│           M
                 │        │
      F ─────────┴───────►│
                          │
      E ─────────────────►│
```

More precisely: `A,F,C -> U`; `A,F,U,C -> O`; `E -> O`; and `M,O -> S`.
`Y*` motivates the construct but is not identified merely by observing `S`. The graph does
not assume the invalid chain “intervention → uptake → measurement → score.” Measurement
does not causally create uptake, and elicitation may alter the response before scoring.

`E` and `M` are distinct. Constrained decoding belongs to `E` whenever it changes the
distribution of `O`; parsing or rescoring a frozen `O` belongs to `M`. Comparisons between
conditional likelihood and constrained generation therefore include a treatment/elicitation
contrast unless both are computed from one frozen response distribution.

