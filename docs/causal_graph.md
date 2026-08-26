# Causal Graph

Required variables are refined rather than conflated:

- `A`: evidence correctness level; `K`: the concrete intervention operator/version.
- `F`: serialization format; `E_U,E_Y`: uptake/downstream elicitation contracts.
- `T`: target propositional content; `Z`: nuisance format/position/lexical cues.
- `U*`: latent target-evidence uptake; `O_U`: observable uptake response.
- `M_U`: uptake scorer; `U_tilde`: observed uptake proxy.
- `Y*`: latent reasoning process; `O_Y`: observable downstream response.
- `M_Y`: downstream scoring operator; `S_Y`: observed downstream score.
- `C`: model, scene, task, and template characteristics.

```text
 A,K ──► T ─────► U* ─────► Y* ─────► O_Y ─────► S_Y
  │      │         │          │          ▲          ▲
  │      │         │          │          │          M_Y
  │      │         └──────────┼─────────►│
  │      └────────────────────┼─────────►│
  └────► Z ───────────────────┼─────────►│
 F,C ─────────────► U*         │          │
 F,C ─────────────► Z          │          E_Y
                               │
 T,Z,U*,C,E_U ───────────────► O_U ─────► U_tilde
                                             ▲
                                             M_U
```

This retains the required high-level relations `A,F,C -> U*`,
`A,F,U*,C -> O_Y`, `E_Y -> O_Y`, and `M_Y,O_Y -> S_Y` while exposing the
otherwise hidden intervention version and shortcut paths. Direct `T/Z -> O_Y` paths are
kept: the DAG does not assume that observed behavior is mediated by the target reasoning
process.

`E` and `M` are distinct. Constrained decoding changes `E` and the distribution of `O`;
it is not a pure measurement operator. Pure measurement effects require fixed stored response
or logit records scored by different `M`. `U_tilde` is post-treatment and cannot be used to
filter individual downstream observations.

