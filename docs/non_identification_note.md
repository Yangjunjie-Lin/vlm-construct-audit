# Non-Identification Example

Let `A` be randomized with values `1=correct` and `0=corrupted`, and let the observed binary
score be `S`.

**DGP T (target-evidence use).** The system parses the proposition, target uptake is
`U_target=A`, its response follows the proposition, and `S=A`.

**DGP Z (shortcut use).** Target uptake is always zero. A lexical/position marker `Z` happens
to equal `A`; the system reads only `Z`, maps it directly to the answer, and again `S=A`.

Both DGPs induce exactly the same joint distribution of `(A,S)`: perfect downstream accuracy
under correct evidence and perfect failure under corruption. They disagree completely about
the target mechanism. Adding a measured uptake question does not identify the distinction if
that question carries the same marker. A marker-balanced intervention or an independently
constructed uptake split can falsify DGP Z, but absence of detected shortcut channels cannot
prove DGP T. Therefore downstream scores alone do not identify evidence-mediated reasoning.

