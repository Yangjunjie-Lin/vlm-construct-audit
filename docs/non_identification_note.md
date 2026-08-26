# Non-Identification Example

Let `A=1` denote correct evidence and `A=0` corrupted evidence. Score `S_Y=1` when the
downstream response agrees with the external scene truth.

**DGP T (target-evidence use).** Latent target uptake is `U*=1` under both values of `A`.
The system follows the supplied target proposition, so its downstream response is correct under
`A=1` and wrong under `A=0`: `S_Y=A`.

**DGP Z (shortcut use).** Target uptake is always zero. A nuisance lexical/position marker `Z`
happens to equal `A`; the system reads only `Z` and again yields `S_Y=A`.

Both DGPs induce exactly the same joint distribution of `(A,S_Y)`. They can also yield the same
observed uptake proxy `U_tilde=1` if the uptake question repeats the marker. They disagree
completely about `U*` and `Y*`. Marker-balanced interventions and an independently constructed
uptake split can falsify this particular DGP Z, but cannot prove DGP T against every unmeasured
shortcut. Downstream scores and manipulation checks therefore do not identify target-evidence
mediation or an internal mechanism.

