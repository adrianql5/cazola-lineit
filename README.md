# Bank demo

A tiny banking library, used to show how the Earned-Trust review treats
critical code. `src/Bank/Payments/` is declared critical in
`.earned-trust.toml`: any change there is read in full and can only be signed
by its owner. Pull requests into this branch are reviewed by the Earned-Trust
workflow; nothing here is a real bank.
